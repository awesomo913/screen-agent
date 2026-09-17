import keyboard
from pynput import keyboard as pynput_keyboard
import ctypes
import json
import threading
import time
import platform
import functools
from typing import Dict, List, Any, Callable, Optional

# ---------------------------------------------------------------------------
# Module State & Thread Safety
# ---------------------------------------------------------------------------
_registry_lock = threading.RLock()
_hotkey_registry: Dict[str, Dict[str, Any]] = {}
_macro_registry: Dict[str, List[Dict[str, Any]]] = {}

# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------
def _response(success: bool, data: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
    """Standardized response dictionary for all public functions."""
    return {"success": success, "data": data, "error": error}


def _wrap_callback(callback: Callable[..., Any]) -> Callable[..., Any]:
    """Safely wraps user callbacks to prevent hotkey listener crashes."""
    @functools.wraps(callback)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        try:
            callback(*args, **kwargs)
        except Exception:
            # Log or swallow to keep hotkey engine alive; client can handle via try/except in their code
            pass
    return wrapper


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register_hotkey(keys: List[str], callback: Callable[..., Any]) -> Dict[str, Any]:
    """Registers a keyboard shortcut that triggers a callback."""
    try:
        hotkey_str = "+".join(keys).lower()
        hotkey_id = f"hk_{abs(hash(hotkey_str)) & 0xFFFFFFFF:08X}"
        
        with _registry_lock:
            if hotkey_id in _hotkey_registry:
                return _response(False, error="Hotkey ID collision. Please unregister first.")
            _hotkey_registry[hotkey_id] = {
                "keys": keys,
                "callback": callback,
                "hotkey_str": hotkey_str
            }
            
        safe_callback = _wrap_callback(callback)
        keyboard.add_hotkey(hotkey_str, safe_callback, suppress=False)
        return _response(True, {"id": hotkey_id, "keys": keys, "sequence": hotkey_str})
    except Exception as e:
        return _response(False, error=str(e))


def unregister_hotkey(hotkey_id: str) -> Dict[str, Any]:
    """Removes a previously registered hotkey by its ID."""
    try:
        with _registry_lock:
            entry = _hotkey_registry.pop(hotkey_id, None)
        if entry is None:
            return _response(False, error="Hotkey ID not found")
        keyboard.remove_hotkey(entry["hotkey_str"])
        return _response(True, {"id": hotkey_id, "status": "unregistered"})
    except Exception as e:
        return _response(False, error=str(e))


def list_registered_hotkeys() -> Dict[str, Any]:
    """Returns all currently active hotkeys."""
    try:
        with _registry_lock:
            snapshot = [{"id": k, "keys": v["keys"], "sequence": v["hotkey_str"]} 
                        for k, v in _hotkey_registry.items()]
        return _response(True, snapshot)
    except Exception as e:
        return _response(False, error=str(e))


def press_key(key: str) -> Dict[str, Any]:
    """Simulates a physical key press."""
    try:
        keyboard.press(key)
        return _response(True, {"key": key, "action": "pressed"})
    except Exception as e:
        return _response(False, error=str(e))


def release_key(key: str) -> Dict[str, Any]:
    """Simulates a physical key release."""
    try:
        keyboard.release(key)
        return _response(True, {"key": key, "action": "released"})
    except Exception as e:
        return _response(False, error=str(e))


def type_text(text: str, interval: float) -> Dict[str, Any]:
    """Types a string character by character with a delay."""
    try:
        ctrl = pynput_keyboard.Controller()
        for char in text:
            ctrl.type(char)
            if interval > 0:
                time.sleep(interval)
        return _response(True, {"text": text, "characters": len(text), "interval": interval})
    except Exception as e:
        return _response(False, error=str(e))


def press_hotkey(keys: List[str]) -> Dict[str, Any]:
    """Presses multiple keys simultaneously as a chord, then releases them."""
    try:
        if not keys:
            return _response(False, error="Empty keys list")
        for k in keys:
            keyboard.press(k)
        time.sleep(0.015)
        for k in reversed(keys):
            keyboard.release(k)
        return _response(True, {"keys": keys, "action": "chord_executed"})
    except Exception as e:
        return _response(False, error=str(e))


def hold_key(key: str, duration: float) -> Dict[str, Any]:
    """Holds a key down for a specified duration."""
    try:
        keyboard.press(key)
        time.sleep(duration)
        keyboard.release(key)
        return _response(True, {"key": key, "duration": duration})
    except Exception as e:
        return _response(False, error=str(e))


def key_is_pressed(key: str) -> Dict[str, Any]:
    """Checks if a specific key is currently held down."""
    try:
        state = keyboard.is_pressed(key)
        return _response(True, {"key": key, "is_pressed": state})
    except Exception as e:
        return _response(False, error=str(e))


def wait_for_key(key: str, timeout: float) -> Dict[str, Any]:
    """Blocks until a key is pressed or timeout expires. Runs non-blocking internally."""
    try:
        event = threading.Event()
        result_container = {"pressed": False}

        def _on_press(e: keyboard.KeyboardEvent) -> None:
            if str(e.name).lower() == str(key).lower():
                result_container["pressed"] = True
                event.set()

        listener = keyboard.hook(_on_press)
        pressed = event.wait(timeout)
        listener.unhook()

        return _response(True, {
            "key": key, 
            "pressed_within_timeout": pressed, 
            "timeout_used": timeout
        })
    except Exception as e:
        return _response(False, error=str(e))


def record_keystrokes(duration: float) -> Dict[str, Any]:
    """Records all keyboard events for a specified duration."""
    try:
        if duration <= 0:
            return _response(False, error="Duration must be > 0")
        events = keyboard.record(duration)
        serialized = [
            {"event_type": e.event_type, "name": e.name, "scan_code": e.scan_code, "time": e.time}
            for e in events
        ]
        return _response(True, {"events": serialized, "count": len(serialized), "duration": duration})
    except Exception as e:
        return _response(False, error=str(e))


def replay_keystrokes(keystrokes: List[Dict[str, Any]], speed: float) -> Dict[str, Any]:
    """Replays a recorded keystroke sequence. Speed multiplier (1.0 = real time)."""
    try:
        if not keystrokes:
            return _response(True, {"replayed": 0})
            
        speed = max(0.01, speed)
        base_time = keystrokes[0].get("time", 0.0)
        for i, evt in enumerate(keystrokes):
            evt_time = evt.get("time", 0.0)
            delay = (evt_time - base_time) / speed if i > 0 else 0
            if delay > 0:
                time.sleep(delay)
            base_time = evt_time
            
            key_name = evt.get("name")
            if evt.get("event_type") == "down":
                keyboard.press(key_name)
            elif evt.get("event_type") == "up":
                keyboard.release(key_name)
                
        return _response(True, {"replayed": len(keystrokes)})
    except Exception as e:
        return _response(False, error=str(e))


@functools.lru_cache(maxsize=1)
def get_keyboard_layout() -> Dict[str, Any]:
    """Retrieves the active OS keyboard layout identifier."""
    try:
        sys = platform.system()
        if sys == "Windows":
            user32 = ctypes.windll.user32
            layout_buf = ctypes.create_unicode_buffer(9)
            user32.GetKeyboardLayoutNameW(layout_buf)
            return _response(True, {"layout_id": layout_buf.value, "platform": sys})
        elif sys == "Linux":
            import subprocess
            out = subprocess.check_output(["setxkbmap", "-query"], stderr=subprocess.STDOUT).decode().strip()
            return _response(True, {"layout": out, "platform": sys})
        elif sys == "Darwin":
            return _response(True, {"layout": "us_intl_mac", "platform": sys})
        return _response(True, {"layout": "generic", "platform": sys})
    except Exception as e:
        return _response(False, error=str(e))


def _set_lock_state(vk: int, state: bool, name: str) -> Dict[str, Any]:
    """Internal helper to toggle lock keys via Win32 API."""
    try:
        if platform.system() != "Windows":
            return _response(False, error="Direct lock state control requires Windows via ctypes")
        
        user32 = ctypes.windll.user32
        current = user32.GetKeyState(vk) & 0x1
        if (current == 1) != state:
            # Press & release to toggle
            user32.keybd_event(vk, 0, 0x0001, 0)  # KEYDOWN
            time.sleep(0.01)
            user32.keybd_event(vk, 0, 0x0002, 0)  # KEYUP
        return _response(True, {"key": name, "target_state": state, "applied": True})
    except Exception as e:
        return _response(False, error=str(e))

def set_num_lock(state: bool) -> Dict[str, Any]:
    return _set_lock_state(0x90, state, "num_lock")

def set_caps_lock(state: bool) -> Dict[str, Any]:
    return _set_lock_state(0x14, state, "caps_lock")

def set_scroll_lock(state: bool) -> Dict[str, Any]:
    return _set_lock_state(0x91, state, "scroll_lock")


def simulate_key_combo(modifier: str, key: str) -> Dict[str, Any]:
    """Holds modifier, presses key, releases both in correct order."""
    try:
        keyboard.press(modifier)
        time.sleep(0.01)
        keyboard.press(key)
        keyboard.release(key)
        keyboard.release(modifier)
        return _response(True, {"combo": f"{modifier}+{key}"})
    except Exception as e:
        return _response(False, error=str(e))


def create_macro(name: str, keystrokes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Saves a macro definition to memory."""
    try:
        if not isinstance(keystrokes, list):
            return _response(False, error="Keystrokes must be a list of event dicts")
        with _registry_lock:
            _macro_registry[name] = keystrokes
        return _response(True, {"name": name, "steps": len(keystrokes)})
    except Exception as e:
        return _response(False, error=str(e))


def execute_macro(name: str) -> Dict[str, Any]:
    """Runs a stored macro synchronously."""
    try:
        with _registry_lock:
            sequence = _macro_registry.get(name)
        if sequence is None:
            return _response(False, error=f"Macro '{name}' not found")
        return replay_keystrokes(sequence, speed=1.0)
    except Exception as e:
        return _response(False, error=str(e))


def save_macros(filepath: str) -> Dict[str, Any]:
    """Persists all in-memory macros to a JSON file."""
    try:
        with _registry_lock:
            snapshot = dict(_macro_registry)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        return _response(True, {"path": filepath, "saved_count": len(snapshot)})
    except Exception as e:
        return _response(False, error=str(e))


def load_macros(filepath: str) -> Dict[str, Any]:
    """Loads macros from a JSON file into memory, merging with existing."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _response(False, error="Invalid macro format: expected JSON object")
        with _registry_lock:
            _macro_registry.update(data)
        return _response(True, {"path": filepath, "loaded_count": len(data)})
    except Exception as e:
        return _response(False, error=str(e))


def block_key(key: str) -> Dict[str, Any]:
    """Prevents the OS from receiving a physical key press."""
    try:
        keyboard.block_key(key)
        return _response(True, {"key": key, "status": "blocked"})
    except Exception as e:
        return _response(False, error=str(e))


def unblock_key(key: str) -> Dict[str, Any]:
    """Restores normal OS handling for a previously blocked key."""
    try:
        keyboard.unblock_key(key)
        return _response(True, {"key": key, "status": "unblocked"})
    except Exception as e:
        return _response(False, error=str(e))


def remap_key(from_key: str, to_key: str) -> Dict[str, Any]:
    """Globally redirects input from one key to another."""
    try:
        keyboard.remap_key(from_key, to_key)
        return _response(True, {"from": from_key, "to": to_key, "status": "remapped"})
    except Exception as e:
        return _response(False, error=str(e))


def get_key_state(key: str) -> Dict[str, Any]:
    """Returns detailed state for a key (pressed status, toggle status)."""
    try:
        result: Dict[str, Any] = {"key": key}
        if platform.system() == "Windows":
            # Try to resolve to virtual key code
            try:
                sc = keyboard.key_to_scan_codes(key)[0]
                vk = ctypes.windll.user32.MapVirtualKeyW(sc, 3)  # MAPVK_VSC_TO_VK_EX
                raw = ctypes.windll.user32.GetKeyState(vk)
                result["is_pressed"] = (raw & 0x8000) != 0
                result["is_toggled"] = (raw & 0x01) != 0
                result["raw_vkey_state"] = raw
                result["vk_code"] = vk
            except Exception:
                # Fallback for special keys
                result["is_pressed"] = keyboard.is_pressed(key)
                result["is_toggled"] = False
        else:
            result["is_pressed"] = keyboard.is_pressed(key)
            result["is_toggled"] = False  # Toggle status requires OS-specific query on *nix
        return _response(True, result)
    except Exception as e:
        return _response(False, error=str(e))