"""
wifi_tools.py - WiFi profile management and password extraction.

Uses netsh wlan CLI parsing for saved network profiles, password
recovery, and profile export/import.  Zero third-party dependencies.
"""

import os
import re
import subprocess
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data: Any = None, message: str = "OK") -> Dict[str, Any]:
    return {"success": True, "data": data, "error": None, "message": message}


def _err(error: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "error": error, "message": error}


def _netsh(args: str, timeout: int = 10) -> str:
    """Run a netsh wlan command and return stdout."""
    r = subprocess.run(
        f"netsh wlan {args}", capture_output=True, text=True,
        timeout=timeout, shell=True,
    )
    return r.stdout


# ---------------------------------------------------------------------------
# Profile Listing
# ---------------------------------------------------------------------------

def list_saved_wifi_profiles() -> Dict[str, Any]:
    """List all saved WiFi profile names."""
    try:
        output = _netsh("show profiles")
        profiles = re.findall(r"All User Profile\s*:\s*(.+)", output)
        profiles = [p.strip() for p in profiles if p.strip()]
        return _ok({"profiles": profiles, "count": len(profiles)},
                    f"Found {len(profiles)} saved WiFi profiles")
    except Exception as e:
        return _err(str(e))


def get_wifi_password(profile_name: str) -> Dict[str, Any]:
    """Extract the saved password for a WiFi profile (requires admin)."""
    try:
        output = _netsh(f'show profile name="{profile_name}" key=clear')
        # Check if profile exists
        if "is not found" in output.lower():
            return _err(f"Profile '{profile_name}' not found")
        # Extract key content
        match = re.search(r"Key Content\s*:\s*(.+)", output)
        password = match.group(1).strip() if match else None
        # Extract auth/cipher info
        auth = re.search(r"Authentication\s*:\s*(.+)", output)
        cipher = re.search(r"Cipher\s*:\s*(.+)", output)
        security = re.search(r"Security key\s*:\s*(.+)", output)
        data = {
            "profile": profile_name,
            "password": password,
            "authentication": auth.group(1).strip() if auth else None,
            "cipher": cipher.group(1).strip() if cipher else None,
            "security_key_present": security.group(1).strip() if security else None,
        }
        if password:
            return _ok(data, f"Password for '{profile_name}': {password}")
        return _ok(data, f"No password stored for '{profile_name}' (open network or not available)")
    except Exception as e:
        return _err(str(e))


def export_all_wifi_passwords() -> Dict[str, Any]:
    """Export all saved WiFi profiles with their passwords."""
    try:
        profiles_result = list_saved_wifi_profiles()
        if not profiles_result.get("success"):
            return profiles_result
        profiles = profiles_result["data"]["profiles"]
        results = []
        for name in profiles:
            pw_result = get_wifi_password(name)
            if pw_result.get("success"):
                results.append(pw_result["data"])
            else:
                results.append({"profile": name, "password": None,
                                "error": pw_result.get("error")})
        return _ok({"networks": results, "count": len(results)},
                    f"Exported passwords for {len(results)} networks")
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Profile Details
# ---------------------------------------------------------------------------

def get_wifi_profile_details(profile_name: str) -> Dict[str, Any]:
    """Get full details of a saved WiFi profile."""
    try:
        output = _netsh(f'show profile name="{profile_name}"')
        if "is not found" in output.lower():
            return _err(f"Profile '{profile_name}' not found")
        fields = {}
        for pattern in [
            ("ssid_name", r"SSID name\s*:\s*\"(.+?)\""),
            ("network_type", r"Network type\s*:\s*(.+)"),
            ("radio_type", r"Radio type\s*:\s*(.+)"),
            ("authentication", r"Authentication\s*:\s*(.+)"),
            ("cipher", r"Cipher\s*:\s*(.+)"),
            ("connection_mode", r"Connection mode\s*:\s*(.+)"),
            ("cost", r"Cost\s*:\s*(.+)"),
        ]:
            m = re.search(pattern[1], output)
            fields[pattern[0]] = m.group(1).strip() if m else None
        fields["profile_name"] = profile_name
        return _ok(fields, f"Details for '{profile_name}'")
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Interface & Connection State
# ---------------------------------------------------------------------------

