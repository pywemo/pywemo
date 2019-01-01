"""Representation of a WeMo Motion device."""
from .switch import Switch


class LightSwitch(Switch):
    """Representation of a WeMo Motion device."""

    def __repr__(self):
        """String representation of the device."""
        return '<WeMo LightSwitch "{name}">'.format(name=self.name)
