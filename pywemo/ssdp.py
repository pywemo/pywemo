"""Module that implements SSDP protocol."""
import logging
import re
import select
import socket
import threading
from datetime import datetime, timedelta

import requests
from lxml import etree as et

from .ouimeaux_device.api.long_press import VIRTUAL_DEVICE_UDN
from .util import etree_to_dict, get_ip_address, interface_addresses

DISCOVER_TIMEOUT = 5

LOG = logging.getLogger(__name__)

RESPONSE_REGEX = re.compile(r'\n(.*)\: (.*)\r')

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=59)

MULTICAST_GROUP = "239.255.255.250"
MULTICAST_PORT = 1900

# Wemo specific urn:
ST = "urn:Belkin:service:basicevent:1"

SSDP_REPLY = f"""HTTP/1.1 200 OK
CACHE-CONTROL: max-age=86400
EXT:
LOCATION: http://%s:%d/setup.xml
OPT: "http://schemas.upnp.org/upnp/1/0/"; ns=01
ST: {ST}
USN: {VIRTUAL_DEVICE_UDN}::{ST}

"""  # Newline characters at the the end of SSDP_REPLY are intentional.
SSDP_REPLY = SSDP_REPLY.replace('\n', '\r\n')

SSDP_NOTIFY = f"""NOTIFY * HTTP/1.1
HOST: {MULTICAST_GROUP}:{MULTICAST_PORT}
CACHE-CONTROL: max-age=1800
LOCATION: http://%s:%d/setup.xml
SERVER: Unspecified, UPnP/1.0, Unspecified
NT: {ST}
NTS: ssdp:alive
USN: {VIRTUAL_DEVICE_UDN}::{ST}

"""  # Newline characters at the the end of SSDP_NOTIFY are intentional.
SSDP_NOTIFY = SSDP_NOTIFY.replace('\n', '\r\n')

EXPECTED_ST_HEADER = ("ST: " + ST).encode("UTF-8")
EXPECTED_MAN_HEADER = b'MAN: "ssdp:discover"'


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

    def find_by_st(self, st):
        """Return a list of entries that match the ST."""
        with self._lock:
            self.update()

            return [entry for entry in self.entries if entry.st == st]

    def find_by_device_description(self, values):
        """
        Return a list of entries that match the description.

        Pass in a dict with values to match against the device tag in the
        description.
        """
        with self._lock:
            self.update()

            return [
                entry
                for entry in self.entries
                if entry.match_device_description(values)
            ]

    def update(self, force_update=False):
        """Scan for new uPnP devices and services."""
        with self._lock:
            if (
                self.last_scan is None
                or force_update
                or datetime.now() - self.last_scan > MIN_TIME_BETWEEN_SCANS
            ):

                self.remove_expired()

                self.entries.extend(
                    entry
                    for entry in scan() + scan(ST)
                    if entry not in self.entries
                )

                self.last_scan = datetime.now()

    def remove_expired(self):
        """Filter out expired entries."""
        with self._lock:
            self.entries = [
                entry for entry in self.entries if not entry.is_expired
            ]


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
                for _ in range(3):
                    try:
                        xml = requests.get(url, timeout=10).content

                        tree = None
                        if xml is not None:
                            tree = et.fromstring(xml)

                        if tree is not None:
                            UPNPEntry.DESCRIPTION_CACHE[url] = etree_to_dict(
                                tree
                            ).get('root', {})
                        else:
                            UPNPEntry.DESCRIPTION_CACHE[url] = {}
                        break

                    except requests.RequestException:
                        logging.getLogger(__name__).warning(
                            "Error fetching description at %s", url
                        )
                        UPNPEntry.DESCRIPTION_CACHE[url] = {}

            except et.ParseError:
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

        return all(val == device.get(key) for key, val in values.items())

    @classmethod
    def from_response(cls, response):
        """Create a uPnP entry from a response."""
        return UPNPEntry(
            {
                key.lower(): item
                for key, item in RESPONSE_REGEX.findall(response)
            }
        )

    def __eq__(self, other):
        """Equality operator."""
        return (
            self.__class__ == other.__class__ and self.values == other.values
        )

    def __repr__(self):
        """Return the string representation of the object."""
        return "<UPNPEntry {} - {}>".format(
            self.values.get('st', ''), self.values.get('location', '')
        )


