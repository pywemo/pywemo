"""Representation of a WeMo Motion device."""
from .api.long_press import LongPressMixin
from .switch import Switch


class LightSwitch(Switch, LongPressMixin):
    """Representation of a WeMo Motion device."""
