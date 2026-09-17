"""
registry_actions.py
Screen Agent Toolkit - Windows Registry Operations Module
Fully implemented with type hints, robust error handling, and standardized Dict returns.
"""

import winreg
import ctypes
import json
import pathlib
import os
import subprocess
import re
import time
import threading
from typing import Dict, Any, Optional, Callable, List, Union, Tuple

# Standardized return structure type
RegistryResult = Dict[str, Any]

# Hive string to winreg constant mapping
HIVE_MAP: Dict[str, int] = {
    "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
    "HKCR": winreg.HKEY_CLASSES_ROOT,
    "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
    "HKCU": winreg.HKEY_CURRENT_USER,
    "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
    "HKEY_USERS": winreg.HKEY_USERS,
    "HKU": winreg.HKEY_USERS,
    "HKEY_CURRENT_CONFIG": winreg.HKEY_CURRENT_CONFIG,
    "HKCC": winreg.HKEY_CURRENT_CONFIG,
}

# Registry value type string to winreg constant mapping
TYPE_MAP: Dict[str, int] = {
    "REG_SZ": winreg.REG_SZ,
    "REG_EXPAND_SZ": winreg.REG_EXPAND_SZ,
    "REG_BINARY": winreg.REG_BINARY,
    "REG_DWORD": winreg.REG_DWORD,
    "REG_MULTI_SZ": winreg.REG_MULTI_SZ,
    "REG_QWORD": winreg.REG_QWORD,
}

# Reverse type map for reading
REVERSE_TYPE_MAP: Dict[int, str] = {v: k for k, v in TYPE_MAP.items()}

# ctypes handles for advanced operations
ADVAPI32 = ctypes.WinDLL("advapi32")
USER32 = ctypes.WinDLL("user32")

def _format_result(success: bool, data: Any = None, error: Optional[str] = None) -> RegistryResult:
    """Standardize function return format."""
    return {"success": success, "data": data, "error": error}

def _map_hive(hive: Union[str, int]) -> int:
    """Convert string hive name to winreg constant."""
    if isinstance(hive, int):
        return hive
    hive_upper = hive.upper().strip()
    if hive_upper not in HIVE_MAP:
        raise ValueError(f"Invalid hive: {hive}. Must be one of {list(HIVE_MAP.keys())}")
    return HIVE_MAP[hive_upper]

def _open_key(hive: int, key_path: str, access: int = winreg.KEY_ALL_ACCESS) -> int:
    """Helper to open registry key with consistent error handling."""
    try:
        return winreg.OpenKey(hive, key_path, 0, access)
    except FileNotFoundError:
        raise FileNotFoundError(f"Key not found: {key_path}")
    except PermissionError:
        raise PermissionError(f"Access denied to key: {key_path}")
    except OSError as e:
        raise OSError(f"Registry OS error: {e}")

def _create_or_open_key(hive: int, key_path: str, access: int = winreg.KEY_ALL_ACCESS) -> Tuple[int, bool]:
    """Create or open key, returns (handle, created_new)."""
    try:
        handle, disp = winreg.CreateKeyEx(hive, key_path, 0, access)
        return handle, disp != winreg.REG_OPENED_EXISTING_KEY
    except OSError as e:
        raise OSError(f"Failed to create/open key: {e}")

# =============================================================================
# Core Registry Operations
# =============================================================================

def read_registry_value(hive: Union[str, int], key_path: str, value_name: str = "") -> RegistryResult:
    try:
        hkey = _open_key(_map_hive(hive), key_path, winreg.KEY_READ)
        value, reg_type = winreg.QueryValueEx(hkey, value_name)
        winreg.CloseKey(hkey)
        type_name = REVERSE_TYPE_MAP.get(reg_type, f"UNKNOWN_{reg_type}")
        if reg_type == winreg.REG_MULTI_SZ and isinstance(value, str):
            value = value.split('\x00') if value else []
        return _format_result(True, {"value": value, "type": type_name, "type_code": reg_type})
    except FileNotFoundError:
        return _format_result(False, error=f"Key or value not found: {key_path}\\{value_name}")
    except Exception as e:
        return _format_result(False, error=str(e))

