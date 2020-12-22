"""Access and manipulate the on-device rules sqlite database."""

import base64
import contextlib
import io
import logging
import sqlite3
import tempfile
import zipfile
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Tuple

import requests

ACTION_TOGGLE = 2.0
ACTION_ON = 1.0
ACTION_OFF = 0.0

LOG = logging.getLogger(__name__)

RULE_TYPE_LONG_PRESS = "Long Press"

VIRTUAL_DEVICE_UDN = "uuid:Socket-1_0-PyWemoVirtualDevice"


class DatabaseRow:
    """Base class for sqlite Row schemas."""

    TABLE_NAME: str
    FIELDS: Dict[str, Callable[[Any], Any]]

    def __init__(self, **kwargs):
        """Initialize a row with the supplied values."""
        for key, value in kwargs.items():
            if key not in self.FIELDS:
                raise AttributeError(
                    f"{key} is not a valid attribute of {type(self).__name__}"
                )
            setattr(self, key, value)
        self._modified = False

    def __setattr__(self, name, value):
        """Update one of the attributes of the Row."""
        if name in self.FIELDS:
            super().__setattr__(name, self.FIELDS[name](value))
        else:
            super().__setattr__(name, value)
        if name != "_modified":
            super().__setattr__("_modified", True)

    def __repr__(self):
        """Return a string representation of the Row."""
        values = []
        for name in self.FIELDS.keys():
            if hasattr(self, name):
                values.append("%s=%r" % (name, getattr(self, name)))
        class_name = self.__class__.__name__
        values_str = ", ".join(values)
        return f"{class_name}({values_str})"

    def __eq__(self, other):
        """Test for quality between two instances."""
        return isinstance(other, self.__class__) and repr(self) == repr(other)

    @property
    def modified(self):
        """Return True if any fields in the Row have been modified."""
        return self._modified

    @classmethod
    def from_sqlite_row(cls, row):
        """Initialize a Row from a sqllite cursor row."""
        kwargs = {}
        for key in row.keys():
            if row[key] is None:
                continue
            kwargs[key] = row[key]
        return cls(**kwargs)

    @classmethod
    def select_all(cls, cursor):
        """Select all Row entries from the underlying sqlite table."""
        names = ",".join(cls.FIELDS.keys())
        cursor.execute(f"SELECT {names} FROM {cls.TABLE_NAME}")
        for row in cursor.fetchall():
            yield cls.from_sqlite_row(row)

    @classmethod
    def create_sqlite_table_from_row_schema(cls, cursor):
        """Create a sqlite table based on the schema for this Row class."""
        fields = []
        for name, value in cls.FIELDS.items():
            if isinstance(value, SQLType):
                fields.append(f"{name} {value.sql_type}")
            else:
                value = SQLType.TYPE_MAP[value]
                fields.append(f"{name} {value}")
        fields_str = ", ".join(fields)
        sql = f"CREATE TABLE {cls.TABLE_NAME}({fields_str})"
        try:
            cursor.execute(sql)
        except sqlite3.Error:
            LOG.exception("Query failed: %s", sql)
            raise

    def primary_key_name(self):
        """Return the primary key for this Row."""
        for name, value in self.FIELDS.items():
            if isinstance(value, PrimaryKey):
                return name
        raise RuntimeError(f"No primary key for table {self.TABLE_NAME}")

    def primary_key_value(self):
        """Return the value of the primary key for this Row."""
        return getattr(self, self.primary_key_name())

    def update_db(self, cursor):
        """Update the sqlite database to reflect any changes to this Row."""
        column_list = []
        values = []
        for name in self.FIELDS.keys():
            if hasattr(self, name):
                column_list.append(name)
                values.append(getattr(self, name))
        column_list_str = ", ".join(column_list)
        value_placeholders = ", ".join(["?"] * len(values))
        sql = (
            f"INSERT OR REPLACE INTO {self.TABLE_NAME} ({column_list_str}) "
            f"VALUES ({value_placeholders})"
        )
        try:
            cursor.execute(sql, values)
        except sqlite3.Error:
            LOG.exception("Query failed: %s %s", sql, values)
            raise
        try:
            pk_name = self.primary_key_name()
        except RuntimeError:
            pass
        else:
            pk_type = self.FIELDS[pk_name]
            if pk_type.auto_increment and not hasattr(self, pk_name):
                setattr(self, pk_name, cursor.lastrowid)

    def remove_from_db(self, cursor):
        """Remove the Row from the sqlite database."""
        pk_name = self.primary_key_name()
        pk_value = self.primary_key_value()
        sql = f"DELETE FROM {self.TABLE_NAME} WHERE {pk_name}=?"
        try:
            cursor.execute(sql, (pk_value,))
        except sqlite3.Error:
            LOG.exception("Query failed: %s %s", sql, pk_value)
            raise


