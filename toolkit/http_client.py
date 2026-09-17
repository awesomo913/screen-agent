import ssl
import json
import time
import os
import asyncio
import hashlib
import urllib3
import requests
import aiohttp
import http.cookiejar
from typing import Dict, Any, Optional, List, Callable

# Global configuration & state
_SSL_CONTEXT = ssl.create_default_context()
_COOKIE_JAR = http.cookiejar.CookieJar()
_PROXY_CONFIG: Dict[str, str] = {}
_RATE_LIMIT_TRACKER: Dict[str, float] = {}

def _build_response(success: bool, status_code: int = 0, data: Any = None, headers: Optional[Dict[str, str]] = None, error: Optional[str] = None) -> Dict[str, Any]:
    """Standardized response formatter."""
    return {
        "success": success,
        "status_code": status_code,
        "data": data,
        "headers": headers or {},
        "error": error
    }

def _parse_json_safely(resp_text: str, content_type: str = "") -> Any:
    """Safely parse response text as JSON if applicable."""
    if "application/json" in content_type.lower():
        try:
            return json.loads(resp_text)
        except json.JSONDecodeError:
            pass
    return resp_text

# ==============================================================================
# CORE HTTP METHODS
# ==============================================================================

def get_request(url: str, headers: dict = None, params: dict = None, timeout: int = 30) -> Dict:
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=timeout, verify=True)
        resp.raise_for_status()
        return _build_response(True, resp.status_code, _parse_json_safely(resp.text, resp.headers.get("Content-Type", "")), dict(resp.headers))
    except Exception as e:
        return _build_response(False, error=str(e))

def post_request(url: str, data: dict = None, json_data: dict = None, headers: dict = None) -> Dict:
    try:
        resp = requests.post(url, headers=headers, data=data, json=json_data, timeout=30, verify=True)
        resp.raise_for_status()
        return _build_response(True, resp.status_code, _parse_json_safely(resp.text, resp.headers.get("Content-Type", "")), dict(resp.headers))
    except Exception as e:
        return _build_response(False, error=str(e))

def put_request(url: str, data: dict = None, headers: dict = None) -> Dict:
    try:
        resp = requests.put(url, headers=headers, data=data, timeout=30, verify=True)
        resp.raise_for_status()
        return _build_response(True, resp.status_code, _parse_json_safely(resp.text, resp.headers.get("Content-Type", "")), dict(resp.headers))
    except Exception as e:
        return _build_response(False, error=str(e))

def delete_request(url: str, headers: dict = None) -> Dict:
    try:
        resp = requests.delete(url, headers=headers, timeout=30, verify=True)
        resp.raise_for_status()
        return _build_response(True, resp.status_code, _parse_json_safely(resp.text, resp.headers.get("Content-Type", "")), dict(resp.headers))
    except Exception as e:
        return _build_response(False, error=str(e))

def patch_request(url: str, data: dict = None, headers: dict = None) -> Dict:
    try:
        resp = requests.patch(url, headers=headers, data=data, timeout=30, verify=True)
        resp.raise_for_status()
        return _build_response(True, resp.status_code, _parse_json_safely(resp.text, resp.headers.get("Content-Type", "")), dict(resp.headers))
    except Exception as e:
        return _build_response(False, error=str(e))

def head_request(url: str, headers: dict = None) -> Dict:
    try:
        resp = requests.head(url, headers=headers, timeout=30, allow_redirects=True, verify=True)
        resp.raise_for_status()
        return _build_response(True, resp.status_code, None, dict(resp.headers))
    except Exception as e:
        return _build_response(False, error=str(e))

# ==============================================================================
# FILE & STREAMING OPERATIONS
# ==============================================================================

def download_file(url: str, output_path: str, chunk_size: int = 8192) -> Dict:
    try:
        with requests.get(url, stream=True, timeout=60, verify=True) as resp:
            resp.raise_for_status()
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
            return _build_response(True, resp.status_code, {"saved_path": output_path}, dict(resp.headers))
    except Exception as e:
        if os.path.exists(output_path):
            os.remove(output_path)
        return _build_response(False, error=str(e))

