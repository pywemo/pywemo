"""
Lightweight Python module to discover and control WeMo devices.
"""

from .ouimeaux_device import Device as WeMoDevice
from .ouimeaux_device.insight import Insight
from .ouimeaux_device.lightswitch import LightSwitch
from .ouimeaux_device.motion import Motion
from .ouimeaux_device.switch import Switch
from .ouimeaux_device.maker import Maker

from .discovery import discover_devices
from .subscribe import SubscriptionRegistry
