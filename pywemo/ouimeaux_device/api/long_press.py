"""Methods to make changes to the long press rules for a device.

Wemo devices store a database of rules that configure actions for the device. A
long press rule is activated when the button on the device is pressed for 2
seconds. A person can press the button for 2 seconds and, based on the rules
configured for the device, it will turn on/off/toggle other Wemo devices on the
network. The methods in this mixin allow editing of the devices that are
controlled by a long press.
"""
import logging
from enum import Enum

from .rules_db import RuleDevicesRow, RulesDb, RulesRow

LOG = logging.getLogger(__name__)

# RulesRow.Type values.
RULE_TYPE_LONG_PRESS = "Long Press"

VIRTUAL_DEVICE_UDN = "uuid:Socket-1_0-PyWemoVirtualDevice"


class ActionType(Enum):
    """Action to perform when a long press rule is triggered."""

    TOGGLE = 2.0
    ON = 1.0
    OFF = 0.0


def ensure_long_press_rule_exists(
    rules_db: RulesDb, device_name: str, device_udn: str
) -> RulesRow:
    """Ensure that a long press rule exists and is enabled for the device.

    Returns the long press rule.
    """
    current_rules = rules_db.rules_for_device()
    for (rule, _) in current_rules:
        if rule.State != "1":
            LOG.info("Enabling long press rule for device %s", device_name)
            rule.State = "1"
            rule.update_db(rules_db.cursor())
        return rule

    LOG.info("Adding long press rule for device %s", device_name)
    current_rules = rules_db.rules_for_device()
    max_order = max(
        rules_db.rules.values(), key=lambda r: r.RuleOrder, default=-1
    )
    new_rule = RulesRow(
        Name=f"{device_name} Long Press Rule",
        Type=RULE_TYPE_LONG_PRESS,
        RuleOrder=max_order + 1,
        StartDate="12201982",
        EndDate="07301982",
        State="1",
        Sync="NOSYNC",
    )
    rules_db.add_rule(new_rule)
    rules_db.add_rule_devices(
        RuleDevicesRow(
            RuleID=new_rule.RuleID,  # pylint: disable=no-member
            DeviceID=device_udn,
            GroupID=0,
            DayID=-1,
            StartTime=60,
            RuleDuration=86340,
            StartAction=ActionType.TOGGLE.value,
            EndAction=-1.0,
            SensorDuration=-1,
            Type=-1,
            Value=-1,
            Level=-1,
            ZBCapabilityStart="",
            ZBCapabilityEnd="",
            OnModeOffset=-1,
            OffModeOffset=-1,
            CountdownTime=-1,
            EndTime=86400,
        )
    )
    return new_rule
