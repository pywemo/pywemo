"""Representation of a WeMo Dimmer device."""
from .api.long_press import LongPressMixin
from .api.service import RequiredService
from .switch import Switch


class Dimmer(Switch):
    """Representation of a WeMo Dimmer device."""

    def __init__(self, *args, **kwargs):
        """Create a WeMo Dimmer device."""
        Switch.__init__(self, *args, **kwargs)
        self._brightness = None

    @property
    def _required_services(self):
        return super()._required_services + [
            RequiredService(name="basicevent", actions=["SetBinaryState"]),
        ]

    def get_brightness(self, force_update=False):
        """Get brightness from device."""
        self.get_state(force_update)
        return self._brightness

    def set_brightness(self, brightness):
        """Set the brightness of this device to an integer between 1-100."""
        value = int(brightness)
        # WeMo only supports values between 1-100. WeMo will ignore a 0
        # brightness value. If 0 is requested, then turn the light off instead.
        if brightness:
            self.basicevent.SetBinaryState(BinaryState=1, brightness=value)
            self._state = 1
            self._brightness = value
        else:
            self.off()

    def get_state(self, force_update=False):
        """Update the state & brightness for the Dimmer."""
        state = super().get_state(force_update)
        if force_update or self._brightness is None:
            try:
                brightness = int(self.basic_state_params.get("brightness", 0))
            except ValueError:
                brightness = 0
            self._brightness = brightness
        return state

    def subscription_update(self, _type, _param):
        """Update the dimmer attributes due to a subscription update event."""
        if _type == "Brightness":
            try:
                self._brightness = int(_param)
            except ValueError:
                return False
            return True
        return super().subscription_update(_type, _param)


class DimmerV1(Dimmer, LongPressMixin):
    """WeMo Dimmer device that supports long press."""
