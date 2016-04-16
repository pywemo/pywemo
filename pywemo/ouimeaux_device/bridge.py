import time
from xml.etree import cElementTree as et
import six
six.add_move(six.MovedAttribute('html_escape', 'cgi', 'html', 'escape'))
from six.moves import html_escape

from . import Device
from ..color import get_profiles, limit_to_gamut

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
    """Returns value clipped to the range [min_val, max_val]"""
    return max(min_val, min(value, max_val))


class Bridge(Device):
    Lights = {}
    Groups = {}

    def __init__(self, *args, **kwargs):
        super(Bridge, self).__init__(*args, **kwargs)
        self.bridge_update()

    def __repr__(self):
        return '<WeMo Bridge "{name}", Lights: {l}, Groups: {g}>'.format(
            name=self.name, l=len(self.Lights), g=len(self.Groups))

    def bridge_update(self):
        UDN = self.basicevent.GetMacAddr().get('PluginUDN')
        endDevices = self.bridge.GetEndDevices(
            DevUDN=UDN, ReqListType='PAIRED_LIST')
        endDeviceList = et.fromstring(endDevices.get('DeviceLists'))

        for light in endDeviceList.iter('DeviceInfo'):
            uniqueID = light.find('DeviceID').text
            if uniqueID in self.Lights:
                self.Lights[uniqueID]._update_state(light)
            else:
                self.Lights[uniqueID] = Light(self, light)

        for group in endDeviceList.iter('GroupInfo'):
            uniqueID = group.find('GroupID').text
            if uniqueID in self.Groups:
                self.Groups[uniqueID]._update_state(group)
            else:
                self.Groups[uniqueID] = Group(self, group)

        return self.Lights, self.Groups

    def bridge_getdevicestatus(self, deviceid):
        statusList = self.bridge.GetDeviceStatus(DeviceIDs=deviceid)
        deviceStatusList = et.fromstring(statusList.get('DeviceStatusList'))
        return deviceStatusList.find('DeviceStatus')

    def bridge_setdevicestatus(self, isgroup, deviceid, capids, values):
        req = et.Element('DeviceStatus')
        et.SubElement(req, 'IsGroupAction').text = isgroup
        et.SubElement(req, 'DeviceID', available="YES").text = deviceid
        et.SubElement(req, 'CapabilityID').text = ','.join(capids)
        et.SubElement(req, 'CapabilityValue').text = ','.join(values)

        buf = six.StringIO()
        et.ElementTree(req).write(buf, encoding='unicode',
                                  xml_declaration=True)
        sendState = html_escape(buf.getvalue(), quote=True)
        return self.bridge.SetDeviceStatus(DeviceStatusList=sendState)


class LinkedDevice(object):
    def __init__(self, bridge, info):
        self.bridge = bridge
        self.state = {}
        self.capabilities = []
        self._values = []
        self._update_state(info)
        self._last_err = None

    def get_state(self, force_update=False):
        if force_update:
            self.bridge.bridge_update()
        return self.state

    def _update_state(self, status):
        """Subclasses should parse status into self.capabilities and
        self._values and then call this to populate self.state"""
        status = {}
        for capability, value in zip(self.capabilities, self._values):
            if not value:
                value = None
            elif ':' in value:
                value = tuple(int(v) for v in value.split(':'))
            else:
                value = int(value)
            status[capability] = value

        # unreachable devices have empty strings for all capability values
        if status['onoff'] is None:
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
        isgroup = 'YES' if isinstance(self, Group) else 'NO'

        capids = []
        values = []
        for cap, val in kwargs.items():
            capids.append(CAPABILITY_NAME2ID[cap])

            if not isinstance(val, (list, tuple)):
                val = (val,)
            values.append(':'.join(str(v) for v in val))

        self._last_err = self.bridge.bridge_setdevicestatus(
            isgroup, self.uniqueID, capids, values)
        return self

    def turn_on(self, **kwargs):
        return self._setdevicestatus(onoff=ON)

    def turn_off(self, **kwargs):
        return self._setdevicestatus(onoff=OFF)

    def toggle(self):
        return self._setdevicestatus(onoff=TOGGLE)


