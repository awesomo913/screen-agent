"""
toolkit_25_process_memory.py
Inspect process memory usage, detect high-memory processes, analyze working sets,
and interact with virtual memory stats on Windows via psutil and ctypes.
"""
from __future__ import annotations
import os
import ctypes
from typing import Any, Dict, List

import psutil

try:
    import subprocess
    HAS_SUBPROCESS = True
except ImportError:
    HAS_SUBPROCESS = False

def get_memory_summary() -> Dict[str, Any]:
    try:
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        return {"success": True, "data": {
            "total_mb": round(vm.total / 1048576, 1),
            "available_mb": round(vm.available / 1048576, 1),
            "used_mb": round(vm.used / 1048576, 1),
            "percent": vm.percent,
            "swap_total_mb": round(sw.total / 1048576, 1),
            "swap_used_mb": round(sw.used / 1048576, 1),
            "swap_percent": sw.percent
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_processes_by_memory(top_n: int = 20) -> Dict[str, Any]:
    """List top N processes sorted by RSS memory usage."""
    try:
        procs = []
        for p in psutil.process_iter(["pid", "name", "memory_info", "memory_percent"]):
            try:
                mi = p.info.get("memory_info")
                procs.append({
                    "pid": p.info["pid"],
                    "name": p.info["name"],
                    "rss_mb": round(mi.rss / 1048576, 2) if mi else 0,
                    "vms_mb": round(mi.vms / 1048576, 2) if mi else 0,
                    "mem_percent": round(p.info.get("memory_percent") or 0, 2)
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        procs.sort(key=lambda x: x["rss_mb"], reverse=True)
        return {"success": True, "data": procs[:top_n], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_process_memory(pid: int) -> Dict[str, Any]:
    try:
        p = psutil.Process(pid)
        mi = p.memory_info()
        mfull = p.memory_full_info()
        return {"success": True, "data": {
            "pid": pid,
            "name": p.name(),
            "rss_mb": round(mi.rss / 1048576, 2),
            "vms_mb": round(mi.vms / 1048576, 2),
            "uss_mb": round(mfull.uss / 1048576, 2) if hasattr(mfull, "uss") else None,
            "peak_working_set_mb": round(mfull.peak_wset / 1048576, 2) if hasattr(mfull, "peak_wset") else None
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_memory_map(pid: int) -> Dict[str, Any]:
    """Get memory map for a process (mapped regions)."""
    try:
        p = psutil.Process(pid)
        mmap = p.memory_maps(grouped=True)
        result = [{"path": m.path, "rss_mb": round(m.rss / 1048576, 3)} for m in mmap]
        result.sort(key=lambda x: x["rss_mb"], reverse=True)
        return {"success": True, "data": result[:50], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_high_memory_processes(threshold_mb: float = 500) -> Dict[str, Any]:
    try:
        result = []
        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                mi = p.info.get("memory_info")
                if mi and mi.rss >= threshold_mb * 1048576:
                    result.append({
                        "pid": p.info["pid"],
                        "name": p.info["name"],
                        "rss_mb": round(mi.rss / 1048576, 2)
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        result.sort(key=lambda x: x["rss_mb"], reverse=True)
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_total_process_memory() -> Dict[str, Any]:
    """Total RSS memory consumed by all running processes."""
    try:
        total = 0
        count = 0
        for p in psutil.process_iter(["memory_info"]):
            try:
                mi = p.info.get("memory_info")
                if mi:
                    total += mi.rss
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return {"success": True, "data": {"processes": count, "total_rss_mb": round(total / 1048576, 1)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_memory_percent_by_process() -> Dict[str, Any]:
    try:
        procs = {}
        for p in psutil.process_iter(["name", "memory_percent"]):
            try:
                pct = p.info.get("memory_percent") or 0
                name = p.info.get("name", "unknown")
                procs[name] = procs.get(name, 0) + pct
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        sorted_procs = sorted(procs.items(), key=lambda x: x[1], reverse=True)[:20]
        return {"success": True, "data": dict(sorted_procs), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_physical_memory_info() -> Dict[str, Any]:
    """Detailed physical RAM slots info via WMI."""
    try:
        import subprocess, json
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-WmiObject Win32_PhysicalMemory | Select-Object BankLabel,Capacity,Speed,Manufacturer,MemoryType | ConvertTo-Json -Depth 2"],
            capture_output=True, text=True, timeout=20
        ).stdout.strip()
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        total = sum(int(d.get("Capacity", 0) or 0) for d in data)
        return {"success": True, "data": {"sticks": data, "total_gb": round(total / 1073741824, 1)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_pagefile_info() -> Dict[str, Any]:
    try:
        import subprocess, json
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-WmiObject Win32_PageFileUsage | Select-Object Name,AllocatedBaseSize,CurrentUsage,PeakUsage | ConvertTo-Json -Depth 2"],
            capture_output=True, text=True, timeout=20
        ).stdout.strip()
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_memory_pressure() -> Dict[str, Any]:
    """Returns a simple pressure indicator: low/medium/high/critical."""
    try:
        vm = psutil.virtual_memory()
        pct = vm.percent
        if pct < 50:
            level = "low"
        elif pct < 70:
            level = "medium"
        elif pct < 85:
            level = "high"
        else:
            level = "critical"
        return {"success": True, "data": {"percent_used": pct, "pressure": level, "free_mb": round(vm.available / 1048576, 1)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def kill_highest_memory_process() -> Dict[str, Any]:
    """Terminate the non-system process consuming the most memory."""
    try:
        system_names = {"system", "smss.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe", "svchost.exe"}
        top = None
        top_mem = 0
        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                mi = p.info.get("memory_info")
                if mi and p.info["name"].lower() not in system_names:
                    if mi.rss > top_mem:
                        top_mem = mi.rss
                        top = p
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if top:
            name = top.name()
            pid = top.pid
            top.kill()
            return {"success": True, "data": {"killed": name, "pid": pid, "freed_mb": round(top_mem / 1048576, 1)}, "error": None}
        return {"success": False, "data": None, "error": "No suitable process found"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_commit_charge() -> Dict[str, Any]:
    """Get Windows commit charge (total committed virtual memory)."""
    try:
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return {"success": True, "data": {
            "total_phys_gb": round(stat.ullTotalPhys / 1073741824, 2),
            "avail_phys_gb": round(stat.ullAvailPhys / 1073741824, 2),
            "total_pagefile_gb": round(stat.ullTotalPageFile / 1073741824, 2),
            "avail_pagefile_gb": round(stat.ullAvailPageFile / 1073741824, 2),
            "memory_load_percent": stat.dwMemoryLoad
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
