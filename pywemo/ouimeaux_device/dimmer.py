from .switch import Switch

class Dimmer(Switch):		
    def set_brightness(self, brightness):
        """
        Set the brightness of this device to an integer between 1-100.
        """
        if self.get_state() == 0 or None:
            self.on()

        self.basicevent.SetBinaryState(brightness=int(brightness))
        self._brightness = int(brightness)

    def __repr__(self):
        return '<WeMo Dimmer "{name}">'.format(name=self.name)
