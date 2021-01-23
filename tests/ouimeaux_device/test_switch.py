"""Integration tests for WeMo Switch devices."""
import pytest

from pywemo import Switch


class Base:
    """Tests that run for each Switch model."""

    @pytest.mark.vcr()
    def test_turn_on(self, switch):
        """Turn on the switch."""
        switch.on()
        assert switch.get_state(force_update=True) == 1

    @pytest.mark.vcr()
    def test_turn_off(self, switch):
        """Turn off the switch."""
        switch.off()
        assert switch.get_state(force_update=True) == 0


class Test_F7C027(Base):
    """Tests for the WeMo F7C027 model switch."""

    @pytest.fixture
    def switch(self, vcr):
        """F7C027 test fixture."""
        with vcr.use_cassette('WeMo_US_2.00.2769.PVT.yaml'):
            return Switch('http://192.168.1.100:49153/setup.xml', '')


class Test_F7C063(Base):
    """Tests for the WeMo F7C063 model switch."""

    @pytest.fixture
    def switch(self, vcr):
        """F7C063 test fixture."""
        with vcr.use_cassette('WeMo_WW_2.00.11420.PVT-OWRT-SNSV2.yaml'):
            return Switch('http://192.168.1.100:49153/setup.xml', '')


class Test_WSP080(Base):
    """Tests for the WeMo WSP080 model switch."""

    @pytest.fixture
    def switch(self, vcr):
        """WSP080 test fixture."""
        with vcr.use_cassette('WEMO_WW_4.00.20101902.PVT-RTOS-SNSV4.yaml'):
            return Switch('http://192.168.1.100:49153/setup.xml', '')
