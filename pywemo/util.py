"""Miscellaneous utility functions."""
from __future__ import annotations

import socket
import warnings
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

import ifaddr
from lxml import etree as et


# Taken from http://stackoverflow.com/a/10077069
def etree_to_dict(tree: et.Element) -> dict[str, Any]:
    """Split a tree into a dict."""
    warnings.warn(
        "pywemo.util.etree_to_dict is unused within pywemo and will be "
        "removed in a future release.",
        DeprecationWarning,
    )
    # strip namespace
    tag_name = tree.tag[tree.tag.find("}") + 1 :]

    tree_dict: dict[str, Any] = {tag_name: {} if tree.attrib else None}
    children = list(tree)
    if children:
        default_dict = defaultdict(list)
        for dict_children in map(etree_to_dict, children):
            for key, value in dict_children.items():
                default_dict[key].append(value)
        tree_dict = {
            tag_name: {
                key: value[0] if len(value) == 1 else value
                for key, value in default_dict.items()
            }
        }
    if tree.attrib:
        tree_dict[tag_name].update(
            ('@' + key, value) for key, value in tree.attrib.items()
        )
    if tree.text:
        text = tree.text.strip()
        if children or tree.attrib:
            if text:
                tree_dict[tag_name]['#text'] = text
        else:
            tree_dict[tag_name] = text
    return tree_dict


def interface_addresses() -> list[str]:
    """
    Return local address for broadcast/multicast.

    Return local address of any network associated with a local interface
    that has broadcast (and probably multicast) capability.
    """
    addresses = []

    for iface in ifaddr.get_adapters():
        for addr in iface.ips:
            if not addr.is_IPv4 or addr.ip == '127.0.0.1':
                continue

            addresses.append(addr.ip)

    return addresses


def get_ip_address(host: str = '1.2.3.4') -> str | None:
    """Return IP from hostname or IP."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((host, 9))
        return cast(str, sock.getsockname()[0])
    except OSError:
        return None
    finally:
        del sock


def signal_strength_to_dbm(value: dict[str, str] | str) -> int:
    """Convert signal strength percentage into a RSSI dBm value.

    WeMo devices use the algorithm described here to convert a RSSI dBm value
    into a signal strength percentage:
    https://community.cambiumnetworks.com/t/cnmaestro-wifi-analyzer-tool/63471

    signal_strength_to_dbm is meant to be used with the
    basicevent.GetSignalStrength UPnP Action.

    signal_strength = device.basicevent.GetSignalStrength()
    signal_strength_to_dbm(signal_strength)
      or
    signal_strength_to_dbm(signal_strength["SignalStrength"])
    """
    if isinstance(value, dict):
        percent_str = value["SignalStrength"]
    else:
        percent_str = value

    percent = round(float(percent_str))
    if percent >= 100:
        return -50
    if percent >= 24:
        return round((percent - 24) * 10 / 26 - 80)
    if percent > 0:
        return round(percent * 10 / 26 - 90)
    return -90


@dataclass
class MetaInfo:
    """Parsed output of the metainfo.GetMetaInfo() Action."""

    mac: str
    serial_number: str
    device_sku: str
    firmware_version: str
    access_point_ssid: str
    model_name: str

    @classmethod
    def from_meta_info(cls, value: dict[str, str] | str) -> MetaInfo:
        """Initialize from metainfo.GetMetaInfo() output."""
        info_str = value["MetaInfo"] if isinstance(value, dict) else value
        values = info_str.split("|")
        if len(values) < 6:
            raise ValueError(f"Could not unpack MetaInfo: {info_str}")
        return cls(*values[:6])


@dataclass
class ExtMetaInfo:
    """Parsed output of the metainfo.GetExtMetaInfo() Action."""

    current_client_state: int
    ice_running: int
    nat_initialized: int
    last_auth_value: int
    uptime: timedelta
    firmware_update_state: int
    utc_time: datetime
    home_id: str
    remote_access_enabled: bool
    model_name: str

    @classmethod
    def from_ext_meta_info(cls, value: dict[str, str] | str) -> ExtMetaInfo:
        """Initialize from metainfo.GetExtMetaInfo() output."""
        info_str = value["ExtMetaInfo"] if isinstance(value, dict) else value
        values = info_str.split("|")
        if not len(values) > 9:
            raise ValueError(f"Could not unpack ExtMetaInfo: {info_str}")

        hours, minutes, seconds = (int(v) for v in values[4].split(":"))
        return cls(
            current_client_state=int(values[0]),
            ice_running=int(values[1]),
            nat_initialized=int(values[2]),
            last_auth_value=int(values[3]),
            uptime=timedelta(hours=hours, minutes=minutes, seconds=seconds),
            firmware_update_state=int(values[5]),
            utc_time=datetime.utcfromtimestamp(int(values[6])),
            home_id=values[7],
            remote_access_enabled=bool(int(values[8])),
            model_name=values[9],
        )
