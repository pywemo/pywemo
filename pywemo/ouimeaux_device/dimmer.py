from . import Device


class Dimmer(Device):

    def set_state(self, state):
        """
        Set the state of this device to on or off.
        """
        self.basicevent.SetBinaryState(BinaryState=int(state))
        self._state = int(state)

    def off(self):
        """
        Turn this device off. If already off, will return "Error".
        """
        return self.set_state(0)

    def on(self):
        """
        Turn this device on. If already on, will return "Error".
        """
        return self.set_state(1)

    def toggle(self):
        """
        Toggle the dimmer's state.
        """
        return self.set_state(not self.get_state())
		
    def set_dimmer(self, dimmer):
        """
        Set the dimmer of this device to on or off.
        """
        self.basicevent.SetBinaryState(brightness=int(dimmer))
        self._dimmer = int(dimmer)

    def fifty(self):
        """
        Set the dimmer to 50%.
        """
        return self.set_dimmer(50)

    def __repr__(self):
        return '<WeMo Dimmer "{name}">'.format(name=self.name)