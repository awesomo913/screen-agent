"""
font_inspector.py - Screen Agent Toolkit Module

Inspect, enumerate, and query fonts installed on the Windows system.
Uses winreg and stdlib only. No external dependencies required.
"""
from __future__ import annotations
import json, os, re, subprocess, sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

_FONT_REG_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
_FONT_DIRS = [
    Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts",
]

def _get_reg_entries() -> Dict[str, str]:
    if not HAS_WINREG:
        return {}
    out: Dict[str, str] = {}
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(root, _FONT_REG_KEY)
            i = 0
            while True:
                try:
                    n, v, _ = winreg.EnumValue(key, i); out[n] = v; i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except Exception:
            pass
    return out

def _resolve(filename: str) -> Optional[Path]:
    if os.path.isabs(filename) and Path(filename).exists():
        return Path(filename)
    for d in _FONT_DIRS:
        p = d / filename
        if p.exists():
            return p
    return None

def _parse(display: str) -> Dict[str, str]:
    m = re.match(r"^(.*?)\s*(\(([^)]+)\))?\s*$", display)
    full = m.group(1).strip() if m else display
    ftype = m.group(3) if m and m.group(3) else "Unknown"
    STYLES = {"Bold","Italic","Light","Thin","Regular","Medium","Black","Heavy",
               "Condensed","Narrow","SemiBold","ExtraBold","ExtraLight","Oblique"}
    words = full.split()
    idx = len(words)
    for i in range(len(words)-1, -1, -1):
        if words[i] in STYLES: idx = i
        else: break
    family = " ".join(words[:idx]) or full
    style = " ".join(words[idx:]) or "Regular"
    return {"family": family, "style": style, "font_type": ftype, "display_name": full}

