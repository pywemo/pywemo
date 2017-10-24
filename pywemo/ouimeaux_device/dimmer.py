from .switch import Switch

class Dimmer(Switch):
    def __init__(self, *args, **kwargs):
        Switch.__init__(self, *args, **kwargs)
        self._brightness = None

    def get_brightness(self, force_update=False):
        """
        Get Brightness From Device
        """
        if force_update or self._brightness is None:
            try:
                brightness = self.basicevent.GetBinaryState().get('brightness')
            except ValueError:
                brightness = 0
            self._brightness = brightness

        return self._brightness

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

    def subscription_update(self, _type, _param):
        return False

    def __repr__(self):
        return '<WeMo Dimmer "{name}">'.format(name=self.name)
