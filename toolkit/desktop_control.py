"""
desktop_control.py - Windows desktop environment manipulation.

Wallpaper, dark/light mode, taskbar position/auto-hide, desktop icon
visibility.  Uses ctypes (user32, kernel32), winreg, and PowerShell.
Zero third-party dependencies.
"""

import ctypes
import ctypes.wintypes
import os
import struct
import subprocess
import time
import winreg
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data: Any = None, message: str = "OK") -> Dict[str, Any]:
    return {"success": True, "data": data, "error": None, "message": message}


def _err(error: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "error": error, "message": error}


def _ps(cmd: str, timeout: int = 15) -> str:
    """Run a PowerShell command and return stdout."""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    if r.returncode != 0 and r.stderr.strip():
        raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout.strip()


# ---------------------------------------------------------------------------
# Wallpaper (user32.dll SystemParametersInfoW)
# ---------------------------------------------------------------------------

SPI_SETDESKWALLPAPER = 0x0014
SPI_GETDESKWALLPAPER = 0x0073
SPIF_UPDATEINIFILE = 0x0001
SPIF_SENDWININICHANGE = 0x0002


def set_wallpaper(image_path: str) -> Dict[str, Any]:
    """Set the desktop wallpaper. Persists across reboots."""
    try:
        path = os.path.abspath(image_path)
        if not os.path.isfile(path):
            return _err(f"File not found: {path}")
        user32 = ctypes.windll.user32
        user32.SystemParametersInfoW.argtypes = [
            ctypes.c_uint, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint,
        ]
        user32.SystemParametersInfoW.restype = ctypes.wintypes.BOOL
        result = user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, path,
            SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE,
        )
        if result:
            return _ok({"path": path}, f"Wallpaper set to {path}")
        return _err("SystemParametersInfoW returned False")
    except Exception as e:
        return _err(str(e))


def get_wallpaper() -> Dict[str, Any]:
    """Get the current desktop wallpaper path."""
    try:
        buf = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETDESKWALLPAPER, len(buf), buf, 0,
        )
        return _ok({"path": buf.value}, f"Current wallpaper: {buf.value}")
    except Exception as e:
        return _err(str(e))


def set_wallpaper_style(style: str) -> Dict[str, Any]:
    """Set wallpaper display style: fill, fit, stretch, tile, center, span."""
    styles = {
        "fill": ("10", "0"), "fit": ("6", "0"), "stretch": ("2", "0"),
        "tile": ("0", "1"), "center": ("0", "0"), "span": ("22", "0"),
    }
    s = style.lower()
    if s not in styles:
        return _err(f"Unknown style '{style}'. Use: {list(styles.keys())}")
    try:
        wp_style, tile_wp = styles[s]
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, wp_style)
        winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile_wp)
        winreg.CloseKey(key)
        return _ok({"style": s}, f"Wallpaper style set to {s}")
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Dark / Light Mode (registry + explorer restart)
# ---------------------------------------------------------------------------

_THEME_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"


def get_theme_mode() -> Dict[str, Any]:
    """Get the current Windows theme mode (dark or light)."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _THEME_KEY)
        apps, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        system, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
        winreg.CloseKey(key)
        mode = "light" if apps == 1 else "dark"
        return _ok({"mode": mode, "apps_light": bool(apps),
                     "system_light": bool(system)},
                    f"Current theme: {mode}")
    except Exception as e:
        return _err(str(e))


def set_dark_mode(enabled: bool = True) -> Dict[str, Any]:
    """Toggle Windows dark mode on (True) or off (False)."""
    try:
        val = 0 if enabled else 1
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _THEME_KEY, 0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, val)
        winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, val)
        winreg.CloseKey(key)
        mode = "dark" if enabled else "light"
        # Broadcast theme change to open windows
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0,
            "ImmersiveColorSet", 0x0002, 1000, ctypes.byref(ctypes.c_long()),
        )
        return _ok({"mode": mode}, f"Theme set to {mode} mode")
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Taskbar Position & Auto-Hide (StuckRects3 binary manipulation)
# ---------------------------------------------------------------------------

_STUCK_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StuckRects3"
_POS_MAP = {"left": 0x00, "top": 0x01, "right": 0x02, "bottom": 0x03}


def get_taskbar_info() -> Dict[str, Any]:
    """Get current taskbar position and auto-hide state."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STUCK_KEY)
        data, _ = winreg.QueryValueEx(key, "Settings")
        winreg.CloseKey(key)
        raw = bytes(data)
        pos_byte = raw[12] if len(raw) > 12 else 0x03
        hide_byte = raw[8] if len(raw) > 8 else 0x00
        pos_names = {v: k for k, v in _POS_MAP.items()}
        position = pos_names.get(pos_byte, "bottom")
        auto_hide = (hide_byte & 0x01) == 0x01
        return _ok({"position": position, "auto_hide": auto_hide},
                    f"Taskbar: {position}, auto-hide={'on' if auto_hide else 'off'}")
    except Exception as e:
        return _err(str(e))


