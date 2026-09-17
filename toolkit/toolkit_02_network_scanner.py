"""
network_scanner.py - Screen Agent Toolkit Module

Scan local networks, probe ports, ping hosts, resolve DNS, get ARP tables,
and inspect network interfaces. Uses stdlib only (socket, subprocess, ipaddress).
"""
from __future__ import annotations
import concurrent.futures, ipaddress, json, os, re, socket, subprocess, sys, time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

_COMMON_PORTS: Dict[int, str] = {
    21:"FTP",22:"SSH",23:"Telnet",25:"SMTP",53:"DNS",80:"HTTP",110:"POP3",
    135:"RPC",139:"NetBIOS",143:"IMAP",443:"HTTPS",445:"SMB",465:"SMTPS",
    587:"SMTP-TLS",993:"IMAPS",995:"POP3S",1433:"MSSQL",1521:"Oracle",
    3306:"MySQL",3389:"RDP",5432:"PostgreSQL",5900:"VNC",6379:"Redis",
    8080:"HTTP-Alt",8443:"HTTPS-Alt",8888:"Jupyter",9200:"Elasticsearch",27017:"MongoDB"
}

def _ping_once(host: str, timeout: float = 1.0) -> bool:
    flag = "-n" if sys.platform == "win32" else "-c"
    tw = "-w" if sys.platform == "win32" else "-W"
    tv = str(int(timeout*1000)) if sys.platform == "win32" else str(int(timeout))
    try:
        r = subprocess.run(["ping", flag, "1", tw, tv, host], capture_output=True, timeout=timeout+2)
        return r.returncode == 0
    except Exception: return False

def _probe_tcp(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout): return True
    except Exception: return False

def _local_subnet() -> Optional[str]:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8",80))
        ip = s.getsockname()[0]; s.close()
        parts = ip.split("."); parts[3] = "0"; return ".".join(parts) + "/24"
    except Exception: return None

