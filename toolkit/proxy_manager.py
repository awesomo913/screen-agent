"""
proxy_manager.py
~~~~~~~~~~~~~~~~

A production‑ready toolkit for managing, testing and rotating HTTP/SOCKS proxies.
It provides a rich set of utilities that can be used by screen‑agents,
scrapers or any application that needs reliable proxy handling.

All public functions return a ``Dict`` with a common structure:

    {
        "success": bool,
        "message": str,
        "data": Any   # optional, depends on the function
    }

The module relies only on the standard library plus the following third‑party
packages (all of which are listed in the import section):

* ``requests`` – high‑level HTTP client
* ``urllib3`` – low‑level HTTP client (used for raw connections)
* ``pysocks`` (imported as ``socks``) – SOCKS support
* ``json`` – JSON handling
* ``threading`` – background health monitoring
* ``time`` – timestamps / delays
* ``random`` – random proxy selection
* ``subprocess`` – system‑level proxy configuration (Windows/macOS/Linux)
* ``re`` – regex utilities
"""

# --------------------------------------------------------------------------- #
# Imports
# --------------------------------------------------------------------------- #
from __future__ import annotations

import json
import random
import re
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
import urllib3
import socks  # type: ignore[import]   # pysocks

# --------------------------------------------------------------------------- #
# Helper Types & Constants
# --------------------------------------------------------------------------- #
ProxyDict = Dict[str, Union[str, int, None]]
Result = Dict[str, Any]

_DEFAULT_TIMEOUT = 10  # seconds
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _make_result(
    success: bool,
    message: str,
    data: Optional[Any] = None,
) -> Result:
    """Standardised result dictionary."""
    return {"success": success, "message": message, "data": data}


# --------------------------------------------------------------------------- #
# System proxy helpers (Windows/macOS/Linux)
# --------------------------------------------------------------------------- #
def set_system_proxy(
    host: str,
    port: int,
    protocol: str = "http",
) -> Result:
    """
    Configure the OS level proxy.

    Supported protocols: ``http``, ``https``, ``socks5``.
    Returns a result dict.
    """
    try:
        norm_proto = protocol.lower()
        if norm_proto not in {"http", "https", "socks5"}:
            raise ValueError(f"Unsupported protocol: {protocol}")

        # Windows – use `netsh winhttp set proxy`
        if subprocess.run(["uname"], capture_output=True).returncode != 0:
            # Assume Windows
            cmd = [
                "netsh",
                "winhttp",
                "set",
                "proxy",
                f"{host}:{port}",
            ]
            subprocess.check_call(cmd)
        else:
            # Unix‑like (Linux/macOS)
            env_cmd = f"export {norm_proto.upper()}_PROXY={host}:{port}"
            subprocess.check_call(env_cmd, shell=True, executable="/bin/bash")

        return _make_result(True, "System proxy set successfully")
    except subprocess.CalledProcessError as exc:
        return _make_result(
            False,
            f"Failed to set system proxy: {exc}",
        )
    except Exception as exc:  # pragma: no cover – defensive
        return _make_result(False, f"Unexpected error: {exc}")


def remove_system_proxy() -> Result:
    """Remove any system‑wide proxy configuration."""
    try:
        # Windows
        if subprocess.run(["uname"], capture_output=True).returncode != 0:
            cmd = ["netsh", "winhttp", "reset", "proxy"]
            subprocess.check_call(cmd)
        else:
            # Unix‑like – clear environment variables in current shell
            for var in ("HTTP_PROXY", "HTTPS_PROXY", "SOCKS5_PROXY"):
                subprocess.run(
                    f"unset {var}",
                    shell=True,
                    executable="/bin/bash",
                    check=False,
                )
        return _make_result(True, "System proxy removed")
    except subprocess.CalledProcessError as exc:
        return _make_result(False, f"Failed to remove system proxy: {exc}")
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"Unexpected error: {exc}")


def get_current_proxy() -> Result:
    """Read current system proxy settings (environment variables)."""
    try:
        env_vars = {k: v for k, v in os.environ.items() if k.endswith("_PROXY")}
        if not env_vars:
            return _make_result(True, "No system proxy configured", {})
        return _make_result(True, "System proxy detected", env_vars)
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"Error reading system proxy: {exc}")


