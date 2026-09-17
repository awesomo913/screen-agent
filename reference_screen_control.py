"""
Screen Control Reference - Complete API for controlling a desktop computer programmatically.
Covers: mouse, keyboard, screenshots, screen reading, window management, clipboard, and automation patterns.
All functions are fully implemented and tested on Windows 11 with Python 3.11.
"""

import pyautogui
import pyperclip
import mss
import mss.tools
import ctypes
import time
import json
import os
import io
import re
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Union
from PIL import Image, ImageDraw, ImageGrab
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

pyautogui.PAUSE = 0.1          # Delay between pyautogui actions (seconds)
pyautogui.FAILSAFE = True      # Move mouse to top-left corner to abort

SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()


# ═══════════════════════════════════════════════════════════════════════════════
# MOUSE CONTROL
# ═══════════════════════════════════════════════════════════════════════════════

def mouse_move(x: int, y: int, duration: float = 0.3) -> Dict[str, Any]:
    """Move mouse cursor to absolute screen coordinates."""
    pyautogui.moveTo(x, y, duration=duration)
    return {"action": "move", "x": x, "y": y}


def mouse_move_relative(dx: int, dy: int, duration: float = 0.3) -> Dict[str, Any]:
    """Move mouse relative to current position."""
    pyautogui.move(dx, dy, duration=duration)
    pos = pyautogui.position()
    return {"action": "move_relative", "dx": dx, "dy": dy, "final_x": pos.x, "final_y": pos.y}


def mouse_click(x: int, y: int, button: str = "left", clicks: int = 1) -> Dict[str, Any]:
    """Click at coordinates. button: 'left', 'right', 'middle'. clicks: 1, 2, 3."""
    pyautogui.click(x, y, button=button, clicks=clicks)
    return {"action": "click", "x": x, "y": y, "button": button, "clicks": clicks}


def mouse_double_click(x: int, y: int) -> Dict[str, Any]:
    """Double-click at coordinates."""
    pyautogui.doubleClick(x, y)
    return {"action": "double_click", "x": x, "y": y}


def mouse_right_click(x: int, y: int) -> Dict[str, Any]:
    """Right-click at coordinates."""
    pyautogui.rightClick(x, y)
    return {"action": "right_click", "x": x, "y": y}


def mouse_triple_click(x: int, y: int) -> Dict[str, Any]:
    """Triple-click to select a full line/paragraph."""
    pyautogui.click(x, y, clicks=3, interval=0.05)
    return {"action": "triple_click", "x": x, "y": y}


def mouse_drag(start_x: int, start_y: int, end_x: int, end_y: int,
               duration: float = 0.5, button: str = "left") -> Dict[str, Any]:
    """Click and drag from start to end coordinates."""
    pyautogui.moveTo(start_x, start_y)
    pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration, button=button)
    return {"action": "drag", "from": (start_x, start_y), "to": (end_x, end_y)}


