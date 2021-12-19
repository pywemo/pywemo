"""Representation of a WeMo Maker device."""
from typing import Dict

from lxml import etree as et

from .api.service import RequiredService
from .switch import Switch


def attribute_xml_to_dict(xml_blob) -> Dict[str, int]:
    """Return attribute values as a dict of key value pairs."""
    xml_blob = "<attributes>" + xml_blob + "</attributes>"
    xml_blob = xml_blob.replace("&gt;", ">")
    xml_blob = xml_blob.replace("&lt;", "<")

    values = {}

    attributes = et.fromstring(xml_blob)

    def set_int_value(name, value):
        try:
            values[name] = int(value)
        except ValueError:
            pass

    for attribute in attributes:
        if attribute[0].text == "Switch":
            set_int_value('switchstate', attribute[1].text)
        elif attribute[0].text == "Sensor":
            set_int_value('sensorstate', attribute[1].text)
        elif attribute[0].text == "SwitchMode":
            set_int_value('switchmode', attribute[1].text)
        elif attribute[0].text == "SensorPresent":
            set_int_value('hassensor', attribute[1].text)

    return values


class Maker(Switch):
    """Representation of a WeMo Maker device."""

    def __init__(self, *args, **kwargs):
        """Create a WeMo Switch device."""
        super().__init__(*args, **kwargs)
        self.maker_params = {}
        self.get_state(force_update=True)

    @property
    def _required_services(self):
        return super()._required_services + [
            RequiredService(name="basicevent", actions=["SetBinaryState"]),
            RequiredService(
                name="deviceevent", actions=["GetAttributes", "SetAttributes"]
            ),
        ]

    def update_maker_params(self):
        """Get and parse the device attributes."""
        maker_resp = self.deviceevent.GetAttributes().get('attributeList')
        self.maker_params = attribute_xml_to_dict(maker_resp)
        self._state = self.switch_state

    def subscription_update(self, _type, _params):
        """Handle reports from device."""
        if _type == "attributeList":
            self.maker_params.update(attribute_xml_to_dict(_params))
            self._state = self.switch_state
            return True

        return super().subscription_update(_type, _params)

    def get_state(self, force_update=False):
        """Return 0 if off and 1 if on."""
        # The base implementation using GetBinaryState doesn't work for the
        # Maker (always returns 0), so pull the switch state from the
        # attributes instead
        if force_update or self._state is None:
            self.update_maker_params()

        return self.switch_state

    def set_state(self, state):
        """Set the state of this device to on or off."""
        # The Maker has a momentary mode - so it's not safe to assume
        # the state is what you just set, so re-read it from the device
        self.basicevent.SetBinaryState(BinaryState=int(state))
        self.get_state(True)

    @property
    def switch_state(self) -> int:
        """Return the state of the switch."""
        return self.maker_params['switchstate']

    @property
    def sensor_state(self) -> int:
        """Return the state of the sensor."""
        return self.maker_params['sensorstate']

    @property
    def switch_mode(self) -> int:
        """Return the switch mode of the sensor."""
        return self.maker_params['switchmode']

    @property
    def has_sensor(self) -> int:
        """Return whether the device has a sensor."""
        return self.maker_params['hassensor']