def upload_file(url: str, file_path: str, field_name: str = "file") -> Dict:
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(file_path, "rb") as f:
            files = {field_name: (os.path.basename(file_path), f)}
            resp = requests.post(url, files=files, timeout=60, verify=True)
            resp.raise_for_status()
            return _build_response(True, resp.status_code, _parse_json_safely(resp.text, resp.headers.get("Content-Type", "")), dict(resp.headers))
    except Exception as e:
        return _build_response(False, error=str(e))

# ==============================================================================
# SESSION & STATE MANAGEMENT
# ==============================================================================

def session_request(method: str, url: str, session_cookies: dict = None) -> Dict:
    try:
        sess = requests.Session()
        sess.verify = True
        sess.headers.update({"User-Agent": "ScreenAgentToolkit/1.0"})
        
        if session_cookies:
            sess.cookies.update(session_cookies)
            
        req = requests.Request(method.upper(), url)
        prepped = sess.prepare_request(req)
        resp = sess.send(prepped, timeout=30)
        resp.raise_for_status()
        
        # Update global cookie jar
        for cookie in sess.cookies:
            _COOKIE_JAR.set_cookie(cookie)
            
        return _build_response(True, resp.status_code, _parse_json_safely(resp.text, resp.headers.get("Content-Type", "")), dict(resp.headers))
    except Exception as e:
        return _build_response(False, error=str(e))

def set_proxy(proxy_url: str, proxy_type: str = "http") -> Dict:
    global _PROXY_CONFIG
    try:
        proxy_type = proxy_type.lower()
        if proxy_type not in ("http", "https", "socks5", "socks4"):
            raise ValueError(f"Unsupported proxy type: {proxy_type}")
        _PROXY_CONFIG[proxy_type] = proxy_url
        return _build_response(True, data={"active_proxies": _PROXY_CONFIG})
    except Exception as e:
        return _build_response(False, error=str(e))

# ==============================================================================
# RETRY & RESILIENCE
# ==============================================================================

def get_with_retry(url: str, max_retries: int = 3, backoff: float = 1.0) -> Dict:
    retry_strategy = urllib3.Retry(
        total=max_retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    mounted_session = requests.Session()
    mounted_session.mount("http://", requests.adapters.HTTPAdapter(max_retries=retry_strategy))
    mounted_session.mount("https://", requests.adapters.HTTPAdapter(max_retries=retry_strategy))
    
    try:
        resp = mounted_session.get(url, timeout=30, verify=True)
        resp.raise_for_status()
        return _build_response(True, resp.status_code, _parse_json_safely(resp.text, resp.headers.get("Content-Type", "")), dict(resp.headers))
    except requests.exceptions.Retry as e:
        return _build_response(False, error=f"Max retries exceeded: {str(e)}")
    except Exception as e:
        return _build_response(False, error=str(e))

# ==============================================================================
# JSON & FORM HELPERS
# ==============================================================================

def post_json(url: str, payload: dict, headers: dict = None) -> Dict:
    try:
        req_headers = headers or {}
        req_headers["Content-Type"] = "application/json"
        resp = requests.post(url, json=payload, headers=req_headers, timeout=30, verify=True)
        resp.raise_for_status()
        return _build_response(True, resp.status_code, _parse_json_safely(resp.text, resp.headers.get("Content-Type", "")), dict(resp.headers))
    except Exception as e:
        return _build_response(False, error=str(e))

def get_json(url: str, headers: dict = None) -> Dict:
    try:
        req_headers = headers or {}
        req_headers["Accept"] = "application/json"
        resp = requests.get(url, headers=req_headers, timeout=30, verify=True)
        resp.raise_for_status()
        return _build_response(True, resp.status_code, _parse_json_safely(resp.text, resp.headers.get("Content-Type", "")), dict(resp.headers))
    except Exception as e:
        return _build_response(False, error=str(e))

def submit_form(url: str, form_data: dict, method: str = "POST") -> Dict:
    try:
        if method.upper() == "POST":
            resp = requests.post(url, data=form_data, timeout=30, verify=True)
        elif method.upper() == "PUT":
            resp = requests.put(url, data=form_data, timeout=30, verify=True)
        elif method.upper() == "PATCH":
            resp = requests.patch(url, data=form_data, timeout=30, verify=True)
        else:
            return _build_response(False, error=f"Unsupported form method: {method}")
        resp.raise_for_status()
        return _build_response(True, resp.status_code, _parse_json_safely(resp.text, resp.headers.get("Content-Type", "")), dict(resp.headers))
    except Exception as e:
        return _build_response(False, error=str(e))

# ==============================================================================
# INSPECTION & UTILITY
# ==============================================================================

def check_url_status(url: str, timeout: int = 10) -> Dict:
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True, verify=True)
        return _build_response(True, resp.status_code, {"url_accessible": True})
    except requests.exceptions.RequestException as e:
        return _build_response(False, error=str(e))
    except Exception as e:
        return _build_response(False, error=str(e))

