"""Integration tests for WeMo Switch devices."""

import unittest

import pytest

from pywemo import Maker


class Test_Maker:
    """Tests that run the Maker."""

    @pytest.mark.vcr()
    def test_turn_on(self, maker):
        maker.on()
        assert maker.get_state(force_update=True) == 1

    @pytest.mark.vcr()
    def test_turn_off(self, maker):
        maker.off()
        assert maker.get_state(force_update=True) == 0

    def test_maker_params(self, maker):
        expected_params = {
            'hassensor': 1,
            'sensorstate': 1,
            'switchmode': 1,
            'switchstate': 0,
        }
        unittest.TestCase().assertDictEqual(
            maker.maker_params, expected_params
        )
        assert maker.switch_state == 0
        assert maker.sensor_state == 1
        assert maker.switch_mode == 1
        assert maker.has_sensor == 1
        assert maker.get_state() == 0

    def test_maker_device_type(self, maker):
        assert maker.device_type == "Maker"
        assert repr(maker) == '<WeMo Maker "WeMo Device">'

    def test_maker_unexpected_subscription_type(self, maker):
        assert maker.subscription_update("", "") is False

    @pytest.mark.parametrize(
        "update,expected_params",
        [
            # Sensor/sensorstate
            (
                (
                    '<attribute><name>Sensor</name><value>0</value>'
                    '<prevalue>1</prevalue><ts>1627869840</ts></attribute>'
                ),
                {
                    'hassensor': 1,
                    'sensorstate': 0,
                    'switchmode': 1,
                    'switchstate': 0,
                },
            ),
            # Switch/switchstate
            (
                (
                    '<attribute><name>Switch</name><value>1</value>'
                    '<prevalue>1</prevalue><ts>1627869840</ts></attribute>'
                ),
                {
                    'hassensor': 1,
                    'sensorstate': 1,
                    'switchmode': 1,
                    'switchstate': 1,
                },
            ),
            # SwitchMode/switchmode
            (
                (
                    '<attribute><name>SwitchMode</name><value>0</value>'
                    '<prevalue>1</prevalue><ts>1627869840</ts></attribute>'
                ),
                {
                    'hassensor': 1,
                    'sensorstate': 1,
                    'switchmode': 0,
                    'switchstate': 0,
                },
            ),
            # SensorPresent/hassensor
            (
                (
                    '<attribute><name>SensorPresent</name><value>0</value>'
                    '<prevalue>1</prevalue><ts>1627869840</ts></attribute>'
                ),
                {
                    'hassensor': 0,
                    'sensorstate': 1,
                    'switchmode': 1,
                    'switchstate': 0,
                },
            ),
            # Invalid state value.
            (
                (
                    '<attribute><name>SensorPresent</name><value>ABC</value>'
                    '<prevalue>1</prevalue><ts>1627869840</ts></attribute>'
                ),
                {
                    'hassensor': 1,
                    'sensorstate': 1,
                    'switchmode': 1,
                    'switchstate': 0,
                },
            ),
            # Unexpected State name
            (
                (
                    '<attribute><name>Unexpected</name><value>ABC</value>'
                    '<prevalue>1</prevalue><ts>1627869840</ts></attribute>'
                ),
                {
                    'hassensor': 1,
                    'sensorstate': 1,
                    'switchmode': 1,
                    'switchstate': 0,
                },
            ),
        ],
    )
    def test_subscription_update(self, update, expected_params, maker):
        """Test that subscription updates happen as expected."""
        updated = maker.subscription_update('attributeList', update)
        assert updated is True
        unittest.TestCase().assertDictEqual(
            maker.maker_params, expected_params
        )

    @pytest.fixture
    def maker(self, vcr):
        with vcr.use_cassette('WeMo_WW_2.00.11423.PVT-OWRT-Maker.yaml'):
            return Maker('http://192.168.1.100:49153/setup.xml')
