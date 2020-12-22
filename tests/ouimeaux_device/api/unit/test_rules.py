import base64
import sqlite3
import tempfile
from unittest.mock import create_autospec, patch

import pytest
import requests

from pywemo.ouimeaux_device.api import rules

MOCK_NAME = "WemoDeviceName"
MOCK_UDN = "WemoDeviceUDN"


@pytest.fixture()
def temp_file():
    with tempfile.NamedTemporaryFile(
        prefix="wemorules", suffix=".db"
    ) as temp_file:
        yield temp_file


@pytest.fixture()
def rules_db(temp_file):
    rules._create_empty_db(temp_file.name)
    try:
        conn = sqlite3.connect(temp_file.name)
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


def test_create_empty_db(rules_db):
    statements = set(
        line for line in rules_db.iterdump() if line.startswith('CREATE TABLE')
    )
    assert statements == set(
        [
            # https://github.com/pavoni/pywemo/issues/61#issuecomment-748693894
            "CREATE TABLE RULES(RuleID PRIMARY KEY, Name TEXT NOT NULL, Type TEXT NOT NULL, RuleOrder INTEGER, StartDate TEXT, EndDate TEXT, State TEXT, Sync INTEGER);",
            "CREATE TABLE RULEDEVICES(RuleDevicePK INTEGER PRIMARY KEY AUTOINCREMENT, RuleID INTEGER, DeviceID TEXT, GroupID INTEGER, DayID INTEGER, StartTime INTEGER, RuleDuration INTEGER, StartAction REAL, EndAction REAL, SensorDuration INTEGER, Type INTEGER, Value INTEGER, Level INTEGER, ZBCapabilityStart TEXT, ZBCapabilityEnd TEXT, OnModeOffset INTEGER, OffModeOffset INTEGER, CountdownTime INTEGER, EndTime INTEGER);",
            "CREATE TABLE DEVICECOMBINATION(DeviceCombinationPK INTEGER PRIMARY KEY AUTOINCREMENT, RuleID INTEGER, SensorID TEXT, SensorGroupID INTEGER, DeviceID TEXT, DeviceGroupID INTEGER);",
            "CREATE TABLE GROUPDEVICES(GroupDevicePK INTEGER PRIMARY KEY AUTOINCREMENT, GroupID INTEGER, DeviceID TEXT);",
            "CREATE TABLE LOCATIONINFO(LocationPk INTEGER PRIMARY KEY AUTOINCREMENT, cityName TEXT, countryName TEXT, latitude TEXT, longitude TEXT, countryCode TEXT, region TEXT);",
            "CREATE TABLE BLOCKEDRULES(Primarykey INTEGER PRIMARY KEY AUTOINCREMENT, ruleId TEXT);",
            "CREATE TABLE RULESNOTIFYMESSAGE(RuleID INTEGER PRIMARY KEY AUTOINCREMENT, NotifyRuleID INTEGER, Message TEXT, Frequency INTEGER);",
            "CREATE TABLE SENSORNOTIFICATION(SensorNotificationPK INTEGER PRIMARY KEY AUTOINCREMENT, RuleID INTEGER, NotifyRuleID INTEGER, NotificationMessage TEXT, NotificationDuration INTEGER);",
            "CREATE TABLE TARGETDEVICES(TargetDevicesPK INTEGER PRIMARY KEY AUTOINCREMENT, RuleID INTEGER, DeviceID TEXT, DeviceIndex INTEGER);",
        ]
    )


def test_pack_unpack_db(temp_file, rules_db):
    orig_statements = set(
        line for line in rules_db.iterdump() if line.startswith('CREATE TABLE')
    )
    packed = rules._pack_db(temp_file, "inner.db")
    inner_name = rules._unpack_db(base64.b64decode(packed), temp_file)

    assert inner_name == "inner.db"

    conn = sqlite3.connect(temp_file.name)
    try:
        unpacked_statements = set(
            line for line in conn.iterdump() if line.startswith('CREATE TABLE')
        )
    finally:
        conn.close()

    assert orig_statements == unpacked_statements