# --------------------------------------------------------------------------- #
# Proxy testing utilities
# --------------------------------------------------------------------------- #
def test_proxy(
    host: str,
    port: int,
    protocol: str = "http",
    timeout: int = _DEFAULT_TIMEOUT,
) -> Result:
    """
    Perform a lightweight request (to httpbin.org/ip) to verify that the proxy
    works and is reachable.
    """
    proxy_url = format_proxy_url(host, port, None, None, protocol)["data"]
    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        resp = requests.get(
            "https://httpbin.org/ip",
            proxies=proxies,
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT},
        )
        resp.raise_for_status()
        ip_info = resp.json()
        return _make_result(
            True,
            "Proxy is functional",
            {"ip": ip_info.get("origin"), "status_code": resp.status_code},
        )
    except requests.RequestException as exc:
        return _make_result(False, f"Proxy test failed: {exc}")


def test_proxy_speed(proxy_url: str, test_url: str = "https://www.google.com") -> Result:
    """
    Measure latency (in seconds) of a single request through the proxy.
    """
    proxies = {"http": proxy_url, "https": proxy_url}
    start = time.time()
    try:
        resp = requests.get(
            test_url,
            proxies=proxies,
            timeout=_DEFAULT_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
        )
        resp.raise_for_status()
        elapsed = time.time() - start
        return _make_result(
            True,
            "Speed test succeeded",
            {"latency": elapsed, "status_code": resp.status_code},
        )
    except requests.RequestException as exc:
        return _make_result(False, f"Speed test failed: {exc}")


def batch_test_proxies(
    proxies: List[ProxyDict],
    concurrent: int = 10,
) -> Result:
    """
    Test a list of proxies concurrently using threads.
    Returns a dict with ``working`` and ``failed`` lists.
    """
    working: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    def worker(p: ProxyDict) -> None:
        res = test_proxy(
            p["host"], int(p["port"]), p.get("protocol", "http")
        )
        if res["success"]:
            working.append({**p, "latency": res["data"]["latency"]})
        else:
            failed.append({**p, "error": res["message"]})

    threads = []
    for proxy in proxies:
        t = threading.Thread(target=worker, args=(proxy,))
        t.start()
        threads.append(t)
        if len(threads) >= concurrent:
            for th in threads:
                th.join()
            threads.clear()

    # Join any remaining threads
    for th in threads:
        th.join()

    return _make_result(
        True,
        "Batch test completed",
        {"working": working, "failed": failed},
    )


# --------------------------------------------------------------------------- #
# Proxy pool & rotation
# --------------------------------------------------------------------------- #
class ProxyPool:
    """
    Simple thread‑safe pool that holds a list of proxy dictionaries.
    """

    def __init__(self, proxies: Optional[List[ProxyDict]] = None):
        self._lock = threading.Lock()
        self._proxies: List[ProxyDict] = proxies or []
        self._index = 0

    def add(self, proxy: ProxyDict) -> None:
        with self._lock:
            self._proxies.append(proxy)

    def rotate(self) -> Result:
        """Move to the next proxy in the pool."""
        with self._lock:
            if not self._proxies:
                return _make_result(False, "Proxy pool is empty")
            self._index = (self._index + 1) % len(self._proxies)
            return _make_result(True, "Rotated to next proxy")

    def get_next(self) -> Result:
        """Return the current proxy and then rotate."""
        with self._lock:
            if not self._proxies:
                return _make_result(False, "Proxy pool is empty")
            proxy = self._proxies[self._index]
            # rotate for next call
            self._index = (self._index + 1) % len(self._proxies)
            return _make_result(True, "Returned next proxy", proxy)

    def stats(self) -> Result:
        with self._lock:
            return _make_result(
                True,
                "Pool statistics",
                {"total": len(self._proxies), "current_index": self._index},
            )

    def list_all(self) -> Result:
        with self._lock:
            return _make_result(True, "All proxies in pool", list(self._proxies))


def rotate_proxy(proxy_list: List[ProxyDict]) -> Result:
    """Return the list rotated by one position (first element becomes last)."""
    if not proxy_list:
        return _make_result(False, "Empty proxy list")
    rotated = proxy_list[1:] + proxy_list[:1]
    return _make_result(True, "List rotated", rotated)


def create_proxy_pool(proxies: List[ProxyDict]) -> Result:
    """Instantiate a ``ProxyPool`` and return its public representation."""
    pool = ProxyPool(proxies)
    return _make_result(True, "Proxy pool created", {"pool": pool})


