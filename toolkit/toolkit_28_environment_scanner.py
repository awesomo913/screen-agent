"""
toolkit_28_environment_scanner.py
Scan the runtime environment: Python info, installed packages, PATH analysis,
virtual env detection, sys.path, and environment variable inspection.
"""
from __future__ import annotations
import sys
import os
import subprocess
import platform
from pathlib import Path
from typing import Any, Dict, List

def get_python_info() -> Dict[str, Any]:
    try:
        return {"success": True, "data": {
            "version": sys.version,
            "version_info": list(sys.version_info[:3]),
            "executable": sys.executable,
            "platform": sys.platform,
            "prefix": sys.prefix,
            "base_prefix": getattr(sys, "base_prefix", sys.prefix),
            "maxsize": sys.maxsize,
            "byteorder": sys.byteorder
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def is_virtual_env() -> Dict[str, Any]:
    try:
        in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
        conda_prefix = os.environ.get("CONDA_PREFIX", "")
        venv_name = os.environ.get("VIRTUAL_ENV", "") or os.environ.get("CONDA_DEFAULT_ENV", "")
        return {"success": True, "data": {
            "in_venv": in_venv or bool(conda_prefix),
            "venv_path": sys.prefix if in_venv else None,
            "conda_env": conda_prefix or None,
            "env_name": venv_name or None
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_installed_packages() -> Dict[str, Any]:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True, text=True, timeout=30
        )
        import json
        data = json.loads(result.stdout) if result.stdout else []
        return {"success": True, "data": {"count": len(data), "packages": data}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def is_package_installed(package_name: str) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package_name],
            capture_output=True, text=True, timeout=15
        )
        installed = result.returncode == 0
        version = None
        if installed:
            for line in result.stdout.splitlines():
                if line.startswith("Version:"):
                    version = line.split(":", 1)[1].strip()
        return {"success": True, "data": {"installed": installed, "version": version, "name": package_name}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_package_info(package_name: str) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package_name],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return {"success": False, "data": None, "error": "Package not found: " + package_name}
        info = {}
        for line in result.stdout.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                info[k.strip()] = v.strip()
        return {"success": True, "data": info, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_sys_path() -> Dict[str, Any]:
    try:
        return {"success": True, "data": sys.path, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_path_entries() -> Dict[str, Any]:
    """List all directories on the system PATH, with existence check."""
    try:
        path_var = os.environ.get("PATH", "")
        entries = path_var.split(os.pathsep)
        result = []
        for e in entries:
            result.append({"path": e, "exists": os.path.isdir(e)})
        return {"success": True, "data": {"count": len(result), "entries": result}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_in_path(executable: str) -> Dict[str, Any]:
    """Find where an executable lives on PATH."""
    try:
        import shutil
        location = shutil.which(executable)
        return {"success": True, "data": {"executable": executable, "location": location, "found": location is not None}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_env_variable(name: str) -> Dict[str, Any]:
    try:
        value = os.environ.get(name)
        return {"success": True, "data": {"name": name, "value": value, "set": value is not None}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_env_variables(filter_prefix: str = "") -> Dict[str, Any]:
    try:
        env = dict(os.environ)
        if filter_prefix:
            env = {k: v for k, v in env.items() if k.upper().startswith(filter_prefix.upper())}
        return {"success": True, "data": {"count": len(env), "variables": env}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_site_packages_dir() -> Dict[str, Any]:
    try:
        import site
        dirs = site.getsitepackages()
        user_dir = site.getusersitepackages()
        return {"success": True, "data": {"site_packages": dirs, "user_site": user_dir}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_pip_available() -> Dict[str, Any]:
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, text=True, timeout=10)
        return {"success": result.returncode == 0, "data": {"version_output": result.stdout.strip()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_platform_info() -> Dict[str, Any]:
    try:
        return {"success": True, "data": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "architecture": platform.architecture()[0],
            "node": platform.node()
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_python_builtins() -> Dict[str, Any]:
    """List available built-in modules."""
    try:
        return {"success": True, "data": sorted(sys.builtin_module_names), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_current_working_directory() -> Dict[str, Any]:
    try:
        cwd = os.getcwd()
        return {"success": True, "data": {"cwd": cwd, "exists": os.path.isdir(cwd)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_home_directory() -> Dict[str, Any]:
    try:
        home = str(Path.home())
        return {"success": True, "data": {"home": home, "exists": os.path.isdir(home)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_user_directories() -> Dict[str, Any]:
    try:
        user_profile = os.environ.get("USERPROFILE", str(Path.home()))
        dirs = {
            "profile": user_profile,
            "desktop": os.path.join(user_profile, "Desktop"),
            "documents": os.path.join(user_profile, "Documents"),
            "downloads": os.path.join(user_profile, "Downloads"),
            "pictures": os.path.join(user_profile, "Pictures"),
            "appdata": os.environ.get("APPDATA", ""),
            "localappdata": os.environ.get("LOCALAPPDATA", ""),
            "temp": os.environ.get("TEMP", "")
        }
        for k, v in dirs.items():
            dirs[k] = {"path": v, "exists": os.path.isdir(v)}
        return {"success": True, "data": dirs, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
