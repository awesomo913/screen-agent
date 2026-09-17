"""
disk_health.py - Screen Agent Toolkit Module

Monitor disk health, SMART status, partition info, volume details,
disk I/O stats, and storage inventory. Uses wmic, PowerShell, psutil.
"""
from __future__ import annotations
import json, os, re, subprocess, time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

def get_disk_partitions() -> Dict[str, Any]:
    """List all disk partitions with filesystem, size, and usage."""
    try:
        if HAS_PSUTIL:
            parts = []
            for p in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    parts.append({"device":p.device,"mountpoint":p.mountpoint,"fstype":p.fstype,
                                   "opts":p.opts,"total_gb":round(usage.total/1e9,2),
                                   "used_gb":round(usage.used/1e9,2),"free_gb":round(usage.free/1e9,2),
                                   "percent":usage.percent})
                except PermissionError:
                    parts.append({"device":p.device,"mountpoint":p.mountpoint,"fstype":p.fstype,"error":"access denied"})
            return {"success": True, "data": parts, "error": None}
        r = subprocess.run(["wmic","logicaldisk","get",
                             "DeviceID,FileSystem,FreeSpace,Size,VolumeName","/format:csv"],
                           capture_output=True, text=True, timeout=15)
        lines = [l for l in r.stdout.splitlines() if l.strip() and "Node" not in l]
        parts = []
        for line in lines:
            cols = line.split(",")
            if len(cols) >= 5:
                try:
                    total = int(cols[4]) if cols[4].strip() else 0
                    free = int(cols[3]) if cols[3].strip() else 0
                    parts.append({"device":cols[1].strip(),"fstype":cols[2].strip(),
                                   "free_gb":round(free/1e9,2),"total_gb":round(total/1e9,2),
                                   "volume_name":cols[5].strip() if len(cols)>5 else ""})
                except (ValueError, IndexError): pass
        return {"success": True, "data": parts, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_disk_io_stats() -> Dict[str, Any]:
    """Get disk I/O counters (reads, writes, bytes, latency)."""
    try:
        if not HAS_PSUTIL:
            return {"success": False, "data": None, "error": "psutil not available"}
        io = psutil.disk_io_counters(perdisk=True)
        return {"success": True, "data": {
            disk: {"read_count":s.read_count,"write_count":s.write_count,
                   "read_bytes":s.read_bytes,"write_bytes":s.write_bytes,
                   "read_mb":round(s.read_bytes/1e6,2),"write_mb":round(s.write_bytes/1e6,2),
                   "read_time_ms":s.read_time,"write_time_ms":s.write_time}
            for disk, s in io.items()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_physical_disks() -> Dict[str, Any]:
    """Get physical disk inventory (model, size, interface, media type)."""
    try:
        ps = """
Get-PhysicalDisk | Select-Object FriendlyName,SerialNumber,MediaType,BusType,Size,HealthStatus,OperationalStatus |
ConvertTo-Json -Depth 2
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            if isinstance(data, dict): data = [data]
            for d in data:
                if "Size" in d and d["Size"]: d["size_gb"] = round(d["Size"]/1e9, 2)
            return {"success": True, "data": data, "error": None}
        return {"success": True, "data": [], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_smart_status() -> Dict[str, Any]:
    """Get SMART health status for all physical disks."""
    try:
        ps = """
Get-PhysicalDisk | Select-Object FriendlyName,HealthStatus,OperationalStatus,Usage | ConvertTo-Json -Depth 2
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            if isinstance(data, dict): data = [data]
            return {"success": True, "data": data, "error": None}
        return {"success": False, "data": None, "error": "No SMART data available"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_volume_info(drive_letter: str) -> Dict[str, Any]:
    """Get detailed info for a specific volume (drive letter)."""
    try:
        letter = drive_letter.rstrip(":\\").upper()
        ps = f"""
$vol = Get-Volume -DriveLetter '{letter}' -ErrorAction SilentlyContinue
if ($vol) {{ $vol | Select-Object DriveLetter,FileSystemLabel,FileSystem,DriveType,
    HealthStatus,OperationalStatus,SizeRemaining,Size | ConvertTo-Json -Depth 2 }}
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            if "Size" in data: data["size_gb"] = round(data["Size"]/1e9, 2)
            if "SizeRemaining" in data: data["free_gb"] = round(data["SizeRemaining"]/1e9, 2)
            return {"success": True, "data": data, "error": None}
        return {"success": False, "data": None, "error": f"Volume {letter}: not found"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_storage_spaces() -> Dict[str, Any]:
    """List Windows Storage Spaces pools and virtual disks."""
    try:
        ps = "Get-StoragePool -IsPrimordial $false -ErrorAction SilentlyContinue | ConvertTo-Json -Depth 2"
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=15)
        data = []
        if r.returncode == 0 and r.stdout.strip():
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict): data = [data]
            except Exception: pass
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_disk_errors(drive_letter: str) -> Dict[str, Any]:
    """Run chkdsk in read-only mode to check for disk errors."""
    try:
        letter = drive_letter.rstrip(":\\").upper() + ":"
        r = subprocess.run(["chkdsk", letter], capture_output=True, text=True, timeout=120)
        output = r.stdout + r.stderr
        has_errors = any(w in output.lower() for w in ["error","corrupt","bad sector","problems"])
        return {"success": True, "data": {"drive":letter,"has_errors":has_errors,
                "output":output.strip(),"return_code":r.returncode}, "error": None}
    except subprocess.TimeoutExpired:
        return {"success": False, "data": None, "error": "chkdsk timed out"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def defrag_analysis(drive_letter: str) -> Dict[str, Any]:
    """Run defrag analysis on a drive (read-only, no defrag performed)."""
    try:
        letter = drive_letter.rstrip(":\\").upper() + ":"
        r = subprocess.run(["defrag", letter, "/A", "/U"], capture_output=True, text=True, timeout=120)
        output = r.stdout + r.stderr
        frag_match = re.search(r"(\d+)%\s+fragmented", output, re.I)
        frag_pct = int(frag_match.group(1)) if frag_match else None
        return {"success": True, "data": {"drive":letter,"fragmentation_percent":frag_pct,
                "output":output.strip()}, "error": None}
    except subprocess.TimeoutExpired:
        return {"success": False, "data": None, "error": "Defrag analysis timed out"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_disk_temperature() -> Dict[str, Any]:
    """Get disk temperature via WMI MSStorageDriver_ATAPISmartData (best effort)."""
    try:
        ps = """
$temp = Get-WmiObject -Namespace root\wmi -Class MSStorageDriver_ATAPISmartData -ErrorAction SilentlyContinue
if ($temp) { $temp | Select-Object InstanceName | ConvertTo-Json } else { '[]' }
"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, text=True, timeout=15)
        return {"success": True, "data": {"note":"Temperature via WMI","output":r.stdout.strip()[:500]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_largest_files(directory: str, top_n: int = 20,
                      recursive: bool = True) -> Dict[str, Any]:
    """Find the N largest files in a directory."""
    try:
        d = Path(directory)
        if not d.is_dir():
            return {"success": False, "data": None, "error": f"Not a directory: {directory}"}
        pattern = "**/*" if recursive else "*"
        files = []
        for f in d.glob(pattern):
            if f.is_file():
                try:
                    size = f.stat().st_size
                    files.append({"path":str(f),"size_mb":round(size/1e6,3),"size_bytes":size})
                except Exception: pass
        files.sort(key=lambda x: x["size_bytes"], reverse=True)
        return {"success": True, "data": files[:top_n], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_directory_size(directory: str) -> Dict[str, Any]:
    """Calculate total size of a directory recursively."""
    try:
        d = Path(directory)
        if not d.is_dir():
            return {"success": False, "data": None, "error": f"Not a directory: {directory}"}
        total = 0; file_count = 0; dir_count = 0
        for item in d.rglob("*"):
            if item.is_file():
                try: total += item.stat().st_size; file_count += 1
                except Exception: pass
            elif item.is_dir(): dir_count += 1
        return {"success": True, "data": {"path":directory,"total_bytes":total,
                "total_mb":round(total/1e6,2),"total_gb":round(total/1e9,4),
                "files":file_count,"directories":dir_count}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_duplicate_files(directory: str, min_size_kb: int = 10) -> Dict[str, Any]:
    """Find duplicate files by size+hash fingerprint in a directory."""
    try:
        import hashlib
        d = Path(directory); min_bytes = min_size_kb * 1024
        size_groups: Dict[int, List[Path]] = {}
        for f in d.rglob("*"):
            if f.is_file():
                try:
                    sz = f.stat().st_size
                    if sz >= min_bytes: size_groups.setdefault(sz, []).append(f)
                except Exception: pass
        duplicates = []
        for sz, flist in size_groups.items():
            if len(flist) < 2: continue
            hash_groups: Dict[str, List[str]] = {}
            for fp in flist:
                try:
                    h = hashlib.md5(fp.read_bytes()).hexdigest()
                    hash_groups.setdefault(h, []).append(str(fp))
                except Exception: pass
            for h, paths in hash_groups.items():
                if len(paths) > 1:
                    duplicates.append({"hash":h,"size_kb":round(sz/1024,1),"files":paths})
        wasted = sum(d["size_kb"]*(len(d["files"])-1) for d in duplicates)
        return {"success": True, "data": {"duplicates":duplicates,"groups":len(duplicates),
                "wasted_kb":round(wasted,1)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_empty_directories(directory: str) -> Dict[str, Any]:
    """Find all empty directories within a path."""
    try:
        d = Path(directory)
        if not d.is_dir():
            return {"success": False, "data": None, "error": f"Not a directory: {directory}"}
        empty = [str(p) for p in d.rglob("*") if p.is_dir() and not any(p.iterdir())]
        return {"success": True, "data": {"empty_dirs":empty,"count":len(empty)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_disk_usage_summary() -> Dict[str, Any]:
    """Summary of disk usage for all mounted drives."""
    try:
        if not HAS_PSUTIL:
            return {"success": False, "data": None, "error": "psutil not available"}
        summary = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                summary.append({"drive":part.mountpoint,"fstype":part.fstype,
                                 "total_gb":round(usage.total/1e9,2),
                                 "used_gb":round(usage.used/1e9,2),
                                 "free_gb":round(usage.free/1e9,2),
                                 "percent_used":usage.percent,
                                 "status":"critical" if usage.percent>90 else "warning" if usage.percent>75 else "ok"})
            except Exception: pass
        return {"success": True, "data": summary, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_recently_modified_files(directory: str, hours: int = 24,
                                 extensions: Optional[List[str]] = None) -> Dict[str, Any]:
    """Find files modified within the last N hours."""
    try:
        import time as time_mod
        d = Path(directory); cutoff = time_mod.time() - hours * 3600
        files = []
        for f in d.rglob("*"):
            if not f.is_file(): continue
            if extensions and f.suffix.lower() not in [e.lower() for e in extensions]: continue
            try:
                mtime = f.stat().st_mtime
                if mtime >= cutoff:
                    from datetime import datetime
                    files.append({"path":str(f),"modified":datetime.fromtimestamp(mtime).isoformat(),
                                   "size_kb":round(f.stat().st_size/1024,1)})
            except Exception: pass
        files.sort(key=lambda x: x["modified"], reverse=True)
        return {"success": True, "data": files, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_disk_io_rate(interval_seconds: float = 1.0) -> Dict[str, Any]:
    """Measure disk I/O rate over an interval (MB/s read and write)."""
    try:
        if not HAS_PSUTIL:
            return {"success": False, "data": None, "error": "psutil not available"}
        before = psutil.disk_io_counters()
        time.sleep(interval_seconds)
        after = psutil.disk_io_counters()
        rb = (after.read_bytes - before.read_bytes) / interval_seconds
        wb = (after.write_bytes - before.write_bytes) / interval_seconds
        return {"success": True, "data": {"read_mbps":round(rb/1e6,2),
                "write_mbps":round(wb/1e6,2),"interval_seconds":interval_seconds}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
