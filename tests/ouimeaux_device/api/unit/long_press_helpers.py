"""Helper(s) for long press testing on supported devices."""

import contextlib
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from pywemo.ouimeaux_device.api import long_press, rules_db


class TestLongPress:
    """Test methods that are shared between devices that support long press."""

    method = "pywemo.ouimeaux_device.api.long_press.rules_db_from_device"

    @pytest.fixture
    def rules_db_from_device(self, device):
        with tempfile.NamedTemporaryFile(
            prefix="wemorules", suffix=".db"
        ) as temp_file:
            rules_db._create_empty_db(temp_file.name)
            try:
                conn = sqlite3.connect(temp_file.name)
                conn.row_factory = sqlite3.Row
                rdb = rules_db.RulesDb(conn, device.udn, device.name)

                @contextlib.contextmanager
                def yield_rdb(*_):
                    yield rdb

                with patch(
                    TestLongPress.method,
                    side_effect=yield_rdb,
                ):
                    yield rdb
            finally:
                conn.close()

    def test_supports_long_press(self, device):
        """Verify that the device has long press support."""
        assert device.supports_long_press()

    @pytest.mark.usefixtures("rules_db_from_device")
    def test_list_add_remove_long_press_udns(self, device):
        """Verify that devices can be added/removed for long press control."""
        udns = frozenset(["uuid:1", "uuid:2"])
        device.add_long_press_udns(udns)
        assert device.list_long_press_udns() == udns

        device.remove_long_press_udns(udns)
        assert device.list_long_press_udns() == frozenset()

    @pytest.mark.usefixtures("rules_db_from_device")
    def test_get_set_long_press_action(self, device):
        """Test code for getting the ActionType of a long press."""
        assert device.get_long_press_action() is None

        device.set_long_press_action(long_press.ActionType.OFF)
        assert device.get_long_press_action() == long_press.ActionType.OFF

    @pytest.mark.usefixtures("rules_db_from_device")
    def test_ensure_remove_long_press_virtual_device(self, device):
        """Test that the virtual device can be added and removed."""
        assert device.list_long_press_udns() == frozenset()

        device.ensure_long_press_virtual_device()
        assert device.list_long_press_udns() == frozenset(
            [long_press.VIRTUAL_DEVICE_UDN]
        )

        device.remove_long_press_virtual_device()
        assert device.list_long_press_udns() == frozenset()
