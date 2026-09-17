"""
toolkit_22_shortcut_inspector.py
Read and write Windows .lnk shortcut files via PowerShell WScript.Shell.
"""
from __future__ import annotations
import subprocess
import json
import os
from pathlib import Path
from typing import Any, Dict, List

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()

def read_shortcut(lnk_path: str) -> Dict[str, Any]:
    try:
        script = '''
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut("''' + lnk_path + '''")
@{
    TargetPath=$sc.TargetPath
    Arguments=$sc.Arguments
    WorkingDirectory=$sc.WorkingDirectory
    Description=$sc.Description
    IconLocation=$sc.IconLocation
    WindowStyle=$sc.WindowStyle
    Hotkey=$sc.Hotkey
} | ConvertTo-Json
'''
        out = _run_ps(script)
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_shortcut(lnk_path: str, target_path: str, arguments: str = "", working_dir: str = "", description: str = "", icon: str = "") -> Dict[str, Any]:
    try:
        script = '''
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut("''' + lnk_path + '''")
$sc.TargetPath = "''' + target_path + '''"
$sc.Arguments = "''' + arguments + '''"
$sc.WorkingDirectory = "''' + working_dir + '''"
$sc.Description = "''' + description + '''"
if ("''' + icon + '''" -ne "") { $sc.IconLocation = "''' + icon + '''" }
$sc.Save()
"OK"
'''
        out = _run_ps(script)
        exists = os.path.isfile(lnk_path)
        return {"success": exists, "data": {"created": lnk_path}, "error": None if exists else "File not created"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def update_shortcut_target(lnk_path: str, new_target: str) -> Dict[str, Any]:
    try:
        script = '''
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut("''' + lnk_path + '''")
$sc.TargetPath = "''' + new_target + '''"
$sc.Save()
"OK"
'''
        _run_ps(script)
        return {"success": True, "data": "Target updated", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def update_shortcut_icon(lnk_path: str, icon_path: str, icon_index: int = 0) -> Dict[str, Any]:
    try:
        icon_loc = icon_path + "," + str(icon_index)
        script = '''
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut("''' + lnk_path + '''")
$sc.IconLocation = "''' + icon_loc + '''"
$sc.Save()
"OK"
'''
        _run_ps(script)
        return {"success": True, "data": "Icon updated", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_shortcut_hotkey(lnk_path: str, hotkey: str) -> Dict[str, Any]:
    """hotkey format e.g. 'Ctrl+Alt+F'"""
    try:
        script = '''
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut("''' + lnk_path + '''")
$sc.Hotkey = "''' + hotkey + '''"
$sc.Save()
"OK"
'''
        _run_ps(script)
        return {"success": True, "data": "Hotkey set to " + hotkey, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_desktop_shortcut(name: str, target_path: str, arguments: str = "", description: str = "") -> Dict[str, Any]:
    try:
        desktop = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\Public"), "Desktop")
        lnk_path = os.path.join(desktop, name + ".lnk")
        return create_shortcut(lnk_path, target_path, arguments=arguments, description=description)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_startmenu_shortcut(name: str, target_path: str, arguments: str = "", description: str = "") -> Dict[str, Any]:
    try:
        startmenu = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")
        lnk_path = os.path.join(startmenu, name + ".lnk")
        return create_shortcut(lnk_path, target_path, arguments=arguments, description=description)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_desktop_shortcuts() -> Dict[str, Any]:
    try:
        desktop = os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\Public"), "Desktop")
        shortcuts = [f for f in os.listdir(desktop) if f.endswith(".lnk")]
        return {"success": True, "data": {"desktop": desktop, "shortcuts": shortcuts, "count": len(shortcuts)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_startmenu_shortcuts(recursive: bool = True) -> Dict[str, Any]:
    try:
        startmenu = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")
        shortcuts = []
        if recursive:
            for root, dirs, files in os.walk(startmenu):
                for f in files:
                    if f.endswith(".lnk"):
                        shortcuts.append(os.path.relpath(os.path.join(root, f), startmenu))
        else:
            shortcuts = [f for f in os.listdir(startmenu) if f.endswith(".lnk")]
        return {"success": True, "data": {"count": len(shortcuts), "shortcuts": shortcuts}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_broken_shortcuts(folder: str) -> Dict[str, Any]:
    """Find .lnk files whose target no longer exists."""
    try:
        broken = []
        for root, dirs, files in os.walk(folder):
            for f in files:
                if f.endswith(".lnk"):
                    lnk = os.path.join(root, f)
                    info = read_shortcut(lnk)
                    if info["success"] and info["data"]:
                        target = info["data"].get("TargetPath", "")
                        if target and not os.path.exists(target):
                            broken.append({"shortcut": lnk, "missing_target": target})
        return {"success": True, "data": broken, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def resolve_shortcut_target(lnk_path: str) -> Dict[str, Any]:
    try:
        info = read_shortcut(lnk_path)
        if not info["success"]:
            return info
        target = info["data"].get("TargetPath", "")
        exists = os.path.exists(target) if target else False
        return {"success": True, "data": {"target": target, "exists": exists}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def delete_shortcut(lnk_path: str) -> Dict[str, Any]:
    try:
        os.remove(lnk_path)
        return {"success": True, "data": "Deleted: " + lnk_path, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def batch_read_shortcuts(folder: str) -> Dict[str, Any]:
    try:
        results = []
        for root, dirs, files in os.walk(folder):
            for f in files:
                if f.endswith(".lnk"):
                    lnk = os.path.join(root, f)
                    info = read_shortcut(lnk)
                    results.append({"file": lnk, "data": info.get("data"), "success": info.get("success")})
        return {"success": True, "data": results, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_url_shortcut(lnk_path: str, url: str) -> Dict[str, Any]:
    """Create a .url internet shortcut file."""
    try:
        if not lnk_path.endswith(".url"):
            lnk_path = lnk_path.rstrip(".lnk") + ".url"
        content = "[InternetShortcut]\nURL=" + url + "\n"
        with open(lnk_path, "w") as f:
            f.write(content)
        return {"success": True, "data": {"created": lnk_path, "url": url}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
