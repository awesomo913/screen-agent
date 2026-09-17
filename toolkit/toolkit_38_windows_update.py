"""
toolkit_38_windows_update.py
Check Windows Update status, list pending/installed updates,
and trigger update operations via PowerShell PSWindowsUpdate or WMI.
"""
from __future__ import annotations
import subprocess
import json
from typing import Any, Dict, List

def _run_ps(script: str, timeout: int = 60) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip()

def get_windows_update_status() -> Dict[str, Any]:
    try:
        script = """
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$result = $searcher.Search("IsInstalled=0 and Type='Software'")
@{
    PendingCount = $result.Updates.Count
} | ConvertTo-Json
"""
        out = _run_ps(script, timeout=30)
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_pending_updates() -> Dict[str, Any]:
    try:
        script = """
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$result = $searcher.Search("IsInstalled=0 and Type='Software'")
$updates = @()
foreach ($u in $result.Updates) {
    $updates += @{
        Title = $u.Title
        KB = $u.KBArticleIDs -join ','
        Severity = $u.MsrcSeverity
        Size_MB = [math]::Round($u.MaxDownloadSize / 1MB, 1)
    }
}
$updates | ConvertTo-Json -Depth 3
"""
        out = _run_ps(script, timeout=60)
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": {"count": len(data), "updates": data}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_installed_updates(max_count: int = 50) -> Dict[str, Any]:
    try:
        script = """
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$count = $searcher.GetTotalHistoryCount()
$history = $searcher.QueryHistory(0, [Math]::Min($count, """ + str(max_count) + """))
$updates = @()
foreach ($u in $history) {
    $updates += @{
        Title = $u.Title
        Date = $u.Date.ToString("yyyy-MM-dd")
        ResultCode = $u.ResultCode
    }
}
$updates | ConvertTo-Json -Depth 3
"""
        out = _run_ps(script, timeout=30)
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": {"count": len(data), "updates": data}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_installed_hotfixes() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-HotFix | Select-Object HotFixID,Description,InstalledBy,InstalledOn | Sort-Object InstalledOn -Descending | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": {"count": len(data), "hotfixes": data}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_last_update_date() -> Dict[str, Any]:
    try:
        out = _run_ps("(Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 1).InstalledOn")
        return {"success": True, "data": {"last_update": out.strip()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def search_installed_kb(kb_number: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-HotFix -Id "' + kb_number + '" -ErrorAction SilentlyContinue | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else None
        return {"success": True, "data": {"found": data is not None, "info": data}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_windows_version_info() -> Dict[str, Any]:
    try:
        out = _run_ps("[System.Environment]::OSVersion | Select-Object Platform,Version,VersionString | ConvertTo-Json")
        data1 = json.loads(out) if out else None
        out2 = _run_ps("Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion' | Select-Object ProductName,ReleaseId,CurrentBuildNumber,UBR,DisplayVersion | ConvertTo-Json")
        data2 = json.loads(out2) if out2 else None
        return {"success": True, "data": {"os_version": data1, "build_info": data2}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_windows_activation() -> Dict[str, Any]:
    try:
        script = "(Get-WmiObject SoftwareLicensingProduct | Where-Object {$_.Name -like 'Windows*' -and $_.PartialProductKey -ne $null}).LicenseStatus"
        out = _run_ps(script)
        status_map = {"1": "Licensed", "0": "Unlicensed", "2": "OOBGrace", "3": "OOTGrace", "4": "NonGenuineGrace", "5": "Notification", "6": "ExtendedGrace"}
        status_code = out.strip()
        return {"success": True, "data": {"code": status_code, "status": status_map.get(status_code, "Unknown")}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_update_service_status() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-Service -Name wuauserv | Select-Object Status,StartType | ConvertTo-Json")
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def start_update_service() -> Dict[str, Any]:
    try:
        _run_ps("Start-Service -Name wuauserv")
        return {"success": True, "data": "Windows Update service started", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def stop_update_service() -> Dict[str, Any]:
    try:
        _run_ps("Stop-Service -Name wuauserv -Force")
        return {"success": True, "data": "Windows Update service stopped", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_reboot_required() -> Dict[str, Any]:
    try:
        script = "Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired'"
        out = _run_ps(script)
        reboot = out.strip().lower() == "true"
        return {"success": True, "data": {"reboot_required": reboot}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_auto_update_settings() -> Dict[str, Any]:
    try:
        script = "Get-ItemProperty -Path 'HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU' -ErrorAction SilentlyContinue | ConvertTo-Json"
        out = _run_ps(script)
        data = json.loads(out) if out else {"note": "No group policy override found"}
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
