"""Representation of a WeMo Bridge (Link) device."""
import time
from xml.etree import cElementTree as et
import six

six.add_move(six.MovedAttribute('html_escape', 'cgi', 'html', 'escape'))

# pylint: disable=wrong-import-position
from six.moves import html_escape  # noqa E402
from . import Device  # noqa E402
from ..color import get_profiles, limit_to_gamut  # noqa E402


CAPABILITY_ID2NAME = dict((
    ('10006', "onoff"),
    ('10008', "levelcontrol"),
    ('30008', "sleepfader"),
    ('30009', "levelcontrol_move"),
    ('3000A', "levelcontrol_stop"),
    ('10300', "colorcontrol"),
    ('30301', "colortemperature"),
))
CAPABILITY_NAME2ID = dict(
    (val, cap) for cap, val in CAPABILITY_ID2NAME.items())

# acceptable values for 'onoff'
OFF = 0
ON = 1
TOGGLE = 2


def limit(value, min_val, max_val):
    """Return a value clipped to the range [min_val, max_val]."""
    return max(min_val, min(value, max_val))


class Bridge(Device):
    """Representation of a WeMo Bridge (Link) device."""

    Lights = {}
    Groups = {}

    def __init__(self, *args, **kwargs):
        """Create a WeMo Bridge (Link) device."""
        super(Bridge, self).__init__(*args, **kwargs)
        self.bridge_update()

    def __repr__(self):
        """Return a string representation of the device."""
        return ('<WeMo Bridge "{name}", Lights: {lights}, ' +
                'Groups: {groups}>').format(
                    name=self.name, lights=len(self.Lights),
                    groups=len(self.Groups))

    def bridge_update(self, force_update=True):
        """Get updated status information for the bridge and its lights."""
        # pylint: disable=maybe-no-member
        if force_update or self.Lights is None or self.Groups is None:
            plugin_udn = self.basicevent.GetMacAddr().get('PluginUDN')

            if hasattr(self.bridge, 'GetEndDevicesWithStatus'):
                end_devices = self.bridge.GetEndDevicesWithStatus(
                    DevUDN=plugin_udn, ReqListType='PAIRED_LIST')
            else:
                end_devices = self.bridge.GetEndDevices(
                    DevUDN=plugin_udn, ReqListType='PAIRED_LIST')

            end_device_list = et.fromstring(end_devices.get('DeviceLists'))

            for light in end_device_list.iter('DeviceInfo'):
                # pylint: disable=invalid-name
                uniqueID = light.find('DeviceID').text
                if uniqueID in self.Lights:
                    self.Lights[uniqueID].update_state(light)
                else:
                    self.Lights[uniqueID] = Light(self, light)

            for group in end_device_list.iter('GroupInfo'):
                # pylint: disable=invalid-name
                uniqueID = group.find('GroupID').text
                if uniqueID in self.Groups:
                    self.Groups[uniqueID].update_state(group)
                else:
                    self.Groups[uniqueID] = Group(self, group)

        return self.Lights, self.Groups

    def bridge_getdevicestatus(self, deviceid):
        """Return the list of device statuses for the bridge's lights."""
        # pylint: disable=maybe-no-member
        status_list = self.bridge.GetDeviceStatus(DeviceIDs=deviceid)
        device_status_list = et.fromstring(status_list.get('DeviceStatusList'))

        return device_status_list.find('DeviceStatus')

    def bridge_setdevicestatus(self, isgroup, deviceid, capids, values):
        """Set the status of the bridge's lights."""
        req = et.Element('DeviceStatus')
        et.SubElement(req, 'IsGroupAction').text = isgroup
        et.SubElement(req, 'DeviceID', available="YES").text = deviceid
        et.SubElement(req, 'CapabilityID').text = ','.join(capids)
        et.SubElement(req, 'CapabilityValue').text = ','.join(values)

        buf = six.BytesIO()
        et.ElementTree(req).write(buf, encoding='utf-8',
                                  xml_declaration=True)
        send_state = html_escape(buf.getvalue().decode(), quote=True)

        # pylint: disable=maybe-no-member
        return self.bridge.SetDeviceStatus(DeviceStatusList=send_state)

    @property
    def device_type(self):
        """Return what kind of WeMo this device is."""
        return "Bridge"


class LinkedDevice:
    """Representation of a device connected to the bridge."""

    def __init__(self, bridge, info):
        """Create a Linked Device."""
        self.bridge = bridge
        self.host = self.bridge.host
        self.port = self.bridge.port
        self.state = {}
        self.capabilities = []
        self._values = []
        self.update_state(info)
        self._last_err = None
        self.mac = self.bridge.mac
        self.serialnumber = self.bridge.serialnumber

    def get_state(self, force_update=False):
        """Return the status of the device."""
        if force_update:
            self.bridge.bridge_update()
        return self.state

    def update_state(self, status):
        """
        Set the device state based on capabilities and values.

        Subclasses should parse status into self.capabilities and
        self._values and then call this to populate self.state.
        """
        status = {}
        for capability, value in zip(self.capabilities, self._values):
            if not value:
                value = None
            elif ':' in value:
                value = tuple(int(round(float(v))) for v in value.split(':'))
            else:
                value = int(round(float(value)))
            status[capability] = value

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
            colorx, colory = colorx / 65535., colory / 65535.
            self.state['color_xy'] = colorx, colory

    def _setdevicestatus(self, **kwargs):
        """Ask the bridge to set the device status."""
        isgroup = 'YES' if isinstance(self, Group) else 'NO'

        capids = []
        values = []
        for cap, val in kwargs.items():
            capids.append(CAPABILITY_NAME2ID[cap])

            if not isinstance(val, (list, tuple)):
                val = (val,)
            values.append(':'.join(str(v) for v in val))

        # pylint: disable=maybe-no-member
        self._last_err = self.bridge.bridge_setdevicestatus(
            isgroup, self.uniqueID, capids, values)
        return self

    def turn_on(self, level=None, transition=0, force_update=False):
        """Turn on the device."""
        return self._setdevicestatus(onoff=ON)

    def turn_off(self, transition=0):
        """Turn off the device."""
        return self._setdevicestatus(onoff=OFF)

    def toggle(self):
        """Toggle the device from on to off or off to on."""
        return self._setdevicestatus(onoff=TOGGLE)

    @property
    def device_type(self):
        """Return what kind of WeMo this device is."""
        return "LinkedDevice"


