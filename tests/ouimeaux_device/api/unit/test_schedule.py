"""Tests for on-device on/off schedules."""

import contextlib
import os
import sqlite3
import tempfile
from datetime import UTC, datetime, time
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from pywemo.ouimeaux_device.api import rules_db, schedule

UDN = "uuid:Socket-1_0-221702K11009ED"


@pytest.fixture
def rdb():
    with tempfile.TemporaryDirectory(prefix="wemorules_") as temp_dir:
        file_name = os.path.join(temp_dir, "rules.db")
        rules_db._create_empty_db(file_name)
        conn = sqlite3.connect(file_name)
        conn.row_factory = sqlite3.Row
        try:
            yield rules_db.RulesDb(conn, UDN, "Plug")
        finally:
            conn.close()


@pytest.fixture
def device(rdb):
    dev = MagicMock()
    dev.udn = UDN

    @contextlib.contextmanager
    def yield_rdb(*_):
        yield rdb

    with patch(
        "pywemo.ouimeaux_device.api.schedule.rules_db_from_device",
        side_effect=yield_rdb,
    ):
        yield dev


def test_rule_rows_match_the_wemo_app(rdb):
    """The rows must match the Wemo app, or the device ignores the rule."""
    schedule.add_switch_schedule_rule(
        rdb,
        UDN,
        "On",
        time(7, 45),
        schedule.ScheduleAction.ON,
        days=schedule.WEEKDAYS,
    )
    rdb.update_if_modified()

    rule = dict(rdb.cursor().execute("SELECT * FROM RULES").fetchone())
    assert rule == {
        "RuleID": 1,
        "Name": "On",
        "Type": "Simple Switch",
        "RuleOrder": 2,
        "StartDate": "12201983",
        "EndDate": "12201983",
        "State": "1",
        "Sync": "NOSYNC",
    }
    rows = rdb.cursor().execute("SELECT * FROM RULEDEVICES").fetchall()
    assert [row["DayID"] for row in rows] == [2, 3, 4, 5, 6]
    device = dict(rows[0])
    del device["RuleDevicePK"]
    assert device == {
        "RuleID": 1,
        "DeviceID": UDN,
        "GroupID": 0,
        "DayID": 2,
        "StartTime": 27900,
        "RuleDuration": 0,
        "StartAction": 1.0,
        "EndAction": 1.0,
        "SensorDuration": 2,
        "Type": -1,
        "Value": -1,
        "Level": -1,
        "ZBCapabilityStart": "",
        "ZBCapabilityEnd": "",
        "OnModeOffset": 0,
        "OffModeOffset": 0,
        "CountdownTime": -1,
        "EndTime": -1,
    }


def test_add_list_remove(device):
    schedule.add_switch_schedule(
        device,
        "Panel on",
        time(7, 45),
        schedule.ScheduleAction.ON,
        days=schedule.WEEKDAYS,
    )
    schedule.add_switch_schedule(
        device, "Panel off", time(17, 45), schedule.ScheduleAction.OFF
    )

    assert schedule.list_switch_schedules(device) == [
        schedule.SwitchSchedule(
            "Panel on",
            time(7, 45),
            schedule.ScheduleAction.ON,
            schedule.WEEKDAYS,
            True,
        ),
        schedule.SwitchSchedule(
            "Panel off",
            time(17, 45),
            schedule.ScheduleAction.OFF,
            schedule.EVERY_DAY,
            True,
        ),
    ]

    assert schedule.remove_switch_schedule(device, "Panel on") == 1
    assert schedule.remove_switch_schedule(device, "Missing") == 0
    assert [s.name for s in schedule.list_switch_schedules(device)] == [
        "Panel off"
    ]


def test_list_ignores_other_rule_types(rdb):
    rdb.add_rule(
        rules_db.RulesRow(
            Name="Long press", Type="Long Press", RuleOrder=0, State="1"
        )
    )
    assert schedule.switch_schedules(rdb) == []


@pytest.mark.parametrize(
    "zone, moment, expected",
    [
        # Winter and summer in the Netherlands.
        (
            "Europe/Amsterdam",
            datetime(2026, 1, 15, 12, tzinfo=UTC),
            ("1", "0", "1"),
        ),
        (
            "Europe/Amsterdam",
            datetime(2026, 7, 15, 12, tzinfo=UTC),
            ("2", "1", "1"),
        ),
        # No daylight saving time, half-hour offset.
        (
            "Asia/Kolkata",
            datetime(2026, 7, 15, 12, tzinfo=UTC),
            ("5.5", "0", "0"),
        ),
        # West of UTC.
        (
            "America/New_York",
            datetime(2026, 1, 15, 12, tzinfo=UTC),
            ("-5", "0", "1"),
        ),
        ("UTC", datetime(2026, 1, 15, 12, tzinfo=UTC), ("0", "0", "0")),
    ],
)
def test_time_sync_args(zone, moment, expected):
    now = moment.timestamp()
    args = schedule.time_sync_args(ZoneInfo(zone), now)
    assert args == {
        "UTC": str(int(now)),
        "TimeZone": expected[0],
        "dst": expected[1],
        "DstSupported": expected[2],
    }


@pytest.mark.parametrize(
    "status, changed", [("success", True), ("failure", False)]
)
def test_sync_time(status, changed):
    device = MagicMock()
    device.timesync.TimeSync.return_value = {"status": status}
    assert schedule.sync_time(device, ZoneInfo("Europe/Amsterdam")) is changed
    kwargs = device.timesync.TimeSync.call_args.kwargs
    assert set(kwargs) == {"UTC", "TimeZone", "dst", "DstSupported"}
