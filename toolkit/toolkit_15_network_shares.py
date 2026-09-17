"""
toolkit_15_network_shares.py
List, create, modify, and remove SMB/Windows network shares and mapped drives.
"""
from __future__ import annotations
import subprocess
import json
import os
from typing import Any, Dict, List

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()

def list_network_shares() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-SmbShare | Select-Object Name,Path,Description,ShareState,CurrentUsers | ConvertTo-Json -Depth 3")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_share_info(share_name: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-SmbShare -Name "' + share_name + '" | Select-Object * | ConvertTo-Json -Depth 3')
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_share(share_name: str, folder_path: str, description: str = "") -> Dict[str, Any]:
    try:
        script = 'New-SmbShare -Name "' + share_name + '" -Path "' + folder_path + '" -Description "' + description + '"'
        out = _run_ps(script)
        return {"success": True, "data": "Share created: " + share_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def remove_share(share_name: str) -> Dict[str, Any]:
    try:
        _run_ps('Remove-SmbShare -Name "' + share_name + '" -Confirm:$false')
        return {"success": True, "data": "Share removed: " + share_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_share_full_access(share_name: str, account: str) -> Dict[str, Any]:
    try:
        _run_ps('Grant-SmbShareAccess -Name "' + share_name + '" -AccountName "' + account + '" -AccessRight Full -Confirm:$false')
        return {"success": True, "data": "Full access granted to " + account, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_share_read_access(share_name: str, account: str) -> Dict[str, Any]:
    try:
        _run_ps('Grant-SmbShareAccess -Name "' + share_name + '" -AccountName "' + account + '" -AccessRight Read -Confirm:$false')
        return {"success": True, "data": "Read access granted to " + account, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def revoke_share_access(share_name: str, account: str) -> Dict[str, Any]:
    try:
        _run_ps('Revoke-SmbShareAccess -Name "' + share_name + '" -AccountName "' + account + '" -Confirm:$false')
        return {"success": True, "data": "Access revoked for " + account, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_share_permissions(share_name: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-SmbShareAccess -Name "' + share_name + '" | Select-Object AccountName,AccessControlType,AccessRight | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_active_connections() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-SmbConnection | Select-Object ServerName,ShareName,UserName,Dialect | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_open_files_on_shares() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-SmbOpenFile | Select-Object FileId,SessionId,Path,ShareRelativePath,ClientUserName | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def close_open_file(file_id: int) -> Dict[str, Any]:
    try:
        _run_ps('Close-SmbOpenFile -FileId ' + str(file_id) + ' -Confirm:$false')
        return {"success": True, "data": "File closed: " + str(file_id), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_mapped_drives() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_MappedLogicalDisk | Select-Object Name,ProviderName,Size,FreeSpace | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def map_network_drive(drive_letter: str, unc_path: str, persist: bool = True) -> Dict[str, Any]:
    try:
        persist_str = "Yes" if persist else "No"
        script = 'net use ' + drive_letter.rstrip("\\") + ': "' + unc_path + '" /persistent:' + persist_str
        out = _run_ps(script)
        return {"success": True, "data": "Drive mapped: " + drive_letter + " -> " + unc_path, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def unmap_network_drive(drive_letter: str) -> Dict[str, Any]:
    try:
        out = _run_ps('net use ' + drive_letter.rstrip("\\") + ': /delete /yes')
        return {"success": True, "data": "Drive unmapped: " + drive_letter, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_smb_sessions() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-SmbSession | Select-Object SessionId,ClientUserName,ClientComputerName,NumOpens | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def close_smb_session(session_id: int) -> Dict[str, Any]:
    try:
        _run_ps('Close-SmbSession -SessionId ' + str(session_id) + ' -Confirm:$false')
        return {"success": True, "data": "Session closed: " + str(session_id), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_smb_server_config() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-SmbServerConfiguration | Select-Object AnnounceServer,EnableSMB1Protocol,EnableSMB2Protocol,RequireSecuritySignature | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_share_count() -> Dict[str, Any]:
    try:
        out = _run_ps("(Get-SmbShare).Count")
        count = int(out.strip()) if out.strip().isdigit() else 0
        return {"success": True, "data": count, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
