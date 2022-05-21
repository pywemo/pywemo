"""Tests for the pywemo.discovery module."""
import unittest.mock as mock

import pytest
import requests

from pywemo import discovery, exceptions, ssdp


@pytest.mark.parametrize(
    "udn,wemo_class",
    [
        ("uuid:Socket-1_0-SERIALNUMBER", discovery.Switch),
        ("uuid:Lightswitch-1_0-SERIALNUMBER", discovery.LightSwitchLongPress),
        ("uuid:Lightswitch-2_0-SERIALNUMBER", discovery.LightSwitchLongPress),
        ("uuid:Lightswitch-3_0-SERIALNUMBER", discovery.LightSwitchLongPress),
        ("uuid:Lightswitch-9_0-SERIALNUMBER", discovery.LightSwitch),
        ("uuid:Dimmer-1_0-SERIALNUMBER", discovery.DimmerLongPress),
        ("uuid:Dimmer-2_0-SERIALNUMBER", discovery.DimmerV2),
        ("uuid:Dimmer-9_0-SERIALNUMBER", discovery.Dimmer),
        ("uuid:Insight-1_0-SERIALNUMBER", discovery.Insight),
        ("uuid:Sensor-1_0-SERIALNUMBER", discovery.Motion),
        ("uuid:Maker-1_0-SERIALNUMBER", discovery.Maker),
        ("uuid:Bridge-1_0-SERIALNUMBER", discovery.Bridge),
        ("uuid:CoffeeMaker-1_0-SERIALNUMBER", discovery.CoffeeMaker),
        ("uuid:Crockpot-1_0-SERIALNUMBER", discovery.CrockPot),
        ("uuid:Humidifier-1_0-SERIALNUMBER", discovery.Humidifier),
        ("uuid:OutdoorPlug-1_0-SERIALNUMBER", discovery.OutdoorPlug),
    ],
)
def test_discover_devices(udn, wemo_class):
    mock_entry = mock.create_autospec(ssdp.UPNPEntry)
    mock_entry.udn = udn
    mock_device = mock.create_autospec(wemo_class)

    with mock.patch("pywemo.discovery.ssdp") as mock_ssdp, mock.patch(
        f"pywemo.discovery.{wemo_class.__name__}", return_value=mock_device
    ):
        mock_ssdp.scan.return_value = [mock_entry]
        devices = discovery.discover_devices()

    assert devices == [mock_device]


def test_discover_devices_empty():
    mock_entry = mock.create_autospec(ssdp.UPNPEntry)
    mock_entry.udn = "no matches"

    with mock.patch("pywemo.discovery.ssdp") as mock_ssdp:
        mock_ssdp.scan.return_value = [mock_entry]
        devices = discovery.discover_devices()

    assert devices == []


def test_device_from_description(vcr):
    with vcr.use_cassette('WeMo_US_2.00.2769.PVT.yaml'):
        switch = discovery.device_from_description(
            "http://192.168.1.100:49153/setup.xml"
        )
    assert isinstance(switch, discovery.Switch)


def test_device_from_description_returns_none():
    with mock.patch("requests.get") as mock_get:
        mock_get.side_effect = requests.HTTPError
        assert (
            discovery.device_from_description("http://127.0.0.1/setup.xml")
            is None
        )

    with mock.patch("requests.get"), mock.patch(
        "pywemo.discovery.DeviceDescription"
    ) as mock_description:
        mock_description.from_xml.side_effect = exceptions.InvalidSchemaError
        assert (
            discovery.device_from_description("http://127.0.0.1/setup.xml")
            is None
        )


def test_device_from_uuid_and_location_returns_none():
    assert discovery.device_from_uuid_and_location("", "") is None
    assert (
        discovery.device_from_uuid_and_location(
            "", "http://127.0.0.1/setup.xml"
        )
        is None
    )
    assert (
        discovery.device_from_uuid_and_location(
            "uuid:Socket-1_0-SERIALNUMBER", ""
        )
        is None
    )

    with mock.patch(
        "pywemo.discovery.Switch", side_effect=exceptions.HTTPException
    ):
        assert (
            discovery.device_from_uuid_and_location(
                "uuid:Socket-1_0-SERIALNUMBER", "http://127.0.0.1/setup.xml"
            )
            is None
        )

    with mock.patch(
        "pywemo.discovery.Switch", side_effect=exceptions.InvalidSchemaError
    ):
        assert (
            discovery.device_from_uuid_and_location(
                "uuid:Socket-1_0-SERIALNUMBER", "http://127.0.0.1/setup.xml"
            )
            is None
        )

    with mock.patch(
        "pywemo.discovery.UnsupportedDevice",
        side_effect=exceptions.HTTPException,
    ):
        assert (
            discovery.device_from_uuid_and_location(
                "uuid:Unsupported-1_0-SERIALNUMBER",
                "http://127.0.0.1/setup.xml",
                debug=True,
            )
            is None
        )


def test_device_from_uuid_and_location_returns_unsupported():
    unsupported = mock.create_autospec(discovery.UnsupportedDevice)
    with mock.patch(
        "pywemo.discovery.UnsupportedDevice", return_value=unsupported
    ):
        assert (
            discovery.device_from_uuid_and_location(
                "uuid:Unsupported-1_0-SERIALNUMBER",
                "http://127.0.0.1/setup.xml",
                debug=True,
            )
            == unsupported
        )


def test_call_once_per_uuid():
    call_count = 0

    def increment_call_count():
        nonlocal call_count
        call_count += 1

    def decrement_call_count():
        nonlocal call_count
        call_count -= 1

    for uuid in ("a_uuid", "b_uuid"):
        discovery._call_once_per_uuid(uuid, increment_call_count)
        assert call_count == 1

        discovery._call_once_per_uuid(uuid, decrement_call_count)
        assert call_count == 0

        discovery._call_once_per_uuid(uuid, increment_call_count)
        assert call_count == 0

        discovery._call_once_per_uuid(uuid, decrement_call_count)
        assert call_count == 0
