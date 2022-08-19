"""Integration tests for the WeMo CrockPot."""

import pytest

from pywemo.ouimeaux_device.crockpot import CrockPot, CrockPotMode


@pytest.fixture
def crockpot(vcr):
    with vcr.use_cassette("crockpot_setup.yaml"):
        return CrockPot("http://192.168.1.100:49153/setup.xml")


@pytest.mark.vcr()
def test_on(crockpot):
    crockpot.on()

    assert crockpot.mode == CrockPotMode.High


@pytest.mark.vcr()
def test_off(crockpot):
    crockpot.off()

    assert crockpot.mode == CrockPotMode.Off
