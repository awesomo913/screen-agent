"""
installed_apps.py - Screen Agent Toolkit Module

Query, search, and manage installed applications on Windows.
Uses registry, WMI, PowerShell, and winget. No external deps.
"""
from __future__ import annotations
import json, os, re, subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

_UNINSTALL_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
] if HAS_WINREG else []

_APP_FIELDS = ["DisplayName","DisplayVersion","Publisher","InstallDate",
               "InstallLocation","UninstallString","EstimatedSize","URLInfoAbout"]

def _read_uninstall_key(root, key_path: str) -> List[Dict]:
    apps = []
    try:
        key = winreg.OpenKey(root, key_path)
        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(key, i); i += 1
                try:
                    subkey = winreg.OpenKey(key, subkey_name)
                    app: Dict[str, Any] = {"key": subkey_name}
                    for field in _APP_FIELDS:
                        try:
                            val, _ = winreg.QueryValueEx(subkey, field)
                            app[field] = val
                        except OSError:
                            app[field] = None
                    winreg.CloseKey(subkey)
                    if app.get("DisplayName"):
                        apps.append(app)
                except OSError:
                    pass
            except OSError:
                break
        winreg.CloseKey(key)
    except OSError:
        pass
    return apps

def list_installed_apps(include_system: bool = False) -> Dict[str, Any]:
    """List all installed applications from the Windows registry."""
    if not HAS_WINREG:
        return {"success": False, "data": None, "error": "winreg not available"}
    try:
        seen = set(); apps = []
        for root, key_path in _UNINSTALL_KEYS:
            for app in _read_uninstall_key(root, key_path):
                name = app.get("DisplayName","")
                if name and name not in seen:
                    seen.add(name)
                    if not include_system:
                        if not app.get("UninstallString") or not app.get("DisplayVersion"):
                            continue
                    size_kb = app.get("EstimatedSize")
                    apps.append({"name": name,
                                  "version": app.get("DisplayVersion"),
                                  "publisher": app.get("Publisher"),
                                  "install_date": app.get("InstallDate"),
                                  "install_location": app.get("InstallLocation"),
                                  "uninstall_string": app.get("UninstallString"),
                                  "size_mb": round(size_kb/1024,1) if size_kb else None,
                                  "url": app.get("URLInfoAbout")})
        apps.sort(key=lambda x: (x["name"] or "").lower())
        return {"success": True, "data": apps, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def search_apps(keyword: str) -> Dict[str, Any]:
    """Search installed apps by name or publisher (case-insensitive)."""
    try:
        r = list_installed_apps(include_system=True)
        if not r["success"]: return r
        needle = keyword.lower()
        matches = [a for a in r["data"] if needle in (a.get("name") or "").lower()
                   or needle in (a.get("publisher") or "").lower()]
        return {"success": True, "data": matches, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_app_details(app_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific installed app."""
    try:
        r = search_apps(app_name)
        if not r["success"]: return r
        if not r["data"]:
            return {"success": False, "data": None, "error": f"App not found: {app_name}"}
        # Return closest match
        exact = [a for a in r["data"] if (a.get("name") or "").lower() == app_name.lower()]
        return {"success": True, "data": exact[0] if exact else r["data"][0], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def count_installed_apps() -> Dict[str, Any]:
    """Count total installed applications."""
    try:
        r = list_installed_apps(include_system=True)
        if not r["success"]: return r
        by_publisher: Dict[str,int] = {}
        for a in r["data"]:
            pub = a.get("publisher") or "Unknown"
            by_publisher[pub] = by_publisher.get(pub,0) + 1
        top_pubs = sorted(by_publisher.items(), key=lambda x: -x[1])[:10]
        return {"success": True, "data": {"total":len(r["data"]),"top_publishers":dict(top_pubs)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_recently_installed_apps(days: int = 30) -> Dict[str, Any]:
    """Find apps installed within the last N days."""
    try:
        r = list_installed_apps(include_system=True)
        if not r["success"]: return r
        cutoff = datetime.now()
        recent = []
        for a in r["data"]:
            idate = a.get("install_date")
            if idate and len(idate) == 8:
                try:
                    d = datetime.strptime(idate, "%Y%m%d")
                    delta = (cutoff - d).days
                    if delta <= days:
                        a["days_ago"] = delta; recent.append(a)
                except ValueError: pass
        recent.sort(key=lambda x: x.get("install_date",""), reverse=True)
        return {"success": True, "data": recent, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_largest_apps(top_n: int = 20) -> Dict[str, Any]:
    """Find the N largest installed applications by estimated size."""
    try:
        r = list_installed_apps(include_system=True)
        if not r["success"]: return r
        sized = [a for a in r["data"] if a.get("size_mb")]
        sized.sort(key=lambda x: x["size_mb"], reverse=True)
        return {"success": True, "data": sized[:top_n], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def uninstall_app(app_name: str, silent: bool = True) -> Dict[str, Any]:
    """Uninstall an application using its registered uninstall string."""
    try:
        r = get_app_details(app_name)
        if not r["success"]: return r
        app = r["data"]
        uninstall_str = app.get("uninstall_string")
        if not uninstall_str:
            return {"success": False, "data": None, "error": "No uninstall string found"}
        if silent:
            uninstall_str = uninstall_str.replace("/I", "/X").replace("/x", "/X")
            if "msiexec" in uninstall_str.lower() and "/quiet" not in uninstall_str.lower():
                uninstall_str += " /quiet /norestart"
        proc = subprocess.run(uninstall_str, shell=True, capture_output=True, text=True, timeout=120)
        return {"success": proc.returncode == 0, "data": {"app":app_name,"return_code":proc.returncode,
                "output":proc.stdout[:500]}, "error": proc.stderr[:200] if proc.returncode else None}
    except subprocess.TimeoutExpired:
        return {"success": False, "data": None, "error": "Uninstall timed out"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_apps_by_publisher(publisher: str) -> Dict[str, Any]:
    """List all apps from a specific publisher."""
    try:
        r = list_installed_apps(include_system=True)
        if not r["success"]: return r
        needle = publisher.lower()
        matches = [a for a in r["data"] if needle in (a.get("publisher") or "").lower()]
        return {"success": True, "data": matches, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_microsoft_apps() -> Dict[str, Any]:
    """List all Microsoft-published apps."""
    return get_apps_by_publisher("Microsoft")

def list_store_apps() -> Dict[str, Any]:
    """List Windows Store (UWP) apps via PowerShell Get-AppxPackage."""
    try:
        ps = """
Get-AppxPackage | Select-Object Name, PackageFullName, Version, Publisher, InstallLocation |
ConvertTo-Json -Depth 2
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            if isinstance(data, dict): data = [data]
            return {"success": True, "data": data, "error": None}
        return {"success": True, "data": [], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def winget_list() -> Dict[str, Any]:
    """List installed apps via winget (Windows Package Manager)."""
    try:
        r = subprocess.run(["winget","list","--accept-source-agreements"],
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return {"success": False, "data": None, "error": "winget not available or failed"}
        lines = r.stdout.splitlines(); apps = []
        header_idx = next((i for i,l in enumerate(lines) if "Name" in l and "Id" in l), None)
        if header_idx is not None:
            for line in lines[header_idx+2:]:
                if line.strip(): apps.append(line.strip())
        return {"success": True, "data": apps, "error": None}
    except FileNotFoundError:
        return {"success": False, "data": None, "error": "winget not found"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def winget_search(query: str) -> Dict[str, Any]:
    """Search for an app in winget repository."""
    try:
        r = subprocess.run(["winget","search","--query",query,"--accept-source-agreements"],
                           capture_output=True, text=True, timeout=30)
        return {"success": r.returncode==0, "data": {"output":r.stdout[:2000]}, "error": r.stderr[:200] or None}
    except FileNotFoundError:
        return {"success": False, "data": None, "error": "winget not found"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def winget_install(package_id: str, silent: bool = True) -> Dict[str, Any]:
    """Install an app via winget by package ID."""
    try:
        cmd = ["winget","install","--id",package_id,"--accept-package-agreements","--accept-source-agreements"]
        if silent: cmd += ["--silent"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return {"success": r.returncode==0, "data": {"package_id":package_id,"output":r.stdout[:500]},
                "error": r.stderr[:200] if r.returncode else None}
    except FileNotFoundError:
        return {"success": False, "data": None, "error": "winget not found"}
    except subprocess.TimeoutExpired:
        return {"success": False, "data": None, "error": "Install timed out"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def winget_upgrade_all() -> Dict[str, Any]:
    """Upgrade all apps via winget."""
    try:
        r = subprocess.run(["winget","upgrade","--all","--accept-package-agreements",
                            "--accept-source-agreements","--silent"],
                           capture_output=True, text=True, timeout=600)
        return {"success": r.returncode==0, "data": {"output":r.stdout[:1000]}, "error": r.stderr[:200] or None}
    except FileNotFoundError:
        return {"success": False, "data": None, "error": "winget not found"}
    except subprocess.TimeoutExpired:
        return {"success": False, "data": None, "error": "Upgrade timed out"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def export_app_list(output_path: str, format: str = "json") -> Dict[str, Any]:
    """Export list of installed apps to JSON or CSV."""
    try:
        r = list_installed_apps(include_system=True)
        if not r["success"]: return r
        out = Path(output_path); out.parent.mkdir(parents=True, exist_ok=True)
        if format.lower() == "json":
            out.write_text(json.dumps(r["data"], indent=2), encoding="utf-8")
        elif format.lower() == "csv":
            import csv
            with open(out,"w",newline="",encoding="utf-8") as f:
                if r["data"]:
                    w = csv.DictWriter(f, fieldnames=list(r["data"][0].keys()))
                    w.writeheader(); w.writerows(r["data"])
        else:
            return {"success": False, "data": None, "error": f"Unknown format: {format}"}
        return {"success": True, "data": {"path":str(out),"count":len(r["data"])}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def is_app_installed(app_name: str) -> Dict[str, Any]:
    """Check if a specific application is installed."""
    try:
        r = search_apps(app_name)
        if not r["success"]: return r
        installed = len(r["data"]) > 0
        return {"success": True, "data": {"installed":installed,
                "app_name":app_name,"matches":len(r["data"])}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
