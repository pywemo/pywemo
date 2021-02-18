"""Access and manipulate the on-device rules sqlite database."""

import base64
import contextlib
import io
import logging
import sqlite3
import tempfile
import zipfile
from types import MappingProxyType
from typing import FrozenSet, List, Mapping, Optional, Tuple

from .db_orm import DatabaseRow, PrimaryKey, SQLType

LOG = logging.getLogger(__name__)


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
        # Sync has type INTEGER in the database, but contains the
        # value 'NOSYNC', it is represented as a string in Python.
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
    """Row schema for the TARGETDEVICES table."""

    TABLE_NAME = "TARGETDEVICES"
    FIELDS = {
        "TargetDevicesPK": PrimaryKey(int, auto_increment=True),
        "RuleID": int,
        "DeviceID": str,
        "DeviceIndex": int,
    }


class DeviceCombinationRow(DatabaseRow):
    """Row schema for the DEVICECOMBINATION table."""

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


ALL_TABLES = [
    RulesRow,
    RuleDevicesRow,
    DeviceCombinationRow,
    GroupDevicesRow,
    LocationInfoRow,
    BlockedRulesRow,
    RulesNotifyMessageRow,
    SensorNotificationRow,
    TargetDevicesRow,
]


class RulesDb:
    """Methods to access and manipulate the `rules` sqlite database."""

    def __init__(
        self, sql_db: sqlite3.Connection, default_udn: str, device_name: str
    ):
        """Preparse tables for device."""
        self._db = sql_db
        self._default_udn = default_udn
        self._device_name = device_name
        self.modified = False
        cursor = sql_db.cursor()
        self._rules = _index_by_primary_key(RulesRow.select_all(cursor))
        self._rule_devices = _index_by_primary_key(
            RuleDevicesRow.select_all(cursor)
        )
        self._target_devices = _index_by_primary_key(
            TargetDevicesRow.select_all(cursor)
        )

    @property
    def db(self) -> sqlite3.Connection:
        """Return the sqlite3 connection instance."""
        return self._db

    def cursor(self) -> sqlite3.Cursor:
        """Return a cursor for the underlying sqlite3 database."""
        return self.db.cursor()

    # pylint: disable=unsubscriptable-object
    # https://github.com/PyCQA/pylint/issues/3882#issuecomment-745148724
    @property
    def rules(self) -> Mapping[int, RulesRow]:
        """Contents of the RULES table, keyed by RuleID."""
        return MappingProxyType(self._rules)

    def add_rule(self, rule: RulesRow) -> RulesRow:
        """Add a new entry to the RULES table."""
        if not hasattr(rule, "RuleID"):
            rule.RuleID = max(self._rules.keys(), default=1)
        rule.update_db(self.cursor())
        self._rules[rule.RuleID] = rule
        self.modified = True
        return rule

    def remove_rule(self, rule: RulesRow) -> None:
        """Remove an entry to the RULES table."""
        del self._rules[rule.RuleID]
        rule.remove_from_db(self.cursor())
        self.modified = True

    @property
    def rule_devices(self) -> Mapping[int, RuleDevicesRow]:
        """Contents of the RULEDEVICES table, keyed by RuleDevicePK."""
        return MappingProxyType(self._rule_devices)

    def add_rule_devices(self, rule_devices: RuleDevicesRow) -> RuleDevicesRow:
        """Add a new entry to the RULEDEVICES table."""
        rule_devices.update_db(self.cursor())
        self._rule_devices[rule_devices.RuleDevicePK] = rule_devices
        self.modified = True
        return rule_devices

    def remove_rule_devices(self, rule_devices: RuleDevicesRow) -> None:
        """Remove an entry to the RULEDEVICES table."""
        del self._rule_devices[rule_devices.RuleDevicePK]
        rule_devices.remove_from_db(self.cursor())
        self.modified = True

    @property
    def target_devices(self) -> Mapping[int, TargetDevicesRow]:
        """Contents of the TARGETDEVICES table, keyed by TargetDevicesPK."""
        return MappingProxyType(self._target_devices)

    def add_target_devices(
        self, target_devices: TargetDevicesRow
    ) -> TargetDevicesRow:
        """Add a new entry to the TARGETDEVICES table."""
        target_devices.update_db(self.cursor())
        self._target_devices[target_devices.TargetDevicesPK] = target_devices
        self.modified = True
        return target_devices

    def remove_target_devices(self, target_devices: TargetDevicesRow) -> None:
        """Remove an entry to the TARGETDEVICES table."""
        del self._target_devices[target_devices.TargetDevicesPK]
        target_devices.remove_from_db(self.cursor())
        self.modified = True

    def update_if_modified(self) -> bool:
        """Sync the contents with the sqlite database.

        Return True if the database was modified.
        """
        modified = self.modified
        cursor = self.cursor()

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

    def rules_for_device(
        self,
        *,
        device_udn: Optional[str] = None,
        rule_type: Optional[str] = None,
    ) -> List[Tuple[RulesRow, RuleDevicesRow]]:
        """Fetch the current rules for a particular device."""
        if device_udn is None:
            device_udn = self._default_udn
        values = []
        for device in self.rule_devices.values():
            if device_udn and device.DeviceID != device_udn:
                continue
            rule = self.rules[device.RuleID]
            if rule_type and rule.Type != rule_type:
                continue
            values.append((rule, device))

        return values

    def get_target_devices_for_rule(self, rule: RulesRow) -> FrozenSet[str]:
        """Return the target DeviceIDs that are associated with the rule."""
        return frozenset(
            [
                target.DeviceID
                for target in self.target_devices.values()
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
                for target in self.target_devices.values()
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
            for target in self.target_devices.values()
            if target.RuleID == rule.RuleID and target.DeviceID == device_id
        ]
        if len(targets) != 1:
            raise NameError(
                f"device {device_id} not found in target devices for rule"
            )
        self.remove_target_devices(targets[0])

    def clear_all(self) -> None:
        """Clear all data from the database."""
        cursor = self.cursor()
        for table in ALL_TABLES:
            cursor.execute(f"DELETE FROM {table.TABLE_NAME}")
        self.modified = True
        self._rules = _index_by_primary_key(RulesRow.select_all(cursor))
        self._rule_devices = _index_by_primary_key(
            RuleDevicesRow.select_all(cursor)
        )
        self._target_devices = _index_by_primary_key(
            TargetDevicesRow.select_all(cursor)
        )


@contextlib.contextmanager
def rules_db_from_device(device) -> RulesDb:
    """Yield a RuleDb instance for the rules on a device.

    Usage:
        with rules_db.rules_db_from_device(device) as rules:
            ...

    The sqlite3.Connection object can be accessed via the '.db' property in the
    returned RulesDb instance. If the database is modified directly, setting
    the `.modified` attribute to True will cause the database to be sent to the
    WeMo device. Any updates that take place via the RulesDb helper methods
    will also be propagated back to the WeMo device.
    """
    fetch = device.rules.FetchRules()
    version = int(fetch["ruleDbVersion"])
    rule_db_url = fetch["ruleDbPath"]
    response = device.session.get(rule_db_url)

    with tempfile.NamedTemporaryFile(
        prefix="wemorules", suffix=".db"
    ) as temp_db_file:
        # Create a new db, or extract the current db.
        if response.status != 200:
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
                    ruleDbBody="&lt;![CDATA[" + body + "]]&gt;",
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
        zip_contents, mode="w", compression=zipfile.ZIP_DEFLATED
    ) as zip_file:
        zip_file.write(db_file.name, arcname=inner_file_name)
    return base64.b64encode(zip_contents.getvalue()).decode("utf-8")


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
        for row_class in ALL_TABLES:
            row_class.create_sqlite_table_from_row_schema(conn.cursor())
        conn.commit()
    finally:
        conn.close()
    return "temppluginRules.db"
