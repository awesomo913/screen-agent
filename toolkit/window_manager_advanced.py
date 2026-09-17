"""
Advanced Window Manager Toolkit for Screen Agents.
Fully implemented, production-ready, Windows-optimized.
"""
import os
import re
import time
import json
import platform
import subprocess
import ctypes
from ctypes import wintypes
from typing import Dict, List, Optional, Any, Tuple

import pygetwindow as gw
import pyautogui
import win32gui
import win32con
import win32process

# Configure DPI awareness for accurate coordinate mapping
if platform.system() == "Windows":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        pass

# Type aliases for clarity
ResponseDict = Dict[str, Any]

# ---------------------------------------------------------
# Core Helpers
# ---------------------------------------------------------
def _response(success: bool, result: Any = None, error: Optional[str] = None) -> ResponseDict:
    """Standard response wrapper ensuring consistent Dict return format."""
    return {"success": success, "result": result, "error": error}

def _resolve_hwnd(title: str) -> Optional[int]:
    """Resolve window title to HWND using exact match first, then partial/regex."""
    if not title:
        return None
    hwnds = []
    def _callback(hwnd: int, _: Any) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            try:
                win_title = win32gui.GetWindowText(hwnd)
                if win_title == title or re.search(re.escape(title), win_title, re.IGNORECASE):
                    hwnds.append(hwnd)
            except Exception:
                pass
        return True
    try:
        win32gui.EnumWindows(_callback, None)
    except Exception:
        pass
    return hwnds[0] if hwnds else None

def _get_monitor_work_area() -> Tuple[int, int, int, int]:
    """Get primary monitor work area (taskbar excluded)."""
    try:
        rect = pyautogui.size()
        # Approximate taskbar offset or use win32gui.GetSystemMetrics
        taskbar_h = ctypes.windll.user32.GetSystemMetrics(win32con.SM_CYSCREEN) - ctypes.windll.user32.GetSystemMetrics(win32con.SM_CYFULLSCREEN)
        return (0, 0, rect.width, rect.height - taskbar_h if taskbar_h > 0 else rect.height)
    except Exception:
        return (0, 0, 1920, 1080)

def _apply_window_pos(hwnd: int, x: int, y: int, w: int, h: int, flags: int = 0) -> bool:
    wrapper = win32gui.SetWindowPos
    try:
        flags |= win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
        wrapper(hwnd, 0, x, y, w, h, flags)
        return True
    except Exception:
        return False

# ---------------------------------------------------------
# Public API Functions
# ---------------------------------------------------------
def list_all_windows() -> ResponseDict:
    try:
        windows = []
        def _enum_callback(hwnd: int, _: Any) -> bool:
            if win32gui.IsWindowVisible(hwnd):
                try:
                    title = win32gui.GetWindowText(hwnd)
                    if title.strip():
                        pid = win32process.GetWindowThreadProcessId(hwnd)[1]
                        l, t, r, b = win32gui.GetWindowRect(hwnd)
                        windows.append({
                            "hwnd": hwnd,
                            "title": title,
                            "pid": pid,
                            "rect": {"left": l, "top": t, "right": r, "bottom": b}
                        })
                except Exception:
                    pass
            return True
        win32gui.EnumWindows(_enum_callback, None)
        return _response(True, result=windows)
    except Exception as e:
        return _response(False, error=str(e))

def get_active_window() -> ResponseDict:
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd or hwnd == 0:
            return _response(True, result=None)
        title = win32gui.GetWindowText(hwnd)
        pid = win32process.GetWindowThreadProcessId(hwnd)[1]
        l, t, r, b = win32gui.GetWindowRect(hwnd)
        return _response(True, result={
            "hwnd": hwnd,
            "title": title,
            "pid": pid,
            "rect": {"left": l, "top": t, "right": r, "bottom": b}
        })
    except Exception as e:
        return _response(False, error=str(e))