def get_local_ip() -> Dict[str, Any]:
    """Get primary local IP and hostname."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8",80))
        ip = s.getsockname()[0]; s.close()
        return {"success": True, "data": {"ip": ip, "hostname": socket.gethostname()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_all_interfaces() -> Dict[str, Any]:
    """List all network interfaces with IP addresses."""
    try:
        if HAS_PSUTIL:
            ifaces = []
            for name, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        ifaces.append({"name":name,"ip":addr.address,"netmask":addr.netmask,"broadcast":addr.broadcast})
            return {"success": True, "data": ifaces, "error": None}
        out = subprocess.check_output(["ipconfig"], text=True, timeout=10)
        ifaces = []; current: Dict[str,str] = {}
        for line in out.splitlines():
            if "adapter" in line.lower() and ":" in line:
                if current: ifaces.append(current)
                current = {"name": line.split(":")[0].strip()}
            elif "IPv4" in line: current["ip"] = line.split(":")[-1].strip().replace("(Preferred)","").strip()
            elif "Subnet" in line: current["netmask"] = line.split(":")[-1].strip()
        if current: ifaces.append(current)
        return {"success": True, "data": ifaces, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def ping_host(host: str, count: int = 4) -> Dict[str, Any]:
    """Ping a host and return latency statistics."""
    try:
        flag = "-n" if sys.platform == "win32" else "-c"
        r = subprocess.run(["ping", flag, str(count), host], capture_output=True, text=True, timeout=30)
        out = r.stdout + r.stderr; alive = r.returncode == 0
        min_ms = max_ms = avg_ms = None
        m = re.search(r"Minimum = (\d+)ms.*Maximum = (\d+)ms.*Average = (\d+)ms", out)
        if m: min_ms, max_ms, avg_ms = int(m.group(1)), int(m.group(2)), int(m.group(3))
        m2 = re.search(r"rtt min/avg/max.*= ([\d.]+)/([\d.]+)/([\d.]+)", out)
        if m2: min_ms, avg_ms, max_ms = float(m2.group(1)), float(m2.group(2)), float(m2.group(3))
        sent = received = 0
        m3 = re.search(r"Sent = (\d+), Received = (\d+)", out)
        if m3: sent, received = int(m3.group(1)), int(m3.group(2))
        return {"success": True, "data": {"host":host,"alive":alive,"min_ms":min_ms,
                "max_ms":max_ms,"avg_ms":avg_ms,"sent":sent or count,"received":received}, "error": None}
    except subprocess.TimeoutExpired:
        return {"success": True, "data": {"host":host,"alive":False}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def resolve_hostname(hostname: str) -> Dict[str, Any]:
    """Forward DNS lookup: hostname to IP addresses."""
    try:
        infos = socket.getaddrinfo(hostname, None)
        addresses = list({i[4][0] for i in infos})
        return {"success": True, "data": {"hostname": hostname, "addresses": addresses}, "error": None}
    except socket.gaierror as e:
        return {"success": False, "data": None, "error": str(e)}

def reverse_dns(ip: str) -> Dict[str, Any]:
    """Reverse DNS: IP to hostname."""
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return {"success": True, "data": {"ip": ip, "hostname": hostname}, "error": None}
    except Exception:
        return {"success": True, "data": {"ip": ip, "hostname": None}, "error": None}

def scan_port(host: str, port: int, timeout: float = 1.0) -> Dict[str, Any]:
    """Check if a single TCP port is open."""
    try:
        is_open = _probe_tcp(host, port, timeout)
        return {"success": True, "data": {"host":host,"port":port,"open":is_open,
                "service":_COMMON_PORTS.get(port,"unknown")}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def scan_common_ports(host: str, timeout: float = 0.5) -> Dict[str, Any]:
    """Scan all well-known common ports on a host."""
    try:
        open_ports = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
            futs = {ex.submit(_probe_tcp, host, p, timeout): (p, s) for p, s in _COMMON_PORTS.items()}
            for fut, (p, s) in futs.items():
                if fut.result(): open_ports.append({"port":p,"service":s})
        open_ports.sort(key=lambda x: x["port"])
        return {"success": True, "data": {"host":host,"open_ports":open_ports}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def scan_port_range(host: str, start_port: int, end_port: int, timeout: float = 0.3) -> Dict[str, Any]:
    """Scan a range of TCP ports on a host (max 5000 ports)."""
    try:
        if end_port - start_port > 5000:
            return {"success": False, "data": None, "error": "Range too large (max 5000)"}
        open_ports = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as ex:
            futs = {ex.submit(_probe_tcp, host, p, timeout): p for p in range(start_port, end_port+1)}
            for fut, p in futs.items():
                if fut.result(): open_ports.append({"port":p,"service":_COMMON_PORTS.get(p,"unknown")})
        open_ports.sort(key=lambda x: x["port"])
        return {"success": True, "data": {"host":host,"open_ports":open_ports}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def scan_subnet(subnet: str = "auto", timeout: float = 0.5) -> Dict[str, Any]:
    """Ping-scan all hosts in a subnet to find live hosts."""
    try:
        if subnet == "auto":
            subnet = _local_subnet()
            if not subnet: return {"success": False, "data": None, "error": "Cannot detect subnet"}
        net = ipaddress.ip_network(subnet, strict=False)
        if net.num_addresses > 1024:
            return {"success": False, "data": None, "error": "Subnet too large (max /22)"}
        hosts = [str(h) for h in net.hosts()]; live = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as ex:
            futs = {ex.submit(_ping_once, h, timeout): h for h in hosts}
            for fut, h in futs.items():
                if fut.result(): live.append(h)
        live.sort(key=lambda ip: tuple(int(x) for x in ip.split(".")))
        return {"success": True, "data": {"subnet":subnet,"live_hosts":live,"count":len(live)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_arp_table() -> Dict[str, Any]:
    """Read the ARP cache table (IP to MAC mappings)."""
    try:
        out = subprocess.check_output(["arp", "-a"], text=True, timeout=10)
        entries = []
        for line in out.splitlines():
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f-:]{11,17})\s+(\w+)", line, re.I)
            if m: entries.append({"ip":m.group(1),"mac":m.group(2),"type":m.group(3)})
        return {"success": True, "data": entries, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_open_connections() -> Dict[str, Any]:
    """List all active TCP/UDP connections on this machine."""
    try:
        if HAS_PSUTIL:
            conns = []
            for c in psutil.net_connections(kind="all"):
                laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else ""
                raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else ""
                try: pname = psutil.Process(c.pid).name() if c.pid else ""
                except Exception: pname = ""
                conns.append({"protocol":c.type.name if hasattr(c.type,"name") else str(c.type),
                               "local":laddr,"remote":raddr,"status":c.status,"pid":c.pid,"process":pname})
            return {"success": True, "data": conns, "error": None}
        out = subprocess.check_output(["netstat", "-ano"], text=True, timeout=15)
        conns = []
        for line in out.splitlines()[4:]:
            parts = line.split(); 
            if len(parts) >= 4:
                conns.append({"protocol":parts[0],"local":parts[1],"remote":parts[2],
                               "status":parts[3] if len(parts)>3 else "","pid":parts[-1]})
        return {"success": True, "data": conns, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_network_stats() -> Dict[str, Any]:
    """Get network I/O statistics (bytes sent/received per interface)."""
    try:
        if HAS_PSUTIL:
            stats = psutil.net_io_counters(pernic=True)
            return {"success": True, "data": {
                iface: {"bytes_sent":s.bytes_sent,"bytes_recv":s.bytes_recv,
                        "packets_sent":s.packets_sent,"packets_recv":s.packets_recv,
                        "errin":s.errin,"errout":s.errout,"dropin":s.dropin,"dropout":s.dropout}
                for iface, s in stats.items()}, "error": None}
        return {"success": False, "data": None, "error": "psutil not available"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def traceroute(host: str, max_hops: int = 20) -> Dict[str, Any]:
    """Run a traceroute to a host."""
    try:
        cmd = ["tracert", "-h", str(max_hops), host] if sys.platform=="win32" else ["traceroute", "-m", str(max_hops), host]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        hops = []
        for line in r.stdout.splitlines():
            m = re.search(r"\s*(\d+)\s+(?:([\d.]+ ms)\s+)*([\d.]+\.[\d.]+\.[\d.]+|\*)", line)
            if m: hops.append({"hop":int(m.group(1)),"address":m.group(3)})
        return {"success": True, "data": {"host":host,"hops":hops}, "error": None}
    except subprocess.TimeoutExpired:
        return {"success": False, "data": None, "error": "Traceroute timed out"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_internet_connectivity(test_hosts: Optional[List[str]] = None) -> Dict[str, Any]:
    """Check if internet is reachable by trying to connect to known hosts."""
    try:
        if test_hosts is None:
            test_hosts = ["8.8.8.8", "1.1.1.1", "208.67.222.222"]
        results = []
        for host in test_hosts:
            try:
                start = time.time()
                with socket.create_connection((host, 53), timeout=3): pass
                latency = round((time.time()-start)*1000, 1)
                results.append({"host":host,"reachable":True,"latency_ms":latency})
            except Exception:
                results.append({"host":host,"reachable":False,"latency_ms":None})
        reachable = any(r["reachable"] for r in results)
        return {"success": True, "data": {"internet_available":reachable,"checks":results}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_public_ip() -> Dict[str, Any]:
    """Get the public/external IP address via DNS query to OpenDNS."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3)
        s.sendto(b"\x00\x00\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
                 b"\x04myip\x07opendns\x03com\x00\x00\x01\x00\x01",
                 ("208.67.222.222", 53))
        data, _ = s.recvfrom(512); s.close()
        if len(data) > 16:
            ip_bytes = data[-4:]
            ip = ".".join(str(b) for b in ip_bytes)
            return {"success": True, "data": {"public_ip": ip}, "error": None}
        return {"success": False, "data": None, "error": "Could not parse response"}
    except Exception:
        try:
            import urllib.request
            with urllib.request.urlopen("https://api.ipify.org", timeout=5) as r:
                ip = r.read().decode().strip()
            return {"success": True, "data": {"public_ip": ip}, "error": None}
        except Exception as e2:
            return {"success": False, "data": None, "error": str(e2)}

