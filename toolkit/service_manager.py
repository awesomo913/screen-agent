import subprocess
import psutil
import ctypes
import platform
import json
import time
import threading
import os
import signal
from pathlib import Path
import winreg
from typing import Dict, Any, List, Optional, Callable, Union, Set
import re
import logging

# Configure module logger
logger = logging.getLogger(__name__)

def _make_response(success: bool, data: Any = None, message: str = "") -> Dict[str, Any]:
    """Standardized response dictionary."""
    return {
        "status": "success" if success else "error",
        "data": data,
        "message": message,
        "timestamp": time.time()
    }

def _is_admin() -> bool:
    """Check if the current process has administrative privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except AttributeError:
        return os.geteuid() == 0

def _run_command(cmd: List[str], timeout: float = 30.0) -> subprocess.CompletedProcess:
    """Execute a subprocess command securely with timeout."""
    startupinfo = None
    creationflags = 0
    if platform.system().lower() == "windows":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NO_WINDOW
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        startupinfo=startupinfo, creationflags=creationflags
    )

def _parse_sc_multiline_output(output: str) -> Dict[str, str]:
    """Parse indented SC.EXE output into a dictionary."""
    data: Dict[str, str] = {}
    for line in output.strip().splitlines():
        line = line.rstrip()
        if not line:
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower().replace(" ", "_")
            data[key] = value.strip()
    return data

def _get_service_binary_path(service_name: str) -> Optional[str]:
    """Retrieve binary path from SC query or registry."""
    try:
        res = _run_command(["sc.exe", "qc", service_name])
        if res.returncode == 0:
            parsed = _parse_sc_multiline_output(res.stdout)
            path = parsed.get("binary_path_name", "").strip('"')
            return path if path else None
    except Exception as e:
        logger.debug(f"Failed to get binary path via sc: {e}")
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"SYSTEM\\CurrentControlSet\\Services\\{service_name}") as key:
            path, _ = winreg.QueryValueEx(key, "ImagePath")
            return str(Path(path.strip('"')))
    except Exception:
        return None

# ==================== CORE FUNCTIONS ====================

def list_services(status_filter: Optional[str] = None) -> Dict[str, Any]:
    """List all services, optionally filtered by state (RUNNING, STOPPED, ALL)."""
    try:
        state_map = {"running": "active", "stopped": "inactive", "all": "all"}
        state_arg = state_map.get(status_filter.lower() if status_filter else "all", "all")
        
        # SC.EXE doesn't filter by 'all' states easily in one command, we query all and parse
        res = _run_command(["sc.exe", "queryex", "type=", "service", "state=", "all"])
        if res.returncode != 0:
            return _make_response(False, message=f"SC query failed: {res.stderr}")
            
        services = []
        blocks = re.split(r"\nSERVICE_NAME:", res.stdout)
        for i, block in enumerate(blocks[1:]):
            name = block.split("\n")[0].strip()
            info = _parse_sc_multiline_output(block)
            svc_state = info.get("state", "").split()[0] if info.get("state") else "UNKNOWN"
            
            if status_filter and svc_state.upper() != status_filter.upper():
                continue
                
            services.append({
                "name": name,
                "display_name": info.get("display_name", ""),
                "state": svc_state,
                "pid": int(info.get("pid", 0)),
                "win32_exit_code": info.get("win32_exit_code", "")
            })
        return _make_response(True, data=services)
    except Exception as e:
        return _make_response(False, message=str(e))

def get_service_status(service_name: str) -> Dict[str, Any]:
    """Get the current running status of a service."""
    try:
        res = _run_command(["sc.exe", "query", service_name])
        if res.returncode != 0:
            if "does not exist" in res.stderr.lower():
                return _make_response(False, message=f"Service '{service_name}' not found")
            return _make_response(False, message=f"Query failed: {res.stderr}")
        parsed = _parse_sc_multiline_output(res.stdout)
        return _make_response(True, data={"name": service_name, "status": parsed.get("state", "").strip()})
    except Exception as e:
        return _make_response(False, message=str(e))

def start_service(service_name: str) -> Dict[str, Any]:
    """Start a Windows service."""
    try:
        res = _run_command(["sc.exe", "start", service_name], timeout=60.0)
        if res.returncode != 0 and "already running" not in res.stderr.lower() and "already running" not in res.stdout.lower():
            return _make_response(False, message=f"Start failed: {res.stderr or res.stdout}")
        return _make_response(True, data={"service": service_name, "action": "start"})
    except Exception as e:
        return _make_response(False, message=str(e))

def stop_service(service_name: str) -> Dict[str, Any]:
    """Stop a Windows service."""
    try:
        res = _run_command(["sc.exe", "stop", service_name], timeout=60.0)
        if res.returncode != 0 and "not running" not in res.stderr.lower() and "not running" not in res.stdout.lower():
            return _make_response(False, message=f"Stop failed: {res.stderr or res.stdout}")
        return _make_response(True, data={"service": service_name, "action": "stop"})
    except Exception as e:
        return _make_response(False, message=str(e))

def restart_service(service_name: str) -> Dict[str, Any]:
    """Safely stop then start a service."""
    stop_res = stop_service(service_name)
    if not stop_res["status"] == "success":
        return _make_response(False, message=f"Pre-restart stop failed: {stop_res['message']}")
    time.sleep(2.0)
    return start_service(service_name)

def pause_service(service_name: str) -> Dict[str, Any]:
    """Pause a Windows service."""
    try:
        res = _run_command(["sc.exe", "pause", service_name])
        return _make_response(res.returncode == 0, data={"service": service_name},
                              message="Paused successfully" if res.returncode == 0 else res.stderr)
    except Exception as e:
        return _make_response(False, message=str(e))

def resume_service(service_name: str) -> Dict[str, Any]:
    """Resume a paused service."""
    try:
        res = _run_command(["sc.exe", "continue", service_name])
        return _make_response(res.returncode == 0, data={"service": service_name},
                              message="Resumed successfully" if res.returncode == 0 else res.stderr)
    except Exception as e:
        return _make_response(False, message=str(e))

def enable_service(service_name: str) -> Dict[str, Any]:
    """Set service to start automatically (demand/auto)."""
    return set_service_startup_type(service_name, "auto")

def disable_service(service_name: str) -> Dict[str, Any]:
    """Disable a service."""
    return set_service_startup_type(service_name, "disabled")

def get_service_info(service_name: str) -> Dict[str, Any]:
    """Retrieve comprehensive service information."""
    try:
        res = _run_command(["sc.exe", "qc", service_name])
        if res.returncode != 0:
            return _make_response(False, message=f"Service not found: {service_name}")
        
        info = _parse_sc_multiline_output(res.stdout)
        info["name"] = service_name
        info["binary_path"] = _get_service_binary_path(service_name)
        
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"SYSTEM\\CurrentControlSet\\Services\\{service_name}") as key:
                info["error_control"] = str(winreg.QueryValueEx(key, "ErrorControl")[0])
                info["object_name"] = winreg.QueryValueEx(key, "ObjectName")[0]
        except Exception as e:
            logger.debug(f"Registry fallback warning: {e}")
            
        return _make_response(True, data=info)
    except Exception as e:
        return _make_response(False, message=str(e))

def find_service_by_name(pattern: str) -> Dict[str, Any]:
    """Search services by display name or service name using regex."""
    try:
        all_svcs = list_services()
        if not all_svcs["status"] == "success":
            return all_svcs
            
        matches = []
        compiled = re.compile(pattern, re.IGNORECASE)
        for svc in all_svcs["data"]:
            if compiled.search(svc.get("name", "")) or compiled.search(svc.get("display_name", "")):
                matches.append(svc)
        return _make_response(True, data=matches)
    except Exception as e:
        return _make_response(False, message=str(e))

def find_service_by_pid(pid: int) -> Dict[str, Any]:
    """Identify service associated with a specific PID."""
    try:
        # Check if process exists
        if not psutil.pid_exists(pid):
            return _make_response(False, message=f"PID {pid} not found")
            
        p = psutil.Process(pid)
        # Try matching against service queryex
        svc_list = []
        res = _run_command(["sc.exe", "queryex", "type=", "service", "state=", "all"])
        for match in re.finditer(r"SERVICE_NAME:\s*(.+?)\n.*?PID:\s*(\d+)", res.stdout, re.DOTALL):
            if int(match.group(2)) == pid:
                svc_list.append(match.group(1))
                
        if svc_list:
            return _make_response(True, data={"pid": pid, "services": svc_list, "process_name": p.name()})
            
        return _make_response(True, data={"pid": pid, "services": [], "process_name": p.name(), "note": "No direct service mapping found"})
    except Exception as e:
        return _make_response(False, message=str(e))

def get_service_dependencies(service_name: str) -> Dict[str, Any]:
    """Get services that this service depends on."""
    try:
        info_res = get_service_info(service_name)
        if info_res["status"] != "success":
            return info_res
            
        deps_str = info_res["data"].get("dependencies", "")
        if not deps_str or deps_str.lower() == "null" or deps_str == "":
            return _make_response(True, data={"service": service_name, "depends_on": []})
            
        deps = [d.strip() for d in deps_str.split("/") if d.strip()]
        return _make_response(True, data={"service": service_name, "depends_on": deps})
    except Exception as e:
        return _make_response(False, message=str(e))

def get_dependent_services(service_name: str) -> Dict[str, Any]:
    """Get services that depend on this service."""
    try:
        res = _run_command(["sc.exe", "enumdepend", service_name])
        dependents = []
        for match in re.finditer(r"SERVICE_NAME:\s*(\S+)", res.stdout):
            dependents.append(match.group(1))
            
        return _make_response(True, data={"parent_service": service_name, "dependents": dependents})
    except Exception as e:
        return _make_response(False, message=str(e))

def set_service_startup_type(service_name: str, startup_type: str) -> Dict[str, Any]:
    """Configure startup type: auto, manual, disabled, delayed-auto."""
    valid = {"auto": "auto", "manual": "demand", "disabled": "disabled", "delayed-auto": "delayed-auto"}
    mapped = valid.get(startup_type.lower().replace("-", "")) or valid.get(startup_type.lower())
    if not mapped:
        return _make_response(False, message=f"Invalid startup type. Use: {list(valid.keys())}")
        
    try:
        res = _run_command(["sc.exe", "config", service_name, "start=", mapped])
        if res.returncode != 0:
            return _make_response(False, message=f"Config failed: {res.stderr or res.stdout}")
            
        # Verify in registry
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"SYSTEM\\CurrentControlSet\\Services\\{service_name}") as k:
                start_val, _ = winreg.QueryValueEx(k, "Start")
                # 2=auto, 3=demand, 4=disabled, 3|2=delayed
                expected_map = {"auto": 2, "demand": 3, "delayed-auto": 50, "disabled": 4}
        except Exception:
            pass
            
        return _make_response(True, data={"service": service_name, "startup_type": mapped})
    except Exception as e:
        return _make_response(False, message=str(e))

def create_service(name: str, binary_path: str, display_name: str) -> Dict[str, Any]:
    """Create a new Windows service."""
    if not Path(binary_path).exists() and "/" not in binary_path:
        return _make_response(False, message="Binary path does not exist")
        
    try:
        bin_path = str(Path(binary_path).resolve())
        res = _run_command(["sc.exe", "create", name, "binPath=", bin_path, "start=", "auto", "DisplayName=", display_name])
        if res.returncode != 0:
            return _make_response(False, message=f"Creation failed: {res.stderr or res.stdout}")
        return _make_response(True, data={"name": name, "path": bin_path, "display": display_name})
    except Exception as e:
        return _make_response(False, message=str(e))

def delete_service(service_name: str) -> Dict[str, Any]:
    """Delete a service and remove registry entries."""
    try:
        stop_service(service_name)  # Best effort stop
        res = _run_command(["sc.exe", "delete", service_name])
        if res.returncode != 0:
            return _make_response(False, message=f"Deletion failed: {res.stderr or res.stdout}")
            
        # Cleanup registry
        try:
            winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, f"SYSTEM\\CurrentControlSet\\Services\\{service_name}")
        except FileNotFoundError:
            pass
        return _make_response(True, data={"service": service_name})
    except Exception as e:
        return _make_response(False, message=str(e))

def get_service_logs(service_name: str, lines: int = 50) -> Dict[str, Any]:
    """Fetch recent Event Viewer logs for a service."""
    try:
        provider_name = service_name
        # Fallback provider name resolution
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"SYSTEM\\CurrentControlSet\\Services\\{service_name}") as k:
                if "ImageName" in str(winreg.QueryValueEx(k, "ImagePath")):
                    provider_name = Path(winreg.QueryValueEx(k, "ImagePath")[0]).stem
        except Exception:
            pass
            
        cmd = ["wevtutil.exe", "qe", "System", 
               f"/q:*[System[Provider[@Name='{provider_name}' or Provider[@Name='{service_name}']]]]",
               "/f:RenderedXml", f"/c:{lines}"]
        res = _run_command(cmd)
        
        if res.returncode != 0:
            return _make_response(True, data={"service": service_name, "logs": [], "note": "No events found or access denied"})
            
        # Extract message tags
        messages = re.findall(r"<EventMessage>(.*?)</EventMessage>", res.stdout, re.DOTALL)
        return _make_response(True, data={"service": service_name, "log_entries": messages[:lines]})
    except Exception as e:
        return _make_response(False, message=str(e))

# Background Monitor Registry
_monitor_registry: Dict[str, threading.Thread] = {}

def monitor_service(service_name: str, callback: Callable[[Dict[str, Any]], None], interval: float = 5.0) -> Dict[str, Any]:
    """Start background monitoring thread for a service."""
    def _worker():
        while _monitor_registry.get(service_name):
            try:
                status_res = get_service_status(service_name)
                callback(status_res)
            except Exception:
                pass
            # Interruptible sleep
            evt = threading.Event()
            if not evt.wait(interval):
                break
                
    if service_name in _monitor_registry:
        return _make_response(False, message=f"Already monitoring {service_name}")
        
    thread = threading.Thread(target=_worker, name=f"monitor_{service_name}", daemon=True)
    _monitor_registry[service_name] = thread
    thread.start()
    return _make_response(True, data={"service": service_name, "thread_id": thread.ident, "interval": interval})

def batch_start_services(service_names: List[str]) -> Dict[str, Any]:
    """Start multiple services and aggregate results."""
    results = {}
    for svc in service_names:
        res = start_service(svc)
        results[svc] = {"status": res["status"], "message": res["message"]}
    success_count = sum(1 for r in results.values() if r["status"] == "success")
    return _make_response(True, data={"results": results, "success_count": success_count})

def batch_stop_services(service_names: List[str]) -> Dict[str, Any]:
    """Stop multiple services and aggregate results."""
    results = {}
    for svc in service_names:
        res = stop_service(svc)
        results[svc] = {"status": res["status"], "message": res["message"]}
    success_count = sum(1 for r in results.values() if r["status"] == "success")
    return _make_response(True, data={"results": results, "success_count": success_count})

def get_service_uptime(service_name: str) -> Dict[str, Any]:
    """Calculate service uptime based on PID creation time."""
    try:
        status = get_service_status(service_name)
        if "RUNNING" not in status.get("data", {}).get("status", "").upper():
            return _make_response(False, message="Service is not running")
            
        info = get_service_info(service_name)
        pid = int(info["data"].get("pid", 0))
        if not pid or pid == 0:
            return _make_response(False, message="No PID associated")
            
        p = psutil.Process(pid)
        uptime_seconds = time.time() - p.create_time()
        return _make_response(True, data={"service": service_name, "pid": pid, "uptime_seconds": round(uptime_seconds, 2)})
    except Exception as e:
        return _make_response(False, message=str(e))

def check_service_health(service_name: str, port: int) -> Dict[str, Any]:
    """Verify service status and optional port binding health."""
    try:
        # 1. Check SCM State
        status_res = get_service_status(service_name)
        is_running = "RUNNING" in status_res.get("data", {}).get("status", "").upper()
        
        port_ok = True
        port_msg = "N/A"
        info_res = get_service_info(service_name)
        pid = int(info_res["data"].get("pid", 0))
        
        if port and pid:
            # Verify port binding via psutil
            net_conns = psutil.Process(pid).net_connections(kind="tcp4")
            port_ok = any(c.laddr.port == port for c in net_conns)
            port_msg = "Bound" if port_ok else "Not Listening"
            
        healthy = is_running and port_ok
        return _make_response(healthy, data={
            "service": service_name,
            "scm_status": "running" if is_running else "stopped",
            "port": port,
            "port_status": port_msg,
            "healthy": healthy
        })
    except Exception as e:
        return _make_response(False, message=str(e))

def export_services_config(output: str) -> Dict[str, Any]:
    """Export current service configurations to a JSON file."""
    try:
        out_path = Path(output)
        all_svcs = list_services()
        if all_svcs["status"] != "success":
            return all_svcs
            
        export_data = []
        for svc in all_svcs["data"]:
            info = get_service_info(svc["name"])
            if info["status"] == "success":
                export_data.append(info["data"])
                
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)
            
        return _make_response(True, data={"file": str(out_path), "exported_count": len(export_data)})
    except Exception as e:
        return _make_response(False, message=str(e))

def import_services_config(filepath: str) -> Dict[str, Any]:
    """Import and apply service configurations from JSON."""
    try:
        path = Path(filepath)
        if not path.exists():
            return _make_response(False, message=f"File not found: {filepath}")
            
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
            
        if not isinstance(config, list):
            return _make_response(False, message="Invalid JSON format. Expected list of service objects.")
            
        results = []
        for svc_cfg in config:
            name = svc_cfg.get("name")
            if not name: continue
                
            res_status = get_service_status(name)
            if res_status["status"] != "success":
                # Try to create if missing
                bin_path = svc_cfg.get("binary_path_name") or svc_cfg.get("binary_path")
                if bin_path:
                    create_service(name, bin_path, svc_cfg.get("display_name", name))
                    
            startup = svc_cfg.get("start_type", svc_cfg.get("start", "demand"))
            set_service_startup_type(name, startup)
            results.append({"name": name, "status": "applied"})
            
        return _make_response(True, data={"imported": len(results), "details": results})
    except Exception as e:
        return _make_response(False, message=str(e))