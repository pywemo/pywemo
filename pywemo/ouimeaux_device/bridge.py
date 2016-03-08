from pywemo.ouimeaux_device import Device

from xml.etree import cElementTree as et
import six
try:
    from html import escape as html_escape
except ImportError:
    from cgi import escape as html_escape


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

    def __repr__(self):
        self.bridge_get_lights()
        self.bridge_get_groups()
        return '<WeMo Bridge "{name}", Lights: {LightCount}, Groups: {GroupCount}>'.format(name=self.name, LightCount=len(self.Lights), GroupCount=len(self.Groups))

    def bridge_get_lights(self):
        UDN = self.basicevent.GetMacAddr().get('PluginUDN')
        endDevices = self.bridge.GetEndDevices(DevUDN=UDN,ReqListType='PAIRED_LIST')
        endDeviceList = et.fromstring(endDevices.get('DeviceLists'))

        for light in endDeviceList.iter('DeviceInfo'):
            self.Lights[self.light_name(light)] = light
        return self.Lights

    def bridge_get_groups(self):
        UDN = self.basicevent.GetMacAddr().get('PluginUDN')
        endDevices = self.bridge.GetEndDevices(DevUDN=UDN,ReqListType='PAIRED_LIST')
        endDeviceList = et.fromstring(endDevices.get('DeviceLists'))

        for group in endDeviceList.iter('GroupInfo'):
            self.Groups[self.group_name(group)] = group
        return self.Groups

    def light_attributes(self, light):
        return {
            'devIndex' : light.find('DeviceIndex').text,
            'devID' : light.find('DeviceID').text,
            'name' : light.find('FriendlyName').text,
            'iconvalue' : light.find('IconVersion').text,
            'firmware' : light.find('FirmwareVersion').text,
            'capabilities' : light.find('CapabilityIDs').text,
            'state' : light.find('CurrentState').text,
            'manufacturer' : light.find('Manufacturer').text,
            'model' : light.find('ModelCode').text,
            'certified' : light.find('WeMoCertified').text
        }

    def group_attributes(self, group):
        return {
            'GroupID' : group.find('GroupID').text,
            'name' : group.find('GroupName').text,
            'capabilities' : group.find('GroupCapabilityIDs').text,
            'state': group.find('GroupCapabilityValues').text
        }

    def light_name(self, light):
        return self.light_attributes(light).get('name')

    def group_name(self, group):
        return self.group_attributes(group).get('name')

    def light_get_id(self, light):
        return self.light_attributes(light).get('devID')

    def group_get_id(self, group):
        return self.group_attributes(group).get('GroupID')

    def light_get_state(self, light):
        """Return a dict with
        state = 0 (off) or 1 (on)
        dim = 0-255 dark to bright
        """
        state = self.getdevicestatus(light)
        return dict(
            state=state['onoff'],
            dim=state['levelcontrol'][0],
        )

    def group_get_state(self, group):
        """Return a dict with
        state = 0 (off) or 1 (on)
        dim = 0-255 dark to bright
        """
        state = self.getdevicestatus(group)
        return dict(
            state=state['onoff'],
            dim=state['levelcontrol'][0],
        )

    def light_set_state(self, light, state=None, dim=None):
        if dim is None:
            return self.setdevicestatus(light, onoff=state)
        return self.setdevicestatus(light, levelcontrol=(dim, 0))

    def group_set_state(self, group, state=None, dim=None):
        if dim is None:
            return self.setdevicestatus(group, onoff=state)
        return self.setdevicestatus(group, levelcontrol=(dim, 0))

    def capabilities(self, device):
        if device.tag == 'DeviceInfo':
            capids = device.find('CapabilityIDs')
        else:
            assert device.tag == 'GroupInfo'
            capids = device.find('GroupCapabilityIDs')
        return [CAPABILITY_ID2NAME.get(c, c) for c in capids.text.split(',')]

    def getdevicestatus(self, device):
        if device.tag == 'DeviceInfo':
            states = device.find('CurrentState').text
        else:
            assert device.tag == 'GroupInfo'
            states = device.find('GroupCapabilityValues').text

        status = {}
        capabilities = self.capabilities(device)
        for capability, state in zip(capabilities, states.split(',')):
            if not state:
                state = None
            elif ':' in state:
                state = tuple(int(v) for v in state.split(':'))
            else:
                state = int(state)
            status[capability] = state
        return status

    def setdevicestatus(self, device, **kwargs):
        if device.tag == 'DeviceInfo':
            isgroup = 'NO'
            devid = self.light_get_id(device)
        else:
            assert device.tag == 'GroupInfo'
            isgroup = 'YES'
            devid = self.group_get_id(device)

        capids = []
        values = []
        for cap, val in kwargs.items():
            capids.append(CAPABILITY_NAME2ID[cap])

            if not isinstance(val, (list, tuple)):
                val = (val,)
            values.append(':'.join(str(v) for v in val))

        req = et.Element('DeviceStatus')
        et.SubElement(req, 'IsGroupAction').text = isgroup
        et.SubElement(req, 'DeviceID', available="YES").text = str(devid)
        et.SubElement(req, 'CapabilityID').text = ','.join(capids)
        et.SubElement(req, 'CapabilityValue').text = ','.join(values)

        buf = six.StringIO()
        et.ElementTree(req).write(buf, encoding='unicode',
                                  xml_declaration=True)
        sendState = html_escape(buf.getvalue(), quote=True)
        return self.bridge.SetDeviceStatus(DeviceStatusList=sendState)

    def get_state(self, device):
        status = self.getdevicestatus(device)
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
            colorxy = colorx / 65535., colory / 65535.
            state['color_xy'] = colorxy

        return state

    def turn_on(self, device, level=None, transition=0):
        T = limit(int(transition * 10), 0, 65535)
        capabilities = self.capabilities(device)

        if level is not None and 'levelcontrol' in capabilities:
            level = limit(int(level), 0, 255)
            return self.setdevicestatus(device, levelcontrol=(level, T))
        elif level == 0:
            return self.setdevicestatus(device, onoff=OFF)
        else:
            return self.setdevicestatus(device, onoff=ON)

    def turn_off(self, device):
        return self.setdevicestatus(device, onoff=OFF)

    def toggle(self, device):
        return self.setdevicestatus(device, onoff=TOGGLE)

    def set_temperature(self, device, kelvin=2700, mireds=None, transition=0):
        T = limit(int(transition * 10), 0, 65535)
        if mireds is None:
            mireds = 1000000 / kelvin

        # Lightify RGBW has a range of 1900-6500K and will not change
        # temperature if the requested value is outside of [151, 555].
        mireds = limit(int(mireds), 151, 555)
        return self.setdevicestatus(device, colortemperature=(mireds, T))

    def set_color(self, device, colorxy, transition=0):
        T = limit(int(transition * 10), 0, 65535)
        colorx = limit(int(colorxy[0] * 65535), 0, 65535)
        colory = limit(int(colorxy[1] * 65535), 0, 65535)
        return self.setdevicestatus(device, colorcontrol=(colorx, colory, T))

    def start_ramp(self, device, up, rate):
        updown = '1' if up else '0'
        rate = limit(int(rate), 0, 255)
        return self.setdevicestatus(device, levelcontrol_move=(updown, rate))

    def stop_ramp(self, device):
        return self.setdevicestatus(device, levelcontrol_stop='')

    def sleepfader(self, device, fadetime):
        return self.setdevicestatus(device, sleepfader=int(fadetime))