def get_response_headers(url: str) -> Dict:
    try:
        resp = requests.head(url, timeout=15, allow_redirects=True, verify=True)
        return _build_response(True, resp.status_code, dict(resp.headers))
    except Exception as e:
        return _build_response(False, error=str(e))

def get_cookies(url: str) -> Dict:
    try:
        # Fetch cookies from URL using http.cookiejar integration
        cookie_handler = http.cookiejar.CookieJar()
        opener = urllib3.util.url.parse_url(url) # Simplified, using requests for actual fetch
        resp = requests.get(url, timeout=15)
        for cookie in resp.cookies:
            _COOKIE_JAR.set_cookie(http.cookiejar.Cookie(
                version=0, name=cookie.name, value=cookie.value, port=None, port_specified=False,
                domain=cookie.domain, domain_specified=True, domain_initial_dot=False, path=cookie.path,
                path_specified=True, secure=cookie.secure, expires=cookie.expires, discard=False, comment=None,
                comment_url=None, rest={'HttpOnly': None}, rfc2109=False
            ))
        return _build_response(True, data={c.name: c.value for c in _COOKIE_JAR})
    except Exception as e:
        return _build_response(False, error=str(e))

def set_cookies(url: str, cookies: dict) -> Dict:
    global _COOKIE_JAR
    try:
        for name, value in cookies.items():
            _COOKIE_JAR.set_cookie(http.cookiejar.Cookie(
                version=0, name=name, value=value, port=None, port_specified=False,
                domain="", domain_specified=True, domain_initial_dot=False, path="/",
                path_specified=True, secure=False, expires=None, discard=True, comment=None,
                comment_url=None, rest={}, rfc2109=False
            ))
        return _build_response(True, data={"cookies_set": len(cookies)})
    except Exception as e:
        return _build_response(False, error=str(e))

# ==============================================================================
# AUTHENTICATION
# ==============================================================================

def basic_auth_request(url: str, username: str, password: str) -> Dict:
    try:
        resp = requests.get(url, auth=(username, password), timeout=30, verify=True)
        if resp.status_code == 401:
            return _build_response(False, resp.status_code, error="Authentication failed")
        resp.raise_for_status()
        return _build_response(True, resp.status_code, _parse_json_safely(resp.text, resp.headers.get("Content-Type", "")), dict(resp.headers))
    except Exception as e:
        return _build_response(False, error=str(e))

def bearer_auth_request(url: str, token: str) -> Dict:
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(url, headers=headers, timeout=30, verify=True)
        if resp.status_code == 401:
            return _build_response(False, resp.status_code, error="Invalid or expired token")
        resp.raise_for_status()
        return _build_response(True, resp.status_code, _parse_json_safely(resp.text, resp.headers.get("Content-Type", "")), dict(resp.headers))
    except Exception as e:
        return _build_response(False, error=str(e))

# ==============================================================================
# ADVANCED PROTOCOLS
# ==============================================================================

def graphql_query(url: str, query: str, variables: dict = None) -> Dict:
    try:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=60, verify=True)
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data and data["errors"]:
            return _build_response(False, resp.status_code, data, dict(resp.headers), error=str(data["errors"]))
        return _build_response(True, resp.status_code, data.get("data"), dict(resp.headers))
    except Exception as e:
        return _build_response(False, error=str(e))

