"""Tests for the Bridge class."""
import os
from xml.etree import cElementTree as et

import pytest

from pywemo import Bridge

LIGHT_ID = '0017880108DA898B'


@pytest.mark.vcr()
def test_light_turn_on():
    bridge = Bridge('http://192.168.1.100:49153/setup.xml', '')

    lights, _ = bridge.bridge_update()
    assert LIGHT_ID in lights
    light = lights[LIGHT_ID]

    # Turn on.
    light.turn_on()
    assert light.get_state(force_update=True)['onoff'] == 1


@pytest.mark.vcr()
def test_light_turn_off():
    bridge = Bridge('http://192.168.1.100:49153/setup.xml', '')

    lights, _ = bridge.bridge_update()
    assert LIGHT_ID in lights
    light = lights[LIGHT_ID]

    # Turn off.
    light.turn_off()
    assert light.get_state(force_update=True)['onoff'] == 0


@pytest.mark.vcr()
def test_bridge_getdevicestatus():
    bridge = Bridge('http://192.168.1.100:49153/setup.xml', '')

    status = bridge.bridge_getdevicestatus(LIGHT_ID)
    expected = b''.join(
        [
            b'<DeviceStatus>',
            b'<IsGroupAction>NO</IsGroupAction>',
            b'<DeviceID available="YES">0017880108DA898B</DeviceID>',
            b'<CapabilityID>10006,10008,30008,30009,3000A</CapabilityID>',
            b'<CapabilityValue>0,255:0,,,</CapabilityValue>',
            b'<LastEventTimeStamp>0</LastEventTimeStamp>',
            b'</DeviceStatus>',
        ]
    )
    assert et.tostring(status) == expected
