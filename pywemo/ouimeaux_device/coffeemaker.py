"""Representation of a WeMo CofeeMaker device."""
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
# CoffeeMaker.deviceevent.GetAttributeList() service call
# Thus these names/values were not chosen randomly
# and the numbers have meaning.
class CoffeeMakerMode(IntEnum):
    """Enum to map WeMo modes to human-readable strings."""

    Refill = 0  # reservoir empty and carafe not in place
    PlaceCarafe = 1  # reservoir has water but carafe not present
    RefillWater = 2  # carafe present but reservoir is empty
    Ready = 3
    Brewing = 4
    Brewed = 5
    CleaningBrewing = 6
    CleaningSoaking = 7
    BrewFailCarafeRemoved = 8


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


def attribute_xml_to_dict(xml_blob):
    """Return integer value of Mode from an attributesList blob, if present."""
    xml_blob = "<attributes>" + xml_blob + "</attributes>"
    xml_blob = xml_blob.replace("&gt;", ">")
    xml_blob = xml_blob.replace("&lt;", "<")
    result = {}
    attributes = et.fromstring(xml_blob)
    for attribute in attributes:
        # The coffee maker might also send unrelated xml blobs, e.g.:
        # <ruleID>coffee-brewed</ruleID>
        # <ruleMsg><![CDATA[Coffee's ready!]]></ruleMsg>
        # so be sure to check the length of attribute
        if len(attribute) >= 2:
            try:
                result[attribute[0].text] = int(attribute[1].text)
            except ValueError:
                pass
    return result


class CoffeeMaker(Switch):
    """Representation of a WeMo CofeeMaker device."""

    def __init__(self, *args, **kwargs):
        """Create a WeMo CoffeeMaker device."""
        Switch.__init__(self, *args, **kwargs)
        self._attributes = {}

    def __repr__(self):
        """Return a string representation of the device."""
        return '<WeMo CoffeeMaker "{name}">'.format(name=self.name)

    def update_attributes(self):
        """Request state from device."""
        # pylint: disable=maybe-no-member
        resp = self.deviceevent.GetAttributes().get('attributeList')
        self._attributes = attribute_xml_to_dict(resp)
        self._state = self.mode

    def subscription_update(self, _type, _params):
        """Handle reports from device."""
        if _type == "attributeList":
            self._attributes.update(attribute_xml_to_dict(_params))
            self._state = self.mode
            return True

        return Switch.subscription_update(self, _type, _params)

    @property
    def device_type(self):
        """Return what kind of WeMo this device is."""
        return "CoffeeMaker"

    @property
    def mode(self):
        """Return the mode of the device."""
        return self._attributes.get('Mode')

    @property
    def mode_string(self):
        """Return the mode of the device as a string."""
        return MODE_NAMES.get(self.mode, "Unknown")

    def get_state(self, force_update=False):
        """Return 0 if off and 1 if on."""
        # The base implementation using GetBinaryState doesn't
        # work for CoffeeMaker (always returns 0), so use mode instead.
        if force_update or self._state is None:
            self.update_attributes()

        # Consider the Coffee Maker to be "on" if it's currently brewing.
        return int(self._state == CoffeeMakerMode.Brewing)

    def set_state(self, state):
        """Set the state of this device to on or off."""
        # CoffeeMaker cannot be turned off remotely,
        # so ignore the request if state is "falsey"
        if state:
            # Coffee Maker always responds with an error if
            # SetBinaryState is called. Use SetAttributes
            # to change the Mode to "Brewing"

            # pylint: disable=maybe-no-member
            self.deviceevent.SetAttributes(attributeList=quote_xml(
                "<attribute><name>Mode</name><value>4</value></attribute>"))

        # The Coffee Maker might not be ready - so it's not safe
        # to assume the state is what you just set,
        # so re-read it from the device
        self.get_state(True)
