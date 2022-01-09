"""Representation of a WeMo Bridge (Link) device."""
from __future__ import annotations

import io
import sys
import time
from html import escape
from typing import Any

from lxml import etree as et

from ..color import ColorXY, get_profiles, limit_to_gamut
from . import Device
from .api.service import RequiredService

CAPABILITY_ID2NAME = dict(
    (
        ('10006', "onoff"),
        ('10008', "levelcontrol"),
        ('30008', "sleepfader"),
        ('30009', "levelcontrol_move"),
        ('3000A', "levelcontrol_stop"),
        ('10300', "colorcontrol"),
        ('30301', "colortemperature"),
    )
)
CAPABILITY_NAME2ID = dict(
    (val, cap) for cap, val in CAPABILITY_ID2NAME.items()
)

# acceptable values for 'onoff'
OFF = 0
ON = 1
TOGGLE = 2


def limit(value: int, min_val: int, max_val: int) -> int:
    """Return a value clipped to the range [min_val, max_val]."""
    return max(min_val, min(value, max_val))


class Bridge(Device):
    """Representation of a WeMo Bridge (Link) device."""

    Lights: dict[str, Light] = {}
    Groups: dict[str, Group] = {}

    EVENT_TYPE_STATUS_CHANGE = "StatusChange"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Create a WeMo Bridge (Link) device."""
        super().__init__(*args, **kwargs)
        self.bridge_update()

    def __repr__(self) -> str:
        """Return a string representation of the device."""
        return (
            '<WeMo Bridge "{name}", Lights: {lights}, ' + 'Groups: {groups}>'
        ).format(
            name=self.name, lights=len(self.Lights), groups=len(self.Groups)
        )

    @property
    def _required_services(self) -> list[RequiredService]:
        return super()._required_services + [
            RequiredService(name="basicevent", actions=["GetMacAddr"]),
            RequiredService(
                name="bridge",
                actions=["GetDeviceStatus", "SetDeviceStatus"],
            ),
        ]

    def bridge_update(
        self, force_update: bool = True
    ) -> tuple[dict[str, Light], dict[str, Group]]:
        """Get updated status information for the bridge and its lights."""
        if force_update or self.Lights is None or self.Groups is None:
            plugin_udn = self.basicevent.GetMacAddr().get('PluginUDN')

            if hasattr(self.bridge, 'GetEndDevicesWithStatus'):
                end_devices = self.bridge.GetEndDevicesWithStatus(
                    DevUDN=plugin_udn, ReqListType='PAIRED_LIST'
                )
            else:
                end_devices = self.bridge.GetEndDevices(
                    DevUDN=plugin_udn, ReqListType='PAIRED_LIST'
                )

            end_devices_xml = end_devices.get('DeviceLists')
            if not end_devices_xml:
                return self.Lights, self.Groups

            end_device_list = et.fromstring(end_devices_xml.encode('utf-8'))

            for light in end_device_list.iter('DeviceInfo'):
                uniqueID = light.find('DeviceID').text
                if uniqueID in self.Lights:
                    self.Lights[uniqueID].update_state(light)
                else:
                    self.Lights[uniqueID] = Light(self, light)

            for group in end_device_list.iter('GroupInfo'):
                uniqueID = group.find('GroupID').text
                if uniqueID in self.Groups:
                    self.Groups[uniqueID].update_state(group)
                else:
                    self.Groups[uniqueID] = Group(self, group)

        return self.Lights, self.Groups

    def get_state(self, force_update: bool = False) -> int:
        """Update the state of the Bridge device."""
        state = super().get_state(force_update)
        self.bridge_update(force_update)
        return state

    def subscription_update(self, _type: str, _param: str) -> bool:
        """Update the bridge attributes due to a subscription update event."""
        if _type == self.EVENT_TYPE_STATUS_CHANGE and _param:
            state_event = et.fromstring(_param.encode('utf8'))
            key = state_event.findtext('DeviceID')
            if not key:
                return False
            if key in self.Lights:
                return self.Lights[key].subscription_update(state_event)

            if key in self.Groups:
                return self.Groups[key].subscription_update(state_event)

            return False
        return super().subscription_update(_type, _param)

    def bridge_getdevicestatus(self, deviceid: str) -> et.Element | None:
        """Return the list of device statuses for the bridge's lights."""
        status_list = self.bridge.GetDeviceStatus(DeviceIDs=deviceid)
        device_status_list_xml = status_list.get('DeviceStatusList')
        if not device_status_list_xml:
            return None
        device_status_list = et.fromstring(
            device_status_list_xml.encode('utf-8')
        )

        return device_status_list.find('DeviceStatus')

    def bridge_setdevicestatus(
        self, isgroup: str, deviceid: str, capids: list[str], values: list[str]
    ) -> dict[str, str]:
        """Set the status of the bridge's lights."""
        req = et.Element('DeviceStatus')
        et.SubElement(req, 'IsGroupAction').text = isgroup
        et.SubElement(req, 'DeviceID', available="YES").text = deviceid
        et.SubElement(req, 'CapabilityID').text = ','.join(capids)
        et.SubElement(req, 'CapabilityValue').text = ','.join(values)

        buf = io.BytesIO()
        et.ElementTree(req).write(buf, encoding='UTF-8', xml_declaration=True)
        send_state = escape(buf.getvalue().decode(), quote=True)

        return self.bridge.SetDeviceStatus(DeviceStatusList=send_state)


