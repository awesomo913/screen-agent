"""
toolkit_59_network_traffic.py
Monitor and analyze Windows network traffic: interface stats, active
connections with process mapping, bandwidth usage, and top talkers.
"""
from __future__ import annotations
import subprocess
import json
import time
from typing import Any, Dict, List

import psutil

def get_network_io_stats() -> Dict[str, Any]:
    """Get total bytes sent/received per interface."""
    try:
        counters = psutil.net_io_counters(pernic=True)
        result = {}
        for nic, stats in counters.items():
            result[nic] = {
                "bytes_sent": stats.bytes_sent,
                "bytes_recv": stats.bytes_recv,
                "packets_sent": stats.packets_sent,
                "packets_recv": stats.packets_recv,
                "errin": stats.errin,
                "errout": stats.errout,
                "dropin": stats.dropin,
                "dropout": stats.dropout
            }
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_bandwidth_usage(duration_s: float = 2.0) -> Dict[str, Any]:
    """Measure bandwidth usage over a short interval."""
    try:
        before = psutil.net_io_counters()
        time.sleep(duration_s)
        after = psutil.net_io_counters()
        sent_bps = (after.bytes_sent - before.bytes_sent) / duration_s
        recv_bps = (after.bytes_recv - before.bytes_recv) / duration_s
        return {"success": True, "data": {
            "upload_kbps": round(sent_bps / 1024, 2),
            "download_kbps": round(recv_bps / 1024, 2),
            "upload_mbps": round(sent_bps / 1048576, 4),
            "download_mbps": round(recv_bps / 1048576, 4),
            "duration_s": duration_s
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_connections_with_process() -> Dict[str, Any]:
    """List all TCP/UDP connections with owning process names."""
    try:
        connections = psutil.net_connections(kind="all")
        result = []
        for conn in connections:
            try:
                proc_name = psutil.Process(conn.pid).name() if conn.pid else ""
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                proc_name = ""
            laddr = ":".join([conn.laddr.ip, str(conn.laddr.port)]) if conn.laddr else ""
            raddr = ":".join([conn.raddr.ip, str(conn.raddr.port)]) if conn.raddr else ""
            result.append({
                "pid": conn.pid,
                "process": proc_name,
                "status": conn.status,
                "type": "TCP" if conn.type == 1 else "UDP",
                "local": laddr,
                "remote": raddr
            })
        return {"success": True, "data": {"count": len(result), "connections": result}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_listening_ports() -> Dict[str, Any]:
    try:
        connections = psutil.net_connections(kind="tcp")
        listening = []
        for conn in connections:
            if conn.status == "LISTEN":
                try:
                    proc_name = psutil.Process(conn.pid).name() if conn.pid else ""
                except Exception:
                    proc_name = ""
                listening.append({
                    "port": conn.laddr.port if conn.laddr else 0,
                    "ip": conn.laddr.ip if conn.laddr else "",
                    "pid": conn.pid,
                    "process": proc_name
                })
        listening.sort(key=lambda x: x["port"])
        return {"success": True, "data": listening, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_established_connections() -> Dict[str, Any]:
    try:
        connections = psutil.net_connections(kind="tcp")
        established = []
        for conn in connections:
            if conn.status == "ESTABLISHED" and conn.raddr:
                try:
                    proc_name = psutil.Process(conn.pid).name() if conn.pid else ""
                except Exception:
                    proc_name = ""
                established.append({
                    "pid": conn.pid,
                    "process": proc_name,
                    "local": conn.laddr.ip + ":" + str(conn.laddr.port) if conn.laddr else "",
                    "remote": conn.raddr.ip + ":" + str(conn.raddr.port) if conn.raddr else ""
                })
        return {"success": True, "data": {"count": len(established), "connections": established}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_network_interfaces_detail() -> Dict[str, Any]:
    try:
        addresses = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        result = {}
        for nic in addresses:
            addrs = []
            for addr in addresses[nic]:
                addrs.append({
                    "family": str(addr.family),
                    "address": addr.address,
                    "netmask": addr.netmask,
                    "broadcast": addr.broadcast
                })
            nic_stats = stats.get(nic)
            result[nic] = {
                "addresses": addrs,
                "is_up": nic_stats.isup if nic_stats else False,
                "speed_mbps": nic_stats.speed if nic_stats else 0,
                "mtu": nic_stats.mtu if nic_stats else 0
            }
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_top_network_processes(top_n: int = 10) -> Dict[str, Any]:
    """Approximate network activity by connections count per process."""
    try:
        proc_conns: dict = {}
        for conn in psutil.net_connections(kind="tcp"):
            if conn.pid and conn.status == "ESTABLISHED":
                try:
                    name = psutil.Process(conn.pid).name()
                    proc_conns[name] = proc_conns.get(name, 0) + 1
                except Exception:
                    pass
        sorted_procs = sorted(proc_conns.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return {"success": True, "data": dict(sorted_procs), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_port_in_use(port: int) -> Dict[str, Any]:
    try:
        for conn in psutil.net_connections(kind="all"):
            if conn.laddr and conn.laddr.port == port:
                try:
                    proc_name = psutil.Process(conn.pid).name() if conn.pid else ""
                except Exception:
                    proc_name = ""
                return {"success": True, "data": {"in_use": True, "pid": conn.pid, "process": proc_name, "status": conn.status}, "error": None}
        return {"success": True, "data": {"in_use": False}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_total_network_bytes() -> Dict[str, Any]:
    try:
        c = psutil.net_io_counters()
        return {"success": True, "data": {
            "total_sent_gb": round(c.bytes_sent / 1073741824, 3),
            "total_recv_gb": round(c.bytes_recv / 1073741824, 3),
            "total_packets_sent": c.packets_sent,
            "total_packets_recv": c.packets_recv
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_arp_table() -> Dict[str, Any]:
    try:
        import subprocess as sp
        out = sp.run(["arp", "-a"], capture_output=True, text=True, timeout=10).stdout
        entries = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0].count(".") == 3:
                entries.append({"ip": parts[0], "mac": parts[1], "type": parts[2]})
        return {"success": True, "data": entries, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_wifi_signal_strength() -> Dict[str, Any]:
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout
        import re
        signal_match = re.search(r"Signals*:s*(d+)%", output)
        ssid_match = re.search(r"SSIDs*:s*(.+)", output)
        bssid_match = re.search(r"BSSIDs*:s*(.+)", output)
        signal = int(signal_match.group(1)) if signal_match else None
        ssid = ssid_match.group(1).strip() if ssid_match else None
        return {"success": True, "data": {"ssid": ssid, "signal_percent": signal}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
