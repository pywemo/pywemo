"""
Module that implements UPNP protocol to discover WeMo devices
"""
import select
import socket
import logging
import datetime as dt

from .ouimeaux_device.insight import Insight
from .ouimeaux_device.lightswitch import LightSwitch
from .ouimeaux_device.motion import Motion
from .ouimeaux_device.switch import Switch

DISCOVER_TIMEOUT = 10

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
SSDP_MX = 1
SSDP_ST = "upnp:rootdevice"

SSDP_REQUEST = 'M-SEARCH * HTTP/1.1\r\n' + \
               'HOST: {}:{:d}\r\n'.format(SSDP_ADDR, SSDP_PORT) + \
               'MAN: "ssdp:discover"\r\n' + \
               'MX: {:d}\r\n'.format(SSDP_MX) + \
               'ST: {}\r\n'.format(SSDP_ST) + \
               '\r\n'


# pylint: disable=too-many-locals, too-many-branches
def discover_devices(max_devices=None, port=54321, timeout=DISCOVER_TIMEOUT):
    """
    Sends a message over the network to discover Chromecasts and returns
    a list of found IP addresses.

    Inspired by Crimsdings
    https://github.com/crimsdings/ChromeCast/blob/master/cc_discovery.py
    """
    # Keep track of devices in dict so we can track unique ones.
    devices = {}

    calc_now = dt.datetime.now
    start = calc_now()

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        sock.bind(('', port))

        sock.sendto(SSDP_REQUEST.encode("ascii"), (SSDP_ADDR, SSDP_PORT))

        sock.setblocking(0)

        while True:
            time_diff = calc_now() - start

            seconds_left = timeout - time_diff.seconds

            if seconds_left <= 0:
                return list(devices.values())

            ready = select.select([sock], [], [], seconds_left)[0]

            if ready:
                response = sock.recv(1024).decode("ascii")

                found_location = found_ua = found_usn = None

                headers = response.split("\r\n\r\n", 1)[0]

                for header in headers.split("\r\n"):
                    parts = header.split(": ", 1)

                    # Headers start with something like 'HTTP/1.1 200 OK'
                    # We cannot split that up in key-value pair, so skip
                    if len(parts) != 2:
                        continue

                    key, value = parts

                    key = key.lower()

                    if key == "location":
                        found_location = value

                    elif key == "x-user-agent":
                        found_ua = value.lower()

                    elif key == "usn":
                        found_usn = value

                if found_location and found_usn and \
                   found_ua == "redsonic" and \
                   found_location not in devices:

                    if found_usn.startswith('uuid:Socket'):
                        cls = Switch
                    elif found_usn.startswith('uuid:Lightswitch'):
                        cls = LightSwitch
                    elif found_usn.startswith('uuid:Insight'):
                        cls = Insight
                    elif found_usn.startswith('uuid:Sensor'):
                        cls = Motion
                    else:
                        cls = None

                    if cls:
                        devices[found_location] = cls(found_location)

                        if max_devices and len(devices) == max_devices:
                            break

    except socket.error:
        logging.getLogger(__name__).exception(
            "Socket error while discovering WeMo devices")

    finally:
        sock.close()

    return list(devices.values())