def build_ssdp_request(ssdp_st, ssdp_mx):
    """Build the standard request to send during SSDP discovery."""
    ssdp_st = ssdp_st or ST
    return "\r\n".join(
        [
            'M-SEARCH * HTTP/1.1',
            f'ST: {ssdp_st}',
            f'MX: {ssdp_mx}',
            'MAN: "ssdp:discover"',
            f'HOST: {MULTICAST_GROUP}:{MULTICAST_PORT}',
            '',
            '',
        ]
    ).encode('ascii')


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


def scan(
    st=None,
    timeout=DISCOVER_TIMEOUT,
    max_entries=None,
    match_mac=None,
    match_serial=None,
):
    """
    Send a message over the network to discover upnp devices.

    Inspired by Crimsdings
    https://github.com/crimsdings/ChromeCast/blob/master/cc_discovery.py
    """
    # pylint: disable=too-many-nested-blocks
    ssdp_target = (MULTICAST_GROUP, MULTICAST_PORT)

    entries = []

    calc_now = datetime.now

    ssdp_request = build_ssdp_request(st, ssdp_mx=1)
    sockets = []
    try:
        for addr in interface_addresses():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.bind((addr, 0))
                s.sendto(ssdp_request, ssdp_target)
                sockets.append(s)
            except socket.error:
                pass

        start = calc_now()
        while sockets:
            time_diff = calc_now() - start

            # pylint: disable=maybe-no-member
            seconds_left = max(timeout - time_diff.seconds, 0)

            ready = select.select(sockets, [], [], min(1, seconds_left))[0]
            if not ready:
                # Only check for timeout when there are no more results. Exit
                # if the time has expired, or probe again if there is more
                # time remaining.
                if seconds_left <= 0:
                    return entries
                for s in sockets:
                    s.sendto(ssdp_request, ssdp_target)

            for sock in ready:
                response = sock.recv(1024).decode("UTF-8", "replace")

                # The device could be slow to respond when fetching the
                # description. It is possible that fetching the results for a
                # single device will take longer than the requested timeout.
                entry = UPNPEntry.from_response(response)
                if entry.description is not None:
                    device = entry.description.get('device', {})
                    mac = device.get('macAddress')
                    serial = device.get('serialNumber')
                    services = device.get("serviceList", {}).get("service", [])
                    service_types = [
                        service.get("serviceType")
                        for service in services
                        if isinstance(service, dict)
                    ]
                else:
                    mac = None
                    serial = None
                    service_types = []

                # Search for devices
                if (
                    st is not None
                    or match_mac is not None
                    or match_serial is not None
                ):
                    if not entry_in_entries(entry, entries, mac, serial):
                        if match_mac is not None:
                            if match_mac == mac:
                                entries.append(entry)
                        elif match_serial is not None:
                            if match_serial == serial:
                                entries.append(entry)
                        elif st is not None:
                            if st == entry.st or st in service_types:
                                entries.append(entry)
                elif not entry_in_entries(entry, entries, mac, serial):
                    entries.append(entry)

                # Return if we've found the max number of devices
                if max_entries:
                    if len(entries) == max_entries:
                        return entries
    except socket.error:
        LOG.exception("Socket error while discovering SSDP devices")
    finally:
        for s in sockets:
            s.close()

    return entries


