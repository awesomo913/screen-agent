import os
import shutil
import hashlib
import json
import time
import threading
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Union
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

class FileSyncManager:
    """Production-ready file synchronization manager for agent toolkits."""
    
    def __init__(self) -> None:
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.exclude_patterns: List[str] = []
        self.include_patterns: List[str] = []
        self.is_paused: bool = False
        self.sync_interval: int = 60
        self.observers: Dict[str, Observer] = {}
        self.threads: Dict[str, threading.Thread] = {}
        self.logs: List[Dict[str, Any]] = []
        
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger("FileSyncManager")

    def _log_event(self, action: str, details: str, status: str = "success") -> None:
        entry = {"timestamp": time.time(), "action": action, "details": details, "status": status}
        self.logs.append(entry)
        if status == "error":
            self.logger.error(f"[{action}] {details}")
        else:
            self.logger.info(f"[{action}] {details}")
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]

    def get_file_hash(self, filepath: Union[str, Path], algorithm: str = 'sha256') -> Dict[str, Any]:
        """Calculates the cryptographic hash of a file."""
        try:
            path = Path(filepath)
            if not path.is_file():
                return {"status": "error", "error": f"File not found: {path}"}
            
            hash_func = getattr(hashlib, algorithm)()
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    hash_func.update(chunk)
            return {"status": "success", "hash": hash_func.hexdigest(), "file": str(path)}
        except Exception as e:
            self._log_event("get_file_hash", str(e), "error")
            return {"status": "error", "error": str(e)}

    def compare_files(self, file1: Union[str, Path], file2: Union[str, Path]) -> Dict[str, Any]:
        """Compares two files to check if they are identical."""
        try:
            p1, p2 = Path(file1), Path(file2)
            if not p1.exists() or not p2.exists():
                return {"status": "success", "match": False, "reason": "Missing file(s)"}
            
            if p1.stat().st_size != p2.stat().st_size:
                return {"status": "success", "match": False, "reason": "Size mismatch"}
                
            hash1 = self.get_file_hash(p1).get("hash")
            hash2 = self.get_file_hash(p2).get("hash")
            
            match = hash1 == hash2
            return {"status": "success", "match": match, "reason": "Identical" if match else "Hash mismatch"}
        except Exception as e:
            self._log_event("compare_files", str(e), "error")
            return {"status": "error", "error": str(e)}

    def exclude_pattern(self, pattern: str) -> Dict[str, Any]:
        """Adds a pattern to the exclusion list."""
        if pattern not in self.exclude_patterns:
            self.exclude_patterns.append(pattern)
        return {"status": "success", "exclude_patterns": self.exclude_patterns}

    def include_pattern(self, pattern: str) -> Dict[str, Any]:
        """Adds a pattern to the inclusion list."""
        if pattern not in self.include_patterns:
            self.include_patterns.append(pattern)
        return {"status": "success", "include_patterns": self.include_patterns}

    def create_sync_profile(self, name: str, source: str, target: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Creates a named synchronization profile."""
        try:
            self.profiles[name] = {
                "source": str(Path(source).resolve()),
                "target": str(Path(target).resolve()),
                "options": options or {}
            }
            self._log_event("create_sync_profile", f"Profile '{name}' created.")
            return {"status": "success", "profile": self.profiles[name]}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def export_sync_config(self, filepath: str) -> Dict[str, Any]:
        """Exports all profiles and settings to a JSON file."""
        try:
            config = {
                "profiles": self.profiles,
                "exclude_patterns": self.exclude_patterns,
                "sync_interval": self.sync_interval
            }
            with open(filepath, 'w') as f:
                json.dump(config, f, indent=4)
            return {"status": "success", "file": filepath}
        except Exception as e:
            self._log_event("export_sync_config", str(e), "error")
            return {"status": "error", "error": str(e)}

    def get_sync_status(self) -> Dict[str, Any]:
        """Returns the current operational status of the sync manager."""
        return {
            "status": "success",
            "is_paused": self.is_paused,
            "interval": self.sync_interval,
            "active_watchers": list(self.observers.keys()),
            "active_threads": list(self.threads.keys()),
            "profiles_count": len(self.profiles)
        }

    def get_sync_log(self, limit: int = 50) -> Dict[str, Any]:
        """Retrieves the recent execution logs."""
        return {"status": "success", "logs": self.logs[-limit:]}

    def pause_sync(self) -> Dict[str, Any]:
        """Pauses all background sync operations."""
        self.is_paused = True
        self._log_event("pause_sync", "Synchronization paused.")
        return {"status": "success", "is_paused": True}

    def resume_sync(self) -> Dict[str, Any]:
        """Resumes background sync operations."""
        self.is_paused = False
        self._log_event("resume_sync", "Synchronization resumed.")
        return {"status": "success", "is_paused": False}

    def set_sync_interval(self, seconds: int) -> Dict[str, Any]:
        """Sets the default interval for scheduled syncs."""
        if seconds < 1:
            return {"status": "error", "error": "Interval must be positive"}
        self.sync_interval = seconds
        return {"status": "success", "interval": self.sync_interval}

    def detect_changes(self, src: str, dest: str) -> Dict[str, Any]:
        """Analyzes differences between two directories."""
        try:
            src_path, dest_path = Path(src), Path(dest)
            if not src_path.exists():
                return {"status": "error", "error": "Source directory does not exist"}
                
            new_files, modified_files, deleted_files = [], [], []
            
            src_files = {p.relative_to(src_path): p for p in src_path.rglob('*') if p.is_file()}
            dest_files = {p.relative_to(dest_path): p for p in dest_path.rglob('*') if p.is_file()}
            
            for rel_path, s_file in src_files.items():
                if rel_path not in dest_files:
                    new_files.append(str(rel_path))
                else:
                    d_file = dest_files[rel_path]
                    if s_file.stat().st_mtime > d_file.stat().st_mtime or s_file.stat().st_size != d_file.stat().st_size:
                        modified_files.append(str(rel_path))
                        
            for rel_path in dest_files:
                if rel_path not in src_files:
                    deleted_files.append(str(rel_path))
                    
            return {
                "status": "success",
                "changes": {"new": new_files, "modified": modified_files, "deleted": deleted_files}
            }
        except Exception as e:
            self._log_event("detect_changes", str(e), "error")
            return {"status": "error", "error": str(e)}

    def resolve_conflicts(self, file1: str, file2: str, strategy: str = "newest") -> Dict[str, Any]:
        """Resolves file conflicts based on a strategy (newest, largest)."""
        try:
            p1, p2 = Path(file1), Path(file2)
            if not p1.exists() or not p2.exists():
                return {"status": "error", "error": "One or both files missing"}
                
            winner = None
            if strategy == "newest":
                winner = p1 if p1.stat().st_mtime > p2.stat().st_mtime else p2
            elif strategy == "largest":
                winner = p1 if p1.stat().st_size > p2.stat().st_size else p2
            else:
                return {"status": "error", "error": f"Unknown strategy: {strategy}"}
                
            return {"status": "success", "kept": str(winner), "discarded": str(p2 if winner == p1 else p1)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def mirror_folder(self, src: str, dest: str) -> Dict[str, Any]:
        """Creates an exact 1:1 replica of source into destination."""
        try:
            src_path, dest_path = Path(src), Path(dest)
            if not src_path.exists():
                return {"status": "error", "error": "Source does not exist"}
                
            changes = self.detect_changes(src, dest)
            if changes.get("status") == "error": return changes
            
            c_dict = changes["changes"]
            copied, deleted = 0, 0
            
            for rel_path in c_dict["new"] + c_dict["modified"]:
                s_file = src_path / rel_path
                d_file = dest_path / rel_path
                d_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(s_file, d_file)
                copied += 1
                
            for rel_path in c_dict["deleted"]:
                d_file = dest_path / rel_path
                if d_file.exists():
                    d_file.unlink()
                    deleted += 1
                    
            self._log_event("mirror_folder", f"Copied {copied}, Deleted {deleted} from {dest}")
            return {"status": "success", "copied": copied, "deleted": deleted}
        except Exception as e:
            self._log_event("mirror_folder", str(e), "error")
            return {"status": "error", "error": str(e)}

    def incremental_sync(self, src: str, dest: str) -> Dict[str, Any]:
        """Syncs only new and modified files from source to destination."""
        try:
            changes = self.detect_changes(src, dest)
            if changes.get("status") == "error": return changes
            
            src_path, dest_path = Path(src), Path(dest)
            copied = 0
            
            for rel_path in changes["changes"]["new"] + changes["changes"]["modified"]:
                s_file = src_path / rel_path
                d_file = dest_path / rel_path
                d_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(s_file, d_file)
                copied += 1
                
            return {"status": "success", "files_synced": copied}
        except Exception as e:
            self._log_event("incremental_sync", str(e), "error")
            return {"status": "error", "error": str(e)}

    def full_sync(self, src: str, dest: str) -> Dict[str, Any]:
        """Completely overwrites the destination with the source."""
        try:
            src_path, dest_path = Path(src), Path(dest)
            if dest_path.exists():
                shutil.rmtree(dest_path)
            shutil.copytree(src_path, dest_path)
            self._log_event("full_sync", f"Full sync from {src} to {dest}")
            return {"status": "success", "source": str(src_path), "destination": str(dest_path)}
        except Exception as e:
            self._log_event("full_sync", str(e), "error")
            return {"status": "error", "error": str(e)}

    def sync_directories(self, src: str, dest: str, mode: str = "incremental") -> Dict[str, Any]:
        """Main dispatcher for synchronizing directories based on mode."""
        if mode == "mirror":
            return self.mirror_folder(src, dest)
        elif mode == "full":
            return self.full_sync(src, dest)
        else:
            return self.incremental_sync(src, dest)

    def batch_sync(self, profile_names: List[str]) -> Dict[str, Any]:
        """Executes synchronization sequentially for a list of profiles."""
        results = {}
        for name in profile_names:
            if name in self.profiles:
                prof = self.profiles[name]
                mode = prof.get("options", {}).get("mode", "incremental")
                res = self.sync_directories(prof["source"], prof["target"], mode)
                results[name] = res
            else:
                results[name] = {"status": "error", "error": "Profile not found"}
        return {"status": "success", "batch_results": results}

    def sync_to_remote(self, src: str, remote_dest: str) -> Dict[str, Any]:
        """Pushes data to a remote path (acts as standard sync in this toolkit implementation)."""
        self._log_event("sync_to_remote", f"Pushing {src} to {remote_dest}")
        return self.sync_directories(src, remote_dest, mode="incremental")

    def sync_from_remote(self, remote_src: str, dest: str) -> Dict[str, Any]:
        """Pulls data from a remote path (acts as standard sync in this toolkit implementation)."""
        self._log_event("sync_from_remote", f"Pulling {remote_src} to {dest}")
        return self.sync_directories(remote_src, dest, mode="incremental")

    def compress_before_sync(self, src: str, archive_dest: str, format: str = "zip") -> Dict[str, Any]:
        """Compresses a directory into an archive before syncing."""
        try:
            archive_base = str(Path(archive_dest).with_suffix(''))
            shutil.make_archive(archive_base, format, src)
            return {"status": "success", "archive": f"{archive_base}.{format}"}
        except Exception as e:
            self._log_event("compress_before_sync", str(e), "error")
            return {"status": "error", "error": str(e)}

    def rollback_sync(self, backup_dir: str, target_dir: str) -> Dict[str, Any]:
        """Restores a target directory from a previous backup state."""
        try:
            self._log_event("rollback_sync", f"Rolling back {target_dir} using {backup_dir}")
            return self.full_sync(backup_dir, target_dir)
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def verify_sync_integrity(self, src: str, dest: str) -> Dict[str, Any]:
        """Cryptographically verifies that two directories are identical."""
        try:
            changes = self.detect_changes(src, dest)
            if changes.get("status") == "error": return changes
            
            c = changes["changes"]
            if c["new"] or c["modified"] or c["deleted"]:
                return {"status": "success", "integrity": False, "reason": "Directories differ in structure or metadata"}
                
            src_path = Path(src)
            dest_path = Path(dest)
            mismatches = []
            
            for p in src_path.rglob('*'):
                if p.is_file():
                    rel = p.relative_to(src_path)
                    res = self.compare_files(p, dest_path / rel)
                    if not res.get("match", False):
                        mismatches.append(str(rel))
                        
            if mismatches:
                return {"status": "success", "integrity": False, "mismatches": mismatches}
                
            return {"status": "success", "integrity": True}
        except Exception as e:
            self._log_event("verify_sync_integrity", str(e), "error")
            return {"status": "error", "error": str(e)}

    def schedule_sync(self, src: str, dest: str, interval: int = None, mode: str = "incremental") -> Dict[str, Any]:
        """Runs a recurring synchronization task in a background thread."""
        interval = interval or self.sync_interval
        thread_id = f"sched_{hash(src + dest)}"
        
        def _job():
            while thread_id in self.threads:
                if not self.is_paused:
                    self.sync_directories(src, dest, mode)
                time.sleep(interval)
                
        t = threading.Thread(target=_job, daemon=True)
        self.threads[thread_id] = t
        t.start()
        return {"status": "success", "thread_id": thread_id, "interval": interval}

    def watch_directory(self, watch_dir: str, callback: Callable[[Dict[str, Any]], None] = None) -> Dict[str, Any]:
        """Sets up a real-time watchdog observer on a directory."""
        try:
            class SyncHandler(FileSystemEventHandler):
                def __init__(self, cb: Callable):
                    self.cb = cb
                def on_any_event(self, event: FileSystemEvent):
                    if not event.is_directory:
                        payload = {
                            "event_type": event.event_type,
                            "src_path": event.src_path,
                            "dest_path": getattr(event, 'dest_path', None)
                        }
                        if self.cb:
                            self.cb(payload)

            observer = Observer()
            handler = SyncHandler(callback)
            observer.schedule(handler, watch_dir, recursive=True)
            observer.start()
            
            self.observers[watch_dir] = observer
            self._log_event("watch_directory", f"Started watching {watch_dir}")
            return {"status": "success", "watched_dir": watch_dir}
        except Exception as e:
            self._log_event("watch_directory", str(e), "error")
            return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    sync_manager = FileSyncManager()
