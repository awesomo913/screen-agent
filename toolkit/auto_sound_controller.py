#!/usr/bin/env python3
"""Auto Sound Controller - Screen-based system audio control and monitoring."""

import os
import sys
import time
import json
import argparse
import threading
import subprocess
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional

import pyautogui
from PIL import Image

try:
    from pynput import keyboard
except ImportError:
    keyboard = None

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    from ctypes import cast, POINTER, windll
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, ISimpleAudioVolume
    HAS_PYCAW = True
except ImportError:
    HAS_PYCAW = False


@dataclass
class AudioProfile:
    """Saved audio profile."""
    name: str
    master_volume: float
    app_volumes: Dict[str, float] = field(default_factory=dict)
    muted: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AudioScheduleEntry:
    """Scheduled audio change."""
    time_str: str
    profile_name: str
    days: List[str] = field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
    enabled: bool = True


class SystemAudioController:
    """Controls system audio via multiple methods."""

    def __init__(self):
        self.endpoint_volume = None
        if HAS_PYCAW:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self.endpoint_volume = cast(interface, POINTER(IAudioEndpointVolume))
            except Exception:
                pass

    def get_master_volume(self):
        if self.endpoint_volume:
            return round(self.endpoint_volume.GetMasterVolumeLevelScalar() * 100)
        return self._get_volume_screen()

    def set_master_volume(self, level):
        level = max(0, min(100, level))
        if self.endpoint_volume:
            self.endpoint_volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            print(f"Master volume set to {level}%")
            return
        self._set_volume_screen(level)

    def get_mute_state(self):
        if self.endpoint_volume:
            return bool(self.endpoint_volume.GetMute())
        return False

    def toggle_mute(self):
        if self.endpoint_volume:
            current = self.endpoint_volume.GetMute()
            self.endpoint_volume.SetMute(not current, None)
            print(f"Mute {'enabled' if not current else 'disabled'}")
            return
        pyautogui.press("volumemute")
        print("Toggled mute via key")

    def volume_up(self, steps=2):
        for _ in range(steps):
            pyautogui.press("volumeup")
        print(f"Volume up {steps} steps")

    def volume_down(self, steps=2):
        for _ in range(steps):
            pyautogui.press("volumedown")
        print(f"Volume down {steps} steps")

    def _get_volume_screen(self):
        pyautogui.press("volumeup")
        time.sleep(0.1)
        pyautogui.press("volumedown")
        time.sleep(0.5)
        sw, sh = pyautogui.size()
        region = (sw // 2 - 100, sh - 120, 200, 60)
        screenshot = pyautogui.screenshot(region=region)
        if HAS_TESSERACT:
            text = pytesseract.image_to_string(screenshot)
            import re
            match = re.search(r'(\d+)', text)
            if match:
                return int(match.group(1))
        return -1

    def _set_volume_screen(self, target):
        current = self.get_master_volume()
        if current < 0:
            pyautogui.press("volumeup", presses=50)
            time.sleep(0.3)
            pyautogui.press("volumedown", presses=50)
            time.sleep(0.3)
            pyautogui.press("volumeup", presses=target // 2)
        else:
            diff = target - current
            if diff > 0:
                pyautogui.press("volumeup", presses=abs(diff) // 2)
            else:
                pyautogui.press("volumedown", presses=abs(diff) // 2)
        print(f"Volume set to ~{target}% via screen control")

    def get_app_sessions(self):
        if not HAS_PYCAW:
            return {}
        sessions = AudioUtilities.GetAllSessions()
        app_vols = {}
        for session in sessions:
            if session.Process:
                vol = session._ctl.QueryInterface(ISimpleAudioVolume)
                app_vols[session.Process.name()] = {
                    "volume": round(vol.GetMasterVolume() * 100),
                    "muted": bool(vol.GetMute()),
                    "pid": session.Process.pid
                }
        return app_vols

    def set_app_volume(self, app_name, level):
        if not HAS_PYCAW:
            print("pycaw not available, cannot set app volume")
            return
        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            if session.Process and app_name.lower() in session.Process.name().lower():
                vol = session._ctl.QueryInterface(ISimpleAudioVolume)
                vol.SetMasterVolume(level / 100.0, None)
                print(f"Set {session.Process.name()} volume to {level}%")
                return True
        print(f"App '{app_name}' not found in audio sessions")
        return False

    def mute_app(self, app_name, mute=True):
        if not HAS_PYCAW:
            return
        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            if session.Process and app_name.lower() in session.Process.name().lower():
                vol = session._ctl.QueryInterface(ISimpleAudioVolume)
                vol.SetMute(mute, None)
                print(f"{'Muted' if mute else 'Unmuted'} {session.Process.name()}")
                return


class AudioProfileManager:
    """Manages audio profiles and schedules."""

    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.expanduser("~/.audio_controller_config.json")
        self.controller = SystemAudioController()
        self.profiles: Dict[str, AudioProfile] = {}
        self.schedule: List[AudioScheduleEntry] = []
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                cfg = json.load(f)
            for name, pdata in cfg.get("profiles", {}).items():
                self.profiles[name] = AudioProfile(**pdata)
            for sdata in cfg.get("schedule", []):
                self.schedule.append(AudioScheduleEntry(**sdata))

    def save_config(self):
        cfg = {
            "profiles": {name: {"name": p.name, "master_volume": p.master_volume,
                                 "app_volumes": p.app_volumes, "muted": p.muted,
                                 "created_at": p.created_at}
                          for name, p in self.profiles.items()},
            "schedule": [{"time_str": s.time_str, "profile_name": s.profile_name,
                          "days": s.days, "enabled": s.enabled}
                         for s in self.schedule]
        }
        with open(self.config_path, "w") as f:
            json.dump(cfg, f, indent=2)

    def create_profile(self, name, master_vol=None, app_volumes=None, muted=False):
        if master_vol is None:
            master_vol = self.controller.get_master_volume()
        if app_volumes is None:
            sessions = self.controller.get_app_sessions()
            app_volumes = {k: v["volume"] for k, v in sessions.items()}
        profile = AudioProfile(name=name, master_volume=master_vol,
                               app_volumes=app_volumes, muted=muted)
        self.profiles[name] = profile
        self.save_config()
        print(f"Created profile '{name}' (master={master_vol}%)")
        return profile

    def apply_profile(self, name):
        profile = self.profiles.get(name)
        if not profile:
            print(f"Profile '{name}' not found")
            return
        self.controller.set_master_volume(int(profile.master_volume))
        if profile.muted:
            if not self.controller.get_mute_state():
                self.controller.toggle_mute()
        else:
            if self.controller.get_mute_state():
                self.controller.toggle_mute()
        for app, vol in profile.app_volumes.items():
            self.controller.set_app_volume(app, int(vol))
        print(f"Applied profile '{name}'")

    def delete_profile(self, name):
        if name in self.profiles:
            del self.profiles[name]
            self.save_config()
            print(f"Deleted profile '{name}'")

    def add_schedule(self, time_str, profile_name, days=None):
        entry = AudioScheduleEntry(time_str=time_str, profile_name=profile_name,
                                    days=days or ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
        self.schedule.append(entry)
        self.save_config()
        print(f"Scheduled '{profile_name}' at {time_str}")

    def run_scheduler(self):
        print("Audio scheduler running. Press Ctrl+C to stop.")
        day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
        try:
            while True:
                now = datetime.now()
                current_time = now.strftime("%H:%M")
                current_day_num = now.weekday()
                for entry in self.schedule:
                    if not entry.enabled:
                        continue
                    if entry.time_str == current_time:
                        day_nums = [day_map.get(d, -1) for d in entry.days]
                        if current_day_num in day_nums:
                            print(f"[{current_time}] Applying profile: {entry.profile_name}")
                            self.apply_profile(entry.profile_name)
                time.sleep(30)
        except KeyboardInterrupt:
            print("Scheduler stopped")

    def fade_volume(self, target, duration=5.0, steps=20):
        current = self.controller.get_master_volume()
        if current < 0:
            current = 50
        step_size = (target - current) / steps
        step_delay = duration / steps
        print(f"Fading volume from {current}% to {target}% over {duration}s")
        for i in range(steps):
            new_vol = int(current + step_size * (i + 1))
            new_vol = max(0, min(100, new_vol))
            self.controller.set_master_volume(new_vol)
            time.sleep(step_delay)
        print(f"Fade complete: {target}%")

    def setup_hotkeys(self):
        if not keyboard:
            print("pynput required for hotkeys")
            return
        print("Audio hotkeys active:")
        print("  Ctrl+Alt+Up: Volume up")
        print("  Ctrl+Alt+Down: Volume down")
        print("  Ctrl+Alt+M: Toggle mute")
        print("  Ctrl+Alt+1-5: Quick profiles")
        print("  ESC: Exit")
        current_keys = set()
        profile_names = list(self.profiles.keys())

        def on_press(key):
            current_keys.add(key)
            try:
                if keyboard.Key.ctrl_l in current_keys and keyboard.Key.alt_l in current_keys:
                    if key == keyboard.Key.up:
                        self.controller.volume_up(5)
                    elif key == keyboard.Key.down:
                        self.controller.volume_down(5)
                    elif hasattr(key, 'char'):
                        if key.char == 'm':
                            self.controller.toggle_mute()
                        elif key.char in '12345':
                            idx = int(key.char) - 1
                            if idx < len(profile_names):
                                self.apply_profile(profile_names[idx])
                if key == keyboard.Key.esc:
                    return False
            except Exception:
                pass

        def on_release(key):
            current_keys.discard(key)

        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()


def main():
    parser = argparse.ArgumentParser(description="Auto Sound Controller")
    parser.add_argument("--config", help="Config file path")
    subparsers = parser.add_subparsers(dest="command")

    vol_p = subparsers.add_parser("volume", help="Get/set master volume")
    vol_p.add_argument("level", nargs="?", type=int, help="Volume level 0-100")

    mute_p = subparsers.add_parser("mute", help="Toggle mute")

    up_p = subparsers.add_parser("up", help="Volume up")
    up_p.add_argument("--steps", type=int, default=5)

    down_p = subparsers.add_parser("down", help="Volume down")
    down_p.add_argument("--steps", type=int, default=5)

    apps_p = subparsers.add_parser("apps", help="List app audio sessions")

    app_vol = subparsers.add_parser("app-volume", help="Set app volume")
    app_vol.add_argument("app", help="App name")
    app_vol.add_argument("level", type=int, help="Volume level 0-100")

    profile_p = subparsers.add_parser("save-profile", help="Save current audio state as profile")
    profile_p.add_argument("name")

    apply_p = subparsers.add_parser("apply-profile", help="Apply an audio profile")
    apply_p.add_argument("name")

    profiles_p = subparsers.add_parser("profiles", help="List saved profiles")

    del_p = subparsers.add_parser("delete-profile", help="Delete a profile")
    del_p.add_argument("name")

    sched_p = subparsers.add_parser("schedule", help="Schedule a profile")
    sched_p.add_argument("time", help="Time HH:MM")
    sched_p.add_argument("profile", help="Profile name")
    sched_p.add_argument("--days", nargs="*", default=["mon", "tue", "wed", "thu", "fri", "sat", "sun"])

    run_sched = subparsers.add_parser("run-scheduler", help="Run the audio scheduler")

    fade_p = subparsers.add_parser("fade", help="Fade volume to target")
    fade_p.add_argument("target", type=int, help="Target volume 0-100")
    fade_p.add_argument("--duration", type=float, default=5.0)

    hotkeys_p = subparsers.add_parser("hotkeys", help="Start hotkey listener")

    args = parser.parse_args()
    mgr = AudioProfileManager(config_path=args.config if hasattr(args, "config") else None)

    if args.command == "volume":
        if args.level is not None:
            mgr.controller.set_master_volume(args.level)
        else:
            vol = mgr.controller.get_master_volume()
            muted = mgr.controller.get_mute_state()
            print(f"Master volume: {vol}% {'(MUTED)' if muted else ''}")
    elif args.command == "mute":
        mgr.controller.toggle_mute()
    elif args.command == "up":
        mgr.controller.volume_up(args.steps)
    elif args.command == "down":
        mgr.controller.volume_down(args.steps)
    elif args.command == "apps":
        sessions = mgr.controller.get_app_sessions()
        for app, info in sessions.items():
            muted = " (MUTED)" if info["muted"] else ""
            print(f"  {app}: {info['volume']}%{muted} (PID: {info['pid']})")
    elif args.command == "app-volume":
        mgr.controller.set_app_volume(args.app, args.level)
    elif args.command == "save-profile":
        mgr.create_profile(args.name)
    elif args.command == "apply-profile":
        mgr.apply_profile(args.name)
    elif args.command == "profiles":
        for name, p in mgr.profiles.items():
            print(f"  {name}: master={p.master_volume}% apps={len(p.app_volumes)} muted={p.muted}")
    elif args.command == "delete-profile":
        mgr.delete_profile(args.name)
    elif args.command == "schedule":
        mgr.add_schedule(args.time, args.profile, args.days)
    elif args.command == "run-scheduler":
        mgr.run_scheduler()
    elif args.command == "fade":
        mgr.fade_volume(args.target, args.duration)
    elif args.command == "hotkeys":
        mgr.setup_hotkeys()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
