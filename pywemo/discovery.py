"""Module to discover WeMo devices."""
import logging
import warnings
from ipaddress import ip_address
from socket import gaierror, gethostbyname

import requests

from . import ssdp
from .exceptions import ActionException, HTTPException
from .ouimeaux_device import UnsupportedDevice, probe_wemo
from .ouimeaux_device.api.service import REQUESTS_TIMEOUT
from .ouimeaux_device.api.xsd import device as deviceParser
from .ouimeaux_device.bridge import Bridge
from .ouimeaux_device.coffeemaker import CoffeeMaker
from .ouimeaux_device.dimmer import Dimmer
from .ouimeaux_device.humidifier import Humidifier
from .ouimeaux_device.insight import Insight
from .ouimeaux_device.lightswitch import LightSwitch
from .ouimeaux_device.maker import Maker
from .ouimeaux_device.motion import Motion
from .ouimeaux_device.outdoor_plug import OutdoorPlug
from .ouimeaux_device.switch import Switch

LOG = logging.getLogger(__name__)


def discover_devices(**kwargs):
    """Find WeMo devices on the local network."""
    wemos = []

    for entry in ssdp.scan(**kwargs):
        if entry.match_device_description(
            {'manufacturer': 'Belkin International Inc.'}
        ):
            try:
                device = device_from_uuid_and_location(
                    entry.udn, entry.location
                )
            except (HTTPException, ActionException) as exc:
                LOG.warning(
                    'Could not connect to device %s (%s)', entry.location, exc
                )
            else:
                wemos.append(device)

    return wemos


def device_from_description(description_url, mac='deprecated'):
    """Return object representing WeMo device running at host, else None."""
    if mac != 'deprecated':
        warnings.warn(
            "The mac argument to device_from_description is deprecated and "
            "will be removed in a future release.",
            DeprecationWarning,
        )
    try:
        xml = requests.get(description_url, timeout=REQUESTS_TIMEOUT)
    except requests.RequestException as err:
        raise HTTPException(err) from err
    parsed = deviceParser.parseString(
        xml.content, silence=True, print_warnings=False
    )
    uuid = parsed.device.UDN

    return device_from_uuid_and_location(uuid, description_url)


def device_from_uuid_and_location(uuid, location):
    """Determine device class based on the device uuid."""
    if not (uuid and location):
        return None
    if uuid.startswith('uuid:Socket'):
        return Switch(location)
    if uuid.startswith('uuid:Lightswitch'):
        return LightSwitch(location)
    if uuid.startswith('uuid:Dimmer'):
        return Dimmer(location)
    if uuid.startswith('uuid:Insight'):
        return Insight(location)
    if uuid.startswith('uuid:Sensor'):
        return Motion(location)
    if uuid.startswith('uuid:Maker'):
        return Maker(location)
    if uuid.startswith('uuid:Bridge'):
        return Bridge(location)
    if uuid.startswith('uuid:CoffeeMaker'):
        return CoffeeMaker(location)
    if uuid.startswith('uuid:Humidifier'):
        return Humidifier(location)
    if uuid.startswith('uuid:OutdoorPlug'):
        return OutdoorPlug(location)
    if uuid.startswith('uuid:'):
        # unsupported device, but if this function was called from
        # discover_devices then this should be a Belkin product and is probably
        # a WeMo product without a custom class yet.  So attempt to return a
        # basic object to allow manual interaction.
        LOG.info(
            'Device with %s is not supported by pywemo, returning '
            'UnsupportedDevice object to allow manual interaction',
            uuid,
        )
        return UnsupportedDevice(location)

    return None


def hostname_lookup(hostname):
    """Resolve a hostname into an IP address."""
    try:
        # The {host} must be resolved to an IP address; if this fails, this
        # will throw a socket.gaierror.
        host_address = gethostbyname(hostname)

        # Reset {host} to the resolved address.
        LOG.debug(
            'Resolved hostname %s to IP address %s.', hostname, host_address
        )
        return host_address

    except gaierror:
        # The {host}-as-hostname did not resolve to an IP address.
        LOG.debug('Could not resolve hostname %s to an IP address.', hostname)
        return hostname


def setup_url_for_address(host, port):
    """Determine setup.xml url for a given host and port pair."""
    # Force hostnames into IP addresses
    try:
        # Attempt to register {host} as an IP address; if this fails ({host} is
        # not an IP address), this will throw a ValueError.
        ip_address(host)
    except ValueError:
        # The provided {host} should be treated as a hostname.
        host = hostname_lookup(host)

    # Automatically determine the port if not provided.
    if not port:
        port = probe_wemo(host)

    if not port:
        return None

    return "http://%s:%s/setup.xml" % (host, port)