def get_next_proxy(pool: ProxyPool) -> Result:
    """Convenient wrapper around ``ProxyPool.get_next``."""
    return pool.get_next()


# --------------------------------------------------------------------------- #
# Proxy validation & filtering
# --------------------------------------------------------------------------- #
def validate_proxy_list(proxies: List[ProxyDict]) -> Result:
    """
    Verify that each entry contains the required keys:
    ``host`` (str) and ``port`` (int). Optional: ``protocol``.
    """
    invalid: List[Dict[str, Any]] = []
    for p in proxies:
        if not isinstance(p.get("host"), str) or not isinstance(p.get("port"), int):
            invalid.append(p)
    if invalid:
        return _make_result(False, "Invalid entries found", {"invalid": invalid})
    return _make_result(True, "All proxies are valid")


def filter_working_proxies(
    proxies: List[ProxyDict],
    timeout: int = _DEFAULT_TIMEOUT,
) -> Result:
    """
    Return only proxies that pass ``test_proxy`` within the given timeout.
    """
    working = []
    for p in proxies:
        result = test_proxy(p["host"], p["port"], p.get("protocol", "http"), timeout)
        if result["success"]:
            working.append(p)
    return _make_result(True, "Filtered working proxies", working)


# --------------------------------------------------------------------------- #
# SOCKS utilities
# --------------------------------------------------------------------------- #
def set_socks_proxy(
    host: str,
    port: int,
    version: int = 5,
) -> Result:
    """
    Configure a SOCKS proxy for urllib3 / requests by monkey‑patching the
    default socket.
    """
    try:
        if version not in {4, 5}:
            raise ValueError("SOCKS version must be 4 or 5")

        socks.set_default_proxy(socks.SOCKS5 if version == 5 else socks.SOCKS4, host, port)
        socket.socket = socks.socksocket  # type: ignore
        return _make_result(True, f"SOCKS{version} proxy set")
    except Exception as exc:
        return _make_result(False, f"Failed to set SOCKS proxy: {exc}")


def create_proxy_chain(proxies: List[ProxyDict]) -> Result:
    """
    Build a chain of proxies where each request goes through the whole list.
    This is a *conceptual* helper – actual chaining would require a tunnel
    implementation which is beyond the scope of this module.
    """
    if not proxies:
        return _make_result(False, "Empty proxy list")
    chain = " -> ".join(
        f"{p.get('protocol', 'http')}://{p['host']}:{p['port']}"
        for p in proxies
    )
    return _make_result(True, "Proxy chain description created", {"chain": chain})


# --------------------------------------------------------------------------- #
# Miscellaneous helpers
# --------------------------------------------------------------------------- #
def parse_proxy_string(proxy_str: str) -> Result:
    """
    Accepted formats:
        * ``scheme://host:port``
        * ``host:port``
        * ``user:password@host:port``
    Returns a normalized dict.
    """
    pattern = re.compile(
        r"""(?:(?P<scheme>\w+)://)?               # optional scheme
            (?:(?P<user>[^:@]+):(?P<password>[^:@]+)@)? # optional auth
            (?P<host>[^:]+):(?P<port>\d+)           # host and port
        """,
        re.VERBOSE,
    )
    match = pattern.fullmatch(proxy_str.strip())
    if not match:
        return _make_result(False, "Unable to parse proxy string")
    groups = match.groupdict()
    return _make_result(
        True,
        "Parsed proxy string",
        {
            "scheme": groups.get("scheme") or "http",
            "user": groups.get("user"),
            "password": groups.get("password"),
            "host": groups["host"],
            "port": int(groups["port"]),
        },
    )


def format_proxy_url(
    host: str,
    port: int,
    user: Optional[str] = None,
    password: Optional[str] = None,
    protocol: str = "http",
) -> Result:
    """
    Return a fully‑qualified proxy URL, e.g.
    ``http://user:pass@host:port``.
    """
    if protocol.lower() not in {"http", "https", "socks5", "socks4"}:
        return _make_result(False, f"Unsupported protocol: {protocol}")
    auth = ""
    if user and password:
        auth = f"{user}:{password}@"
    url = f"{protocol.lower()}://{auth}{host}:{port}"
    return _make_result(True, "Formatted proxy URL", url)


