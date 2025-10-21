"""Tests for working with the rules database."""

import base64
import os
import sqlite3
import tempfile
from unittest.mock import Mock, create_autospec, patch

import pytest
import urllib3

from pywemo.exceptions import HTTPException, RulesDbQueryError
from pywemo.ouimeaux_device.api import rules_db
from pywemo.ouimeaux_device.api.service import REQUESTS_TIMEOUT, Session

MOCK_NAME = "WemoDeviceName"
MOCK_UDN = "WemoDeviceUDN"
MOCK_TARGET_UDN = "WemoTargetUDN"
MOCK_RULE_TYPE = "RuleType"


@pytest.fixture()
def temp_file_name():
    with tempfile.TemporaryDirectory(prefix="wemorules_") as temp_dir:
        yield os.path.join(temp_dir, "rules.db")


@pytest.fixture()
def sqldb(temp_file_name):
    rules_db._create_empty_db(temp_file_name)
    try:
        conn = sqlite3.connect(temp_file_name)
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


def test_create_empty_db(sqldb):
    statements = set(
        line for line in sqldb.iterdump() if line.startswith("CREATE TABLE")
    )
    assert statements == set(  # noqa: E501
        [
            # https://github.com/pywemo/pywemo/issues/61#issuecomment-748693894
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


def test_pack_unpack_db(temp_file_name, sqldb):
    orig_statements = set(
        line for line in sqldb.iterdump() if line.startswith("CREATE TABLE")
    )
    sqldb.close()
    packed = rules_db._pack_db(temp_file_name, "inner.db")
    inner_name = rules_db._unpack_db(base64.b64decode(packed), temp_file_name)

    assert inner_name == "inner.db"

    conn = sqlite3.connect(temp_file_name)
    try:
        unpacked_statements = set(
            line for line in conn.iterdump() if line.startswith("CREATE TABLE")
        )
    finally:
        conn.close()

    assert orig_statements == unpacked_statements


def test_auto_primary_key(sqldb):
    """Ensure the primary key for a row is updated when it is added to the db."""
    cursor = sqldb.cursor()
    row1 = rules_db.TargetDevicesRow(RuleID=12)
    row2 = rules_db.TargetDevicesRow(RuleID=34)
    row1.update_db(cursor)
    row2.update_db(cursor)

    assert row1.TargetDevicesPK + 1 == row2.TargetDevicesPK


def test_add_remove(sqldb):
    db = rules_db.RulesDb(sqldb, MOCK_UDN, MOCK_NAME)

    # Rules
    assert len(db._rules) == 0
    rule = db.add_rule(
        rules_db.RulesRow(
            RuleID=501,
            Name="Long Press Rule",
            Type=MOCK_RULE_TYPE,
            State=1,
        )
    )
    assert len(db._rules) == 1
    db.remove_rule(rule)
    assert len(db._rules) == 0

    # RuleDevices
    assert len(db._rule_devices) == 0
    device = db.add_rule_devices(
        rules_db.RuleDevicesRow(RuleDevicePK=1, RuleID=501, DeviceID=MOCK_UDN)
    )
    assert len(db._rule_devices) == 1
    db.remove_rule_devices(device)
    assert len(db._rule_devices) == 0

    # TargetDevices
    assert len(db._target_devices) == 0
    target = db.add_target_devices(
        rules_db.TargetDevicesRow(RuleID=501, DeviceID=MOCK_TARGET_UDN)
    )
    assert len(db._target_devices) == 1
    db.remove_target_devices(target)
    assert len(db._target_devices) == 0


def test_clear_all(sqldb):
    db = rules_db.RulesDb(sqldb, MOCK_UDN, MOCK_NAME)
    rule = db.add_rule(
        rules_db.RulesRow(
            RuleID=501,
            Name="Long Press Rule",
            Type=MOCK_RULE_TYPE,
            State=1,
        )
    )
    assert len(db._rules) == 1

    # RuleDevices
    assert len(db._rule_devices) == 0
    device = db.add_rule_devices(
        rules_db.RuleDevicesRow(RuleDevicePK=1, RuleID=501, DeviceID=MOCK_UDN)
    )
    assert len(db._rule_devices) == 1

    # TargetDevices
    assert len(db._target_devices) == 0
    target = db.add_target_devices(
        rules_db.TargetDevicesRow(RuleID=501, DeviceID=MOCK_TARGET_UDN)
    )
    assert len(db._target_devices) == 1

    db.clear_all()
    assert len(db._rules) == 0
    assert len(db._rule_devices) == 0
    assert len(db._target_devices) == 0


def test_update_if_modified_field_changed(sqldb):
    cursor = sqldb.cursor()
    rules_db.RulesRow(
        RuleID=501,
        Name="Long Press Rule",
        Type=MOCK_RULE_TYPE,
        State=1,
    ).update_db(cursor)

    rules_db.RuleDevicesRow(
        RuleDevicePK=1, RuleID=501, DeviceID=MOCK_UDN
    ).update_db(cursor)

    db = rules_db.RulesDb(sqldb, MOCK_UDN, MOCK_NAME)
    rule, device = db.rules_for_device()[0]
    assert db.update_if_modified() is False

    # Modifying an entry in the db should cause update_if_modified() to be True
    rule.State = 0
    assert db.update_if_modified() is True


def test_update_if_modified_new_entry(sqldb):
    rule = rules_db.RulesRow(RuleID=501)
    db = rules_db.RulesDb(sqldb, MOCK_UDN, MOCK_NAME)
    assert db.update_if_modified() is False

    # Adding a new entry in the db should cause update_if_modified() to be True
    db.add_target_device_to_rule(rule, MOCK_TARGET_UDN)
    assert db.update_if_modified() is True


def test_add_remove_target_device_to_rule(sqldb):
    rule = rules_db.RulesRow(RuleID=501)
    db = rules_db.RulesDb(sqldb, MOCK_UDN, MOCK_NAME)
    assert MOCK_TARGET_UDN not in db.get_target_devices_for_rule(rule)

    db.add_target_device_to_rule(rule, MOCK_TARGET_UDN)
    assert MOCK_TARGET_UDN in db.get_target_devices_for_rule(rule)

    db.remove_target_device_from_rule(rule, MOCK_TARGET_UDN)
    assert MOCK_TARGET_UDN not in db.get_target_devices_for_rule(rule)


def test_get_target_devices_for_rule(sqldb):
    cursor = sqldb.cursor()
    rule = rules_db.RulesRow(RuleID=501)
    rules_db.TargetDevicesRow(
        RuleID=rule.RuleID,
        DeviceID=MOCK_TARGET_UDN,
    ).update_db(cursor)
    db = rules_db.RulesDb(sqldb, MOCK_UDN, MOCK_NAME)

    assert db.get_target_devices_for_rule(rule) == frozenset([MOCK_TARGET_UDN])


def test_entry_with_no_primary_key(sqldb):
    # Create a RULEDEVICES table that allows NULLS for RuleDevicePK
    # From https://github.com/pywemo/pywemo/issues/276
    sqldb.cursor().execute("DROP TABLE RULEDEVICES")
    sqldb.cursor().execute(
        """CREATE TABLE RULEDEVICES (RuleDevicePK UNIQUE, RuleID INTEGER, DeviceID, GroupID, DayID INTEGER, StartTime,RuleDuration, StartAction INTEGER, EndAction INTEGER, SensorDuration,Type,Value,Level,ZBCapabilityStart TEXT DEFAULT "", ZBCapabilityEnd TEXT  DEFAULT "", OnModeOffset INTEGER  DEFAULT 0,OffModeOffset INTEGER DEFAULT 0,CountdownTime INTEGER DEFAULT 0,EndTime INTEGER DEFAULT 0, ProductName TEXT  DEFAULT "")"""
    )
    sqldb.cursor().execute(
        "INSERT INTO RULEDEVICES VALUES(NULL,22,'uuid:Lightswitch-1_0','0',1,'60','86280',0,0,'0','-1','-1','-1','-1','-1',0,0,1800,86340,'')"
    )
    # Should not cause an exception.
    db = rules_db.RulesDb(sqldb, MOCK_UDN, MOCK_NAME)
    # Should not be indexed either.
    assert len(db.rule_devices) == 0


def test_rules_db_from_device(temp_file_name, sqldb):
    rules_db.RulesRow(RuleID=501, Name="", Type="").update_db(sqldb.cursor())
    sqldb.commit()
    sqldb.close()
    zip_content = base64.b64decode(
        rules_db._pack_db(temp_file_name, "inner.db")
    )
    mock_response = create_autospec(urllib3.HTTPResponse, instance=True)
    mock_response.status = 200
    mock_response.data = zip_content
    store_rules = []

    class Device:
        name = MOCK_NAME
        udn = MOCK_UDN
        session = Session("http://localhost/")

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

    with patch(
        "urllib3.PoolManager.request", return_value=mock_response
    ) as mock_request:
        with rules_db.rules_db_from_device(Device) as db:
            mock_request.assert_called_once_with(
                method="GET", url="http://localhost/rules.db"
            )
            # Make a modification to trigger StoreRules.
            assert len(db._rules) == 1
            db._rules[501].State = 1

    assert len(store_rules) == 1
    assert store_rules[0]["ruleDbVersion"] == 2
    assert len(store_rules[0]["ruleDbBody"]) > 1000


def test_rules_db_from_device_404():
    mock_response = create_autospec(urllib3.HTTPResponse, instance=True)
    mock_response.status = 404

    class Device:
        name = MOCK_NAME
        udn = MOCK_UDN
        session = Session("http://localhost/")

        class rules:
            @staticmethod
            def FetchRules():
                return {
                    "ruleDbVersion": "1",
                    "ruleDbPath": "http://localhost/rules.db",
                }

    completed_with_no_exceptions = False
    with patch(
        "urllib3.PoolManager.request", return_value=mock_response
    ) as mock_request:
        with rules_db.rules_db_from_device(Device) as db:
            mock_request.assert_called_once_with(
                method="GET", url="http://localhost/rules.db"
            )
        assert len(db.rules) == 0
        completed_with_no_exceptions = True

    assert completed_with_no_exceptions


def test_rules_db_from_device_raises_http_exception():
    device = Mock()
    device.session = Session("http://localhost/")
    device.rules = Mock()
    device.rules.FetchRules.return_value = {
        "ruleDbVersion": 1,
        "ruleDbPath": "http://localhost/",
    }
    with patch(
        "urllib3.PoolManager.request", side_effect=urllib3.exceptions.HTTPError
    ):
        with pytest.raises(HTTPException):
            with rules_db.rules_db_from_device(device):
                pass


def test_sqlite_errors_raised():
    mock_response = create_autospec(urllib3.HTTPResponse, instance=True)
    mock_response.status = 404

    class Device:
        name = MOCK_NAME
        udn = MOCK_UDN
        session = Session("http://localhost/")

        class rules:
            @staticmethod
            def FetchRules():
                return {
                    "ruleDbVersion": "1",
                    "ruleDbPath": "http://localhost/rules.db",
                }

    with patch(
        "urllib3.PoolManager.request", return_value=mock_response
    ) as mock_request:
        with pytest.raises(RulesDbQueryError):
            with rules_db.rules_db_from_device(Device) as db:
                raise sqlite3.OperationalError("test")
