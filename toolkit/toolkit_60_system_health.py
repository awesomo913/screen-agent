"""
toolkit_60_system_health.py
Comprehensive system health check: aggregate CPU, memory, disk, network,
temperature, uptime, event errors, and services into a single health report.
"""
from __future__ import annotations
import subprocess
import json
import time
import os
from typing import Any, Dict, List

import psutil

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=20
    )
    return result.stdout.strip()

def get_cpu_health() -> Dict[str, Any]:
    try:
        usage = psutil.cpu_percent(interval=1)
        freq = psutil.cpu_freq()
        count = psutil.cpu_count()
        count_phys = psutil.cpu_count(logical=False)
        load = [round(x / count * 100, 1) for x in os.getloadavg()] if hasattr(os, "getloadavg") else []
        status = "critical" if usage > 90 else "high" if usage > 75 else "normal"
        return {"success": True, "data": {
            "usage_percent": usage,
            "status": status,
            "core_count": count,
            "physical_cores": count_phys,
            "freq_mhz": round(freq.current, 0) if freq else None,
            "freq_max_mhz": round(freq.max, 0) if freq else None
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_memory_health() -> Dict[str, Any]:
    try:
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        status = "critical" if vm.percent > 90 else "high" if vm.percent > 75 else "normal"
        return {"success": True, "data": {
            "total_gb": round(vm.total / 1073741824, 2),
            "available_gb": round(vm.available / 1073741824, 2),
            "used_percent": vm.percent,
            "status": status,
            "swap_used_percent": sw.percent
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_disk_health() -> Dict[str, Any]:
    try:
        partitions = psutil.disk_partitions()
        disks = []
        for p in partitions:
            try:
                usage = psutil.disk_usage(p.mountpoint)
                status = "critical" if usage.percent > 95 else "warning" if usage.percent > 85 else "normal"
                disks.append({
                    "device": p.device,
                    "mountpoint": p.mountpoint,
                    "total_gb": round(usage.total / 1073741824, 2),
                    "free_gb": round(usage.free / 1073741824, 2),
                    "used_percent": usage.percent,
                    "status": status
                })
            except Exception:
                pass
        overall = "critical" if any(d["status"] == "critical" for d in disks) else "warning" if any(d["status"] == "warning" for d in disks) else "normal"
        return {"success": True, "data": {"disks": disks, "overall_status": overall}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_network_health() -> Dict[str, Any]:
    try:
        import socket
        connected = True
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
        except Exception:
            connected = False
        stats = psutil.net_io_counters()
        return {"success": True, "data": {
            "internet_connected": connected,
            "total_sent_gb": round(stats.bytes_sent / 1073741824, 3),
            "total_recv_gb": round(stats.bytes_recv / 1073741824, 3),
            "errors_in": stats.errin,
            "errors_out": stats.errout
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_uptime() -> Dict[str, Any]:
    try:
        boot_time = psutil.boot_time()
        uptime_s = time.time() - boot_time
        days = int(uptime_s // 86400)
        hours = int((uptime_s % 86400) // 3600)
        mins = int((uptime_s % 3600) // 60)
        import datetime
        boot_dt = datetime.datetime.fromtimestamp(boot_time).isoformat()
        return {"success": True, "data": {
            "boot_time": boot_dt,
            "uptime_seconds": int(uptime_s),
            "uptime_formatted": str(days) + "d " + str(hours) + "h " + str(mins) + "m"
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_running_processes_count() -> Dict[str, Any]:
    try:
        procs = list(psutil.process_iter())
        return {"success": True, "data": {"count": len(procs)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_recent_error_events(count: int = 10) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-WinEvent -LogName System -MaxEvents 100 | Where-Object {$_.Level -eq 2} | Select-Object -First ' + str(count) + ' | Select-Object TimeCreated,Id,Message | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": {"count": len(data), "errors": data}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_failed_services() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-Service | Where-Object {$_.Status -eq 'Stopped' -and $_.StartType -eq 'Automatic'} | Select-Object Name,DisplayName,Status,StartType | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": {"count": len(data), "services": data}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_cpu_temperature() -> Dict[str, Any]:
    """Attempt to read CPU temperature via WMI (requires OEM support)."""
    try:
        out = _run_ps("Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi -ErrorAction SilentlyContinue | Select-Object CurrentTemperature | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else None
        if data:
            temps = [data] if isinstance(data, dict) else data
            celsius = [(t.get("CurrentTemperature", 0) - 2732) / 10 for t in temps if t.get("CurrentTemperature")]
            return {"success": True, "data": {"temperatures_c": celsius}, "error": None}
        return {"success": True, "data": {"note": "Temperature data not available (OEM WMI required)"}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_full_health_report() -> Dict[str, Any]:
    """Run all health checks and return a comprehensive report."""
    try:
        report = {}
        checks = {
            "cpu": get_cpu_health,
            "memory": get_memory_health,
            "disk": get_disk_health,
            "network": get_network_health,
            "uptime": get_uptime,
            "processes": get_running_processes_count,
            "failed_services": get_failed_services
        }
        overall_status = "healthy"
        for key, fn in checks.items():
            r = fn()
            report[key] = r["data"] if r["success"] else {"error": r["error"]}
            if r["success"] and isinstance(r["data"], dict):
                if r["data"].get("status") in ("critical", "warning"):
                    overall_status = "degraded"
        report["overall_status"] = overall_status
        return {"success": True, "data": report, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
