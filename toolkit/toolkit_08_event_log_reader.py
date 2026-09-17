"""
event_log_reader.py - Screen Agent Toolkit Module

Read, search, filter, and analyze Windows Event Logs.
Uses PowerShell and pywin32/winevent. No external deps required.
"""
from __future__ import annotations
import json, os, re, subprocess
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

_EVENT_LOGS = ["System","Application","Security","Setup","ForwardedEvents"]
_LEVEL_MAP = {0:"Info",1:"Critical",2:"Error",3:"Warning",4:"Info",5:"Verbose"}

def _ps_get_events(log_name: str, max_events: int, level: Optional[int],
                   hours: Optional[int], event_id: Optional[int],
                   source: Optional[str], keyword: Optional[str]) -> str:
    filters = [f"LogName='{log_name}'"]
    if level is not None: filters.append(f"Level={level}")
    if event_id is not None: filters.append(f"Id={event_id}")
    if hours is not None:
        start = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
        filters.append(f"StartTime='{start}'")
    if source: filters.append(f"ProviderName='{source}'")
    filter_hash = "@{" + "; ".join(filters) + "}"
    where_clause = f"| Where-Object {{ $_.Message -like '*{keyword}*' }}" if keyword else ""
    return f"""
$events = Get-WinEvent -FilterHashtable {filter_hash} -MaxEvents {max_events} -ErrorAction SilentlyContinue
{where_clause}
$events | Select-Object TimeCreated, Id, LevelDisplayName, ProviderName, Message |
ConvertTo-Json -Depth 2
"""

