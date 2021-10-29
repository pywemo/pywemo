"""Representation of a WeMo CrockPot device."""
from lxml import etree as et

from pywemo.ouimeaux_device.api.xsd.device import quote_xml

from .switch import Switch
import logging

from enum import IntEnum

# These enums were derived from the CrockPot.basicevent.GetCrockpotState() service call
# Thus these names/values were not chosen randomly and the numbers have meaning.
class CrockPotMode(IntEnum):
    Off  = 0 
    Warm = 50
    Low  = 51
    High = 52

MODE_NAMES = {
    CrockPotMode.Off:  "Turned Off",
    CrockPotMode.Warm: "Warm",
    CrockPotMode.Low:  "Low",
    CrockPotMode.High: "High",
}

class CrockPot(Switch):
    def __init__(self, *args, **kwargs):
        """Create a WeMo CrockPot device."""
        Switch.__init__(self, *args, **kwargs)
        self._attributes = {}

    def update_attributes(self):
        """
        Request state from device
        """
        stateAttributes = self.basicevent.GetCrockpotState()

        # Only update our state on complete updates from the device
        if stateAttributes is not None and stateAttributes["mode"] is not None and stateAttributes["time"] is not None and stateAttributes["cookedTime"] is not None:
            self._attributes = stateAttributes
            self._state = self.mode

    def subscription_update(self, _type, _params):
        """
        Handle reports from device
        """
        if _params is None:
            return False

        if _type == "mode":
            self._attributes['mode'] = str(_params)
            self._state = self.mode
            return True
        elif _type == "time":
            self._attributes['time'] = str(_params)
            return True
        elif _type == "cookedTime":
            self._attributes['cookedTime'] = str(_params)
            return True

        return Switch.subscription_update(self, _type, _params)

    @property
    def mode(self) -> int:
        """Return the mode of the device."""
        return int(self._attributes.get('mode'))

    @property
    def mode_string(self) -> str:
        """Return the mode of the device as a string."""
        return MODE_NAMES.get(self.mode, "Unknown")

    @property
    def remaining_time(self) -> int:
        """Return the remaining time in minutes."""
        return int(self._attributes.get('time'))

    @property
    def cooked_time(self) -> int:
        """Return the cooked time in minutes."""
        return int(self._attributes.get('cookedTime'))

    def get_state(self, force_update=False):
        """
        Returns 0 if off and 1 if on.
        """
        # The base implementation using GetBinaryState doesn't work for CrockPot (always returns 0)
        # so use mode instead.
        if force_update or self.mode is None:
            self.update_attributes()

        return int(self.mode != CrockPotMode.Off)

    def set_state(self, state):
        """
        Set the state of this device to on or off.
        """
        if state:
            self.update_settings(CrockPotMode.High, int(self._attributes.get('time')))
        else:
            self.update_settings(CrockPotMode.Off, 0)
    
    def update_settings(self, mode : CrockPotMode, time : int):
        """
        Update mode and cooking time
        """
        self.basicevent.SetCrockpotState(mode=str(int(mode)), time=str(time))

        # The CrockPot might not be ready - so it's not safe to assume the state is what you just set
        # so re-read it from the device
        self.get_state(True)
