"""Integration tests for the WeMo Humidifier."""

import pytest

from pywemo.ouimeaux_device.humidifier import (
    DesiredHumidity,
    FanMode,
    Humidifier,
)


@pytest.fixture
def humidifier(vcr):
    with vcr.use_cassette('WeMo_WW_2.00.11423.PVT-OWRT-Smart.yaml'):
        return Humidifier('http://192.168.1.100:49153/setup.xml')


@pytest.mark.vcr()
def test_on(humidifier):
    humidifier.on()

    assert humidifier.fan_mode == FanMode.Minimum
    assert humidifier.fan_mode_string == "Minimum"
    assert humidifier.get_state() == 1


@pytest.mark.vcr()
def test_off(humidifier):
    humidifier.off()

    assert humidifier.fan_mode == FanMode.Off
    assert humidifier.fan_mode_string == "Off"
    assert humidifier.get_state() == 0


@pytest.mark.vcr()
def test_desired_humidity(humidifier):
    humidifier.on()
    humidifier.set_humidity(DesiredHumidity.FiftyFivePercent)

    assert humidifier.desired_humidity == DesiredHumidity.FiftyFivePercent
    assert humidifier.desired_humidity_percent == "55"


@pytest.mark.vcr()
def test_set_fan_mode_and_humidity(humidifier):
    humidifier.set_fan_mode_and_humidity(
        FanMode.Medium, DesiredHumidity.FortyFivePercent
    )

    assert humidifier.fan_mode == FanMode.Medium
    assert humidifier.fan_mode_string == "Medium"

    assert humidifier.desired_humidity == DesiredHumidity.FortyFivePercent
    assert humidifier.desired_humidity_percent == "45"

    assert humidifier.get_state() == 1


@pytest.mark.vcr()
def test_reset_filter_life(humidifier):
    humidifier.reset_filter_life()

    assert humidifier.filter_life_percent == pytest.approx(100.0)