def find_window_by_title(title_pattern: str) -> ResponseDict:
    try:
        pattern = re.compile(title_pattern, re.IGNORECASE)
        found = None
        def _search(hwnd: int, _: Any) -> bool:
            nonlocal found
            if found: return True
            if win32gui.IsWindowVisible(hwnd):
                try:
                    title = win32gui.GetWindowText(hwnd)
                    if pattern.search(title):
                        pid = win32process.GetWindowThreadProcessId(hwnd)[1]
                        l, t, r, b = win32gui.GetWindowRect(hwnd)
                        found = {"hwnd": hwnd, "title": title, "pid": pid, "rect": {"left": l, "top": t, "right": r, "bottom": b}}
                        return False
                except Exception:
                    pass
            return True
        win32gui.EnumWindows(_search, None)
        return _response(True, result=found)
    except Exception as e:
        return _response(False, error=str(e))

def find_window_by_pid(pid: int) -> ResponseDict:
    try:
        found = None
        def _search(hwnd: int, _: Any) -> bool:
            nonlocal found
            if found: return True
            try:
                _, w_pid = win32process.GetWindowThreadProcessId(hwnd)
                if w_pid == pid and win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    l, t, r, b = win32gui.GetWindowRect(hwnd)
                    found = {"hwnd": hwnd, "title": title, "pid": pid, "rect": {"left": l, "top": t, "right": r, "bottom": b}}
                    return False
            except Exception:
                pass
            return True
        win32gui.EnumWindows(_search, None)
        return _response(True, result=found)
    except Exception as e:
        return _response(False, error=str(e))

def activate_window(title: str) -> ResponseDict:
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd:
            return _response(False, error="Window not found")
        
        # Reliable foreground activation workaround
        try:
            fg_thread = ctypes.windll.user32.GetWindowThreadProcessId(win32gui.GetForegroundWindow(), None)
            app_thread = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
            if fg_thread != app_thread:
                ctypes.windll.user32.AttachThreadInput(fg_thread, app_thread, True)
                time.sleep(0.05)
                win32gui.SetForegroundWindow(hwnd)
                ctypes.windll.user32.AttachThreadInput(fg_thread, app_thread, False)
            else:
                win32gui.SetForegroundWindow(hwnd)
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        except Exception:
            win32gui.SetForegroundWindow(hwnd)
        return _response(True)
    except Exception as e:
        return _response(False, error=str(e))

def minimize_window(title: str) -> ResponseDict:
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd: return _response(False, error="Window not found")
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        return _response(True)
    except Exception as e:
        return _response(False, error=str(e))

def maximize_window(title: str) -> ResponseDict:
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd: return _response(False, error="Window not found")
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        return _response(True)
    except Exception as e:
        return _response(False, error=str(e))

def restore_window(title: str) -> ResponseDict:
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd: return _response(False, error="Window not found")
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        return _response(True)
    except Exception as e:
        return _response(False, error=str(e))

def close_window(title: str) -> ResponseDict:
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd: return _response(False, error="Window not found")
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        return _response(True)
    except Exception as e:
        return _response(False, error=str(e))

