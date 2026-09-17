import psutil
import platform
import os
import subprocess
import socket
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

def _success(data: Any) -> Dict[str, Any]:
    return {"status": "success", "data": data}

def _fail(error: str) -> Dict[str, Any]:
    return {"status": "error", "data": None, "error": error}

def get_cpu_usage(interval: float = 1.0) -> Dict[str, Any]:
    try:
        total = psutil.cpu_percent(interval=interval)
        per_cpu = psutil.cpu_percent(interval=0, percpu=True)
        return _success({"total_percent": total, "per_cpu_percent": per_cpu, "measurement_interval": interval})
    except Exception as e:
        return _fail(str(e))

def get_cpu_info() -> Dict[str, Any]:
    try:
        info = {
            "processor": platform.processor() or "Unknown",
            "architecture": platform.machine(),
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True)
        }
        try:
            if platform.system() == 'Linux':
                out = subprocess.run(['uname', '-r'], capture_output=True, text=True, check=True)
                info['kernel_version'] = out.stdout.strip()
            elif platform.system() == 'Windows':
                out = subprocess.run(['cmd', '/c', 'ver'], capture_output=True, text=True, check=True)
                info['kernel_version'] = out.stdout.strip()
        except subprocess.SubprocessError:
            pass
        return _success(info)
    except Exception as e:
        return _fail(str(e))

def get_cpu_freq() -> Dict[str, Any]:
    try:
        freq = psutil.cpu_freq()
        if freq is None:
            return _fail("CPU frequency information is not available on this system.")
        return _success({"current_mhz": freq.current, "min_mhz": freq.min, "max_mhz": freq.max})
    except Exception as e:
        return _fail(str(e))

def get_cpu_count(logical: bool = True) -> Dict[str, Any]:
    try:
        count = psutil.cpu_count(logical=logical)
        return _success({"count": count, "logical": logical})
    except Exception as e:
        return _fail(str(e))

def get_memory_usage() -> Dict[str, Any]:
    try:
        mem = psutil.virtual_memory()
        return _success(mem._asdict())
    except Exception as e:
        return _fail(str(e))

def get_swap_usage() -> Dict[str, Any]:
    try:
        swap = psutil.swap_memory()
        return _success(swap._asdict())
    except Exception as e:
        return _fail(str(e))

def get_disk_usage(path: str = "/") -> Dict[str, Any]:
    try:
        if not os.path.exists(path):
            return _fail(f"Path '{path}' does not exist.")
        usage = psutil.disk_usage(path)
        return _success(usage._asdict())
    except Exception as e:
        return _fail(str(e))

def get_all_disks() -> Dict[str, Any]:
    try:
        partitions = psutil.disk_partitions(all=True)
        return _success([p._asdict() for p in partitions])
    except Exception as e:
        return _fail(str(e))

def get_disk_io() -> Dict[str, Any]:
    try:
        io = psutil.disk_io_counters(perdisk=True, nowrap=True)
        if io is None:
            return _fail("Disk I/O counters are not available.")
        return _success({disk: stats._asdict() for disk, stats in io.items()})
    except Exception as e:
        return _fail(str(e))

def get_network_io() -> Dict[str, Any]:
    try:
        io = psutil.net_io_counters(pernic=True, nowrap=True)
        return _success({iface: stats._asdict() for iface, stats in io.items()})
    except Exception as e:
        return _fail(str(e))

def get_network_connections(kind: str = "inet") -> Dict[str, Any]:
    try:
        conns = psutil.net_connections(kind=kind)
        return _success([c._asdict() for c in conns])
    except psutil.AccessDenied:
        return _fail("Insufficient privileges to query network connections.")
    except Exception as e:
        return _fail(str(e))

def get_network_interfaces() -> Dict[str, Any]:
    try:
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        interfaces: Dict[str, Any] = {}
        for iface, addr_list in addrs.items():
            addresses = [{"family": str(a.family), "address": a.address, "netmask": a.netmask, "broadcast": a.broadcast} for a in addr_list]
            s = stats.get(iface)
            interfaces[iface] = {"addresses": addresses, "stats": s._asdict() if s else None}
        return _success(interfaces)
    except Exception as e:
        return _fail(str(e))

