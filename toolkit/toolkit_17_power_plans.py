"""
toolkit_17_power_plans.py
List, query, and switch Windows power plans (balanced, high performance, etc.)
via powercfg and PowerShell.
"""
from __future__ import annotations
import subprocess
import re
import json
from typing import Any, Dict, List

def _run(cmd: list, timeout: int = 20) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.stdout.strip()

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=20
    )
    return result.stdout.strip()

def list_power_plans() -> Dict[str, Any]:
    try:
        out = _run(["powercfg", "/list"])
        plans = []
        for line in out.splitlines():
            m = re.search(r"GUID: ([0-9a-f\-]+)\s+\((.+?)\)(\s+\*)?", line, re.IGNORECASE)
            if m:
                plans.append({
                    "guid": m.group(1).strip(),
                    "name": m.group(2).strip(),
                    "active": bool(m.group(3))
                })
        return {"success": True, "data": plans, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_active_power_plan() -> Dict[str, Any]:
    try:
        out = _run(["powercfg", "/getactivescheme"])
        m = re.search(r"GUID: ([0-9a-f\-]+)\s+\((.+?)\)", out, re.IGNORECASE)
        if m:
            return {"success": True, "data": {"guid": m.group(1).strip(), "name": m.group(2).strip()}, "error": None}
        return {"success": True, "data": {"raw": out}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_power_plan(plan_guid: str) -> Dict[str, Any]:
    try:
        out = _run(["powercfg", "/setactive", plan_guid])
        return {"success": True, "data": "Power plan set to " + plan_guid, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_balanced_plan() -> Dict[str, Any]:
    try:
        out = _run(["powercfg", "/setactive", "381b4222-f694-41f0-9685-ff5bb260df2e"])
        return {"success": True, "data": "Switched to Balanced plan", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_high_performance_plan() -> Dict[str, Any]:
    try:
        out = _run(["powercfg", "/setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"])
        return {"success": True, "data": "Switched to High Performance plan", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_power_saver_plan() -> Dict[str, Any]:
    try:
        out = _run(["powercfg", "/setactive", "a1841308-3541-4fab-bc81-f71556f20b4a"])
        return {"success": True, "data": "Switched to Power Saver plan", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_sleep_timeout(on_battery: bool = True) -> Dict[str, Any]:
    """Get current sleep timeout in minutes."""
    try:
        index = "dc" if not on_battery else "ac"
        out = _run(["powercfg", "/query", "SCHEME_CURRENT", "SUB_SLEEP", "STANDBYIDLE"])
        lines = out.splitlines()
        for i, line in enumerate(lines):
            if "Current " + index.upper() + " Power Setting Index:" in line:
                val = int(line.split(":")[-1].strip(), 16)
                return {"success": True, "data": {"seconds": val, "minutes": val // 60}, "error": None}
        return {"success": True, "data": {"raw": out}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_sleep_timeout(minutes: int, on_battery: bool = True) -> Dict[str, Any]:
    try:
        seconds = minutes * 60
        setting = "monitor-timeout-ac" if not on_battery else "monitor-timeout-dc"
        index = "dc" if on_battery else "ac"
        out = _run(["powercfg", "/change", "standby-timeout-" + index, str(minutes)])
        return {"success": True, "data": "Sleep timeout set to " + str(minutes) + " min", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_monitor_timeout(minutes: int, on_battery: bool = True) -> Dict[str, Any]:
    try:
        index = "dc" if on_battery else "ac"
        _run(["powercfg", "/change", "monitor-timeout-" + index, str(minutes)])
        return {"success": True, "data": "Monitor timeout set to " + str(minutes) + " min", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_hibernate_timeout(minutes: int, on_battery: bool = True) -> Dict[str, Any]:
    try:
        index = "dc" if on_battery else "ac"
        _run(["powercfg", "/change", "hibernate-timeout-" + index, str(minutes)])
        return {"success": True, "data": "Hibernate timeout set to " + str(minutes) + " min", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_power_plan(name: str, clone_guid: str = "381b4222-f694-41f0-9685-ff5bb260df2e") -> Dict[str, Any]:
    try:
        out = _run(["powercfg", "/duplicatescheme", clone_guid])
        m = re.search(r"GUID: ([0-9a-f\-]+)", out, re.IGNORECASE)
        if not m:
            return {"success": False, "data": None, "error": "Could not extract new GUID: " + out}
        new_guid = m.group(1).strip()
        _run(["powercfg", "/changename", new_guid, name])
        return {"success": True, "data": {"guid": new_guid, "name": name}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def delete_power_plan(plan_guid: str) -> Dict[str, Any]:
    try:
        _run(["powercfg", "/delete", plan_guid])
        return {"success": True, "data": "Plan deleted: " + plan_guid, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def export_power_plan(plan_guid: str, output_path: str) -> Dict[str, Any]:
    try:
        _run(["powercfg", "/export", output_path, plan_guid])
        import os
        exists = os.path.isfile(output_path)
        return {"success": exists, "data": {"path": output_path, "exported": exists}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def import_power_plan(file_path: str) -> Dict[str, Any]:
    try:
        out = _run(["powercfg", "/import", file_path])
        m = re.search(r"GUID: ([0-9a-f\-]+)", out, re.IGNORECASE)
        guid = m.group(1).strip() if m else None
        return {"success": True, "data": {"guid": guid, "output": out}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_battery_info() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_Battery | Select-Object Name,BatteryStatus,EstimatedChargeRemaining,EstimatedRunTime,Status | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def generate_battery_report(output_path: str = "C:\\battery_report.html") -> Dict[str, Any]:
    try:
        _run(["powercfg", "/batteryreport", "/output", output_path])
        import os
        exists = os.path.isfile(output_path)
        return {"success": exists, "data": {"path": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def generate_energy_report(output_path: str = "C:\\energy_report.html") -> Dict[str, Any]:
    try:
        _run(["powercfg", "/energy", "/output", output_path, "/duration", "10"])
        import os
        exists = os.path.isfile(output_path)
        return {"success": exists, "data": {"path": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_power_settings_summary() -> Dict[str, Any]:
    try:
        out = _run(["powercfg", "/query", "SCHEME_CURRENT"])
        lines = out.splitlines()
        return {"success": True, "data": {"lines": len(lines), "raw_preview": "\n".join(lines[:20])}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
