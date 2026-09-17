"""
toolkit_65_remote_desktop.py
Remote Desktop (RDP) management: list RDP sessions, connect to remote hosts,
manage RDP settings, check RDP status, and configure firewall for RDP.
"""
from __future__ import annotations
import subprocess
import json
import os
from typing import Any, Dict, List

def _run_ps(script: str, timeout: int = 20) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip()

def _run(cmd: list, timeout: int = 15) -> tuple:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.stdout.strip(), result.returncode

def list_rdp_sessions() -> Dict[str, Any]:
    """List active RDP/console sessions on this machine."""
    try:
        out, code = _run(["qwinsta"], timeout=10)
        sessions = []
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 3:
                sessions.append({"session": parts[0], "user": parts[1] if len(parts) > 1 else "", "state": parts[3] if len(parts) > 3 else ""})
        return {"success": True, "data": {"count": len(sessions), "sessions": sessions}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def connect_rdp(host: str, username: str = "", width: int = 1920, height: int = 1080, fullscreen: bool = False) -> Dict[str, Any]:
    """Launch mstsc.exe to connect to a remote host."""
    try:
        args = ["mstsc", "/v:" + host]
        if width and height:
            args += ["/w:" + str(width), "/h:" + str(height)]
        if fullscreen:
            args.append("/f")
        if username:
            args += ["/u:" + username]
        proc = subprocess.Popen(args)
        return {"success": True, "data": {"pid": proc.pid, "host": host}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def is_rdp_enabled() -> Dict[str, Any]:
    try:
        script = "(Get-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server' -Name fDenyTSConnections).fDenyTSConnections"
        out = _run_ps(script)
        enabled = out.strip() == "0"
        return {"success": True, "data": {"rdp_enabled": enabled}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def enable_rdp() -> Dict[str, Any]:
    try:
        _run_ps("Set-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server' -Name fDenyTSConnections -Value 0")
        _run_ps("Enable-NetFirewallRule -DisplayGroup 'Remote Desktop'")
        return {"success": True, "data": "RDP enabled", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def disable_rdp() -> Dict[str, Any]:
    try:
        _run_ps("Set-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server' -Name fDenyTSConnections -Value 1")
        return {"success": True, "data": "RDP disabled", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_rdp_port() -> Dict[str, Any]:
    try:
        script = "(Get-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp' -Name PortNumber).PortNumber"
        out = _run_ps(script)
        return {"success": True, "data": {"port": int(out.strip()) if out.strip().isdigit() else 3389}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_rdp_port(port: int) -> Dict[str, Any]:
    try:
        _run_ps("Set-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp' -Name PortNumber -Value " + str(port))
        return {"success": True, "data": "RDP port set to " + str(port), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def disconnect_rdp_session(session_id: int) -> Dict[str, Any]:
    try:
        out, code = _run(["logoff", str(session_id)])
        return {"success": code == 0, "data": "Session " + str(session_id) + " disconnected", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_rdp_users_allowed() -> Dict[str, Any]:
    try:
        out = _run_ps('Get-LocalGroupMember -Group "Remote Desktop Users" -ErrorAction SilentlyContinue | Select-Object Name,ObjectClass | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def add_rdp_user(username: str) -> Dict[str, Any]:
    try:
        _run_ps('Add-LocalGroupMember -Group "Remote Desktop Users" -Member "' + username + '"')
        return {"success": True, "data": username + " added to Remote Desktop Users", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def remove_rdp_user(username: str) -> Dict[str, Any]:
    try:
        _run_ps('Remove-LocalGroupMember -Group "Remote Desktop Users" -Member "' + username + '"')
        return {"success": True, "data": username + " removed from Remote Desktop Users", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_rdp_session_count() -> Dict[str, Any]:
    try:
        r = list_rdp_sessions()
        if not r["success"]: return r
        active = [s for s in r["data"]["sessions"] if "Active" in s.get("state", "")]
        return {"success": True, "data": {"total": r["data"]["count"], "active": len(active)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_rdp_firewall_rule() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-NetFirewallRule -DisplayGroup 'Remote Desktop' | Select-Object DisplayName,Enabled | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_remote_registry_value(host: str, key_path: str, value_name: str) -> Dict[str, Any]:
    try:
        script = 'Invoke-Command -ComputerName "' + host + '" -ScriptBlock { (Get-ItemProperty -Path "' + key_path + '" -Name "' + value_name + '")."' + value_name + '" } -ErrorAction SilentlyContinue'
        out = _run_ps(script)
        return {"success": True, "data": out.strip(), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
