"""Representation of a WeMo CoffeeMaker device."""
from __future__ import annotations

from enum import IntEnum
from typing import Any

from .api.attributes import AttributeDevice

_UNKNOWN = -1


# These enums were derived from the
# CoffeeMaker.deviceevent.GetAttributeList() service call
# Thus these names/values were not chosen randomly
# and the numbers have meaning.
class CoffeeMakerMode(IntEnum):
    """Enum to map WeMo modes to human-readable strings."""

    _UNKNOWN = _UNKNOWN
    # pylint: disable=invalid-name
    Refill = 0  # reservoir empty and carafe not in place
    PlaceCarafe = 1  # reservoir has water but carafe not present
    RefillWater = 2  # carafe present but reservoir is empty
    Ready = 3
    Brewing = 4
    Brewed = 5
    CleaningBrewing = 6
    CleaningSoaking = 7
    BrewFailCarafeRemoved = 8

    @classmethod
    def _missing_(cls, value: Any) -> CoffeeMakerMode:
        return cls._UNKNOWN


MODE_NAMES = {
    CoffeeMakerMode.Refill: "Refill",
    CoffeeMakerMode.PlaceCarafe: "PlaceCarafe",
    CoffeeMakerMode.RefillWater: "RefillWater",
    CoffeeMakerMode.Ready: "Ready",
    CoffeeMakerMode.Brewing: "Brewing",
    CoffeeMakerMode.Brewed: "Brewed",
    CoffeeMakerMode.CleaningBrewing: "CleaningBrewing",
    CoffeeMakerMode.CleaningSoaking: "CleaningSoaking",
    CoffeeMakerMode.BrewFailCarafeRemoved: "BrewFailCarafeRemoved",
}


class CoffeeMaker(AttributeDevice):
    """Representation of a WeMo CoffeeMaker device."""

    _state_property = "mode"  # Required by AttributeDevice.

    @property
    def mode(self) -> CoffeeMakerMode:
        """Return the mode of the device."""
        return CoffeeMakerMode(int(self._attributes.get("Mode", _UNKNOWN)))

    @property
    def mode_string(self) -> str:
        """Return the mode of the device as a string."""
        return MODE_NAMES.get(self.mode, "Unknown")

    def get_state(self, force_update: bool = False) -> int:
        """Return 0 if off and 1 if on."""
        # The base implementation using GetBinaryState doesn't work for
        # CoffeeMaker (always returns 0), so use mode instead.
        # Consider the Coffee Maker to be "on" if it's currently brewing.
        return int(super().get_state(force_update) == CoffeeMakerMode.Brewing)

    def set_state(self, state: int) -> None:
        """Set the state of this device to on or off."""
        # CoffeeMaker cannot be turned off remotely, so ignore the request if
        # state is "falsey"
        if state:
            # Coffee Maker always responds with an error if SetBinaryState is
            # called. Use SetAttributes to change the Mode to "Brewing"
            self._set_attributes(("Mode", CoffeeMakerMode.Brewing))
