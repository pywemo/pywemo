"""Connect a WeMo setup access point to the configured home Wi-Fi."""

import argparse
import getpass
import ipaddress
import json
import logging
import re
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pywemo


def report_failure(exc, password=""):
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        detail = str(exc)
        if password:
            detail = detail.replace(password, "[REDACTED]")
        print(f"  {type(exc).__name__}: {detail}", flush=True)
        exc = exc.__cause__ or exc.__context__


def connect_with_fallback(device, ssid, password, method, lengths, explicit=False):
    candidates = [(method, lengths)]
    if not explicit:
        candidates += [(1, True), (2, False), (3, True), (1, False), (2, True), (3, False)]
    candidates = list(dict.fromkeys(candidates))
    for index, (encoding, append_lengths) in enumerate(candidates, 1):
        print(
            f"Attempt {index}/{len(candidates)}: SSID={ssid}; "
            f"encrypt_method={encoding}; password_lengths={append_lengths}",
            flush=True,
        )
        try:
            result = device.setup(
                ssid=ssid, password=password,
                _encrypt_method=encoding, _add_password_lengths=append_lengths,
            )
            print(f"Setup result: {result}", flush=True)
            if result == ("1", "success"):
                return True
            if result[0] == "2":
                print("Device reports a short password; stopping retries.")
                return False
        except pywemo.exceptions.ShortPassword as exc:
            report_failure(exc, password)
            return False
        except pywemo.exceptions.PyWeMoException as exc:
            print("Attempt failed:", flush=True)
            report_failure(exc, password)
        if index < len(candidates):
            # A failed request can mean the device joined Wi-Fi and disappeared.
            # Only try another encoding if the setup endpoint still responds.
            print("Checking that the setup endpoint is still reachable...", flush=True)
            try:
                device.get_service("WiFiSetup").GetApList()
            except pywemo.exceptions.PyWeMoException as exc:
                report_failure(exc, password)
                print("Setup status uncertain. Reconnect to home Wi-Fi and discover devices before retrying.")
                return False
    print("All selected encoding attempts failed. The diagnostics and errors above show each attempt.")
    return False


def check_setup_network():
    result = subprocess.run(
        ["netsh", "wlan", "show", "interfaces"],
        capture_output=True, text=True, check=True, timeout=20,
    )
    names = re.findall(r"^\s*SSID\s*:\s*(.+?)\s*$", result.stdout, re.MULTILINE)
    if len(names) != 1:
        raise ValueError("Cannot identify one connected Wi-Fi SSID. Check Windows Wi-Fi connection.")
    name = names[0]
    print(f"Connected Wi-Fi: {name}")
    if not name.casefold().startswith("wemo"):
        raise ValueError("Connect this computer to the intended WeMo setup Wi-Fi first.")


def detect_gateway():
    command = (
        "Get-NetIPConfiguration | Where-Object { "
        "$_.NetAdapter.Status -eq 'Up' -and "
        "$_.NetAdapter.InterfaceType -eq 71 } | "
        "ForEach-Object { $_.IPv4DefaultGateway.NextHop } | ConvertTo-Json"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        capture_output=True, text=True, check=True, timeout=20,
    )
    gateways = json.loads(result.stdout.strip() or "null")
    if isinstance(gateways, str):
        gateways = [gateways]
    if not gateways or len(gateways) != 1:
        raise ValueError("Cannot identify one Wi-Fi gateway. Supply --ip ADDRESS.")
    return gateways[0]