def write_registry_value(hive: Union[str, int], key_path: str, value_name: str, value: Any, value_type: str = "REG_SZ") -> RegistryResult:
    try:
        hkey, created = _create_or_open_key(_map_hive(hive), key_path)
        reg_type = TYPE_MAP.get(value_type.upper())
        if reg_type is None:
            return _format_result(False, error=f"Unsupported value_type: {value_type}")
        
        # Handle type-specific formatting
        if reg_type == winreg.REG_DWORD:
            value = int(value)
        elif reg_type == winreg.REG_QWORD:
            value = int(value)
        elif reg_type == winreg.REG_MULTI_SZ and isinstance(value, list):
            value = '\x00'.join(str(v) for v in value)
        
        winreg.SetValueEx(hkey, value_name, 0, reg_type, value)
        winreg.CloseKey(hkey)
        return _format_result(True, data={"created": created, "type": value_type})
    except Exception as e:
        return _format_result(False, error=str(e))

def delete_registry_value(hive: Union[str, int], key_path: str, value_name: str) -> RegistryResult:
    try:
        hkey = _open_key(_map_hive(hive), key_path, winreg.KEY_WRITE)
        winreg.DeleteValue(hkey, value_name)
        winreg.CloseKey(hkey)
        return _format_result(True, data={"deleted": value_name})
    except FileNotFoundError:
        return _format_result(False, error="Value not found to delete")
    except Exception as e:
        return _format_result(False, error=str(e))

def create_registry_key(hive: Union[str, int], key_path: str) -> RegistryResult:
    try:
        hkey, created = _create_or_open_key(_map_hive(hive), key_path)
        winreg.CloseKey(hkey)
        return _format_result(True, data={"created": created, "path": key_path})
    except Exception as e:
        return _format_result(False, error=str(e))

def delete_registry_key(hive: Union[str, int], key_path: str, recursive: bool = True) -> RegistryResult:
    try:
        hkey = _map_hive(hive)
        if recursive:
            # Use RegDeleteTreeW for robust recursive deletion
            res = ADVAPI32.RegDeleteTreeW(hkey, key_path)
            if res != 0:
                raise ctypes.WinError(res)
        else:
            winreg.DeleteKey(hkey, key_path)
        return _format_result(True, data={"deleted": key_path})
    except FileNotFoundError:
        return _format_result(False, error="Key not found")
    except OSError as e:
        return _format_result(False, error=str(e))

def list_registry_keys(hive: Union[str, int], key_path: str) -> RegistryResult:
    try:
        hkey = _open_key(_map_hive(hive), key_path, winreg.KEY_READ)
        keys = []
        i = 0
        while True:
            try:
                keys.append(winreg.EnumKey(hkey, i))
                i += 1
            except OSError:
                break
        winreg.CloseKey(hkey)
        return _format_result(True, data={"keys": keys, "count": len(keys)})
    except Exception as e:
        return _format_result(False, error=str(e))

def list_registry_values(hive: Union[str, int], key_path: str) -> RegistryResult:
    try:
        hkey = _open_key(_map_hive(hive), key_path, winreg.KEY_READ)
        values = []
        i = 0
        while True:
            try:
                name, data, typ = winreg.EnumValue(hkey, i)
                type_name = REVERSE_TYPE_MAP.get(typ, f"UNKNOWN_{typ}")
                values.append({"name": name, "data": data, "type": type_name})
                i += 1
            except OSError:
                break
        winreg.CloseKey(hkey)
        return _format_result(True, data={"values": values, "count": len(values)})
    except Exception as e:
        return _format_result(False, error=str(e))

def key_exists(hive: Union[str, int], key_path: str) -> RegistryResult:
    try:
        hkey = _open_key(_map_hive(hive), key_path, winreg.KEY_READ)
        winreg.CloseKey(hkey)
        return _format_result(True, data={"exists": True})
    except FileNotFoundError:
        return _format_result(True, data={"exists": False})
    except Exception as e:
        return _format_result(False, error=str(e))

