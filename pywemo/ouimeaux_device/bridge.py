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
        self.get_state(force_update=True)

    def __repr__(self):
        return '<WeMo Bridge "{name}", Lights: {l}, Groups: {g}>'.format(
            name=self.name, l=len(self.Lights), g=len(self.Groups))

    def get_state(self, force_update=False):
        if force_update or not self.Lights:
            UDN = self.basicevent.GetMacAddr().get('PluginUDN')
            endDevices = self.bridge.GetEndDevices(
                DevUDN=UDN, ReqListType='PAIRED_LIST')
            endDeviceList = et.fromstring(endDevices.get('DeviceLists'))

            for light in endDeviceList.iter('DeviceInfo'):
                uniqueID = light.find('DeviceID').text
                if uniqueID in self.Lights:
                    self.Lights[uniqueID].update(light)
                else:
                    self.Lights[uniqueID] = Light(self, light)

            for group in endDeviceList.iter('GroupInfo'):
                uniqueID = group.find('GroupID').text
                if uniqueID in self.Groups:
                    self.Groups[uniqueID].update(group)
                else:
                    self.Groups[uniqueID] = Group(self, group)
        return self.Lights, self.Groups

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
        self.capabilities = []
        self._states = []
        self.update(info)

    def update(self, info):
        self.info = info

    def get_state(self, force_update=False):
        if force_update:
            self.bridge.get_state(force_update=True)
        return self.state

    def _setdevicestatus(self, **kwargs):
        isgroup = 'YES' if isinstance(self, Group) else 'NO'

        capids = []
        values = []
        for cap, val in kwargs.items():
            capids.append(CAPABILITY_NAME2ID[cap])

            if not isinstance(val, (list, tuple)):
                val = (val,)
            values.append(':'.join(str(v) for v in val))

        return self.bridge.bridge_setdevicestatus(
            isgroup, self.uniqueID, capids, values)

    def _getdevicestatus(self):
        status = {}
        for capability, state in zip(self.capabilities, self._states):
            if not state:
                state = None
            elif ':' in state:
                state = tuple(int(v) for v in state.split(':'))
            else:
                state = int(state)
            status[capability] = state
        return status

    @property
    def state(self):
        status = self._getdevicestatus()

        state = {}
        state['onoff'] = status['onoff']

        if 'levelcontrol' in status:
            state['level'] = status['levelcontrol'][0]

        if 'colortemperature' in status:
            temperature = status['colortemperature'][0]
            state['temperature_mireds'] = temperature
            state['temperature_kelvin'] = int(1000000 / temperature)

        if 'colorcontrol' in status:
            colorx, colory = status['colorcontrol'][:2]
            colorx, colory = colorx / 65535., colory / 65535.
            state['color_xy'] = colorx, colory
        return state

    def turn_on(self, *kwargs):
        return self._setdevicestatus(onoff=ON)

    def turn_off(self):
        return self._setdevicestatus(onoff=OFF)

    def toggle(self):
        return self._setdevicestatus(onoff=TOGGLE)


class Light(LinkedDevice):
    def __init__(self, bridge, info):
        super(Light, self).__init__(bridge, info)
        self.devIndex = info.find('DeviceIndex').text
        self.uniqueID = info.find('DeviceID').text
        self.iconvalue = info.find('IconVersion').text
        self.firmware = info.find('FirmwareVersion').text
        self.manufacturer = info.find('Manufacturer').text
        self.model = info.find('ModelCode').text
        self.certified = info.find('WeMoCertified').text

        self.temperature_range, self.gamut = get_profiles(self.model)

    def update(self, info):
        self.info = info
        self.name = info.find('FriendlyName').text
        self.capabilities = [
            CAPABILITY_ID2NAME.get(c, c)
            for c in info.find('CapabilityIDs').text.split(',')
        ]
        self._states = info.find('CurrentState').text.split(',')

    def __repr__(self):
        return '<LIGHT "{name}">'.format(name=self.name)

    def turn_on(self, level=None, transition=0):
        T = limit(int(transition * 10), 0, 65535)


        if level == 0 and 'sleepfader' in self.capabilities:
            return self.sleepfader(transition)

        elif level is not None and 'levelcontrol' in self.capabilities:
            # Work around fw bugs. When we set a new brightness level but
            # the bulb is off, it first turns on at the old brightness and
            # then fades to the new setting. So we have to force the saved
            # brightness to 0 first. Second problem is that when we turn a
            # bulb on with levelcontrol the onoff state doesn't update.
            is_on = self.get_state(force_update=True)['onoff'] != 0
            if not is_on:
                self._setdevicestatus(levelcontrol=(1, 0))
                self._setdevicestatus(onoff=ON)

            level = limit(int(level), 0, 255)
            return self._setdevicestatus(levelcontrol=(level, T))

        elif level == 0:
            return self._setdevicestatus(onoff=OFF)

        else:
            return self._setdevicestatus(onoff=ON)

    def set_temperature(self, kelvin=2700, mireds=None, transition=0):
        T = limit(int(transition * 10), 0, 65535)
        if mireds is None:
            mireds = 1000000 / kelvin
        mireds = limit(int(mireds), *self.temperature_range)
        return self._setdevicestatus(colortemperature=(mireds, T))

    def set_color(self, colorxy, transition=0):
        T = limit(int(transition * 10), 0, 65535)
        colorxy = limit_to_gamut(colorxy, self.gamut)
        colorx = limit(int(colorxy[0] * 65535), 0, 65535)
        colory = limit(int(colorxy[1] * 65535), 0, 65535)
        return self._setdevicestatus(colorcontrol=(colorx, colory, T))

    def start_ramp(self, up, rate):
        updown = '1' if up else '0'
        rate = limit(int(rate), 0, 255)
        return self._setdevicestatus(levelcontrol_move=(updown, rate))

    def stop_ramp(self):
        return self._setdevicestatus(levelcontrol_stop='')

    def sleepfader(self, fadetime):
        fadetime = limit(int(fadetime * 10), 0, 65535)
        reference = int(time.time())
        return self._setdevicestatus(sleepfader=(fadetime, reference))


class Group(LinkedDevice):
    def __init__(self, bridge, info):
        super(Group, self).__init__(bridge, info)
        self.uniqueID = info.find('GroupID').text

    def update(self, info):
        self.name = info.find('GroupName').text
        self.capabilities = [
            CAPABILITY_ID2NAME.get(c, c)
            for c in info.find('GroupCapabilityIDs').text.split(',')
        ]
        self._states = info.find('GroupCapabilityValues').text.split(',')

    def __repr__(self):
        return '<GROUP "{name}">'.format(name=self.name)
