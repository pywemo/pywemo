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


@pytest.mark.parametrize(
    "update,expected_updated,expected_state",
    [
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f'<DeviceID available="YES">{LIGHT_ID}</DeviceID>'
                '<CapabilityId>10006</CapabilityId>'
                '<Value>0</Value>'
                '</StateEvent>'
            ),
            True,
            {'available': True, 'level': 255, 'onoff': 0},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f'<DeviceID available="YES">{LIGHT_ID}</DeviceID>'
                '<CapabilityId>10006</CapabilityId>'
                '<Value>1</Value>'
                '</StateEvent>'
            ),
            True,
            {'available': True, 'level': 255, 'onoff': 1},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f'<DeviceID available="YES">{LIGHT_ID}</DeviceID>'
                '<CapabilityId>10008</CapabilityId>'
                '<Value>128:0</Value>'
                '</StateEvent>'
            ),
            True,
            {'available': True, 'level': 128, 'onoff': 1},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f'<DeviceID available="NO">{LIGHT_ID}</DeviceID>'
                '<CapabilityId>10006</CapabilityId>'
                '<Value>0</Value>'
                '</StateEvent>'
            ),
            True,
            {'available': False, 'level': 255, 'onoff': 0},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f'<DeviceID>{LIGHT_ID}</DeviceID>'
                '<CapabilityId>10006</CapabilityId>'
                '<Value>0</Value>'
                '</StateEvent>'
            ),
            True,
            {'available': True, 'level': 255, 'onoff': 0},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f'<DeviceID>{LIGHT_ID}</DeviceID>'
                '<CapabilityId>30301</CapabilityId>'
                '<Value>2700:0</Value>'
                '</StateEvent>'
            ),
            False,
            {},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                '<DeviceID>SomeOtherDevice</DeviceID>'
                '<CapabilityId>10006</CapabilityId>'
                '<Value>0</Value>'
                '</StateEvent>'
            ),
            False,
            {},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                '<MissingDevice/>'
                '<CapabilityId>10006</CapabilityId>'
                '<Value>0</Value>'
                '</StateEvent>'
            ),
            False,
            {},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f'<DeviceID>{LIGHT_ID}</DeviceID>'
                '<MissingCapabilityId/>'
                '<Value>0</Value>'
                '</StateEvent>'
            ),
            False,
            {},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f'<DeviceID>{LIGHT_ID}</DeviceID>'
                '<CapabilityId>10006</CapabilityId>'
                '<MissingValue/>'
                '</StateEvent>'
            ),
            False,
            {},
        ),
    ],
)
def test_subscription_update(update, expected_updated, expected_state, bridge):
    updated = bridge.subscription_update('StatusChange', update)
    assert updated == expected_updated
    if updated:
        assert bridge.Lights[LIGHT_ID].get_state() == expected_state
