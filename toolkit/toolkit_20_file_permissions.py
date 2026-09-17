"""
toolkit_20_file_permissions.py
Read and modify Windows file/folder ACL permissions, ownership,
and inheritance via Python icacls/PowerShell. No external deps.
"""
from __future__ import annotations
import subprocess
import os
import stat
from typing import Any, Dict, List

def _run(cmd: list) -> tuple:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout.strip(), result.returncode

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()

def get_permissions(path: str) -> Dict[str, Any]:
    """Get ACL permissions for a file or folder using icacls."""
    try:
        out, code = _run(["icacls", path])
        lines = [l.strip() for l in out.splitlines() if l.strip() and "Successfully" not in l]
        return {"success": True, "data": {"path": path, "acl_lines": lines}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_owner(path: str) -> Dict[str, Any]:
    try:
        out = _run_ps('(Get-Acl "' + path + '").Owner')
        return {"success": True, "data": out.strip(), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_acl_details(path: str) -> Dict[str, Any]:
    try:
        script = '(Get-Acl "' + path + '").Access | Select-Object IdentityReference,FileSystemRights,AccessControlType,IsInherited | ConvertTo-Json -Depth 3'
        out = _run_ps(script)
        import json
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def grant_full_control(path: str, account: str) -> Dict[str, Any]:
    try:
        out, code = _run(["icacls", path, "/grant", account + ":(F)"])
        return {"success": code == 0, "data": out, "error": None if code == 0 else out}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def grant_read_access(path: str, account: str) -> Dict[str, Any]:
    try:
        out, code = _run(["icacls", path, "/grant", account + ":(R)"])
        return {"success": code == 0, "data": out, "error": None if code == 0 else out}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def grant_modify_access(path: str, account: str) -> Dict[str, Any]:
    try:
        out, code = _run(["icacls", path, "/grant", account + ":(M)"])
        return {"success": code == 0, "data": out, "error": None if code == 0 else out}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def deny_access(path: str, account: str) -> Dict[str, Any]:
    try:
        out, code = _run(["icacls", path, "/deny", account + ":(F)"])
        return {"success": code == 0, "data": out, "error": None if code == 0 else out}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def remove_access(path: str, account: str) -> Dict[str, Any]:
    try:
        out, code = _run(["icacls", path, "/remove", account])
        return {"success": code == 0, "data": out, "error": None if code == 0 else out}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def reset_permissions(path: str) -> Dict[str, Any]:
    """Reset to inherited permissions."""
    try:
        out, code = _run(["icacls", path, "/reset"])
        return {"success": code == 0, "data": out, "error": None if code == 0 else out}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def disable_inheritance(path: str, copy_existing: bool = True) -> Dict[str, Any]:
    try:
        flag = "/c" if copy_existing else "/r"
        out, code = _run(["icacls", path, "/inheritance:d" + flag])
        return {"success": code == 0, "data": out, "error": None if code == 0 else out}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def enable_inheritance(path: str) -> Dict[str, Any]:
    try:
        out, code = _run(["icacls", path, "/inheritance:e"])
        return {"success": code == 0, "data": out, "error": None if code == 0 else out}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def take_ownership(path: str) -> Dict[str, Any]:
    try:
        out, code = _run(["takeown", "/f", path])
        return {"success": code == 0, "data": out, "error": None if code == 0 else out}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def take_ownership_recursive(path: str) -> Dict[str, Any]:
    try:
        out, code = _run(["takeown", "/f", path, "/r", "/d", "y"])
        return {"success": code == 0, "data": out, "error": None if code == 0 else out}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_owner(path: str, account: str) -> Dict[str, Any]:
    try:
        script = '''
$acl = Get-Acl "''' + path + '''"
$owner = New-Object System.Security.Principal.NTAccount("''' + account + '''")
$acl.SetOwner($owner)
Set-Acl "''' + path + '''" $acl
"OK"
'''
        out = _run_ps(script)
        return {"success": True, "data": "Owner set to " + account, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def is_readonly(path: str) -> Dict[str, Any]:
    try:
        attrs = os.stat(path)
        readonly = not (attrs.st_mode & stat.S_IWRITE)
        return {"success": True, "data": readonly, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_readonly(path: str, readonly: bool = True) -> Dict[str, Any]:
    try:
        if readonly:
            os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        else:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        return {"success": True, "data": {"readonly": readonly}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_file_attributes(path: str) -> Dict[str, Any]:
    try:
        script = '(Get-ItemProperty -Path "' + path + '").Attributes.ToString()'
        out = _run_ps(script)
        return {"success": True, "data": out.strip(), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_hidden(path: str, hidden: bool = True) -> Dict[str, Any]:
    try:
        action = "+H" if hidden else "-H"
        out, code = _run(["attrib", action, path])
        return {"success": code == 0, "data": {"hidden": hidden}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_system_attribute(path: str, system: bool = True) -> Dict[str, Any]:
    try:
        action = "+S" if system else "-S"
        out, code = _run(["attrib", action, path])
        return {"success": code == 0, "data": {"system": system}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def export_permissions(path: str, output_file: str) -> Dict[str, Any]:
    try:
        out, code = _run(["icacls", path, "/save", output_file, "/t"])
        return {"success": code == 0, "data": {"saved_to": output_file}, "error": None if code == 0 else out}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
