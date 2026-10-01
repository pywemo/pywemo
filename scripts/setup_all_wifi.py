"""Provision visible open WeMo setup networks sequentially on Windows."""

import argparse
import getpass
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET

import setup_wifi


def wlan(*args):
    """Invoke netsh without shell interpolation of SSIDs or profile names."""
    result = subprocess.run(
        ["netsh", "wlan", *args], capture_output=True, text=True,
        check=True, timeout=20,
    )
    return result.stdout


def connected():
    """Return the sole connected SSID and its saved Windows profile name."""
    output = wlan("show", "interfaces")
    names = re.findall(r"^\s*SSID\s*:\s*(.+?)\s*$", output, re.MULTILINE)
    profiles = re.findall(r"^\s*Profile\s*:\s*(.+?)\s*$", output, re.MULTILINE)
    return (names[0] if len(names) == 1 else None,
            profiles[0] if len(profiles) == 1 else None)


def scan():
    """Select only visible open WeMo setup networks from English netsh output."""
    output = wlan("show", "networks", "mode=bssid")
    networks = []
    for block in re.split(r"(?m)^\s*SSID \d+\s*:\s*", output)[1:]:
        name = block.splitlines()[0].strip()
        auth = re.search(r"(?m)^\s*Authentication\s*:\s*(.+)$", block)
        encryption = re.search(r"(?m)^\s*Encryption\s*:\s*(.+)$", block)
        if (name.casefold().startswith("wemo.") and auth and encryption
                and auth[1].strip() == "Open" and encryption[1].strip() == "None"):
            networks.append(name)
    return sorted(set(networks))


def wait_for(name):
    """Wait for association; netsh connect returns before Wi-Fi is ready."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if connected()[0] == name:
            return
        time.sleep(2)
    raise RuntimeError(f"Timed out connecting to {name}")


def profile_xml(name, ssid):
    """Build a temporary manual-connect profile, escaping SSID XML characters."""
    ns = "http://www.microsoft.com/networking/WLAN/profile/v1"
    ET.register_namespace("", ns)
    root = ET.Element(f"{{{ns}}}WLANProfile")
    def add(parent, tag, value=None):
        element = ET.SubElement(parent, f"{{{ns}}}{tag}")
        element.text = value
        return element
    add(root, "name", name)
    config = add(root, "SSIDConfig")
    network = add(config, "SSID")
    add(network, "hex", ssid.encode("utf-8").hex())
    add(network, "name", ssid)
    add(root, "connectionType", "ESS")
    add(root, "connectionMode", "manual")
    security = add(add(root, "MSM"), "security")
    auth = add(security, "authEncryption")
    add(auth, "authentication", "open")
    add(auth, "encryption", "none")
    add(auth, "useOneX", "false")
    return ET.tostring(root, encoding="unicode")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=setup_wifi.ROOT / "wemo-setup.json")
    parser.add_argument("--list", action="store_true", help="List candidates without changing connections")
    args = parser.parse_args()
    results = []
    original_ssid, original_profile = connected()
    if not original_ssid or not original_profile:
        parser.error("Start connected to your home Wi-Fi with a saved Windows profile.")
    candidates = scan()
    # Take one snapshot so failed devices are not retried indefinitely.
    print(f"Visible open WeMo setup networks: {candidates}", flush=True)
    if args.list or not candidates:
        return 0
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    ssid = config.get("ssid")
    if not isinstance(ssid, str) or not ssid.strip():
        parser.error("Config requires a nonempty ssid.")
    if original_ssid != ssid:
        parser.error("Start on the target home Wi-Fi so its saved profile can be restored.")
    password = config.get("password") or getpass.getpass(f"Password for {ssid}: ")
    if not isinstance(password, str):
        parser.error("Password must be a string.")
    try:
        for network in candidates:
            # Unique names avoid replacing the user's existing Wi-Fi profiles.
            profile = f"pywemo-setup-{uuid.uuid4().hex}"
            try:
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "profile.xml"
                    path.write_text(profile_xml(profile, network), encoding="utf-8")
                    wlan("add", "profile", f"filename={path}", "user=current")
                print(f"Connecting computer to {network}...", flush=True)
                wlan("connect", f"name={profile}", f"ssid={network}")
                wait_for(network)
                # Allow DHCP to assign the setup network's address and gateway.
                time.sleep(3)
                code = setup_wifi.main(["--config", str(args.config)], supplied_password=password)
                results.append((network, "setup reported success" if code == 0 else "failed or uncertain"))
            except Exception as exc:
                print(f"{network}: {type(exc).__name__}; continuing", flush=True)
                results.append((network, "failed or uncertain"))
            finally:
                # Delete temporary profiles even if restoring home Wi-Fi fails.
                try:
                    wlan("connect", f"name={original_profile}", f"ssid={original_ssid}")
                    wait_for(original_ssid)
                finally:
                    wlan("delete", "profile", f"name={profile}")
    finally:
        wlan("connect", f"name={original_profile}", f"ssid={original_ssid}")
        print("Batch results:", flush=True)
        for network, result in results:
            print(f"  {network}: {result}")
        print("Run home-network discovery to verify devices, including uncertain results.")
    return 0 if all(result == "setup reported success" for _, result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