if sys.version_info >= (3, 8):
    # Remove pylint disable when Python 3.7 support is removed.
    from typing import TypedDict  # pylint: disable=no-name-in-module

    class DeviceState(TypedDict, total=False):
        """LinkedDevice state dictionary type."""

        available: bool
        onoff: int
        level: int
        temperature_mireds: int
        temperature_kelvin: int
        color_xy: ColorXY


else:
    from typing import Dict, Union

    DeviceState = Dict[str, Union[ColorXY, bool, int]]


class LinkedDevice:
    """Representation of a device connected to the bridge."""

    def __init__(self, bridge: Bridge, info: et.Element) -> None:
        """Create a Linked Device."""
        self.bridge = bridge
        self.host = self.bridge.host
        self.port = self.bridge.port
        self.name = ''
        self.state: DeviceState = {}
        self.capabilities: list[str] = []
        self._values: list[str] = []
        self.update_state(info)
        self._last_err: dict[str, str] = {}
        self.mac = self.bridge.mac
        self.serialnumber = self.bridge.serial_number
        self.uniqueID = ''

    def get_state(self, force_update: bool = False) -> DeviceState:
        """Return the status of the device."""
        if force_update:
            self.bridge.bridge_update()
        return self.state

    def update_state(self, status: Any) -> None:
        """
        Set the device state based on capabilities and values.

        Subclasses should parse status into self.capabilities and
        self._values and then call this to populate self.state.
        """
        status = {}
        for capability, value in zip(self.capabilities, self._values):
            if not value:
                status[capability] = None
            elif ':' in value:
                status[capability] = tuple(
                    int(round(float(v))) for v in value.split(':')
                )
            else:
                status[capability] = int(round(float(value)))

        # unreachable devices have empty strings for all capability values
        if status.get('onoff') is None:
            self.state['available'] = False
            self.state['onoff'] = 0
            return

        self.state['available'] = True
        self.state['onoff'] = status['onoff']

        if status.get('levelcontrol') is not None:
            self.state['level'] = status['levelcontrol'][0]

        if status.get('colortemperature') is not None:
            temperature = status['colortemperature'][0]
            self.state['temperature_mireds'] = temperature
            self.state['temperature_kelvin'] = int(1000000 / temperature)

        if status.get('colorcontrol') is not None:
            colorx, colory = status['colorcontrol'][:2]
            colorx, colory = colorx / 65535.0, colory / 65535.0
            self.state['color_xy'] = colorx, colory

    def subscription_update(self, state_event: et.Element) -> bool:
        """Update the light values due to a subscription update event."""
        device_id = state_event.find('DeviceID')
        if device_id.get('available', 'YES').upper() == 'YES':
            capability = state_event.findtext('CapabilityId')
            value = state_event.findtext('Value')
        else:
            capability = CAPABILITY_NAME2ID.get('onoff')
            value = ''  # Use an empty string to indicate an unreachable device

        if capability is None or value is None:
            return False
        name = CAPABILITY_ID2NAME.get(capability, capability)
        # Update only the capability/value pair that changed.
        try:
            index = self.capabilities.index(name)
        except ValueError:
            # Should't receive updates for capabilities that were not
            # originally present.
            return False
        else:
            self._values[index] = value

        # Don't call the subclass. It expects to have a list of all the
        # capability/value pairs. The subscription_update only receives a
        # single capability/value pair.
        LinkedDevice.update_state(self, {})
        return True

    def _setdevicestatus(self, **kwargs: Any) -> LinkedDevice:
        """Ask the bridge to set the device status."""
        isgroup = 'YES' if isinstance(self, Group) else 'NO'

        capids = []
        values = []
        for cap, val in kwargs.items():
            capids.append(CAPABILITY_NAME2ID[cap])

            if not isinstance(val, (list, tuple)):
                val = (val,)
            values.append(':'.join(str(v) for v in val))

        self._last_err = self.bridge.bridge_setdevicestatus(
            isgroup, self.uniqueID, capids, values
        )
        return self

    def turn_on(
        self,
        level: int | None = None,
        transition: int = 0,
        force_update: bool = False,
    ) -> LinkedDevice:
        """Turn on the device."""
        return self._setdevicestatus(onoff=ON)

    def turn_off(self, transition: int = 0) -> LinkedDevice:
        """Turn off the device."""
        return self._setdevicestatus(onoff=OFF)

    def toggle(self) -> LinkedDevice:
        """Toggle the device from on to off or off to on."""
        return self._setdevicestatus(onoff=TOGGLE)

    @property
    def device_type(self) -> str:
        """Return what kind of WeMo this device is."""
        return type(self).__name__

    def __repr__(self) -> str:
        """Return a string representation of the device."""
        return f'<{self.device_type.upper()} "{self.name}">'


