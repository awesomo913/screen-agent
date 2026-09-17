# file_watcher.py
"""
Screen‑Agent Toolkit – File‑Watcher utilities

Provides a rich set of helper functions for monitoring files and directories.
All helpers start a background thread or a watchdog ``Observer`` and return a
dictionary that can be inspected or logged by the caller.

Typical return format::

    {
        "status": "started" | "error" | "stopped",
        "message": str,
        "data": {...}   # optional, function‑specific payload
    }

The module is deliberately self‑contained – no external configuration files are
required.
"""

from __future__ import annotations

import json
import os
import hashlib
import time
import threading
import shutil
from pathlib import Path
from typing import Callable, Dict, List, Set, Tuple, Any, Optional

from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    PatternMatchingEventHandler,
)

# --------------------------------------------------------------------------- #
# Helper utilities
# --------------------------------------------------------------------------- #
def _hash_file(path: Path) -> str:
    """Calculate SHA‑256 hash of a file; returns empty string on error."""
    try:
        hasher = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""


def _safe_json_dump(data: Any, path: Path) -> None:
    """Write JSON atomically."""
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    tmp.replace(path)


# --------------------------------------------------------------------------- #
# Core watcher implementations
# --------------------------------------------------------------------------- #
def watch_directory(
    path: str | Path,
    patterns: List[str] | Tuple[str, ...] = ("*.*",),
    recursive: bool = True,
    callback: Callable[[FileSystemEventHandler, Any], None] | None = None,
) -> Dict[str, Any]:
    """
    Watch ``path`` for filesystem events that match ``patterns``.
    Returns a dict with the created ``Observer`` and ``Handler`` objects.

    Parameters
    ----------
    path: directory to watch
    patterns: glob patterns understood by ``PatternMatchingEventHandler``
    recursive: whether to watch sub‑directories
    callback: optional function called with (event, observer) on each event
    """
    try:
        p = Path(path).resolve()
        if not p.is_dir():
            raise NotADirectoryError(f"{p} is not a directory")

        class _Handler(PatternMatchingEventHandler):
            def __init__(self):
                super().__init__(patterns=patterns, ignore_directories=False)

            def on_any_event(self, event):
                if callback:
                    try:
                        callback(event, self)
                    except Exception as exc:
                        # swallow callback errors – they are user‑code
                        print(f"[watch_directory] callback error: {exc}")

        handler = _Handler()
        observer = Observer()
        observer.schedule(handler, str(p), recursive=recursive)
        observer.start()

        return {
            "status": "started",
            "message": f"Watching directory {p}",
            "data": {"observer": observer, "handler": handler},
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc), "data": {}}


def watch_file_changes(filepath: str | Path, interval: float = 1.0) -> Dict[str, Any]:
    """
    Poll ``filepath`` every ``interval`` seconds and emit a dict when its size
    or modification time changes.
    """
    p = Path(filepath).resolve()

    def _worker(stop_event: threading.Event, out: Dict):
        last_stat = None
        while not stop_event.is_set():
            try:
                cur = p.stat()
                if last_stat and (cur.st_mtime != last_stat.st_mtime or cur.st_size != last_stat.st_size):
                    out["status"] = "changed"
                    out["message"] = f"File {p} changed"
                    out["data"] = {
                        "size": cur.st_size,
                        "mtime": cur.st_mtime,
                        "hash": _hash_file(p) if cur.st_size < 10 * 1024 * 1024 else None,
                    }
                last_stat = cur
            except FileNotFoundError:
                out["status"] = "missing"
                out["message"] = f"File {p} not found"
                out["data"] = {}
                break
            except Exception as exc:
                out["status"] = "error"
                out["message"] = str(exc)
                break
            time.sleep(interval)

    stop_evt = threading.Event()
    result: Dict[str, Any] = {"status": "started", "message": "Polling started", "data": {}}
    t = threading.Thread(target=_worker, args=(stop_evt, result), daemon=True)
    t.start()
    result["data"]["thread"] = t
    result["data"]["stop_event"] = stop_evt
    return result


def get_directory_snapshot(path: str | Path) -> Dict[str, Any]:
    """
    Return a snapshot of a directory – a mapping from relative path → metadata.
    Metadata includes size, mtime and SHA‑256 hash (if file <10 MiB).
    """
    p = Path(path).resolve()
    snap: Dict[str, Any] = {}
    try:
        for f in p.rglob("*"):
            if f.is_file():
                rel = f.relative_to(p).as_posix()
                stat = f.stat()
                meta = {
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                }
                if stat.st_size <= 10 * 1024 * 1024:
                    meta["hash"] = _hash_file(f)
                snap[rel] = meta
        return {"status": "success", "message": f"Snapshot of {p}", "data": snap}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "data": {}}


