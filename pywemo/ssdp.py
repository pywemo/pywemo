"""Module that implements SSDP protocol."""
import logging
import re
import select
import socket
import threading
import time

from datetime import datetime, timedelta
import xml.etree.ElementTree as XMLElementTree
import requests

from .util import etree_to_dict, interface_addresses

DISCOVER_TIMEOUT = 5

RESPONSE_REGEX = re.compile(r'\n(.*)\: (.*)\r')

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=59)

# Wemo specific urn:
ST = "urn:Belkin:service:basicevent:1"


class SSDP:
    """Controls the scanning of uPnP devices and services and caches output."""

    def __init__(self):
        """Create SSDP object."""
        self.entries = []
        self.last_scan = None
        self._lock = threading.RLock()

    def scan(self):
        """Scan the network."""
        with self._lock:
            self.update()

    def all(self):
        """
        Return all found entries.

        Will scan for entries if not scanned recently.
        """
        with self._lock:
            self.update()

            return list(self.entries)

    # pylint: disable=invalid-name
    def find_by_st(self, st):
        """Return a list of entries that match the ST."""
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
        """Scan for new uPnP devices and services."""
        with self._lock:
            if self.last_scan is None or force_update or \
               datetime.now()-self.last_scan > MIN_TIME_BETWEEN_SCANS:

                self.remove_expired()

                self.entries.extend(
                    entry for entry in scan() + scan(ST)
                    if entry not in self.entries)

                self.last_scan = datetime.now()

    def remove_expired(self):
        """Filter out expired entries."""
        with self._lock:
            self.entries = [entry for entry in self.entries
                            if not entry.is_expired]


class UPNPEntry:
    """Found uPnP entry."""

    DESCRIPTION_CACHE = {'_NO_LOCATION': {}}

    def __init__(self, values):
        """Create a UPNPEntry object."""
        self.values = values
        self.created = datetime.now()

        if 'cache-control' in self.values:
            cache_seconds = int(self.values['cache-control'].split('=')[1])

            self.expires = self.created + timedelta(seconds=cache_seconds)
        else:
            self.expires = None

    @property
    def is_expired(self):
        """Return whether the entry is expired or not."""
        return self.expires is not None and datetime.now() > self.expires

    # pylint: disable=invalid-name
    @property
    def st(self):
        """Return ST value."""
        return self.values.get('st')

    @property
    def location(self):
        """Return location value."""
        return self.values.get('location')

    @property
    def description(self):
        """Return the description from the uPnP entry."""
        url = self.values.get('location', '_NO_LOCATION')

        if url not in UPNPEntry.DESCRIPTION_CACHE:
            try:
                xml = requests.get(url, timeout=10).text

                tree = None
                if xml is not None:
                    tree = XMLElementTree.fromstring(xml)

                if tree is not None:
                    UPNPEntry.DESCRIPTION_CACHE[url] = \
                        etree_to_dict(tree).get('root', {})
                else:
                    UPNPEntry.DESCRIPTION_CACHE[url] = {}

            except requests.RequestException:
                logging.getLogger(__name__).warning(
                    "Error fetching description at %s", url)

                UPNPEntry.DESCRIPTION_CACHE[url] = {}

            except XMLElementTree.ParseError:
                # There used to be a log message here to record an error about
                # malformed XML, but this only happens on non-WeMo devices
                # and can be safely ignored.
                UPNPEntry.DESCRIPTION_CACHE[url] = {}

        return UPNPEntry.DESCRIPTION_CACHE[url]

    def match_device_description(self, values):
        """
        Fetch description and match against it.

        Values should only contain lowercase keys.
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
        """Create a uPnP entry from a response."""
        return UPNPEntry({key.lower(): item for key, item
                          in RESPONSE_REGEX.findall(response)})

    def __eq__(self, other):
        """Equality operator."""
        return (self.__class__ == other.__class__ and
                self.values == other.values)

    def __repr__(self):
        """Return the string representation of the object."""
        return "<UPNPEntry {} - {}>".format(
            self.values.get('st', ''), self.values.get('location', ''))


def build_ssdp_request(ssdp_st, ssdp_mx):
    """Build the standard request to send during SSDP discovery."""
    ssdp_st = ssdp_st or ST
    return "\r\n".join([
        'M-SEARCH * HTTP/1.1',
        'ST: {}'.format(ssdp_st),
        'MX: {:d}'.format(ssdp_mx),
        'MAN: "ssdp:discover"',
        'HOST: 239.255.255.250:1900',
        '', '']).encode('ascii')


def entry_in_entries(entry, entries, mac, serial):
    """Check if a device entry is in a list of device entries."""
    # If we don't have a mac or serial, let's just compare objects instead:
    if mac is None and serial is None:
        return entry in entries

    for item in entries:
        if item.description is not None:
            e_device = item.description.get('device', {})
            e_mac = e_device.get('macAddress')
            e_serial = e_device.get('serialNumber')
        else:
            e_mac = None
            e_serial = None

        if e_mac == mac and e_serial == serial and item.st == entry.st:
            return True

    return False


# pylint: disable=invalid-name,too-many-nested-blocks
def scan(st=None, timeout=DISCOVER_TIMEOUT,
         max_entries=None, match_mac=None, match_serial=None):
    """
    Send a message over the network to discover upnp devices.

    Inspired by Crimsdings
    https://github.com/crimsdings/ChromeCast/blob/master/cc_discovery.py
    """
    ssdp_target = ("239.255.255.250", 1900)

    entries = []

    calc_now = datetime.now
    start = calc_now()

    sockets = []
    try:
        for addr in interface_addresses():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sockets.append(s)
                s.bind((addr, 0))

                # Send 2 separate ssdp requests to mimic wemo app behavior:
                ssdp_request = build_ssdp_request(st, ssdp_mx=1)
                s.sendto(ssdp_request, ssdp_target)

                time.sleep(0.5)

                ssdp_request = build_ssdp_request(st, ssdp_mx=2)
                s.sendto(ssdp_request, ssdp_target)

                s.setblocking(0)
            except socket.error:
                pass

        while sockets:
            time_diff = calc_now() - start

            # pylint: disable=maybe-no-member
            seconds_left = timeout - time_diff.seconds

            if seconds_left <= 0:
                return entries

            ready = select.select(sockets, [], [], seconds_left)[0]

            for sock in ready:
                response = sock.recv(1024).decode("UTF-8", "replace")

                entry = UPNPEntry.from_response(response)
                if entry.description is not None:
                    device = entry.description.get('device', {})
                    mac = device.get('macAddress')
                    serial = device.get('serialNumber')
                else:
                    mac = None
                    serial = None

                # Search for devices
                if (st is not None or
                        match_mac is not None or
                        match_serial is not None):
                    if not entry_in_entries(entry, entries, mac, serial):
                        if match_mac is not None:
                            if match_mac == mac:
                                entries.append(entry)
                        elif match_serial is not None:
                            if match_serial == serial:
                                entries.append(entry)
                        elif st is not None:
                            if st == entry.st:
                                entries.append(entry)
                elif not entry_in_entries(entry, entries, mac, serial):
                    entries.append(entry)

                # Return if we've found the max number of devices
                if max_entries:
                    if len(entries) == max_entries:
                        return entries
    except socket.error:
        logging.getLogger(__name__).exception(
            "Socket error while discovering SSDP devices")
    finally:
        for s in sockets:
            s.close()

    return entries


if __name__ == "__main__":
    from pprint import pprint

    pprint("Scanning UPNP..")
    pprint(scan())
