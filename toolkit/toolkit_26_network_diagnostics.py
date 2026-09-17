"""
toolkit_26_network_diagnostics.py
Network connectivity tests, latency measurements, route tracing,
and interface diagnostics. Uses stdlib + subprocess only.
"""
from __future__ import annotations
import subprocess
import socket
import time
import json
import re
from typing import Any, Dict, List

def _run(cmd: list, timeout: int = 30) -> tuple:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.stdout.strip(), result.returncode

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()

def ping(host: str, count: int = 4) -> Dict[str, Any]:
    try:
        out, code = _run(["ping", "-n", str(count), host])
        lines = out.splitlines()
        stats_line = [l for l in lines if "Average" in l or "Minimum" in l]
        packet_line = [l for l in lines if "Lost" in l or "loss" in l.lower()]
        return {"success": code == 0, "data": {
            "host": host,
            "reachable": code == 0,
            "output_summary": lines[-3:] if len(lines) >= 3 else lines
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def ping_with_latency(host: str) -> Dict[str, Any]:
    try:
        start = time.perf_counter()
        out, code = _run(["ping", "-n", "1", host], timeout=10)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        m = re.search(r"time[=<](\d+)ms", out, re.IGNORECASE)
        rtt = int(m.group(1)) if m else None
        return {"success": code == 0, "data": {"host": host, "reachable": code == 0, "rtt_ms": rtt, "elapsed_ms": elapsed_ms}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def traceroute(host: str, max_hops: int = 30) -> Dict[str, Any]:
    try:
        out, code = _run(["tracert", "-h", str(max_hops), "-d", host], timeout=60)
        hops = []
        for line in out.splitlines():
            m = re.match(r"\s*(\d+)\s+(.+)", line)
            if m:
                hops.append({"hop": int(m.group(1)), "info": m.group(2).strip()})
        return {"success": True, "data": {"host": host, "hops": hops}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def resolve_hostname(hostname: str) -> Dict[str, Any]:
    try:
        addresses = socket.getaddrinfo(hostname, None)
        ips = list(set([a[4][0] for a in addresses]))
        return {"success": True, "data": {"hostname": hostname, "ip_addresses": ips}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def reverse_lookup(ip: str) -> Dict[str, Any]:
    try:
        hostname = socket.gethostbyaddr(ip)[0]
        return {"success": True, "data": {"ip": ip, "hostname": hostname}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_port_open(host: str, port: int, timeout: float = 3.0) -> Dict[str, Any]:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        open_ = result == 0
        return {"success": True, "data": {"host": host, "port": port, "open": open_}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def scan_ports(host: str, ports: list) -> Dict[str, Any]:
    try:
        results = {}
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                open_ = sock.connect_ex((host, int(port))) == 0
                sock.close()
                results[str(port)] = open_
            except Exception:
                results[str(port)] = False
        return {"success": True, "data": results, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_network_interfaces() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-NetAdapter | Select-Object Name,InterfaceDescription,Status,LinkSpeed,MacAddress | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_ip_addresses() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-NetIPAddress | Where-Object {$_.AddressFamily -eq 'IPv4'} | Select-Object InterfaceAlias,IPAddress,PrefixLength,AddressState | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_default_gateway() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Select-Object InterfaceAlias,NextHop,RouteMetric | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else None
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_dns_servers() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-DnsClientServerAddress | Where-Object {$_.AddressFamily -eq 2} | Select-Object InterfaceAlias,ServerAddresses | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def run_netstat_summary() -> Dict[str, Any]:
    try:
        out, code = _run(["netstat", "-an"])
        lines = out.splitlines()
        listening = sum(1 for l in lines if "LISTENING" in l)
        established = sum(1 for l in lines if "ESTABLISHED" in l)
        time_wait = sum(1 for l in lines if "TIME_WAIT" in l)
        return {"success": True, "data": {"listening": listening, "established": established, "time_wait": time_wait, "total_lines": len(lines)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_active_connections() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-NetTCPConnection | Where-Object {$_.State -eq 'Established'} | Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_local_hostname() -> Dict[str, Any]:
    try:
        hostname = socket.gethostname()
        return {"success": True, "data": hostname, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_public_ip() -> Dict[str, Any]:
    """Attempt to get public IP via socket trick (no HTTP required)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        return {"success": True, "data": {"local_ip": local_ip}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def test_internet_connectivity() -> Dict[str, Any]:
    try:
        results = {}
        for host in ["8.8.8.8", "1.1.1.1", "google.com"]:
            result = ping_with_latency(host)
            results[host] = {"reachable": result["data"].get("reachable", False) if result["success"] else False,
                             "rtt_ms": result["data"].get("rtt_ms") if result["success"] else None}
        connected = any(v["reachable"] for v in results.values())
        return {"success": True, "data": {"connected": connected, "tests": results}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
