"""
toolkit_24_icon_cache.py
Manage Windows icon cache, thumbnail cache, and font cache.
Helps fix broken/missing icons and refresh the shell. Stdlib only.
"""
from __future__ import annotations
import subprocess
import os
import glob
from pathlib import Path
from typing import Any, Dict, List

def _run(cmd: list, timeout: int = 30) -> tuple:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.stdout.strip(), result.returncode

def _run_ps(script: str, timeout: int = 30) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip()

def get_icon_cache_location() -> Dict[str, Any]:
    try:
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        path = os.path.join(local_appdata, "Microsoft", "Windows", "Explorer")
        return {"success": True, "data": {"path": path, "exists": os.path.isdir(path)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_icon_cache_files() -> Dict[str, Any]:
    try:
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        explorer_dir = os.path.join(local_appdata, "Microsoft", "Windows", "Explorer")
        files = []
        if os.path.isdir(explorer_dir):
            for f in os.listdir(explorer_dir):
                if "iconcache" in f.lower() or "thumbcache" in f.lower():
                    fp = os.path.join(explorer_dir, f)
                    files.append({"name": f, "size_kb": round(os.path.getsize(fp) / 1024, 1), "path": fp})
        return {"success": True, "data": {"count": len(files), "files": files}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_icon_cache_total_size() -> Dict[str, Any]:
    try:
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        explorer_dir = os.path.join(local_appdata, "Microsoft", "Windows", "Explorer")
        total = 0
        if os.path.isdir(explorer_dir):
            for f in os.listdir(explorer_dir):
                if "iconcache" in f.lower() or "thumbcache" in f.lower():
                    try:
                        total += os.path.getsize(os.path.join(explorer_dir, f))
                    except OSError:
                        pass
        return {"success": True, "data": {"total_size_mb": round(total / 1048576, 2)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clear_icon_cache() -> Dict[str, Any]:
    """Stop Explorer, delete icon cache files, restart Explorer."""
    try:
        script = """
Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$dir = "$env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer"
Get-ChildItem -Path $dir -Filter "iconcache*" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Start-Process explorer
"OK"
"""
        out = _run_ps(script, timeout=20)
        return {"success": True, "data": "Icon cache cleared and Explorer restarted", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clear_thumbnail_cache() -> Dict[str, Any]:
    """Delete Windows thumbnail cache files."""
    try:
        script = """
$dir = "$env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer"
Get-ChildItem -Path $dir -Filter "thumbcache*" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
"OK"
"""
        out = _run_ps(script)
        return {"success": True, "data": "Thumbnail cache cleared", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clear_all_caches() -> Dict[str, Any]:
    """Clear both icon and thumbnail caches."""
    try:
        script = """
Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$dir = "$env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer"
Get-ChildItem -Path $dir -Filter "iconcache*" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $dir -Filter "thumbcache*" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Start-Process explorer
"OK"
"""
        out = _run_ps(script, timeout=20)
        return {"success": True, "data": "All caches cleared and Explorer restarted", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def restart_explorer() -> Dict[str, Any]:
    try:
        out = _run_ps("Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 1; Start-Process explorer; 'OK'")
        return {"success": True, "data": "Explorer restarted", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def rebuild_font_cache() -> Dict[str, Any]:
    """Rebuild Windows font cache by restarting the font cache service."""
    try:
        script = """
Stop-Service -Name FontCache -Force -ErrorAction SilentlyContinue
Stop-Service -Name FontCache3.0.0.0 -Force -ErrorAction SilentlyContinue
$fontcache = "$env:LOCALAPPDATA\\FontCache"
Remove-Item -Path $fontcache -Recurse -Force -ErrorAction SilentlyContinue
Start-Service -Name FontCache -ErrorAction SilentlyContinue
"OK"
"""
        out = _run_ps(script)
        return {"success": True, "data": "Font cache rebuilt", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_font_cache_size() -> Dict[str, Any]:
    try:
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        font_cache = os.path.join(local_appdata, "FontCache")
        total = 0
        count = 0
        if os.path.isdir(font_cache):
            for root, dirs, files in os.walk(font_cache):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total += os.path.getsize(fp)
                        count += 1
                    except OSError:
                        pass
        return {"success": True, "data": {"path": font_cache, "files": count, "size_mb": round(total / 1048576, 2)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clear_dns_cache() -> Dict[str, Any]:
    try:
        out, code = _run(["ipconfig", "/flushdns"])
        return {"success": code == 0, "data": out, "error": None if code == 0 else out}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clear_temp_files() -> Dict[str, Any]:
    """Delete files from user TEMP folder."""
    try:
        temp = os.environ.get("TEMP", "")
        deleted = 0
        failed = 0
        if os.path.isdir(temp):
            for f in os.listdir(temp):
                fp = os.path.join(temp, f)
                try:
                    if os.path.isfile(fp):
                        os.remove(fp)
                        deleted += 1
                except Exception:
                    failed += 1
        return {"success": True, "data": {"deleted": deleted, "failed": failed, "temp_dir": temp}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_temp_folder_size() -> Dict[str, Any]:
    try:
        temp = os.environ.get("TEMP", "")
        total = 0
        count = 0
        if os.path.isdir(temp):
            for f in os.listdir(temp):
                fp = os.path.join(temp, f)
                if os.path.isfile(fp):
                    try:
                        total += os.path.getsize(fp)
                        count += 1
                    except OSError:
                        pass
        return {"success": True, "data": {"path": temp, "files": count, "size_mb": round(total / 1048576, 2)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clear_prefetch() -> Dict[str, Any]:
    """Clear Windows Prefetch folder (may need admin)."""
    try:
        script = 'Remove-Item "C:\\Windows\\Prefetch\\*" -Force -ErrorAction SilentlyContinue; "OK"'
        out = _run_ps(script)
        return {"success": True, "data": "Prefetch cleared", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clear_recent_files_list() -> Dict[str, Any]:
    """Clear the Recent Files list in Windows Explorer."""
    try:
        script = 'Remove-Item "$env:APPDATA\\Microsoft\\Windows\\Recent\\*" -Force -Recurse -ErrorAction SilentlyContinue; "OK"'
        out = _run_ps(script)
        return {"success": True, "data": "Recent files list cleared", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_windows_update_cache_size() -> Dict[str, Any]:
    try:
        cache_dir = "C:\\Windows\\SoftwareDistribution\\Download"
        total = 0
        count = 0
        if os.path.isdir(cache_dir):
            for root, dirs, files in os.walk(cache_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total += os.path.getsize(fp)
                        count += 1
                    except OSError:
                        pass
        return {"success": True, "data": {"path": cache_dir, "files": count, "size_mb": round(total / 1048576, 2)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
