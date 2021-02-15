"""Integration tests for the Bridge class."""

import pytest
from lxml import etree as et

from pywemo import Bridge

LIGHT_ID = '0017880108DA898B'


@pytest.fixture
def bridge(vcr):
    with vcr.use_cassette('WeMo_WW_2.00.11057.PVT-OWRT-Link.yaml'):
        return Bridge('http://192.168.1.100:49153/setup.xml')


@pytest.mark.vcr()
def test_light_turn_on(bridge):
    lights, _ = bridge.bridge_update()
    assert LIGHT_ID in lights
    light = lights[LIGHT_ID]

    # Turn on.
    light.turn_on()
    assert light.get_state(force_update=True)['onoff'] == 1


@pytest.mark.vcr()
def test_light_turn_off(bridge):
    lights, _ = bridge.bridge_update()
    assert LIGHT_ID in lights
    light = lights[LIGHT_ID]

    # Turn off.
    light.turn_off()
    assert light.get_state(force_update=True)['onoff'] == 0


@pytest.mark.vcr()
def test_bridge_getdevicestatus(bridge):
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
