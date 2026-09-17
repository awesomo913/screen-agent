"""
toolkit_63_screen_capture_advanced.py
Advanced screen capture: multi-monitor support, capture specific windows,
time-lapse recording, region capture with coordinates, and capture comparison.
Distinct from screenshot_manager (basic screenshots).
"""
from __future__ import annotations
import os
import time
from pathlib import Path
from typing import Any, Dict, List

import mss
import mss.tools
from PIL import Image
import pyautogui

def get_monitor_list() -> Dict[str, Any]:
    try:
        with mss.mss() as sct:
            monitors = []
            for i, m in enumerate(sct.monitors):
                monitors.append({"index": i, "left": m["left"], "top": m["top"], "width": m["width"], "height": m["height"]})
        return {"success": True, "data": {"count": len(monitors) - 1, "monitors": monitors[1:]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def capture_monitor(monitor_index: int = 1, output_path: str = "") -> Dict[str, Any]:
    try:
        if not output_path:
            output_path = "C:\\capture_monitor_" + str(monitor_index) + ".png"
        with mss.mss() as sct:
            monitors = sct.monitors
            if monitor_index >= len(monitors):
                return {"success": False, "data": None, "error": "Monitor index out of range"}
            screen = sct.grab(monitors[monitor_index])
            mss.tools.to_png(screen.rgb, screen.size, output=output_path)
        return {"success": True, "data": {"saved": output_path, "monitor": monitor_index}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def capture_all_monitors(output_folder: str = "C:\\captures") -> Dict[str, Any]:
    try:
        os.makedirs(output_folder, exist_ok=True)
        with mss.mss() as sct:
            paths = []
            for i, m in enumerate(sct.monitors[1:], 1):
                screen = sct.grab(m)
                path = os.path.join(output_folder, "monitor_" + str(i) + ".png")
                mss.tools.to_png(screen.rgb, screen.size, output=path)
                paths.append(path)
        return {"success": True, "data": {"saved": paths}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def capture_region(x: int, y: int, width: int, height: int, output_path: str = "") -> Dict[str, Any]:
    try:
        if not output_path:
            output_path = "C:\\capture_region.png"
        with mss.mss() as sct:
            region = {"top": y, "left": x, "width": width, "height": height}
            screen = sct.grab(region)
            mss.tools.to_png(screen.rgb, screen.size, output=output_path)
        return {"success": True, "data": {"saved": output_path, "region": {"x": x, "y": y, "w": width, "h": height}}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def capture_window(title_keyword: str, output_path: str = "") -> Dict[str, Any]:
    try:
        import ctypes, ctypes.wintypes
        if not output_path:
            output_path = "C:\\capture_window.png"
        user32 = ctypes.windll.user32
        hwnd = None
        found = []
        def callback(h, extra):
            if user32.IsWindowVisible(h):
                length = user32.GetWindowTextLengthW(h)
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(h, buf, length + 1)
                if title_keyword.lower() in buf.value.lower():
                    found.append(h)
            return True
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
        user32.EnumWindows(EnumWindowsProc(callback), 0)
        if not found:
            return {"success": False, "data": None, "error": "Window not found: " + title_keyword}
        hwnd = found[0]
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        left, top = rect.left, rect.top
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        with mss.mss() as sct:
            region = {"top": top, "left": left, "width": width, "height": height}
            screen = sct.grab(region)
            mss.tools.to_png(screen.rgb, screen.size, output=output_path)
        return {"success": True, "data": {"saved": output_path, "rect": {"left": left, "top": top, "width": width, "height": height}}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def timelapse_capture(output_folder: str, count: int = 10, interval_s: float = 1.0) -> Dict[str, Any]:
    try:
        os.makedirs(output_folder, exist_ok=True)
        paths = []
        with mss.mss() as sct:
            for i in range(count):
                screen = sct.grab(sct.monitors[0])
                path = os.path.join(output_folder, "frame_" + str(i).zfill(4) + ".png")
                mss.tools.to_png(screen.rgb, screen.size, output=path)
                paths.append(path)
                if i < count - 1:
                    time.sleep(interval_s)
        return {"success": True, "data": {"frames": count, "saved_to": output_folder, "files": paths}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def compare_screenshots(path1: str, path2: str) -> Dict[str, Any]:
    """Compare two screenshots pixel by pixel and return difference stats."""
    try:
        img1 = Image.open(path1).convert("RGB")
        img2 = Image.open(path2).convert("RGB")
        if img1.size != img2.size:
            return {"success": False, "data": None, "error": "Images have different sizes"}
        from PIL import ImageChops
        diff = ImageChops.difference(img1, img2)
        pixels = list(diff.getdata())
        total = len(pixels)
        changed = sum(1 for p in pixels if p != (0, 0, 0))
        avg_diff = sum(sum(p) / 3 for p in pixels) / total
        return {"success": True, "data": {
            "total_pixels": total,
            "changed_pixels": changed,
            "change_percent": round(changed / total * 100, 2),
            "avg_pixel_diff": round(avg_diff, 2)
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def capture_and_resize(width: int, height: int, output_path: str = "") -> Dict[str, Any]:
    """Full screenshot resized to specific dimensions."""
    try:
        if not output_path:
            output_path = "C:\\capture_resized.png"
        with mss.mss() as sct:
            screen = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", screen.size, screen.bgra, "raw", "BGRX")
        img = img.resize((width, height), Image.LANCZOS)
        img.save(output_path)
        return {"success": True, "data": {"saved": output_path, "size": [width, height]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_screen_resolution() -> Dict[str, Any]:
    try:
        with mss.mss() as sct:
            primary = sct.monitors[1]
            return {"success": True, "data": {"width": primary["width"], "height": primary["height"]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def save_screenshot_with_timestamp(output_folder: str = "C:\\screenshots") -> Dict[str, Any]:
    try:
        import datetime
        os.makedirs(output_folder, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(output_folder, "screenshot_" + ts + ".png")
        img = pyautogui.screenshot()
        img.save(path)
        return {"success": True, "data": {"saved": path, "timestamp": ts}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
