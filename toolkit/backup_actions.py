import shutil
import pathlib
import os
import zipfile
import tarfile
import hashlib
import json
import time
import datetime
import sqlite3
import threading
import sys
import subprocess
from typing import Dict, Any, Optional, List, Tuple


def _result(success: bool, message: str, data: Optional[Any] = None, error: Optional[str] = None) -> Dict[str, Any]:
    """Standardized result dictionary."""
    return {
        "success": success,
        "message": message,
        "data": data,
        "error": error
    }


def _compute_file_hash(file_path: pathlib.Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def create_backup(source: str, dest: str, format: str) -> Dict[str, Any]:
    """Create a full backup archive."""
    try:
        src = pathlib.Path(source).resolve()
        if not src.exists():
            return _result(False, f"Source path '{source}' does not exist.")
        
        dest_path = pathlib.Path(dest).resolve()
        dest_path.mkdir(parents=True, exist_ok=True)
        
        supported = {"zip", "tar", "gztar", "bztar"}
        fmt = format.lower()
        if fmt not in supported:
            return _result(False, f"Unsupported format '{format}'. Supported: {supported}")
            
        archive_base = str(dest_path / f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        created_path = shutil.make_archive(archive_base, fmt, str(src))
        
        stat = os.stat(created_path)
        return _result(
            True, 
            "Backup created successfully.", 
            {
                "archive_path": created_path,
                "format": fmt,
                "size_bytes": stat.st_size,
                "created_at": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
            }
        )
    except Exception as e:
        return _result(False, "Failed to create backup.", error=str(e))


def restore_backup(backup_path: str, dest: str) -> Dict[str, Any]:
    """Restore a backup archive to a destination."""
    try:
        bp = pathlib.Path(backup_path).resolve()
        if not bp.exists():
            return _result(False, f"Backup file '{backup_path}' not found.")
            
        dest_path = pathlib.Path(dest).resolve()
        dest_path.mkdir(parents=True, exist_ok=True)
        
        ext = bp.suffix.lower()
        if ext == ".zip":
            with zipfile.ZipFile(bp, "r") as z:
                z.extractall(dest_path)
                files = z.namelist()
        elif ext in {".tar", ".gz", ".tgz", ".bz2", ".tbz2"}:
            mode = "r:bz2" if ext in {".bz2", ".tbz2"} else "r:gz" if ext in {".gz", ".tgz"} else "r"
            with tarfile.open(bp, mode) as t:
                t.extractall(dest_path)
                files = t.getnames()
        else:
            return _result(False, "Unsupported archive format for restoration.")
            
        return _result(True, "Backup restored successfully.", {"extracted_files": len(files), "destination": str(dest_path)})
    except Exception as e:
        return _result(False, "Failed to restore backup.", error=str(e))


def incremental_backup(source: str, dest: str, manifest: Dict) -> Dict[str, Any]:
    """Backup only files that are new or modified since the last manifest."""
    try:
        src = pathlib.Path(source).resolve()
        dest_path = pathlib.Path(dest).resolve()
        dest_path.mkdir(parents=True, exist_ok=True)
        
        new_manifest = {}
        copied = 0
        
        for file_path in src.rglob("*"):
            if not file_path.is_file():
                continue
                
            rel_path = str(file_path.relative_to(src))
            stat = file_path.stat()
            current_hash = _compute_file_hash(file_path)
            file_info = {"size": stat.st_size, "mtime": stat.st_mtime, "hash": current_hash}
            new_manifest[rel_path] = file_info
            
            if rel_path in manifest:
                if manifest[rel_path].get("hash") == current_hash:
                    continue  # Unchanged
                    
            dest_file = dest_path / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(file_path), str(dest_file))
            copied += 1
            
        return _result(True, f"Incremental backup completed. {copied} files copied.", {"new_manifest": new_manifest, "copied_count": copied})
    except Exception as e:
        return _result(False, "Incremental backup failed.", error=str(e))


def differential_backup(source: str, dest: str, base_manifest: Dict) -> Dict[str, Any]:
    """Backup all files changed since the base manifest, without updating reference."""
    try:
        src = pathlib.Path(source).resolve()
        dest_path = pathlib.Path(dest).resolve()
        dest_path.mkdir(parents=True, exist_ok=True)
        
        copied = 0
        for file_path in src.rglob("*"):
            if not file_path.is_file():
                continue
                
            rel_path = str(file_path.relative_to(src))
            current_hash = _compute_file_hash(file_path)
            
            # If not in base or hash differs, it's changed
            if rel_path not in base_manifest or base_manifest[rel_path].get("hash") != current_hash:
                dest_file = dest_path / rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(file_path), str(dest_file))
                copied += 1
                
        return _result(True, f"Differential backup completed. {copied} files copied.", {"copied_count": copied})
    except Exception as e:
        return _result(False, "Differential backup failed.", error=str(e))