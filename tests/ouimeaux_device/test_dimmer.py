"""Tests for the Dimmer class."""
import pytest

from pywemo import Dimmer

from .api.unit import long_press_helpers


class Base:
    """Tests that run for each Dimmer model."""

    @pytest.mark.vcr()
    def test_turn_on(self, dimmer):
        """Turn on the dimmer."""
        dimmer.on()
        assert dimmer.get_state(force_update=True) == 1

    @pytest.mark.vcr()
    def test_turn_off(self, dimmer):
        """Turn off the dimmer."""
        dimmer.off()
        assert dimmer.get_state(force_update=True) == 0

    def test_subscription_update_brightness(self, dimmer):
        assert dimmer.subscription_update('Brightness', '23') == True
        assert dimmer.get_brightness() == 23

        assert dimmer.subscription_update('BinaryState', '1') == True
        assert dimmer.get_state() == 1


class Test_PVT_OWRT_Dimmer_v1(Base, long_press_helpers.TestLongPress):
    """Tests for the WeMo Dimmer, hardware version v1."""

    @pytest.fixture
    def dimmer(self, vcr):
        """The test fixture."""
        with vcr.use_cassette('WeMo_WW_2.00.11453.PVT-OWRT-Dimmer'):
            return Dimmer('http://192.168.1.100:49153/setup.xml', '')

    device = dimmer  # for TestLongPress
