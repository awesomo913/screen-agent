"""
toolkit_14_certificate_store.py
Inspect and manage Windows certificate stores via PowerShell and certutil.
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

def _run(cmd: list) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout.strip()

def list_certificates(store: str = "My", location: str = "CurrentUser") -> Dict[str, Any]:
    """List certs from a store. store: My, Root, CA, TrustedPeople, etc."""
    try:
        script = 'Get-ChildItem -Path Cert:\\' + location + '\\' + store + ' | Select-Object Subject,Issuer,Thumbprint,NotBefore,NotAfter,HasPrivateKey | ConvertTo-Json -Depth 3'
        out = _run_ps(script)
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_root_certificates() -> Dict[str, Any]:
    try:
        out = _run_ps('Get-ChildItem -Path Cert:\\CurrentUser\\Root | Select-Object Subject,Issuer,Thumbprint,NotBefore,NotAfter | ConvertTo-Json -Depth 3')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_personal_certificates() -> Dict[str, Any]:
    try:
        out = _run_ps('Get-ChildItem -Path Cert:\\CurrentUser\\My | Select-Object Subject,Issuer,Thumbprint,NotBefore,NotAfter,HasPrivateKey | ConvertTo-Json -Depth 3')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_certificate_by_thumbprint(thumbprint: str, store: str = "My", location: str = "CurrentUser") -> Dict[str, Any]:
    try:
        script = 'Get-ChildItem -Path Cert:\\' + location + '\\' + store + ' | Where-Object {$_.Thumbprint -eq "' + thumbprint + '"} | Select-Object Subject,Issuer,Thumbprint,NotBefore,NotAfter,HasPrivateKey,SerialNumber | ConvertTo-Json -Depth 3'
        out = _run_ps(script)
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_certificate_by_subject(subject_keyword: str, location: str = "CurrentUser") -> Dict[str, Any]:
    try:
        script = 'Get-ChildItem -Path Cert:\\' + location + '\\* -Recurse | Where-Object {$_.Subject -like "*' + subject_keyword + '*"} | Select-Object Subject,Issuer,Thumbprint,NotBefore,NotAfter,PSParentPath | ConvertTo-Json -Depth 3'
        out = _run_ps(script)
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_expired_certificates(location: str = "CurrentUser") -> Dict[str, Any]:
    try:
        script = 'Get-ChildItem -Path Cert:\\' + location + '\\* -Recurse | Where-Object {$_.NotAfter -lt (Get-Date)} | Select-Object Subject,Thumbprint,NotAfter,PSParentPath | ConvertTo-Json -Depth 3'
        out = _run_ps(script)
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_expiring_soon_certificates(days: int = 30, location: str = "CurrentUser") -> Dict[str, Any]:
    try:
        script = '$cutoff = (Get-Date).AddDays(' + str(days) + '); Get-ChildItem -Path Cert:\\' + location + '\\* -Recurse | Where-Object {$_.NotAfter -gt (Get-Date) -and $_.NotAfter -lt $cutoff} | Select-Object Subject,Thumbprint,NotAfter,PSParentPath | ConvertTo-Json -Depth 3'
        out = _run_ps(script)
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def count_certificates(store: str = "My", location: str = "CurrentUser") -> Dict[str, Any]:
    try:
        script = '(Get-ChildItem -Path Cert:\\' + location + '\\' + store + ').Count'
        out = _run_ps(script)
        count = int(out.strip()) if out.strip().isdigit() else 0
        return {"success": True, "data": count, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def export_certificate(thumbprint: str, output_path: str, store: str = "My", location: str = "CurrentUser") -> Dict[str, Any]:
    try:
        script = '$cert = Get-ChildItem -Path Cert:\\' + location + '\\' + store + ' | Where-Object {$_.Thumbprint -eq "' + thumbprint + '"}; Export-Certificate -Cert $cert -FilePath "' + output_path + '" -Type CERT'
        out = _run_ps(script)
        exists = os.path.isfile(output_path)
        return {"success": exists, "data": {"path": output_path, "exported": exists}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def remove_certificate(thumbprint: str, store: str = "My", location: str = "CurrentUser") -> Dict[str, Any]:
    try:
        script = 'Get-ChildItem -Path Cert:\\' + location + '\\' + store + ' | Where-Object {$_.Thumbprint -eq "' + thumbprint + '"} | Remove-Item'
        _run_ps(script)
        return {"success": True, "data": "Certificate removed: " + thumbprint, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_certificate_stores(location: str = "CurrentUser") -> Dict[str, Any]:
    try:
        script = 'Get-ChildItem -Path Cert:\\' + location + ' | Select-Object Name,PSPath | ConvertTo-Json -Depth 2'
        out = _run_ps(script)
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def verify_certificate(thumbprint: str, store: str = "My", location: str = "CurrentUser") -> Dict[str, Any]:
    try:
        script = '$cert = Get-ChildItem -Path Cert:\\' + location + '\\' + store + ' | Where-Object {$_.Thumbprint -eq "' + thumbprint + '"}; $cert.Verify()'
        out = _run_ps(script)
        valid = out.strip().lower() in ("true", "1")
        return {"success": True, "data": {"valid": valid, "thumbprint": thumbprint}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_certificate_details(thumbprint: str, store: str = "My", location: str = "CurrentUser") -> Dict[str, Any]:
    try:
        script = '$cert = Get-ChildItem -Path Cert:\\' + location + '\\' + store + ' | Where-Object {$_.Thumbprint -eq "' + thumbprint + '"}; $cert | Select-Object * | ConvertTo-Json -Depth 3'
        out = _run_ps(script)
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_certificates_with_private_key(location: str = "CurrentUser") -> Dict[str, Any]:
    try:
        script = 'Get-ChildItem -Path Cert:\\' + location + '\\My | Where-Object {$_.HasPrivateKey} | Select-Object Subject,Thumbprint,NotBefore,NotAfter | ConvertTo-Json -Depth 3'
        out = _run_ps(script)
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_local_machine_certificates(store: str = "My") -> Dict[str, Any]:
    try:
        out = _run_ps('Get-ChildItem -Path Cert:\\LocalMachine\\' + store + ' | Select-Object Subject,Issuer,Thumbprint,NotBefore,NotAfter | ConvertTo-Json -Depth 3')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
