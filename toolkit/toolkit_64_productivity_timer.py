"""
toolkit_64_productivity_timer.py
Pomodoro timer, work session tracking, break reminders, time logging,
and focus session analytics. Uses stdlib only + optional TTS for alerts.
"""
from __future__ import annotations
import time
import json
import os
import datetime
from typing import Any, Dict, List

_session_log: list = []
_active_session: dict = {}

def start_timer(label: str = "Work", duration_minutes: float = 25.0) -> Dict[str, Any]:
    """Start a timed session (non-blocking - returns immediately)."""
    try:
        global _active_session
        _active_session = {
            "label": label,
            "start": time.time(),
            "duration_minutes": duration_minutes,
            "end": time.time() + duration_minutes * 60
        }
        return {"success": True, "data": {
            "label": label,
            "duration_minutes": duration_minutes,
            "ends_at": datetime.datetime.fromtimestamp(_active_session["end"]).isoformat()
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_timer_status() -> Dict[str, Any]:
    try:
        if not _active_session:
            return {"success": True, "data": {"active": False}, "error": None}
        remaining = _active_session["end"] - time.time()
        elapsed = time.time() - _active_session["start"]
        if remaining <= 0:
            return {"success": True, "data": {
                "active": False, "label": _active_session.get("label", ""),
                "completed": True, "elapsed_minutes": round(_active_session["duration_minutes"], 1)
            }, "error": None}
        return {"success": True, "data": {
            "active": True,
            "label": _active_session.get("label", ""),
            "remaining_minutes": round(remaining / 60, 1),
            "remaining_seconds": int(remaining),
            "elapsed_minutes": round(elapsed / 60, 1),
            "progress_percent": round((elapsed / (_active_session["duration_minutes"] * 60)) * 100, 1)
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def stop_timer() -> Dict[str, Any]:
    try:
        global _active_session, _session_log
        if not _active_session:
            return {"success": True, "data": {"stopped": False, "note": "No active timer"}, "error": None}
        elapsed = time.time() - _active_session["start"]
        record = {
            "label": _active_session.get("label", ""),
            "planned_minutes": _active_session.get("duration_minutes", 0),
            "actual_minutes": round(elapsed / 60, 2),
            "date": datetime.datetime.now().isoformat()
        }
        _session_log.append(record)
        _active_session = {}
        return {"success": True, "data": record, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def wait_and_alert(duration_minutes: float = 25.0, message: str = "Timer complete!") -> Dict[str, Any]:
    """Block until timer ends, then show a message box alert."""
    try:
        time.sleep(duration_minutes * 60)
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, "Timer Alert", 0x40)
        return {"success": True, "data": {"alerted": message, "after_minutes": duration_minutes}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def log_work_session(label: str, duration_minutes: float, notes: str = "") -> Dict[str, Any]:
    try:
        global _session_log
        record = {
            "label": label,
            "actual_minutes": duration_minutes,
            "planned_minutes": duration_minutes,
            "notes": notes,
            "date": datetime.datetime.now().isoformat()
        }
        _session_log.append(record)
        return {"success": True, "data": record, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_session_log() -> Dict[str, Any]:
    try:
        total = sum(s.get("actual_minutes", 0) for s in _session_log)
        return {"success": True, "data": {
            "sessions": len(_session_log),
            "total_minutes": round(total, 1),
            "total_hours": round(total / 60, 2),
            "log": _session_log
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clear_session_log() -> Dict[str, Any]:
    try:
        global _session_log
        count = len(_session_log)
        _session_log = []
        return {"success": True, "data": {"cleared": count}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def save_session_log(file_path: str) -> Dict[str, Any]:
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(_session_log, f, indent=2)
        return {"success": True, "data": {"saved": file_path, "sessions": len(_session_log)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def load_session_log(file_path: str) -> Dict[str, Any]:
    try:
        global _session_log
        with open(file_path, "r", encoding="utf-8") as f:
            _session_log = json.load(f)
        return {"success": True, "data": {"loaded": len(_session_log)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def pomodoro_start(work_minutes: float = 25.0, break_minutes: float = 5.0, cycles: int = 1) -> Dict[str, Any]:
    """Start a Pomodoro sequence (blocking). Shows alerts between phases."""
    try:
        import ctypes
        completed_cycles = 0
        for i in range(cycles):
            time.sleep(work_minutes * 60)
            ctypes.windll.user32.MessageBoxW(0, "Work session complete! Take a " + str(int(break_minutes)) + " minute break.", "Pomodoro", 0x40)
            log_work_session("Pomodoro Work", work_minutes)
            if i < cycles - 1:
                time.sleep(break_minutes * 60)
                ctypes.windll.user32.MessageBoxW(0, "Break over! Back to work.", "Pomodoro", 0x40)
                log_work_session("Pomodoro Break", break_minutes)
            completed_cycles += 1
        return {"success": True, "data": {"completed_cycles": completed_cycles}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_daily_summary() -> Dict[str, Any]:
    """Summarize today's logged sessions."""
    try:
        today = datetime.date.today().isoformat()
        today_sessions = [s for s in _session_log if s.get("date", "").startswith(today)]
        total = sum(s.get("actual_minutes", 0) for s in today_sessions)
        by_label: dict = {}
        for s in today_sessions:
            lbl = s.get("label", "Other")
            by_label[lbl] = by_label.get(lbl, 0) + s.get("actual_minutes", 0)
        return {"success": True, "data": {
            "date": today,
            "sessions": len(today_sessions),
            "total_minutes": round(total, 1),
            "total_hours": round(total / 60, 2),
            "by_label": by_label
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def countdown(seconds: int) -> Dict[str, Any]:
    """Simple blocking countdown."""
    try:
        start = time.time()
        time.sleep(seconds)
        return {"success": True, "data": {"elapsed_s": round(time.time() - start, 1)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_current_time_info() -> Dict[str, Any]:
    try:
        now = datetime.datetime.now()
        return {"success": True, "data": {
            "iso": now.isoformat(),
            "date": now.date().isoformat(),
            "time": now.strftime("%H:%M:%S"),
            "timestamp": time.time(),
            "weekday": now.strftime("%A"),
            "week_number": now.isocalendar()[1]
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
