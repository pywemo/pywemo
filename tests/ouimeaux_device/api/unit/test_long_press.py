import sqlite3
import tempfile

import pytest

from pywemo.ouimeaux_device.api import long_press, rules_db

MOCK_NAME = "WemoDeviceName"
MOCK_UDN = "WemoDeviceUDN"


@pytest.mark.parametrize(
    "test_input,expected",
    [
        # Test case 0: No long press existed in the database.
        # Expect that a new entry is generated.
        (
            [],
            [
                (
                    rules_db.RulesRow(
                        RuleID=1,
                        Name=f"{MOCK_NAME} Long Press Rule",
                        Type=long_press.RULE_TYPE_LONG_PRESS,
                        RuleOrder=0,
                        StartDate="12201982",
                        EndDate="07301982",
                        State=1,
                        Sync="NOSYNC",
                    ),
                    rules_db.RuleDevicesRow(
                        RuleDevicePK=1,
                        RuleID=1,
                        DeviceID=MOCK_UDN,
                        GroupID=0,
                        DayID=-1,
                        StartTime=60,
                        RuleDuration=86340,
                        StartAction=long_press.ActionType.TOGGLE.value,
                        EndAction=-1.0,
                        SensorDuration=-1,
                        Type=-1,
                        Value=-1,
                        Level=-1,
                        ZBCapabilityStart='',
                        ZBCapabilityEnd='',
                        OnModeOffset=-1,
                        OffModeOffset=-1,
                        CountdownTime=-1,
                        EndTime=86400,
                    ),
                ),
            ],
        ),
        # Test case 1: Long press rule exists, but has State=0.
        # Expect that the existing rules remain and all that is changed is
        # State=1.
        (
            [
                rules_db.RulesRow(
                    RuleID=501,
                    Name="Long Press Rule",
                    Type=long_press.RULE_TYPE_LONG_PRESS,
                    State=0,
                ),
                rules_db.RuleDevicesRow(
                    RuleDevicePK=1, RuleID=501, DeviceID=MOCK_UDN
                ),
            ],
            [
                (
                    rules_db.RulesRow(
                        RuleID=501,
                        Name="Long Press Rule",
                        Type=long_press.RULE_TYPE_LONG_PRESS,
                        State=1,
                    ),
                    rules_db.RuleDevicesRow(
                        RuleDevicePK=1, RuleID=501, DeviceID=MOCK_UDN
                    ),
                )
            ],
        ),
        # Test case 2: Long press rule exists and has State=1. Expect that
        # nothing is changed.
        (
            [
                rules_db.RulesRow(
                    RuleID=501,
                    Name="Long Press Rule",
                    Type=long_press.RULE_TYPE_LONG_PRESS,
                    State=1,
                ),
                rules_db.RuleDevicesRow(
                    RuleDevicePK=1, RuleID=501, DeviceID=MOCK_UDN
                ),
            ],
            [
                (
                    rules_db.RulesRow(
                        RuleID=501,
                        Name="Long Press Rule",
                        Type=long_press.RULE_TYPE_LONG_PRESS,
                        State=1,
                    ),
                    rules_db.RuleDevicesRow(
                        RuleDevicePK=1, RuleID=501, DeviceID=MOCK_UDN
                    ),
                )
            ],
        ),
    ],
)
def test_ensure_long_press_rule_exists(test_input, expected):
    with tempfile.NamedTemporaryFile(
        prefix="wemorules", suffix=".db"
    ) as temp_file:
        rules_db._create_empty_db(temp_file.name)
        try:
            conn = sqlite3.connect(temp_file.name)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            for row in test_input:
                row.update_db(cursor)

            db = rules_db.RulesDb(conn, MOCK_UDN, MOCK_NAME)
            long_press.ensure_long_press_rule_exists(db, MOCK_NAME, MOCK_UDN)

            assert (
                db.rules_for_device(rule_type=long_press.RULE_TYPE_LONG_PRESS)
                == expected
            )
        finally:
            conn.close()
