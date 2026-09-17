"""
mouse_actions.py
Production-ready screen agent toolkit for advanced mouse control.
"""

import pyautogui
from pynput import mouse
import ctypes
import time
import math
import random
import threading
import json
import platform
from typing import Dict, Any, List, Tuple, Optional

# Global configuration for agent responsiveness
pyautogui.FAILSAFE = False  # Disable corner fail-safe for uninterrupted automation
pyautogui.PAUSE = 0.0       # Remove inter-action delays


def _result(success: bool, message: str, data: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
    """Standardized response dictionary generator."""
    return {
        "success": success,
        "message": message,
        "data": data,
        "error": error
    }


def move_to(x: float, y: float, duration: float = 0.5) -> Dict[str, Any]:
    """Move mouse to absolute coordinates."""
    try:
        pyautogui.moveTo(x, y, duration=duration)
        return _result(True, f"Moved to ({x}, {y}) in {duration}s")
    except Exception as e:
        return _result(False, "Failed to move mouse", error=str(e))


def click(x: float, y: float, button: str = "left") -> Dict[str, Any]:
    """Click at absolute coordinates with specified button."""
    try:
        pyautogui.click(x, y, button=button)
        return _result(True, f"Clicked {button} at ({x}, {y})")
    except Exception as e:
        return _result(False, "Failed to click", error=str(e))


def double_click(x: float, y: float) -> Dict[str, Any]:
    """Double-click at absolute coordinates."""
    try:
        pyautogui.doubleClick(x, y)
        return _result(True, f"Double-clicked at ({x}, {y})")
    except Exception as e:
        return _result(False, "Failed to double-click", error=str(e))


def right_click(x: float, y: float) -> Dict[str, Any]:
    """Right-click at absolute coordinates."""
    try:
        pyautogui.rightClick(x, y)
        return _result(True, f"Right-clicked at ({x}, {y})")
    except Exception as e:
        return _result(False, "Failed to right-click", error=str(e))


def middle_click(x: float, y: float) -> Dict[str, Any]:
    """Middle-click at absolute coordinates."""
    try:
        pyautogui.middleClick(x, y)
        return _result(True, f"Middle-clicked at ({x}, {y})")
    except Exception as e:
        return _result(False, "Failed to middle-click", error=str(e))


def drag_to(start_x: float, start_y: float, end_x: float, end_y: float, duration: float = 0.5) -> Dict[str, Any]:
    """Drag from start coordinates to end coordinates."""
    try:
        pyautogui.moveTo(start_x, start_y, duration=0)
        pyautogui.dragTo(end_x, end_y, duration=duration)
        return _result(True, f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})")
    except Exception as e:
        return _result(False, "Failed to drag", error=str(e))


def scroll(amount: int, x: Optional[float] = None, y: Optional[float] = None) -> Dict[str, Any]:
    """Scroll vertically at specific coordinates (or current position)."""
    try:
        pyautogui.scroll(amount, x, y)
        pos = (x, y) if x is not None and y is not None else "current"
        return _result(True, f"Scrolled vertical {amount} at {pos}")
    except Exception as e:
        return _result(False, "Vertical scroll failed", error=str(e))


def scroll_horizontal(amount: int, x: Optional[float] = None, y: Optional[float] = None) -> Dict[str, Any]:
    """Scroll horizontally at specific coordinates."""
    try:
        pyautogui.hscroll(amount, x, y)
        pos = (x, y) if x is not None and y is not None else "current"
        return _result(True, f"Scrolled horizontal {amount} at {pos}")
    except Exception as e:
        return _result(False, "Horizontal scroll failed", error=str(e))


def get_position() -> Dict[str, Any]:
    """Get current mouse coordinates."""
    try:
        pos = pyautogui.position()
        return _result(True, "Position retrieved", data={"x": pos.x, "y": pos.y})
    except Exception as e:
        return _result(False, "Failed to get position", error=str(e))


def move_relative(dx: float, dy: float, duration: float = 0.5) -> Dict[str, Any]:
    """Move mouse relative to current position."""
    try:
        pyautogui.move(dx, dy, duration=duration)
        return _result(True, f"Moved relatively ({dx}, {dy}) in {duration}s")
    except Exception as e:
        return _result(False, "Failed to move relatively", error=str(e))


def click_and_hold(x: float, y: float, button: str = "left") -> Dict[str, Any]:
    """Press mouse button at specified location without releasing."""
    try:
        pyautogui.moveTo(x, y, duration=0.0)
        pyautogui.mouseDown(button=button)
        return _result(True, f"Mouse {button} pressed at ({x}, {y})")
    except Exception as e:
        return _result(False, "Failed to click and hold", error=str(e))


def release(x: Optional[float] = None, y: Optional[float] = None, button: str = "left") -> Dict[str, Any]:
    """Release mouse button at specified location."""
    try:
        pyautogui.mouseUp(x, y, button=button)
        return _result(True, f"Mouse {button} released")
    except Exception as e:
        return _result(False, "Failed to release mouse", error=str(e))