def list_fonts(include_path: bool = False) -> Dict[str, Any]:
    """List all installed fonts with family/style metadata."""
    try:
        entries = _get_reg_entries()
        fonts = []
        for dn, fn in entries.items():
            info = _parse(dn); info["filename"] = fn
            if include_path:
                p = _resolve(fn); info["path"] = str(p) if p else None
            fonts.append(info)
        fonts.sort(key=lambda f: f["family"].lower())
        return {"success": True, "data": fonts, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def is_font_installed(font_name: str) -> Dict[str, Any]:
    """Check if a font is installed (case-insensitive partial match)."""
    try:
        entries = _get_reg_entries()
        needle = font_name.lower()
        matches = [k for k in entries if needle in k.lower()]
        return {"success": True, "data": {"installed": bool(matches), "matches": matches}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_font_path(font_name: str) -> Dict[str, Any]:
    """Get file path(s) of an installed font by partial display name."""
    try:
        entries = _get_reg_entries(); needle = font_name.lower(); results = []
        for dn, fn in entries.items():
            if needle in dn.lower():
                p = _resolve(fn)
                results.append({"display_name": dn, "filename": fn,
                                 "path": str(p) if p else None, "exists": p is not None})
        return {"success": True, "data": results, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def search_fonts(keyword: str) -> Dict[str, Any]:
    """Search fonts by keyword matching family or style."""
    try:
        r = list_fonts()
        if not r["success"]: return r
        kl = keyword.lower()
        return {"success": True, "data": [f for f in r["data"] if kl in f["family"].lower()
                or kl in f["style"].lower() or kl in f["display_name"].lower()], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def count_fonts() -> Dict[str, Any]:
    """Count total installed fonts and unique families."""
    try:
        entries = _get_reg_entries()
        families = {_parse(k)["family"] for k in entries}
        return {"success": True, "data": {"total": len(entries), "families": len(families)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_font_families() -> Dict[str, Any]:
    """List unique font family names only."""
    try:
        entries = _get_reg_entries()
        families = sorted({_parse(k)["family"] for k in entries})
        return {"success": True, "data": families, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_family_variants(family_name: str) -> Dict[str, Any]:
    """Get all installed variants of a font family."""
    try:
        entries = _get_reg_entries(); needle = family_name.lower(); variants = []
        for dn, fn in entries.items():
            info = _parse(dn)
            if needle in info["family"].lower():
                info["filename"] = fn; p = _resolve(fn); info["path"] = str(p) if p else None
                variants.append(info)
        return {"success": True, "data": variants, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_fonts_by_type(font_type: str = "TrueType") -> Dict[str, Any]:
    """Filter fonts by type: TrueType, OpenType, etc."""
    try:
        r = list_fonts()
        if not r["success"]: return r
        needle = font_type.lower()
        return {"success": True, "data": [f for f in r["data"] if needle in f["font_type"].lower()], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_recently_installed_fonts(days: int = 30) -> Dict[str, Any]:
    """Find fonts installed within the last N days."""
    try:
        entries = _get_reg_entries(); cutoff = datetime.now().timestamp() - days * 86400; recent = []
        for dn, fn in entries.items():
            p = _resolve(fn)
            if p and p.exists() and p.stat().st_mtime >= cutoff:
                recent.append({"display_name": dn, "path": str(p),
                                "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat()})
        recent.sort(key=lambda x: x["modified"], reverse=True)
        return {"success": True, "data": recent, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_missing_fonts(font_names: List[str]) -> Dict[str, Any]:
    """Check which fonts from a list are NOT installed."""
    try:
        entries = _get_reg_entries(); all_lower = [k.lower() for k in entries]
        missing = [n for n in font_names if not any(n.lower() in k for k in all_lower)]
        found = [n for n in font_names if any(n.lower() in k for k in all_lower)]
        return {"success": True, "data": {"missing": missing, "found": found}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def export_font_list(output_path: str, format: str = "json") -> Dict[str, Any]:
    """Export installed font list to JSON or CSV file."""
    try:
        r = list_fonts(include_path=True)
        if not r["success"]: return r
        fonts = r["data"]; out = Path(output_path); out.parent.mkdir(parents=True, exist_ok=True)
        if format.lower() == "json":
            out.write_text(json.dumps(fonts, indent=2), encoding="utf-8")
        elif format.lower() == "csv":
            import csv
            with open(out, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["family","style","font_type","display_name","filename","path"])
                w.writeheader(); w.writerows(fonts)
        else:
            return {"success": False, "data": None, "error": f"Unknown format: {format}"}
        return {"success": True, "data": {"path": str(out), "count": len(fonts)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_monospace_fonts() -> Dict[str, Any]:
    """Return fonts likely to be monospace/fixed-width based on name."""
    try:
        MONO = {"mono","courier","console","fixed","code","terminal","typewriter"}
        r = list_fonts()
        if not r["success"]: return r
        return {"success": True, "data": [f for f in r["data"]
                if any(k in f["family"].lower() for k in MONO)], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_system_ui_fonts() -> Dict[str, Any]:
    """Get Windows system UI fonts (Caption, Icon, Menu, Message, etc.)."""
    if not HAS_WINREG:
        return {"success": False, "data": None, "error": "winreg not available"}
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop\WindowMetrics")
        result = {}
        for fk in ["CaptionFont","IconFont","MenuFont","MessageFont","SmCaptionFont","StatusFont"]:
            try:
                val, _ = winreg.QueryValueEx(key, fk)
                result[fk] = val[28:92].decode("utf-16-le").rstrip("\x00") if isinstance(val, bytes) and len(val) >= 92 else None
            except OSError:
                result[fk] = None
        winreg.CloseKey(key)
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_fonts_in_directory(directory: str) -> Dict[str, Any]:
    """List font files in a directory (installed or not)."""
    try:
        d = Path(directory)
        if not d.is_dir():
            return {"success": False, "data": None, "error": f"Not a directory: {directory}"}
        exts = {".ttf",".otf",".fon",".ttc",".pfb",".pfm"}
        files = [{"name": f.name, "path": str(f), "size_kb": round(f.stat().st_size/1024,1),
                  "extension": f.suffix.lower()} for f in d.iterdir() if f.suffix.lower() in exts]
        files.sort(key=lambda x: x["name"].lower())
        return {"success": True, "data": files, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def group_fonts_by_family() -> Dict[str, Any]:
    """Return all fonts grouped by family name."""
    try:
        r = list_fonts()
        if not r["success"]: return r
        grouped: Dict[str, List] = {}
        for f in r["data"]:
            grouped.setdefault(f["family"], []).append(f)
        return {"success": True, "data": grouped, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_largest_font_files(top_n: int = 10) -> Dict[str, Any]:
    """Return the N largest font files by size."""
    try:
        entries = _get_reg_entries(); sized = []
        for dn, fn in entries.items():
            p = _resolve(fn)
            if p and p.exists():
                sized.append({"display_name": dn, "path": str(p), "size_kb": round(p.stat().st_size/1024,1)})
        sized.sort(key=lambda x: x["size_kb"], reverse=True)
        return {"success": True, "data": sized[:top_n], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def install_font(font_path: str, all_users: bool = False) -> Dict[str, Any]:
    """Install a font file. all_users=True requires admin rights."""
    try:
        src = Path(font_path)
        if not src.exists():
            return {"success": False, "data": None, "error": f"File not found: {font_path}"}
        if src.suffix.lower() not in {".ttf",".otf",".fon",".ttc"}:
            return {"success": False, "data": None, "error": "Unsupported font format"}
        if all_users:
            dest_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        else:
            dest_dir = Path(os.environ.get("LOCALAPPDATA","")) / "Microsoft" / "Windows" / "Fonts"
            dest_dir.mkdir(parents=True, exist_ok=True)
        import shutil; dest = dest_dir / src.name; shutil.copy2(src, dest)
        if HAS_WINREG:
            root = winreg.HKEY_LOCAL_MACHINE if all_users else winreg.HKEY_CURRENT_USER
            key = winreg.OpenKey(root, _FONT_REG_KEY, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, src.stem + " (TrueType)", 0, winreg.REG_SZ,
                              src.name if all_users else str(dest))
            winreg.CloseKey(key)
        return {"success": True, "data": {"installed_to": str(dest)}, "error": None}
    except PermissionError:
        return {"success": False, "data": None, "error": "Permission denied - run as admin"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_font_statistics() -> Dict[str, Any]:
    """Return summary statistics about installed fonts."""
    try:
        entries = _get_reg_entries()
        by_type: Dict[str, int] = {}
        total_size = 0; found_files = 0
        for dn, fn in entries.items():
            info = _parse(dn); t = info["font_type"]
            by_type[t] = by_type.get(t, 0) + 1
            p = _resolve(fn)
            if p and p.exists():
                found_files += 1; total_size += p.stat().st_size
        families = {_parse(k)["family"] for k in entries}
        return {"success": True, "data": {
            "total_fonts": len(entries), "unique_families": len(families),
            "by_type": by_type, "files_found": found_files,
            "total_size_mb": round(total_size/1024/1024, 2)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