class Light(LinkedDevice):
    """Representation of a Light connected to the Bridge."""

    def __init__(self, bridge, info):
        """Create a Light device."""
        super(Light, self).__init__(bridge, info)

        self.device_index = info.findtext('DeviceIndex')
        # pylint: disable=invalid-name
        self.uniqueID = info.findtext('DeviceID')
        self.iconvalue = info.findtext('IconVersion')
        self.firmware = info.findtext('FirmwareVersion')
        self.manufacturer = info.findtext('Manufacturer')
        self.model = info.findtext('ModelCode')
        self.certified = info.findtext('WeMoCertified')

        self.temperature_range, self.gamut = get_profiles(self.model)
        self._pending = {}

    def _queuedevicestatus(self, queue=False, **kwargs):
        """Queue an update to the device."""
        if kwargs:
            self._pending.update(kwargs)
        if not queue:
            self._setdevicestatus(**self._pending)
            self._pending = {}

        return self

    def update_state(self, status):
        """Update the device state."""
        if status.tag == 'DeviceInfo':
            self.name = status.findtext('FriendlyName')

        capabilities = (status.findtext('CapabilityIDs') or
                        status.findtext('CapabilityID'))
        currentstate = (status.findtext('CurrentState') or
                        status.findtext('CapabilityValue'))

        if capabilities is not None:
            self.capabilities = [
                CAPABILITY_ID2NAME.get(c, c)
                for c in capabilities.split(',')
            ]
        if currentstate is not None:
            self._values = currentstate.split(',')

        super(Light, self).update_state(status)

    def __repr__(self):
        """Return a string representation of the device."""
        return '<LIGHT "{name}">'.format(name=self.name)

    def turn_on(self, level=None, transition=0, force_update=False):
        """Turn on the light."""
        transition_time = limit(int(transition * 10), 0, 65535)

        if level == 0:
            return self.turn_off(transition)
        elif 'levelcontrol' in self.capabilities:
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
            return self._queuedevicestatus(levelcontrol=(level,
                                                         transition_time))

        return self._queuedevicestatus(onoff=ON)

    def turn_off(self, transition=0):
        """Turn off the light."""
        if transition and 'sleepfader' in self.capabilities:
            # Sleepfader control did not turn off bulb when fadetime was 0
            transition_time = limit(int(transition * 10), 1, 65535)
            reference = int(time.time())
            return self._queuedevicestatus(sleepfader=(transition_time,
                                                       reference))

        return self._queuedevicestatus(onoff=OFF)

    def set_temperature(self, kelvin=2700, mireds=None,
                        transition=0, delay=True):
        """Set the color temperature of the light."""
        transition_time = limit(int(transition * 10), 0, 65535)
        if mireds is None:
            mireds = 1000000 / kelvin
        mireds = limit(int(mireds), *self.temperature_range)
        return self._queuedevicestatus(
            colortemperature=(mireds, transition_time), queue=delay)

    def set_color(self, colorxy, transition=0, delay=True):
        """Set the color of the light."""
        transition_time = limit(int(transition * 10), 0, 65535)
        colorxy = limit_to_gamut(colorxy, self.gamut)
        colorx = limit(int(colorxy[0] * 65535), 0, 65535)
        colory = limit(int(colorxy[1] * 65535), 0, 65535)
        return self._queuedevicestatus(
            colorcontrol=(colorx, colory, transition_time), queue=delay)

    def start_ramp(self, ramp_up, rate):
        """Start ramping the brightness up or down."""
        up_down = '1' if ramp_up else '0'
        rate = limit(int(rate), 0, 255)
        return self._queuedevicestatus(levelcontrol_move=(up_down, rate))

    def stop_ramp(self):
        """Start ramping the brightness up or down."""
        return self._setdevicestatus(levelcontrol_stop='')

    @property
    def device_type(self):
        """Return what kind of WeMo this device is."""
        return "Light"


class Group(LinkedDevice):
    """Representation of a Group of lights connected to the Bridge."""

    def __init__(self, bridge, info):
        """Create a Group device."""
        super(Group, self).__init__(bridge, info)
        # pylint: disable=invalid-name
        self.uniqueID = info.findtext('GroupID')

    def update_state(self, status):
        """Update the device state."""
        if status.tag == 'GroupInfo':
            self.name = status.findtext('GroupName')

        capabilities = (status.findtext('GroupCapabilityIDs') or
                        status.findtext('CapabilityID'))
        currentstate = (status.findtext('GroupCapabilityValues') or
                        status.findtext('CapabilityValue'))

        if capabilities is not None:
            self.capabilities = [
                CAPABILITY_ID2NAME.get(c, c)
                for c in capabilities.split(',')
            ]
        if currentstate is not None:
            self._values = currentstate.split(',')
        super(Group, self).update_state(status)

    def __repr__(self):
        """Return a string representation of the device."""
        return '<GROUP "{name}">'.format(name=self.name)

    @property
    def device_type(self):
        """Return what kind of WeMo this device is."""
        return "Group"
