"""Integration tests for the WeMo CrockPot."""

from unittest.mock import patch

import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from pywemo.ouimeaux_device.crockpot import CrockPot, CrockPotMode


@pytest.fixture
def crockpot(vcr):
    with vcr.use_cassette("crockpot_setup.yaml"):
        return CrockPot("http://192.168.1.100:49153/setup.xml")


@pytest.mark.vcr()
def test_on(crockpot):
    crockpot.on()

    assert crockpot.mode == CrockPotMode.High
    assert crockpot.mode_string == "High"


@pytest.mark.vcr()
def test_off(crockpot):
    crockpot.off()

    assert crockpot.mode == CrockPotMode.Off
    assert crockpot.mode_string == "Turned Off"


@st.composite
def state_dict(draw):
    keys = st.one_of(
        st.sampled_from(["cookedTime", "mode", "time"]), st.text()
    )
    values = st.one_of(st.integers(), st.text())
    return {
        key: str(value)
        for key, value in draw(st.dictionaries(keys, values)).items()
    }


@given(state=state_dict())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
# Positive examples.
@example(state={"cookedTime": "0", "mode": "0", "time": "0"})
@example(state={"cookedTime": "1", "mode": "50", "time": "1"})
@example(state={"cookedTime": "2", "mode": "51", "time": "2"})
@example(state={"cookedTime": "3", "mode": "52", "time": "3"})
# Negative examples.
@example(state={"cookedTime": "'", "mode": "50", "time": "1"})
@example(state={"cookedTime": "1", "mode": "'", "time": "1"})
@example(state={"cookedTime": "1", "mode": "50", "time": "'"})
@example(state={"mode": "50", "time": "1"})
@example(state={"cookedTime": "1", "time": "1"})
@example(state={"cookedTime": "1", "mode": "50"})
def test_update_attributes(state, crockpot):
    crockpot._attributes = {}
    try:
        expected = (
            CrockPotMode(int(state["mode"])),
            int(state["time"]),
            int(state["cookedTime"]),
        )
    except (KeyError, ValueError):
        # State should only change if all values are well formed.
        expected = (
            crockpot.mode,
            crockpot.remaining_time,
            crockpot.cooked_time,
        )

    with patch.object(
        crockpot.basicevent, "GetCrockpotState", return_value=state
    ):
        crockpot.get_state(True)
        assert expected == (
            crockpot.mode,
            crockpot.remaining_time,
            crockpot.cooked_time,
        )

    # Test the subscription_update method with the same data.
    for key, value in state.items():
        if key == "BinaryState":
            continue  # Handled by CrockPot superclass. Not tested here.
        result = crockpot.subscription_update(key, value)

        subscription_update_valid = key in ("mode", "time", "cookedTime")
        try:
            _ = int(value)
        except ValueError:
            subscription_update_valid = False

        assert result is subscription_update_valid