class Light(LinkedDevice):
    def __init__(self, bridge, info):
        super(Light, self).__init__(bridge, info)
        self.devIndex = info.findtext('DeviceIndex')
        self.uniqueID = info.findtext('DeviceID')
        self.iconvalue = info.findtext('IconVersion')
        self.firmware = info.findtext('FirmwareVersion')
        self.manufacturer = info.findtext('Manufacturer')
        self.model = info.findtext('ModelCode')
        self.certified = info.findtext('WeMoCertified')

        self.temperature_range, self.gamut = get_profiles(self.model)
        self._pending = {}

    def _queuedevicestatus(self, queue=False, **kwargs):
        if kwargs:
            self._pending.update(kwargs)
        if not queue:
            self._setdevicestatus(**self._pending)
            self._pending = {}
        return self

    def _update_state(self, status):
        if status.tag == 'DeviceInfo':
            self.name = status.findtext('FriendlyName')

        capabilities = (status.findtext('CapabilityIDs') or
                        status.findtext('CapabilityID'))
        currentstate = (status.findtext('CurrentState') or
                        status.findtext('CapabilityValue'))

        self.capabilities = [
            CAPABILITY_ID2NAME.get(c, c)
            for c in capabilities.split(',')
        ]
        self._values = currentstate.split(',')
        super(Light, self)._update_state(status)

    def __repr__(self):
        return '<LIGHT "{name}">'.format(name=self.name)

    def turn_on(self, level=None, transition=0, force_update=False):
        T = limit(int(transition * 10), 0, 65535)

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
            if level is None:
                level = self.state['level']

            if self.state['onoff'] == 0:
                self._setdevicestatus(levelcontrol=(0, 0), onoff=ON)

            level = limit(int(level), 0, 255)
            return self._queuedevicestatus(levelcontrol=(level, T))
        else:
            return self._queuedevicestatus(onoff=ON)

    def turn_off(self, transition=0):
        if transition and 'sleepfader' in self.capabilities:
            # Sleepfader control did not turn off bulb when fadetime was 0
            T = limit(int(transition * 10), 1, 65535)
            reference = int(time.time())
            return self._queuedevicestatus(sleepfader=(T, reference))
        else:
            return self._queuedevicestatus(onoff=OFF)

    def set_temperature(self, kelvin=2700, mireds=None,
                        transition=0, delay=True):
        T = limit(int(transition * 10), 0, 65535)
        if mireds is None:
            mireds = 1000000 / kelvin
        mireds = limit(int(mireds), *self.temperature_range)
        return self._queuedevicestatus(
            colortemperature=(mireds, T), queue=delay)

    def set_color(self, colorxy, transition=0, delay=True):
        T = limit(int(transition * 10), 0, 65535)
        colorxy = limit_to_gamut(colorxy, self.gamut)
        colorx = limit(int(colorxy[0] * 65535), 0, 65535)
        colory = limit(int(colorxy[1] * 65535), 0, 65535)
        return self._queuedevicestatus(
            colorcontrol=(colorx, colory, T), queue=delay)

    def start_ramp(self, up, rate):
        updown = '1' if up else '0'
        rate = limit(int(rate), 0, 255)
        return self._queuedevicestatus(levelcontrol_move=(updown, rate))

    def stop_ramp(self):
        return self._setdevicestatus(levelcontrol_stop='')


class Group(LinkedDevice):
    def __init__(self, bridge, info):
        super(Group, self).__init__(bridge, info)
        self.uniqueID = info.findtext('GroupID')

    def _update_state(self, status):
        if status.tag == 'GroupInfo':
            self.name = status.findtext('GroupName')

        capabilities = (status.findtext('GroupCapabilityIDs') or
                        status.findtext('CapabilityID'))
        currentstate = (status.findtext('GroupCapabilityValues') or
                        status.findtext('CapabilityValue'))

        self.capabilities = [
            CAPABILITY_ID2NAME.get(c, c)
            for c in capabilities.split(',')
        ]
        self._values = currentstate.split(',')
        super(Group, self)._update_state(status)

    def __repr__(self):
        return '<GROUP "{name}">'.format(name=self.name)
