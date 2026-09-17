"""
toolkit_23_windows_search.py
Search for files and content using Windows Search index (WDS),
Everything-style rapid enumeration, and content search via PowerShell/cmd.
"""
from __future__ import annotations
import subprocess
import os
import glob
import fnmatch
from pathlib import Path
from typing import Any, Dict, List

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()

def search_files_by_name(folder: str, pattern: str, recursive: bool = True) -> Dict[str, Any]:
    """Search for files matching a glob pattern."""
    try:
        results = []
        if recursive:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if fnmatch.fnmatch(f.lower(), pattern.lower()):
                        results.append(os.path.join(root, f))
        else:
            results = glob.glob(os.path.join(folder, pattern))
        return {"success": True, "data": {"count": len(results), "files": results[:500]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def search_files_by_extension(folder: str, extension: str, recursive: bool = True) -> Dict[str, Any]:
    try:
        ext = extension if extension.startswith(".") else "." + extension
        results = []
        if recursive:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith(ext.lower()):
                        results.append(os.path.join(root, f))
        else:
            results = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(ext.lower())]
        return {"success": True, "data": {"count": len(results), "files": results[:500]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def search_content_in_files(folder: str, search_text: str, extension: str = "*.txt", recursive: bool = True) -> Dict[str, Any]:
    """Search for text content inside files."""
    try:
        out = _run_ps('Get-ChildItem -Path "' + folder + '" -Filter "' + extension + '" -Recurse:$' + str(recursive).lower() + ' | Select-String -Pattern "' + search_text + '" | Select-Object Filename,LineNumber,Line | ConvertTo-Json -Depth 3')
        import json
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_large_files(folder: str, min_size_mb: float = 100, recursive: bool = True) -> Dict[str, Any]:
    try:
        min_bytes = min_size_mb * 1024 * 1024
        results = []
        if recursive:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        size = os.path.getsize(fp)
                        if size >= min_bytes:
                            results.append({"path": fp, "size_mb": round(size / 1048576, 2)})
                    except OSError:
                        pass
        else:
            for f in os.listdir(folder):
                fp = os.path.join(folder, f)
                if os.path.isfile(fp):
                    size = os.path.getsize(fp)
                    if size >= min_bytes:
                        results.append({"path": fp, "size_mb": round(size / 1048576, 2)})
        results.sort(key=lambda x: x["size_mb"], reverse=True)
        return {"success": True, "data": {"count": len(results), "files": results[:100]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_files_modified_since(folder: str, days_ago: int = 7, recursive: bool = True) -> Dict[str, Any]:
    import time
    try:
        cutoff = time.time() - (days_ago * 86400)
        results = []
        if recursive:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        if os.path.getmtime(fp) >= cutoff:
                            results.append(fp)
                    except OSError:
                        pass
        else:
            for f in os.listdir(folder):
                fp = os.path.join(folder, f)
                if os.path.isfile(fp) and os.path.getmtime(fp) >= cutoff:
                    results.append(fp)
        return {"success": True, "data": {"count": len(results), "files": results[:500]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_empty_folders(folder: str) -> Dict[str, Any]:
    try:
        empty = []
        for root, dirs, files in os.walk(folder, topdown=False):
            if not dirs and not files:
                empty.append(root)
        return {"success": True, "data": empty, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_duplicate_names(folder: str, recursive: bool = True) -> Dict[str, Any]:
    """Find files that share the same name (different paths)."""
    try:
        from collections import defaultdict
        name_map: dict = defaultdict(list)
        if recursive:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    name_map[f.lower()].append(os.path.join(root, f))
        else:
            for f in os.listdir(folder):
                if os.path.isfile(os.path.join(folder, f)):
                    name_map[f.lower()].append(os.path.join(folder, f))
        dupes = {k: v for k, v in name_map.items() if len(v) > 1}
        return {"success": True, "data": {"duplicate_count": len(dupes), "duplicates": dupes}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def search_registry(key_path: str, value_name: str = "") -> Dict[str, Any]:
    """Search Windows Registry for a key/value."""
    try:
        if value_name:
            script = 'Get-ItemProperty -Path "' + key_path + '" -Name "' + value_name + '" -ErrorAction SilentlyContinue | ConvertTo-Json -Depth 2'
        else:
            script = 'Get-ItemProperty -Path "' + key_path + '" -ErrorAction SilentlyContinue | ConvertTo-Json -Depth 2'
        out = _run_ps(script)
        import json
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def search_files_by_size_range(folder: str, min_kb: float = 0, max_kb: float = 1024, recursive: bool = True) -> Dict[str, Any]:
    try:
        min_b = min_kb * 1024
        max_b = max_kb * 1024
        results = []
        if recursive:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        sz = os.path.getsize(fp)
                        if min_b <= sz <= max_b:
                            results.append({"path": fp, "size_kb": round(sz / 1024, 2)})
                    except OSError:
                        pass
        return {"success": True, "data": {"count": len(results), "files": results[:200]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_folder_stats(folder: str) -> Dict[str, Any]:
    try:
        total_size = 0
        file_count = 0
        folder_count = 0
        ext_counts: dict = {}
        for root, dirs, files in os.walk(folder):
            folder_count += len(dirs)
            for f in files:
                file_count += 1
                fp = os.path.join(root, f)
                try:
                    total_size += os.path.getsize(fp)
                except OSError:
                    pass
                ext = Path(f).suffix.lower()
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
        top_exts = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        return {"success": True, "data": {
            "total_size_mb": round(total_size / 1048576, 2),
            "file_count": file_count,
            "folder_count": folder_count,
            "top_extensions": dict(top_exts)
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_files_without_extension(folder: str, recursive: bool = True) -> Dict[str, Any]:
    try:
        results = []
        if recursive:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if "." not in f:
                        results.append(os.path.join(root, f))
        else:
            for f in os.listdir(folder):
                fp = os.path.join(folder, f)
                if os.path.isfile(fp) and "." not in f:
                    results.append(fp)
        return {"success": True, "data": results, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def count_files_by_extension(folder: str, recursive: bool = True) -> Dict[str, Any]:
    try:
        ext_map: dict = {}
        if recursive:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    ext = Path(f).suffix.lower() or "(no ext)"
                    ext_map[ext] = ext_map.get(ext, 0) + 1
        else:
            for f in os.listdir(folder):
                if os.path.isfile(os.path.join(folder, f)):
                    ext = Path(f).suffix.lower() or "(no ext)"
                    ext_map[ext] = ext_map.get(ext, 0) + 1
        return {"success": True, "data": dict(sorted(ext_map.items(), key=lambda x: x[1], reverse=True)), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
