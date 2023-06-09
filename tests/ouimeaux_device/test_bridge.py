"""Integration tests for the Bridge class."""

import pytest
from lxml import etree as et

from pywemo import Bridge

LIGHT_ID = "F0D1B8000001420C"
GROUP_ID = "12345678"


@pytest.fixture
def bridge(vcr):
    with vcr.use_cassette("WeMo_WW_2.00.11057.PVT-OWRT-Link.yaml"):
        return Bridge("http://192.168.1.100:49153/setup.xml")


@pytest.fixture
def light(bridge):
    assert LIGHT_ID in bridge.lights
    light = bridge.lights[LIGHT_ID]
    return light


@pytest.fixture
def group(bridge):
    assert GROUP_ID in bridge.groups
    group = bridge.groups[GROUP_ID]
    return group


@pytest.mark.vcr()
def test_light_turn_on(light):
    light.turn_on(level=120)
    assert light.get_state(force_update=True)["onoff"] == 1
    assert light.get_state()["level"] == 120


@pytest.mark.vcr()
def test_light_turn_off(light):
    light.turn_off()
    assert light.get_state(force_update=True)["onoff"] == 0


@pytest.mark.vcr()
def test_light_color_fade(light):
    light.set_color((0.701, 0.299), 5, False)

    color_xy = light.get_state(force_update=True)["color_xy"]
    assert color_xy == pytest.approx((0.701, 0.299), rel=1e-3)


@pytest.mark.vcr()
def test_light_color_temperature(light):
    light.set_temperature(kelvin=5000)
    assert light.get_state(force_update=True)["temperature_kelvin"] == 5000


@pytest.mark.vcr()
def test_light_start_ramp(light):
    light.start_ramp("1", 100)
    light.get_state(force_update=True)


@pytest.mark.vcr()
def test_group_turn_on(group):
    group.turn_on()
    assert group.get_state(force_update=True)["onoff"] == 1


@pytest.mark.vcr()
def test_group_turn_off(group):
    group.turn_off()
    assert group.get_state(force_update=True)["onoff"] == 0


@pytest.mark.vcr()
def test_group_toggle(group):
    orig_onoff = group.get_state()["onoff"]
    group.toggle()
    assert group.get_state(force_update=True)["onoff"] != orig_onoff


@pytest.mark.vcr()
def test_bridge_getdevicestatus(bridge):
    status = bridge.bridge_getdevicestatus(LIGHT_ID)
    expected = b"".join(
        [
            b"<DeviceStatus>",
            b"<IsGroupAction>NO</IsGroupAction>",
            b'<DeviceID available="YES">F0D1B8000001420C</DeviceID>',
            b"<CapabilityID>",
            b"10006,10008,10300,30008,30009,3000A,30301",
            b"</CapabilityID>",
            b"<CapabilityValue>",
            b"0,120:0,45940:19594:50,,,,200:0",
            b"</CapabilityValue>",
            b"<LastEventTimeStamp>0</LastEventTimeStamp>",
            b"</DeviceStatus>",
        ]
    )
    assert et.tostring(status) == expected


@pytest.mark.vcr()
def test_bridge_unavailable_light(bridge, light):
    assert light.get_state()["available"] is True
    bridge.bridge_update(force_update=True)
    assert light.get_state()["available"] is False