def list_event_logs() -> Dict[str, Any]:
    """List all available Windows event log names."""
    try:
        ps = "Get-WinEvent -ListLog * -ErrorAction SilentlyContinue | Select-Object LogName, RecordCount, IsEnabled, LogType | ConvertTo-Json -Depth 2"
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            if isinstance(data, dict): data = [data]
            return {"success": True, "data": data, "error": None}
        return {"success": True, "data": [{"LogName":l} for l in _EVENT_LOGS], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_recent_events(log_name: str = "System", max_events: int = 50,
                       hours: int = 24) -> Dict[str, Any]:
    """Get recent events from a Windows event log."""
    try:
        ps = _ps_get_events(log_name, max_events, None, hours, None, None, None)
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict): data = [data]
                for e in data:
                    if isinstance(e.get("TimeCreated"), dict): e["TimeCreated"] = str(e["TimeCreated"])
                    if e.get("Message"): e["Message"] = e["Message"][:500]
                return {"success": True, "data": data, "error": None}
            except Exception: pass
        return {"success": True, "data": [], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_errors(log_name: str = "System", max_events: int = 50,
               hours: int = 24) -> Dict[str, Any]:
    """Get error and critical events from a log."""
    try:
        ps = f"""
$start = (Get-Date).AddHours(-{hours})
Get-WinEvent -FilterHashtable @{{LogName='{log_name}'; Level=1,2; StartTime=$start}} -MaxEvents {max_events} -ErrorAction SilentlyContinue |
Select-Object TimeCreated, Id, LevelDisplayName, ProviderName, @{{N='Message';E={{$_.Message.Substring(0, [Math]::Min(400,$_.Message.Length))}}}} |
ConvertTo-Json -Depth 2
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict): data = [data]
                return {"success": True, "data": data, "error": None}
            except Exception: pass
        return {"success": True, "data": [], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_warnings(log_name: str = "System", max_events: int = 50,
                  hours: int = 24) -> Dict[str, Any]:
    """Get warning events from a log."""
    try:
        ps = f"""
$start = (Get-Date).AddHours(-{hours})
Get-WinEvent -FilterHashtable @{{LogName='{log_name}'; Level=3; StartTime=$start}} -MaxEvents {max_events} -ErrorAction SilentlyContinue |
Select-Object TimeCreated, Id, LevelDisplayName, ProviderName, @{{N='Message';E={{$_.Message.Substring(0, [Math]::Min(400,$_.Message.Length))}}}} |
ConvertTo-Json -Depth 2
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict): data = [data]
                return {"success": True, "data": data, "error": None}
            except Exception: pass
        return {"success": True, "data": [], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def search_events(keyword: str, log_name: str = "System",
                   max_events: int = 50, hours: int = 48) -> Dict[str, Any]:
    """Search event log messages for a keyword."""
    try:
        ps = f"""
$start = (Get-Date).AddHours(-{hours})
Get-WinEvent -FilterHashtable @{{LogName='{log_name}'; StartTime=$start}} -MaxEvents 500 -ErrorAction SilentlyContinue |
Where-Object {{$_.Message -like '*{keyword}*'}} | Select-Object -First {max_events} |
Select-Object TimeCreated, Id, LevelDisplayName, ProviderName, @{{N='Message';E={{$_.Message.Substring(0, [Math]::Min(500,$_.Message.Length))}}}} |
ConvertTo-Json -Depth 2
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict): data = [data]
                return {"success": True, "data": data, "error": None}
            except Exception: pass
        return {"success": True, "data": [], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_event_by_id(event_id: int, log_name: str = "System",
                     max_events: int = 20, hours: int = 72) -> Dict[str, Any]:
    """Get events matching a specific Event ID."""
    try:
        ps = f"""
$start = (Get-Date).AddHours(-{hours})
Get-WinEvent -FilterHashtable @{{LogName='{log_name}'; Id={event_id}; StartTime=$start}} -MaxEvents {max_events} -ErrorAction SilentlyContinue |
Select-Object TimeCreated, Id, LevelDisplayName, ProviderName, @{{N='Message';E={{$_.Message.Substring(0, [Math]::Min(500,$_.Message.Length))}}}} |
ConvertTo-Json -Depth 2
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict): data = [data]
                return {"success": True, "data": data, "error": None}
            except Exception: pass
        return {"success": True, "data": [], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_system_crashes(hours: int = 168) -> Dict[str, Any]:
    """Get system crash/BSOD events (Event ID 41, 1001, 6008)."""
    try:
        crash_ids = [41, 1001, 6008]
        all_events = []
        for eid in crash_ids:
            r = get_event_by_id(eid, "System", max_events=20, hours=hours)
            if r["success"] and r["data"]: all_events.extend(r["data"])
        all_events.sort(key=lambda x: str(x.get("TimeCreated","")), reverse=True)
        return {"success": True, "data": all_events, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_application_crashes(hours: int = 168) -> Dict[str, Any]:
    """Get application crash events from Application log."""
    try:
        r = get_event_by_id(1000, "Application", max_events=30, hours=hours)
        return r
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_security_events(hours: int = 24, max_events: int = 50) -> Dict[str, Any]:
    """Get security audit events (logon failures, policy changes, etc.)."""
    try:
        ps = f"""
$start = (Get-Date).AddHours(-{hours})
Get-WinEvent -FilterHashtable @{{LogName='Security'; StartTime=$start; Id=4625,4648,4720,4728,4756,4732}} -MaxEvents {max_events} -ErrorAction SilentlyContinue |
Select-Object TimeCreated, Id, LevelDisplayName, @{{N='EventType';E={{switch($_.Id){{4625{{'Failed Logon'}}4648{{'Explicit Logon'}}4720{{'User Created'}}4728{{'Group Member Added'}}default{{'Security Event'}}}}}}}} ,@{{N='Message';E={{$_.Message.Substring(0,[Math]::Min(400,$_.Message.Length))}}}} |
ConvertTo-Json -Depth 2
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict): data = [data]
                return {"success": True, "data": data, "error": None}
            except Exception: pass
        return {"success": True, "data": [], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_hardware_events(hours: int = 72) -> Dict[str, Any]:
    """Get hardware error events from System log."""
    try:
        r = search_events("hardware", "System", 30, hours)
        return r
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_log_statistics(log_name: str = "System", hours: int = 24) -> Dict[str, Any]:
    """Get event count statistics by level for a log."""
    try:
        ps = f"""
$start = (Get-Date).AddHours(-{hours})
$events = Get-WinEvent -FilterHashtable @{{LogName='{log_name}'; StartTime=$start}} -MaxEvents 5000 -ErrorAction SilentlyContinue
$stats = $events | Group-Object LevelDisplayName | Select-Object Name, Count
$stats | ConvertTo-Json -Depth 2
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict): data = [data]
                stats = {d.get("Name","?"):d.get("Count",0) for d in data}
                return {"success": True, "data": {"log":log_name,"hours":hours,"counts":stats}, "error": None}
            except Exception: pass
        return {"success": True, "data": {"log":log_name,"hours":hours,"counts":{}}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def export_events(log_name: str, output_path: str, hours: int = 24,
                   max_events: int = 500) -> Dict[str, Any]:
    """Export events from a log to a JSON file."""
    try:
        r = get_recent_events(log_name, max_events, hours)
        if not r["success"]: return r
        from pathlib import Path
        out = Path(output_path); out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(r["data"], indent=2, default=str), encoding="utf-8")
        return {"success": True, "data": {"path":str(out),"count":len(r["data"])}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clear_event_log(log_name: str) -> Dict[str, Any]:
    """Clear all events from a Windows event log (requires admin)."""
    try:
        ps = f"Clear-EventLog -LogName '{log_name}' -ErrorAction Stop"
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            return {"success": True, "data": {"cleared":log_name}, "error": None}
        return {"success": False, "data": None, "error": r.stderr.strip()}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_startup_events(hours: int = 168) -> Dict[str, Any]:
    """Get Windows startup and shutdown events."""
    try:
        # 6005=started, 6006=stopped, 6008=unexpected shutdown, 6013=uptime
        all_events = []
        for eid in [6005, 6006, 6008]:
            r = get_event_by_id(eid, "System", 10, hours)
            if r["success"]: all_events.extend(r["data"])
        all_events.sort(key=lambda x: str(x.get("TimeCreated","")), reverse=True)
        return {"success": True, "data": all_events, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_driver_errors(hours: int = 72) -> Dict[str, Any]:
    """Find driver-related errors in System log."""
    try:
        ps = f"""
$start = (Get-Date).AddHours(-{hours})
Get-WinEvent -FilterHashtable @{{LogName='System'; Level=1,2; StartTime=$start}} -MaxEvents 100 -ErrorAction SilentlyContinue |
Where-Object {{$_.ProviderName -like '*driver*' -or $_.Message -like '*driver*' -or $_.ProviderName -like '*disk*' -or $_.ProviderName -like '*nvlddmkm*'}} |
Select-Object TimeCreated, Id, LevelDisplayName, ProviderName, @{{N='Message';E={{$_.Message.Substring(0,[Math]::Min(400,$_.Message.Length))}}}} |
ConvertTo-Json -Depth 2
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict): data = [data]
                return {"success": True, "data": data, "error": None}
            except Exception: pass
        return {"success": True, "data": [], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