def value_exists(hive: Union[str, int], key_path: str, value_name: str) -> RegistryResult:
    try:
        hkey = _open_key(_map_hive(hive), key_path, winreg.KEY_READ)
        winreg.QueryValueEx(hkey, value_name)
        winreg.CloseKey(hkey)
        return _format_result(True, data={"exists": True})
    except FileNotFoundError:
        return _format_result(False, error="Key not found")
    except OSError:
        return _format_result(True, data={"exists": False})
    except Exception as e:
        return _format_result(False, error=str(e))

# =============================================================================
# Export/Import & Search
# =============================================================================

def export_registry_key(hive: Union[str, int], key_path: str, output: Union[str, pathlib.Path]) -> RegistryResult:
    try:
        out_path = str(pathlib.Path(output).resolve())
        res = subprocess.run(
            ["reg", "export", key_path, out_path, "/y"],
            capture_output=True, text=True, check=False
        )
        if res.returncode == 0:
            return _format_result(True, data={"file": out_path, "size_bytes": os.path.getsize(out_path)})
        return _format_result(False, error=res.stderr.strip() or "Export failed")
    except Exception as e:
        return _format_result(False, error=str(e))

def import_registry_file(filepath: Union[str, pathlib.Path]) -> RegistryResult:
    try:
        fpath = str(pathlib.Path(filepath).resolve())
        if not os.path.isfile(fpath):
            return _format_result(False, error="File not found")
        res = subprocess.run(["reg", "import", fpath], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            return _format_result(True, data={"imported": fpath})
        return _format_result(False, error=res.stderr.strip() or "Import failed")
    except Exception as e:
        return _format_result(False, error=str(e))

def search_registry(hive: Union[str, int], key_path: str, pattern: str, recursive: bool = True) -> RegistryResult:
    try:
        pattern_re = re.compile(pattern, re.IGNORECASE)
        matches: List[Dict[str, Any]] = []
        base_hive = _map_hive(hive)
        
        def _scan(current_path: str):
            try:
                hkey = winreg.OpenKey(base_hive, current_path, 0, winreg.KEY_READ)
                # Check keys
                i = 0
                while True:
                    try:
                        subkey = winreg.EnumKey(hkey, i)
                        full_subkey = f"{current_path}\\{subkey}"
                        if pattern_re.search(full_subkey):
                            matches.append({"type": "key", "path": full_subkey})
                        if recursive:
                            _scan(full_subkey)
                        i += 1
                    except OSError:
                        break
                
                # Check values
                j = 0
                while True:
                    try:
                        vname, vdata, vtype = winreg.EnumValue(hkey, j)
                        if pattern_re.search(vname) or pattern_re.search(str(vdata)):
                            matches.append({"type": "value", "key": current_path, "name": vname, "data": vdata})
                        j += 1
                    except OSError:
                        break
                winreg.CloseKey(hkey)
            except OSError:
                pass

        _scan(key_path)
        return _format_result(True, data={"matches": matches, "count": len(matches)})
    except Exception as e:
        return _format_result(False, error=str(e))

# =============================================================================
# Backup/Restore & Info
# =============================================================================

def backup_registry_key(hive: Union[str, int], key_path: str, output: Union[str, pathlib.Path]) -> RegistryResult:
    try:
        out_path = str(pathlib.Path(output).resolve())
        hkey = _map_hive(hive)
        res = ADVAPI32.RegSaveKeyW(hkey, key_path, out_path)
        if res != 0:
            # Fallback to reg export with .hiv extension if SeBackupPrivilege fails
            out_path_txt = out_path + ".reg"
            return export_registry_key(hive, key_path, out_path_txt)
        return _format_result(True, data={"file": out_path, "size_bytes": os.path.getsize(out_path)})
    except Exception as e:
        return _format_result(False, error=str(e))

def restore_registry_key(hive: Union[str, int], key_path: str, backup_file: Union[str, pathlib.Path]) -> RegistryResult:
    try:
        bpath = str(pathlib.Path(backup_file).resolve())
        if bpath.lower().endswith(".reg"):
            return import_registry_file(bpath)
        
        hkey = _map_hive(hive)
        # Try RegLoadKeyW (requires admin, loads hive file into specified path)
        res = ADVAPI32.RegLoadKeyW(hkey, key_path, bpath)
        if res == 0:
            return _format_result(True, data={"restored": bpath, "target": key_path, "method": "load_key"})
        
        # Fallback: replace via export/import logic or warn
        return _format_result(False, error=f"RegLoadKey failed (code {res}). Requires Administrator privileges. Use .reg files for standard imports.")
    except Exception as e:
        return _format_result(False, error=str(e))

def get_registry_key_info(hive: Union[str, int], key_path: str) -> RegistryResult:
    try:
        hkey = _open_key(_map_hive(hive), key_path, winreg.KEY_READ)
        subkeys, values, last_write = winreg.QueryInfoKey(hkey)
        winreg.CloseKey(hkey)
        # Convert Windows FILETIME to local time string
        lw_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_write))
        return _format_result(True, data={
            "subkey_count": subkeys,
            "value_count": values,
            "last_write_time_local": lw_date,
            "last_write_time_utc_unix": last_write
        })
    except Exception as e:
        return _format_result(False, error=str(e))

