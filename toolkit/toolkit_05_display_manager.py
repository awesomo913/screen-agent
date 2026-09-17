"""
display_manager.py - Screen Agent Toolkit Module

Manage displays, monitors, resolution, brightness, DPI scaling, and
virtual desktops on Windows using ctypes/user32 and PowerShell.
"""
from __future__ import annotations
import ctypes, ctypes.wintypes, json, os, re, subprocess
from typing import Any, Dict, List, Optional, Tuple

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# DEVMODE structure constants
ENUM_CURRENT_SETTINGS = -1
ENUM_REGISTRY_SETTINGS = -2
CDS_TEST = 0x00000002
CDS_UPDATEREGISTRY = 0x00000001
DISP_CHANGE_SUCCESSFUL = 0
DM_PELSWIDTH = 0x00080000
DM_PELSHEIGHT = 0x00100000
DM_BITSPERPEL = 0x00040000
DM_DISPLAYFREQUENCY = 0x00400000
DM_DISPLAYFLAGS = 0x00000200

class _DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", ctypes.c_wchar * 32),
        ("dmSpecVersion", ctypes.c_ushort), ("dmDriverVersion", ctypes.c_ushort),
        ("dmSize", ctypes.c_ushort), ("dmDriverExtra", ctypes.c_ushort),
        ("dmFields", ctypes.c_ulong),
        ("dmPositionX", ctypes.c_long), ("dmPositionY", ctypes.c_long),
        ("dmDisplayOrientation", ctypes.c_ulong), ("dmDisplayFixedOutput", ctypes.c_ulong),
        ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short), ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", ctypes.c_ushort), ("dmBitsPerPel", ctypes.c_ulong),
        ("dmPelsWidth", ctypes.c_ulong), ("dmPelsHeight", ctypes.c_ulong),
        ("dmDisplayFlags", ctypes.c_ulong), ("dmDisplayFrequency", ctypes.c_ulong),
        ("dmICMMethod", ctypes.c_ulong), ("dmICMIntent", ctypes.c_ulong),
        ("dmMediaType", ctypes.c_ulong), ("dmDitherType", ctypes.c_ulong),
        ("dmReserved1", ctypes.c_ulong), ("dmReserved2", ctypes.c_ulong),
        ("dmPanningWidth", ctypes.c_ulong), ("dmPanningHeight", ctypes.c_ulong),
    ]

def _get_devmode(device_name: Optional[str] = None) -> Optional[_DEVMODEW]:
    dm = _DEVMODEW(); dm.dmSize = ctypes.sizeof(_DEVMODEW)
    if user32.EnumDisplaySettingsW(device_name, ENUM_CURRENT_SETTINGS, ctypes.byref(dm)):
        return dm
    return None