class SQLType:
    """Base class for custom sqlite schema types."""

    TYPE_MAP = {
        int: "INTEGER",
        float: "REAL",
        str: "TEXT",
    }

    def __init__(self, type_constructor, *, sql_type=None, not_null=False):
        """Create a SQLType.

        Args:
            type_constructor: Callable(value) that will receive the value from
              the database cursor and convert it to a Python type.
            sql_type: The sqlite field type.
            not_null: Whether or not the sqlite field can be null.
        """
        self.type_constructor = type_constructor
        self._sql_type = (
            sql_type
            if sql_type is not None
            else SQLType.TYPE_MAP[type_constructor]
        )
        self.not_null = not_null

    def __call__(self, value):
        """Convert the sqlite row value to a Python type."""
        return self.type_constructor(value)

    @property
    def sql_type(self):
        """Return the sqlite type name for this type."""
        if self.not_null:
            return f"{self._sql_type} NOT NULL".lstrip()
        return self._sql_type.lstrip()


class PrimaryKey(SQLType):
    """Class used to indicate the primary key field for a Row."""

    def __init__(self, *args, auto_increment=False, **kwargs):
        """Create a PrimaryKey instance."""
        super().__init__(*args, **kwargs)
        self.auto_increment = auto_increment

    @property
    def sql_type(self):
        """Return the sqlite type name for this type."""
        value = super().sql_type
        value = f"{value} PRIMARY KEY"
        if self.auto_increment:
            value = f"{value} AUTOINCREMENT"
        return value.lstrip()


class RulesRow(DatabaseRow):
    """Row schema for the RULES table."""

    TABLE_NAME = "RULES"
    FIELDS = {
        "RuleID": PrimaryKey(int, sql_type=""),
        "Name": SQLType(str, not_null=True),
        "Type": SQLType(str, not_null=True),
        "RuleOrder": int,
        "StartDate": str,
        "EndDate": str,
        "State": str,
        "Sync": SQLType(str, sql_type="INTEGER"),
    }


class RuleDevicesRow(DatabaseRow):
    """Row schema for the RULEDEVICES table."""

    TABLE_NAME = "RULEDEVICES"
    FIELDS = {
        "RuleDevicePK": PrimaryKey(int, auto_increment=True),
        "RuleID": int,
        "DeviceID": str,
        "GroupID": int,
        "DayID": int,
        "StartTime": int,
        "RuleDuration": int,
        "StartAction": float,
        "EndAction": float,
        "SensorDuration": int,
        "Type": int,
        "Value": int,
        "Level": int,
        "ZBCapabilityStart": str,
        "ZBCapabilityEnd": str,
        "OnModeOffset": int,
        "OffModeOffset": int,
        "CountdownTime": int,
        "EndTime": int,
    }


class TargetDevicesRow(DatabaseRow):
    """Row schema for the RULEDEVICES table."""

    TABLE_NAME = "TARGETDEVICES"
    FIELDS = {
        "TargetDevicesPK": PrimaryKey(int, auto_increment=True),
        "RuleID": int,
        "DeviceID": str,
        "DeviceIndex": int,
    }


