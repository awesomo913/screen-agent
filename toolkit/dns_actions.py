"""
dns_actions.py - Production-grade DNS utilities for screen agent toolkit.
Fully implemented with type hints, robust error handling, and consistent Dict return structures.
"""

import dns.resolver
import socket
import subprocess
import json
import time
import ipaddress
import re
import threading
import platform
import urllib.request
from typing import Dict, Any, List, Optional, Callable, Union

# Standard return envelope
def _result(success: bool, data: Any, error: Optional[str] = None) -> Dict[str, Any]:
    return {"success": success, "data": data, "error": error}

# Common public DNS servers for propagation/latency checks
_PUBLIC_DNS_SERVERS = ["8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1", "9.9.9.9"]


def resolve_hostname(hostname: str, record_type: str) -> Dict[str, Any]:
    """Resolve a hostname for a specific DNS record type."""
    try:
        answers = dns.resolver.resolve(hostname, record_type.upper())
        records = [str(r).rstrip(".") for r in answers]
        return _result(True, records)
    except dns.resolver.NXDOMAIN:
        return _result(False, [], f"Domain '{hostname}' does not exist.")
    except dns.resolver.NoAnswer:
        return _result(False, [], f"No {record_type.upper()} records found for '{hostname}'.")
    except Exception as e:
        return _result(False, [], str(e))


def reverse_dns(ip_address: str) -> Dict[str, Any]:
    """Perform reverse DNS lookup (PTR) for an IP address."""
    try:
        ipaddress.ip_address(ip_address)  # Validate IP format
        answers = dns.resolver.resolve_address(ip_address)
        hostname = str(answers[0]).rstrip(".")
        return _result(True, hostname)
    except ValueError:
        return _result(False, None, "Invalid IP address format.")
    except dns.resolver.NXDOMAIN:
        return _result(False, None, "No reverse DNS record found for this IP.")
    except Exception as e:
        return _result(False, None, str(e))


def get_mx_records(domain: str) -> Dict[str, Any]:
    """Retrieve MX (Mail Exchange) records for a domain."""
    try:
        answers = dns.resolver.resolve(domain, "MX")
        records = [{"priority": r.preference, "host": str(r.exchange).rstrip(".")} for r in answers]
        return _result(True, sorted(records, key=lambda x: x["priority"]))
    except dns.resolver.NoAnswer:
        return _result(False, [], "No MX records found.")
    except Exception as e:
        return _result(False, [], str(e))


def get_ns_records(domain: str) -> Dict[str, Any]:
    """Retrieve NS (Name Server) records for a domain."""
    try:
        answers = dns.resolver.resolve(domain, "NS")
        return _result(True, [str(r).rstrip(".") for r in answers])
    except dns.resolver.NoAnswer:
        return _result(False, [], "No NS records found.")
    except Exception as e:
        return _result(False, [], str(e))


def get_txt_records(domain: str) -> Dict[str, Any]:
    """Retrieve TXT records for a domain."""
    try:
        answers = dns.resolver.resolve(domain, "TXT")
        return _result(True, ["".join(str(s) for s in r.strings) for r in answers])
    except dns.resolver.NoAnswer:
        return _result(False, [], "No TXT records found.")
    except Exception as e:
        return _result(False, [], str(e))


def get_soa_record(domain: str) -> Dict[str, Any]:
    """Retrieve the SOA (Start of Authority) record for a domain."""
    try:
        answers = dns.resolver.resolve(domain, "SOA")
        r = answers[0]
        return _result(True, {
            "mname": str(r.mname).rstrip("."),
            "rname": str(r.rname).rstrip("."),
            "serial": r.serial,
            "refresh": r.refresh,
            "retry": r.retry,
            "expire": r.expire,
            "minimum": r.minimum
        })
    except dns.resolver.NoAnswer:
        return _result(False, {}, "No SOA record found.")
    except Exception as e:
        return _result(False, {}, str(e))


def get_cname_record(domain: str) -> Dict[str, Any]:
    """Retrieve CNAME record(s) for a domain."""
    try:
        answers = dns.resolver.resolve(domain, "CNAME")
        return _result(True, [str(r).rstrip(".") for r in answers])
    except dns.resolver.NoAnswer:
        return _result(False, [], "No CNAME records found.")
    except Exception as e:
        return _result(False, [], str(e))


def get_all_records(domain: str) -> Dict[str, Any]:
    """Retrieve all common DNS record types supported by dnspython."""
    record_types = ["A", "AAAA", "MX", "NS", "TXT", "SOA", "CNAME"]
    results: Dict[str, Any] = {}
    for rtype in record_types:
        res = resolve_hostname(domain, rtype)
        if res["success"]:
            results[rtype] = res["data"]
    return _result(bool(results), results, "No records found for any supported type." if not results else None)


def check_domain_exists(domain: str) -> Dict[str, Any]:
    """Check if a domain exists by querying for A, AAAA, or NS records."""
    for rtype in ["A", "AAAA", "NS"]:
        try:
            dns.resolver.resolve(domain, rtype)
            return _result(True, True)
        except dns.resolver.NoAnswer:
            continue
        except dns.resolver.NXDOMAIN:
            return _result(True, False, "NXDOMAIN: Domain does not exist.")
        except Exception as e:
            return _result(False, None, str(e))
    return _result(True, False, "Domain exists but has no A/AAAA/NS records.")