# =============================================================================
# Startup & Software Management
# =============================================================================

def set_startup_program(name: str, path: str) -> RegistryResult:
    try:
        startup_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        res = write_registry_value("HKCU", startup_key, name, path, "REG_SZ")
        return res
    except Exception as e:
        return _format_result(False, error=str(e))

def remove_startup_program(name: str) -> RegistryResult:
    try:
        startup_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        return delete_registry_value("HKCU", startup_key, name)
    except Exception as e:
        return _format_result(False, error=str(e))

def list_startup_programs() -> RegistryResult:
    try:
        run_keys = [
            ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
            ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        ]
        programs: List[Dict[str, str]] = []
        for hive, path in run_keys:
            res = list_registry_values(hive, path)
            if res["success"] and res["data"]["values"]:
                for v in res["data"]["values"]:
                    programs.append({"name": v["name"], "path": v["data"], "source": hive})
        return _format_result(True, data={"programs": programs, "count": len(programs)})
    except Exception as e:
        return _format_result(False, error=str(e))

def get_installed_software() -> RegistryResult:
    try:
        uninstall_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
        ]
        software: List[Dict[str, Any]] = []
        for path in uninstall_paths:
            res = list_registry_keys("HKLM", path)
            if res["success"]:
                for app_key in res["data"]["keys"]:
                    full_path = f"{path}\\{app_key}"
                    val_res = list_registry_values("HKLM", full_path)
                    if val_res["success"]:
                        app_info = {"key": app_key}
                        for v in val_res["data"]["values"]:
                            if isinstance(v["data"], str):
                                app_info[v["name"]] = v["data"]
                        if app_info.get("DisplayName"):
                            software.append(app_info)
        return _format_result(True, data={"software": software, "count": len(software)})
    except Exception as e:
        return _format_result(False, error=str(e))

# =============================================================================
# File Associations
# =============================================================================

def get_file_associations(extension: str) -> RegistryResult:
    try:
        if not extension.startswith("."):
            extension = f".{extension}"
        prog_id_res = read_registry_value("HKCR", extension, "")
        prog_id = prog_id_res["data"]["value"] if prog_id_res["success"] else ""
        
        command = ""
        if prog_id:
            cmd_res = read_registry_value("HKCR", f"{prog_id}\\shell\\open\\command", "")
            if cmd_res["success"]:
                command = cmd_res["data"]["value"]
                
        return _format_result(True, data={
            "extension": extension,
            "prog_id": prog_id,
            "command": command
        })
    except Exception as e:
        return _format_result(False, error=str(e))

def set_file_association(extension: str, program: str) -> RegistryResult:
    try:
        if not extension.startswith("."):
            extension = f".{extension}"
        prog_id = f"AgentApp.{extension.replace('.', '')}"
        
        ext_res = write_registry_value("HKCR", extension, "", prog_id, "REG_SZ")
        if not ext_res["success"]: return ext_res
        
        cmd_path = f"{prog_id}\\shell\\open\\command"
        cmd_res = write_registry_value("HKCR", cmd_path, "", f'"{program}" "%1"', "REG_SZ")
        if not cmd_res["success"]: return cmd_res
        
        return _format_result(True, data={"extension": extension, "prog_id": prog_id, "command": f'"{program}" "%1"'})
    except Exception as e:
        return _format_result(False, error=str(e))

