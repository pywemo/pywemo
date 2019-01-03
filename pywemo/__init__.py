"""Lightweight Python module to discover and control WeMo devices."""

from .ouimeaux_device import Device as WeMoDevice  # noqa F401
from .ouimeaux_device.insight import Insight  # noqa F401
from .ouimeaux_device.lightswitch import LightSwitch  # noqa F401
from .ouimeaux_device.dimmer import Dimmer  # noqa F401
from .ouimeaux_device.motion import Motion  # noqa F401
from .ouimeaux_device.switch import Switch  # noqa F401
from .ouimeaux_device.maker import Maker  # noqa F401
from .ouimeaux_device.coffeemaker import CoffeeMaker  # noqa F401
from .ouimeaux_device.bridge import Bridge  # noqa F401
from .ouimeaux_device.humidifier import Humidifier  # noqa F401

from .discovery import discover_devices  # noqa F401
from .subscribe import SubscriptionRegistry  # noqa F401
