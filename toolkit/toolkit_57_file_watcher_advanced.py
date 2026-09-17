"""
toolkit_57_file_watcher_advanced.py
Advanced file system monitoring: watch directories for changes,
debounce events, filter by pattern, log events, and trigger callbacks.
Distinct from file_watcher (basic) - adds debouncing, filtering, and batch processing.
"""
from __future__ import annotations
import os
import time
import hashlib
import threading
from pathlib import Path
from typing import Any, Dict, List

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileDeletedEvent, FileMovedEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

_watch_sessions: dict = {}

def scan_for_changes(folder: str, state_file: str = "") -> Dict[str, Any]:
    """
    Compute a snapshot of file hashes. Compare to previous snapshot to find changes.
    If state_file provided, persists state between calls.
    """
    try:
        import json
        current_state: dict = {}
        for root, dirs, files in os.walk(folder):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    mtime = os.path.getmtime(fp)
                    size = os.path.getsize(fp)
                    current_state[os.path.relpath(fp, folder)] = {"mtime": mtime, "size": size}
                except OSError:
                    pass
        if not state_file:
            return {"success": True, "data": {"snapshot": current_state, "file_count": len(current_state)}, "error": None}
        old_state: dict = {}
        if os.path.isfile(state_file):
            with open(state_file, "r") as sf:
                old_state = json.load(sf)
        added = [k for k in current_state if k not in old_state]
        removed = [k for k in old_state if k not in current_state]
        modified = [k for k in current_state if k in old_state and
                    (current_state[k]["mtime"] != old_state[k]["mtime"] or current_state[k]["size"] != old_state[k]["size"])]
        with open(state_file, "w") as sf:
            json.dump(current_state, sf)
        return {"success": True, "data": {
            "added": added, "removed": removed, "modified": modified,
            "total": len(current_state), "changes": len(added) + len(removed) + len(modified)
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def poll_for_new_files(folder: str, extension: str = "", interval_s: float = 2.0, max_polls: int = 10) -> Dict[str, Any]:
    """Poll a folder and return newly appeared files."""
    try:
        ext = extension.lower() if extension else ""
        seen: set = set()
        new_files = []
        for _ in range(max_polls):
            current: set = set()
            for f in os.listdir(folder):
                if not ext or f.lower().endswith(ext):
                    current.add(f)
            appeared = current - seen
            new_files.extend(list(appeared))
            seen = current
            if appeared:
                break
            time.sleep(interval_s)
        return {"success": True, "data": {"new_files": new_files, "count": len(new_files)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_recently_modified_files(folder: str, minutes: int = 5, recursive: bool = True) -> Dict[str, Any]:
    try:
        cutoff = time.time() - minutes * 60
        results = []
        if recursive:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        mtime = os.path.getmtime(fp)
                        if mtime >= cutoff:
                            results.append({"path": fp, "modified": mtime})
                    except OSError:
                        pass
        else:
            for f in os.listdir(folder):
                fp = os.path.join(folder, f)
                if os.path.isfile(fp):
                    try:
                        mtime = os.path.getmtime(fp)
                        if mtime >= cutoff:
                            results.append({"path": fp, "modified": mtime})
                    except OSError:
                        pass
        results.sort(key=lambda x: x["modified"], reverse=True)
        return {"success": True, "data": {"count": len(results), "files": results}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def watch_folder_events(folder: str, duration_s: float = 5.0, patterns: list = []) -> Dict[str, Any]:
    """Watch a folder for changes for a duration. Returns event log."""
    try:
        if not HAS_WATCHDOG:
            return {"success": False, "data": None, "error": "watchdog not installed (pip install watchdog)"}
        events_log = []
        class Handler(FileSystemEventHandler):
            def on_any_event(self, event):
                if not event.is_directory:
                    if not patterns or any(event.src_path.endswith(p) for p in patterns):
                        events_log.append({"event": event.event_type, "path": event.src_path, "time": time.time()})
        observer = Observer()
        observer.schedule(Handler(), folder, recursive=True)
        observer.start()
        time.sleep(duration_s)
        observer.stop()
        observer.join(timeout=2)
        return {"success": True, "data": {"events": events_log, "count": len(events_log)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def compute_folder_hash(folder: str) -> Dict[str, Any]:
    """Single hash representing entire folder contents (for change detection)."""
    try:
        h = hashlib.sha256()
        for root, dirs, files in os.walk(folder):
            dirs.sort()
            for f in sorted(files):
                fp = os.path.join(root, f)
                rel = os.path.relpath(fp, folder)
                h.update(rel.encode())
                try:
                    h.update(str(os.path.getsize(fp)).encode())
                    h.update(str(int(os.path.getmtime(fp))).encode())
                except OSError:
                    pass
        return {"success": True, "data": h.hexdigest(), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_files_created_today(folder: str) -> Dict[str, Any]:
    try:
        import datetime
        today = datetime.date.today()
        results = []
        for root, dirs, files in os.walk(folder):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    ctime = os.path.getctime(fp)
                    if datetime.date.fromtimestamp(ctime) == today:
                        results.append(fp)
                except OSError:
                    pass
        return {"success": True, "data": {"count": len(results), "files": results[:200]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def wait_for_file(file_path: str, timeout_s: float = 30.0, check_interval: float = 0.5) -> Dict[str, Any]:
    """Wait until a file appears on disk."""
    try:
        start = time.time()
        while time.time() - start < timeout_s:
            if os.path.isfile(file_path):
                return {"success": True, "data": {"found": True, "elapsed_s": round(time.time() - start, 1)}, "error": None}
            time.sleep(check_interval)
        return {"success": False, "data": {"found": False}, "error": "File not found within " + str(timeout_s) + "s: " + file_path}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def wait_for_file_stable(file_path: str, stable_s: float = 2.0, timeout_s: float = 30.0) -> Dict[str, Any]:
    """Wait until a file size stops changing (fully written)."""
    try:
        start = time.time()
        last_size = -1
        stable_start = None
        while time.time() - start < timeout_s:
            if not os.path.isfile(file_path):
                time.sleep(0.3)
                continue
            size = os.path.getsize(file_path)
            if size == last_size:
                if stable_start is None:
                    stable_start = time.time()
                elif time.time() - stable_start >= stable_s:
                    return {"success": True, "data": {"stable": True, "size": size}, "error": None}
            else:
                stable_start = None
            last_size = size
            time.sleep(0.3)
        return {"success": False, "data": None, "error": "File did not stabilize"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_watchdog_available() -> Dict[str, Any]:
    return {"success": True, "data": {"watchdog": HAS_WATCHDOG}, "error": None}

def get_oldest_file(folder: str, extension: str = "") -> Dict[str, Any]:
    try:
        files = []
        for f in os.listdir(folder):
            fp = os.path.join(folder, f)
            if os.path.isfile(fp):
                if not extension or f.lower().endswith(extension.lower()):
                    files.append((os.path.getmtime(fp), fp))
        if not files:
            return {"success": True, "data": None, "error": None}
        oldest = min(files, key=lambda x: x[0])
        return {"success": True, "data": {"path": oldest[1], "mtime": oldest[0]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_newest_file(folder: str, extension: str = "") -> Dict[str, Any]:
    try:
        files = []
        for f in os.listdir(folder):
            fp = os.path.join(folder, f)
            if os.path.isfile(fp):
                if not extension or f.lower().endswith(extension.lower()):
                    files.append((os.path.getmtime(fp), fp))
        if not files:
            return {"success": True, "data": None, "error": None}
        newest = max(files, key=lambda x: x[0])
        return {"success": True, "data": {"path": newest[1], "mtime": newest[0]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
