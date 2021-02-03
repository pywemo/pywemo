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

    @pytest.mark.vcr()
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

    @pytest.fixture
    def maker(self, vcr):
        with vcr.use_cassette('WeMo_WW_2.00.11423.PVT-OWRT-Maker.yaml'):
            return Maker('http://192.168.1.100:49153/setup.xml', '')
