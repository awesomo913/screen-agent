"""
user_accounts.py - Screen Agent Toolkit Module

Manage Windows user accounts, groups, sessions, and policies.
Uses net commands, PowerShell, WMI, and ctypes. No external deps.
"""
from __future__ import annotations
import json, os, re, subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

def list_local_users() -> Dict[str, Any]:
    """List all local user accounts on this machine."""
    try:
        ps = """
Get-LocalUser | Select-Object Name, FullName, Enabled, Description, LastLogon,
  PasswordLastSet, PasswordExpires, PasswordRequired, UserMayChangePassword,
  AccountExpires, SID | ConvertTo-Json -Depth 2
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            if isinstance(data, dict): data = [data]
            for u in data:
                for k in ["LastLogon","PasswordLastSet","AccountExpires"]:
                    if u.get(k) and isinstance(u[k], dict) and "value" in u[k]:
                        u[k] = u[k]["value"]
            return {"success": True, "data": data, "error": None}
        # Fallback: net user
        r2 = subprocess.run(["net","user"], capture_output=True, text=True, timeout=10)
        users = re.findall(r"^(\S+)", r2.stdout, re.MULTILINE)
        return {"success": True, "data": [{"name":u} for u in users if u and "---" not in u], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_user_details(username: str) -> Dict[str, Any]:
    """Get detailed information about a specific user account."""
    try:
        r = subprocess.run(["net","user",username], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return {"success": False, "data": None, "error": f"User not found: {username}"}
        info: Dict[str,str] = {}
        for line in r.stdout.splitlines():
            if "  " in line and line.strip():
                parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
                if len(parts) == 2: info[parts[0].strip()] = parts[1].strip()
        return {"success": True, "data": info, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_local_groups() -> Dict[str, Any]:
    """List all local groups on this machine."""
    try:
        ps = "Get-LocalGroup | Select-Object Name, Description, SID | ConvertTo-Json -Depth 2"
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            if isinstance(data, dict): data = [data]
            return {"success": True, "data": data, "error": None}
        r2 = subprocess.run(["net","localgroup"], capture_output=True, text=True, timeout=10)
        groups = re.findall(r"\*(.*)", r2.stdout)
        return {"success": True, "data": [{"name":g.strip()} for g in groups if g.strip()], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_group_members(group_name: str) -> Dict[str, Any]:
    """List members of a local group."""
    try:
        ps = f"Get-LocalGroupMember -Group '{group_name}' | Select-Object Name, ObjectClass, PrincipalSource | ConvertTo-Json -Depth 2"
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            if isinstance(data, dict): data = [data]
            return {"success": True, "data": data, "error": None}
        r2 = subprocess.run(["net","localgroup",group_name], capture_output=True, text=True, timeout=10)
        members = [l.strip() for l in r2.stdout.splitlines()
                   if l.strip() and "---" not in l and "Members" not in l
                   and "command" not in l.lower() and l.strip()]
        return {"success": True, "data": [{"name":m} for m in members if m], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_local_user(username: str, password: str, full_name: str = "",
                       description: str = "") -> Dict[str, Any]:
    """Create a new local user account."""
    try:
        cmd = ["net","user",username,password,"/ADD"]
        if full_name: cmd += [f"/FULLNAME:{full_name}"]
        if description: cmd += [f"/COMMENT:{description}"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            return {"success": True, "data": {"created":username}, "error": None}
        return {"success": False, "data": None, "error": r.stderr.strip() or r.stdout.strip()}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def delete_local_user(username: str) -> Dict[str, Any]:
    """Delete a local user account."""
    try:
        r = subprocess.run(["net","user",username,"/DELETE"],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            return {"success": True, "data": {"deleted":username}, "error": None}
        return {"success": False, "data": None, "error": r.stderr.strip() or r.stdout.strip()}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def enable_user(username: str) -> Dict[str, Any]:
    """Enable a disabled user account."""
    try:
        r = subprocess.run(["net","user",username,"/ACTIVE:YES"],
                           capture_output=True, text=True, timeout=15)
        return {"success": r.returncode==0, "data": {"user":username,"enabled":True},
                "error": r.stderr.strip() if r.returncode else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def disable_user(username: str) -> Dict[str, Any]:
    """Disable a user account."""
    try:
        r = subprocess.run(["net","user",username,"/ACTIVE:NO"],
                           capture_output=True, text=True, timeout=15)
        return {"success": r.returncode==0, "data": {"user":username,"enabled":False},
                "error": r.stderr.strip() if r.returncode else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def change_password(username: str, new_password: str) -> Dict[str, Any]:
    """Change password for a local user account."""
    try:
        r = subprocess.run(["net","user",username,new_password],
                           capture_output=True, text=True, timeout=15)
        return {"success": r.returncode==0, "data": {"user":username},
                "error": r.stderr.strip() if r.returncode else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def add_user_to_group(username: str, group_name: str) -> Dict[str, Any]:
    """Add a user to a local group."""
    try:
        r = subprocess.run(["net","localgroup",group_name,username,"/ADD"],
                           capture_output=True, text=True, timeout=15)
        return {"success": r.returncode==0, "data": {"user":username,"group":group_name},
                "error": r.stderr.strip() if r.returncode else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def remove_user_from_group(username: str, group_name: str) -> Dict[str, Any]:
    """Remove a user from a local group."""
    try:
        r = subprocess.run(["net","localgroup",group_name,username,"/DELETE"],
                           capture_output=True, text=True, timeout=15)
        return {"success": r.returncode==0, "data": {"user":username,"group":group_name},
                "error": r.stderr.strip() if r.returncode else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_logged_in_users() -> Dict[str, Any]:
    """Get currently logged-in user sessions."""
    try:
        r = subprocess.run(["query","session"], capture_output=True, text=True, timeout=10)
        sessions = []
        for line in r.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 3:
                sessions.append({"session":parts[0].strip(">"),"user":parts[1] if len(parts)>1 else "",
                                   "id":parts[2] if len(parts)>2 else "","state":parts[3] if len(parts)>3 else ""})
        return {"success": True, "data": sessions, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_current_user() -> Dict[str, Any]:
    """Get information about the currently logged-in user."""
    try:
        username = os.environ.get("USERNAME","")
        domain = os.environ.get("USERDOMAIN","")
        profile = os.environ.get("USERPROFILE","")
        ps = "([System.Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)"
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=5)
        is_admin = r.stdout.strip().lower() == "true"
        return {"success": True, "data": {"username":username,"domain":domain,
                "profile_path":profile,"is_admin":is_admin}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def is_user_admin(username: Optional[str] = None) -> Dict[str, Any]:
    """Check if a user has administrator privileges."""
    try:
        if username is None:
            ps = "([System.Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)"
        else:
            ps = f"$groups = (Get-LocalGroupMember -Group 'Administrators').Name; $groups -contains '{username}' -or $groups -contains ($env:COMPUTERNAME + '\\{username}')"
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=10)
        is_admin = r.stdout.strip().lower() == "true"
        return {"success": True, "data": {"username":username or os.environ.get("USERNAME"),"is_admin":is_admin}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_login_history(username: Optional[str] = None) -> Dict[str, Any]:
    """Get recent login/logout events from Windows Event Log."""
    try:
        user_filter = f"Message LIKE '%{username}%' AND " if username else ""
        ps = f"""