def set_taskbar_position(position: str) -> Dict[str, Any]:
    """Move the taskbar: left, top, right, or bottom. Restarts explorer."""
    pos = position.lower()
    if pos not in _POS_MAP:
        return _err(f"Invalid position '{position}'. Use: {list(_POS_MAP.keys())}")
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _STUCK_KEY, 0, winreg.KEY_ALL_ACCESS,
        )
        data, _ = winreg.QueryValueEx(key, "Settings")
        raw = bytearray(data)
        raw[12] = _POS_MAP[pos]
        winreg.SetValueEx(key, "Settings", 0, winreg.REG_BINARY, bytes(raw))
        winreg.CloseKey(key)
        _restart_explorer()
        return _ok({"position": pos}, f"Taskbar moved to {pos}")
    except Exception as e:
        return _err(str(e))


def set_taskbar_autohide(enabled: bool = True) -> Dict[str, Any]:
    """Enable or disable taskbar auto-hide. Restarts explorer."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _STUCK_KEY, 0, winreg.KEY_ALL_ACCESS,
        )
        data, _ = winreg.QueryValueEx(key, "Settings")
        raw = bytearray(data)
        if enabled:
            raw[8] = raw[8] | 0x01
        else:
            raw[8] = raw[8] & ~0x01
        winreg.SetValueEx(key, "Settings", 0, winreg.REG_BINARY, bytes(raw))
        winreg.CloseKey(key)
        _restart_explorer()
        state = "enabled" if enabled else "disabled"
        return _ok({"auto_hide": enabled}, f"Taskbar auto-hide {state}")
    except Exception as e:
        return _err(str(e))


def _restart_explorer():
    """Restart Windows Explorer to apply shell changes."""
    subprocess.run(["taskkill", "/f", "/im", "explorer.exe"],
                   capture_output=True, timeout=5)
    subprocess.Popen(["explorer.exe"])
    time.sleep(1)


# ---------------------------------------------------------------------------
# Desktop Icons Visibility
# ---------------------------------------------------------------------------

_ADV_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"


def hide_desktop_icons() -> Dict[str, Any]:
    """Hide all desktop icons."""
    return _set_desktop_icons(hide=True)


def show_desktop_icons() -> Dict[str, Any]:
    """Show all desktop icons."""
    return _set_desktop_icons(hide=False)


def get_desktop_icons_visible() -> Dict[str, Any]:
    """Check whether desktop icons are currently visible."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _ADV_KEY)
        val, _ = winreg.QueryValueEx(key, "HideIcons")
        winreg.CloseKey(key)
        visible = val == 0
        return _ok({"visible": visible},
                    f"Desktop icons are {'visible' if visible else 'hidden'}")
    except FileNotFoundError:
        return _ok({"visible": True}, "Desktop icons are visible (default)")
    except Exception as e:
        return _err(str(e))


def _set_desktop_icons(hide: bool) -> Dict[str, Any]:
    try:
        val = 1 if hide else 0
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _ADV_KEY, 0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, "HideIcons", 0, winreg.REG_DWORD, val)
        winreg.CloseKey(key)
        # Refresh desktop
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Windows", 0x0002, 1000,
            ctypes.byref(ctypes.c_long()),
        )
        state = "hidden" if hide else "visible"
        return _ok({"visible": not hide}, f"Desktop icons {state}")
    except Exception as e:
        return _err(str(e))
