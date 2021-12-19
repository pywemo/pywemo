"""Integration tests for the Insight class."""

import datetime
import threading

import pytest

from pywemo import Insight, StandbyState
from pywemo.subscribe import EVENT_TYPE_BINARY_STATE, EVENT_TYPE_INSIGHT_PARAMS


class Test_Insight:
    """Integration tests for the Insight class."""

    @pytest.fixture
    def insight(self, vcr):
        with vcr.use_cassette('WeMo_WW_2.00.11408.PVT-OWRT-Insight.yaml'):
            return Insight('http://192.168.1.100:49153/setup.xml')

    @pytest.mark.vcr()
    def test_turn_on(self, insight):
        """Turn on the insight switch."""
        insight.on()
        assert insight.get_state(force_update=True) == 8

    @pytest.mark.vcr()
    def test_turn_off(self, insight):
        """Turn off the insight switch."""
        insight.off()
        assert insight.get_state(force_update=True) == 0

    @pytest.mark.vcr()
    def test_insight_params(self, insight):
        insight.update_insight_params()
        assert insight.today_kwh == pytest.approx(0.0194118)
        assert insight.total_kwh == pytest.approx(1.6638418)
        assert insight.current_power == 0
        assert insight.current_power_watts == 0.0
        assert insight.wifi_power == 8
        assert insight.threshold_power == 8000
        assert insight.threshold_power_watts == pytest.approx(8.0)
        assert insight.today_on_time == 300
        assert insight.on_for == 231
        assert insight.total_on_time == 183183
        assert insight.last_change.astimezone(datetime.timezone.utc) == (
            datetime.datetime(
                2021, 1, 25, 0, 2, 4, tzinfo=datetime.timezone.utc
            )
        )
        assert insight.today_on_time == 300
        assert insight.get_standby_state == StandbyState.OFF

    @pytest.mark.vcr()
    def test_subscribe(self, insight, subscription_registry):
        subscription_registry.register(insight)

        # Wait for registry to be ready to make sure the Insight device has
        # been registered.
        ready = threading.Event()
        subscription_registry._sched.enter(0.1, 0, ready.set)
        ready.wait()

        # Subscribe to all events.
        subscription_registry.on(
            insight, None, lambda a, b, c: insight.subscription_update(b, c)
        )

        subscription_registry.event(
            insight,
            EVENT_TYPE_BINARY_STATE,
            '1',
        )
        assert insight.get_state() == 1

        subscription_registry.event(
            insight,
            EVENT_TYPE_INSIGHT_PARAMS,
            '8|1611105078|2607|0|12416|1209600|328|500|457600|69632638|9500',
        )
        assert insight.today_kwh == pytest.approx(0.0076266668)
        assert insight.total_kwh == pytest.approx(1.1605439898)
        assert insight.current_power == 500
        assert insight.current_power_watts == pytest.approx(0.5)
        assert insight.wifi_power == 328
        assert insight.threshold_power == 9500
        assert insight.threshold_power_watts == pytest.approx(9.5)
        assert insight.today_on_time == 0
        assert insight.on_for == 2607
        assert insight.total_on_time == 12416
        assert insight.last_change.astimezone(datetime.timezone.utc) == (
            datetime.datetime(
                2021, 1, 20, 1, 11, 18, tzinfo=datetime.timezone.utc
            )
        )
        assert insight.today_on_time == 0
        assert insight.get_standby_state == StandbyState.STANDBY

        subscription_registry.unregister(insight)

    def test_subscription_update(self, insight):
        assert insight.subscription_update("BinaryState", "8") is True
        assert insight.subscription_update("BinaryState", "1") is True
        assert insight.subscription_update("BinaryState", "0") is False
        params = (
            "8|1611105078|2607|0|12416|1209600|328|500|457600|69632638|9500"
        )
        assert insight.subscription_update("InsightParams", params) is True
        assert insight.subscription_update("UnknownParam", "1") is False
