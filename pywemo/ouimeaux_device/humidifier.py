"""Representation of a WeMo Humidifier device."""

from xml.etree import cElementTree as et
import sys
from pywemo.ouimeaux_device.api.xsd.device import quote_xml
from .switch import Switch


if sys.version_info[0] < 3:
    class IntEnum:
        """Enum class."""

        pass
else:
    from enum import IntEnum


# These enums were derived from the
# Humidifier.deviceevent.GetAttributeList()
# service call.
# Thus these names/values were not chosen randomly
# and the numbers have meaning.
class FanMode(IntEnum):
    """Enum to map WeMo FanModes to human-readable strings."""

    Off = 0  # Fan and device turned off
    Minimum = 1
    Low = 2
    Medium = 3
    High = 4
    Maximum = 5


FAN_MODE_NAMES = {
    FanMode.Off: "Off",
    FanMode.Minimum: "Minimum",
    FanMode.Low: "Low",
    FanMode.Medium: "Medium",
    FanMode.High: "High",
    FanMode.Maximum: "Maximum"
}


class DesiredHumidity(IntEnum):
    """Enum to map WeMo DesiredHumidity to human-readable strings."""

    FortyFivePercent = 0
    FiftyPercent = 1
    FiftyFivePercent = 2
    SixtyPercent = 3
    OneHundredPercent = 4  # "Always On" Mode


DESIRED_HUMIDITY_NAMES = {
    DesiredHumidity.FortyFivePercent: "45",
    DesiredHumidity.FiftyPercent: "50",
    DesiredHumidity.FiftyFivePercent: "55",
    DesiredHumidity.SixtyPercent: "60",
    DesiredHumidity.OneHundredPercent: "100"
}


class WaterLevel(IntEnum):
    """Enum to map WeMo WaterLevel to human-readable strings."""

    Empty = 0
    Low = 1
    Good = 2


WATER_LEVEL_NAMES = {
    WaterLevel.Empty: "Empty",
    WaterLevel.Low: "Low",
    WaterLevel.Good: "Good",
}

FILTER_LIFE_MAX = 60480


def attribute_xml_to_dict(xml_blob):
    """Return attribute values as a dict of key value pairs."""
    xml_blob = "<attributes>" + xml_blob + "</attributes>"
    xml_blob = xml_blob.replace("&gt;", ">")
    xml_blob = xml_blob.replace("&lt;", "<")

    result = {}

    attributes = et.fromstring(xml_blob)

    result["water_level"] = int(2)

    for attribute in attributes:
        if attribute[0].text == "FanMode":
            try:
                result["fan_mode"] = int(attribute[1].text)
            except ValueError:
                pass
        elif attribute[0].text == "DesiredHumidity":
            try:
                result["desired_humidity"] = int(attribute[1].text)
            except ValueError:
                pass
        elif attribute[0].text == "CurrentHumidity":
            try:
                result["current_humidity"] = float(attribute[1].text)
            except ValueError:
                pass
        elif attribute[0].text == "NoWater" and attribute[1].text == "1":
            try:
                result["water_level"] = int(0)
            except ValueError:
                pass
        elif attribute[0].text == "WaterAdvise" and attribute[1].text == "1":
            try:
                result["water_level"] = int(1)
            except ValueError:
                pass
        elif attribute[0].text == "FilterLife":
            try:
                result["filter_life"] = float(round((float(attribute[1].text)
                                                     / float(60480))
                                                    * float(100), 2))
            except ValueError:
                pass
        elif attribute[0].text == "ExpiredFilterTime":
            try:
                result["filter_expired"] = bool(int(attribute[1].text))
            except ValueError:
                pass

    return result