def hover(x: float, y: float, duration: float = 0.5) -> Dict[str, Any]:
    """Hover over coordinates with optional duration."""
    try:
        pyautogui.moveTo(x, y, duration=duration)
        return _result(True, f"Hovered at ({x}, {y}) for {duration}s")
    except Exception as e:
        return _result(False, "Failed to hover", error=str(e))


def smooth_move(x: float, y: float, speed: float = 500.0) -> Dict[str, Any]:
    """Smoothly move to target using distance/speed calculation with easing."""
    try:
        start = pyautogui.position()
        dist = math.hypot(x - start.x, y - start.y)
        duration = dist / speed if speed > 0 else 0.0
        pyautogui.moveTo(x, y, duration=duration)
        return _result(True, f"Smooth moved to ({x}, {y}) at {speed} px/s")
    except Exception as e:
        return _result(False, "Failed smooth move", error=str(e))


def bezier_move(x: float, y: float, control_points: List[Tuple[float, float]], duration: float = 0.5) -> Dict[str, Any]:
    """Move along a Bezier curve defined by control points."""
    try:
        if not control_points:
            return _result(False, "Control points required", error="Empty control_points list")
            
        start = pyautogui.position()
        points = [start] + control_points + [pyautogui.Point(x, y)]
        n = len(points) - 1
        steps = max(50, int(duration * 100))
        dt = 1.0 / steps
        
        def binomial(n: int, k: int) -> int:
            return math.factorial(n) // (math.factorial(k) * math.factorial(n - k))

        def evaluate_bezier(t: float) -> Tuple[float, float]:
            bx, by = 0.0, 0.0
            for i, (px, py) in enumerate(points):
                coeff = binomial(n, i) * ((1 - t) ** (n - i)) * (t ** i)
                bx += px * coeff
                by += py * coeff
            return bx, by

        for i in range(1, steps + 1):
            t = i * dt
            tx, ty = evaluate_bezier(t)
            pyautogui.moveTo(tx, ty, duration=0)
            time.sleep(duration / steps)
            
        return _result(True, f"Bezier moved to ({x}, {y}) with {n} segments")
    except Exception as e:
        return _result(False, "Failed bezier move", error=str(e))


def random_move(x: float, y: float, jitter: float = 10.0) -> Dict[str, Any]:
    """Move to target with randomized human-like jitter."""
    try:
        steps = random.randint(5, 12)
        sx, sy = pyautogui.position()
        dx, dy = x - sx, y - sy
        
        step_x = dx / steps
        step_y = dy / steps
        
        for _ in range(steps):
            jx = random.uniform(-jitter, jitter)
            jy = random.uniform(-jitter, jitter)
            pyautogui.moveRel(step_x + jx, step_y + jy, duration=0.0)
            time.sleep(random.uniform(0.005, 0.02))
            
        pyautogui.moveTo(x, y, duration=0)
        return _result(True, f"Jitter move to ({x}, {y})")
    except Exception as e:
        return _result(False, "Failed random move", error=str(e))


def triple_click(x: float, y: float) -> Dict[str, Any]:
    """Triple-click at specified coordinates."""
    try:
        pyautogui.click(x, y, clicks=3, interval=0.1)
        return _result(True, f"Triple-clicked at ({x}, {y})")
    except Exception as e:
        return _result(False, "Failed triple-click", error=str(e))


def mouse_down(x: float, y: float, button: str = "left") -> Dict[str, Any]:
    """Press mouse button at coordinates."""
    try:
        pyautogui.mouseDown(x, y, button=button)
        return _result(True, f"Mouse {button} down at ({x}, {y})")
    except Exception as e:
        return _result(False, "Failed mouse down", error=str(e))


def mouse_up(x: float, y: float, button: str = "left") -> Dict[str, Any]:
    """Release mouse button at coordinates."""
    try:
        pyautogui.mouseUp(x, y, button=button)
        return _result(True, f"Mouse {button} up at ({x}, {y})")
    except Exception as e:
        return _result(False, "Failed mouse up", error=str(e))


def get_screen_size() -> Dict[str, Any]:
    """Get primary monitor resolution."""
    try:
        size = pyautogui.size()
        return _result(True, "Screen size retrieved", data={"width": size.width, "height": size.height})
    except Exception as e:
        return _result(False, "Failed to get screen size", error=str(e))


