#!/usr/bin/env python3
"""Screen Macro Recorder - Record and replay mouse/keyboard macros
Records all mouse movements, clicks, keyboard presses with precise timing.
Supports loop playback, speed adjustment, and conditional triggers.
"""

import time
import json
import sys
import os
import threading
import logging
import argparse
from pathlib import Path
from datetime import datetime
try:
    from pynput import mouse, keyboard
    from pynput.mouse import Button, Controller as MouseController
    from pynput.keyboard import Key, Controller as KeyboardController
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False
try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MacroRecorder")


class MacroEvent:
    """Represents a single recorded event."""
    def __init__(self, event_type, data, timestamp):
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp

    def to_dict(self):
        return {"type": self.event_type, "data": self.data, "time": self.timestamp}

    @classmethod
    def from_dict(cls, d):
        return cls(d["type"], d["data"], d["time"])


class MacroRecorder:
    """Records mouse and keyboard events with timing."""

    def __init__(self):
        if not HAS_PYNPUT:
            raise ImportError("pynput required. Install: pip install pynput")
        self.events = []
        self.recording = False
        self.start_time = 0
        self.mouse_listener = None
        self.keyboard_listener = None
        self.record_mouse_moves = False
        self.move_interval = 0.05
        self.last_move_time = 0
        self.stop_key = Key.f9

    def _get_timestamp(self):
        return round(time.time() - self.start_time, 4)

    def _on_mouse_click(self, x, y, button, pressed):
        if not self.recording:
            return
        action = "mouse_down" if pressed else "mouse_up"
        btn = "left" if button == Button.left else "right" if button == Button.right else "middle"
        event = MacroEvent(action, {"x": x, "y": y, "button": btn}, self._get_timestamp())
        self.events.append(event)
        logger.debug(f"{action} at ({x},{y}) button={btn}")

    def _on_mouse_scroll(self, x, y, dx, dy):
        if not self.recording:
            return
        event = MacroEvent("mouse_scroll", {"x": x, "y": y, "dx": dx, "dy": dy}, self._get_timestamp())
        self.events.append(event)

    def _on_mouse_move(self, x, y):
        if not self.recording or not self.record_mouse_moves:
            return
        now = time.time()
        if now - self.last_move_time >= self.move_interval:
            event = MacroEvent("mouse_move", {"x": x, "y": y}, self._get_timestamp())
            self.events.append(event)
            self.last_move_time = now

    def _on_key_press(self, key):
        if key == self.stop_key:
            self.stop_recording()
            return False
        if not self.recording:
            return
        key_str = key.char if hasattr(key, "char") and key.char else str(key)
        event = MacroEvent("key_down", {"key": key_str}, self._get_timestamp())
        self.events.append(event)

    def _on_key_release(self, key):
        if not self.recording:
            return
        key_str = key.char if hasattr(key, "char") and key.char else str(key)
        event = MacroEvent("key_up", {"key": key_str}, self._get_timestamp())
        self.events.append(event)

    def start_recording(self, record_moves=False):
        """Start recording events. Press F9 to stop."""
        self.events = []
        self.recording = True
        self.record_mouse_moves = record_moves
        self.start_time = time.time()
        self.last_move_time = 0
        self.mouse_listener = mouse.Listener(
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll,
            on_move=self._on_mouse_move
        )
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.mouse_listener.start()
        self.keyboard_listener.start()
        logger.info("Recording started. Press F9 to stop.")

    def stop_recording(self):
        """Stop recording events."""
        self.recording = False
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        logger.info(f"Recording stopped. {len(self.events)} events captured.")

    def save_macro(self, filepath):
        """Save recorded macro to file."""
        data = {
            "version": "1.0",
            "recorded_at": datetime.now().isoformat(),
            "event_count": len(self.events),
            "duration": self.events[-1].timestamp if self.events else 0,
            "events": [e.to_dict() for e in self.events]
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Macro saved to {filepath} ({len(self.events)} events)")

    def load_macro(self, filepath):
        """Load a macro from file."""
        with open(filepath, "r") as f:
            data = json.load(f)
        self.events = [MacroEvent.from_dict(e) for e in data["events"]]
        logger.info(f"Loaded macro from {filepath} ({len(self.events)} events)")


class MacroPlayer:
    """Plays back recorded macros with speed control."""

    def __init__(self):
        if not HAS_PYAUTOGUI:
            raise ImportError("pyautogui required. Install: pip install pyautogui")
        pyautogui.FAILSAFE = True
        self.playing = False
        self.paused = False

    def play(self, events, speed=1.0, loops=1, loop_delay=0.5):
        """Play back macro events."""
        self.playing = True
        logger.info(f"Playing {len(events)} events at {speed}x speed, {loops} loops")
        for loop_num in range(loops):
            if not self.playing:
                break
            if loops > 1:
                logger.info(f"Loop {loop_num + 1}/{loops}")
            prev_time = 0
            for event in events:
                if not self.playing:
                    break
                while self.paused:
                    time.sleep(0.1)
                delay = (event.timestamp - prev_time) / speed
                if delay > 0:
                    time.sleep(delay)
                prev_time = event.timestamp
                self._execute_event(event)
            if loop_num < loops - 1:
                time.sleep(loop_delay)
        self.playing = False
        logger.info("Playback complete")

    def _execute_event(self, event):
        """Execute a single macro event."""
        etype = event.event_type
        data = event.data
        if etype == "mouse_down":
            pyautogui.mouseDown(data["x"], data["y"], button=data["button"])
        elif etype == "mouse_up":
            pyautogui.mouseUp(data["x"], data["y"], button=data["button"])
        elif etype == "mouse_move":
            pyautogui.moveTo(data["x"], data["y"], duration=0.01)
        elif etype == "mouse_scroll":
            pyautogui.scroll(data["dy"], data["x"], data["y"])
        elif etype == "key_down":
            key = data["key"]
            if key.startswith("Key."):
                key_name = key.replace("Key.", "")
                pyautogui.keyDown(key_name)
            elif len(key) == 1:
                pyautogui.keyDown(key)
        elif etype == "key_up":
            key = data["key"]
            if key.startswith("Key."):
                key_name = key.replace("Key.", "")
                pyautogui.keyUp(key_name)
            elif len(key) == 1:
                pyautogui.keyUp(key)

    def stop(self):
        self.playing = False

    def pause(self):
        self.paused = True
        logger.info("Playback paused")

    def resume(self):
        self.paused = False
        logger.info("Playback resumed")


class MacroManager:
    """High-level macro management with hotkey triggers."""

    def __init__(self, macro_dir="macros"):
        self.macro_dir = Path(macro_dir)
        self.macro_dir.mkdir(parents=True, exist_ok=True)
        self.recorder = MacroRecorder()
        self.player = MacroPlayer()

    def list_macros(self):
        """List all saved macros."""
        macros = list(self.macro_dir.glob("*.json"))
        return [m.stem for m in macros]

    def record(self, name, record_moves=False):
        """Record a new macro."""
        print(f"Recording macro: {name}")
        print("Press F9 to stop recording...")
        time.sleep(2)
        self.recorder.start_recording(record_moves=record_moves)
        self.recorder.keyboard_listener.join()
        filepath = self.macro_dir / f"{name}.json"
        self.recorder.save_macro(str(filepath))
        return filepath

    def play_macro(self, name, speed=1.0, loops=1):
        """Play a saved macro by name."""
        filepath = self.macro_dir / f"{name}.json"
        if not filepath.exists():
            logger.error(f"Macro not found: {name}")
            return False
        self.recorder.load_macro(str(filepath))
        print(f"Playing macro {name} in 3 seconds...")
        time.sleep(3)
        self.player.play(self.recorder.events, speed=speed, loops=loops)
        return True

    def delete_macro(self, name):
        """Delete a saved macro."""
        filepath = self.macro_dir / f"{name}.json"
        if filepath.exists():
            filepath.unlink()
            logger.info(f"Deleted macro: {name}")
            return True
        return False

    def get_macro_info(self, name):
        """Get info about a saved macro."""
        filepath = self.macro_dir / f"{name}.json"
        if not filepath.exists():
            return None
        with open(filepath) as f:
            data = json.load(f)
        return {
            "name": name,
            "events": data["event_count"],
            "duration": f"{data['duration']:.1f}s",
            "recorded": data["recorded_at"],
            "file_size": f"{filepath.stat().st_size / 1024:.1f}KB"
        }


def main():
    parser = argparse.ArgumentParser(description="Screen Macro Recorder")
    subparsers = parser.add_subparsers(dest="command")

    rec_parser = subparsers.add_parser("record", help="Record a new macro")
    rec_parser.add_argument("name", help="Macro name")
    rec_parser.add_argument("--moves", action="store_true", help="Record mouse movements")

    play_parser = subparsers.add_parser("play", help="Play a macro")
    play_parser.add_argument("name", help="Macro name")
    play_parser.add_argument("--speed", type=float, default=1.0, help="Playback speed")
    play_parser.add_argument("--loops", type=int, default=1, help="Number of loops")

    list_parser = subparsers.add_parser("list", help="List saved macros")
    info_parser = subparsers.add_parser("info", help="Show macro info")
    info_parser.add_argument("name", help="Macro name")

    del_parser = subparsers.add_parser("delete", help="Delete a macro")
    del_parser.add_argument("name", help="Macro name")

    args = parser.parse_args()
    mgr = MacroManager()

    if args.command == "record":
        mgr.record(args.name, record_moves=args.moves)
    elif args.command == "play":
        mgr.play_macro(args.name, speed=args.speed, loops=args.loops)
    elif args.command == "list":
        macros = mgr.list_macros()
        print(f"Saved macros ({len(macros)}):")
        for m in macros:
            info = mgr.get_macro_info(m)
            print(f"  {m}: {info['events']} events, {info['duration']}")
    elif args.command == "info":
        info = mgr.get_macro_info(args.name)
        if info:
            for k, v in info.items():
                print(f"  {k}: {v}")
        else:
            print(f"Macro not found: {args.name}")
    elif args.command == "delete":
        if mgr.delete_macro(args.name):
            print(f"Deleted: {args.name}")
        else:
            print(f"Not found: {args.name}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
