#!/usr/bin/env python3
"""
139_desktop_hotkey_manager.py
Screen-control hotkey manager: registers global hotkeys, triggers scripts,
manages key bindings, records macros, and shows live shortcut overlay.
"""

import pyautogui
import argparse
import time
import os
import re
import json
import threading
import logging
import subprocess
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Callable
from datetime import datetime
from pathlib import Path
import win32gui
import win32con
import win32api
import tkinter as tk
from tkinter import ttk, simpledialog
from pynput import keyboard as pynput_kb

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

DATA_DIR = Path.home() / "HotkeyManagerData"
DATA_DIR.mkdir(exist_ok=True)

MODIFIER_NAMES = {
    pynput_kb.Key.ctrl_l: "ctrl",
    pynput_kb.Key.ctrl_r: "ctrl",
    pynput_kb.Key.alt_l: "alt",
    pynput_kb.Key.alt_r: "alt",
    pynput_kb.Key.shift_l: "shift",
    pynput_kb.Key.shift_r: "shift",
    pynput_kb.Key.cmd: "win",
}

@dataclass
class HotkeyBinding:
    binding_id: str
    hotkey: str
    action_type: str
    action_value: str
    description: str = ""
    enabled: bool = True
    trigger_count: int = 0
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    last_triggered: str = ""

@dataclass
class MacroStep:
    step_type: str
    value: str
    delay: float = 0.1
    x: int = 0
    y: int = 0

@dataclass
class Macro:
    macro_id: str
    name: str
    steps: List[MacroStep]
    description: str = ""
    hotkey: str = ""
    created: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class HotkeyEvent:
    hotkey: str
    action_type: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = True

class ActionExecutor:
    def execute(self, binding: HotkeyBinding) -> bool:
        action_type = binding.action_type
        value = binding.action_value
        try:
            if action_type == "type_text":
                pyautogui.typewrite(value, interval=0.04)
            elif action_type == "hotkey":
                keys = value.split("+")
                pyautogui.hotkey(*keys)
            elif action_type == "run_command":
                subprocess.Popen(value, shell=True)
            elif action_type == "open_file":
                subprocess.Popen(["start", "", value], shell=True)
            elif action_type == "open_url":
                subprocess.Popen(["start", value], shell=True)
            elif action_type == "click":
                parts = value.split(",")
                if len(parts) >= 2:
                    x, y = int(parts[0]), int(parts[1])
                    pyautogui.click(x, y)
            elif action_type == "screenshot":
                from PIL import ImageGrab
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                out = Path(value) if value else DATA_DIR / f"screenshot_{ts}.png"
                ImageGrab.grab().save(out)
                log.info(f"Screenshot saved: {out}")
            elif action_type == "show_window":
                self._bring_window_to_front(value)
            elif action_type == "paste_clipboard":
                pyautogui.hotkey('ctrl', 'v')
            elif action_type == "scroll":
                parts = value.split(",")
                amount = int(parts[0]) if parts else 3
                pyautogui.scroll(amount)
            elif action_type == "minimize_all":
                pyautogui.hotkey('win', 'd')
            elif action_type == "lock_screen":
                subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
            elif action_type == "sleep_pc":
                subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState 0,1,0"])
            elif action_type == "volume":
                if value == "up":
                    pyautogui.press('volumeup')
                elif value == "down":
                    pyautogui.press('volumedown')
                elif value == "mute":
                    pyautogui.press('volumemute')
            elif action_type == "python_script":
                if Path(value).exists():
                    subprocess.Popen(["python", value])
                else:
                    exec(value)
            return True
        except Exception as e:
            log.error(f"Action execution error ({action_type}={value}): {e}")
            return False

    def _bring_window_to_front(self, title_pattern: str):
        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if title_pattern.lower() in t.lower():
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                    return False
        win32gui.EnumWindows(cb, None)