class DeviceCombinationRow(DatabaseRow):
    """Row schema for the RULEDEVICES table."""

    TABLE_NAME = "DEVICECOMBINATION"
    FIELDS = {
        "DeviceCombinationPK": PrimaryKey(int, auto_increment=True),
        "RuleID": int,
        "SensorID": str,
        "SensorGroupID": int,
        "DeviceID": str,
        "DeviceGroupID": int,
    }


class GroupDevicesRow(DatabaseRow):
    """Row schema for the GROUPDEVICES table."""

    TABLE_NAME = "GROUPDEVICES"
    FIELDS = {
        "GroupDevicePK": PrimaryKey(int, auto_increment=True),
        "GroupID": int,
        "DeviceID": str,
    }


class LocationInfoRow(DatabaseRow):
    """Row schema for the LOCATIONINFO table."""

    TABLE_NAME = "LOCATIONINFO"
    FIELDS = {
        "LocationPk": PrimaryKey(int, auto_increment=True),
        "cityName": str,
        "countryName": str,
        "latitude": str,
        "longitude": str,
        "countryCode": str,
        "region": str,
    }


class BlockedRulesRow(DatabaseRow):
    """Row schema for the BLOCKEDRULES table."""

    TABLE_NAME = "BLOCKEDRULES"
    FIELDS = {
        "Primarykey": PrimaryKey(int, auto_increment=True),
        "ruleId": str,
    }


class RulesNotifyMessageRow(DatabaseRow):
    """Row schema for the RULESNOTIFYMESSAGE table."""

    TABLE_NAME = "RULESNOTIFYMESSAGE"
    FIELDS = {
        "RuleID": PrimaryKey(int, auto_increment=True),
        "NotifyRuleID": int,
        "Message": str,
        "Frequency": int,
    }


class SensorNotificationRow(DatabaseRow):
    """Row schema for the SENSORNOTIFICATION table."""

    TABLE_NAME = "SENSORNOTIFICATION"
    FIELDS = {
        "SensorNotificationPK": PrimaryKey(int, auto_increment=True),
        "RuleID": int,
        "NotifyRuleID": int,
        "NotificationMessage": str,
        "NotificationDuration": int,
    }


