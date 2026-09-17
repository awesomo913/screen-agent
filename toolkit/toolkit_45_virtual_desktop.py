"""
toolkit_45_virtual_desktop.py
Manage Windows Virtual Desktops (Win10/11): list, create, switch,
move windows between desktops. Uses ctypes and IVirtualDesktopManager.
"""
from __future__ import annotations
import subprocess
import ctypes
import ctypes.wintypes
import json
from typing import Any, Dict, List

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=20
    )
    return result.stdout.strip()

def get_virtual_desktop_count() -> Dict[str, Any]:
    """Get count of virtual desktops via registry."""
    try:
        script = """
$key = "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\VirtualDesktops"
$count = (Get-ItemProperty -Path $key -Name "VirtualDesktopIDs" -ErrorAction SilentlyContinue).VirtualDesktopIDs
if ($count) { [math]::Floor($count.Length / 16) } else { 1 }
"""
        out = _run_ps(script)
        count = int(out.strip()) if out.strip().isdigit() else 1
        return {"success": True, "data": {"count": count}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_virtual_desktop() -> Dict[str, Any]:
    """Create a new virtual desktop by sending hotkey Ctrl+Win+D."""
    try:
        script = """
Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
public class Input {
    [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, int dwFlags, int dwExtraInfo);
    public const int KEYEVENTF_KEYUP = 2;
    public const byte VK_LWIN = 0x5B;
    public const byte VK_CONTROL = 0x11;
    public const byte VK_D = 0x44;
}
"@
[Input]::keybd_event([Input]::VK_CONTROL, 0, 0, 0)
[Input]::keybd_event([Input]::VK_LWIN, 0, 0, 0)
[Input]::keybd_event([Input]::VK_D, 0, 0, 0)
Start-Sleep -Milliseconds 100
[Input]::keybd_event([Input]::VK_D, 0, [Input]::KEYEVENTF_KEYUP, 0)
[Input]::keybd_event([Input]::VK_LWIN, 0, [Input]::KEYEVENTF_KEYUP, 0)
[Input]::keybd_event([Input]::VK_CONTROL, 0, [Input]::KEYEVENTF_KEYUP, 0)
"OK"
"""
        out = _run_ps(script)
        return {"success": True, "data": "New virtual desktop created", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def close_current_virtual_desktop() -> Dict[str, Any]:
    """Close current virtual desktop with Ctrl+Win+F4."""
    try:
        script = """
Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
public class Input2 {
    [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, int dwFlags, int dwExtraInfo);
    public const int KEYEVENTF_KEYUP = 2;
    public const byte VK_LWIN = 0x5B;
    public const byte VK_CONTROL = 0x11;
    public const byte VK_F4 = 0x73;
}
"@
[Input2]::keybd_event([Input2]::VK_CONTROL, 0, 0, 0)
[Input2]::keybd_event([Input2]::VK_LWIN, 0, 0, 0)
[Input2]::keybd_event([Input2]::VK_F4, 0, 0, 0)
Start-Sleep -Milliseconds 100
[Input2]::keybd_event([Input2]::VK_F4, 0, [Input2]::KEYEVENTF_KEYUP, 0)
[Input2]::keybd_event([Input2]::VK_LWIN, 0, [Input2]::KEYEVENTF_KEYUP, 0)
[Input2]::keybd_event([Input2]::VK_CONTROL, 0, [Input2]::KEYEVENTF_KEYUP, 0)
"OK"
"""
        out = _run_ps(script)
        return {"success": True, "data": "Current virtual desktop closed", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def switch_to_next_desktop() -> Dict[str, Any]:
    """Switch to next virtual desktop with Ctrl+Win+Right."""
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "win", "right")
        return {"success": True, "data": "Switched to next desktop", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def switch_to_prev_desktop() -> Dict[str, Any]:
    """Switch to previous virtual desktop with Ctrl+Win+Left."""
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "win", "left")
        return {"success": True, "data": "Switched to previous desktop", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def open_task_view() -> Dict[str, Any]:
    """Open Task View (Win+Tab)."""
    try:
        import pyautogui
        pyautogui.hotkey("win", "tab")
        return {"success": True, "data": "Task View opened", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_current_window_count() -> Dict[str, Any]:
    try:
        out = _run_ps("(Get-Process | Where-Object {$_.MainWindowTitle -ne ''}).Count")
        count = int(out.strip()) if out.strip().isdigit() else 0
        return {"success": True, "data": count, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def move_window_to_new_desktop(hwnd: int) -> Dict[str, Any]:
    """Create new desktop and move specified window to it (uses VDM COM)."""
    try:
        CLSID_VirtualDesktopManager = "{AA509086-5CA9-4C25-8F95-589D3C07B48A}"
        IID_IVirtualDesktopManager = "{A5CD92FF-29BE-454C-8D04-D82879FB3F1B}"
        VDM = ctypes.windll.ole32
        vdm_ptr = ctypes.c_void_p()
        hr = ctypes.windll.ole32.CoCreateInstance(
            ctypes.byref(ctypes.create_string_buffer(CLSID_VirtualDesktopManager.encode())),
            None, 0x1,
            ctypes.byref(ctypes.create_string_buffer(IID_IVirtualDesktopManager.encode())),
            ctypes.byref(vdm_ptr)
        )
        return {"success": False, "data": None, "error": "VirtualDesktopManager COM requires manual implementation; use switch hotkeys instead"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def show_all_windows_on_desktop() -> Dict[str, Any]:
    """Show all windows on current virtual desktop via Task View."""
    try:
        out = _run_ps("Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | Select-Object Id,ProcessName,MainWindowTitle | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def snap_window_left(hwnd: int) -> Dict[str, Any]:
    """Snap window to left half (Win+Left)."""
    try:
        user32 = ctypes.windll.user32
        user32.SetForegroundWindow(hwnd)
        import pyautogui
        pyautogui.hotkey("win", "left")
        return {"success": True, "data": "Window snapped left", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def snap_window_right(hwnd: int) -> Dict[str, Any]:
    """Snap window to right half (Win+Right)."""
    try:
        user32 = ctypes.windll.user32
        user32.SetForegroundWindow(hwnd)
        import pyautogui
        pyautogui.hotkey("win", "right")
        return {"success": True, "data": "Window snapped right", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def snap_window_top_left(hwnd: int) -> Dict[str, Any]:
    try:
        user32 = ctypes.windll.user32
        user32.SetForegroundWindow(hwnd)
        import pyautogui
        pyautogui.hotkey("win", "left")
        import time; time.sleep(0.2)
        pyautogui.hotkey("win", "up")
        return {"success": True, "data": "Window snapped top-left", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def tile_windows_side_by_side(hwnd1: int, hwnd2: int) -> Dict[str, Any]:
    """Tile two windows side by side."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        half = screen_w // 2
        user32.MoveWindow(hwnd1, 0, 0, half, screen_h, True)
        user32.MoveWindow(hwnd2, half, 0, half, screen_h, True)
        user32.SetForegroundWindow(hwnd1)
        return {"success": True, "data": {"screen_w": screen_w, "screen_h": screen_h}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_screen_resolution() -> Dict[str, Any]:
    try:
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        return {"success": True, "data": {"width": w, "height": h}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