class MacroRunner:
    def run(self, macro: Macro):
        log.info(f"Running macro: {macro.name} ({len(macro.steps)} steps)")
        for i, step in enumerate(macro.steps):
            log.debug(f"Step {i+1}: {step.step_type} = {step.value}")
            try:
                if step.step_type == "type":
                    pyautogui.typewrite(step.value, interval=0.04)
                elif step.step_type == "key":
                    keys = step.value.split("+")
                    if len(keys) > 1:
                        pyautogui.hotkey(*keys)
                    else:
                        pyautogui.press(step.value)
                elif step.step_type == "click":
                    pyautogui.click(step.x, step.y)
                elif step.step_type == "right_click":
                    pyautogui.rightClick(step.x, step.y)
                elif step.step_type == "move":
                    pyautogui.moveTo(step.x, step.y, duration=0.2)
                elif step.step_type == "scroll":
                    pyautogui.scroll(int(step.value) if step.value else 3)
                elif step.step_type == "delay":
                    time.sleep(float(step.value) if step.value else 0.5)
                elif step.step_type == "run":
                    subprocess.Popen(step.value, shell=True)
            except Exception as e:
                log.error(f"Macro step error: {e}")
            if step.delay > 0:
                time.sleep(step.delay)

class MacroRecorder:
    def __init__(self):
        self._steps: List[MacroStep] = []
        self._recording = False
        self._last_key_time = 0
        self._mouse_listener = None
        self._key_listener = None

    def start(self) -> List[MacroStep]:
        self._steps = []
        self._recording = True
        self._last_key_time = time.time()
        from pynput import mouse as pm
        def on_click(x, y, button, pressed):
            if self._recording and pressed:
                delay = time.time() - self._last_key_time
                self._steps.append(MacroStep("click", "", min(delay, 2.0), x, y))
                self._last_key_time = time.time()
        def on_press(key):
            if not self._recording:
                return False
            try:
                delay = time.time() - self._last_key_time
                if hasattr(key, 'char') and key.char:
                    self._steps.append(MacroStep("type", key.char, min(delay, 2.0)))
                else:
                    name = key.name if hasattr(key, 'name') else str(key)
                    self._steps.append(MacroStep("key", name, min(delay, 2.0)))
                self._last_key_time = time.time()
            except Exception:
                pass
        self._mouse_listener = pm.Listener(on_click=on_click)
        self._key_listener = pynput_kb.Listener(on_press=on_press)
        self._mouse_listener.start()
        self._key_listener.start()
        return self._steps

    def stop(self) -> List[MacroStep]:
        self._recording = False
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._key_listener:
            self._key_listener.stop()
        return self._steps

class HotkeyStorage:
    def __init__(self):
        self.path = DATA_DIR / "hotkeys.json"
        self.bindings: Dict[str, HotkeyBinding] = {}
        self._load_defaults()
        self._load()

    def _load_defaults(self):
        defaults = [
            HotkeyBinding("screenshot_hk", "ctrl+shift+s", "screenshot", "",
                          "Take screenshot", True),
            HotkeyBinding("notepad_hk", "ctrl+alt+n", "run_command", "notepad.exe",
                          "Open Notepad", True),
            HotkeyBinding("lock_hk", "ctrl+alt+l", "lock_screen", "",
                          "Lock screen", True),
            HotkeyBinding("minim_hk", "ctrl+alt+m", "minimize_all", "",
                          "Minimize all windows", True),
        ]
        for b in defaults:
            self.bindings[b.binding_id] = b

    def _load(self):
        if self.path.exists():
            with open(self.path) as f:
                data = json.load(f)
            for bid, bd in data.items():
                self.bindings[bid] = HotkeyBinding(**bd)

    def _save(self):
        with open(self.path, 'w') as f:
            json.dump({k: asdict(v) for k, v in self.bindings.items()}, f, indent=2)

    def add(self, binding: HotkeyBinding):
        self.bindings[binding.binding_id] = binding
        self._save()

    def delete(self, bid: str):
        if bid in self.bindings:
            del self.bindings[bid]
            self._save()

    def toggle(self, bid: str) -> bool:
        if bid in self.bindings:
            self.bindings[bid].enabled = not self.bindings[bid].enabled
            self._save()
            return self.bindings[bid].enabled
        return False

    def list_all(self):
        print(f"{'ID':<18} {'Hotkey':<18} {'Action':<16} {'Value':<24} {'Enabled'}")
        print("-" * 80)
        for bid, b in self.bindings.items():
            enabled = "yes" if b.enabled else "no"
            print(f"{bid:<18} {b.hotkey:<18} {b.action_type:<16} "
                  f"{b.action_value[:23]:<24} {enabled}")

