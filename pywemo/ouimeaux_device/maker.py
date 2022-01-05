"""Representation of a WeMo Maker device."""
from __future__ import annotations

import warnings

from .api.attributes import AttributeDevice
from .api.service import RequiredService


class Maker(AttributeDevice):
    """Representation of a WeMo Maker device."""

    _state_property = "switch_state"  # Required by AttributeDevice.

    @property
    def maker_params(self) -> dict[str, int]:
        """Legacy maker_params value."""
        warnings.warn(
            "maker_params is deprecated and will be removed in a future "
            "release. Use the properties on the Maker instance instead.",
            DeprecationWarning,
        )
        return {
            "switchstate": self.switch_state,
            "sensorstate": self.sensor_state,
            "switchmode": self.switch_mode,
            "hassensor": self.has_sensor,
        }

    @property
    def _required_services(self) -> list[RequiredService]:
        return super()._required_services + [
            RequiredService(name="basicevent", actions=["SetBinaryState"]),
        ]

    def update_maker_params(self) -> None:
        """Get and parse the device attributes."""
        warnings.warn(
            "update_maker_params is deprecated and will be removed in a "
            "future release. Use update_attributes instead.",
            DeprecationWarning,
        )
        self.update_attributes()

    def set_state(self, state: int) -> None:
        """Set the state of this device to on or off."""
        # The Maker has a momentary mode - so it's not safe to assume
        # the state is what you just set, so re-read it from the device
        self.basicevent.SetBinaryState(BinaryState=int(state))
        self.get_state(True)

    @property
    def switch_state(self) -> int:
        """Return the state of the switch."""
        return int(self._attributes["Switch"])

    @property
    def sensor_state(self) -> int:
        """Return the state of the sensor."""
        return int(self._attributes["Sensor"])

    @property
    def switch_mode(self) -> int:
        """Return the switch mode of the sensor."""
        return int(self._attributes["SwitchMode"])

    @property
    def has_sensor(self) -> int:
        """Return whether the device has a sensor."""
        return int(self._attributes["SensorPresent"])
