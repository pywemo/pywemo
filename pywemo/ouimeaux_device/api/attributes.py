"""Attribute device helpers."""
from __future__ import annotations

from typing import Any

from lxml import etree as et

from ..switch import Switch
from .service import RequiredService
from .xsd_types import quote_xml


def _is_int_or_float(value: str) -> bool:
    if value.isdecimal():
        return True
    values = value.split(".")
    return len(values) == 2 and values[0].isdecimal() and values[1].isdecimal()


class AttributeDevice(Switch):
    """Handles all parsing/getting/setting of attribute lists.

    This is intended to be used as the base class for all devices that support
    the deviceevent.GetAttributes() method.

    Subclasses can use the _attributes property to fetch the string values of
    all attributes. Subclasses must provide the name of the property to use
    for self._state in a property named _state_property.
    """

    EVENT_TYPE_ATTRIBUTE_LIST = "attributeList"

    _attributes: dict[str, str] = {}
    _state_property: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Create a Attributes device."""
        assert isinstance(self._state_property, str)
        super().__init__(*args, **kwargs)
        self.update_attributes()

    @property
    def _required_services(self) -> list[RequiredService]:
        return super()._required_services + [
            RequiredService(
                name="deviceevent", actions=["GetAttributes", "SetAttributes"]
            ),
        ]

    def _update_attributes_dict(self, xml_blob: str) -> None:
        xml_blob = "<attributes>" + xml_blob + "</attributes>"
        xml_blob = xml_blob.replace("&gt;", ">")
        xml_blob = xml_blob.replace("&lt;", "<")

        self._attributes.update(
            {
                attribute[0].text: attribute[1].text
                for attribute in et.fromstring(xml_blob)
                if len(attribute) >= 2 and _is_int_or_float(attribute[1].text)
            }
        )

        state: int | None = getattr(self, self._state_property)
        self._state = state

    def update_attributes(self) -> None:
        """Request state from device."""
        resp = self.deviceevent.GetAttributes().get(
            self.EVENT_TYPE_ATTRIBUTE_LIST
        )
        assert resp is not None
        self._update_attributes_dict(resp)

    def subscription_update(self, _type: str, _params: str) -> bool:
        """Handle subscription push-events from device."""
        if _type == self.EVENT_TYPE_ATTRIBUTE_LIST:
            self._update_attributes_dict(_params)
            return True

        return super().subscription_update(_type, _params)

    def get_state(self, force_update: bool = False) -> int:
        """Return 0 if off and 1 if on."""
        if force_update or self._state is None:
            self.update_attributes()

        assert self._state is not None
        return self._state

    def _set_attributes(self, *args: tuple[str, str | int | float]) -> None:
        """Set the specified attributes on the device."""
        attribute_xml = "</attribute><attribute>".join(
            f"<name>{name}</name><value>{value}</value>"
            for name, value in args
        )
        attribute_xml = f"<attribute>{attribute_xml}</attribute>"
        self.deviceevent.SetAttributes(attributeList=quote_xml(attribute_xml))

        # Refresh the device state
        self.get_state(True)
