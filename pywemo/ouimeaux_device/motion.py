"""Representation of a WeMo Motion device."""
from . import Device


class Motion(Device):
    """Representation of a WeMo Motion device."""

    def __repr__(self):
        """Return a string representation of the device."""
        return '<WeMo Motion "{name}">'.format(name=self.name)

    @property
    def device_type(self):
        """Return what kind of WeMo this device is."""
        return "Motion"
