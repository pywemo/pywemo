"""Representation of a WeMo Heater device."""

from enum import IntEnum
from typing import TypedDict

from .api.attributes import AttributeDevice


class Mode(IntEnum):
    """Heater operation modes."""

    # pylint: disable=invalid-name

    Off = 0
    Frostprotect = 1
    High = 2
    Low = 3
    Eco = 4


class Temperature(IntEnum):
    """Temperature units."""

    # pylint: disable=invalid-name

    Celsius = 0
    Fahrenheit = 1


class SetTemperature(IntEnum):
    """Target temperature setting."""


class AutoOffTime(IntEnum):
    """Auto off time in minutes."""


class TimeRemaining(IntEnum):
    """Time remaining in minutes."""


class _Attributes(TypedDict, total=False):
    """Attributes for the WeMo Heater."""

    # pylint: disable=invalid-name

    Mode: int
    Temperature: float
    SetTemperature: float
    AutoOffTime: int
    RunMode: int
    TimeRemaining: int
    WemoDisabled: int
    TempUnit: int


class Heater(AttributeDevice):
    """Representation of a WeMo Heater device."""

    _state_property = "mode"
    _attributes: _Attributes

    def __repr__(self) -> str:
        """Return a string representation of the device."""
        return f'<WeMo Heater "{self.name}">'

    @property
    def mode(self) -> Mode:
        """Return the current heater mode."""
        return Mode(self._attributes.get("Mode", 0))

    @property
    def mode_string(self) -> str:
        """Return the current mode as a string."""
        return self.mode.name

    def set_mode(self, mode: str | int) -> None:
        """Set the heater mode.

        Args:
            mode: Mode enum value, int (0=Off, 1=Frostprotect, 2=High, 3=Low,
            4=Eco), or string

        """
        if isinstance(mode, str):
            mode = Mode[mode]
        self._set_attributes(("Mode", int(mode)))

    @property
    def current_temperature(self) -> float:
        """Return the current temperature in Celsius.

        Note: Device may return in either unit depending on state.
        Values > 50 are Fahrenheit (room temp in C is always < 50).
        """
        raw_value = float(self._attributes.get("Temperature", 0))
        if raw_value > 50:
            return float(round(self._fahrenheit_to_celsius(raw_value)))
        return raw_value

    @property
    def target_temperature(self) -> float:
        """Return the target temperature in Celsius.

        Note: Device may return SetTemperature in either Fahrenheit
        or Celsius depending on device state and firmware. Values
        > 50 are always Fahrenheit (max Celsius target is 29).
        This heuristic matches the homebridge-wemo approach.
        """
        raw_value = float(self._attributes.get("SetTemperature", 0))
        if raw_value > 50:
            return float(round(self._fahrenheit_to_celsius(raw_value)))
        return float(round(raw_value))

    def set_target_temperature(self, temperature: float) -> None:
        """Set the target temperature.

        Args:
            temperature: Target temperature in current unit (Celsius or
                         Fahrenheit based on temperature_unit property)

        Notes:
            - CRITICAL: The WeMo heater API always expects Fahrenheit
              internally, regardless of the display unit setting (TempUnit)
            - This method automatically converts Celsius to Fahrenheit if
              needed
            - The temperature_unit property determines the input/output unit

        """
        # Convert to float
        temp_value = float(temperature)

        # CRITICAL FIX: Convert to Fahrenheit if currently in Celsius mode
        # The device API always expects Fahrenheit internally!
        if self.temperature_unit == Temperature.Celsius:
            temp_fahrenheit = self._celsius_to_fahrenheit(temp_value)
        else:
            # Already in Fahrenheit — round to integer since the device
            # truncates (floors) decimal F values. Rounding first ensures
            # e.g. 72.9°F becomes 73°F, not 72°F.
            temp_fahrenheit = float(round(temp_value))

        # Send to device (always in Fahrenheit).
        # _set_attributes updates _attributes["SetTemperature"]
        # with F value; target_temperature converts on read.
        self._set_attributes(("SetTemperature", temp_fahrenheit))

    def _celsius_to_fahrenheit(self, celsius: float) -> float:
        """Convert Celsius to Fahrenheit.

        Args:
            celsius: Temperature in Celsius

        Returns:
            Temperature in Fahrenheit

        """
        return (celsius * 9.0 / 5.0) + 32.0

    def _fahrenheit_to_celsius(self, fahrenheit: float) -> float:
        """Convert Fahrenheit to Celsius.

        Args:
            fahrenheit: Temperature in Fahrenheit

        Returns:
            Temperature in Celsius

        """
        return (fahrenheit - 32.0) * 5.0 / 9.0

    @property
    def temperature_unit(self) -> Temperature:
        """Return the temperature unit (0=Fahrenheit, 1=Celsius)."""
        return Temperature(self._attributes.get("TempUnit", 0))

    @property
    def temperature_unit_string(self) -> str:
        """Return temperature unit as string."""
        return "C" if self.temperature_unit == Temperature.Celsius else "F"

    def set_temperature_unit(self, unit: str | int) -> None:
        """Set the temperature unit.

        Args:
            unit: Temperature enum value, int (0=F, 1=C), or string ('F', 'C')

        Notes:
            This only changes the DISPLAY unit. The API always uses Fahrenheit
            internally.

        """
        if isinstance(unit, str):
            unit = (
                Temperature.Celsius
                if unit.upper() == "C"
                else Temperature.Fahrenheit
            )
        self._set_attributes(("TempUnit", int(unit)))

    @property
    def auto_off_time(self) -> int:
        """Return the auto off time in minutes."""
        return int(self._attributes.get("AutoOffTime", 0))

    def set_auto_off_time(self, minutes: int) -> None:
        """Set auto off time in minutes.

        Args:
            minutes: Minutes until auto off (0 to disable)

        """
        self._set_attributes(("AutoOffTime", int(minutes)))

    @property
    def time_remaining(self) -> int:
        """Return time remaining in minutes before auto off."""
        return int(self._attributes.get("TimeRemaining", 0))

    @property
    def heating_status(self) -> bool:
        """Return whether the heater is actively heating."""
        # Check if heater is on (not in Off mode)
        return self.mode != Mode.Off

    def turn_on(self) -> None:
        """Turn the heater on to Eco mode."""
        self.set_mode(Mode.Eco)

    def turn_off(self) -> None:
        """Turn the heater off."""
        self.set_mode(Mode.Off)

    @property
    def state(self) -> int:
        """Return 1 if heater is on (not in Off mode), 0 otherwise."""
        return 0 if self.mode == Mode.Off else 1

    def get_state(self, force_update: bool = False) -> int:
        """Return the state of the device.

        Args:
            force_update: If True, refresh attributes from device

        Returns:
            int: 1 if on, 0 if off

        """
        if force_update:
            self.update_attributes()
        return self.state

    def get_temperature_range(self) -> tuple[int, int]:
        """Return the valid temperature range for this device.

        Returns:
            tuple: (min_temp, max_temp) in current display unit

        Note:
            These are typical ranges for WeMo heaters.

        """
        if self.temperature_unit == Temperature.Celsius:
            return (16, 29)  # Typical Celsius range
        return (60, 85)  # Typical Fahrenheit range