def test_auto_primary_key(rules_db):
    """Ensure the primary key for a row is updated when it is added to the db."""
    cursor = rules_db.cursor()
    row1 = rules.TargetDevicesRow(RuleID=12)
    row2 = rules.TargetDevicesRow(RuleID=34)
    row1.update_db(cursor)
    row2.update_db(cursor)

    assert row1.TargetDevicesPK + 1 == row2.TargetDevicesPK


@pytest.mark.parametrize(
    "test_input,expected",
    [
        # Test case 0: No long press existed in the database.
        # Expect that a new entry is generated.
        (
            [],
            [
                (
                    rules.RulesRow(
                        RuleID=1,
                        Name=f"{MOCK_NAME} Long Press Rule",
                        Type=rules.RULE_TYPE_LONG_PRESS,
                        RuleOrder=0,
                        StartDate="12201982",
                        EndDate="07301982",
                        State=1,
                        Sync="NOSYNC",
                    ),
                    rules.RuleDevicesRow(
                        RuleDevicePK=1,
                        RuleID=1,
                        DeviceID=MOCK_UDN,
                        GroupID=0,
                        DayID=-1,
                        StartTime=60,
                        RuleDuration=86340,
                        StartAction=2.0,
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
                rules.RulesRow(
                    RuleID=501,
                    Name="Long Press Rule",
                    Type=rules.RULE_TYPE_LONG_PRESS,
                    State=0,
                ),
                rules.RuleDevicesRow(
                    RuleDevicePK=1, RuleID=501, DeviceID=MOCK_UDN
                ),
            ],
            [
                (
                    rules.RulesRow(
                        RuleID=501,
                        Name="Long Press Rule",
                        Type=rules.RULE_TYPE_LONG_PRESS,
                        State=1,
                    ),
                    rules.RuleDevicesRow(
                        RuleDevicePK=1, RuleID=501, DeviceID=MOCK_UDN
                    ),
                )
            ],
        ),
        # Test case 2: Long press rule exists and has State=1. Expect that
        # nothing is changed.
        (
            [
                rules.RulesRow(
                    RuleID=501,
                    Name="Long Press Rule",
                    Type=rules.RULE_TYPE_LONG_PRESS,
                    State=1,
                ),
                rules.RuleDevicesRow(
                    RuleDevicePK=1, RuleID=501, DeviceID=MOCK_UDN
                ),
            ],
            [
                (
                    rules.RulesRow(
                        RuleID=501,
                        Name="Long Press Rule",
                        Type=rules.RULE_TYPE_LONG_PRESS,
                        State=1,
                    ),
                    rules.RuleDevicesRow(
                        RuleDevicePK=1, RuleID=501, DeviceID=MOCK_UDN
                    ),
                )
            ],
        ),
    ],
)
def test_ensure_long_press_rule_exists(rules_db, test_input, expected):
    cursor = rules_db.cursor()
    for row in test_input:
        row.update_db(cursor)

    db = rules.RulesDb(rules_db, MOCK_UDN, MOCK_NAME)
    db.ensure_long_press_rule_exists()

    assert (
        db.rules_for_device(rule_type=rules.RULE_TYPE_LONG_PRESS) == expected
    )


def test_add_remove(rules_db):
    rule = rules.RulesRow(
        RuleID=501,
        Name="Long Press Rule",
        Type=rules.RULE_TYPE_LONG_PRESS,
        State=1,
    )
    devices = rules.RuleDevicesRow(
        RuleDevicePK=1, RuleID=501, DeviceID=MOCK_UDN
    )
    target = rules.TargetDevicesRow

    db = rules.RulesDb(rules_db, MOCK_UDN, MOCK_NAME)

    # Rules
    assert len(db._rules) == 0
    rule = db.add_rule(
        rules.RulesRow(
            RuleID=501,
            Name="Long Press Rule",
            Type=rules.RULE_TYPE_LONG_PRESS,
            State=1,
        )
    )
    assert len(db._rules) == 1
    db.remove_rule(rule)
    assert len(db._rules) == 0

    # RuleDevices
    assert len(db._rule_devices) == 0
    device = db.add_rule_devices(
        rules.RuleDevicesRow(RuleDevicePK=1, RuleID=501, DeviceID=MOCK_UDN)
    )
    assert len(db._rule_devices) == 1
    db.remove_rule_devices(device)
    assert len(db._rule_devices) == 0

    # TargetDevices
    assert len(db._target_devices) == 0
    target = db.add_target_devices(
        rules.TargetDevicesRow(RuleID=501, DeviceID=rules.VIRTUAL_DEVICE_UDN)
    )
    assert len(db._target_devices) == 1
    db.remove_target_devices(target)
    assert len(db._target_devices) == 0


def test_update_if_modified_field_changed(rules_db):
    cursor = rules_db.cursor()
    rules.RulesRow(
        RuleID=501,
        Name="Long Press Rule",
        Type=rules.RULE_TYPE_LONG_PRESS,
        State=1,
    ).update_db(cursor)

    rules.RuleDevicesRow(
        RuleDevicePK=1, RuleID=501, DeviceID=MOCK_UDN
    ).update_db(cursor)

    db = rules.RulesDb(rules_db, MOCK_UDN, MOCK_NAME)
    rule, device = db.rules_for_device()[0]
    assert db.update_if_modified() is False

    # Modifying an entry in the db should cause update_if_modified() == True.
    rule.State = 0
    assert db.update_if_modified() is True


def test_update_if_modified_new_entry(rules_db):
    rule = rules.RulesRow(RuleID=501)
    db = rules.RulesDb(rules_db, MOCK_UDN, MOCK_NAME)
    assert db.update_if_modified() is False

    # Adding a new entry  in the db should cause update_if_modified() == True.
    db.add_target_device_to_rule(rule, rules.VIRTUAL_DEVICE_UDN)
    assert db.update_if_modified() is True


def test_add_remove_target_device_to_rule(rules_db):
    rule = rules.RulesRow(RuleID=501)
    db = rules.RulesDb(rules_db, MOCK_UDN, MOCK_NAME)
    assert rules.VIRTUAL_DEVICE_UDN not in db.get_target_devices_for_rule(rule)

    db.add_target_device_to_rule(rule, rules.VIRTUAL_DEVICE_UDN)
    assert rules.VIRTUAL_DEVICE_UDN in db.get_target_devices_for_rule(rule)

    db.remove_target_device_from_rule(rule, rules.VIRTUAL_DEVICE_UDN)
    assert rules.VIRTUAL_DEVICE_UDN not in db.get_target_devices_for_rule(rule)


def test_get_target_devices_for_rule(rules_db):
    cursor = rules_db.cursor()
    rule = rules.RulesRow(RuleID=501)
    rules.TargetDevicesRow(
        RuleID=rule.RuleID, DeviceID=rules.VIRTUAL_DEVICE_UDN
    ).update_db(cursor)
    db = rules.RulesDb(rules_db, MOCK_UDN, MOCK_NAME)

    assert db.get_target_devices_for_rule(rule) == frozenset(
        [rules.VIRTUAL_DEVICE_UDN]
    )


def test_rules_db_from_device(temp_file, rules_db):
    rules.RulesRow(RuleID=501, Name="", Type="").update_db(rules_db.cursor())
    rules_db.commit()
    rules_db.close()
    zip_content = base64.b64decode(rules._pack_db(temp_file, "inner.db"))
    mock_response = create_autospec(requests.Response, instance=True)
    mock_response.status_code = 200
    mock_response.content = zip_content
    store_rules = []

    class Device:
        name = MOCK_NAME
        udn = MOCK_UDN

        class rules:
            @staticmethod
            def FetchRules():
                return {
                    "ruleDbVersion": "1",
                    "ruleDbPath": "http://localhost/rules.db",
                }

            @staticmethod
            def StoreRules(**kwargs):
                store_rules.append(kwargs)

    with patch("requests.get", return_value=mock_response) as mock_get:
        with rules.rules_db_from_device(Device) as db:
            mock_get.assert_called_once_with("http://localhost/rules.db")
            # Make a modification to trigger StoreRules.
            assert len(db._rules) == 1
            db._rules[501].State = 1

    assert len(store_rules) == 1
    assert store_rules[0]["ruleDbVersion"] == 2
    assert len(store_rules[0]["ruleDbBody"]) > 1000
