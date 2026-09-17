"""
toolkit_67_windows_notifications.py
Send modern Windows 10/11 toast notifications, manage notification history,
and control notification settings for apps. Uses Windows Runtime APIs via PowerShell.
"""
from __future__ import annotations
import subprocess
import json
import os
from typing import Any, Dict, List

def _run_ps(script: str, timeout: int = 15) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip()

def send_toast(title: str, message: str, app_id: str = "ScreenAgent") -> Dict[str, Any]:
    """Send a Windows 10/11 toast notification."""
    try:
        script = """
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
$elements = $xml.GetElementsByTagName("text")
$elements[0].InnerText = '""" + title.replace("'", "") + """'
$elements[1].InnerText = '""" + message.replace("'", "") + """'
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('""" + app_id + """').Show($toast)
'OK'
"""
        out = _run_ps(script)
        return {"success": True, "data": {"sent": True, "title": title}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def send_toast_with_image(title: str, message: str, image_path: str, app_id: str = "ScreenAgent") -> Dict[str, Any]:
    """Send a toast notification with an inline image."""
    try:
        script = """
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastTemplateType]::ToastImageAndText02
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
$elements = $xml.GetElementsByTagName("text")
$elements[0].InnerText = '""" + title.replace("'", "") + """'
$elements[1].InnerText = '""" + message.replace("'", "") + """'
$imgElements = $xml.GetElementsByTagName("image")
$imgElements[0].SetAttribute("src", "file:///""" + image_path.replace("\\", "/") + """")
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('""" + app_id + """').Show($toast)
'OK'
"""
        out = _run_ps(script)
        return {"success": True, "data": {"sent": True}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def send_scheduled_toast(title: str, message: str, delay_seconds: int = 60) -> Dict[str, Any]:
    """Schedule a toast notification to appear after a delay."""
    try:
        script = """
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
$elements = $xml.GetElementsByTagName("text")
$elements[0].InnerText = '""" + title.replace("'", "") + """'
$elements[1].InnerText = '""" + message.replace("'", "") + """'
$deliveryTime = [DateTimeOffset]::Now.AddSeconds(""" + str(delay_seconds) + """)
$toast = [Windows.UI.Notifications.ScheduledToastNotification]::new($xml, $deliveryTime)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('ScreenAgent').AddToSchedule($toast)
'OK'
"""
        out = _run_ps(script)
        return {"success": True, "data": {"scheduled_in_seconds": delay_seconds}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_notification_settings() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings' -ErrorAction SilentlyContinue | ConvertTo-Json")
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_quiet_hours(enabled: bool = True) -> Dict[str, Any]:
    try:
        script = """
$path = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings"
if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
Set-ItemProperty -Path $path -Name "NOC_GLOBAL_SETTING_TOASTS_ENABLED" -Value """ + ("0" if enabled else "1") + """ -Type DWORD -Force
'OK'
"""
        _run_ps(script)
        return {"success": True, "data": {"quiet_hours": enabled}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_app_notification_settings() -> Dict[str, Any]:
    try:
        script = """
$path = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings"
$apps = Get-ChildItem -Path $path -ErrorAction SilentlyContinue | ForEach-Object {
    $name = $_.PSChildName
    $enabled = (Get-ItemProperty -Path $_.PSPath -Name "Enabled" -ErrorAction SilentlyContinue).Enabled
    @{App=$name; Enabled=$enabled}
}
$apps | ConvertTo-Json -Depth 3
"""
        out = _run_ps(script)
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def disable_app_notifications(app_id: str) -> Dict[str, Any]:
    try:
        script = """
$path = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings\\""" + app_id + """"
if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
Set-ItemProperty -Path $path -Name "Enabled" -Value 0 -Type DWORD -Force
'OK'
"""
        _run_ps(script)
        return {"success": True, "data": "Notifications disabled for: " + app_id, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def enable_app_notifications(app_id: str) -> Dict[str, Any]:
    try:
        script = """
$path = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings\\""" + app_id + """"
if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
Set-ItemProperty -Path $path -Name "Enabled" -Value 1 -Type DWORD -Force
'OK'
"""
        _run_ps(script)
        return {"success": True, "data": "Notifications enabled for: " + app_id, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def send_balloon_tip(title: str, message: str, icon: str = "info", duration_ms: int = 5000) -> Dict[str, Any]:
    """Send legacy balloon tip notification from system tray."""
    try:
        icon_map = {"info": "Information", "warning": "Warning", "error": "Error", "none": "None"}
        icon_str = icon_map.get(icon.lower(), "Information")
        script = """
Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.BalloonTipTitle = '""" + title.replace("'", "") + """'
$n.BalloonTipText = '""" + message.replace("'", "") + """'
$n.BalloonTipIcon = '""" + icon_str + """'
$n.ShowBalloonTip(""" + str(duration_ms) + """)
Start-Sleep -Milliseconds """ + str(duration_ms + 500) + """
$n.Dispose()
'OK'
"""
        out = _run_ps(script, timeout=duration_ms // 1000 + 5)
        return {"success": True, "data": "Balloon tip shown", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_focus_assist_status() -> Dict[str, Any]:
    try:
        script = "(Get-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\Store\\Cache\\DefaultAccount\\$$windows.data.notifications.quietmodesettings\\Current\\Data' -ErrorAction SilentlyContinue)"
        out = _run_ps(script)
        return {"success": True, "data": {"raw": out[:200]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
