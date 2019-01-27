"""Representation of a WeMo Dimmer device."""
from .switch import Switch


class Dimmer(Switch):
    """Representation of a WeMo Dimmer device."""

    def __init__(self, *args, **kwargs):
        """Create a WeMo Dimmer device."""
        Switch.__init__(self, *args, **kwargs)
        self._brightness = None

    def get_brightness(self, force_update=False):
        """Get brightness from device."""
        if force_update or self._brightness is None:
            try:
                # pylint: disable=maybe-no-member
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

        # pylint: disable=maybe-no-member
        self.basicevent.SetBinaryState(brightness=int(brightness))
        self._brightness = int(brightness)

    def subscription_update(self, _type, _param):
        """Disable subscription updates."""
        return False

    def __repr__(self):
        """Return a string representation of the device."""
        return '<WeMo Dimmer "{name}">'.format(name=self.name)

    @property
    def device_type(self):
        """Return what kind of WeMo this device is."""
        return "Dimmer"
