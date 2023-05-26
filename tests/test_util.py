"""Tests for pywemo.util."""

from datetime import datetime, timedelta

import pytest

from pywemo import util


def test_interface_addresses():
    addresses = util.interface_addresses()

    for address in addresses:
        assert address != "127.0.0.1"
        assert ":" not in address  # No IPv6


@pytest.mark.parametrize(
    "test_input,expected",
    [
        (100, -50),
        (24, -80),
        (0, -90),
        (5000, -50),
        (-4.2, -90),
        (50, -70),
        (10, -86),
    ],
)
def test_signal_strength_to_dbm(test_input, expected):
    signal_strength = {"SignalStrength": f"{test_input}"}

    assert util.signal_strength_to_dbm(signal_strength) == expected
    assert (
        util.signal_strength_to_dbm(signal_strength["SignalStrength"])
        == expected
    )


def test_meta_info():
    meta_info = {
        "MetaInfo": "|".join(
            [
                "MAC_ADDRESS",
                "SERIAL_NUMBER",
                "Plugin Device",
                "WeMo_WW_2.00.11532.PVT-OWRT-Insight",
                "WeMo.Insight.684",
                "Insight",
            ]
        )
    }
    expected = util.MetaInfo(
        mac="MAC_ADDRESS",
        serial_number="SERIAL_NUMBER",
        device_sku="Plugin Device",
        firmware_version="WeMo_WW_2.00.11532.PVT-OWRT-Insight",
        access_point_ssid="WeMo.Insight.684",
        model_name="Insight",
    )

    assert util.MetaInfo.from_meta_info(meta_info) == expected
    assert util.MetaInfo.from_meta_info(meta_info["MetaInfo"]) == expected

    assert (
        util.MetaInfo.from_meta_info(meta_info["MetaInfo"] + "|extra")
        == expected
    )

    with pytest.raises(ValueError):
        util.MetaInfo.from_meta_info("")

    with pytest.raises(ValueError):
        util.MetaInfo.from_meta_info("\b")


def test_ext_meta_info():
    ext_meta_info = {
        "ExtMetaInfo": "1|0|1|0|1579:8:42|4|1640081818|123456|1|Insight"
    }
    expected = util.ExtMetaInfo(
        current_client_state=1,
        ice_running=0,
        nat_initialized=1,
        last_auth_value=0,
        uptime=timedelta(hours=1579, minutes=8, seconds=42),
        firmware_update_state=4,
        utc_time=datetime(
            year=2021, month=12, day=21, hour=10, minute=16, second=58
        ),
        home_id="123456",
        remote_access_enabled=True,
        model_name="Insight",
    )

    assert util.ExtMetaInfo.from_ext_meta_info(ext_meta_info) == expected
    assert (
        util.ExtMetaInfo.from_ext_meta_info(ext_meta_info["ExtMetaInfo"])
        == expected
    )

    assert (
        util.ExtMetaInfo.from_ext_meta_info(
            ext_meta_info["ExtMetaInfo"] + "|extra"
        )
        == expected
    )

    with pytest.raises(ValueError):
        util.ExtMetaInfo.from_ext_meta_info("")

    with pytest.raises(ValueError):
        util.ExtMetaInfo.from_ext_meta_info("\b")
