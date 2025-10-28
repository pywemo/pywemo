"""Integration tests for WeMo Switch devices."""

import pytest

from pywemo import Switch


class Base:
    """Tests that run for each Switch model."""

    @pytest.mark.vcr
    def test_turn_on(self, switch):
        switch.on()
        assert switch.get_state(force_update=True) == 1

    @pytest.mark.vcr
    def test_turn_off(self, switch):
        switch.off()
        assert switch.get_state(force_update=True) == 0


class Test_F7C027(Base):
    """Tests for the WeMo F7C027 model switch."""

    @pytest.fixture
    def switch(self, vcr):
        with vcr.use_cassette("WeMo_US_2.00.2769.PVT.yaml"):
            return Switch("http://192.168.1.100:49153/setup.xml")

    @pytest.mark.vcr
    def test_config_any(self, switch):
        assert switch._config_any == {
            "binaryState": "0",
            "firmwareVersion": "WeMo_US_2.00.2769.PVT",
            "iconVersion": "0|49153",
        }


class Test_F7C063(Base):
    """Tests for the WeMo F7C063 model switch."""

    @pytest.fixture
    def switch(self, vcr):
        with vcr.use_cassette("WeMo_WW_2.00.11420.PVT-OWRT-SNSV2.yaml"):
            return Switch("http://192.168.1.100:49153/setup.xml")

    @pytest.mark.vcr
    def test_config_any(self, switch):
        assert switch._config_any == {
            "binaryState": "0",
            "firmwareVersion": "WeMo_WW_2.00.11420.PVT-OWRT-SNSV2",
            "hkSetupCode": "012-34-567",
            "hwVersion": "v3",
            "iconVersion": "2|49153",
            "new_algo": "1",
        }


class Test_WSP080(Base):
    """Tests for the WeMo WSP080 model switch."""

    @pytest.fixture
    def switch(self, vcr):
        with vcr.use_cassette("WEMO_WW_4.00.20101902.PVT-RTOS-SNSV4.yaml"):
            return Switch("http://192.168.1.100:49153/setup.xml")

    @pytest.mark.vcr
    def test_config_any(self, switch):
        assert switch._config_any == {
            "binaryState": "0",
            "firmwareVersion": "WEMO_WW_4.00.20101902.PVT-RTOS-SNSV4",
            "hkSetupCode": "012-34-567",
            "hwVersion": "v4",
            "iconVersion": "1|49152",
            "new_algo": "1",
            "rtos": "1",
        }