def get_public_ip(proxy: Optional[ProxyDict] = None) -> Result:
    """
    Query ``https://api.ipify.org?format=json`` either directly or via a proxy.
    """
    proxies = None
    if proxy:
        proxy_url = format_proxy_url(
            proxy["host"],
            proxy["port"],
            proxy.get("user"),
            proxy.get("password"),
            proxy.get("protocol", "http"),
        )["data"]
        proxies = {"http": proxy_url, "https": proxy_url}
    try:
        resp = requests.get(
            "https://api.ipify.org?format=json",
            proxies=proxies,
            timeout=_DEFAULT_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
        )
        resp.raise_for_status()
        ip = resp.json()["ip"]
        return _make_result(True, "Public IP retrieved", ip)
    except requests.RequestException as exc:
        return _make_result(False, f"Failed to obtain public IP: {exc}")


def check_proxy_anonymity(proxy: ProxyDict) -> Result:
    """
    Determine anonymity level (transparent, anonymous, elite) by comparing
    the public IP with the proxy IP.
    """
    ip_direct = get_public_ip()
    ip_via_proxy = get_public_ip(proxy)

    if not ip_direct["success"] or not ip_via_proxy["success"]:
        return _make_result(
            False,
            "Could not determine anonymity (failed IP checks)",
        )

    direct_ip = ip_direct["data"]
    proxy_ip = ip_via_proxy["data"]

    if direct_ip == proxy_ip:
        level = "transparent"
    else:
        # Simple heuristic: if the proxy adds `Via` or `X-Forwarded-For`
        # we treat it as anonymous; otherwise elite.
        test_url = "https://httpbin.org/headers"
        proxy_url = format_proxy_url(
            proxy["host"],
            proxy["port"],
            proxy.get("user"),
            proxy.get("password"),
            proxy.get("protocol", "http"),
        )["data"]
        try:
            r = requests.get(
                test_url,
                proxies={"http": proxy_url, "https": proxy_url},
                timeout=_DEFAULT_TIMEOUT,
                headers={"User-Agent": _USER_AGENT},
            )
            r.raise_for_status()
            headers = r.json()["headers"]
            if any(k.lower() in {"via", "x-forwarded-for"} for k in headers):
                level = "anonymous"
            else:
                level = "elite"
        except Exception:
            level = "unknown"

    return _make_result(True, "Anonymity level detected", {"level": level})