def get_whois_info(domain: str) -> Dict[str, Any]:
    """Retrieve WHOIS information using system command."""
    try:
        system = platform.system()
        cmd = ["whois", domain]
        # Windows often lacks native whois, fallback/error handled gracefully
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
        if proc.returncode == 0 and proc.stdout.strip():
            return _result(True, proc.stdout.strip())
        else:
            return _result(False, None, f"whois command failed or not installed: {proc.stderr.strip()}")
    except FileNotFoundError:
        return _result(False, None, "WHOIS utility not found in system PATH.")
    except subprocess.TimeoutExpired:
        return _result(False, None, "WHOIS request timed out.")
    except Exception as e:
        return _result(False, None, str(e))


def dns_lookup_batch(domains: List[str], record_type: str) -> Dict[str, Any]:
    """Perform batch DNS resolution for multiple domains."""
    results: Dict[str, Any] = {}
    for domain in domains:
        results[domain] = resolve_hostname(domain, record_type)["data"] if resolve_hostname(domain, record_type)["success"] else resolve_hostname(domain, record_type)["error"]
    return _result(True, results)


def get_dns_servers() -> Dict[str, Any]:
    """Get currently configured DNS servers in the environment."""
    try:
        res = dns.resolver.get_default_resolver()
        servers = [str(ns) for ns in res.nameservers] if hasattr(res, 'nameservers') else []
        if not servers:
            # Fallback to socket fallback
            servers = [ns for ns in dns.resolver.Resolver().nameservers]
        return _result(True, servers)
    except Exception as e:
        return _result(False, [], str(e))


def set_dns_server(server: str) -> Dict[str, Any]:
    """Override the default resolver's nameserver list (session-level)."""
    try:
        socket.inet_aton(server)  # Basic IP validation
        dns.resolver.get_default_resolver().nameservers = [server]
        return _result(True, {"configured_server": server}, "Note: Affects only Python dnspython resolver in this session.")
    except socket.error:
        return _result(False, None, "Invalid IPv4 address format for DNS server.")
    except Exception as e:
        return _result(False, None, str(e))


def flush_dns_cache() -> Dict[str, Any]:
    """Flush OS-level DNS cache based on detected platform."""
    system = platform.system()
    try:
        if system == "Windows":
            cmd = ["ipconfig", "/flushdns"]
        elif system == "Darwin":
            # macOS 10.10+ compatibility layer
            cmd = ["dscacheutil", "-flushcache"]
        else:
            # Linux (systemd-resolved or nscd)
            cmd = ["sudo", "systemd-resolve", "--flush-caches"]
        
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
        if proc.returncode == 0:
            return _result(True, f"DNS cache flushed on {system}.")
        return _result(False, None, f"Cache flush command failed: {proc.stderr.strip()}")
    except FileNotFoundError:
        return _result(False, None, f"Platform-specific cache flush utility not found for {system}.")
    except subprocess.TimeoutExpired:
        return _result(False, None, "Cache flush operation timed out.")
    except Exception as e:
        return _result(False, None, str(e))


def trace_dns(domain: str) -> Dict[str, Any]:
    """Perform DNS trace using system tools (dig/nslookup)."""
    try:
        system = platform.system()
        if system == "Darwin" or (system == "Linux" and subprocess.run(["which", "dig"], capture_output=True).returncode == 0):
            cmd = ["dig", "+trace", domain]
        else:
            cmd = ["nslookup", "-type=SOA", domain]
            
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
        if proc.returncode == 0 and proc.stdout.strip():
            return _result(True, proc.stdout.strip())
        return _result(False, None, f"Trace failed: {proc.stderr.strip()}")
    except FileNotFoundError:
        return _result(False, None, "dig/nslookup not available for tracing.")
    except subprocess.TimeoutExpired:
        return _result(False, None, "DNS trace timed out.")
    except Exception as e:
        return _result(False, None, str(e))


def check_dns_propagation(domain: str, record_type: str, expected: str) -> Dict[str, Any]:
    """Check if a record matches an expected value across multiple public DNS servers."""
    results = {}
    expected_lower = expected.lower()
    for server in _PUBLIC_DNS_SERVERS:
        try:
            res = dns.resolver.Resolver()
            res.nameservers = [server]
            answers = res.resolve(domain, record_type.upper())
            match = any(str(r).rstrip(".").lower() == expected_lower for r in answers)
            results[server] = {"propagated": match, "records": [str(r).rstrip(".") for r in answers]}
        except Exception as e:
            results[server] = {"propagated": False, "records": [], "error": str(e)}
    return _result(True, results)


def get_ptr_record(ip: str) -> Dict[str, Any]:
    """Retrieve PTR record for an IP address (alias to reverse_dns)."""
    return reverse_dns(ip)


