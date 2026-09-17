"""
hosts_file_manager.py - Screen Agent Toolkit Module

Read, add, remove, and manage the Windows hosts file (/etc/hosts).
Block domains, create aliases, backup/restore. Stdlib only.
"""
from __future__ import annotations
import json, os, re, shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_HOSTS_PATH = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
_HOSTS_BACKUP_DIR = Path(os.environ.get("TEMP", os.getcwd())) / "hosts_backups"

def _parse_hosts_file(content: str) -> List[Dict]:
    entries = []
    for i, line in enumerate(content.splitlines(), 1):
        original = line
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            entries.append({"line":i,"type":"comment" if stripped.startswith("#") else "blank",
                             "raw":original,"ip":None,"hostname":None,"active":False})
            continue
        parts = stripped.split()
        if len(parts) >= 2:
            entries.append({"line":i,"type":"entry","raw":original,"ip":parts[0],
                             "hostname":parts[1],"aliases":parts[2:] if len(parts)>2 else [],
                             "active":True})
        else:
            entries.append({"line":i,"type":"unknown","raw":original,"ip":None,"hostname":None,"active":False})
    return entries

def read_hosts_file() -> Dict[str, Any]:
    """Read and parse the Windows hosts file."""
    try:
        content = _HOSTS_PATH.read_text(encoding="utf-8", errors="replace")
        entries = _parse_hosts_file(content)
        active = [e for e in entries if e["type"]=="entry"]
        return {"success": True, "data": {"path":str(_HOSTS_PATH),"entries":entries,
                "active_count":len(active),"total_lines":len(entries)}, "error": None}
    except PermissionError:
        return {"success": False, "data": None, "error": "Permission denied reading hosts file"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_host_entries() -> Dict[str, Any]:
    """List all active (non-comment) host entries."""
    try:
        r = read_hosts_file()
        if not r["success"]: return r
        active = [e for e in r["data"]["entries"] if e["type"]=="entry"]
        return {"success": True, "data": active, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def add_host_entry(ip: str, hostname: str, comment: str = "") -> Dict[str, Any]:
    """Add a new entry to the hosts file."""
    try:
        # Validate IP roughly
        if not re.match(r"^[\d.:a-fA-F]+$", ip):
            return {"success": False, "data": None, "error": f"Invalid IP address: {ip}"}
        content = _HOSTS_PATH.read_text(encoding="utf-8", errors="replace")
        # Check if already exists
        for line in content.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1].lower() == hostname.lower():
                return {"success": False, "data": None, "error": f"Hostname {hostname} already exists"}
        line = f"{ip}\t{hostname}"
        if comment: line += f"\t# {comment}"
        if not content.endswith("\n"): content += "\n"
        content += line + "\n"
        _HOSTS_PATH.write_text(content, encoding="utf-8")
        return {"success": True, "data": {"ip":ip,"hostname":hostname}, "error": None}
    except PermissionError:
        return {"success": False, "data": None, "error": "Permission denied - run as admin"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def remove_host_entry(hostname: str) -> Dict[str, Any]:
    """Remove a host entry by hostname."""
    try:
        content = _HOSTS_PATH.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines(keepends=True); removed = []; kept = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 2 and not parts[0].startswith("#") and parts[1].lower() == hostname.lower():
                removed.append(line.strip())
            else:
                kept.append(line)
        if not removed:
            return {"success": False, "data": None, "error": f"Hostname not found: {hostname}"}
        _HOSTS_PATH.write_text("".join(kept), encoding="utf-8")
        return {"success": True, "data": {"removed":removed}, "error": None}
    except PermissionError:
        return {"success": False, "data": None, "error": "Permission denied - run as admin"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def block_domain(domain: str) -> Dict[str, Any]:
    """Block a domain by pointing it to 0.0.0.0 in hosts file."""
    try:
        r = add_host_entry("0.0.0.0", domain, comment="blocked by screen-agent")
        if not r["success"] and "already exists" in (r.get("error") or ""):
            return {"success": True, "data": {"blocked":domain,"note":"already blocked"}, "error": None}
        return r
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def unblock_domain(domain: str) -> Dict[str, Any]:
    """Remove a domain block from hosts file."""
    return remove_host_entry(domain)

def block_multiple_domains(domains: List[str]) -> Dict[str, Any]:
    """Block multiple domains at once."""
    try:
        results = {"blocked":[],"failed":[]}
        for d in domains:
            r = block_domain(d)
            if r["success"]: results["blocked"].append(d)
            else: results["failed"].append({"domain":d,"error":r.get("error")})
        return {"success": True, "data": results, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def disable_host_entry(hostname: str) -> Dict[str, Any]:
    """Comment out a host entry without deleting it."""
    try:
        content = _HOSTS_PATH.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines(keepends=True); disabled = []; new_lines = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 2 and not line.strip().startswith("#") and parts[1].lower() == hostname.lower():
                new_lines.append("# " + line); disabled.append(hostname)
            else:
                new_lines.append(line)
        if not disabled:
            return {"success": False, "data": None, "error": f"Entry not found: {hostname}"}
        _HOSTS_PATH.write_text("".join(new_lines), encoding="utf-8")
        return {"success": True, "data": {"disabled":hostname}, "error": None}
    except PermissionError:
        return {"success": False, "data": None, "error": "Permission denied - run as admin"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def enable_host_entry(hostname: str) -> Dict[str, Any]:
    """Re-enable a commented-out host entry."""
    try:
        content = _HOSTS_PATH.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines(keepends=True); enabled = []; new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                uncommented = stripped.lstrip("#").strip()
                parts = uncommented.split()
                if len(parts) >= 2 and parts[1].lower() == hostname.lower():
                    new_lines.append(uncommented + "\n"); enabled.append(hostname); continue
            new_lines.append(line)
        if not enabled:
            return {"success": False, "data": None, "error": f"Disabled entry not found: {hostname}"}
        _HOSTS_PATH.write_text("".join(new_lines), encoding="utf-8")
        return {"success": True, "data": {"enabled":hostname}, "error": None}
    except PermissionError:
        return {"success": False, "data": None, "error": "Permission denied - run as admin"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def backup_hosts_file(backup_path: Optional[str] = None) -> Dict[str, Any]:
    """Create a timestamped backup of the hosts file."""
    try:
        if backup_path is None:
            _HOSTS_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = str(_HOSTS_BACKUP_DIR / f"hosts_{ts}.bak")
        shutil.copy2(_HOSTS_PATH, backup_path)
        size = Path(backup_path).stat().st_size
        return {"success": True, "data": {"backup_path":backup_path,"size_bytes":size}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def restore_hosts_file(backup_path: str) -> Dict[str, Any]:
    """Restore the hosts file from a backup."""
    try:
        src = Path(backup_path)
        if not src.exists():
            return {"success": False, "data": None, "error": f"Backup not found: {backup_path}"}
        # Create safety backup first
        backup_hosts_file()
        shutil.copy2(src, _HOSTS_PATH)
        return {"success": True, "data": {"restored_from":backup_path}, "error": None}
    except PermissionError:
        return {"success": False, "data": None, "error": "Permission denied - run as admin"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_backups() -> Dict[str, Any]:
    """List available hosts file backups."""
    try:
        if not _HOSTS_BACKUP_DIR.is_dir():
            return {"success": True, "data": [], "error": None}
        backups = []
        for f in _HOSTS_BACKUP_DIR.glob("hosts_*.bak"):
            backups.append({"path":str(f),"name":f.name,
                             "size_bytes":f.stat().st_size,
                             "created":datetime.fromtimestamp(f.stat().st_mtime).isoformat()})
        backups.sort(key=lambda x: x["created"], reverse=True)
        return {"success": True, "data": backups, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def reset_hosts_file() -> Dict[str, Any]:
    """Reset hosts file to Windows default content (backup first)."""
    try:
        backup_hosts_file()
        default_content = """# Copyright (c) 1993-2009 Microsoft Corp.
#
# This is a sample HOSTS file used by Microsoft TCP/IP for Windows.
# This file contains the mappings of IP addresses to host names.
# Each entry should be kept on an individual line. The IP address should
# be placed in the first column followed by the corresponding host name.
# The IP address and the host name should be separated by at least one space.
#
# Additionally, comments (such as these) may be inserted on individual
# lines or following the machine name denoted by a '#' symbol.
#
# For example:
#      102.54.94.97     rhino.acme.com          # source server
#       38.25.63.10     x.acme.com              # x client host

# localhost name resolution is handled within DNS itself.
# 127.0.0.1       localhost
# ::1             localhost
"""
        _HOSTS_PATH.write_text(default_content, encoding="utf-8")
        return {"success": True, "data": {"reset":True,"path":str(_HOSTS_PATH)}, "error": None}
    except PermissionError:
        return {"success": False, "data": None, "error": "Permission denied - run as admin"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_host_entry(hostname: str) -> Dict[str, Any]:
    """Search for a hostname in the hosts file."""
    try:
        r = read_hosts_file()
        if not r["success"]: return r
        needle = hostname.lower()
        matches = [e for e in r["data"]["entries"]
                   if e.get("hostname","") and needle in e["hostname"].lower()]
        return {"success": True, "data": {"found":bool(matches),"matches":matches}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_hosts_file_stats() -> Dict[str, Any]:
    """Get statistics about the hosts file."""
    try:
        r = read_hosts_file()
        if not r["success"]: return r
        entries = r["data"]["entries"]
        active = [e for e in entries if e["type"]=="entry"]
        blocked = [e for e in active if e.get("ip") in ("0.0.0.0","127.0.0.1")]
        comments = [e for e in entries if e["type"]=="comment"]
        ips = list({e["ip"] for e in active if e.get("ip")})
        return {"success": True, "data": {
            "total_lines":len(entries), "active_entries":len(active),
            "blocked_domains":len(blocked), "comment_lines":len(comments),
            "unique_ips":len(ips), "file_size_bytes":_HOSTS_PATH.stat().st_size,
            "file_path":str(_HOSTS_PATH)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
