"""
toolkit_47_app_launcher.py
Launch, manage, and query installed applications on Windows.
Find apps by name, open recently used files, and manage default programs.
"""
from __future__ import annotations
import subprocess
import os
import json
import winreg
from pathlib import Path
from typing import Any, Dict, List

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=20
    )
    return result.stdout.strip()

def launch_app(executable_path: str, arguments: str = "", working_dir: str = "") -> Dict[str, Any]:
    try:
        cmd = [executable_path]
        if arguments:
            cmd.extend(arguments.split())
        kwargs = {}
        if working_dir:
            kwargs["cwd"] = working_dir
        proc = subprocess.Popen(cmd, **kwargs)
        return {"success": True, "data": {"pid": proc.pid, "executable": executable_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def open_with_default_app(file_path: str) -> Dict[str, Any]:
    """Open a file with its default associated application."""
    try:
        os.startfile(file_path)
        return {"success": True, "data": "Opened: " + file_path, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def open_url_in_browser(url: str) -> Dict[str, Any]:
    try:
        import webbrowser
        webbrowser.open(url)
        return {"success": True, "data": "URL opened: " + url, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def launch_app_by_name(app_name: str) -> Dict[str, Any]:
    """Try to find and launch an app by searching common paths and registry."""
    try:
        common_paths = [
            os.environ.get("PROGRAMFILES", "C:\\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
            "C:\\Windows\\System32"
        ]
        for base in common_paths:
            if not base:
                continue
            for root, dirs, files in os.walk(base):
                for f in files:
                    if f.lower() == app_name.lower() + ".exe" or f.lower() == app_name.lower():
                        exe = os.path.join(root, f)
                        proc = subprocess.Popen([exe])
                        return {"success": True, "data": {"found": exe, "pid": proc.pid}, "error": None}
        return {"success": False, "data": None, "error": "App not found: " + app_name}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_app_path(app_name: str) -> Dict[str, Any]:
    """Search for an executable by name."""
    try:
        import shutil
        path = shutil.which(app_name)
        if path:
            return {"success": True, "data": {"name": app_name, "path": path}, "error": None}
        exts = [".exe", ".cmd", ".bat", ""]
        for ext in exts:
            target = app_name + ext
            p = shutil.which(target)
            if p:
                return {"success": True, "data": {"name": target, "path": p}, "error": None}
        return {"success": True, "data": {"name": app_name, "path": None, "found": False}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_installed_apps_registry() -> Dict[str, Any]:
    """Query Windows registry for installed apps."""
    try:
        apps = []
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"),
            (winreg.HKEY_CURRENT_USER, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall")
        ]
        for hive, subkey in reg_paths:
            try:
                key = winreg.OpenKey(hive, subkey)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sub = winreg.OpenKey(key, winreg.EnumKey(key, i))
                        def _get(name):
                            try: return winreg.QueryValueEx(sub, name)[0]
                            except: return ""
                        name = _get("DisplayName")
                        if name:
                            apps.append({
                                "name": name,
                                "version": _get("DisplayVersion"),
                                "publisher": _get("Publisher"),
                                "install_location": _get("InstallLocation"),
                                "uninstall_string": _get("UninstallString")
                            })
                        winreg.CloseKey(sub)
                    except Exception:
                        pass
                winreg.CloseKey(key)
            except Exception:
                pass
        return {"success": True, "data": {"count": len(apps), "apps": apps}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def search_installed_apps(keyword: str) -> Dict[str, Any]:
    try:
        r = get_installed_apps_registry()
        if not r["success"]:
            return r
        matches = [a for a in r["data"]["apps"] if keyword.lower() in a["name"].lower()]
        return {"success": True, "data": {"count": len(matches), "apps": matches}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def open_windows_settings(page: str = "") -> Dict[str, Any]:
    """Open Windows Settings. page: 'system', 'display', 'network', 'bluetooth', etc."""
    try:
        url = "ms-settings:" + page
        subprocess.Popen(["explorer", url])
        return {"success": True, "data": "Settings opened: " + url, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def open_control_panel() -> Dict[str, Any]:
    try:
        subprocess.Popen(["control"])
        return {"success": True, "data": "Control Panel opened", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def open_task_manager() -> Dict[str, Any]:
    try:
        subprocess.Popen(["taskmgr"])
        return {"success": True, "data": "Task Manager opened", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def open_device_manager() -> Dict[str, Any]:
    try:
        subprocess.Popen(["devmgmt.msc"])
        return {"success": True, "data": "Device Manager opened", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def open_event_viewer() -> Dict[str, Any]:
    try:
        subprocess.Popen(["eventvwr.msc"])
        return {"success": True, "data": "Event Viewer opened", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def open_services() -> Dict[str, Any]:
    try:
        subprocess.Popen(["services.msc"])
        return {"success": True, "data": "Services opened", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def run_as_admin(executable_path: str, arguments: str = "") -> Dict[str, Any]:
    """Launch an app with elevated privileges using ShellExecute runas."""
    try:
        import ctypes
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable_path, arguments or None, None, 1)
        success = int(ret) > 32
        return {"success": success, "data": {"result": int(ret)}, "error": None if success else "Elevation failed or cancelled"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_recently_opened_files() -> Dict[str, Any]:
    try:
        recent = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Recent")
        files = []
        if os.path.isdir(recent):
            for f in os.listdir(recent):
                if f.endswith(".lnk"):
                    fp = os.path.join(recent, f)
                    files.append({
                        "name": f[:-4],
                        "modified": os.path.getmtime(fp)
                    })
        files.sort(key=lambda x: x["modified"], reverse=True)
        return {"success": True, "data": {"count": len(files), "files": files[:20]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
