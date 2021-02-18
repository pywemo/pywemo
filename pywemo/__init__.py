"""Lightweight Python module to discover and control WeMo devices."""
# flake8: noqa F401

from .discovery import discover_devices, setup_url_for_address
from .exceptions import PyWeMoException
from .ouimeaux_device import Device as WeMoDevice
from .ouimeaux_device.bridge import Bridge
from .ouimeaux_device.coffeemaker import CoffeeMaker
from .ouimeaux_device.dimmer import Dimmer
from .ouimeaux_device.humidifier import Humidifier
from .ouimeaux_device.insight import Insight
from .ouimeaux_device.lightswitch import LightSwitch
from .ouimeaux_device.maker import Maker
from .ouimeaux_device.motion import Motion
from .ouimeaux_device.switch import Switch
from .subscribe import SubscriptionRegistry