class DiscoveryResponder:
    """Inform Wemo devices of the pywemo virtual Wemo device.

    The DiscoveryResponder informs Wemo devices of the /setup.xml URL for the
    pywemo virtual Wemo device. The virtual device is used for receiving long
    press actions from Wemo devices and is integrated into the
    SubscriptionRegistry HTTP server.

    Wemo devices are informed of the pywemo virtual Wemo device in two ways:

    1. Wemo devices periodically send UPnP M-SEARCH discovery requests for the
    to locate other devices on the network. DiscoveryResponder responds to
    these requests with the URL for the virtual device.

    2. A UPnP NOTIFY message is periodically multicasted by DiscoveryResponder
    to inform Wemo devices on the network of the URL for the virtual device.
    """

    def __init__(self, callback_port: int):
        """Create a server that will respond to WeMo discovery requests.

        Args:
            callback_port: The port for the SubscriptionRegistry HTTP server.
        """
        self.callback_port = callback_port
        self._thread = None
        self._exit = threading.Event()
        self._thread_exception = None
        self._notify_enabled = True  # Only ever set to False in tests.

    def send_notify(self) -> None:
        """Send a UPnP NOTIFY message containing the virtual device URL."""
        ssdp_target = (MULTICAST_GROUP, MULTICAST_PORT)
        for addr in interface_addresses():  # Send on all interfaces.
            callback_addr = (addr, self.callback_port)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.bind((addr, 0))
                sock.sendto(
                    (SSDP_NOTIFY % callback_addr).encode("UTF-8"), ssdp_target
                )
            except socket.error:
                pass
            finally:
                sock.close()

    def respond_to_discovery(self) -> None:
        """Respond to a WeMo discovery request with the virtual device URL."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Join the multicast group on all interfaces.
            group = socket.inet_aton(MULTICAST_GROUP)
            for addr in interface_addresses():
                try:
                    local = socket.inet_aton(addr)
                    sock.setsockopt(
                        socket.IPPROTO_IP,
                        socket.IP_ADD_MEMBERSHIP,
                        group + local,
                    )
                except socket.error:
                    pass

            sock.bind((MULTICAST_GROUP, MULTICAST_PORT))

            next_notify = datetime.min
            while not self._exit.is_set():
                # Periodically send NOTIFY messages.
                now = datetime.now()
                if now > next_notify and self._notify_enabled:
                    next_notify = now + timedelta(minutes=2)
                    self.send_notify()

                # Check for new discovery requests.
                if not select.select([sock], [], [], 1)[0]:
                    continue  # Timeout, no data. Loop again and check for exit
                msg, sock_addr = sock.recvfrom(1024)
                lines = msg.splitlines()
                if len(lines) < 3 or not lines[0].startswith(
                    b"M-SEARCH * HTTP"
                ):
                    continue
                if (
                    EXPECTED_ST_HEADER not in lines
                    or EXPECTED_MAN_HEADER not in lines
                ):
                    continue
                callback_addr = (
                    get_ip_address(sock_addr[0]),
                    self.callback_port,
                )
                try:
                    sock.sendto(
                        (SSDP_REPLY % callback_addr).encode("UTF-8"), sock_addr
                    )
                except socket.error:
                    LOG.exception("Failed to send SSDP reply to %r", sock_addr)
        except Exception as exp:
            self._thread_exception = exp  # Used in the stop() method.
            raise
        finally:
            sock.close()

    def start(self) -> None:
        """Start the server."""
        self._exit.clear()
        self._thread_exception = None
        self._thread = threading.Thread(
            target=self.respond_to_discovery,
            name='Wemo DiscoveryResponder Thread',
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the server."""
        if self._thread:
            self._exit.set()
            self._thread.join()
            self._thread = None
            # Improve visibility of any exceptions that occurred on the thread.
            if self._thread_exception is not None:
                # pylint: disable=raising-bad-type
                raise self._thread_exception


if __name__ == "__main__":
    from pprint import pprint

    pprint("Scanning UPNP..")
    pprint(scan())
