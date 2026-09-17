"""
toolkit_30_system_tray.py
Control Windows system tray: enumerate tray icons, show balloon notifications,
interact with the notification area via PowerShell and Win32 APIs.
"""
from __future__ import annotations
import ctypes
import ctypes.wintypes
import subprocess
import os
from typing import Any, Dict, List

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=20
    )
    return result.stdout.strip()

def show_balloon_notification(title: str, message: str, duration_ms: int = 5000, icon_type: str = "info") -> Dict[str, Any]:
    """Show a Windows balloon notification (legacy tray tooltip style)."""
    try:
        icon_map = {"info": 1, "warning": 2, "error": 3, "none": 0}
        nif_icon = icon_map.get(icon_type.lower(), 1)
        script = '''
Add-Type -AssemblyName System.Windows.Forms
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.BalloonTipTitle = "''' + title + '''"
$notify.BalloonTipText = "''' + message + '''"
$notify.BalloonTipIcon = "''' + icon_type.capitalize() + '''"
$notify.Visible = $true
$notify.ShowBalloonTip(''' + str(duration_ms) + ''')
Start-Sleep -Milliseconds ''' + str(duration_ms + 500) + '''
$notify.Dispose()
"OK"
'''
        out = _run_ps(script)
        return {"success": True, "data": "Notification shown", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def show_toast_notification(title: str, message: str) -> Dict[str, Any]:
    """Show a Windows 10/11 toast notification via PowerShell."""
    try:
        script = '''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
$elements = $xml.GetElementsByTagName("text")
$elements[0].InnerText = "''' + title + '''"
$elements[1].InnerText = "''' + message + '''"
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$appId = "ScreenAgent"
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
"OK"
'''
        out = _run_ps(script)
        return {"success": True, "data": "Toast notification sent", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def play_notification_sound(sound: str = "asterisk") -> Dict[str, Any]:
    """Play a Windows notification sound. sounds: asterisk, hand, question, beep"""
    try:
        import winsound
        sounds = {
            "asterisk": winsound.MB_ICONASTERISK,
            "hand": winsound.MB_ICONHAND,
            "question": winsound.MB_ICONQUESTION,
            "exclamation": winsound.MB_ICONEXCLAMATION,
            "ok": winsound.MB_OK,
            "beep": None
        }
        flag = sounds.get(sound.lower(), winsound.MB_ICONASTERISK)
        if flag is None:
            winsound.Beep(1000, 300)
        else:
            winsound.MessageBeep(flag)
        return {"success": True, "data": "Played: " + sound, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_notification_area_icons() -> Dict[str, Any]:
    """List items visible in the system notification area via PowerShell."""
    try:
        import json
        out = _run_ps("Get-Process | Where-Object {$_.MainWindowTitle -ne '' -or $_.Name -in @('explorer','chrome','firefox')} | Select-Object Id,Name,CPU | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_do_not_disturb(enabled: bool = True) -> Dict[str, Any]:
    """Enable or disable Focus Assist (Do Not Disturb) via registry."""
    try:
        key = "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\Store\\DefaultAccount\\Current\\default$windows.data.notifications.quiethours.userprefs\\windows.data.notifications.quiethours.userprefs"
        if enabled:
            script = '''
$path = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings"
Set-ItemProperty -Path $path -Name "NOC_GLOBAL_SETTING_ALLOW_TOASTS_ABOVE_LOCK" -Value 0 -Type DWORD -Force
Set-ItemProperty -Path $path -Name "NOC_GLOBAL_SETTING_TOASTS_ENABLED" -Value 0 -Type DWORD -Force
"OK"
'''
        else:
            script = '''
$path = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings"
Set-ItemProperty -Path $path -Name "NOC_GLOBAL_SETTING_TOASTS_ENABLED" -Value 1 -Type DWORD -Force
"OK"
'''
        out = _run_ps(script)
        return {"success": True, "data": {"do_not_disturb": enabled}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_action_center_count() -> Dict[str, Any]:
    """Get count of unread notifications in Action Center (approx via WMI)."""
    try:
        out = _run_ps("(Get-WinEvent -LogName 'Microsoft-Windows-Shell-NotificationCenter/Operational' -MaxEvents 10 -ErrorAction SilentlyContinue).Count")
        count = int(out.strip()) if out.strip().isdigit() else 0
        return {"success": True, "data": {"recent_notifications": count}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def open_action_center() -> Dict[str, Any]:
    try:
        subprocess.Popen(["explorer", "ms-actioncenter:"])
        return {"success": True, "data": "Action Center opened", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def open_notification_settings() -> Dict[str, Any]:
    try:
        subprocess.Popen(["explorer", "ms-settings:notifications"])
        return {"success": True, "data": "Notification settings opened", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def message_box(title: str, message: str, style: int = 0) -> Dict[str, Any]:
    """Show a Win32 message box. style: 0=OK, 1=OK/Cancel, 4=Yes/No, etc."""
    try:
        result = user32.MessageBoxW(0, message, title, style)
        labels = {1: "OK", 2: "Cancel", 6: "Yes", 7: "No"}
        return {"success": True, "data": {"return_code": result, "button": labels.get(result, str(result))}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def input_box(prompt: str, title: str = "Input") -> Dict[str, Any]:
    """Show a PowerShell input dialog."""
    try:
        script = '''
Add-Type -AssemblyName Microsoft.VisualBasic
$result = [Microsoft.VisualBasic.Interaction]::InputBox("''' + prompt + '''", "''' + title + '''", "")
$result
'''
        out = _run_ps(script)
        return {"success": True, "data": out.strip(), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_lock_screen_status() -> Dict[str, Any]:
    try:
        import json
        out = _run_ps("Get-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Authentication\\LogonUI' -ErrorAction SilentlyContinue | Select-Object LastLoggedOnUser,LockedOn | ConvertTo-Json")
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def lock_workstation() -> Dict[str, Any]:
    try:
        result = user32.LockWorkStation()
        return {"success": bool(result), "data": "Workstation locked", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_screen_saver_info() -> Dict[str, Any]:
    try:
        import json
        out = _run_ps("Get-ItemProperty -Path 'HKCU:\\Control Panel\\Desktop' | Select-Object ScreenSaveActive,ScreenSaveTimeOut,SCRNSAVE.EXE | ConvertTo-Json")
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
