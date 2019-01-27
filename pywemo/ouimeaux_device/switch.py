"""Representation of a WeMo Switch device."""
from . import Device


class Switch(Device):
    """Representation of a WeMo Switch device."""

    def set_state(self, state):
        """Set the state of this device to on or off."""
        # pylint: disable=maybe-no-member
        self.basicevent.SetBinaryState(BinaryState=int(state))
        self._state = int(state)

    def off(self):
        """Turn this device off. If already off, will return "Error"."""
        return self.set_state(0)

    # pylint: disable=invalid-name
    def on(self):
        """Turn this device on. If already on, will return "Error"."""
        return self.set_state(1)

    def toggle(self):
        """Toggle the switch's state."""
        return self.set_state(not self.get_state())

    def __repr__(self):
        """Return a string representation of the device."""
        return '<WeMo Switch "{name}">'.format(name=self.name)

    @property
    def device_type(self):
        """Return what kind of WeMo this device is."""
        return "Humidifier"
