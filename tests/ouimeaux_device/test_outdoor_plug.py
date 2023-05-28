"""Integration tests for the OutdoorPlug class."""

import pytest

from pywemo.discovery import device_from_uuid_and_location


class Base:
    """Tests that run for each OutdoorPlug model."""

    @pytest.mark.vcr()
    def test_turn_on(self, outdoor_plug):
        outdoor_plug.on()
        assert outdoor_plug.get_state(force_update=True) == 1

    @pytest.mark.vcr()
    def test_turn_off(self, outdoor_plug):
        outdoor_plug.off()
        assert outdoor_plug.get_state(force_update=True) == 0


class Test_WSP090(Base):
    """Tests for the WeMo WSP090 OutdoorPlug."""

    @pytest.fixture
    def outdoor_plug(self, vcr):
        with vcr.use_cassette("WEMO_WW_1.00.20081401.PVT-RTOS-OutdoorV1"):
            return device_from_uuid_and_location(
                "uuid:OutdoorPlug-1_0-SERIALNUMBER",
                "http://192.168.1.100:49153/setup.xml",
            )
