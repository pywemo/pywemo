from .switch import Switch

class Dimmer(Switch):
    def __init__(self, *args, **kwargs):
        Switch.__init__(self, *args, **kwargs)
        self._brightness = {}

    def get_brightness(self):
        """
        Get brightness from device
        """
        brightness = self.basicevent.GetBinaryState().get('brightness')
        self._brightness = brightness

    def set_brightness(self, brightness):
        """
        Set the brightness of this device to an integer between 1-100.
        Setting the brightness does not turn the light on, so we need
        to check the state of the switch. 
        """
        if brightness == 0:
            if self.get_state() != 0:
                self.off()
        else:
            if self.get_state() == 0:
                    self.on()

        self.basicevent.SetBinaryState(brightness=int(brightness))
        self._brightness = int(brightness)

    def __repr__(self):
        return '<WeMo Dimmer "{name}">'.format(name=self.name)