def websocket_connect(url: str, on_message: Callable = None) -> Dict:
    async def _ws_task():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(url, ssl=_SSL_CONTEXT) as ws:
                    msg = await asyncio.wait_for(ws.receive(), timeout=10.0)
                    if msg.type == aiohttp.WSMsgType.TEXT and on_message:
                        on_message(msg.data)
                    return {"success": True, "message": msg.data, "type": str(msg.type)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    try:
        result = asyncio.run(_ws_task())
        return _build_response(result.get("success", False), data=result)
    except Exception as e:
        return _build_response(False, error=str(e))

# ==============================================================================
# CONCURRENCY & RATE LIMITING
# ==============================================================================

async def _fetch_batch(semaphore: asyncio.Semaphore, method: str, url: str, headers: dict = None) -> dict:
    async with semaphore:
        try:
            async with aiohttp.ClientSession() as session:
                if method.upper() == "GET":
                    async with session.get(url, headers=headers, ssl=_SSL_CONTEXT) as resp:
                        text = await resp.text()
                        return {"url": url, "status": resp.status, "headers": dict(resp.headers), "data": _parse_json_safely(text, resp.content_type)}
                else:
                    async with session.post(url, headers=headers, ssl=_SSL_CONTEXT) as resp:
                        text = await resp.text()
                        return {"url": url, "status": resp.status, "headers": dict(resp.headers), "data": _parse_json_safely(text, resp.content_type)}
        except Exception as e:
            return {"url": url, "status": 0, "error": str(e)}

def batch_requests(urls: list, method: str = "GET", concurrency: int = 5) -> Dict:
    try:
        semaphore = asyncio.Semaphore(concurrency)
        tasks = [_fetch_batch(semaphore, method, url) for url in urls]
        results = asyncio.run(asyncio.gather(*tasks, return_exceptions=True))
        processed = []
        for r in results:
            if isinstance(r, dict):
                processed.append(r)
            else:
                processed.append({"error": str(r)})
        return _build_response(True, data={"results": processed, "count": len(processed)})
    except Exception as e:
        return _build_response(False, error=str(e))

def rate_limited_request(url: str, requests_per_sec: float = 1.0) -> Dict:
    global _RATE_LIMIT_TRACKER
    try:
        min_interval = 1.0 / requests_per_sec
        now = time.time()
        last_req = _RATE_LIMIT_TRACKER.get(url, 0.0)
        elapsed = now - last_req
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _RATE_LIMIT_TRACKER[url] = time.time()
        
        return get_request(url)
    except Exception as e:
        return _build_response(False, error=str(e))

# ==============================================================================
# CACHING
# ==============================================================================

def cache_response(url: str, cache_dir: str = "/tmp/http_cache", ttl: int = 3600) -> Dict:
    try:
        os.makedirs(cache_dir, exist_ok=True)
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        meta_path = os.path.join(cache_dir, f"{url_hash}.meta")
        cache_path = os.path.join(cache_dir, f"{url_hash}.cache")
        
        if os.path.exists(meta_path) and os.path.exists(cache_path):
            with open(meta_path, "r") as f:
                meta = json.load(f)
            if time.time() - meta.get("timestamp", 0) < ttl:
                with open(cache_path, "r") as f:
                    cached_data = json.load(f)
                return _build_response(True, data=cached_data, headers={"cache_status": "HIT", "path": cache_path})
        
        # Fetch fresh
        resp = requests.get(url, timeout=30, verify=True)
        resp.raise_for_status()
        data = _parse_json_safely(resp.text, resp.headers.get("Content-Type", ""))
        
        # Save cache
        meta = {"url": url, "timestamp": time.time(), "status_code": resp.status_code}
        with open(meta_path, "w") as f:
            json.dump(meta, f)
        with open(cache_path, "w") as f:
            # Ensure serializable
            try:
                json.dump(data, f)
            except TypeError:
                json.dump(str(data), f)
                
        return _build_response(True, resp.status_code, data, dict(resp.headers), error=None)
    except Exception as e:
        return _build_response(False, error=str(e))