"""
toolkit_29_window_inspector.py
Inspect open windows: title, position, size, state, process, z-order.
Uses pyautogui for window list, ctypes for detailed Win32 info.
"""
from __future__ import annotations
import ctypes
import ctypes.wintypes
import subprocess
import os
from typing import Any, Dict, List

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    import win32gui
    import win32con
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

user32 = ctypes.windll.user32

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=20
    )
    return result.stdout.strip()

def list_open_windows() -> Dict[str, Any]:
    try:
        import json
        out = _run_ps("Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | Select-Object Id,ProcessName,MainWindowTitle,MainWindowHandle | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_window_titles() -> Dict[str, Any]:
    try:
        import json
        out = _run_ps("Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | Select-Object -ExpandProperty MainWindowTitle | ConvertTo-Json")
        data = json.loads(out) if out else []
        if isinstance(data, list) and not data:
            data = []
        elif isinstance(data, str):
            data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_window_by_title(keyword: str) -> Dict[str, Any]:
    try:
        import json
        out = _run_ps('Get-Process | Where-Object {$_.MainWindowTitle -like "*' + keyword + '*"} | Select-Object Id,ProcessName,MainWindowTitle | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_foreground_window() -> Dict[str, Any]:
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"success": True, "data": None, "error": None}
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return {"success": True, "data": {
            "hwnd": hwnd,
            "title": title,
            "pid": pid.value,
            "rect": {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom},
            "width": rect.right - rect.left,
            "height": rect.bottom - rect.top
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_window_rect(hwnd: int) -> Dict[str, Any]:
    try:
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return {"success": True, "data": {
            "left": rect.left, "top": rect.top,
            "right": rect.right, "bottom": rect.bottom,
            "width": rect.right - rect.left,
            "height": rect.bottom - rect.top
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def move_window(hwnd: int, x: int, y: int, width: int = -1, height: int = -1) -> Dict[str, Any]:
    try:
        if width < 0 or height < 0:
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            if width < 0:
                width = rect.right - rect.left
            if height < 0:
                height = rect.bottom - rect.top
        result = user32.MoveWindow(hwnd, x, y, width, height, True)
        return {"success": bool(result), "data": {"moved_to": {"x": x, "y": y, "w": width, "h": height}}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def minimize_window(hwnd: int) -> Dict[str, Any]:
    try:
        user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        return {"success": True, "data": "Window minimized", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def maximize_window(hwnd: int) -> Dict[str, Any]:
    try:
        user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
        return {"success": True, "data": "Window maximized", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def restore_window(hwnd: int) -> Dict[str, Any]:
    try:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        return {"success": True, "data": "Window restored", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def hide_window(hwnd: int) -> Dict[str, Any]:
    try:
        user32.ShowWindow(hwnd, 0)  # SW_HIDE
        return {"success": True, "data": "Window hidden", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def show_window(hwnd: int) -> Dict[str, Any]:
    try:
        user32.ShowWindow(hwnd, 5)  # SW_SHOW
        return {"success": True, "data": "Window shown", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def bring_to_front(hwnd: int) -> Dict[str, Any]:
    try:
        user32.SetForegroundWindow(hwnd)
        return {"success": True, "data": "Window brought to front", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def close_window(hwnd: int) -> Dict[str, Any]:
    try:
        WM_CLOSE = 0x0010
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return {"success": True, "data": "Close message sent", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def is_window_visible(hwnd: int) -> Dict[str, Any]:
    try:
        visible = bool(user32.IsWindowVisible(hwnd))
        return {"success": True, "data": visible, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_window_title(hwnd: int) -> Dict[str, Any]:
    try:
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return {"success": True, "data": buf.value, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_window_title(hwnd: int, new_title: str) -> Dict[str, Any]:
    try:
        result = user32.SetWindowTextW(hwnd, new_title)
        return {"success": bool(result), "data": "Title set to: " + new_title, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_window_pid(hwnd: int) -> Dict[str, Any]:
    try:
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return {"success": True, "data": pid.value, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def count_open_windows() -> Dict[str, Any]:
    try:
        import json
        out = _run_ps("(Get-Process | Where-Object {$_.MainWindowTitle -ne ''}).Count")
        count = int(out.strip()) if out.strip().isdigit() else 0
        return {"success": True, "data": count, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