def compare_snapshots(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare two snapshots (as returned by ``get_directory_snapshot``) and
    return a dict that lists ``added``, ``removed`` and ``modified`` paths.
    """
    try:
        old_set = set(old.keys())
        new_set = set(new.keys())
        added = list(new_set - old_set)
        removed = list(old_set - new_set)

        modified = []
        for key in old_set & new_set:
            if old[key] != new[key]:
                modified.append(key)

        return {
            "status": "success",
            "message": "Snapshot comparison complete",
            "data": {"added": added, "removed": removed, "modified": modified},
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc), "data": {}}


def monitor_new_files(directory: str | Path, extension_filter: Tuple[str, ...] = ()) -> Dict[str, Any]:
    """
    Detect newly created files (optionally filtered by extension) in ``directory``.
    Emits a dict each time a new file appears.
    """
    p = Path(directory).resolve()
    known: Set[Path] = set(p.rglob("*")) if p.is_dir() else set()

    stop_evt = threading.Event()
    result: Dict[str, Any] = {"status": "started", "message": f"Monitoring new files in {p}", "data": {}}

    def _worker():
        while not stop_evt.is_set():
            try:
                current = set(p.rglob("*"))
                new = current - known
                for f in new:
                    if f.is_file() and (not extension_filter or f.suffix in extension_filter):
                        result["status"] = "new_file"
                        result["message"] = f"New file detected: {f}"
                        result["data"] = {"path": str(f)}
                known.update(new)
                time.sleep(1.0)
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)
                break

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    result["data"]["thread"] = t
    result["data"]["stop_event"] = stop_evt
    return result


def monitor_deleted_files(directory: str | Path) -> Dict[str, Any]:
    """
    Watch ``directory`` for file deletions.
    """
    p = Path(directory).resolve()
    known = {f for f in p.rglob("*") if f.is_file()}
    stop_evt = threading.Event()
    result = {"status": "started", "message": f"Monitoring deletions in {p}", "data": {}}

    def _worker():
        while not stop_evt.is_set():
            try:
                current = {f for f in p.rglob("*") if f.is_file()}
                deleted = known - current
                for f in deleted:
                    result["status"] = "deleted"
                    result["message"] = f"File deleted: {f}"
                    result["data"] = {"path": str(f)}
                known.update(current - deleted)
                time.sleep(1.0)
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)
                break

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    result["data"]["thread"] = t
    result["data"]["stop_event"] = stop_evt
    return result


def monitor_modified_files(directory: str | Path, hash_check: bool = False) -> Dict[str, Any]:
    """
    Detect modifications inside ``directory``. If ``hash_check`` is True a
    content hash (SHA‑256) is recomputed for each file; otherwise only size/mtime
    are compared.
    """
    p = Path(directory).resolve()
    snapshot = get_directory_snapshot(p)["data"]
    stop_evt = threading.Event()
    result = {"status": "started", "message": f"Monitoring modifications in {p}", "data": {}}

    def _worker():
        nonlocal snapshot
        while not stop_evt.is_set():
            try:
                new_snap = get_directory_snapshot(p)["data"]
                diff = compare_snapshots(snapshot, new_snap)["data"]
                if diff["added"] or diff["removed"] or diff["modified"]:
                    result["status"] = "modified"
                    result["message"] = "Changes detected"
                    result["data"] = diff
                snapshot = new_snap
                time.sleep(1.5)
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)
                break

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    result["data"]["thread"] = t
    result["data"]["stop_event"] = stop_evt
    return result


def tail_file(filepath: str | Path, lines: int = 10) -> Dict[str, Any]:
    """
    Return the last ``lines`` lines of ``filepath`` efficiently.
    """
    p = Path(filepath).resolve()
    try:
        with p.open("rb") as f:
            # Seek from the end and read backwards until we have enough newlines
            f.seek(0, os.SEEK_END)
            buffer = bytearray()
            block_size = 1024
            while len(buffer.splitlines()) <= lines and f.tell() > 0:
                read_size = min(block_size, f.tell())
                f.seek(-read_size, os.SEEK_CUR)
                buffer[:0] = f.read(read_size)
                f.seek(-read_size, os.SEEK_CUR)
            tail = buffer.decode(errors="replace").splitlines()[-lines:]
        return {"status": "success", "message": f"Tailed {lines} lines from {p}", "data": {"lines": tail}}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "data": {}}


def watch_log_file(filepath: str | Path, pattern: str) -> Dict[str, Any]:
    """
    Continuously watch a log file for lines matching ``pattern`` (simple substring
    match). Emits a dict each time a match occurs.
    """
    p = Path(filepath).resolve()
    stop_evt = threading.Event()
    result = {"status": "started", "message": f"Watching log {p} for pattern '{pattern}'", "data": {}}
    last_position = 0

    def _worker():
        nonlocal last_position
        while not stop_evt.is_set():
            try:
                if not p.is_file():
                    time.sleep(1)
                    continue
                with p.open("r", encoding="utf-8", errors="replace") as f:
                    f.seek(last_position)
                    for line in f:
                        if pattern in line:
                            result["status"] = "match"
                            result["message"] = f"Pattern found in {p}"
                            result["data"] = {"line": line.rstrip("\n")}
                    last_position = f.tell()
                time.sleep(0.5)
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)
                break

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    result["data"]["thread"] = t
    result["data"]["stop_event"] = stop_evt
    return result


def watch_file_size(filepath: str | Path, threshold: int) -> Dict[str, Any]:
    """
    Monitor ``filepath`` and report when its size exceeds ``threshold`` bytes.
    """
    p = Path(filepath).resolve()
    stop_evt = threading.Event()
    result = {"status": "started", "message": f"Watching size of {p}", "data": {}}

    def _worker():
        while not stop_evt.is_set():
            try:
                size = p.stat().st_size
                if size > threshold:
                    result["status"] = "exceeded"
                    result["message"] = f"Size {size} > {threshold}"
                    result["data"] = {"size": size}
                    break
                time.sleep(1.0)
            except FileNotFoundError:
                result["status"] = "missing"
                result["message"] = f"{p} does not exist"
                break
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)
                break

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    result["data"]["thread"] = t
    result["data"]["stop_event"] = stop_evt
    return result


def monitor_disk_usage(path: str | Path, threshold: float = 0.9) -> Dict[str, Any]:
    """
    Periodically poll disk usage for ``path``. If the used fraction exceeds
    ``threshold`` (0‑1), a dict is emitted.
    """
    p = Path(path).resolve()
    stop_evt = threading.Event()
    result = {"status": "started", "message": f"Monitoring disk usage for {p}", "data": {}}

    def _worker():
        while not stop_evt.is_set():
            try:
                usage = shutil.disk_usage(str(p))
                used_frac = usage.used / usage.total
                if used_frac >= threshold:
                    result["status"] = "full"
                    result["message"] = f"Disk usage {used_frac:.2%} exceeds {threshold:.2%}"
                    result["data"] = {
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "used_fraction": used_frac,
                    }
                    break
                time.sleep(30)  # poll every 30 s
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)
                break

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    result["data"]["thread"] = t
    result["data"]["stop_event"] = stop_evt
    return result


def watch_directory_tree(root: str | Path, depth: int = 3) -> Dict[str, Any]:
    """
    Produce a static snapshot (as a dict) of the directory tree up to ``depth``.
    The function returns the snapshot immediately (no background thread).
    """
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        return {"status": "error", "message": f"{root_path} not a directory", "data": {}}

    tree: Dict[str, Any] = {}

    def _walk(current: Path, current_depth: int):
        if current_depth > depth:
            return
        for entry in current.iterdir():
            rel = entry.relative_to(root_path).as_posix()
            if entry.is_dir():
                tree[rel] = {"type": "dir"}
                _walk(entry, current_depth + 1)
            else:
                tree[rel] = {
                    "type": "file",
                    "size": entry.stat().st_size,
                    "mtime": entry.stat().st_mtime,
                }

    _walk(root_path, 0)
    return {"status": "success", "message": f"Tree up to depth {depth}", "data": tree}


def detect_file_moves(directory: str | Path) -> Dict[str, Any]:
    """
    Detect moves/renames inside ``directory`` by tracking inode → path mapping.
    Emits a dict for each detected move.
    """
    p = Path(directory).resolve()
    inode_map: Dict[int, Path] = {}
    stop_evt = threading.Event()
    result = {"status": "started", "message": f"Detecting moves in {p}", "data": {}}

    def _build_map():
        for f in p.rglob("*"):
            if f.is_file():
                inode_map[f.stat().st_ino] = f

    _build_map()

    def _worker():
        while not stop_evt.is_set():
            try:
                current_map: Dict[int, Path] = {}
                for f in p.rglob("*"):
                    if f.is_file():
                        current_map[f.stat().st_ino] = f
                # Look for inodes whose path changed
                for ino, old_path in inode_map.items():
                    new_path = current_map.get(ino)
                    if new_path and new_path != old_path:
                        result["status"] = "moved"
                        result["message"] = f"{old_path} -> {new_path}"
                        result["data"] = {"old": str(old_path), "new": str(new_path)}
                inode_map.clear()
                inode_map.update(current_map)
                time.sleep(2.0)
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)
                break

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    result["data"]["thread"] = t
    result["data"]["stop_event"] = stop_evt
    return result


def watch_file_permissions(filepath: str | Path) -> Dict[str, Any]:
    """
    Monitor a file's permission bits (mode). Emits a dict on any change.
    """
    p = Path(filepath).resolve()
    stop_evt = threading.Event()
    result = {"status": "started", "message": f"Watching permissions for {p}", "data": {}}
    try:
        last_mode = p.stat().st_mode
    except FileNotFoundError:
        return {"status": "error", "message": f"{p} does not exist", "data": {}}

    def _worker():
        nonlocal last_mode
        while not stop_evt.is_set():
            try:
                cur_mode = p.stat().st_mode
                if cur_mode != last_mode:
                    result["status"] = "changed"
                    result["message"] = f"Permissions changed for {p}"
                    result["data"] = {"old": oct(last_mode), "new": oct(cur_mode)}
                    last_mode = cur_mode
                time.sleep(1.2)
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)
                break

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    result["data"]["thread"] = t
    result["data"]["stop_event"] = stop_evt
    return result


def monitor_file_locks(filepath: str | Path, poll_interval: float = 1.0) -> Dict[str, Any]:
    """
    Very lightweight lock detector: attempts to open the file exclusively.
    If it fails, we assume another process holds a lock.
    """
    p = Path(filepath).resolve()
    stop_evt = threading.Event()
    result = {"status": "started", "message": f"Monitoring lock status for {p}", "data": {}}
    locked = False

    def _worker():
        nonlocal locked
        while not stop_evt.is_set():
            try:
                # On POSIX we try an exclusive non‑blocking open (O_EXCL not honoured on existing file)
                # So we use a simple heuristic: try to rename the file – if it fails, assume locked.
                tmp = p.with_name(p.name + ".tmp.lock")
                try:
                    p.rename(tmp)
                    tmp.rename(p)  # rename back
                    now_locked = False
                except Exception:
                    now_locked = True
                if now_locked != locked:
                    locked = now_locked
                    result["status"] = "locked" if locked else "unlocked"
                    result["message"] = f"{p} is now {'locked' if locked else 'unlocked'}"
                    result["data"] = {"locked": locked}
                time.sleep(poll_interval)
            except FileNotFoundError:
                result["status"] = "missing"
                result["message"] = f"{p} vanished"
                break
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)
                break

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    result["data"]["thread"] = t
    result["data"]["stop_event"] = stop_evt
    return result


def batch_watch(paths: List[Tuple[str, List[str]]], events: Tuple[str, ...]) -> Dict[str, Any]:
    """
    Watch multiple directories (``paths``) each paired with its own glob pattern
    list. ``events`` is a tuple of watchdog event names to listen for
    (e.g. ``("created","deleted","modified")``). Returns a dict of observers.
    """
    observers: List[Observer] = []
    try:
        for directory, patterns in paths:
            handler = PatternMatchingEventHandler(patterns=patterns, ignore_directories=False)

            def _make_callback(event_name):
                def _cb(event):
                    if event.event_type in events:
                        print(f"[batch_watch] {event_name} → {event.src_path}")
                return _cb

            handler.on_created = _make_callback("created")
            handler.on_deleted = _make_callback("deleted")
            handler.on_modified = _make_callback("modified")
            handler.on_moved = _make_callback("moved")

            obs = Observer()
            obs.schedule(handler, str(Path(directory).resolve()), recursive=True)
            obs.start()
            observers.append(obs)

        return {
            "status": "started",
            "message": f"Batch watching {len(paths)} paths",
            "data": {"observers": observers},
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc), "data": {}}


def create_file_trigger(filepath: str | Path, action: Callable[[Path], None]) -> Dict[str, Any]:
    """
    Set up a watchdog observer that runs ``action`` whenever ``filepath`` changes.
    """
    p = Path(filepath).resolve()
    stop_evt = threading.Event()
    result = {"status": "started", "message": f"Trigger on {p}", "data": {}}

    class _TriggerHandler(FileSystemEventHandler):
        def on_modified(self, event):
            if isinstance(event, FileModifiedEvent) and Path(event.src_path).resolve() == p:
                try:
                    action(p)
                    result["status"] = "triggered"
                    result["message"] = f"Action executed for {p}"
                except Exception as exc:
                    result["status"] = "error"
                    result["message"] = f"Action error: {exc}"

    handler = _TriggerHandler()
    observer = Observer()
    observer.schedule(handler, str(p.parent), recursive=False)
    observer.start()

    result["data"]["observer"] = observer
    result["data"]["handler"] = handler
    result["data"]["stop_event"] = stop_evt
    return result


def watch_config_changes(config_path: str | Path) -> Dict[str, Any]:
    """
    Monitor a JSON/YAML config file and reload it on change. Returns the latest
    parsed content in ``data['config']``.
    """
    p = Path(config_path).resolve()
    stop_evt = threading.Event()
    result = {"status": "started", "message": f"Watching config {p}", "data": {"config": None}}

    def _load():
        try:
            with p.open("r", encoding="utf-8") as f:
                if p.suffix.lower() in {".json"}:
                    return json.load(f)
                # fallback – treat as JSON (could be extended with yaml)
                return json.load(f)
        except Exception as exc:
            return {"error": str(exc)}

    class _ConfigHandler(FileSystemEventHandler):
        def on_modified(self, event):
            if Path(event.src_path).resolve() == p:
                result["data"]["config"] = _load()
                result["status"] = "reloaded"
                result["message"] = f"Config reloaded from {p}"

    handler = _ConfigHandler()
    observer = Observer()
    observer.schedule(handler, str(p.parent), recursive=False)
    observer.start()
    # Load initially
    result["data"]["config"] = _load()
    return {"status": "started", "message": "Config watch started", "data": {"observer": observer, "handler": handler, "config": result["data"]["config"], "stop_event": stop_evt}}


def monitor_temp_files(directory: str | Path, max_age: float = 3600) -> Dict[str, Any]:
    """
    Periodically delete files in ``directory`` older than ``max_age`` seconds.
    Returns a dict summarising deletions.
    """
    p = Path(directory).resolve()
    stop_evt = threading.Event()
    result = {"status": "started", "message": f"Cleaning temp files in {p}", "data": {"deleted": []}}

    def _worker():
        while not stop_evt.is_set():
            now = time.time()
            for f in p.iterdir():
                try:
                    if f.is_file() and (now - f.stat().st_mtime) > max_age:
                        f.unlink()
                        result["data"]["deleted"].append(str(f))
                except Exception:
                    continue
            time.sleep(300)  # run every 5 min

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    result["data"]["thread"] = t
    result["data"]["stop_event"] = stop_evt
    return result


def cleanup_watched(directory: str | Path, rules: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply user‑provided ``rules`` to files inside ``directory``.
    Supported rule keys (all optional):
        - "delete_ext": List[str] – delete files with these extensions.
        - "archive_ext": List[str] – move files to ``archive_dir``.
        - "max_age": float – delete files older than this (seconds).

    Returns a dict with actions performed.
    """
    p = Path(directory).resolve()
    archive_dir = Path(rules.get("archive_dir", p / "archive")).resolve()
    archive_dir.mkdir(parents=True, exist_ok=True)
    actions = {"deleted": [], "archived": []}
    now = time.time()

    try:
        for f in p.rglob("*"):
            if not f.is_file():
                continue
            # Delete by extension
            if "delete_ext" in rules and f.suffix in rules["delete_ext"]:
                f.unlink()
                actions["deleted"].append(str(f))
                continue
            # Archive by extension
            if "archive_ext" in rules and f.suffix in rules["archive_ext"]:
                dest = archive_dir / f.name
                f.rename(dest)
                actions["archived"].append(str(dest))
                continue
            # Age based deletion
            if "max_age" in rules and (now - f.stat().st_mtime) > rules["max_age"]:
                f.unlink()
                actions["deleted"].append(str(f))
    except Exception as exc:
        return {"status": "error", "message": str(exc), "data": actions}

    return {"status": "success", "message": "Cleanup finished", "data": actions}


def get_file_events_log(path: str | Path, since: float = 0.0) -> Dict[str, Any]:
    """
    Reads a JSON‑lines log saved by other watcher helpers (each line a JSON object)
    and returns events whose ``timestamp`` ≥ ``since`` (epoch seconds).
    """
    p = Path(path).resolve()
    events = []
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    if obj.get("timestamp", 0) >= since:
                        events.append(obj)
                except json.JSONDecodeError:
                    continue
        return {"status": "success", "message": f"Read {len(events)} events", "data": events}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "data": []}