@pytest.mark.parametrize(
    "update,expected_updated,expected_state",
    [
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f'<DeviceID available="YES">{LIGHT_ID}</DeviceID>'
                "<CapabilityId>10006</CapabilityId>"
                "<Value>0</Value>"
                "</StateEvent>"
            ),
            True,
            {
                "available": True,
                "level": 120,
                "onoff": 0,
                "color_xy": (0.17599755855649654, 0.653986419470512),
                "temperature_kelvin": 2092,
                "temperature_mireds": 478,
            },
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f'<DeviceID available="YES">{LIGHT_ID}</DeviceID>'
                "<CapabilityId>10006</CapabilityId>"
                "<Value>1</Value>"
                "</StateEvent>"
            ),
            True,
            {
                "available": True,
                "level": 120,
                "onoff": 1,
                "color_xy": (0.17599755855649654, 0.653986419470512),
                "temperature_kelvin": 2092,
                "temperature_mireds": 478,
            },
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f'<DeviceID available="YES">{LIGHT_ID}</DeviceID>'
                "<CapabilityId>10008</CapabilityId>"
                "<Value>128:0</Value>"
                "</StateEvent>"
            ),
            True,
            {
                "available": True,
                "level": 128,
                "onoff": 0,
                "color_xy": (0.17599755855649654, 0.653986419470512),
                "temperature_kelvin": 2092,
                "temperature_mireds": 478,
            },
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f'<DeviceID available="NO">{LIGHT_ID}</DeviceID>'
                "<CapabilityId>10006</CapabilityId>"
                "<Value>0</Value>"
                "</StateEvent>"
            ),
            True,
            {
                "available": False,
                "level": 120,
                "onoff": 0,
                "color_xy": (0.17599755855649654, 0.653986419470512),
                "temperature_kelvin": 2092,
                "temperature_mireds": 478,
            },
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f"<DeviceID>{LIGHT_ID}</DeviceID>"
                "<CapabilityId>10006</CapabilityId>"
                "<Value>0</Value>"
                "</StateEvent>"
            ),
            True,
            {
                "available": True,
                "level": 120,
                "onoff": 0,
                "color_xy": (0.17599755855649654, 0.653986419470512),
                "temperature_kelvin": 2092,
                "temperature_mireds": 478,
            },
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f"<DeviceID>{LIGHT_ID}</DeviceID>"
                "<CapabilityId>30301</CapabilityId>"
                "<Value>2700:0</Value>"
                "</StateEvent>"
            ),
            True,
            {
                "available": True,
                "color_xy": (0.17599755855649654, 0.653986419470512),
                "level": 120,
                "onoff": 0,
                "temperature_kelvin": 370,
                "temperature_mireds": 2700,
            },
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f"<DeviceID>{LIGHT_ID}</DeviceID>"
                "<CapabilityId>30301</CapabilityId>"
                "<Value>0:0</Value>"
                "</StateEvent>"
            ),
            False,
            {},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f"<DeviceID>{LIGHT_ID}</DeviceID>"
                "<CapabilityId>99999</CapabilityId>"
                "<Value>2700:0</Value>"
                "</StateEvent>"
            ),
            False,
            {},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                "<DeviceID>SomeOtherDevice</DeviceID>"
                "<CapabilityId>10006</CapabilityId>"
                "<Value>0</Value>"
                "</StateEvent>"
            ),
            False,
            {},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                "<MissingDevice/>"
                "<CapabilityId>10006</CapabilityId>"
                "<Value>0</Value>"
                "</StateEvent>"
            ),
            False,
            {},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f"<DeviceID>{LIGHT_ID}</DeviceID>"
                "<MissingCapabilityId/>"
                "<Value>0</Value>"
                "</StateEvent>"
            ),
            False,
            {},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f"<DeviceID>{LIGHT_ID}</DeviceID>"
                "<CapabilityId>10006</CapabilityId>"
                "<MissingValue/>"
                "</StateEvent>"
            ),
            False,
            {},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f"<DeviceID>{LIGHT_ID}</DeviceID>"
                "<CapabilityId>10006</CapabilityId>"
                "<Value>Invalid</Value>"
                "</StateEvent>"
            ),
            False,
            {},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f"<DeviceID>{LIGHT_ID}</DeviceID>"
                "<CapabilityId>NewCapability</CapabilityId>"
                "<Value>0</Value>"
                "</StateEvent>"
            ),
            False,
            {},
        ),
        (
            (
                '<?xml version="1.0" encoding="utf-8"?><StateEvent>'
                f"<DeviceID>{LIGHT_ID}</DeviceID>"
                "<CapabilityId>10300</CapabilityId>"
                "<Value>0</Value>"
                "</StateEvent>"
            ),
            False,
            {},
        ),
    ],
)
def test_subscription_update(update, expected_updated, expected_state, bridge):
    updated = bridge.subscription_update("StatusChange", update)
    assert updated == expected_updated
    if updated:
        assert bridge.lights[LIGHT_ID].get_state() == expected_state
