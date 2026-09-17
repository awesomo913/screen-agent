"""
toolkit_48_keyboard_mouse.py
Advanced keyboard and mouse control: hotkey registration, mouse gestures,
multi-click, cursor position tracking, and input simulation.
"""
from __future__ import annotations
import time
import ctypes
import ctypes.wintypes
from typing import Any, Dict, List

import pyautogui

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

try:
    import mouse
    HAS_MOUSE = True
except ImportError:
    HAS_MOUSE = False

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

def get_mouse_position() -> Dict[str, Any]:
    try:
        x, y = pyautogui.position()
        return {"success": True, "data": {"x": x, "y": y}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def move_mouse(x: int, y: int, duration: float = 0.1) -> Dict[str, Any]:
    try:
        pyautogui.moveTo(x, y, duration=duration)
        return {"success": True, "data": {"moved_to": {"x": x, "y": y}}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def move_mouse_relative(dx: int, dy: int, duration: float = 0.1) -> Dict[str, Any]:
    try:
        pyautogui.moveRel(dx, dy, duration=duration)
        return {"success": True, "data": {"moved_by": {"dx": dx, "dy": dy}}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def click(x: int = -1, y: int = -1, button: str = "left", clicks: int = 1, interval: float = 0.1) -> Dict[str, Any]:
    try:
        if x >= 0 and y >= 0:
            pyautogui.click(x, y, button=button, clicks=clicks, interval=interval)
        else:
            pyautogui.click(button=button, clicks=clicks, interval=interval)
        return {"success": True, "data": {"clicked": {"x": x, "y": y, "button": button, "clicks": clicks}}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def right_click(x: int = -1, y: int = -1) -> Dict[str, Any]:
    try:
        if x >= 0 and y >= 0:
            pyautogui.rightClick(x, y)
        else:
            pyautogui.rightClick()
        return {"success": True, "data": "Right clicked", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def double_click(x: int = -1, y: int = -1) -> Dict[str, Any]:
    try:
        if x >= 0 and y >= 0:
            pyautogui.doubleClick(x, y)
        else:
            pyautogui.doubleClick()
        return {"success": True, "data": "Double clicked", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def scroll(direction: str = "down", amount: int = 3, x: int = -1, y: int = -1) -> Dict[str, Any]:
    try:
        clicks = -amount if direction.lower() == "down" else amount
        if x >= 0 and y >= 0:
            pyautogui.scroll(clicks, x=x, y=y)
        else:
            pyautogui.scroll(clicks)
        return {"success": True, "data": {"direction": direction, "amount": amount}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def drag(start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.3, button: str = "left") -> Dict[str, Any]:
    try:
        pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration, button=button)
        return {"success": True, "data": {"from": {"x": start_x, "y": start_y}, "to": {"x": end_x, "y": end_y}}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def drag_to(start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.3) -> Dict[str, Any]:
    try:
        pyautogui.moveTo(start_x, start_y, duration=0.1)
        pyautogui.dragTo(end_x, end_y, duration=duration)
        return {"success": True, "data": "Dragged", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def type_text(text: str, interval: float = 0.02) -> Dict[str, Any]:
    try:
        pyautogui.write(text, interval=interval)
        return {"success": True, "data": "Typed: " + text[:30], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def press_key(key: str) -> Dict[str, Any]:
    try:
        pyautogui.press(key)
        return {"success": True, "data": "Pressed: " + key, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def hotkey(*keys: str) -> Dict[str, Any]:
    try:
        pyautogui.hotkey(*keys)
        return {"success": True, "data": "Hotkey: " + "+".join(keys), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def press_hotkey(key_combo: str) -> Dict[str, Any]:
    """Press a hotkey combo like 'ctrl+c', 'alt+f4', 'ctrl+shift+esc'."""
    try:
        keys = [k.strip() for k in key_combo.lower().split("+")]
        pyautogui.hotkey(*keys)
        return {"success": True, "data": "Hotkey pressed: " + key_combo, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def hold_key(key: str, duration: float = 1.0) -> Dict[str, Any]:
    try:
        pyautogui.keyDown(key)
        time.sleep(duration)
        pyautogui.keyUp(key)
        return {"success": True, "data": "Held " + key + " for " + str(duration) + "s", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_screen_size() -> Dict[str, Any]:
    try:
        w, h = pyautogui.size()
        return {"success": True, "data": {"width": w, "height": h}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_pixel_color_at(x: int, y: int) -> Dict[str, Any]:
    try:
        color = pyautogui.screenshot(region=(x, y, 1, 1)).getpixel((0, 0))
        return {"success": True, "data": {"x": x, "y": y, "rgb": color}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def locate_on_screen(image_path: str, confidence: float = 0.9) -> Dict[str, Any]:
    try:
        loc = pyautogui.locateOnScreen(image_path, confidence=confidence)
        if loc:
            center = pyautogui.center(loc)
            return {"success": True, "data": {"found": True, "x": center.x, "y": center.y, "region": list(loc)}, "error": None}
        return {"success": True, "data": {"found": False}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def click_image(image_path: str, confidence: float = 0.9) -> Dict[str, Any]:
    try:
        loc = pyautogui.locateCenterOnScreen(image_path, confidence=confidence)
        if not loc:
            return {"success": False, "data": None, "error": "Image not found on screen"}
        pyautogui.click(loc)
        return {"success": True, "data": {"clicked_at": {"x": loc.x, "y": loc.y}}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_libraries() -> Dict[str, Any]:
    return {"success": True, "data": {"pyautogui": True, "keyboard": HAS_KEYBOARD, "mouse": HAS_MOUSE}, "error": None}
