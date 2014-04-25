"""
Lightweight Python module to discover and control WeMo devices.
"""

from .ouimeaux_device import Device as WeMoDevice
from .ouimeaux_device.insight import Insight
from .ouimeaux_device.lightswitch import LightSwitch
from .ouimeaux_device.motion import Motion
from .ouimeaux_device.switch import Switch

from .upnp import discover_devices, device_from_host
