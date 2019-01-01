"""
Module to discover WeMo devices.
"""
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


def discover_devices(st=None, max_devices=None, match_mac=None, match_serial=None):
    """ Finds WeMo devices on the local network. """
    st = st or ssdp.ST
    ssdp_entries = ssdp.scan(st, max_entries=max_devices,
                             match_mac=match_mac, match_serial=match_serial)

    wemos = []

    for entry in ssdp_entries:
        if entry.match_device_description(
                {'manufacturer': 'Belkin International Inc.'}):
            mac = entry.description.get('device').get('macAddress')
            device = device_from_description(entry.location, mac)

            if device is not None:
                wemos.append(device)

    return wemos


def device_from_description(description_url, mac):
    """ Returns object representing WeMo device running at host, else None. """
    xml = requests.get(description_url, timeout=10)
    uuid = deviceParser.parseString(xml.content).device.UDN

    if mac is None:
        try:
            mac = deviceParser.parseString(xml.content).device.macAddress
        except:
            LOG.debug(
                'No MAC address was supplied or found in setup xml at: %s.'
                , description_url)

    return device_from_uuid_and_location(uuid, mac, description_url)


def device_from_uuid_and_location(uuid, mac, location):
    """ Tries to determine which device it is based on the uuid. """
    if uuid is None:
        return None
    elif uuid.startswith('uuid:Socket'):
        return Switch(location, mac)
    elif uuid.startswith('uuid:Lightswitch'):
        return LightSwitch(location, mac)
    elif uuid.startswith('uuid:Dimmer'):
        return Dimmer(location, mac)
    elif uuid.startswith('uuid:Insight'):
        return Insight(location, mac)
    elif uuid.startswith('uuid:Sensor'):
        return Motion(location, mac)
    elif uuid.startswith('uuid:Maker'):
        return Maker(location, mac)
    elif uuid.startswith('uuid:Bridge'):
        return Bridge(location, mac)
    elif uuid.startswith('uuid:CoffeeMaker'):
        return CoffeeMaker(location, mac)
    elif uuid.startswith('uuid:Humidifier'):
        return Humidifier(location, mac)
    else:
        return None
