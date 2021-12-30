"""Representation of a WeMo Humidifier device."""
from __future__ import annotations

from enum import IntEnum
from typing import Any

from .api.attributes import AttributeDevice

_UNKNOWN = -1


# These enums were derived from Humidifier.deviceevent.GetAttributeList() and
# thus the names/values were not chosen randomly and the numbers have meaning.
class FanMode(IntEnum):
    """Enum to map WeMo FanModes to human-readable strings."""

    _UNKNOWN = _UNKNOWN
    # pylint: disable=invalid-name
    Off = 0  # Fan and device turned off
    Minimum = 1
    Low = 2
    Medium = 3
    High = 4
    Maximum = 5

    @classmethod
    def _missing_(cls, value: Any) -> FanMode:
        return cls._UNKNOWN


FAN_MODE_NAMES = {
    FanMode.Off: "Off",
    FanMode.Minimum: "Minimum",
    FanMode.Low: "Low",
    FanMode.Medium: "Medium",
    FanMode.High: "High",
    FanMode.Maximum: "Maximum",
}


class DesiredHumidity(IntEnum):
    """Enum to map WeMo DesiredHumidity to human-readable strings."""

    _UNKNOWN = _UNKNOWN
    # pylint: disable=invalid-name
    FortyFivePercent = 0
    FiftyPercent = 1
    FiftyFivePercent = 2
    SixtyPercent = 3
    OneHundredPercent = 4  # "Always On" Mode

    @classmethod
    def _missing_(cls, value: Any) -> DesiredHumidity:
        return cls._UNKNOWN


DESIRED_HUMIDITY_NAMES = {
    DesiredHumidity.FortyFivePercent: "45",
    DesiredHumidity.FiftyPercent: "50",
    DesiredHumidity.FiftyFivePercent: "55",
    DesiredHumidity.SixtyPercent: "60",
    DesiredHumidity.OneHundredPercent: "100",
}


class WaterLevel(IntEnum):
    """Enum to map WeMo WaterLevel to human-readable strings."""

    # pylint: disable=invalid-name
    Empty = 0
    Low = 1
    Good = 2


WATER_LEVEL_NAMES = {
    WaterLevel.Empty: "Empty",
    WaterLevel.Low: "Low",
    WaterLevel.Good: "Good",
}

FILTER_LIFE_MAX = 60480


class Humidifier(AttributeDevice):
    """Representation of a WeMo Humidifier device."""

    _state_property = "fan_mode"  # Required by AttributeDevice.

    @property
    def fan_mode(self) -> FanMode:
        """Return the FanMode setting (as an int index of the IntEnum)."""
        return FanMode(int(self._attributes.get("FanMode", _UNKNOWN)))

    @property
    def fan_mode_string(self) -> str:
        """Return the FanMode setting as a string.

        (Off, Low, Medium, High, Maximum).
        """
        return FAN_MODE_NAMES.get(self.fan_mode, "Unknown")

    @property
    def desired_humidity(self) -> DesiredHumidity:
        """Return the desired humidity (as an int index of the IntEnum)."""
        return DesiredHumidity(
            int(self._attributes.get("DesiredHumidity", _UNKNOWN))
        )

    @property
    def desired_humidity_percent(self) -> str:
        """Return the desired humidity in percent (string)."""
        return DESIRED_HUMIDITY_NAMES.get(self.desired_humidity, "Unknown")

    @property
    def current_humidity_percent(self) -> float:
        """Return the observed relative humidity in percent (float)."""
        return float(self._attributes.get("CurrentHumidity", 0.0))

    @property
    def water_level(self) -> WaterLevel:
        """Return 0 if water level is Empty, 1 if Low, and 2 if Good."""
        if self._attributes.get("NoWater") == "1":
            return WaterLevel.Empty
        if self._attributes.get("WaterAdvise") == "1":
            return WaterLevel.Low
        return WaterLevel.Good

    @property
    def water_level_string(self) -> str:
        """Return Empty, Low, or Good depending on the water level."""
        return WATER_LEVEL_NAMES.get(self.water_level, "Unknown")

    @property
    def filter_life_percent(self) -> float:
        """Return the percentage (float) of filter life remaining."""
        filter_life = float(self._attributes.get("FilterLife", 0.0))
        return round(filter_life / float(FILTER_LIFE_MAX) * 100.0, 2)

    @property
    def filter_expired(self) -> bool:
        """Return False if filter is OK, or True if it needs to be changed."""
        return bool(int(self._attributes.get("ExpiredFilterTime", 0)))

    def get_state(self, force_update: bool = False) -> int:
        """Return 0 if off and 1 if on."""
        # The base implementation using GetBinaryState
        # doesn't work for Humidifier (always returns 0)
        # so use fan mode instead.
        # Consider the Humidifier to be "on" if it's not off.
        return int(super().get_state(force_update) != FanMode.Off)

    def set_state(self, state: int) -> None:
        """Set the fan mode of this device.

        Provided for compatibility with the Switch base class.

        Args:
          state: An int index of the FanMode IntEnum.
        """
        self.set_fan_mode(FanMode(state))

    def set_fan_mode(self, fan_mode: FanMode) -> None:
        """Set the fan mode of this device.

        Provided for compatibility with the Switch base class.
        """
        self.set_fan_mode_and_humidity(fan_mode=fan_mode)

    def set_humidity(self, desired_humidity: DesiredHumidity) -> None:
        """Set the desired humidity (as int index of the IntEnum)."""
        self.set_fan_mode_and_humidity(desired_humidity=desired_humidity)

    def set_fan_mode_and_humidity(
        self,
        fan_mode: FanMode | None = None,
        desired_humidity: DesiredHumidity | None = None,
    ) -> None:
        """Set the desired humidity and fan mode."""
        args: list[tuple[str, int]] = []

        if fan_mode is not None:
            if FanMode(fan_mode) == _UNKNOWN:
                raise ValueError(f"Unexpected value for fan_mode: {fan_mode}")
            args.append(("FanMode", fan_mode))

        if desired_humidity is not None:
            if DesiredHumidity(desired_humidity) == _UNKNOWN:
                raise ValueError(
                    "Unexpected value for desired_humidity: "
                    f"{desired_humidity}"
                )
            args.append(("DesiredHumidity", desired_humidity))

        self._set_attributes(*args)

    def reset_filter_life(self) -> None:
        """Reset the filter life (call this when you install a new filter)."""
        self._set_attributes(("FilterLife", FILTER_LIFE_MAX))