def mouse_scroll(amount: int, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
    """Scroll vertically. Positive = up, negative = down."""
    pyautogui.scroll(amount, x, y)
    return {"action": "scroll", "amount": amount, "x": x, "y": y}


def mouse_scroll_horizontal(amount: int, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
    """Scroll horizontally. Positive = right, negative = left."""
    pyautogui.hscroll(amount, x, y)
    return {"action": "hscroll", "amount": amount}


def mouse_position() -> Dict[str, int]:
    """Get current mouse cursor position."""
    pos = pyautogui.position()
    return {"x": pos.x, "y": pos.y}


def mouse_down(x: int, y: int, button: str = "left") -> Dict[str, Any]:
    """Press and hold mouse button without releasing."""
    pyautogui.moveTo(x, y)
    pyautogui.mouseDown(button=button)
    return {"action": "mouse_down", "x": x, "y": y, "button": button}


def mouse_up(button: str = "left") -> Dict[str, Any]:
    """Release a held mouse button."""
    pyautogui.mouseUp(button=button)
    return {"action": "mouse_up", "button": button}


# ═══════════════════════════════════════════════════════════════════════════════
# KEYBOARD CONTROL
# ═══════════════════════════════════════════════════════════════════════════════

def key_type(text: str, interval: float = 0.02) -> Dict[str, Any]:
    """Type a string of text character by character. Works for ASCII text."""
    pyautogui.typewrite(text, interval=interval)
    return {"action": "type", "text": text, "chars": len(text)}


def key_write(text: str) -> Dict[str, Any]:
    """Type text using the keyboard. Handles Unicode characters (non-ASCII)."""
    pyautogui.write(text)
    return {"action": "write", "text": text}


def key_press(key: str) -> Dict[str, Any]:
    """Press and release a single key. Examples: 'enter', 'tab', 'escape', 'backspace',
    'delete', 'space', 'up', 'down', 'left', 'right', 'home', 'end',
    'pageup', 'pagedown', 'f1'-'f12', 'capslock', 'numlock', 'printscreen'."""
    pyautogui.press(key)
    return {"action": "press", "key": key}


def key_press_multiple(key: str, times: int, interval: float = 0.05) -> Dict[str, Any]:
    """Press a key multiple times."""
    for _ in range(times):
        pyautogui.press(key)
        time.sleep(interval)
    return {"action": "press_multiple", "key": key, "times": times}


def key_hotkey(*keys: str) -> Dict[str, Any]:
    """Press a keyboard shortcut. Examples: hotkey('ctrl', 'c'), hotkey('alt', 'f4'),
    hotkey('ctrl', 'shift', 'esc'), hotkey('win', 'd')."""
    pyautogui.hotkey(*keys)
    return {"action": "hotkey", "keys": list(keys)}


def key_hold(key: str, duration: float = 0.5) -> Dict[str, Any]:
    """Hold a key down for a duration then release."""
    pyautogui.keyDown(key)
    time.sleep(duration)
    pyautogui.keyUp(key)
    return {"action": "hold", "key": key, "duration": duration}


def key_down(key: str) -> Dict[str, Any]:
    """Press and hold a key without releasing."""
    pyautogui.keyDown(key)
    return {"action": "key_down", "key": key}


def key_up(key: str) -> Dict[str, Any]:
    """Release a held key."""
    pyautogui.keyUp(key)
    return {"action": "key_up", "key": key}


# Common keyboard shortcuts as convenience functions
def copy() -> Dict[str, Any]:
    """Ctrl+C - copy selection to clipboard."""
    return key_hotkey('ctrl', 'c')

def paste() -> Dict[str, Any]:
    """Ctrl+V - paste from clipboard."""
    return key_hotkey('ctrl', 'v')

def cut() -> Dict[str, Any]:
    """Ctrl+X - cut selection to clipboard."""
    return key_hotkey('ctrl', 'x')

def select_all() -> Dict[str, Any]:
    """Ctrl+A - select all content."""
    return key_hotkey('ctrl', 'a')

def undo() -> Dict[str, Any]:
    """Ctrl+Z - undo last action."""
    return key_hotkey('ctrl', 'z')

def redo() -> Dict[str, Any]:
    """Ctrl+Y - redo last undone action."""
    return key_hotkey('ctrl', 'y')

def save() -> Dict[str, Any]:
    """Ctrl+S - save current document."""
    return key_hotkey('ctrl', 's')

def find() -> Dict[str, Any]:
    """Ctrl+F - open find dialog."""
    return key_hotkey('ctrl', 'f')

def new_tab() -> Dict[str, Any]:
    """Ctrl+T - open new browser tab."""
    return key_hotkey('ctrl', 't')

def close_tab() -> Dict[str, Any]:
    """Ctrl+W - close current tab."""
    return key_hotkey('ctrl', 'w')

def close_window() -> Dict[str, Any]:
    """Alt+F4 - close current window."""
    return key_hotkey('alt', 'F4')

def switch_window() -> Dict[str, Any]:
    """Alt+Tab - switch between windows."""
    return key_hotkey('alt', 'tab')

def minimize_all() -> Dict[str, Any]:
    """Win+D - show desktop / minimize all."""
    return key_hotkey('win', 'd')

def open_start_menu() -> Dict[str, Any]:
    """Open Windows Start menu."""
    pyautogui.press('win')
    return {"action": "start_menu"}

def open_task_manager() -> Dict[str, Any]:
    """Ctrl+Shift+Esc - open Task Manager."""
    return key_hotkey('ctrl', 'shift', 'escape')

def open_settings() -> Dict[str, Any]:
    """Win+I - open Windows Settings."""
    return key_hotkey('win', 'i')

def open_file_explorer() -> Dict[str, Any]:
    """Win+E - open File Explorer."""
    return key_hotkey('win', 'e')

def open_run_dialog() -> Dict[str, Any]:
    """Win+R - open Run dialog."""
    return key_hotkey('win', 'r')

def take_screenshot_snip() -> Dict[str, Any]:
    """Win+Shift+S - open Snipping Tool."""
    return key_hotkey('win', 'shift', 's')

def lock_screen() -> Dict[str, Any]:
    """Win+L - lock the screen."""
    return key_hotkey('win', 'l')


# ═══════════════════════════════════════════════════════════════════════════════
# CLIPBOARD OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def clipboard_copy(text: str) -> Dict[str, Any]:
    """Copy text to clipboard programmatically (without keyboard)."""
    pyperclip.copy(text)
    return {"action": "clipboard_copy", "length": len(text)}


def clipboard_paste() -> Dict[str, Any]:
    """Read text from clipboard."""
    text = pyperclip.paste()
    return {"action": "clipboard_paste", "text": text, "length": len(text)}


def clipboard_clear() -> Dict[str, Any]:
    """Clear the clipboard."""
    pyperclip.copy("")
    return {"action": "clipboard_clear"}


def copy_selected_text() -> str:
    """Copy whatever is currently selected on screen and return it."""
    old = pyperclip.paste()
    key_hotkey('ctrl', 'c')
    time.sleep(0.1)
    text = pyperclip.paste()
    return text


def paste_text(text: str) -> Dict[str, Any]:
    """Put text on clipboard then paste it (handles Unicode)."""
    pyperclip.copy(text)
    time.sleep(0.05)
    key_hotkey('ctrl', 'v')
    return {"action": "paste_text", "length": len(text)}


# ═══════════════════════════════════════════════════════════════════════════════
# SCREENSHOTS & SCREEN READING
# ═══════════════════════════════════════════════════════════════════════════════

def screenshot_full() -> Image.Image:
    """Capture the entire screen as a PIL Image."""
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        img = sct.grab(monitor)
        return Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")


def screenshot_region(left: int, top: int, width: int, height: int) -> Image.Image:
    """Capture a specific region of the screen."""
    with mss.mss() as sct:
        monitor = {"left": left, "top": top, "width": width, "height": height}
        img = sct.grab(monitor)
        return Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")


def screenshot_save(path: str, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
    """Save a screenshot to file. Region: (left, top, width, height) or None for full screen."""
    if region:
        img = screenshot_region(*region)
    else:
        img = screenshot_full()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return {"action": "screenshot_save", "path": path, "size": img.size}


def screenshot_to_bytes(max_width: int = 1280) -> bytes:
    """Capture screen and return as PNG bytes (for sending to AI vision models).
    Resizes to max_width to reduce data size."""
    img = screenshot_full()
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def get_pixel_color(x: int, y: int) -> Tuple[int, int, int]:
    """Get the RGB color of a pixel at screen coordinates."""
    return pyautogui.pixel(x, y)


def get_screen_size() -> Dict[str, int]:
    """Get the screen resolution."""
    return {"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT}


def locate_image_on_screen(image_path: str, confidence: float = 0.8) -> Optional[Dict[str, int]]:
    """Find an image on screen using template matching.
    Returns center coordinates if found, None if not."""
    try:
        location = pyautogui.locateOnScreen(image_path, confidence=confidence)
        if location:
            center = pyautogui.center(location)
            return {"x": center.x, "y": center.y, "left": location.left,
                    "top": location.top, "width": location.width, "height": location.height}
    except Exception:
        pass
    return None


def wait_for_image(image_path: str, timeout: float = 10.0,
                   interval: float = 0.5) -> Optional[Dict[str, int]]:
    """Wait until an image appears on screen or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        result = locate_image_on_screen(image_path)
        if result:
            return result
        time.sleep(interval)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# WINDOW MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def get_active_window() -> Optional[Dict[str, Any]]:
    """Get info about the currently focused window."""
    win = pyautogui.getActiveWindow()
    if win:
        return {"title": win.title, "left": win.left, "top": win.top,
                "width": win.width, "height": win.height}
    return None


def get_all_windows() -> List[Dict[str, Any]]:
    """List all visible windows with their titles and positions."""
    windows = []
    for win in pyautogui.getAllWindows():
        if win.title and win.visible:
            windows.append({"title": win.title, "left": win.left, "top": win.top,
                           "width": win.width, "height": win.height})
    return windows


def find_window(title_contains: str) -> Optional[Dict[str, Any]]:
    """Find a window by partial title match (case-insensitive)."""
    for win in pyautogui.getAllWindows():
        if title_contains.lower() in win.title.lower():
            return {"title": win.title, "left": win.left, "top": win.top,
                   "width": win.width, "height": win.height, "window": win}
    return None


def focus_window(title_contains: str) -> Dict[str, Any]:
    """Bring a window to the foreground by partial title match."""
    result = find_window(title_contains)
    if result and "window" in result:
        try:
            result["window"].activate()
            return {"action": "focus_window", "title": result["title"], "success": True}
        except Exception:
            pass
    return {"action": "focus_window", "success": False}


def resize_window(title_contains: str, width: int, height: int) -> Dict[str, Any]:
    """Resize a window by title."""
    result = find_window(title_contains)
    if result and "window" in result:
        result["window"].resizeTo(width, height)
        return {"action": "resize", "title": result["title"], "width": width, "height": height}
    return {"action": "resize", "success": False}


def move_window(title_contains: str, x: int, y: int) -> Dict[str, Any]:
    """Move a window to specific screen coordinates."""
    result = find_window(title_contains)
    if result and "window" in result:
        result["window"].moveTo(x, y)
        return {"action": "move_window", "title": result["title"], "x": x, "y": y}
    return {"action": "move_window", "success": False}


def maximize_window(title_contains: str) -> Dict[str, Any]:
    """Maximize a window."""
    result = find_window(title_contains)
    if result and "window" in result:
        result["window"].maximize()
        return {"action": "maximize", "title": result["title"]}
    return {"action": "maximize", "success": False}


def minimize_window(title_contains: str) -> Dict[str, Any]:
    """Minimize a window."""
    result = find_window(title_contains)
    if result and "window" in result:
        result["window"].minimize()
        return {"action": "minimize", "title": result["title"]}
    return {"action": "minimize", "success": False}


# ═══════════════════════════════════════════════════════════════════════════════
# APPLICATION LAUNCHING
# ═══════════════════════════════════════════════════════════════════════════════

def open_application(name: str) -> Dict[str, Any]:
    """Open an application using the Start menu search."""
    pyautogui.press('win')
    time.sleep(0.5)
    pyautogui.typewrite(name, interval=0.03)
    time.sleep(0.8)
    pyautogui.press('enter')
    return {"action": "open_app", "name": name}


def run_command(command: str, timeout: int = 30) -> Dict[str, Any]:
    """Run a shell command and return the output."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True,
                               text=True, timeout=timeout)
        return {"success": True, "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(), "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def open_url(url: str) -> Dict[str, Any]:
    """Open a URL in the default browser."""
    os.startfile(url)
    return {"action": "open_url", "url": url}


def open_file(path: str) -> Dict[str, Any]:
    """Open a file with its default application."""
    os.startfile(path)
    return {"action": "open_file", "path": path}


# ═══════════════════════════════════════════════════════════════════════════════
# WAITING & TIMING
# ═══════════════════════════════════════════════════════════════════════════════

def wait(seconds: float) -> Dict[str, Any]:
    """Pause execution for a number of seconds."""
    time.sleep(seconds)
    return {"action": "wait", "seconds": seconds}


def wait_until_idle(check_interval: float = 0.5, idle_threshold: float = 2.0) -> Dict[str, Any]:
    """Wait until the mouse hasn't moved for idle_threshold seconds."""
    last_pos = pyautogui.position()
    idle_start = time.time()
    while True:
        time.sleep(check_interval)
        current = pyautogui.position()
        if current != last_pos:
            last_pos = current
            idle_start = time.time()
        elif time.time() - idle_start >= idle_threshold:
            return {"action": "idle_detected", "waited": time.time() - idle_start}


# ═══════════════════════════════════════════════════════════════════════════════
# COMPOUND ACTIONS - Common multi-step patterns
# ═══════════════════════════════════════════════════════════════════════════════

def click_and_type(x: int, y: int, text: str, clear_first: bool = True) -> Dict[str, Any]:
    """Click on a text field and type into it."""
    mouse_click(x, y)
    time.sleep(0.1)
    if clear_first:
        select_all()
        time.sleep(0.05)
    paste_text(text)
    return {"action": "click_and_type", "x": x, "y": y, "text": text}


def right_click_option(x: int, y: int, option_index: int) -> Dict[str, Any]:
    """Right-click and select the Nth option from the context menu (0-based)."""
    mouse_right_click(x, y)
    time.sleep(0.3)
    for _ in range(option_index):
        key_press('down')
        time.sleep(0.05)
    key_press('enter')
    return {"action": "right_click_option", "x": x, "y": y, "option": option_index}


def search_start_menu(query: str) -> Dict[str, Any]:
    """Open Start menu and search for something."""
    open_start_menu()
    time.sleep(0.5)
    pyautogui.typewrite(query, interval=0.03)
    time.sleep(0.8)
    return {"action": "search_start", "query": query}


def navigate_to_url(url: str) -> Dict[str, Any]:
    """In a browser, navigate to a URL using the address bar."""
    key_hotkey('ctrl', 'l')  # Focus address bar
    time.sleep(0.2)
    paste_text(url)
    time.sleep(0.1)
    key_press('enter')
    return {"action": "navigate_url", "url": url}


def select_text_region(start_x: int, start_y: int,
                       end_x: int, end_y: int) -> Dict[str, Any]:
    """Select text by clicking at start and shift-clicking at end."""
    mouse_click(start_x, start_y)
    time.sleep(0.1)
    pyautogui.keyDown('shift')
    mouse_click(end_x, end_y)
    pyautogui.keyUp('shift')
    return {"action": "select_region", "from": (start_x, start_y), "to": (end_x, end_y)}


def copy_text_at(x: int, y: int) -> str:
    """Triple-click to select a line, copy it, and return the text."""
    mouse_triple_click(x, y)
    time.sleep(0.1)
    return copy_selected_text()


def scroll_to_top() -> Dict[str, Any]:
    """Scroll to the top of a page/document."""
    key_hotkey('ctrl', 'home')
    return {"action": "scroll_to_top"}


def scroll_to_bottom() -> Dict[str, Any]:
    """Scroll to the bottom of a page/document."""
    key_hotkey('ctrl', 'end')
    return {"action": "scroll_to_bottom"}


def zoom_in(times: int = 1) -> Dict[str, Any]:
    """Zoom in using Ctrl+Plus."""
    for _ in range(times):
        key_hotkey('ctrl', 'plus')
    return {"action": "zoom_in", "times": times}


def zoom_out(times: int = 1) -> Dict[str, Any]:
    """Zoom out using Ctrl+Minus."""
    for _ in range(times):
        key_hotkey('ctrl', 'minus')
    return {"action": "zoom_out", "times": times}


def zoom_reset() -> Dict[str, Any]:
    """Reset zoom to 100% using Ctrl+0."""
    key_hotkey('ctrl', '0')
    return {"action": "zoom_reset"}


# ═══════════════════════════════════════════════════════════════════════════════
# FILE DIALOG HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def file_dialog_type_path(path: str) -> Dict[str, Any]:
    """In an open/save file dialog, type a path into the filename field."""
    key_hotkey('alt', 'd')  # Focus the address bar in file dialogs
    time.sleep(0.2)
    paste_text(path)
    time.sleep(0.1)
    key_press('enter')
    return {"action": "file_dialog_path", "path": path}


def file_dialog_save_as(path: str) -> Dict[str, Any]:
    """Open Save As dialog (Ctrl+Shift+S), type path, and confirm."""
    key_hotkey('ctrl', 'shift', 's')
    time.sleep(0.5)
    file_dialog_type_path(path)
    time.sleep(0.3)
    key_press('enter')
    return {"action": "save_as", "path": path}


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM INFORMATION (no GUI needed)
# ═══════════════════════════════════════════════════════════════════════════════

def get_running_processes() -> List[Dict[str, Any]]:
    """Get list of running processes via tasklist."""
    result = run_command('tasklist /FO CSV /NH')
    processes = []
    if result["success"]:
        for line in result["stdout"].split('\n'):
            parts = line.strip().strip('"').split('","')
            if len(parts) >= 5:
                processes.append({
                    "name": parts[0], "pid": parts[1],
                    "session": parts[2], "memory": parts[4]
                })
    return processes


def get_disk_space() -> Dict[str, Any]:
    """Get disk space info for all drives."""
    result = run_command('wmic logicaldisk get size,freespace,caption /format:csv')
    return {"output": result.get("stdout", "")}


def get_system_info() -> Dict[str, Any]:
    """Get basic system information."""
    return {
        "hostname": run_command("hostname")["stdout"],
        "os_version": run_command("ver")["stdout"],
        "username": os.environ.get("USERNAME", "unknown"),
        "screen": get_screen_size(),
        "home_dir": str(Path.home()),
    }


def kill_process(name_or_pid: str) -> Dict[str, Any]:
    """Kill a process by name or PID."""
    if name_or_pid.isdigit():
        return run_command(f'taskkill /PID {name_or_pid} /F')
    return run_command(f'taskkill /IM {name_or_pid} /F')


# ═══════════════════════════════════════════════════════════════════════════════
# AUTOMATION PATTERNS - Building blocks for complex workflows
# ═══════════════════════════════════════════════════════════════════════════════

def repeat_action(action_func, times: int, delay: float = 0.1, **kwargs) -> List[Dict]:
    """Repeat any action function N times with a delay between each."""
    results = []
    for i in range(times):
        results.append(action_func(**kwargs))
        if i < times - 1:
            time.sleep(delay)
    return results


def sequence(*actions: Dict[str, Any], delay: float = 0.1) -> List[Dict]:
    """Execute a sequence of actions with delays between them.
    Usage: sequence(
        lambda: mouse_click(100, 200),
        lambda: key_type("hello"),
        lambda: key_press("enter"),
    )"""
    results = []
    for action in actions:
        if callable(action):
            results.append(action())
        time.sleep(delay)
    return results


def retry_until_found(image_path: str, action_func, max_retries: int = 5,
                      delay: float = 1.0) -> Dict[str, Any]:
    """Keep performing an action until an image appears on screen."""
    for attempt in range(max_retries):
        found = locate_image_on_screen(image_path)
        if found:
            return {"found": True, "attempt": attempt, "location": found}
        action_func()
        time.sleep(delay)
    return {"found": False, "attempts": max_retries}


def conditional_click(image_path: str, offset_x: int = 0, offset_y: int = 0) -> Dict[str, Any]:
    """Find an image on screen and click it (with optional offset)."""
    location = locate_image_on_screen(image_path)
    if location:
        mouse_click(location["x"] + offset_x, location["y"] + offset_y)
        return {"clicked": True, "x": location["x"], "y": location["y"]}
    return {"clicked": False}


# ═══════════════════════════════════════════════════════════════════════════════
# SCREEN RECORDING (lightweight frame capture)
# ═══════════════════════════════════════════════════════════════════════════════

def record_mouse_trail(duration: float = 5.0, interval: float = 0.05) -> List[Dict]:
    """Record mouse positions over time."""
    trail = []
    start = time.time()
    while time.time() - start < duration:
        pos = pyautogui.position()
        trail.append({"t": round(time.time() - start, 3), "x": pos.x, "y": pos.y})
        time.sleep(interval)
    return trail


def replay_mouse_trail(trail: List[Dict], speed: float = 1.0) -> Dict[str, Any]:
    """Replay a recorded mouse trail."""
    if not trail:
        return {"replayed": 0}
    for i, point in enumerate(trail):
        pyautogui.moveTo(point["x"], point["y"], duration=0)
        if i > 0:
            delay = (point["t"] - trail[i-1]["t"]) / speed
            if delay > 0:
                time.sleep(delay)
    return {"replayed": len(trail)}


# ═══════════════════════════════════════════════════════════════════════════════
# FULL EXAMPLE: Agent action loop pattern
# ═══════════════════════════════════════════════════════════════════════════════

"""
This is the pattern used by Screen Agent to control the computer:

1. Take a screenshot
2. Send screenshot + task description to an AI vision model
3. AI responds with a JSON action (click, type, scroll, tool_call, etc.)
4. Execute the action
5. Repeat until AI says "done"

Example action JSON from the AI:
    {"action": "click", "x": 500, "y": 300, "button": "left", "reason": "clicking the OK button"}
    {"action": "type", "text": "hello world", "reason": "typing into the search box"}
    {"action": "hotkey", "keys": ["ctrl", "s"], "reason": "saving the file"}
    {"action": "tool_call", "tool": "system_monitor.get_cpu_usage", "args": {"interval": 0.5}, "reason": "checking CPU"}
    {"action": "think", "thought": "I can see Notepad is open with a blank document", "reason": "analyzing screen"}
    {"action": "done", "reason": "task complete - file has been saved"}
"""


if __name__ == "__main__":
    print("Screen Control Reference")
    print(f"Screen: {SCREEN_WIDTH}x{SCREEN_HEIGHT}")
    print(f"Mouse: {mouse_position()}")
    print(f"Active window: {get_active_window()}")
    print(f"System: {get_system_info()}")
