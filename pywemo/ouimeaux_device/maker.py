from datetime import datetime
from . import Device
from .switch import Switch
from xml.etree import cElementTree as et


class Maker(Switch):

    def __repr__(self):
        return '<WeMo Maker "{name}">'.format(name=self.name)

    @property
    def maker_params(self):
        makerresp = self.deviceevent.GetAttributes().get('attributeList')
        makerresp = "<attributes>" + makerresp + "</attributes>"
        makerresp = makerresp.replace("&gt;",">")
        makerresp = makerresp.replace("&lt;","<")
        attributes = et.fromstring(makerresp)
        for attribute in attributes:
            if attribute[0].text == "Switch":
                switchstate = attribute[1].text
            elif attribute[0].text == "Sensor":
                sensorstate = attribute[1].text
            elif attribute[0].text == "SwitchMode":
                switchmode = attribute[1].text
            elif attribute[0].text == "SensorPresent":
                hassensor = attribute[1].text
        return {
            'switchstate' : int(switchstate),
            'sensorstate' : int(sensorstate),
            'switchmode' : int(switchmode),
            'hassensor' : int(hassensor)}

    def get_state(self, force_update=False):
        """
        Returns 0 if off and 1 if on.
        """
        # The base implementation using GetBinaryState doesn't for for Maker (always returns 0).
        # So pull the switch state from the atrributes instead
        if force_update or self._state is None:
            params = self.maker_params or {}
            try:
                self._state = int(params.get('switchstate',0))
            except ValueError:
                self._state = 0

        return self._state

    def set_state(self, state):
        """
        Set the state of this device to on or off.
        """
        # The Maker has a momentary mode - so it's not safe to assume the state is what you just set
        # so re-read it from the device
        self.basicevent.SetBinaryState(BinaryState=int(state))
        self.get_state(True)

    @property
    def sensor_state(self):
        return self.maker_params['sensorstate']

    @property
    def switch_mode(self):
        return self.maker_params['switchmode']

    @property
    def has_sensor(self):
        return self.maker_params['hassensor']
