"""Integration tests for the LightSwitch class."""

import pytest

from pywemo.discovery import device_from_uuid_and_location

from .api.unit import long_press_helpers


class Base:
    """Tests that run for each LightSwitch model."""

    @pytest.mark.vcr
    def test_turn_on(self, lightswitch):
        lightswitch.on()
        assert lightswitch.get_state(force_update=True) == 1

    @pytest.mark.vcr
    def test_turn_off(self, lightswitch):
        lightswitch.off()
        assert lightswitch.get_state(force_update=True) == 0


class Test_F7C030(Base, long_press_helpers.TestLongPress):
    """Tests for the WeMo F7C030 LightSwitch."""

    @pytest.fixture
    def lightswitch(self, vcr):
        with vcr.use_cassette("WeMo_WW_2.00.11408.PVT-OWRT-LS"):
            return device_from_uuid_and_location(
                "uuid:Lightswitch-1_0-SERIALNUMBER",
                "http://192.168.1.100:49153/setup.xml",
            )

    device = lightswitch  # for TestLongPress


class Test_WLS040(Base, long_press_helpers.TestLongPress):
    """Tests for the WeMo WLS040 LightSwitch."""

    @pytest.fixture
    def lightswitch(self, vcr):
        with vcr.use_cassette("WeMo_WW_2.00.11563.PVT-OWRT-LIGHTV2-WLS040"):
            return device_from_uuid_and_location(
                "uuid:Lightswitch-2_0-SERIALNUMBER",
                "http://192.168.1.100:49153/setup.xml",
            )

    device = lightswitch  # for TestLongPress


class Test_WLS0403(Base, long_press_helpers.TestLongPress):
    """Tests for the WeMo WLS0403 three-wey LightSwitch."""

    @pytest.fixture
    def lightswitch(self, vcr):
        with vcr.use_cassette("WeMo_WW_2.00.11563.PVT-OWRT-LIGHTV2-WLS0403"):
            return device_from_uuid_and_location(
                "uuid:Lightswitch-3_0-SERIALNUMBER",
                "http://192.168.1.100:49153/setup.xml",
            )

    device = lightswitch  # for TestLongPress


class Test_NoLongPress(Base):
    """Tests for the WeMo WeMo_WW_2.00.2263.PVT firmware."""

    @pytest.fixture
    def lightswitch(self, vcr):
        with vcr.use_cassette("WeMo_WW_2.00.2263.PVT"):
            return device_from_uuid_and_location(
                "uuid:Lightswitch-1_0-SERIALNUMBER",
                "http://192.168.1.100:49153/Lightsetup.xml",
            )