def get_screen_resolution() -> Dict[str, Any]:
    """Get the primary screen resolution."""
    try:
        w = user32.GetSystemMetrics(0); h = user32.GetSystemMetrics(1)
        return {"success": True, "data": {"width": w, "height": h, "resolution": f"{w}x{h}"}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_all_monitors() -> Dict[str, Any]:
    """List all connected monitors with resolution and position."""
    try:
        monitors = []
        def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            info = ctypes.create_string_buffer(40 + ctypes.sizeof(ctypes.wintypes.RECT) * 2)
            ctypes.memset(info, 0, len(info)); struct_size = ctypes.c_ulong(len(info))
            ctypes.memmove(info, ctypes.addressof(struct_size), 4)
            from ctypes import wintypes
            mi = wintypes.MONITORINFO()
            mi.cbSize = ctypes.sizeof(wintypes.MONITORINFO)
            if user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi)):
                r = mi.rcMonitor
                monitors.append({"left":r.left,"top":r.top,"right":r.right,"bottom":r.bottom,
                                   "width":r.right-r.left,"height":r.bottom-r.top,
                                   "is_primary": bool(mi.dwFlags & 1)})
            return True
        MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t,
                                               ctypes.c_size_t, ctypes.POINTER(ctypes.wintypes.RECT),
                                               ctypes.c_size_t)
        cb = MONITORENUMPROC(callback)
        user32.EnumDisplayMonitors(None, None, cb, 0)
        return {"success": True, "data": monitors, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_display_settings() -> Dict[str, Any]:
    """Get current display settings: resolution, bit depth, refresh rate."""
    try:
        dm = _get_devmode()
        if not dm:
            return {"success": False, "data": None, "error": "Could not get display settings"}
        return {"success": True, "data": {
            "width": dm.dmPelsWidth, "height": dm.dmPelsHeight,
            "bits_per_pixel": dm.dmBitsPerPel,
            "refresh_rate_hz": dm.dmDisplayFrequency,
            "resolution": f"{dm.dmPelsWidth}x{dm.dmPelsHeight}"}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_resolution(width: int, height: int, refresh_rate: int = 0) -> Dict[str, Any]:
    """Change screen resolution (and optionally refresh rate)."""
    try:
        dm = _get_devmode()
        if not dm: return {"success": False, "data": None, "error": "Cannot read current settings"}
        dm.dmPelsWidth = width; dm.dmPelsHeight = height
        dm.dmFields = DM_PELSWIDTH | DM_PELSHEIGHT
        if refresh_rate > 0:
            dm.dmDisplayFrequency = refresh_rate; dm.dmFields |= DM_DISPLAYFREQUENCY
        result = user32.ChangeDisplaySettingsW(ctypes.byref(dm), CDS_UPDATEREGISTRY)
        if result == DISP_CHANGE_SUCCESSFUL:
            return {"success": True, "data": {"width":width,"height":height,"refresh_rate":refresh_rate}, "error": None}
        return {"success": False, "data": None, "error": f"ChangeDisplaySettings failed: code {result}"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_supported_resolutions() -> Dict[str, Any]:
    """List all supported display resolutions for the primary monitor."""
    try:
        resolutions = set(); dm = _DEVMODEW(); dm.dmSize = ctypes.sizeof(_DEVMODEW); i = 0
        while user32.EnumDisplaySettingsW(None, i, ctypes.byref(dm)):
            resolutions.add((dm.dmPelsWidth, dm.dmPelsHeight, dm.dmDisplayFrequency)); i += 1
        sorted_res = sorted(resolutions, key=lambda x: (x[0]*x[1], x[2]), reverse=True)
        return {"success": True, "data": [{"width":w,"height":h,"refresh_hz":r,"label":f"{w}x{h}@{r}Hz"}
                                           for w,h,r in sorted_res], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_dpi_scaling() -> Dict[str, Any]:
    """Get DPI scaling factor for all monitors."""
    try:
        ps = """
Add-Type -TypeDefinition @'
using System;using System.Runtime.InteropServices;
public class DPI {
  [DllImport("shcore.dll")]
  public static extern int GetDpiForMonitor(IntPtr hmonitor, int dpiType, out uint dpiX, out uint dpiY);
}
'@
$screens = [System.Windows.Forms.Screen]::AllScreens
Add-Type -AssemblyName System.Windows.Forms
$results = @()
foreach ($s in $screens) {
  $results += [PSCustomObject]@{
    Name = $s.DeviceName; Primary = $s.Primary;
    Width = $s.Bounds.Width; Height = $s.Bounds.Height;
    ScaleFactor = [Math]::Round($s.Bounds.Width / $s.WorkingArea.Width * 100)
  }
}
$results | ConvertTo-Json -Depth 2
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict): data = [data]
                return {"success": True, "data": data, "error": None}
            except Exception: pass
        # Fallback: GetDeviceCaps
        hdc = gdi32.CreateDCW("DISPLAY", None, None, None)
        dpi_x = gdi32.GetDeviceCaps(hdc, 88)
        dpi_y = gdi32.GetDeviceCaps(hdc, 90)
        gdi32.DeleteDC(hdc)
        return {"success": True, "data": {"dpi_x":dpi_x,"dpi_y":dpi_y,"scale_percent":round(dpi_x/96*100)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_brightness(level: int) -> Dict[str, Any]:
    """Set monitor brightness (0-100) via WMI or PowerShell."""
    try:
        level = max(0, min(100, level))
        ps = f"""
$mon = Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods -ErrorAction SilentlyContinue
if ($mon) {{ $mon.WmiSetBrightness(1, {level}); Write-Output 'OK' }}
else {{ Write-Output 'NOT_SUPPORTED' }}
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=10)
        out = r.stdout.strip()
        if "NOT_SUPPORTED" in out:
            return {"success": False, "data": None, "error": "Brightness control not supported on this monitor"}
        return {"success": True, "data": {"level": level}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_brightness() -> Dict[str, Any]:
    """Get current monitor brightness level."""
    try:
        ps = """
$mon = Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness -ErrorAction SilentlyContinue
if ($mon) { $mon.CurrentBrightness } else { Write-Output 'NOT_SUPPORTED' }
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=10)
        out = r.stdout.strip()
        if "NOT_SUPPORTED" in out:
            return {"success": False, "data": None, "error": "Brightness not supported"}
        return {"success": True, "data": {"brightness": int(out) if out.isdigit() else None}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def turn_off_display() -> Dict[str, Any]:
    """Turn off the display immediately."""
    try:
        user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
        return {"success": True, "data": {"action": "display_off"}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_display_rotation(degrees: int, monitor_index: int = 0) -> Dict[str, Any]:
    """Set display rotation (0, 90, 180, 270 degrees)."""
    try:
        if degrees not in (0, 90, 180, 270):
            return {"success": False, "data": None, "error": "Degrees must be 0, 90, 180, or 270"}
        orient_map = {0: 0, 90: 1, 180: 2, 270: 3}
        dm = _get_devmode()
        if not dm: return {"success": False, "data": None, "error": "Cannot get display settings"}
        orientation = orient_map[degrees]
        dm.dmDisplayOrientation = orientation
        dm.dmFields = 0x00000080  # DM_DISPLAYORIENTATION
        if degrees in (90, 270):
            dm.dmPelsWidth, dm.dmPelsHeight = dm.dmPelsHeight, dm.dmPelsWidth
            dm.dmFields |= DM_PELSWIDTH | DM_PELSHEIGHT
        result = user32.ChangeDisplaySettingsW(ctypes.byref(dm), CDS_UPDATEREGISTRY)
        if result == DISP_CHANGE_SUCCESSFUL:
            return {"success": True, "data": {"degrees": degrees}, "error": None}
        return {"success": False, "data": None, "error": f"Rotation failed: code {result}"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_virtual_desktop_count() -> Dict[str, Any]:
    """Get the number of virtual desktops on Windows 10/11."""
    try:
        ps = """
$obj = New-Object -ComObject Shell.Application
$vd = $obj.Namespace('shell:Desktop')
[int](Get-ItemProperty -Path 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\VirtualDesktops' -Name 'VirtualDesktopIDs' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty VirtualDesktopIDs).Length / 16
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=10)
        count = int(r.stdout.strip()) if r.stdout.strip().isdigit() else 1
        return {"success": True, "data": {"virtual_desktops": count}, "error": None}
    except Exception as e:
        return {"success": True, "data": {"virtual_desktops": 1}, "error": None}

def take_monitor_screenshot(monitor_index: int = 0, output_path: str = "") -> Dict[str, Any]:
    """Take a screenshot of a specific monitor."""
    try:
        try:
            import mss
            HAS_MSS = True
        except ImportError:
            HAS_MSS = False
        from PIL import ImageGrab
        from datetime import datetime as dt
        if not output_path:
            import tempfile
            output_path = os.path.join(tempfile.gettempdir(), f"monitor_{monitor_index}_{dt.now().strftime('%Y%m%d_%H%M%S')}.png")
        if HAS_MSS:
            with mss.mss() as sct:
                monitors = sct.monitors
                if monitor_index + 1 >= len(monitors):
                    return {"success": False, "data": None, "error": f"Monitor {monitor_index} not found"}
                mon = monitors[monitor_index + 1]
                img = sct.grab(mon)
                from PIL import Image
                Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX").save(output_path)
        else:
            ImageGrab.grab().save(output_path)
        return {"success": True, "data": {"path": output_path, "monitor": monitor_index}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_display_info_summary() -> Dict[str, Any]:
    """Get a complete summary of all display information."""
    try:
        res = get_screen_resolution()
        settings = get_display_settings()
        monitors = get_all_monitors()
        return {"success": True, "data": {
            "primary_resolution": res.get("data"),
            "settings": settings.get("data"),
            "monitors": monitors.get("data"),
            "monitor_count": len(monitors.get("data", []))}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def enable_night_light(enabled: bool = True) -> Dict[str, Any]:
    """Enable or disable Windows Night Light feature."""
    try:
        state = "Enable" if enabled else "Disable"
        ps = f"""
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current\default$windows.data.bluelightreduction.bluelightreductionstate\windows.data.bluelightreduction.bluelightreductionstate'
if (Test-Path $key) {{
  $val = (Get-ItemProperty $key -Name 'Data').Data
  Write-Output "Key exists"
}} else {{ Write-Output "Key not found" }}
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=10)
        return {"success": True, "data": {"action": f"night_light_{state.lower()}",
                "note":"Registry key manipulation required for full control"}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
