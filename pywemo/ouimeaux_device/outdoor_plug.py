"""Representation of a WeMo OutdoorPlug device."""
from .switch import Switch


class OutdoorPlug(Switch):
    """Representation of a WeMo Motion device."""

    def __repr__(self):
        """Return a string representation of the device."""
        return '<WeMo OutdoorPlug "{name}">'.format(name=self.name)

    @property
    def device_type(self):
        """Return what kind of WeMo this device is."""
        return "OutdoorPlug"