def validate_domain(domain: str) -> Dict[str, Any]:
    """Validate domain format against RFC 1123/RFC 1035 standards."""
    if not domain:
        return _result(False, False, "Domain cannot be empty.")
    # Regex: labels separated by dots, 1-63 chars, alphanumeric + hyphens, no leading/trailing hyphens
    pattern = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*$")
    is_valid = bool(pattern.match(domain)) and len(domain) <= 253
    return _result(True, is_valid, "Invalid domain format." if not is_valid else None)


def get_ip_geolocation(ip: str) -> Dict[str, Any]:
    """Fetch IP geolocation data using a public HTTP API."""
    try:
        ipaddress.ip_address(ip)
        url = f"http://ip-api.com/json/{ip}"
        req = urllib.request.Request(url, headers={"User-Agent": "DNSAgentToolkit/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
        if data.get("status") == "success":
            return _result(True, {k: v for k, v in data.items() if k != "status"})
        return _result(False, None, data.get("message", "Geolocation lookup failed."))
    except ValueError:
        return _result(False, None, "Invalid IP address format.")
    except urllib.error.URLError as e:
        return _result(False, None, f"Network error: {e.reason}")
    except Exception as e:
        return _result(False, None, str(e))


def measure_dns_latency(domain: str, server: str) -> Dict[str, Any]:
    """Measure DNS resolution latency in milliseconds."""
    try:
        res = dns.resolver.Resolver()
        res.nameservers = [server]
        res.lifetime = 5.0
        start = time.perf_counter()
        res.resolve(domain, "A")
        latency_ms = (time.perf_counter() - start) * 1000
        return _result(True, {"latency_ms": round(latency_ms, 3), "server": server, "domain": domain})
    except dns.resolver.NXDOMAIN:
        return _result(False, None, "Domain does not exist.")
    except dns.resolver.NoAnswer:
        return _result(False, None, "No answer from server.")
    except Exception as e:
        return _result(False, None, str(e))


def check_dnssec(domain: str) -> Dict[str, Any]:
    """Check if a domain has DNSSEC enabled by querying DNSKEY and RRSIG."""
    try:
        res = dns.resolver.Resolver()
        res.edns = 0  # Enable EDNS0 for DNSSEC support
        res.flags |= dns.flags.DO  # Set DNSSEC OK flag
        
        try:
            dnskey = res.resolve(domain, "DNSKEY")
            rrsig = res.resolve(domain, "RRSIG")
            has_dnssec = bool(dnskey) and bool(rrsig)
            return _result(True, {"enabled": has_dnssec, "dnskey_count": len(list(dnskey))})
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            return _result(True, {"enabled": False, "dnskey_count": 0})
    except Exception as e:
        return _result(False, None, str(e))


def get_spf_record(domain: str) -> Dict[str, Any]:
    """Extract SPF record from domain TXT records."""
    try:
        answers = dns.resolver.resolve(domain, "TXT")
        spf_records = []
        for r in answers:
            txt = "".join(str(s) for s in r.strings)
            if txt.strip().startswith("v=spf1"):
                spf_records.append(txt.strip())
        return _result(True, spf_records or ["No SPF record configured."])
    except dns.resolver.NoAnswer:
        return _result(False, [], "No TXT records found.")
    except Exception as e:
        return _result(False, [], str(e))


def get_dmarc_record(domain: str) -> Dict[str, Any]:
    """Retrieve DMARC record from _dmarc.{domain} TXT."""
    dmarc_domain = f"_dmarc.{domain}"
    try:
        answers = dns.resolver.resolve(dmarc_domain, "TXT")
        records = ["".join(str(s) for s in r.strings).strip() for r in answers]
        return _result(True, records)
    except dns.resolver.NXDOMAIN:
        return _result(False, [], "No DMARC record found.")
    except Exception as e:
        return _result(False, [], str(e))


def monitor_dns_changes(domain: str, interval: float, callback: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
    """Monitor DNS records for changes in a background thread."""
    def _monitor_worker():
        baseline = {}
        while True:
            try:
                current = dns.resolver.resolve(domain, "A")
                current_set = {str(r).rstrip(".") for r in current}
                if baseline and baseline != current_set:
                    change_data = {
                        "domain": domain,
                        "timestamp": time.time(),
                        "previous": list(baseline),
                        "current": list(current_set)
                    }
                    try:
                        callback(change_data)
                    except Exception:
                        pass  # Silently fail callback to keep monitor alive
                baseline = current_set
            except Exception:
                baseline = {}
            time.sleep(interval)

    thread = threading.Thread(target=_monitor_worker, daemon=True, name=f"dns-monitor-{domain}")
    thread.start()
    return _result(True, {
        "monitoring": True,
        "domain": domain,
        "interval_seconds": interval,
        "thread_id": thread.ident
    })


def compare_dns_servers(domain: str, servers: List[str]) -> Dict[str, Any]:
    """Compare resolution results across multiple DNS servers."""
    results = {}
    for server in servers:
        try:
            res = dns.resolver.Resolver()
            res.nameservers = [server]
            res.lifetime = 5.0
            answers = list(res.resolve(domain, "A"))
            results[server] = [str(r).rstrip(".") for r in answers]
        except Exception as e:
            results[server] = str(e)
    return _result(True, results)