Get-WinEvent -FilterHashtable @{{LogName='Security'; Id=4624,4634}} -MaxEvents 50 -ErrorAction SilentlyContinue |
Select-Object TimeCreated, Id, Message |
ConvertTo-Json -Depth 2
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict): data = [data]
                events = []
                for e in data:
                    msg = e.get("Message","")
                    events.append({"time":str(e.get("TimeCreated","")),
                                    "event_id":e.get("Id"),
                                    "type":"logon" if e.get("Id")==4624 else "logoff",
                                    "details":msg[:300]})
                return {"success": True, "data": events, "error": None}
            except Exception: pass
        return {"success": True, "data": [], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def lock_user_account(username: str) -> Dict[str, Any]:
    """Lock a user account by setting an impossible password attempt scenario."""
    try:
        ps = f"Disable-LocalUser -Name '{username}'"
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=10)
        return {"success": r.returncode==0, "data": {"locked":username},
                "error": r.stderr.strip() if r.returncode else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_password_policy() -> Dict[str, Any]:
    """Get local password policy settings."""
    try:
        r = subprocess.run(["net","accounts"], capture_output=True, text=True, timeout=10)
        policy: Dict[str,str] = {}
        for line in r.stdout.splitlines():
            if ":" in line:
                k, _, v = line.partition(":"); policy[k.strip()] = v.strip()
        return {"success": True, "data": policy, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_user_profiles() -> Dict[str, Any]:
    """List all user profiles on this machine from the registry."""
    if not HAS_WINREG:
        return {"success": False, "data": None, "error": "winreg not available"}
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList")
        profiles = []; i = 0
        while True:
            try:
                sid = winreg.EnumKey(key, i); i += 1
                try:
                    sub = winreg.OpenKey(key, sid)
                    path, _ = winreg.QueryValueEx(sub, "ProfileImagePath")
                    winreg.CloseKey(sub)
                    profiles.append({"sid":sid,"profile_path":path,
                                      "username":Path(path).name})
                except OSError: pass
            except OSError: break
        winreg.CloseKey(key)
        return {"success": True, "data": profiles, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