class Light(LinkedDevice):
    """Representation of a Light connected to the Bridge."""

    def __init__(self, bridge: Bridge, info: et.Element) -> None:
        """Create a Light device."""
        super().__init__(bridge, info)

        self.device_index = info.findtext('DeviceIndex')
        self.uniqueID = info.findtext('DeviceID')
        self.iconvalue = info.findtext('IconVersion')
        self.firmware = info.findtext('FirmwareVersion')
        self.manufacturer = info.findtext('Manufacturer')
        self.model = info.findtext('ModelCode')
        self.certified = info.findtext('WeMoCertified')

        self.temperature_range, self.gamut = get_profiles(self.model)
        self._pending: dict[str, Any] = {}

    def _queuedevicestatus(self, queue: bool = False, **kwargs: Any) -> Light:
        """Queue an update to the device."""
        if kwargs:
            self._pending.update(kwargs)
        if not queue:
            self._setdevicestatus(**self._pending)
            self._pending = {}

        return self

    def update_state(self, status: et.Element) -> None:
        """Update the device state."""
        if status.tag == 'DeviceInfo':
            self.name = status.findtext('FriendlyName')

        capabilities = status.findtext('CapabilityIDs') or status.findtext(
            'CapabilityID'
        )
        currentstate = status.findtext('CurrentState') or status.findtext(
            'CapabilityValue'
        )

        if capabilities is not None:
            self.capabilities = [
                CAPABILITY_ID2NAME.get(c, c) for c in capabilities.split(',')
            ]
        if currentstate is not None:
            self._values = currentstate.split(',')

        super().update_state(status)

    def turn_on(
        self,
        level: int | None = None,
        transition: int = 0,
        force_update: bool = False,
    ) -> Light:
        """Turn on the light."""
        transition_time = limit(int(transition * 10), 0, 65535)

        if level == 0:
            return self.turn_off(transition)
        if 'levelcontrol' in self.capabilities:
            # Work around observed fw bugs.
            # - When we set a new brightness level but the bulb is off, it
            #   first turns on at the old brightness and then fades to the new
            #   setting. So we have to force the saved brightness to 0 first.
            # - When we turn a bulb on with levelcontrol the onoff state
            #   doesn't update.
            # - After turning off a bulb with sleepfader, it fails to turn back
            #   on unless the brightness is re-set with levelcontrol.
            self.get_state(force_update=force_update)
            # A freshly power cycled bridge has no record of the bulb
            # brightness, so default to full on if the client didn't request
            # a level and we have no record
            if level is None:
                level = self.state.get("level", 255)

            if self.state['onoff'] == 0:
                self._setdevicestatus(levelcontrol=(0, 0), onoff=ON)

            level = limit(int(level), 0, 255)
            return self._queuedevicestatus(
                levelcontrol=(level, transition_time)
            )

        return self._queuedevicestatus(onoff=ON)

    def turn_off(self, transition: int = 0) -> Light:
        """Turn off the light."""
        if transition and 'sleepfader' in self.capabilities:
            # Sleepfader control did not turn off bulb when fadetime was 0
            transition_time = limit(int(transition * 10), 1, 65535)
            reference = int(time.time())
            return self._queuedevicestatus(
                sleepfader=(transition_time, reference)
            )

        return self._queuedevicestatus(onoff=OFF)

    def set_temperature(
        self,
        kelvin: int = 2700,
        mireds: int | None = None,
        transition: int = 0,
        delay: bool = True,
    ) -> Light:
        """Set the color temperature of the light."""
        transition_time = limit(int(transition * 10), 0, 65535)
        if mireds is None:
            mireds = int(1000000 / kelvin)
        mireds = limit(int(mireds), *self.temperature_range)
        return self._queuedevicestatus(
            colortemperature=(mireds, transition_time), queue=delay
        )

    def set_color(
        self, colorxy: ColorXY, transition: int = 0, delay: bool = True
    ) -> Light:
        """Set the color of the light."""
        transition_time = limit(int(transition * 10), 0, 65535)
        colorxy = limit_to_gamut(colorxy, self.gamut)
        colorx = limit(int(colorxy[0] * 65535), 0, 65535)
        colory = limit(int(colorxy[1] * 65535), 0, 65535)
        return self._queuedevicestatus(
            colorcontrol=(colorx, colory, transition_time), queue=delay
        )

    def start_ramp(self, ramp_up: bool, rate: int) -> Light:
        """Start ramping the brightness up or down."""
        up_down = '1' if ramp_up else '0'
        rate = limit(int(rate), 0, 255)
        return self._queuedevicestatus(levelcontrol_move=(up_down, rate))

    def stop_ramp(self) -> LinkedDevice:
        """Start ramping the brightness up or down."""
        return self._setdevicestatus(levelcontrol_stop='')


class Group(LinkedDevice):
    """Representation of a Group of lights connected to the Bridge."""

    def __init__(self, bridge: Bridge, info: et.Element) -> None:
        """Create a Group device."""
        super().__init__(bridge, info)
        self.uniqueID = info.findtext('GroupID')

    def update_state(self, status: et.Element) -> None:
        """Update the device state."""
        if status.tag == 'GroupInfo':
            self.name = status.findtext('GroupName')

        capabilities = status.findtext(
            'GroupCapabilityIDs'
        ) or status.findtext('CapabilityID')
        currentstate = status.findtext(
            'GroupCapabilityValues'
        ) or status.findtext('CapabilityValue')

        if capabilities is not None:
            self.capabilities = [
                CAPABILITY_ID2NAME.get(c, c) for c in capabilities.split(',')
            ]
        if currentstate is not None:
            self._values = currentstate.split(',')
        super().update_state(status)