class RulesDb:
    """Methods to access and manipulate the `rules` sqlite database."""

    def __init__(
        self, sql_db: sqlite3.Connection, default_udn: str, device_name: str
    ):
        """Preparse tables for device."""
        self._db = sql_db
        self._default_udn = default_udn
        self._device_name = device_name
        self._modified = False
        cursor = sql_db.cursor()
        self._rules = _index_by_primary_key(RulesRow.select_all(cursor))
        self._rule_devices = _index_by_primary_key(
            RuleDevicesRow.select_all(cursor)
        )
        self._target_devices = _index_by_primary_key(
            TargetDevicesRow.select_all(cursor)
        )

    def add_rule(self, rule: RulesRow) -> RulesRow:
        """Add a new entry to the RULES table."""
        if not hasattr(rule, 'RuleID'):
            rule.RuleID = max(self._rules.keys(), default=1)
        rule.update_db(self._db.cursor())
        self._rules[rule.RuleID] = rule
        self._modified = True
        return rule

    def remove_rule(self, rule: RulesRow) -> None:
        """Remove an entry to the RULES table."""
        del self._rules[rule.RuleID]
        rule.remove_from_db(self._db.cursor())
        self._modified = True

    def add_rule_devices(self, rule_devices: RuleDevicesRow) -> RuleDevicesRow:
        """Add a new entry to the RULEDEVICES table."""
        rule_devices.update_db(self._db.cursor())
        self._rule_devices[rule_devices.RuleDevicePK] = rule_devices
        self._modified = True
        return rule_devices

    def remove_rule_devices(self, rule_devices: RuleDevicesRow) -> None:
        """Remove an entry to the RULEDEVICES table."""
        del self._rule_devices[rule_devices.RuleDevicePK]
        rule_devices.remove_from_db(self._db.cursor())
        self._modified = True

    def add_target_devices(
        self, target_devices: TargetDevicesRow
    ) -> TargetDevicesRow:
        """Add a new entry to the TARGETDEVICES table."""
        target_devices.update_db(self._db.cursor())
        self._target_devices[target_devices.TargetDevicesPK] = target_devices
        self._modified = True
        return target_devices

    def remove_target_devices(self, target_devices: TargetDevicesRow) -> None:
        """Remove an entry to the TARGETDEVICES table."""
        del self._target_devices[target_devices.TargetDevicesPK]
        target_devices.remove_from_db(self._db.cursor())
        self._modified = True

    def update_if_modified(self) -> bool:
        """Sync the contents with the sqlite database.

        Return True if the database was modified.
        """
        modified = self._modified
        cursor = self._db.cursor()

        def update(rows):
            nonlocal modified
            for row in rows:
                if row.modified:
                    row.update_db(cursor)
                    modified = True

        update(self._rules.values())
        update(self._rule_devices.values())
        update(self._target_devices.values())
        return modified

    # pylint: disable=unsubscriptable-object
    # https://github.com/PyCQA/pylint/issues/3882#issuecomment-745148724
    def rules_for_device(
        self,
        *,
        device_udn: Optional[str] = None,
        rule_type: Optional[str] = None,
    ) -> List[Tuple[RulesRow, RuleDevicesRow]]:
        """Fetch the current rules for a partular device."""
        if device_udn is None:
            device_udn = self._default_udn
        values = []
        for device in self._rule_devices.values():
            if device_udn and device.DeviceID != device_udn:
                continue
            rule = self._rules[device.RuleID]
            if rule_type and rule.Type != rule_type:
                continue
            values.append((rule, device))

        return values

    def ensure_long_press_rule_exists(
        self,
        *,
        device_udn: Optional[str] = None,
        device_name: Optional[str] = None,
    ) -> RulesRow:
        """Ensure that a long press rule exists and is enabled for the device.

        Returns the long press rule.
        """
        if device_udn is None:
            device_udn = self._default_udn
        if device_name is None:
            device_name = self._device_name

        current_rules = self.rules_for_device(
            device_udn=device_udn, rule_type=RULE_TYPE_LONG_PRESS
        )
        for (rule, _) in current_rules:
            if rule.State != "1":
                LOG.info("Enabling long press rule for device %s", device_udn)
                rule.State = "1"
                rule.update_db(self._db.cursor())
            return rule

        LOG.info("Adding long press rule for device %s", device_udn)
        current_rules = self.rules_for_device(device_udn=device_udn)
        max_order = max(
            self._rules.values(), key=lambda r: r.RuleOrder, default=-1
        )
        new_rule = RulesRow(
            Name=f"{device_name} Long Press Rule",
            Type=RULE_TYPE_LONG_PRESS,
            RuleOrder=max_order + 1,
            StartDate='12201982',
            EndDate='07301982',
            State="1",
            Sync="NOSYNC",
        )
        self.add_rule(new_rule)
        self.add_rule_devices(
            RuleDevicesRow(
                RuleID=new_rule.RuleID,  # pylint: disable=no-member
                DeviceID=device_udn,
                GroupID=0,
                DayID=-1,
                StartTime=60,
                RuleDuration=86340,
                StartAction=ACTION_TOGGLE,
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
            )
        )
        return new_rule

    def get_target_devices_for_rule(self, rule: RulesRow) -> FrozenSet[str]:
        """Return the target DeviceIDs that are associated with the rule."""
        return frozenset(
            [
                target.DeviceID
                for target in self._target_devices.values()
                if target.RuleID == rule.RuleID
            ]
        )

    def add_target_device_to_rule(
        self,
        rule: RulesRow,
        device_id: str,
        *,
        device_index: Optional[int] = None,
    ):
        """Add a new target DeviceID to the rule."""
        if device_index is None:
            target_device_index = (
                target.DeviceIndex
                for target in self._target_devices.values()
                if target.RuleID == rule.RuleID
            )
            device_index = max(target_device_index, default=-1) + 1
        self.add_target_devices(
            TargetDevicesRow(
                RuleID=rule.RuleID,
                DeviceID=device_id,
                DeviceIndex=device_index,
            )
        )

    def remove_target_device_from_rule(self, rule: RulesRow, device_id: str):
        """Remove a target DeviceID from a rule."""
        targets = [
            target
            for target in self._target_devices.values()
            if target.RuleID == rule.RuleID and target.DeviceID == device_id
        ]
        if len(targets) != 1:
            raise NameError(
                f"device {device_id} not found in target devices for rule"
            )
        self.remove_target_devices(targets[0])


