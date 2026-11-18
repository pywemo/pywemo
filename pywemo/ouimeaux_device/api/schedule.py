"""Methods to switch a device on or off at set times.

The device runs these schedules from its rules database, without the cloud.
The rows match what the Wemo Android app (1.30.2) writes for a schedule; the
device ignores rules that use other values. Schedules use the local time of
the device, so call sync_time first, and again when the UTC offset changes.
"""

from __future__ import annotations

import time as _time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, time, tzinfo
from enum import Enum, IntEnum
from typing import TYPE_CHECKING, no_type_check

from .rules_db import RuleDevicesRow, RulesDb, RulesRow, rules_db_from_device

if TYPE_CHECKING:
    from .. import Device

# RulesRow.Type values.
RULE_TYPE_SIMPLE_SWITCH = "Simple Switch"


class Weekday(IntEnum):
    """Day of the week (RuleDevicesRow.DayID)."""

    SUNDAY = 1
    MONDAY = 2
    TUESDAY = 3
    WEDNESDAY = 4
    THURSDAY = 5
    FRIDAY = 6
    SATURDAY = 7


EVERY_DAY = frozenset(Weekday)
WEEKDAYS = frozenset(
    {
        Weekday.MONDAY,
        Weekday.TUESDAY,
        Weekday.WEDNESDAY,
        Weekday.THURSDAY,
        Weekday.FRIDAY,
    }
)


class ScheduleAction(Enum):
    """What the device does at the scheduled time."""

    ON = 1.0
    OFF = 0.0


@dataclass(frozen=True)
class SwitchSchedule:
    """A scheduled on or off action, as stored on the device."""

    name: str
    at: time
    action: ScheduleAction
    days: frozenset[Weekday]
    enabled: bool


@no_type_check
def add_switch_schedule_rule(
    rules_db: RulesDb,
    device_udn: str,
    name: str,
    at: time,
    action: ScheduleAction,
    *,
    days: Iterable[Weekday] = EVERY_DAY,
) -> RulesRow:
    """Add a rule that switches the device on or off at a local time."""
    rule = RulesRow(
        Name=name,
        Type=RULE_TYPE_SIMPLE_SWITCH,
        RuleOrder=2,
        StartDate="12201983",
        EndDate="12201983",
        State="1",
        Sync="NOSYNC",
    )
    rules_db.add_rule(rule)
    for day in sorted(set(days)):
        rules_db.add_rule_devices(
            RuleDevicesRow(
                RuleID=rule.RuleID,  # pylint: disable=no-member
                DeviceID=device_udn,
                GroupID=0,
                DayID=int(day),
                StartTime=at.hour * 3600 + at.minute * 60 + at.second,
                RuleDuration=0,
                StartAction=action.value,
                EndAction=action.value,
                SensorDuration=2,
                Type=-1,
                Value=-1,
                Level=-1,
                ZBCapabilityStart="",
                ZBCapabilityEnd="",
                OnModeOffset=0,
                OffModeOffset=0,
                CountdownTime=-1,
                EndTime=-1,
            )
        )
    return rule


@no_type_check
def switch_schedules(rules_db: RulesDb) -> list[SwitchSchedule]:
    """Return the Simple Switch schedules in the rules database."""
    rows = {}
    for rule, device in rules_db.rules_for_device(
        rule_type=RULE_TYPE_SIMPLE_SWITCH
    ):
        rows.setdefault(rule.RuleID, (rule, []))[1].append(device)
    result = []
    for rule, devices in rows.values():
        seconds = devices[0].StartTime
        result.append(
            SwitchSchedule(
                name=rule.Name,
                at=time(seconds // 3600, seconds % 3600 // 60, seconds % 60),
                action=ScheduleAction(devices[0].StartAction),
                days=frozenset(Weekday(d.DayID) for d in devices),
                enabled=rule.State == "1",
            )
        )
    return result


@no_type_check
def remove_switch_schedule_rules(rules_db: RulesDb, name: str) -> int:
    """Remove the Simple Switch rules with this name; return how many."""
    rules = {}
    for rule, device in rules_db.rules_for_device(
        rule_type=RULE_TYPE_SIMPLE_SWITCH
    ):
        if rule.Name == name:
            rules_db.remove_rule_devices(device)
            rules[rule.RuleID] = rule
    for rule in rules.values():
        rules_db.remove_rule(rule)
    return len(rules)


@no_type_check
def add_switch_schedule(
    device: Device,
    name: str,
    at: time,
    action: ScheduleAction,
    *,
    days: Iterable[Weekday] = EVERY_DAY,
) -> None:
    """Make the device switch itself on or off at a local time."""
    with rules_db_from_device(device) as rules_db:
        add_switch_schedule_rule(
            rules_db, device.udn, name, at, action, days=days
        )


@no_type_check
def list_switch_schedules(device: Device) -> list[SwitchSchedule]:
    """Return the on/off schedules stored on the device."""
    with rules_db_from_device(device) as rules_db:
        return switch_schedules(rules_db)


@no_type_check
def remove_switch_schedule(device: Device, name: str) -> int:
    """Remove the schedules with this name; return how many were removed."""
    with rules_db_from_device(device) as rules_db:
        return remove_switch_schedule_rules(rules_db, name)


def time_sync_args(
    tz: tzinfo | None = None, now: float | None = None
) -> dict[str, str]:
    """TimeSync arguments in the format the Wemo app sends.

    TimeZone is the current UTC offset in hours (daylight saving time
    included, ".5" for half-hour zones), dst is "1" while daylight saving
    time is in effect and DstSupported is "1" if the zone uses it.

    tz defaults to the system time zone; now is a Unix timestamp.
    """
    if now is None:
        now = _time.time()
    if tz is None:
        local = _time.localtime(now)
        in_dst = local.tm_isdst > 0
        offset_s = local.tm_gmtoff
        supported = _time.daylight != 0
    else:
        moment = datetime.fromtimestamp(now, tz)
        in_dst = bool(moment.dst())
        offset = moment.utcoffset()
        offset_s = int(offset.total_seconds()) if offset else 0
        supported = any(
            datetime(moment.year, month, 1, tzinfo=tz).dst()
            for month in (1, 7)
        )
    minutes = offset_s // 60
    zone = str(int(minutes / 60))
    if abs(minutes) % 60 == 30:
        zone += ".5"
    return {
        "UTC": str(int(now)),
        "TimeZone": zone,
        "dst": "1" if in_dst else "0",
        "DstSupported": "1" if supported else "0",
    }


def sync_time(device: Device, tz: tzinfo | None = None) -> bool:
    """Set the device clock and time zone; True if the device changed.

    The device answers "failure" when the values match what it already has,
    so False is not an error.
    """
    response = device.timesync.TimeSync(**time_sync_args(tz))
    return response.get("status") == "success"
