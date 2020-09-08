"""Representation of a WeMo Maker device."""
from xml.etree import cElementTree as et
from .switch import Switch


class Maker(Switch):
    """Representation of a WeMo Maker device."""

    def __repr__(self):
        """Return a string representation of the device."""
        return '<WeMo Maker "{name}">'.format(name=self.name)

    @property
    def maker_params(self):
        """Get and parse the device attributes."""
        # pylint: disable=maybe-no-member
        makerresp = self.deviceevent.GetAttributes().get('attributeList')
        makerresp = "<attributes>" + makerresp + "</attributes>"
        makerresp = makerresp.replace("&gt;", ">")
        makerresp = makerresp.replace("&lt;", "<")
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
            'switchstate': int(switchstate),
            'sensorstate': int(sensorstate),
            'switchmode': int(switchmode),
            'hassensor': int(hassensor)}

    def get_state(self, force_update=False):
        """Return 0 if off and 1 if on."""
        # The base implementation using GetBinaryState doesn't
        # work for the Maker (always returns 0),
        # so pull the switch state from the atrributes instead
        if force_update or self._state is None:
            params = self.maker_params or {}
            try:
                self._state = int(params.get('switchstate', 0))
            except ValueError:
                self._state = 0

        return self._state

    def set_state(self, state):
        """Set the state of this device to on or off."""
        # The Maker has a momentary mode - so it's not safe to assume
        # the state is what you just set, so re-read it from the device

        # pylint: disable=maybe-no-member
        self.basicevent.SetBinaryState(BinaryState=int(state))
        self.get_state(True)

    @property
    def device_type(self):
        """Return what kind of WeMo this device is."""
        return "Maker"

    @property
    def sensor_state(self):
        """Return the state of the sensor."""
        return self.maker_params['sensorstate']

    @property
    def switch_mode(self):
        """Return the switch mode of the sensor."""
        return self.maker_params['switchmode']

    @property
    def has_sensor(self):
        """Return whether the device has a sensor."""
        return self.maker_params['hassensor']