class MacroStorage:
    def __init__(self):
        self.path = DATA_DIR / "macros.json"
        self.macros: Dict[str, Macro] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path) as f:
                data = json.load(f)
            for mid, md in data.items():
                steps = [MacroStep(**s) for s in md.pop('steps', [])]
                m = Macro(**md)
                m.steps = steps
                self.macros[mid] = m

    def _save(self):
        with open(self.path, 'w') as f:
            json.dump({k: asdict(v) for k, v in self.macros.items()}, f, indent=2)

    def add(self, macro: Macro):
        self.macros[macro.macro_id] = macro
        self._save()

    def get(self, mid: str) -> Optional[Macro]:
        return self.macros.get(mid)

    def list_all(self):
        print(f"{'ID':<20} {'Name':<24} {'Steps':<8} {'Hotkey'}")
        print("-" * 60)
        for mid, m in self.macros.items():
            print(f"{mid:<20} {m.name:<24} {len(m.steps):<8} {m.hotkey or '-'}")

class GlobalHotkeyDaemon:
    def __init__(self, storage: HotkeyStorage, macro_storage: MacroStorage):
        self.storage = storage
        self.macro_storage = macro_storage
        self.executor = ActionExecutor()
        self.macro_runner = MacroRunner()
        self._active_mods: set = set()
        self._stop = threading.Event()
        self._listener: Optional[pynput_kb.Listener] = None
        self.event_log: List[HotkeyEvent] = []

    def _parse_hotkey(self, hotkey: str) -> Tuple[set, str]:
        parts = hotkey.lower().split("+")
        mods = set()
        key = ""
        for p in parts:
            if p in ("ctrl", "control"):
                mods.add("ctrl")
            elif p in ("alt", "menu"):
                mods.add("alt")
            elif p in ("shift",):
                mods.add("shift")
            elif p in ("win", "cmd", "super"):
                mods.add("win")
            else:
                key = p
        return mods, key

    def _get_mod_name(self, key) -> Optional[str]:
        return MODIFIER_NAMES.get(key)

    def _get_key_name(self, key) -> str:
        if hasattr(key, 'char') and key.char:
            return key.char.lower()
        if hasattr(key, 'name'):
            return key.name.lower()
        return str(key).lower()

    def _on_press(self, key):
        mod = self._get_mod_name(key)
        if mod:
            self._active_mods.add(mod)
            return
        key_name = self._get_key_name(key)
        for binding in self.storage.bindings.values():
            if not binding.enabled:
                continue
            req_mods, req_key = self._parse_hotkey(binding.hotkey)
            if self._active_mods >= req_mods and key_name == req_key:
                log.info(f"Hotkey triggered: {binding.hotkey} -> {binding.action_type}")
                binding.trigger_count += 1
                binding.last_triggered = datetime.now().isoformat()
                self.storage._save()
                t = threading.Thread(target=self.executor.execute, args=(binding,), daemon=True)
                t.start()
                self.event_log.append(HotkeyEvent(binding.hotkey, binding.action_type))

    def _on_release(self, key):
        mod = self._get_mod_name(key)
        if mod:
            self._active_mods.discard(mod)

    def start(self):
        log.info("Hotkey daemon started")
        self._listener = pynput_kb.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self._listener.start()
        self._stop.wait()
        self._listener.stop()

    def stop(self):
        self._stop.set()

