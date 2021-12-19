"""Representation of a WeMo Switch device."""
from . import Device
from .api.service import RequiredService


class Switch(Device):
    """Representation of a WeMo Switch device."""

    @property
    def _required_services(self):
        return super()._required_services + [
            RequiredService(name="basicevent", actions=["SetBinaryState"]),
        ]

    def set_state(self, state):
        """Set the state of this device to on or off."""
        self.basicevent.SetBinaryState(BinaryState=int(state))
        self._state = int(state)

    def off(self):
        """Turn this device off. If already off, will return "Error"."""
        return self.set_state(0)

    def on(self):
        """Turn this device on. If already on, will return "Error"."""
        return self.set_state(1)

    def toggle(self):
        """Toggle the switch's state."""
        return self.set_state(not self.get_state())