def get_geo_location(proxy: ProxyDict) -> Result:
    """
    Use ``ip-api.com`` to fetch geographical information for the proxy IP.
    """
    ip_res = get_public_ip(proxy)
    if not ip_res["success"]:
        return _make_result(False, "Cannot get IP for geo lookup")

    ip = ip_res["data"]
    try:
        resp = requests.get(
            f"http://ip-api.com/json/{ip}",
            timeout=_DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if data["status"] != "success":
            raise ValueError(data.get("message", "Unknown error"))
        return _make_result(True, "Geo location retrieved", data)
    except Exception as exc:
        return _make_result(False, f"Geo lookup failed: {exc}")


# --------------------------------------------------------------------------- #
# File I/O
# --------------------------------------------------------------------------- #
def load_proxies_from_file(filepath: Union[str, Path]) -> Result:
    """
    Load a JSON file containing a list of proxy dicts.
    Expected format:
        [
            {"host": "...", "port": 1234, "protocol": "..."},
            ...
        ]
    """
    path = Path(filepath)
    if not path.is_file():
        return _make_result(False, f"File not found: {filepath}")

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("JSON root must be a list")
        return _make_result(True, "Proxies loaded", data)
    except Exception as exc:
        return _make_result(False, f"Failed to load proxies: {exc}")


def save_proxies_to_file(proxies: List[ProxyDict], filepath: Union[str, Path]) -> Result:
    """
    Persist a list of proxy dictionaries as pretty‑printed JSON.
    """
    path = Path(filepath)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(proxies, f, indent=4, sort_keys=True)
        return _make_result(True, f"Proxies saved to {filepath}")
    except Exception as exc:
        return _make_result(False, f"Failed to save proxies: {exc}")


# --------------------------------------------------------------------------- #
# Health monitoring
# --------------------------------------------------------------------------- #
def monitor_proxy_health(
    proxies: List[ProxyDict],
    interval: int = 60,
) -> Result:
    """
    Launch a background thread that periodically checks each proxy.
    The function returns immediately with a handle to the thread.
    """

    stop_flag = threading.Event()

    def worker() -> None:
        while not stop_flag.is_set():
            for p in proxies:
                test_proxy(p["host"], p["port"], p.get("protocol", "http"))
            stop_flag.wait(interval)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return _make_result(
        True,
        "Health monitor started",
        {"thread": thread, "stop_event": stop_flag},
    )


def get_proxy_stats(pool: ProxyPool) -> Result:
    """Wrapper around ``ProxyPool.stats``."""
    return pool.stats()


# --------------------------------------------------------------------------- #
# Browser integration (selenium compatible)
# --------------------------------------------------------------------------- #
def set_browser_proxy(
    browser: Any,
    proxy_config: Dict[str, Any],
) -> Result:
    """
    Apply proxy settings to a Selenium ``webdriver`` instance.
    The caller must supply the correct driver type (Chrome, Firefox, Edge).
    """
    try:
        # Chrome example
        if getattr(browser, "capabilities", {}).get("browserName") == "chrome":
            options = browser.options
            proxy = proxy_config.get("proxy")
            if not proxy:
                raise ValueError("Missing 'proxy' key in config")
            options.add_argument(f'--proxy-server={proxy}')
            return _make_result(True, "Chrome proxy configured")
        # Firefox example
        elif getattr(browser, "capabilities", {}).get("browserName") == "firefox":
            profile = browser.profile
            proxy = proxy_config.get("proxy")
            if not proxy:
                raise ValueError("Missing 'proxy' key in config")
            host, port = proxy.split(":")
            profile.set_preference("network.proxy.type", 1)
            profile.set_preference("network.proxy.http", host)
            profile.set_preference("network.proxy.http_port", int(port))
            profile.update_preferences()
            return _make_result(True, "Firefox proxy configured")
        else:
            return _make_result(False, "Unsupported browser type")
    except Exception as exc:
        return _make_result(False, f"Failed to set browser proxy: {exc}")


# --------------------------------------------------------------------------- #
# Authenticated proxy creation
# --------------------------------------------------------------------------- #
def create_authenticated_proxy(
    host: str,
    port: int,
    user: str,
    password: str,
) -> Result:
    """
    Return a dict suitable for the other helpers that includes authentication.
    """
    return _make_result(
        True,
        "Authenticated proxy dict created",
        {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "protocol": "http",
        },
    )


# --------------------------------------------------------------------------- #
# Generic request helper
# --------------------------------------------------------------------------- #
def proxy_request(
    url: str,
    proxy: ProxyDict,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
) -> Result:
    """
    Perform an HTTP request through a given proxy.
    Supports GET, POST, PUT, DELETE.
    """
    proxy_url = format_proxy_url(
        proxy["host"],
        proxy["port"],
        proxy.get("user"),
        proxy.get("password"),
        proxy.get("protocol", "http"),
    )["data"]
    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        resp = requests.request(
            method.upper(),
            url,
            json=data,
            proxies=proxies,
            timeout=_DEFAULT_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
        )
        resp.raise_for_status()
        # Try to decode JSON, fall back to text
        try:
            payload = resp.json()
        except ValueError:
            payload = resp.text
        return _make_result(
            True,
            f"{method.upper()} request successful",
            {"status_code": resp.status_code, "response": payload},
        )
    except requests.RequestException as exc:
        return _make_result(False, f"Request failed: {exc}")


# --------------------------------------------------------------------------- #
# Public API (what gets exported when ``from proxy_manager import *``)
# --------------------------------------------------------------------------- #
__all__ = [
    # system
    "set_system_proxy",
    "remove_system_proxy",
    "get_current_proxy",
    # testing
    "test_proxy",
    "test_proxy_speed",
    "batch_test_proxies",
    # pool & rotation
    "ProxyPool",
    "rotate_proxy",
    "create_proxy_pool",
    "get_next_proxy",
    # validation
    "validate_proxy_list",
    "filter_working_proxies",
    # socks
    "set_socks_proxy",
    "create_proxy_chain",
    # misc
    "parse_proxy_string",
    "format_proxy_url",
    "get_public_ip",
    "check_proxy_anonymity",
    "get_geo_location",
    # file IO
    "load_proxies_from_file",
    "save_proxies_to_file",
    # health monitoring
    "monitor_proxy_health",
    "get_proxy_stats",
    # browser integration
    "set_browser_proxy",
    # auth
    "create_authenticated_proxy",
    # request helper
    "proxy_request",
]