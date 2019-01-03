"""Module to discover WeMo devices."""
import logging
import requests

from . import ssdp
from .ouimeaux_device.bridge import Bridge
from .ouimeaux_device.insight import Insight
from .ouimeaux_device.lightswitch import LightSwitch
from .ouimeaux_device.dimmer import Dimmer
from .ouimeaux_device.motion import Motion
from .ouimeaux_device.switch import Switch
from .ouimeaux_device.maker import Maker
from .ouimeaux_device.coffeemaker import CoffeeMaker
from .ouimeaux_device.humidifier import Humidifier
from .ouimeaux_device.api.xsd import device as deviceParser

LOG = logging.getLogger(__name__)


def discover_devices(ssdp_st=None, max_devices=None,
                     match_mac=None, match_serial=None,
                     rediscovery_enabled=True):
    """Find WeMo devices on the local network."""
    ssdp_st = ssdp_st or ssdp.ST
    ssdp_entries = ssdp.scan(ssdp_st, max_entries=max_devices,
                             match_mac=match_mac, match_serial=match_serial)

    wemos = []

    for entry in ssdp_entries:
        if entry.match_device_description(
                {'manufacturer': 'Belkin International Inc.'}):
            mac = entry.description.get('device').get('macAddress')
            device = device_from_description(
                description_url=entry.location, mac=mac,
                rediscovery_enabled=rediscovery_enabled)

            if device is not None:
                wemos.append(device)

    return wemos


def device_from_description(description_url, mac, rediscovery_enabled=True):
    """Return object representing WeMo device running at host, else None."""
    xml = requests.get(description_url, timeout=10)
    uuid = deviceParser.parseString(xml.content).device.UDN
    device_mac = mac or deviceParser.parseString(xml.content).device.macAddress

    if device_mac is None:
        LOG.debug(
            'No MAC address was supplied or found in setup xml at: %s.',
            description_url)

    return device_from_uuid_and_location(
        uuid, device_mac, description_url,
        rediscovery_enabled=rediscovery_enabled)


def device_from_uuid_and_location(uuid, mac, location,
                                  rediscovery_enabled=True):
    """Determine device class based on the device uuid."""
    if uuid is None:
        return None
    if uuid.startswith('uuid:Socket'):
        return Switch(url=location, mac=mac,
                      rediscovery_enabled=rediscovery_enabled)
    if uuid.startswith('uuid:Lightswitch'):
        return LightSwitch(url=location, mac=mac,
                           rediscovery_enabled=rediscovery_enabled)
    if uuid.startswith('uuid:Dimmer'):
        return Dimmer(url=location, mac=mac,
                      rediscovery_enabled=rediscovery_enabled)
    if uuid.startswith('uuid:Insight'):
        return Insight(url=location, mac=mac,
                       rediscovery_enabled=rediscovery_enabled)
    if uuid.startswith('uuid:Sensor'):
        return Motion(url=location, mac=mac,
                      rediscovery_enabled=rediscovery_enabled)
    if uuid.startswith('uuid:Maker'):
        return Maker(url=location, mac=mac,
                     rediscovery_enabled=rediscovery_enabled)
    if uuid.startswith('uuid:Bridge'):
        return Bridge(url=location, mac=mac,
                      rediscovery_enabled=rediscovery_enabled)
    if uuid.startswith('uuid:CoffeeMaker'):
        return CoffeeMaker(url=location, mac=mac,
                           rediscovery_enabled=rediscovery_enabled)
    if uuid.startswith('uuid:Humidifier'):
        return Humidifier(url=location, mac=mac,
                          rediscovery_enabled=rediscovery_enabled)

    return None
