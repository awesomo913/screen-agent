"""
toolkit_55_active_directory.py
Query Active Directory / domain info: users, groups, computers,
organizational units via LDAP and PowerShell ADSI. Windows domain tools.
"""
from __future__ import annotations
import subprocess
import json
from typing import Any, Dict, List

try:
    import ldap3
    HAS_LDAP3 = True
except ImportError:
    HAS_LDAP3 = False

def _run_ps(script: str, timeout: int = 30) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip()

def get_domain_info() -> Dict[str, Any]:
    try:
        script = """
try {
    $domain = [System.DirectoryServices.ActiveDirectory.Domain]::GetCurrentDomain()
    @{
        Name = $domain.Name
        Forest = $domain.Forest.Name
        DomainMode = $domain.DomainMode.ToString()
        PDCRoleOwner = $domain.PdcRoleOwner.Name
    } | ConvertTo-Json
} catch {
    @{Error = $_.Exception.Message} | ConvertTo-Json
}
"""
        out = _run_ps(script)
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_current_user_info() -> Dict[str, Any]:
    try:
        script = """
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent()
@{
    Name = $user.Name
    AuthenticationType = $user.AuthenticationType
    IsSystem = $user.IsSystem
    Groups = ($user.Groups | ForEach-Object { $_.Translate([System.Security.Principal.NTAccount]).Value }) -join ","
} | ConvertTo-Json
"""
        out = _run_ps(script)
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def is_domain_joined() -> Dict[str, Any]:
    try:
        script = "(Get-WmiObject Win32_ComputerSystem).PartOfDomain"
        out = _run_ps(script)
        joined = out.strip().lower() == "true"
        return {"success": True, "data": {"domain_joined": joined}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_domain_computers() -> Dict[str, Any]:
    try:
        script = """
try {
    $searcher = New-Object System.DirectoryServices.DirectorySearcher
    $searcher.Filter = "(&(objectClass=computer))"
    $searcher.PropertiesToLoad.AddRange(@("name","operatingSystem","lastLogonDate"))
    $results = $searcher.FindAll()
    $computers = @()
    foreach ($r in $results) {
        $computers += @{
            Name = $r.Properties["name"][0]
            OS = if ($r.Properties["operatingsystem"].Count -gt 0) {$r.Properties["operatingsystem"][0]} else {""}
        }
    }
    $computers | ConvertTo-Json -Depth 3
} catch {
    @{Error=$_.Exception.Message} | ConvertTo-Json
}
"""
        out = _run_ps(script)
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": {"count": len(data), "computers": data}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_domain_users() -> Dict[str, Any]:
    try:
        script = """
try {
    $searcher = New-Object System.DirectoryServices.DirectorySearcher
    $searcher.Filter = "(&(objectClass=user)(objectCategory=person))"
    $searcher.PropertiesToLoad.AddRange(@("samaccountname","displayname","mail","enabled"))
    $results = $searcher.FindAll()
    $users = @()
    foreach ($r in $results) {
        $users += @{
            Username = if ($r.Properties["samaccountname"].Count -gt 0) {$r.Properties["samaccountname"][0]} else {""}
            DisplayName = if ($r.Properties["displayname"].Count -gt 0) {$r.Properties["displayname"][0]} else {""}
            Email = if ($r.Properties["mail"].Count -gt 0) {$r.Properties["mail"][0]} else {""}
        }
    }
    $users | ConvertTo-Json -Depth 3
} catch {
    @{Error=$_.Exception.Message} | ConvertTo-Json
}
"""
        out = _run_ps(script)
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": {"count": len(data), "users": data[:100]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_domain_groups() -> Dict[str, Any]:
    try:
        script = """
try {
    $searcher = New-Object System.DirectoryServices.DirectorySearcher
    $searcher.Filter = "(objectClass=group)"
    $searcher.PropertiesToLoad.AddRange(@("name","description","grouptype"))
    $results = $searcher.FindAll()
    $groups = @()
    foreach ($r in $results) {
        $groups += @{
            Name = if ($r.Properties["name"].Count -gt 0) {$r.Properties["name"][0]} else {""}
            Description = if ($r.Properties["description"].Count -gt 0) {$r.Properties["description"][0]} else {""}
        }
    }
    $groups | ConvertTo-Json -Depth 3
} catch {
    @{Error=$_.Exception.Message} | ConvertTo-Json
}
"""
        out = _run_ps(script)
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": {"count": len(data), "groups": data[:100]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_local_groups() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-LocalGroup | Select-Object Name,Description,SID | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_local_group_members(group_name: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-LocalGroupMember -Group "' + group_name + '" | Select-Object Name,ObjectClass,PrincipalSource | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_administrators() -> Dict[str, Any]:
    return get_local_group_members("Administrators")

def get_domain_controllers() -> Dict[str, Any]:
    try:
        script = """
try {
    $domain = [System.DirectoryServices.ActiveDirectory.Domain]::GetCurrentDomain()
    $dcs = $domain.DomainControllers | ForEach-Object { @{Name=$_.Name; OS=$_.OSVersion; Roles=($_.Roles -join ",")} }
    $dcs | ConvertTo-Json -Depth 3
} catch {
    @{Error=$_.Exception.Message} | ConvertTo-Json
}
"""
        out = _run_ps(script)
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_group_policy_applied() -> Dict[str, Any]:
    try:
        out, code = subprocess.run(["gpresult", "/r", "/scope", "computer"], capture_output=True, text=True, timeout=20).stdout, 0
        lines = out.splitlines()[:30]
        return {"success": True, "data": {"gpo_output_preview": lines}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_ldap3_available() -> Dict[str, Any]:
    return {"success": True, "data": {"ldap3": HAS_LDAP3}, "error": None}

def get_current_logon_server() -> Dict[str, Any]:
    try:
        import os
        server = os.environ.get("LOGONSERVER", "")
        return {"success": True, "data": {"logon_server": server}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_user_account_info(username: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-LocalUser -Name "' + username + '" | Select-Object Name,FullName,Enabled,LastLogon,PasswordExpires,Description | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
