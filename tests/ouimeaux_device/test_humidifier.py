"""Integration tests for the WeMo Humidifier."""

import pytest

from pywemo.ouimeaux_device.humidifier import (
    DesiredHumidity,
    FanMode,
    Humidifier,
    WaterLevel,
)


@pytest.fixture
def humidifier(vcr):
    with vcr.use_cassette("WeMo_WW_2.00.11423.PVT-OWRT-Smart.yaml"):
        return Humidifier("http://192.168.1.100:49153/setup.xml")


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

    with pytest.raises(ValueError):
        humidifier.set_fan_mode_and_humidity(fan_mode=99)

    with pytest.raises(ValueError):
        humidifier.set_fan_mode_and_humidity(desired_humidity=99)


@pytest.mark.vcr()
def test_reset_filter_life(humidifier):
    assert humidifier.filter_life_percent == pytest.approx(59.62)

    humidifier.reset_filter_life()

    assert humidifier.filter_life_percent == pytest.approx(100.0)


def test_filter_expired(humidifier):
    assert humidifier.filter_expired is False


def test_current_humidity_percent(humidifier):
    assert humidifier.current_humidity_percent == pytest.approx(42.0)


def test_water_level(humidifier):
    assert humidifier.water_level == WaterLevel.Good
    assert humidifier.water_level_string == "Good"