def watch_symlinks(directory: str | Path) -> Dict[str, Any]:
    """
    Detect creation, deletion or target change of symbolic links inside ``directory``.
    """
    p = Path(directory).resolve()
    known: Dict[Path, Path] = {}  # link → target
    stop_evt = threading.Event()
    result = {"status": "started", "message": f"Symlink watch on {p}", "data": {}}

    def _snapshot():
        for link in p.rglob("*"):
            if link.is_symlink():
                try:
                    target = link.resolve(strict=False)
                    known[link] = target
                except Exception:
                    known[link] = Path("")  # broken link

    _snapshot()

    def _worker():
        while not stop_evt.is_set():
            try:
                current: Dict[Path, Path] = {}
                for link in p.rglob("*"):
                    if link.is_symlink():
                        try:
                            target = link.resolve(strict=False)
                        except Exception:
                            target = Path("")
                        current[link] = target
                # New links
                for link, tgt in current.items():
                    if link not in known:
                        result["status"] = "created"
                        result["message"] = f"Symlink created: {link}"
                        result["data"] = {"link": str(link), "target": str(tgt)}
                # Deleted links
                for link in set(known) - set(current):
                    result["status"] = "deleted"
                    result["message"] = f"Symlink removed: {link}"
                    result["data"] = {"link": str(link)}
                # Target changes
                for link, old_tgt in known.items():
                    new_tgt = current.get(link)
                    if new_tgt is not None and new_tgt != old_tgt:
                        result["status"] = "changed"
                        result["message"] = f"Symlink target changed: {link}"
                        result["data"] = {"link": str(link), "old_target": str(old_tgt), "new_target": str(new_tgt)}
                known.clear()
                known.update(current)
                time.sleep(2.0)
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)
                break

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    result["data"]["thread"] = t
    result["data"]["stop_event"] = stop_evt
    return result


