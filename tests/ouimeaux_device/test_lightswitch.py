"""Integration tests for the LightSwitch class."""

import pytest

from pywemo import LightSwitch

from .api.unit import long_press_helpers


class Base:
    """Tests that run for each LightSwitch model."""

    @pytest.mark.vcr()
    def test_turn_on(self, lightswitch):
        lightswitch.on()
        assert lightswitch.get_state(force_update=True) == 1

    @pytest.mark.vcr()
    def test_turn_off(self, lightswitch):
        lightswitch.off()
        assert lightswitch.get_state(force_update=True) == 0


class Test_PVT_OWRT_LS_v1(Base, long_press_helpers.TestLongPress):
    """Tests for the WeMo LightSwitch, hardware version v1."""

    @pytest.fixture
    def lightswitch(self, vcr):
        with vcr.use_cassette('WeMo_WW_2.00.11408.PVT-OWRT-LS'):
            return LightSwitch('http://192.168.1.100:49153/setup.xml', '')

    device = lightswitch  # for TestLongPress