from typing import Tuple

class HotkeyManagerGUI:
    def __init__(self, storage: HotkeyStorage, macro_storage: MacroStorage):
        self.storage = storage
        self.macro_storage = macro_storage
        self.root = tk.Tk()
        self.root.title("Hotkey Manager")
        self.root.geometry("760x460")
        self.root.configure(bg="#1a1a2e")
        self._build_ui()

    def _build_ui(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self._build_hotkeys_tab(nb)
        self._build_macros_tab(nb)
        self._build_log_tab(nb)

    def _build_hotkeys_tab(self, nb):
        frame = tk.Frame(nb, bg="#1a1a2e")
        nb.add(frame, text="Hotkeys")
        cols = ("ID","Hotkey","Action","Value","Enabled","Triggers")
        self.hk_tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)
        widths = [110,110,100,170,60,60]
        for col, w in zip(cols, widths):
            self.hk_tree.heading(col, text=col)
            self.hk_tree.column(col, width=w)
        self.hk_tree.pack(fill="both", expand=True, padx=4, pady=4)
        btn_f = tk.Frame(frame, bg="#1a1a2e")
        btn_f.pack(fill="x", padx=4, pady=2)
        tk.Button(btn_f, text="Toggle Enable", command=self._toggle_hk,
                  bg="#444", fg="white", font=("Arial",9)).pack(side="left", padx=2)
        tk.Button(btn_f, text="Delete", command=self._delete_hk,
                  bg="#883333", fg="white", font=("Arial",9)).pack(side="left", padx=2)
        tk.Button(btn_f, text="Refresh", command=self._refresh_hk,
                  bg="#226622", fg="white", font=("Arial",9)).pack(side="left", padx=2)
        self._refresh_hk()

    def _build_macros_tab(self, nb):
        frame = tk.Frame(nb, bg="#1a1a2e")
        nb.add(frame, text="Macros")
        cols = ("ID","Name","Steps","Hotkey")
        self.mac_tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)
        for col in cols:
            self.mac_tree.heading(col, text=col)
            self.mac_tree.column(col, width=160)
        self.mac_tree.pack(fill="both", expand=True, padx=4, pady=4)
        btn_f = tk.Frame(frame, bg="#1a1a2e")
        btn_f.pack(fill="x", padx=4)
        tk.Button(btn_f, text="Run Selected", command=self._run_macro,
                  bg="#336633", fg="white", font=("Arial",9)).pack(side="left", padx=2)
        tk.Button(btn_f, text="Refresh", command=self._refresh_macros,
                  bg="#226622", fg="white", font=("Arial",9)).pack(side="left", padx=2)
        self._refresh_macros()

    def _build_log_tab(self, nb):
        frame = tk.Frame(nb, bg="#1a1a2e")
        nb.add(frame, text="Event Log")
        self.log_text = tk.Text(frame, bg="#111", fg="#aaa", font=("Courier",9), state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _refresh_hk(self):
        self.hk_tree.delete(*self.hk_tree.get_children())
        for bid, b in self.storage.bindings.items():
            self.hk_tree.insert("", "end", values=(
                bid, b.hotkey, b.action_type,
                b.action_value[:22], "yes" if b.enabled else "no",
                b.trigger_count
            ))

    def _refresh_macros(self):
        self.mac_tree.delete(*self.mac_tree.get_children())
        for mid, m in self.macro_storage.macros.items():
            self.mac_tree.insert("", "end", values=(mid, m.name, len(m.steps), m.hotkey or "-"))

    def _toggle_hk(self):
        sel = self.hk_tree.selection()
        if sel:
            bid = self.hk_tree.item(sel[0])['values'][0]
            self.storage.toggle(bid)
            self._refresh_hk()

    def _delete_hk(self):
        sel = self.hk_tree.selection()
        if sel:
            bid = self.hk_tree.item(sel[0])['values'][0]
            self.storage.delete(bid)
            self._refresh_hk()

    def _run_macro(self):
        sel = self.mac_tree.selection()
        if sel:
            mid = self.mac_tree.item(sel[0])['values'][0]
            macro = self.macro_storage.get(mid)
            if macro:
                runner = MacroRunner()
                threading.Thread(target=runner.run, args=(macro,), daemon=True).start()

    def run(self):
        self.root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="Desktop Hotkey Manager")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("gui", help="Open hotkey manager GUI")
    sub.add_parser("daemon", help="Start global hotkey daemon")

    p_add = sub.add_parser("add", help="Add a hotkey binding")
    p_add.add_argument("hotkey", help="e.g. ctrl+shift+x")
    p_add.add_argument("action", choices=["type_text","hotkey","run_command","open_url",
                                          "open_file","screenshot","lock_screen",
                                          "minimize_all","volume","python_script"])
    p_add.add_argument("value", help="Action value")
    p_add.add_argument("--id", default=None)
    p_add.add_argument("--description", default="")

    sub.add_parser("list", help="List all hotkeys")

    p_del = sub.add_parser("delete", help="Delete a binding")
    p_del.add_argument("binding_id")

    p_macro_add = sub.add_parser("macro-add", help="Add a macro from JSON steps file")
    p_macro_add.add_argument("name")
    p_macro_add.add_argument("steps_json", help="JSON file with steps list")
    p_macro_add.add_argument("--hotkey", default="")

    p_macro_run = sub.add_parser("macro-run", help="Run a macro by ID")
    p_macro_run.add_argument("macro_id")

    sub.add_parser("macros", help="List all macros")

    args = parser.parse_args()
    hk_storage = HotkeyStorage()
    mac_storage = MacroStorage()

    if args.cmd == "gui":
        app = HotkeyManagerGUI(hk_storage, mac_storage)
        app.run()

    elif args.cmd == "daemon":
        daemon = GlobalHotkeyDaemon(hk_storage, mac_storage)
        print("Hotkey daemon started. Press Ctrl+C to stop.")
        try:
            daemon.start()
        except KeyboardInterrupt:
            daemon.stop()
            print("Daemon stopped.")

    elif args.cmd == "add":
        bid = args.id or datetime.now().strftime("%Y%m%d%H%M%S")
        b = HotkeyBinding(binding_id=bid, hotkey=args.hotkey,
                          action_type=args.action, action_value=args.value,
                          description=args.description)
        hk_storage.add(b)
        print(f"Hotkey added: {bid} ({args.hotkey} -> {args.action})")

    elif args.cmd == "list":
        hk_storage.list_all()

    elif args.cmd == "delete":
        hk_storage.delete(args.binding_id)
        print(f"Deleted: {args.binding_id}")

    elif args.cmd == "macro-add":
        with open(args.steps_json) as f:
            steps_data = json.load(f)
        steps = [MacroStep(**s) for s in steps_data]
        mid = datetime.now().strftime("%Y%m%d%H%M%S")
        macro = Macro(macro_id=mid, name=args.name, steps=steps, hotkey=args.hotkey)
        mac_storage.add(macro)
        print(f"Macro added: {mid} ({args.name}, {len(steps)} steps)")

    elif args.cmd == "macro-run":
        macro = mac_storage.get(args.macro_id)
        if not macro:
            print(f"Macro not found: {args.macro_id}")
            return
        print(f"Running macro '{macro.name}' in 3s...")
        time.sleep(3)
        runner = MacroRunner()
        runner.run(macro)
        print("Macro complete")

    elif args.cmd == "macros":
        mac_storage.list_all()

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