def monitor_file_creation_rate(directory: str | Path, window: float = 60.0) -> Dict[str, Any]:
    """
    Measure how many files are created in ``directory`` per ``window`` seconds.
    Emits a dict each time the rate is recomputed.
    """
    p = Path(directory).resolve()
    stop_evt = threading.Event()
    result = {"status": "started", "message": f"Creation‑rate monitor on {p}", "data": {}}
    timestamps: List[float] = []

    def _worker():
        while not stop_evt.is_set():
            try:
                for f in p.rglob("*"):
                    if f.is_file():
                        ts = f.stat().st_ctime
                        timestamps.append(ts)
                # prune old timestamps
                now = time.time()
                timestamps[:] = [t for t in timestamps if now - t <= window]
                rate = len(timestamps) / window
                result["status"] = "rate"
                result["message"] = f"Current creation rate: {rate:.2f} files/sec"
                result["data"] = {"rate": rate, "window": window}
                time.sleep(window / 2)
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)
                break

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    result["data"]["thread"] = t
    result["data"]["stop_event"] = stop_evt
    return result


def detect_large_files(directory: str | Path, size_limit: int = 100 * 1024 * 1024) -> Dict[str, Any]:
    """
    Scan ``directory`` (recursively) and return a list of files larger than
    ``size_limit`` bytes.
    """
    p = Path(directory).resolve()
    large: List[str] = []
    try:
        for f in p.rglob("*"):
            if f.is_file() and f.stat().st_size > size_limit:
                large.append(str(f))
        return {
            "status": "success",
            "message": f"Found {len(large)} large files",
            "data": {"files": large, "size_limit": size_limit},
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc), "data": {}}


def watch_file_encoding(filepath: str | Path) -> Dict[str, Any]:
    """
    Attempt to guess the text encoding of ``filepath`` using ``chardet``.
    Returns the guessed encoding and confidence.
    """
    try:
        import chardet
    except ImportError:
        return {"status": "error", "message": "chardet library not installed", "data": {}}

    p = Path(filepath).resolve()
    try:
        with p.open("rb") as f:
            raw = f.read(1024 * 100)  # read first 100 KB
        guess = chardet.detect(raw)
        return {
            "status": "success",
            "message": f"Encoding detection for {p}",
            "data": {"encoding": guess.get("encoding"), "confidence": guess.get("confidence")},
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc), "data": {}}