def get_wifi_info() -> Dict[str, Any]:
    """Get current WiFi connection details (Windows netsh)."""
    try:
        out = subprocess.check_output(["netsh","wlan","show","interfaces"], text=True, timeout=10)
        info: Dict[str,str] = {}
        for line in out.splitlines():
            if ":" in line:
                k, _, v = line.partition(":"); info[k.strip()] = v.strip()
        return {"success": True, "data": info, "error": None}
    except FileNotFoundError:
        return {"success": False, "data": None, "error": "netsh not available (not Windows or WiFi)"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_wifi_networks() -> Dict[str, Any]:
    """List available WiFi networks (Windows netsh)."""
    try:
        out = subprocess.check_output(["netsh","wlan","show","networks","mode=bssid"],
                                       text=True, timeout=15)
        networks = []; current: Dict[str,str] = {}
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("SSID") and "BSSID" not in line:
                if current: networks.append(current)
                current = {"ssid": line.split(":")[-1].strip()}
            elif "Authentication" in line: current["auth"] = line.split(":")[-1].strip()
            elif "Signal" in line: current["signal"] = line.split(":")[-1].strip()
            elif "Radio type" in line: current["radio"] = line.split(":")[-1].strip()
        if current: networks.append(current)
        return {"success": True, "data": networks, "error": None}
    except FileNotFoundError:
        return {"success": False, "data": None, "error": "netsh not available"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def flush_dns_cache() -> Dict[str, Any]:
    """Flush the Windows DNS resolver cache."""
    try:
        r = subprocess.run(["ipconfig","/flushdns"], capture_output=True, text=True, timeout=10)
        return {"success": r.returncode==0, "data": {"output":r.stdout.strip()}, "error": r.stderr.strip() or None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
