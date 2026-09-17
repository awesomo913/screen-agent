"""
startup_manager.py - Screen Agent Toolkit Module

Manage Windows startup programs: list, add, remove, enable/disable entries
in registry Run keys, Startup folders, and Task Scheduler startup tasks.
Stdlib + winreg only.
"""
from __future__ import annotations
import json, os, re, shutil, subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

_RUN_KEYS = [
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",      "HKCU"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",      "HKLM"),
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",  "HKCU-Once"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",  "HKLM-Once"),
] if HAS_WINREG else []

_STARTUP_FOLDERS = [
    Path(os.environ.get("APPDATA","")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup",
    Path(os.environ.get("PROGRAMDATA","")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "StartUp",
]

def list_startup_registry() -> Dict[str, Any]:
    """List all startup programs registered in registry Run keys."""
    if not HAS_WINREG:
        return {"success": False, "data": None, "error": "winreg not available"}
    try:
        entries = []
        for root, key_path, label in _RUN_KEYS:
            try:
                key = winreg.OpenKey(root, key_path)
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        entries.append({"name":name, "command":value, "source":label, "key_path":key_path})
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except OSError:
                pass
        return {"success": True, "data": entries, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_startup_folder() -> Dict[str, Any]:
    """List startup programs in the Windows Startup folders."""
    try:
        entries = []
        for folder in _STARTUP_FOLDERS:
            if folder.is_dir():
                for f in folder.iterdir():
                    if f.is_file():
                        entries.append({"name":f.stem, "path":str(f),
                                        "extension":f.suffix, "folder":str(folder),
                                        "scope":"user" if "APPDATA" in str(folder).upper() else "all_users"})
        return {"success": True, "data": entries, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_all_startup() -> Dict[str, Any]:
    """List all startup programs from registry and startup folders combined."""
    try:
        reg = list_startup_registry()
        folder = list_startup_folder()
        all_entries = []
        if reg["success"]: all_entries.extend(reg["data"])
        if folder["success"]: all_entries.extend(folder["data"])
        return {"success": True, "data": all_entries, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def add_startup_registry(name: str, command: str, all_users: bool = False,
                          run_once: bool = False) -> Dict[str, Any]:
    """Add a program to registry startup."""
    if not HAS_WINREG:
        return {"success": False, "data": None, "error": "winreg not available"}
    try:
        root = winreg.HKEY_LOCAL_MACHINE if all_users else winreg.HKEY_CURRENT_USER
        subkey = "RunOnce" if run_once else "Run"
        key_path = f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\{subkey}"
        key = winreg.OpenKey(root, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)
        return {"success": True, "data": {"name":name,"command":command}, "error": None}
    except PermissionError:
        return {"success": False, "data": None, "error": "Permission denied - run as admin for all_users"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def remove_startup_registry(name: str, all_users: bool = False,
                             run_once: bool = False) -> Dict[str, Any]:
    """Remove a startup registry entry by name."""
    if not HAS_WINREG:
        return {"success": False, "data": None, "error": "winreg not available"}
    try:
        root = winreg.HKEY_LOCAL_MACHINE if all_users else winreg.HKEY_CURRENT_USER
        subkey = "RunOnce" if run_once else "Run"
        key_path = f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\{subkey}"
        key = winreg.OpenKey(root, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, name)
        winreg.CloseKey(key)
        return {"success": True, "data": {"removed": name}, "error": None}
    except FileNotFoundError:
        return {"success": False, "data": None, "error": f"Entry not found: {name}"}
    except PermissionError:
        return {"success": False, "data": None, "error": "Permission denied"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def add_startup_shortcut(name: str, target_path: str, all_users: bool = False,
                          arguments: str = "", working_dir: str = "") -> Dict[str, Any]:
    """Create a .lnk shortcut in the Startup folder."""
    try:
        folder = _STARTUP_FOLDERS[1] if all_users else _STARTUP_FOLDERS[0]
        if not folder.exists():
            return {"success": False, "data": None, "error": f"Startup folder not found: {folder}"}
        shortcut_path = folder / f"{name}.lnk"
        ps_script = f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{shortcut_path}')
$s.TargetPath = '{target_path}'
$s.Arguments = '{arguments}'
$s.WorkingDirectory = '{working_dir or str(Path(target_path).parent)}'
$s.Save()
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps_script],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and shortcut_path.exists():
            return {"success": True, "data": {"shortcut": str(shortcut_path)}, "error": None}
        return {"success": False, "data": None, "error": r.stderr.strip()}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def remove_startup_shortcut(name: str, all_users: bool = False) -> Dict[str, Any]:
    """Remove a .lnk file from the Startup folder."""
    try:
        folder = _STARTUP_FOLDERS[1] if all_users else _STARTUP_FOLDERS[0]
        shortcut = folder / f"{name}.lnk"
        if not shortcut.exists():
            return {"success": False, "data": None, "error": f"Shortcut not found: {shortcut}"}
        shortcut.unlink()
        return {"success": True, "data": {"removed": str(shortcut)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def disable_startup_entry(name: str) -> Dict[str, Any]:
    """Disable a startup entry by moving it to a disabled registry key."""
    if not HAS_WINREG:
        return {"success": False, "data": None, "error": "winreg not available"}
    try:
        DISABLED_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
        # Find the entry first
        for root, key_path, label in _RUN_KEYS[:2]:
            try:
                key = winreg.OpenKey(root, key_path)
                i = 0
                while True:
                    try:
                        n, v, _ = winreg.EnumValue(key, i)
                        if n.lower() == name.lower():
                            winreg.CloseKey(key)
                            # Write disabled flag (03 00 00 00 ... = disabled in StartupApproved)
                            try:
                                dk = winreg.OpenKey(root, DISABLED_KEY, 0, winreg.KEY_SET_VALUE)
                                winreg.SetValueEx(dk, name, 0, winreg.REG_BINARY,
                                                  b"\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
                                winreg.CloseKey(dk)
                                return {"success": True, "data": {"disabled": name, "source": label}, "error": None}
                            except Exception as e2:
                                return {"success": False, "data": None, "error": f"Could not write disabled flag: {e2}"}
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except OSError:
                pass
        return {"success": False, "data": None, "error": f"Entry not found: {name}"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def enable_startup_entry(name: str) -> Dict[str, Any]:
    """Re-enable a disabled startup entry in StartupApproved."""
    if not HAS_WINREG:
        return {"success": False, "data": None, "error": "winreg not available"}
    try:
        DISABLED_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                key = winreg.OpenKey(root, DISABLED_KEY, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, name, 0, winreg.REG_BINARY,
                                  b"\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
                winreg.CloseKey(key)
                return {"success": True, "data": {"enabled": name}, "error": None}
            except OSError:
                pass
        return {"success": False, "data": None, "error": f"Disabled entry not found: {name}"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_startup_impact() -> Dict[str, Any]:
    """Get startup program impact ratings from Windows Task Manager data."""
    try:
        ps = """
Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location, User |
ConvertTo-Json -Depth 2
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            if isinstance(data, dict): data = [data]
            return {"success": True, "data": data, "error": None}
        return {"success": True, "data": [], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_scheduled_startup_tasks() -> Dict[str, Any]:
    """List Task Scheduler tasks set to run at logon or startup."""
    try:
        ps = """
Get-ScheduledTask | Where-Object {
    $_.Triggers | Where-Object {$_.CimClass.CimClassName -match 'Logon|Boot|Startup'}
} | Select-Object TaskName, TaskPath, State, Description |
ConvertTo-Json -Depth 2
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict): data = [data]
                return {"success": True, "data": data, "error": None}
            except json.JSONDecodeError:
                pass
        return {"success": True, "data": [], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_startup_folder_path(all_users: bool = False) -> Dict[str, Any]:
    """Get the path to the Windows Startup folder."""
    try:
        folder = _STARTUP_FOLDERS[1] if all_users else _STARTUP_FOLDERS[0]
        return {"success": True, "data": {"path": str(folder), "exists": folder.is_dir()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def backup_startup_registry(output_path: str) -> Dict[str, Any]:
    """Export all registry startup entries to a JSON backup file."""
    try:
        r = list_startup_registry()
        if not r["success"]: return r
        out = Path(output_path); out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(r["data"], indent=2), encoding="utf-8")
        return {"success": True, "data": {"path":str(out),"count":len(r["data"])}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def restore_startup_registry(backup_path: str) -> Dict[str, Any]:
    """Restore startup registry entries from a JSON backup file."""
    if not HAS_WINREG:
        return {"success": False, "data": None, "error": "winreg not available"}
    try:
        data = json.loads(Path(backup_path).read_text(encoding="utf-8"))
        restored = 0; errors = []
        for entry in data:
            if "name" in entry and "command" in entry:
                try:
                    hkcu = "HKCU" in entry.get("source","")
                    root = winreg.HKEY_CURRENT_USER if hkcu else winreg.HKEY_LOCAL_MACHINE
                    key = winreg.OpenKey(root, entry.get("key_path", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
                                        0, winreg.KEY_SET_VALUE)
                    winreg.SetValueEx(key, entry["name"], 0, winreg.REG_SZ, entry["command"])
                    winreg.CloseKey(key); restored += 1
                except Exception as e2: errors.append(f"{entry['name']}: {e2}")
        return {"success": True, "data": {"restored":restored,"errors":errors}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_startup_by_name(search: str) -> Dict[str, Any]:
    """Search all startup entries by name (case-insensitive)."""
    try:
        r = list_all_startup()
        if not r["success"]: return r
        needle = search.lower()
        matches = [e for e in r["data"] if needle in e.get("name","").lower()
                   or needle in e.get("command","").lower()
                   or needle in e.get("path","").lower()]
        return {"success": True, "data": matches, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def count_startup_entries() -> Dict[str, Any]:
    """Count total startup entries from all sources."""
    try:
        r = list_all_startup()
        if not r["success"]: return r
        reg_count = sum(1 for e in r["data"] if "key_path" in e)
        folder_count = sum(1 for e in r["data"] if "folder" in e)
        return {"success": True, "data": {"total":len(r["data"]),
                "registry":reg_count,"folder":folder_count}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