def main():
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("pywemo.ouimeaux_device").setLevel(logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", help="WeMo setup IP; defaults to the Wi-Fi gateway")
    parser.add_argument("--config", type=Path, default=ROOT / "wemo-setup.json")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="Identify device without configuring it")
    modes.add_argument("--diagnose", action="store_true", help="Scan networks without changing Wi-Fi")
    modes.add_argument("--factory-reset", action="store_true", help="Erase device name, rules and Wi-Fi, then reboot")
    parser.add_argument("--encrypt-method", type=int, choices=(1, 2, 3))
    parser.add_argument("--password-lengths", choices=("yes", "no"))
    args = parser.parse_args()
    try:
        check_setup_network()
        host = args.ip or detect_gateway()
        ipaddress.IPv4Address(host)
        print(f"Checking WeMo at {host}...", flush=True)
        url = pywemo.setup_url_for_address(host)
        if not url:
            raise ValueError("No WeMo found. Connect to its WeMo.* Wi-Fi and check --ip.")
        device = pywemo.discovery.device_from_description(url)
        if device is None:
            raise ValueError("WeMo device description could not be loaded.")
        print(f"Device: {device.name} ({device.model_name})", flush=True)
        if args.check:
            return 0
        if args.factory_reset:
            print("Factory reset erases this device's name, rules and Wi-Fi settings.")
            if input(f"Type RESET to reset {device.name}: ") != "RESET":
                print("Reset cancelled.")
                return 0
            print(f"Reset response: {device.reset(data=True, wifi=True)}")
            print("Wait for the device to reboot, reconnect to its WeMo Wi-Fi, then run --diagnose.")
            return 0
        if not args.config.exists():
            raise ValueError("Create wemo-setup.json using wemo-setup.example.json first.")
        config = json.loads(args.config.read_text(encoding="utf-8-sig"))
        ssid = config.get("ssid")
        if not isinstance(ssid, str) or not ssid.strip():
            raise ValueError("Config must contain a nonempty ssid.")
        print(f"Scanning for {ssid}...", flush=True)
        access_points = device.get_service("WiFiSetup").GetApList()["ApList"]
        rows = [
            row.strip().rstrip(",")
            for row in access_points.splitlines()
            if "|" in row
        ]
        print("Networks reported by WeMo (SSID | channel | remaining scan fields):")
        for row in rows:
            print(f"  {row}")
        if not rows:
            print("  No network rows returned.")
        matches = [row for row in rows if row.startswith(f"{ssid}|")]
        if not matches:
            raise ValueError(f"WeMo cannot see {ssid}. Check 2.4 GHz coverage and SSID.")
        for match in matches:
            fields = match.split("|")
            print(f"Target network: {fields[0]}; channel: {fields[1]}; security: {fields[-1]}")
        flags = getattr(device, "_config_any", {})
        is_rtos = flags.get("rtos", "0") == "1"
        is_iot = flags.get("iot", "0") == "1"
        method = args.encrypt_method or (2 if is_rtos and not is_iot else 1)
        lengths = method in (1, 3) if args.password_lengths is None else args.password_lengths == "yes"
        print(f"Firmware flags: rtos={is_rtos}, iot={is_iot}")
        print(f"Password encoding: method={method}, append_lengths={lengths}")
        if args.diagnose:
            print("Diagnostics complete; no Wi-Fi settings changed.")
            return 0
        password = config.get("password")
        if not password:
            password = getpass.getpass(f"Password for {ssid}: ")
        if not isinstance(password, str):
            raise ValueError("Config password must be a string.")
        print(f"Connecting {device.name} to {ssid}...", flush=True)
        if not connect_with_fallback(
            device, ssid, password, method, lengths,
            explicit=args.encrypt_method is not None or args.password_lengths is not None,
        ):
            return 1
        print(f"Reconnect this computer to {ssid}, then run discovery to verify.")
        return 0
    except Exception as exc:
        # Avoid printing exception details that might contain Wi-Fi credentials.
        if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError):
            print(f"Error: {exc}", file=sys.stderr)
        else:
            print(f"Setup failed ({type(exc).__name__}). Check connection and config.", file=sys.stderr)
            cause = exc.__cause__
            while cause is not None:
                print(f"Caused by: {type(cause).__name__}", file=sys.stderr)
                cause = cause.__cause__
            print("Run --diagnose to inspect target security. Try --encrypt-method 2 --password-lengths no if automatic encoding fails.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