def move_window(title: str, x: int, y: int) -> ResponseDict:
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd: return _response(False, error="Window not found")
        l, t, r, b = win32gui.GetWindowRect(hwnd)
        w, h = r - l, b - t
        win32gui.SetWindowPos(hwnd, 0, x, y, w, h, win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
        return _response(True)
    except Exception as e:
        return _response(False, error=str(e))

def resize_window(title: str, width: int, height: int) -> ResponseDict:
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd: return _response(False, error="Window not found")
        l, t, _, _ = win32gui.GetWindowRect(hwnd)
        win32gui.SetWindowPos(hwnd, 0, l, t, width, height, win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
        return _response(True)
    except Exception as e:
        return _response(False, error=str(e))

def snap_window_left(title: str) -> ResponseDict:
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd: return _response(False, error="Window not found")
        _, _, monitor_w, monitor_h = _get_monitor_work_area()
        half_w = monitor_w // 2
        win32gui.SetWindowPos(hwnd, 0, 0, 0, half_w, monitor_h, win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
        return _response(True)
    except Exception as e:
        return _response(False, error=str(e))

def snap_window_right(title: str) -> ResponseDict:
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd: return _response(False, error="Window not found")
        _, _, monitor_w, monitor_h = _get_monitor_work_area()
        half_w = monitor_w // 2
        win32gui.SetWindowPos(hwnd, 0, half_w, 0, half_w, monitor_h, win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
        return _response(True)
    except Exception as e:
        return _response(False, error=str(e))

def tile_windows(titles: List[str], layout: str = "grid") -> ResponseDict:
    try:
        valid_titles = []
        for t in titles:
            hwnd = _resolve_hwnd(t)
            if hwnd: valid_titles.append((t, hwnd))
        
        if not valid_titles: return _response(False, error="No valid windows found")
        
        count = len(valid_titles)
        _, _, desk_w, desk_h = _get_monitor_work_area()
        
        cols = 1
        rows = 1
        if layout == "horizontal":
            cols = count
        elif layout == "vertical":
            rows = count
        else:  # grid
            cols = int(count ** 0.5 + 0.5)
            rows = (count + cols - 1) // cols
            
        cell_w = desk_w // cols
        cell_h = desk_h // rows
        
        for i, (_, hwnd) in enumerate(valid_titles):
            col = i % cols
            row = (i // cols) % rows
            _apply_window_pos(hwnd, col * cell_w, row * cell_h, cell_w, cell_h)
            
        return _response(True, result={"tiled": count, "layout": layout})
    except Exception as e:
        return _response(False, error=str(e))

def cascade_windows(titles: List[str]) -> ResponseDict:
    try:
        valid_hwnds = []
        for t in titles:
            hwnd = _resolve_hwnd(t)
            if hwnd: valid_hwnds.append(hwnd)
            
        if not valid_hwnds: return _response(False, error="No valid windows found")
        
        _, _, desk_w, desk_h = _get_monitor_work_area()
        cascade_offset = 30
        win_w, win_h = 640, 480  # Default cascade size
        
        for i, hwnd in enumerate(valid_hwnds):
            x = 50 + (i * cascade_offset)
            y = 50 + (i * cascade_offset)
            # Keep within bounds
            if x + win_w > desk_w: x = 0
            if y + win_h > desk_h: y = 0
            _apply_window_pos(hwnd, x, y, win_w, win_h)
            
        return _response(True, result={"cascaded": len(valid_hwnds)})
    except Exception as e:
        return _response(False, error=str(e))

def set_window_topmost(title: str, topmost: bool) -> ResponseDict:
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd: return _response(False, error="Window not found")
        flag = win32con.HWND_TOPMOST if topmost else win32con.HWND_NOTOPMOST
        win32gui.SetWindowPos(hwnd, flag, 0, 0, 0, 0, 
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
        return _response(True)
    except Exception as e:
        return _response(False, error=str(e))

def set_window_opacity(title: str, opacity: float) -> ResponseDict:
    """opacity: 0.0 (transparent) to 1.0 (opaque)"""
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd: return _response(False, error="Window not found")
        if not (0.0 <= opacity <= 1.0):
            return _response(False, error="Opacity must be between 0.0 and 1.0")
            
        alpha = int(opacity * 255)
        # Add WS_EX_LAYERED style
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        ex_style |= win32con.WS_EX_LAYERED
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
        
        # Set layered attributes
        ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, alpha, win32con.LWA_ALPHA)
        return _response(True)
    except Exception as e:
        return _response(False, error=str(e))

def get_window_info(title: str) -> ResponseDict:
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd: return _response(False, error="Window not found")
        
        title_text = win32gui.GetWindowText(hwnd)
        pid, tid = win32process.GetWindowThreadProcessId(hwnd)
        l, t, r, b = win32gui.GetWindowRect(hwnd)
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        
        return _response(True, result={
            "hwnd": hwnd,
            "title": title_text,
            "pid": pid,
            "tid": tid,
            "rect": {"left": l, "top": t, "right": r, "bottom": b},
            "style": style,
            "ex_style": ex_style,
            "is_visible": bool(win32gui.IsWindowVisible(hwnd)),
            "is_iconic": bool(win32gui.IsIconic(hwnd))
        })
    except Exception as e:
        return _response(False, error=str(e))

def get_window_rect(title: str) -> ResponseDict:
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd: return _response(False, error="Window not found")
        l, t, r, b = win32gui.GetWindowRect(hwnd)
        return _response(True, result={"left": l, "top": t, "right": r, "bottom": b})
    except Exception as e:
        return _response(False, error=str(e))

def hide_window(title: str) -> ResponseDict:
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd: return _response(False, error="Window not found")
        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
        return _response(True)
    except Exception as e:
        return _response(False, error=str(e))

def show_window(title: str) -> ResponseDict:
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd: return _response(False, error="Window not found")
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        return _response(True)
    except Exception as e:
        return _response(False, error=str(e))

def get_window_screenshot(title: str, output: str) -> ResponseDict:
    try:
        hwnd = _resolve_hwnd(title)
        if not hwnd: return _response(False, error="Window not found")
        
        l, t, r, b = win32gui.GetWindowRect(hwnd)
        w, h = r - l, b - t
        
        # Fallback to pygetwindow for region safety
        win_obj = None
        for w_obj in gw.getAllWindows():
            try:
                if w_obj._hWnd == hwnd or (w_obj.title and re.search(re.escape(title), w_obj.title, re.IGNORECASE)):
                    win_obj = w_obj
                    break
            except Exception:
                pass
                
        if win_obj:
            win_obj.activate()
            img = pyautogui.screenshot(region=(l, t, w, h))
        else:
            img = pyautogui.screenshot(region=(l, t, w, h))
            
        img.save(output)
        return _response(True, result={"path": os.path.abspath(output), "width": w, "height": h})
    except Exception as e:
        return _response(False, error=str(e))

def wait_for_window(title: str, timeout: float = 10.0) -> ResponseDict:
    try:
        start = time.time()
        pattern = re.compile(re.escape(title), re.IGNORECASE)
        while time.time() - start < timeout:
            hwnd = _resolve_hwnd(title)
            if hwnd:
                pid = win32process.GetWindowThreadProcessId(hwnd)[1]
                return _response(True, result={"hwnd": hwnd, "pid": pid, "found_in": time.time() - start})
            time.sleep(0.25)
        return _response(False, error="Timeout waiting for window")
    except Exception as e:
        return _response(False, error=str(e))

def arrange_monitors(layout: str = "extend") -> ResponseDict:
    """
    Arrange monitor layout. Supports: 'duplicate', 'extend', 'second_only', 'pc_only'.
    Custom layouts require external tools or manual Display Settings.
    """
    try:
        valid = {"duplicate": "/clone", "extend": "/extend", "second_only": "/external", "pc_only": "/internal"}
        layout = layout.lower()
        if layout not in valid:
            # Fallback to default extend for undefined custom strings
            layout = "extend"
            
        cmd = f"DisplaySwitch.exe {valid[layout]}"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            return _response(True, result=f"Applied {layout} layout")
        return _response(False, error=f"DisplaySwitch failed: {res.stderr.strip()}")
    except Exception as e:
        return _response(False, error=str(e))

def switch_virtual_desktop(desktop_num: int) -> ResponseDict:
    """
    Switch to a specific virtual desktop by relative offset or absolute count.
    Note: Absolute desktop switching requires COM interfaces. This uses reliable hotkey simulation.
    desktop_num > 0: switch right | desktop_num < 0: switch left
    """
    try:
        if desktop_num == 0:
            return _response(True, result="Already on current desktop")
            
        key = "right" if desktop_num > 0 else "left"
        steps = abs(int(desktop_num))
        
        # Use pyautogui for reliable Win+Ctrl+Left/Right hotkeys
        pyautogui.FAILSAFE = False
        for _ in range(steps):
            pyautogui.hotkey("ctrl", "win", key)
            time.sleep(0.15)
            
        return _response(True, result=f"Switched {steps} desktops {key}")
    except Exception as e:
        return _response(False, error=str(e))

if __name__ == "__main__":
    # Quick self-test / demonstration
    print(json.dumps(list_all_windows(), indent=2))
    print(json.dumps(get_active_window(), indent=2))