"""
Module to discover WeMo devices.
"""
import requests

from . import ssdp
from .ouimeaux_device.insight import Insight
from .ouimeaux_device.lightswitch import LightSwitch
from .ouimeaux_device.motion import Motion
from .ouimeaux_device.switch import Switch
from .ouimeaux_device.maker import Maker
from .ouimeaux_device.api.xsd import device as deviceParser


def discover_devices(st=None, max_devices=None):
    """ Finds WeMo devices on the local network. """
    st = st or ssdp.ST_ROOTDEVICE
    ssdp_entries = ssdp.scan(st, max_entries=max_devices)

    wemos = []

    for entry in ssdp_entries:
        if entry.match_device_description(
                {'manufacturer': 'Belkin International Inc.'}):
            device = device_from_description(entry.location)

            if device is not None:
                wemos.append(device)

    return wemos


def device_from_description(description_url):
    """ Returns object representing WeMo device running at host, else None. """
    try:
        xml = requests.get(description_url, timeout=10)

        uuid = deviceParser.parseString(xml.content).device.UDN

        return device_from_uuid_and_location(uuid, description_url)

    except Exception:  # pylint: disable=broad-except
        return None


def device_from_uuid_and_location(uuid, location):
    """ Tries to determine which device it is based on the uuid. """
    if uuid.startswith('uuid:Socket'):
        return Switch(location)
    elif uuid.startswith('uuid:Lightswitch'):
        return LightSwitch(location)
    elif uuid.startswith('uuid:Insight'):
        return Insight(location)
    elif uuid.startswith('uuid:Sensor'):
        return Motion(location)
    elif uuid.startswith('uuid:Maker'):
        return Maker(location)
    else:
        return None