def set_mouse_speed(speed: float) -> Dict[str, Any]:
    """Set OS-level mouse pointer speed (Windows: 0-20)."""
    sys = platform.system()
    try:
        if sys == "Windows":
            # SPI_SETMOUSESPEED = 0x0071, SPIF_UPDATEINIFILE = 0x01
            ctypes.windll.user32.SystemParametersInfoW(0x0071, 0, int(speed), 0x01)
            return _result(True, f"Mouse speed set to {speed} (Windows)")
        elif sys == "Darwin":
            # macOS uses defaults write for mouse scaling
            import subprocess
            scaled = speed / 10.0 if speed > 1 else speed
            subprocess.run(["defaults", "write", "NSGlobalDomain", "com.apple.mouse.scaling", str(scaled)], check=True)
            return _result(True, f"Mouse speed set to {speed} (macOS)")
        elif sys == "Linux":
            import subprocess
            subprocess.run(["xset", "m", str(speed)], check=True)
            return _result(True, f"Mouse speed set to {speed} (Linux)")
        return _result(False, "Unsupported platform for speed control")
    except Exception as e:
        return _result(False, "Failed to set mouse speed", error=str(e))


def _get_cursor_handle() -> Optional[bool]:
    """Platform-aware cursor show/hide via ctypes."""
    sys = platform.system()
    if sys == "Windows":
        return ctypes.windll.user32.ShowCursor
    return None


def hide_cursor() -> Dict[str, Any]:
    """Hide the system mouse cursor."""
    try:
        sys = platform.system()
        if sys == "Windows":
            ctypes.windll.user32.ShowCursor(False)
            return _result(True, "Cursor hidden (Windows)")
        elif sys == "Linux":
            import subprocess
            subprocess.run(["xsetroot", "-cursor_name", "left_ptr"], check=True)
            return _result(True, "Cursor hidden (Linux)")
        return _result(False, "Cursor hide not fully supported on this platform without GUI framework")
    except Exception as e:
        return _result(False, "Failed to hide cursor", error=str(e))


def show_cursor() -> Dict[str, Any]:
    """Show the system mouse cursor."""
    try:
        sys = platform.system()
        if sys == "Windows":
            # Ensure counter goes positive by looping
            while ctypes.windll.user32.ShowCursor(True) < 0:
                pass
            return _result(True, "Cursor shown (Windows)")
        elif sys == "Linux":
            import subprocess
            subprocess.run(["xsetroot", "-cursor_name", "left_ptr"], check=True)
            return _result(True, "Cursor shown (Linux)")
        return _result(False, "Cursor show not fully supported on this platform without GUI framework")
    except Exception as e:
        return _result(False, "Failed to show cursor", error=str(e))


def record_mouse(duration: float) -> Dict[str, Any]:
    """Record mouse movements and clicks for a set duration."""
    events = []
    start_time = time.time()
    lock = threading.Lock()
    listen_stop = threading.Event()

    def on_move(x: int, y: int):
        if not listen_stop.is_set():
            t = time.time() - start_time
            with lock:
                events.append({"t": t, "type": "move", "x": x, "y": y})
                
    def on_click(x: int, y: int, button: mouse.Button, pressed: bool):
        if not listen_stop.is_set():
            t = time.time() - start_time
            with lock:
                events.append({
                    "t": t, "type": "click", 
                    "x": x, "y": y, 
                    "button": button.name, 
                    "pressed": pressed
                })

    def on_scroll(x: int, y: int, dx: int, dy: int):
        if not listen_stop.is_set():
            t = time.time() - start_time
            with lock:
                events.append({
                    "t": t, "type": "scroll", 
                    "x": x, "y": y, 
                    "dx": dx, "dy": dy
                })

    try:
        with mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll) as listener:
            timer = threading.Thread(target=lambda: (time.sleep(duration), listen_stop.set()), daemon=True)
            timer.start()
            listener.join()
            
        events.sort(key=lambda e: e["t"])
        return _result(True, f"Recorded {len(events)} events over {duration}s", data=events)
    except Exception as e:
        return _result(False, "Recording failed", error=str(e))


def replay_mouse(recording: List[Dict[str, Any]], speed: float = 1.0) -> Dict[str, Any]:
    """Replay a recorded mouse trajectory."""
    try:
        if not recording:
            return _result(False, "Empty recording provided", error="No events to replay")
            
        sorted_events = sorted(recording, key=lambda e: e.get("t", 0))
        base_t0 = sorted_events[0]["t"]
        last_t = base_t0
        
        for event in sorted_events:
            delay = (event["t"] - last_t) / speed if speed > 0 else 0.0
            if delay > 0:
                time.sleep(delay)
            last_t = event["t"]
            
            etype = event.get("type")
            if etype == "move":
                pyautogui.moveTo(event["x"], event["y"], duration=0)
            elif etype == "click" and event.get("pressed", False):
                btn = event.get("button", "left")
                pyautogui.moveTo(event["x"], event["y"], duration=0)
                pyautogui.click(event["x"], event["y"], button=btn)
            elif etype == "scroll":
                pyautogui.moveRel(0, 0)  # ensure focus
                if event.get("dy", 0) != 0:
                    pyautogui.scroll(event["dy"], event.get("x"), event.get("y"))
                if event.get("dx", 0) != 0:
                    pyautogui.hscroll(event["dx"], event.get("x"), event.get("y"))
                    
        return _result(True, f"Replayed {len(sorted_events)} events at {speed}x speed")
    except Exception as e:
        return _result(False, "Replay failed", error=str(e))