# =============================================================================
# Environment Variables
# =============================================================================

def get_environment_variable(name: str, system: bool = False) -> RegistryResult:
    try:
        if system:
            key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
            res = read_registry_value("HKLM", key_path, name)
        else:
            key_path = r"Environment"
            res = read_registry_value("HKCU", key_path, name)
            
        if not res["success"]:
            return _format_result(False, error=f"Variable '{name}' not found in {'system' if system else 'user'} environment")
        
        return res
    except Exception as e:
        return _format_result(False, error=str(e))

def set_environment_variable(name: str, value: str, system: bool = False) -> RegistryResult:
    try:
        if system:
            key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
            hive = "HKLM"
        else:
            key_path = r"Environment"
            hive = "HKCU"
            
        res = write_registry_value(hive, key_path, name, value, "REG_EXPAND_SZ")
        if not res["success"]:
            return res
            
        # Broadcast WM_SETTINGCHANGE so GUI processes pick it up
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        USER32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
            0x0002, 5000, None
        )
        return _format_result(True, data={"name": name, "system": system, "value": value})
    except Exception as e:
        return _format_result(False, error=str(e))

# =============================================================================
# Monitoring & Comparison
# =============================================================================

def monitor_registry_key(hive: Union[str, int], key_path: str, callback: Callable[[Dict[str, Any]], None]) -> RegistryResult:
    try:
        def _monitor_loop():
            hkey = _map_hive(hive)
            handle = winreg.OpenKey(hkey, key_path, 0, winreg.KEY_NOTIFY)
            filter_flags = winreg.REG_NOTIFY_CHANGE_NAME | winreg.REG_NOTIFY_CHANGE_ATTRIBUTES | \
                           winreg.REG_NOTIFY_CHANGE_LAST_SET | winreg.REG_NOTIFY_CHANGE_SECURITY
            try:
                while True:
                    winreg.NotifyChangeKeyValue(handle, True, filter_flags, None, False)
                    callback({
                        "event": "change_detected",
                        "key": key_path,
                        "hive": key_path.split("\\")[0] if "\\" in key_path else hive,
                        "timestamp": time.time(),
                        "iso_time": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
            except OSError:
                pass
            finally:
                try: winreg.CloseKey(handle)
                except: pass

        thread = threading.Thread(target=_monitor_loop, daemon=True)
        thread.start()
        return _format_result(True, data={"thread_id": thread.ident, "status": "monitoring_started"})
    except Exception as e:
        return _format_result(False, error=str(e))

def compare_registry_snapshots(snapshot1: Dict[str, Any], snapshot2: Dict[str, Any]) -> RegistryResult:
    """
    Compare two registry snapshots (Dicts from previous list_* calls).
    Returns added, removed, and modified entries.
    """
    try:
        def _diff_keys(d1: Dict[str, Any], d2: Dict[str, Any]) -> Tuple[List[str], List[str]]:
            s1, s2 = set(d1.keys()), set(d2.keys())
            return list(s1 - s2), list(s2 - s1)
        
        added_keys, removed_keys = _diff_keys(snapshot1, snapshot2)
        modified: Dict[str, Dict[str, Any]] = {}
        
        for k in set(snapshot1.keys()) & set(snapshot2.keys()):
            v1, v2 = snapshot1[k], snapshot2[k]
            if isinstance(v1, dict) and isinstance(v2, dict):
                if v1 != v2:
                    modified[k] = {"old": v1, "new": v2}
            elif v1 != v2:
                modified[k] = {"old": v1, "new": v2}
                
        return _format_result(True, data={
            "added": added_keys,
            "removed": removed_keys,
            "modified": modified,
            "summary": {
                "added_count": len(added_keys),
                "removed_count": len(removed_keys),
                "modified_count": len(modified)
            }
        })
    except Exception as e:
        return _format_result(False, error=str(e))