def get_wifi_interface_info() -> Dict[str, Any]:
    """Get current WiFi interface state (connected SSID, signal, etc.)."""
    try:
        output = _netsh("show interfaces")
        fields = {}
        for key, pattern in [
            ("name", r"Name\s*:\s*(.+)"),
            ("description", r"Description\s*:\s*(.+)"),
            ("state", r"State\s*:\s*(.+)"),
            ("ssid", r"SSID\s*:\s*(.+)"),
            ("bssid", r"BSSID\s*:\s*(.+)"),
            ("radio_type", r"Radio type\s*:\s*(.+)"),
            ("authentication", r"Authentication\s*:\s*(.+)"),
            ("signal", r"Signal\s*:\s*(.+)"),
            ("channel", r"Channel\s*:\s*(.+)"),
            ("receive_rate", r"Receive rate \(Mbps\)\s*:\s*(.+)"),
            ("transmit_rate", r"Transmit rate \(Mbps\)\s*:\s*(.+)"),
        ]:
            m = re.search(pattern, output)
            fields[key] = m.group(1).strip() if m else None
        # Convert signal percentage to approximate dBm
        if fields.get("signal"):
            pct_match = re.match(r"(\d+)", fields["signal"])
            if pct_match:
                pct = int(pct_match.group(1))
                # Approximate: dBm = (pct / 2) - 100
                dbm = round((pct / 2) - 100)
                fields["signal_dbm"] = dbm
                fields["signal_percent"] = pct
        return _ok(fields, f"WiFi interface: {fields.get('ssid', 'disconnected')}")
    except Exception as e:
        return _err(str(e))


def list_available_networks() -> Dict[str, Any]:
    """Scan and list currently visible WiFi networks."""
    try:
        output = _netsh("show networks mode=bssid")
        networks = []
        blocks = re.split(r"(?=SSID \d+\s*:)", output)
        for block in blocks:
            if not block.strip():
                continue
            ssid_m = re.search(r"SSID \d+\s*:\s*(.+)", block)
            if not ssid_m:
                continue
            net = {"ssid": ssid_m.group(1).strip()}
            for key, pat in [
                ("network_type", r"Network type\s*:\s*(.+)"),
                ("authentication", r"Authentication\s*:\s*(.+)"),
                ("encryption", r"Encryption\s*:\s*(.+)"),
                ("bssid", r"BSSID \d+\s*:\s*(.+)"),
                ("signal", r"Signal\s*:\s*(.+)"),
                ("channel", r"Channel\s*:\s*(.+)"),
            ]:
                m = re.search(pat, block)
                net[key] = m.group(1).strip() if m else None
            # Signal to dBm
            if net.get("signal"):
                pct_m = re.match(r"(\d+)", net["signal"])
                if pct_m:
                    pct = int(pct_m.group(1))
                    net["signal_percent"] = pct
                    net["signal_dbm"] = round((pct / 2) - 100)
            networks.append(net)
        return _ok({"networks": networks, "count": len(networks)},
                    f"Found {len(networks)} available networks")
    except Exception as e:
        return _err(str(e))


def disconnect_wifi() -> Dict[str, Any]:
    """Disconnect from the current WiFi network."""
    try:
        _netsh("disconnect")
        return _ok(None, "WiFi disconnected")
    except Exception as e:
        return _err(str(e))


def connect_wifi(profile_name: str) -> Dict[str, Any]:
    """Connect to a saved WiFi profile."""
    try:
        output = _netsh(f'connect name="{profile_name}"')
        if "successfully" in output.lower() or "completed" in output.lower():
            return _ok({"profile": profile_name},
                        f"Connected to '{profile_name}'")
        return _err(f"Connection failed: {output.strip()[:200]}")
    except Exception as e:
        return _err(str(e))