class Humidifier(Switch):
    """Representation of a WeMo Humidifier device."""

    def __init__(self, *args, **kwargs):
        """Create a WeMo Humidifier device."""
        Switch.__init__(self, *args, **kwargs)
        self._attributes = {}
        self.update_attributes()

    def __repr__(self):
        """Return a string representation of the device."""
        return '<WeMo Humidifier "{name}">'.format(name=self.name)

    def update_attributes(self):
        """Request state from device."""
        # pylint: disable=maybe-no-member
        resp = self.deviceevent.GetAttributes().get('attributeList')
        self._attributes = attribute_xml_to_dict(resp)
        self._state = self.fan_mode

    def subscription_update(self, _type, _params):
        """Handle reports from device."""
        if _type == "attributeList":
            self._attributes.update(attribute_xml_to_dict(_params))
            self._state = self.fan_mode

            return True

        return Switch.subscription_update(self, _type, _params)

    @property
    def device_type(self):
        """Return what kind of WeMo this device is."""
        return "Humidifier"

    @property
    def fan_mode(self):
        """Return the FanMode setting (as an int index of the IntEnum)."""
        return self._attributes.get('fan_mode')

    @property
    def fan_mode_string(self):
        """
        Return the FanMode setting as a string.

        (Off, Low, Medium, High, Maximum).
        """
        return FAN_MODE_NAMES.get(self.fan_mode, "Unknown")

    @property
    def desired_humidity(self):
        """Return the desired humidity (as an int index of the IntEnum)."""
        return self._attributes.get('desired_humidity')

    @property
    def desired_humidity_percent(self):
        """Return the desired humidity in percent (string)."""
        return DESIRED_HUMIDITY_NAMES.get(self.desired_humidity, "Unknown")

    @property
    def current_humidity_percent(self):
        """Return the observed relative humidity in percent (float)."""
        return self._attributes.get('current_humidity')

    @property
    def water_level(self):
        """Return 0 if water level is Empty, 1 if Low, and 2 if Good."""
        return self._attributes.get('water_level')

    @property
    def water_level_string(self):
        """Return Empty, Low, or Good depending on the water level."""
        return WATER_LEVEL_NAMES.get(self.water_level, "Unknown")

    @property
    def filter_life_percent(self):
        """Return the percentage (float) of filter life remaining."""
        return self._attributes.get('filter_life')

    @property
    def filter_expired(self):
        """Return 0 if filter is OK, and 1 if it needs to be changed."""
        return self._attributes.get('filter_expired')

    def get_state(self, force_update=False):
        """Return 0 if off and 1 if on."""
        # The base implementation using GetBinaryState
        # doesn't work for Humidifier (always returns 0)
        # so use fan mode instead.
        if force_update or self._state is None:
            self.update_attributes()

        # Consider the Humidifier to be "on" if it's not off.
        return int(self._state != FanMode.Off)

    def set_state(self, state):
        """
        Set the fan mode of this device (as int index of the FanMode IntEnum).

        Provided for compatibility with the Switch base class.
        """
        self.set_fan_mode(state)

    def set_fan_mode(self, fan_mode):
        """
        Set the fan mode of this device (as int index of the FanMode IntEnum).

        Provided for compatibility with the Switch base class.
        """
        # Send the attribute list to the device
        # pylint: disable=maybe-no-member
        self.deviceevent.SetAttributes(attributeList=quote_xml(
            "<attribute><name>FanMode</name><value>" +
            str(int(fan_mode)) + "</value></attribute>"))

        # Refresh the device state
        self.get_state(True)

    def set_humidity(self, desired_humidity):
        """Set the desired humidity (as int index of the IntEnum)."""
        # Send the attribute list to the device
        # pylint: disable=maybe-no-member
        self.deviceevent.SetAttributes(attributeList=quote_xml(
            "<attribute><name>DesiredHumidity</name><value>" +
            str(int(desired_humidity)) + "</value></attribute>"))

        # Refresh the device state
        self.get_state(True)

    def set_fan_mode_and_humidity(self, fan_mode, desired_humidity):
        """
        Set the desired humidity and fan mode.

        (as int index of their respective IntEnums)
        """
        # Send the attribute list to the device
        # pylint: disable=maybe-no-member
        self.deviceevent.SetAttributes(attributeList=quote_xml(
            "<attribute><name>FanMode</name><value>" +
            str(int(fan_mode)) + "</value></attribute>" +
            "<attribute><name>DesiredHumidity</name><value>" +
            str(int(desired_humidity)) + "</value></attribute>"))

        # Refresh the device state
        self.get_state(True)

    def reset_filter_life(self):
        """Reset the filter life (call this when you install a new filter)."""
        # Send the attribute list to the device
        # pylint: disable=maybe-no-member
        self.deviceevent.SetAttributes(attributeList=quote_xml(
            "<attribute><name>FilterLife</name><value>" +
            str(FILTER_LIFE_MAX) + "</value></attribute>"))

        # Refresh the device state
        self.get_state(True)