def get_process_list(sort_by: str = "cpu_percent") -> Dict[str, Any]:
    try:
        processes = []
        for p in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status', 'create_time', 'nice']):
            try:
                info = p.info
                if info.get('create_time') is not None:
                    info['create_time_iso'] = datetime.fromtimestamp(info['create_time']).isoformat()
                    del info['create_time']
                processes.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        valid_sort_keys = {'pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'nice'}
        if sort_by in valid_sort_keys and processes:
            processes.sort(key=lambda x: (x.get(sort_by, 0) or 0), reverse=True)

        return _success({"processes": processes, "count": len(processes)})
    except Exception as e:
        return _fail(str(e))

def get_process_info(pid: int) -> Dict[str, Any]:
    try:
        p = psutil.Process(pid)
        info = p.as_dict(attrs=['pid', 'name', 'exe', 'cmdline', 'username', 'create_time', 'status', 
                                'cpu_percent', 'memory_percent', 'memory_info', 'connections', 'open_files', 'threads'])
        if info.get('create_time'):
            info['create_time_iso'] = datetime.fromtimestamp(info['create_time']).isoformat()
            
        for key, val in list(info.items()):
            if hasattr(val, '_asdict'):
                info[key] = val._asdict()
            elif isinstance(val, list):
                info[key] = [item._asdict() if hasattr(item, '_asdict') else item for item in val]
                
        return _success(info)
    except psutil.NoSuchProcess:
        return _fail(f"Process with PID {pid} not found.")
    except psutil.AccessDenied:
        return _fail(f"Access denied for PID {pid}.")
    except Exception as e:
        return _fail(str(e))

def kill_process(pid: int, force: bool = False) -> Dict[str, Any]:
    try:
        p = psutil.Process(pid)
        if p.is_running():
            p.kill() if force else p.terminate()
            p.wait(timeout=5)
        action = "force_killed" if force else "terminated"
        return _success({"pid": pid, "action": action, "status": "completed"})
    except psutil.NoSuchProcess:
        return _fail(f"Process with PID {pid} not found.")
    except (psutil.AccessDenied, psutil.TimeoutExpired, Exception) as e:
        return _fail(str(e))

def get_battery_status() -> Dict[str, Any]:
    try:
        batt = psutil.sensors_battery()
        if batt is None:
            return _fail("Battery status is not available or not applicable for this system.")
        secs_left = "Unknown" if batt.secsleft == psutil.POWER_TIME_UNKNOWN else str(batt.secsleft)
        return _success({"percent": batt.percent, "seconds_left": secs_left, "power_plugged": batt.power_plugged})
    except Exception as e:
        return _fail(str(e))

def get_system_uptime() -> Dict[str, Any]:
    try:
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        return _success({"boot_timestamp": datetime.fromtimestamp(boot_time).isoformat(), "uptime_seconds": uptime_seconds})
    except Exception as e:
        return _fail(str(e))

def get_boot_time() -> Dict[str, Any]:
    try:
        bt = psutil.boot_time()
        return _success({"timestamp": bt, "isoformat": datetime.fromtimestamp(bt).isoformat()})
    except Exception as e:
        return _fail(str(e))

def get_os_info() -> Dict[str, Any]:
    try:
        uname = platform.uname()
        info = {
            "system": uname.system,
            "node": uname.node,
            "release": uname.release,
            "version": uname.version,
            "machine": uname.machine,
            "processor": uname.processor,
            "platform": platform.platform()
        }
        return _success(info)
    except Exception as e:
        return _fail(str(e))

def get_hostname() -> Dict[str, Any]:
    try:
        hostname = socket.gethostname()
        fqdn = socket.getfqdn()
        return _success({"hostname": hostname, "fqdn": fqdn})
    except Exception as e:
        return _fail(str(e))

def get_ip_addresses() -> Dict[str, Any]:
    try:
        addrs = psutil.net_if_addrs()
        ip_dict: Dict[str, List[str]] = {
            iface: [a.address for a in iface_addrs if a.family == socket.AF_INET]
            for iface, iface_addrs in addrs.items()
        }
        return _success(ip_dict)
    except Exception as e:
        return _fail(str(e))

def get_logged_users() -> Dict[str, Any]:
    try:
        users = [u._asdict() for u in psutil.users()]
        return _success(users)
    except Exception as e:
        return _fail(str(e))

def get_temperature_sensors() -> Dict[str, Any]:
    try:
        if not hasattr(psutil, "sensors_temperatures"):
            return _fail("Temperature sensors API is not available on this platform.")
        temps = psutil.sensors_temperatures()
        if not temps:
            return _fail("No temperature sensor data found.")
        result = {chip: [t._asdict() for t in chip_temps] for chip, chip_temps in temps.items()}
        return _success(result)
    except Exception as e:
        return _fail(str(e))

def monitor_resource(resource: str = "cpu", interval: float = 1.0, duration: int = 10) -> Dict[str, Any]:
    try:
        measurements = []
        start_time = time.time()
        resource = resource.lower()
        
        if resource not in {"cpu", "memory", "disk", "network"}:
            return _fail(f"Unsupported resource: {resource}. Choose from cpu, memory, disk, network.")

        while time.time() - start_time < duration:
            timestamp = time.time()
            if resource == "cpu":
                value = psutil.cpu_percent(interval=interval)
            elif resource == "memory":
                value = psutil.virtual_memory().percent
            elif resource == "disk":
                value = psutil.disk_usage('/').percent
            elif resource == "network":
                io = psutil.net_io_counters()
                value = {"bytes_sent": io.bytes_sent, "bytes_recv": io.bytes_recv}
            measurements.append({"timestamp": timestamp, "value": value})
            time.sleep(interval)

        return _success({"resource": resource, "interval": interval, "measurements": measurements})
    except Exception as e:
        return _fail(str(e))

def generate_system_report(output_path: str = "") -> Dict[str, Any]:
    try:
        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "agent_version": "1.0.0"
            },
            "hostname": get_hostname()["data"],
            "os": get_os_info()["data"],
            "cpu_usage": get_cpu_usage(interval=0.5)["data"],
            "cpu_info": get_cpu_info()["data"],
            "cpu_freq": get_cpu_freq()["data"],
            "memory_usage": get_memory_usage()["data"],
            "swap_usage": get_swap_usage()["data"],
            "disk_usage_root": get_disk_usage("/")["data"],
            "all_disks": get_all_disks()["data"],
            "disk_io": get_disk_io()["data"],
            "network_io": get_network_io()["data"],
            "network_interfaces": get_network_interfaces()["data"],
            "logged_users": get_logged_users()["data"],
            "system_uptime": get_system_uptime()["data"],
            "temperature_sensors": get_temperature_sensors()["data"],
            "battery_status": get_battery_status()["data"]
        }

        if output_path:
            dir_name = os.path.dirname(output_path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str)

        return _success(report)
    except Exception as e:
        return _fail(str(e))