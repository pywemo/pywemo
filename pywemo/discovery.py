"""
Module to discover WeMo devices.
"""

from . import ssdp
from .ouimeaux_device.insight import Insight
from .ouimeaux_device.lightswitch import LightSwitch
from .ouimeaux_device.motion import Motion
from .ouimeaux_device.switch import Switch


def discover_devices(st=None, max_devices=None):
    """ Finds WeMo devices on the local network. """
    ssdp_entries = ssdp.scan(st, max_entries=max_devices)

    wemos = []

    for entry in ssdp_entries:
        st = entry.st

        if st is None:
            continue
        elif st.startswith('uuid:Socket'):
            wemos.append(Switch(entry.location))
        elif st.startswith('uuid:Lightswitch'):
            wemos.append(LightSwitch(entry.location))
        elif st.startswith('uuid:Insight'):
            wemos.append(Insight(entry.location))
        elif st.startswith('uuid:Sensor'):
            wemos.append(Motion(entry.location))

    return wemos