@contextlib.contextmanager
def rules_db_from_device(device) -> RulesDb:
    """Return a RuleDb instance for the rules on a device.

    Will also update the rules on the device if RuleDb is modified.
    """
    fetch = device.rules.FetchRules()
    version = int(fetch["ruleDbVersion"])
    rule_db_url = fetch["ruleDbPath"]
    response = requests.get(rule_db_url)

    with tempfile.NamedTemporaryFile(
        prefix="wemorules", suffix=".db"
    ) as temp_db_file:
        # Create a new db, or extract the current db.
        if response.status_code != 200:
            db_file_name = _create_empty_db(temp_db_file.name)
        else:
            db_file_name = _unpack_db(response.content, temp_db_file)

        # Open the DB.
        conn = sqlite3.connect(temp_db_file.name)
        try:
            conn.row_factory = sqlite3.Row
            rules = RulesDb(
                conn, default_udn=device.udn, device_name=device.name
            )
            yield rules

            if rules.update_if_modified():
                LOG.debug("Rules for %s updated. Storing rules.", device.name)
                conn.commit()
                conn.close()
                conn = None
                body = _pack_db(temp_db_file, db_file_name)
                device.rules.StoreRules(
                    ruleDbVersion=version + 1,
                    processDb=1,
                    ruleDbBody='&lt;![CDATA[' + body + ']]&gt;',
                )
        finally:
            if conn is not None:
                conn.close()


def _unpack_db(content, db_file):
    """Unpack the sqlite database from a .zip file content."""
    zip_contents = io.BytesIO(content)
    with zipfile.ZipFile(zip_contents) as zip_file:
        inner_file_name = zip_file.namelist()[0]
        with zip_file.open(inner_file_name) as zipped_db_file:
            db_file.write(zipped_db_file.read())
        return inner_file_name
    raise RuntimeError("Could not find database within zip file")


def _pack_db(db_file, inner_file_name):
    """Pack the sqlite database as a base64(zipped(db))."""
    zip_contents = io.BytesIO()
    with zipfile.ZipFile(
        zip_contents, mode='w', compression=zipfile.ZIP_DEFLATED
    ) as zip_file:
        zip_file.write(db_file.name, arcname=inner_file_name)
    return base64.b64encode(zip_contents.getvalue()).decode('utf-8')


def _index_by_primary_key(rows):
    """Return a dict of Rows indexed by the primary key."""
    result = {}
    for row in rows:
        result[row.primary_key_value()] = row
    return result


def _create_empty_db(file_name):
    """Create an empty sqlite database.

    Returns the name of the database file that would be inside the zip.
    """
    conn = sqlite3.connect(file_name)
    try:
        for row_class in [
            RulesRow,
            RuleDevicesRow,
            DeviceCombinationRow,
            GroupDevicesRow,
            LocationInfoRow,
            BlockedRulesRow,
            RulesNotifyMessageRow,
            SensorNotificationRow,
            TargetDevicesRow,
        ]:
            row_class.create_sqlite_table_from_row_schema(conn.cursor())
        conn.commit()
    finally:
        conn.close()
    return 'temppluginRules.db'
