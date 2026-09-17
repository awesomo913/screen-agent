"""
toolkit_53_process_automation.py
High-level desktop process automation: open apps, wait for windows,
interact with dialog boxes, automate repetitive GUI workflows.
Builds on pyautogui but adds smarter waiting and app lifecycle management.
"""
from __future__ import annotations
import subprocess
import time
import os
import ctypes
import ctypes.wintypes
from typing import Any, Dict, List

import pyautogui

user32 = ctypes.windll.user32

def _find_window_by_title(keyword: str, timeout: float = 5.0) -> int:
    """Return HWND of first window matching keyword in title, or 0."""
    start = time.time()
    hwnds = []
    def callback(hwnd, extra):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if keyword.lower() in buf.value.lower():
                hwnds.append(hwnd)
        return True
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
    while time.time() - start < timeout:
        hwnds.clear()
        user32.EnumWindows(EnumWindowsProc(callback), 0)
        if hwnds:
            return hwnds[0]
        time.sleep(0.3)
    return 0

def open_app_and_wait(executable: str, window_title_keyword: str, timeout: float = 10.0) -> Dict[str, Any]:
    try:
        proc = subprocess.Popen([executable])
        hwnd = _find_window_by_title(window_title_keyword, timeout)
        if hwnd:
            user32.SetForegroundWindow(hwnd)
        return {"success": bool(hwnd), "data": {"pid": proc.pid, "hwnd": hwnd, "title_found": bool(hwnd)}, "error": None if hwnd else "Window not found in time"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def wait_for_window(title_keyword: str, timeout: float = 15.0) -> Dict[str, Any]:
    try:
        hwnd = _find_window_by_title(title_keyword, timeout)
        return {"success": bool(hwnd), "data": {"hwnd": hwnd, "found": bool(hwnd)}, "error": None if hwnd else "Window not found within " + str(timeout) + "s"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def wait_for_image(image_path: str, timeout: float = 10.0, confidence: float = 0.85) -> Dict[str, Any]:
    try:
        start = time.time()
        while time.time() - start < timeout:
            loc = pyautogui.locateCenterOnScreen(image_path, confidence=confidence)
            if loc:
                return {"success": True, "data": {"x": loc.x, "y": loc.y, "found": True}, "error": None}
            time.sleep(0.5)
        return {"success": False, "data": {"found": False}, "error": "Image not found within " + str(timeout) + "s"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def click_when_visible(image_path: str, timeout: float = 10.0, confidence: float = 0.85) -> Dict[str, Any]:
    try:
        r = wait_for_image(image_path, timeout, confidence)
        if not r["success"]:
            return r
        pyautogui.click(r["data"]["x"], r["data"]["y"])
        return {"success": True, "data": {"clicked_at": {"x": r["data"]["x"], "y": r["data"]["y"]}}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def type_in_focused_field(text: str, clear_first: bool = True, interval: float = 0.02) -> Dict[str, Any]:
    try:
        if clear_first:
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
        pyautogui.write(text, interval=interval)
        return {"success": True, "data": {"typed": len(text)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def click_button_by_text(button_text: str, search_region: list = []) -> Dict[str, Any]:
    """Find and click a button that contains specified text using OCR screenshot scan."""
    try:
        region = tuple(search_region) if len(search_region) == 4 else None
        screenshot = pyautogui.screenshot(region=region)
        try:
            import pytesseract
            import numpy as np
            text_data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)
            for i, word in enumerate(text_data["text"]):
                if button_text.lower() in word.lower() and int(text_data["conf"][i]) > 50:
                    x = text_data["left"][i] + text_data["width"][i] // 2
                    y = text_data["top"][i] + text_data["height"][i] // 2
                    if region:
                        x += region[0]
                        y += region[1]
                    pyautogui.click(x, y)
                    return {"success": True, "data": {"clicked_at": {"x": x, "y": y}}, "error": None}
        except ImportError:
            pass
        return {"success": False, "data": None, "error": "pytesseract not available for OCR button finding"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def close_app_by_title(title_keyword: str) -> Dict[str, Any]:
    try:
        hwnd = _find_window_by_title(title_keyword, timeout=2.0)
        if not hwnd:
            return {"success": False, "data": None, "error": "Window not found: " + title_keyword}
        WM_CLOSE = 0x0010
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return {"success": True, "data": "Close sent to: " + title_keyword, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def kill_app_by_name(process_name: str) -> Dict[str, Any]:
    try:
        result = subprocess.run(["taskkill", "/IM", process_name, "/F"], capture_output=True, text=True)
        return {"success": result.returncode == 0, "data": result.stdout.strip(), "error": result.stderr.strip() or None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def press_enter_in_dialog() -> Dict[str, Any]:
    try:
        pyautogui.press("enter")
        return {"success": True, "data": "Enter pressed", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def dismiss_dialog_ok() -> Dict[str, Any]:
    """Press Alt+O or Enter to dismiss common OK dialogs."""
    try:
        pyautogui.hotkey("alt", "o")
        time.sleep(0.2)
        return {"success": True, "data": "OK dialog dismissed", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def dismiss_dialog_cancel() -> Dict[str, Any]:
    try:
        pyautogui.press("escape")
        return {"success": True, "data": "Dialog cancelled (Escape)", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def screenshot_region(left: int, top: int, width: int, height: int, output_path: str) -> Dict[str, Any]:
    try:
        img = pyautogui.screenshot(region=(left, top, width, height))
        img.save(output_path)
        return {"success": True, "data": {"saved": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def wait_and_click(x: int, y: int, delay: float = 1.0) -> Dict[str, Any]:
    try:
        time.sleep(delay)
        pyautogui.click(x, y)
        return {"success": True, "data": {"clicked": {"x": x, "y": y}, "delay": delay}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def focus_window(title_keyword: str) -> Dict[str, Any]:
    try:
        hwnd = _find_window_by_title(title_keyword, timeout=3.0)
        if not hwnd:
            return {"success": False, "data": None, "error": "Window not found"}
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        return {"success": True, "data": {"hwnd": hwnd, "focused": True}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def run_and_screenshot(executable: str, wait_s: float = 2.0, output_path: str = "C:\\screenshot.png") -> Dict[str, Any]:
    try:
        subprocess.Popen([executable])
        time.sleep(wait_s)
        img = pyautogui.screenshot()
        img.save(output_path)
        return {"success": True, "data": {"screenshot": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
