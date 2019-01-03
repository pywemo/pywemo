"""Representation of a WeMo Motion device."""
from . import Device


class Motion(Device):
    """Representation of a WeMo Motion device."""

    def __repr__(self):
        """Return a string representation of the device."""
        return '<WeMo Motion "{name}">'.format(name=self.name)
