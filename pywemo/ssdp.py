"""
Module that implements SSDP protocol
"""
import re
import select
import socket
import logging
from datetime import datetime, timedelta
import threading
import xml.etree.ElementTree as ElementTree

import requests

from .util import etree_to_dict

DISCOVER_TIMEOUT = SSDP_MX = 5

RESPONSE_REGEX = re.compile(r'\n(.*)\: (.*)\r')

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=59)

# Devices and services
ST_ALL = "ssdp:all"

# Devices only, some devices will only respond to this query
ST_ROOTDEVICE = "upnp:rootdevice"


class SSDP(object):
    """
    Controls the scanning of uPnP devices and services and caches output.
    """

    def __init__(self):
        self.entries = []
        self.last_scan = None
        self._lock = threading.RLock()

    def scan(self):
        """ Scan the network. """
        with self._lock:
            self.update()

    def all(self):
        """
        Returns all found entries.
        Will scan for entries if not scanned recently.
        """
        with self._lock:
            self.update()

            return list(self.entries)

    # pylint: disable=invalid-name
    def find_by_st(self, st):
        """ Return a list of entries that match the ST. """
        with self._lock:
            self.update()

            return [entry for entry in self.entries
                    if entry.st == st]

    def find_by_device_description(self, values):
        """
        Return a list of entries that match the description.
        Pass in a dict with values to match against the device tag in the
        description.
        """
        with self._lock:
            self.update()

            return [entry for entry in self.entries
                    if entry.match_device_description(values)]

    def update(self, force_update=False):
        """ Scans for new uPnP devices and services. """
        with self._lock:
            if self.last_scan is None or force_update or \
               datetime.now()-self.last_scan > MIN_TIME_BETWEEN_SCANS:

                self.remove_expired()

                # Wemo does not respond to a query for all devices+services
                # but only to a query for just root devices.
                self.entries.extend(
                    entry for entry in scan() + scan(ST_ROOTDEVICE)
                    if entry not in self.entries)

                self.last_scan = datetime.now()

    def remove_expired(self):
        """ Filter out expired entries. """
        with self._lock:
            self.entries = [entry for entry in self.entries
                            if not entry.is_expired]


class UPNPEntry(object):
    """ Found uPnP entry. """
    DESCRIPTION_CACHE = {'_NO_LOCATION': {}}

    def __init__(self, values):
        self.values = values
        self.created = datetime.now()

        if 'cache-control' in self.values:
            cache_seconds = int(self.values['cache-control'].split('=')[1])

            self.expires = self.created + timedelta(seconds=cache_seconds)
        else:
            self.expires = None

    @property
    def is_expired(self):
        """ Returns if the entry is expired or not. """
        return self.expires is not None and datetime.now() > self.expires

    # pylint: disable=invalid-name
    @property
    def st(self):
        """ Returns ST value. """
        return self.values.get('st')

    @property
    def location(self):
        """ Return Location value. """
        return self.values.get('location')

    @property
    def description(self):
        """ Returns the description from the uPnP entry. """
        url = self.values.get('location', '_NO_LOCATION')

        if url not in UPNPEntry.DESCRIPTION_CACHE:
            try:
                xml = requests.get(url).text

                tree = None
                if len(xml) > 0:
                    tree = ElementTree.fromstring(xml)

                if tree:
                    UPNPEntry.DESCRIPTION_CACHE[url] = \
                        etree_to_dict(tree).get('root', {})
                else:
                    UPNPEntry.DESCRIPTION_CACHE[url] = None

            except requests.RequestException:
                logging.getLogger(__name__).exception(
                    "Error fetching description at {}".format(url))

                UPNPEntry.DESCRIPTION_CACHE[url] = {}

            except (requests.RequestException, ElementTree.ParseError):
                logging.getLogger(__name__).exception(
                    "Found malformed XML at {}: {}".format(url, xml))

                UPNPEntry.DESCRIPTION_CACHE[url] = {}

        return UPNPEntry.DESCRIPTION_CACHE[url]

    def match_device_description(self, values):
        """
        Fetches description and matches against it.
        values should only contain lowercase keys.
        """

        if self.description is None:
            return False

        device = self.description.get('device')

        if device is None:
            return False

        return all(val == device.get(key)
                   for key, val in values.items())

    @classmethod
    def from_response(cls, response):
        """ Creates a uPnP entry from a response. """
        return UPNPEntry({key.lower(): item for key, item
                          in RESPONSE_REGEX.findall(response)})

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and
                self.values == other.values)

    def __repr__(self):
        return "<UPNPEntry {} - {}>".format(
            self.values.get('st', ''), self.values.get('location', ''))


# pylint: disable=invalid-name
def scan(st=None, timeout=DISCOVER_TIMEOUT, max_entries=None):
    """
    Sends a message over the network to discover upnp devices.

    Inspired by Crimsdings
    https://github.com/crimsdings/ChromeCast/blob/master/cc_discovery.py
    """
    ssdp_st = st or ST_ALL
    ssdp_target = ("239.255.255.250", 1900)
    ssdp_request = "\r\n".join([
        'M-SEARCH * HTTP/1.1',
        'HOST: 239.255.255.250:1900',
        'MAN: "ssdp:discover"',
        'MX: {:d}'.format(SSDP_MX),
        'ST: {}'.format(ssdp_st),
        '', '']).encode('ascii')

    entries = []

    calc_now = datetime.now
    start = calc_now()

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        sock.sendto(ssdp_request, ssdp_target)

        sock.setblocking(0)

        while True:
            time_diff = calc_now() - start

            # pylint: disable=maybe-no-member
            seconds_left = timeout - time_diff.seconds

            if seconds_left <= 0:
                return entries

            ready = select.select([sock], [], [], seconds_left)[0]

            if ready:
                response = sock.recv(1024).decode("ascii")

                entry = UPNPEntry.from_response(response)

                if (st is None or entry.st == st) and entry not in entries:
                    entries.append(entry)

                    if max_entries and len(entries) == max_entries:
                        return entries

    except socket.error:
        logging.getLogger(__name__).exception(
            "Socket error while discovering SSDP devices")

    finally:
        sock.close()

    return entries


if __name__ == "__main__":
    from pprint import pprint

    pprint("Scanning UPNP..")
    pprint(scan())
