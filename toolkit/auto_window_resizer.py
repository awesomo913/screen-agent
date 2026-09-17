#!/usr/bin/env python3
"""Auto Window Resizer & Layout Manager - Manage window positions and sizes via screen control."""

import os
import sys
import time
import json
import argparse
import ctypes
import ctypes.wintypes
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

import pyautogui

try:
    import win32gui
    import win32con
    import win32api
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    from pynput import keyboard
except ImportError:
    keyboard = None


@dataclass
class WindowInfo:
    """Information about a window."""
    hwnd: int
    title: str
    x: int
    y: int
    width: int
    height: int
    pid: int = 0
    exe_name: str = ""
    visible: bool = True
    minimized: bool = False
    maximized: bool = False


@dataclass
class WindowLayout:
    """A saved window layout configuration."""
    name: str
    description: str = ""
    windows: List[Dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    monitor_config: Dict = field(default_factory=dict)


class WindowManager:
    """Manages window positions, sizes, and layouts."""

    PRESET_LAYOUTS = {
        "side_by_side": [
            {"position": "left_half"},
            {"position": "right_half"}
        ],
        "quad": [
            {"position": "top_left_quarter"},
            {"position": "top_right_quarter"},
            {"position": "bottom_left_quarter"},
            {"position": "bottom_right_quarter"}
        ],
        "main_side": [
            {"position": "left_two_thirds"},
            {"position": "right_third_top"},
            {"position": "right_third_bottom"}
        ],
        "stacked": [
            {"position": "top_half"},
            {"position": "bottom_half"}
        ],
        "center_focus": [
            {"position": "center_large"}
        ],
    }

    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.expanduser("~/.window_layout_config.json")
        self.saved_layouts: Dict[str, WindowLayout] = {}
        self.screen_width, self.screen_height = pyautogui.size()
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                cfg = json.load(f)
            for name, layout_data in cfg.get("layouts", {}).items():
                self.saved_layouts[name] = WindowLayout(
                    name=name,
                    description=layout_data.get("description", ""),
                    windows=layout_data.get("windows", []),
                    created_at=layout_data.get("created_at", ""),
                    monitor_config=layout_data.get("monitor_config", {})
                )

    def save_config(self):
        cfg = {"layouts": {}}
        for name, layout in self.saved_layouts.items():
            cfg["layouts"][name] = {
                "description": layout.description,
                "windows": layout.windows,
                "created_at": layout.created_at,
                "monitor_config": layout.monitor_config
            }
        with open(self.config_path, "w") as f:
            json.dump(cfg, f, indent=2)

    def get_all_windows(self) -> List[WindowInfo]:
        windows = []
        if not HAS_WIN32:
            return self._get_windows_ctypes()

        def enum_handler(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    rect = win32gui.GetWindowRect(hwnd)
                    x, y = rect[0], rect[1]
                    w = rect[2] - rect[0]
                    h = rect[3] - rect[1]
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    except:
                        pid = 0
                    placement = win32gui.GetWindowPlacement(hwnd)
                    minimized = placement[1] == win32con.SW_SHOWMINIMIZED
                    maximized = placement[1] == win32con.SW_SHOWMAXIMIZED
                    results.append(WindowInfo(
                        hwnd=hwnd, title=title, x=x, y=y,
                        width=w, height=h, pid=pid,
                        visible=True, minimized=minimized, maximized=maximized
                    ))
            return True

        win32gui.EnumWindows(enum_handler, windows)
        return windows

    def _get_windows_ctypes(self) -> List[WindowInfo]:
        windows = []
        user32 = ctypes.windll.user32

        def callback(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    rect = ctypes.wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    windows.append(WindowInfo(
                        hwnd=hwnd, title=buff.value,
                        x=rect.left, y=rect.top,
                        width=rect.right - rect.left,
                        height=rect.bottom - rect.top
                    ))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(callback), 0)
        return windows

    def find_window(self, title_pattern) -> Optional[WindowInfo]:
        for w in self.get_all_windows():
            if title_pattern.lower() in w.title.lower():
                return w
        return None

    def find_windows(self, title_pattern) -> List[WindowInfo]:
        return [w for w in self.get_all_windows() if title_pattern.lower() in w.title.lower()]

    def move_window(self, hwnd, x, y, width=None, height=None):
        user32 = ctypes.windll.user32
        if width is None or height is None:
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            if width is None:
                width = rect.right - rect.left
            if height is None:
                height = rect.bottom - rect.top
        user32.ShowWindow(hwnd, 9)
        user32.MoveWindow(hwnd, x, y, width, height, True)
        print(f"Moved window {hwnd} to ({x},{y}) size {width}x{height}")

    def resize_window(self, hwnd, width, height):
        user32 = ctypes.windll.user32
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        user32.MoveWindow(hwnd, rect.left, rect.top, width, height, True)
        print(f"Resized window {hwnd} to {width}x{height}")

    def minimize_window(self, hwnd):
        ctypes.windll.user32.ShowWindow(hwnd, 6)

    def maximize_window(self, hwnd):
        ctypes.windll.user32.ShowWindow(hwnd, 3)

    def restore_window(self, hwnd):
        ctypes.windll.user32.ShowWindow(hwnd, 9)

    def focus_window(self, hwnd):
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)

    def close_window(self, hwnd):
        ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)

    def get_position_coords(self, position_name):
        sw, sh = self.screen_width, self.screen_height
        taskbar_h = 40
        usable_h = sh - taskbar_h
        positions = {
            "left_half": (0, 0, sw // 2, usable_h),
            "right_half": (sw // 2, 0, sw // 2, usable_h),
            "top_half": (0, 0, sw, usable_h // 2),
            "bottom_half": (0, usable_h // 2, sw, usable_h // 2),
            "top_left_quarter": (0, 0, sw // 2, usable_h // 2),
            "top_right_quarter": (sw // 2, 0, sw // 2, usable_h // 2),
            "bottom_left_quarter": (0, usable_h // 2, sw // 2, usable_h // 2),
            "bottom_right_quarter": (sw // 2, usable_h // 2, sw // 2, usable_h // 2),
            "left_third": (0, 0, sw // 3, usable_h),
            "center_third": (sw // 3, 0, sw // 3, usable_h),
            "right_third": (2 * sw // 3, 0, sw // 3, usable_h),
            "left_two_thirds": (0, 0, 2 * sw // 3, usable_h),
            "right_third_top": (2 * sw // 3, 0, sw // 3, usable_h // 2),
            "right_third_bottom": (2 * sw // 3, usable_h // 2, sw // 3, usable_h // 2),
            "center_large": (sw // 8, sh // 8, 3 * sw // 4, 3 * usable_h // 4),
            "fullscreen": (0, 0, sw, usable_h),
        }
        return positions.get(position_name, (0, 0, sw // 2, usable_h))

    def apply_position(self, hwnd, position_name):
        x, y, w, h = self.get_position_coords(position_name)
        self.restore_window(hwnd)
        time.sleep(0.1)
        self.move_window(hwnd, x, y, w, h)

    def tile_windows(self, title_patterns, layout_name="side_by_side"):
        layout = self.PRESET_LAYOUTS.get(layout_name, self.PRESET_LAYOUTS["side_by_side"])
        matched = []
        for pattern in title_patterns:
            win = self.find_window(pattern)
            if win:
                matched.append(win)
        for i, win in enumerate(matched):
            if i < len(layout):
                pos = layout[i]["position"]
                self.apply_position(win.hwnd, pos)
                time.sleep(0.2)
        print(f"Tiled {len(matched)} windows using '{layout_name}' layout")

    def save_current_layout(self, name, description=""):
        windows = self.get_all_windows()
        layout = WindowLayout(
            name=name, description=description,
            monitor_config={"width": self.screen_width, "height": self.screen_height}
        )
        for w in windows:
            if w.width > 50 and w.height > 50 and not w.minimized:
                layout.windows.append({
                    "title": w.title, "x": w.x, "y": w.y,
                    "width": w.width, "height": w.height,
                    "minimized": w.minimized, "maximized": w.maximized
                })
        self.saved_layouts[name] = layout
        self.save_config()
        print(f"Saved layout '{name}' with {len(layout.windows)} windows")

    def restore_layout(self, name):
        layout = self.saved_layouts.get(name)
        if not layout:
            print(f"Layout '{name}' not found")
            return
        for wdata in layout.windows:
            win = self.find_window(wdata["title"])
            if win:
                if wdata.get("maximized"):
                    self.maximize_window(win.hwnd)
                elif wdata.get("minimized"):
                    self.minimize_window(win.hwnd)
                else:
                    self.move_window(win.hwnd, wdata["x"], wdata["y"], wdata["width"], wdata["height"])
                time.sleep(0.1)
        print(f"Restored layout '{name}'")

    def cascade_windows(self, title_patterns=None):
        if title_patterns:
            windows = []
            for p in title_patterns:
                w = self.find_window(p)
                if w:
                    windows.append(w)
        else:
            windows = [w for w in self.get_all_windows() if w.width > 100 and w.height > 100]
        offset = 30
        base_w = self.screen_width * 2 // 3
        base_h = self.screen_height * 2 // 3
        for i, w in enumerate(windows):
            x = offset * i
            y = offset * i
            self.move_window(w.hwnd, x, y, base_w, base_h)
            time.sleep(0.1)
        print(f"Cascaded {len(windows)} windows")

    def minimize_all_except(self, keep_title):
        for w in self.get_all_windows():
            if keep_title.lower() not in w.title.lower() and w.width > 100:
                self.minimize_window(w.hwnd)
                time.sleep(0.05)

    def setup_hotkeys(self):
        if not keyboard:
            print("pynput not installed, hotkeys disabled")
            return
        print("Hotkeys active:")
        print("  Ctrl+Alt+1: Side by side")
        print("  Ctrl+Alt+2: Quad layout")
        print("  Ctrl+Alt+3: Main + sidebar")
        print("  Ctrl+Alt+S: Save layout")
        print("  Ctrl+Alt+R: Restore layout")
        print("  ESC: Exit")

        current_keys = set()

        def on_press(key):
            current_keys.add(key)
            try:
                if (keyboard.Key.ctrl_l in current_keys and
                    keyboard.Key.alt_l in current_keys):
                    if hasattr(key, 'char'):
                        if key.char == '1':
                            self.tile_windows([], "side_by_side")
                        elif key.char == '2':
                            self.tile_windows([], "quad")
                        elif key.char == '3':
                            self.tile_windows([], "main_side")
                        elif key.char == 's':
                            self.save_current_layout("quick_save")
                        elif key.char == 'r':
                            self.restore_layout("quick_save")
                if key == keyboard.Key.esc:
                    return False
            except Exception:
                pass

        def on_release(key):
            current_keys.discard(key)

        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()


def main():
    parser = argparse.ArgumentParser(description="Auto Window Resizer & Layout Manager")
    parser.add_argument("--config", help="Config file path")
    subparsers = parser.add_subparsers(dest="command")

    list_p = subparsers.add_parser("list", help="List all visible windows")
    list_p.add_argument("--filter", help="Filter by title pattern")

    move_p = subparsers.add_parser("move", help="Move a window")
    move_p.add_argument("title", help="Window title pattern")
    move_p.add_argument("--x", type=int, required=True)
    move_p.add_argument("--y", type=int, required=True)
    move_p.add_argument("--width", type=int)
    move_p.add_argument("--height", type=int)

    pos_p = subparsers.add_parser("position", help="Position a window")
    pos_p.add_argument("title", help="Window title pattern")
    pos_p.add_argument("preset", help="Position preset name")

    tile_p = subparsers.add_parser("tile", help="Tile windows")
    tile_p.add_argument("titles", nargs="*", help="Window title patterns")
    tile_p.add_argument("--layout", default="side_by_side", help="Layout name")

    save_p = subparsers.add_parser("save-layout", help="Save current layout")
    save_p.add_argument("name", help="Layout name")
    save_p.add_argument("--desc", default="", help="Description")

    restore_p = subparsers.add_parser("restore-layout", help="Restore a saved layout")
    restore_p.add_argument("name", help="Layout name")

    layouts_p = subparsers.add_parser("layouts", help="List saved layouts")

    cascade_p = subparsers.add_parser("cascade", help="Cascade windows")
    cascade_p.add_argument("titles", nargs="*", help="Window title patterns")

    focus_p = subparsers.add_parser("focus", help="Focus a window")
    focus_p.add_argument("title", help="Window title pattern")

    minimize_p = subparsers.add_parser("minimize-except", help="Minimize all except matching")
    minimize_p.add_argument("title", help="Window title to keep")

    hotkeys_p = subparsers.add_parser("hotkeys", help="Start hotkey listener")

    presets_p = subparsers.add_parser("presets", help="List position presets")

    args = parser.parse_args()
    mgr = WindowManager(config_path=args.config if hasattr(args, 'config') else None)

    if args.command == "list":
        for w in mgr.get_all_windows():
            if args.filter and args.filter.lower() not in w.title.lower():
                continue
            state = "MIN" if w.minimized else ("MAX" if w.maximized else "NRM")
            print(f"  [{state}] {w.title[:60]:<60} ({w.x},{w.y}) {w.width}x{w.height} hwnd={w.hwnd}")
    elif args.command == "move":
        win = mgr.find_window(args.title)
        if win:
            mgr.move_window(win.hwnd, args.x, args.y, args.width, args.height)
        else:
            print(f"Window '{args.title}' not found")
    elif args.command == "position":
        win = mgr.find_window(args.title)
        if win:
            mgr.apply_position(win.hwnd, args.preset)
        else:
            print(f"Window '{args.title}' not found")
    elif args.command == "tile":
        mgr.tile_windows(args.titles, args.layout)
    elif args.command == "save-layout":
        mgr.save_current_layout(args.name, args.desc)
    elif args.command == "restore-layout":
        mgr.restore_layout(args.name)
    elif args.command == "layouts":
        for name, layout in mgr.saved_layouts.items():
            print(f"  {name}: {layout.description} ({len(layout.windows)} windows, {layout.created_at})")
    elif args.command == "cascade":
        mgr.cascade_windows(args.titles if args.titles else None)
    elif args.command == "focus":
        win = mgr.find_window(args.title)
        if win:
            mgr.focus_window(win.hwnd)
        else:
            print(f"Window '{args.title}' not found")
    elif args.command == "minimize-except":
        mgr.minimize_all_except(args.title)
    elif args.command == "hotkeys":
        mgr.setup_hotkeys()
    elif args.command == "presets":
        print("Available position presets:")
        for name in sorted(mgr.get_position_coords.__code__.co_consts):
            if isinstance(name, str) and "_" in name:
                print(f"  {name}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
