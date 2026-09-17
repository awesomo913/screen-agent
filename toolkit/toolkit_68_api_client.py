"""
toolkit_68_api_client.py
Generic REST API client with authentication support, pagination handling,
rate limiting, caching, and response parsing utilities.
"""
from __future__ import annotations
import json
import time
import hashlib
import os
from urllib import request, parse, error
from typing import Any, Dict, List

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

_response_cache: dict = {}
_rate_limit_state: dict = {}

def _build_headers(api_key: str = "", bearer_token: str = "", extra_headers: dict = {}) -> dict:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    if bearer_token:
        headers["Authorization"] = "Bearer " + bearer_token
    headers.update(extra_headers)
    return headers

def get_request(url: str, params: dict = {}, api_key: str = "", bearer_token: str = "", timeout: int = 15) -> Dict[str, Any]:
    try:
        headers = _build_headers(api_key, bearer_token)
        if params:
            url = url + "?" + parse.urlencode(params)
        if HAS_REQUESTS:
            resp = requests.get(url, headers=headers, timeout=timeout)
            try:
                data = resp.json()
            except Exception:
                data = resp.text
            return {"success": resp.status_code < 400, "data": {"status": resp.status_code, "body": data, "headers": dict(resp.headers)}, "error": None if resp.status_code < 400 else str(resp.status_code)}
        req = request.Request(url, headers=headers)
        with request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
            return {"success": True, "data": {"status": resp.status, "body": body}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def post_request(url: str, body: dict = {}, api_key: str = "", bearer_token: str = "", timeout: int = 15) -> Dict[str, Any]:
    try:
        headers = _build_headers(api_key, bearer_token)
        if HAS_REQUESTS:
            resp = requests.post(url, json=body, headers=headers, timeout=timeout)
            try:
                data = resp.json()
            except Exception:
                data = resp.text
            return {"success": resp.status_code < 400, "data": {"status": resp.status_code, "body": data}, "error": None if resp.status_code < 400 else str(resp.status_code)}
        data_bytes = json.dumps(body).encode("utf-8")
        req = request.Request(url, data=data_bytes, headers=headers, method="POST")
        with request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
            return {"success": True, "data": {"status": resp.status, "body": body}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def put_request(url: str, body: dict = {}, api_key: str = "", bearer_token: str = "", timeout: int = 15) -> Dict[str, Any]:
    try:
        if not HAS_REQUESTS:
            return {"success": False, "data": None, "error": "requests library required for PUT"}
        headers = _build_headers(api_key, bearer_token)
        resp = requests.put(url, json=body, headers=headers, timeout=timeout)
        return {"success": resp.status_code < 400, "data": {"status": resp.status_code, "body": resp.json() if resp.text else {}}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def delete_request(url: str, api_key: str = "", bearer_token: str = "", timeout: int = 15) -> Dict[str, Any]:
    try:
        if not HAS_REQUESTS:
            return {"success": False, "data": None, "error": "requests library required for DELETE"}
        headers = _build_headers(api_key, bearer_token)
        resp = requests.delete(url, headers=headers, timeout=timeout)
        return {"success": resp.status_code < 400, "data": {"status": resp.status_code}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def patch_request(url: str, body: dict = {}, api_key: str = "", bearer_token: str = "", timeout: int = 15) -> Dict[str, Any]:
    try:
        if not HAS_REQUESTS:
            return {"success": False, "data": None, "error": "requests library required for PATCH"}
        headers = _build_headers(api_key, bearer_token)
        resp = requests.patch(url, json=body, headers=headers, timeout=timeout)
        return {"success": resp.status_code < 400, "data": {"status": resp.status_code, "body": resp.json() if resp.text else {}}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_with_cache(url: str, api_key: str = "", ttl_seconds: int = 300) -> Dict[str, Any]:
    try:
        cache_key = hashlib.md5((url + api_key).encode()).hexdigest()
        if cache_key in _response_cache:
            cached = _response_cache[cache_key]
            if time.time() - cached["ts"] < ttl_seconds:
                return {"success": True, "data": {"body": cached["data"], "cached": True}, "error": None}
        result = get_request(url, api_key=api_key)
        if result["success"]:
            _response_cache[cache_key] = {"data": result["data"]["body"], "ts": time.time()}
        return result
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def paginate_get(base_url: str, page_param: str = "page", max_pages: int = 5, api_key: str = "") -> Dict[str, Any]:
    try:
        all_results = []
        for page in range(1, max_pages + 1):
            r = get_request(base_url, params={page_param: page}, api_key=api_key)
            if not r["success"]:
                break
            body = r["data"]["body"]
            if isinstance(body, list):
                if not body:
                    break
                all_results.extend(body)
            elif isinstance(body, dict):
                items = body.get("data") or body.get("results") or body.get("items") or []
                if not items:
                    break
                all_results.extend(items)
            else:
                break
        return {"success": True, "data": {"pages_fetched": page, "total_items": len(all_results), "items": all_results}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_api_health(url: str, timeout: int = 5) -> Dict[str, Any]:
    try:
        if HAS_REQUESTS:
            resp = requests.get(url, timeout=timeout)
            return {"success": True, "data": {"reachable": True, "status": resp.status_code, "latency_ms": resp.elapsed.total_seconds() * 1000}, "error": None}
        start = time.time()
        req = request.Request(url)
        with request.urlopen(req, timeout=timeout) as resp:
            latency = (time.time() - start) * 1000
            return {"success": True, "data": {"reachable": True, "status": resp.status, "latency_ms": round(latency, 1)}, "error": None}
    except Exception as e:
        return {"success": False, "data": {"reachable": False}, "error": str(e)}

def clear_cache() -> Dict[str, Any]:
    global _response_cache
    count = len(_response_cache)
    _response_cache = {}
    return {"success": True, "data": {"cleared": count}, "error": None}

def upload_file(url: str, file_path: str, field_name: str = "file", api_key: str = "") -> Dict[str, Any]:
    try:
        if not HAS_REQUESTS:
            return {"success": False, "data": None, "error": "requests library required for file upload"}
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key
        with open(file_path, "rb") as f:
            resp = requests.post(url, files={field_name: f}, headers=headers, timeout=30)
        return {"success": resp.status_code < 400, "data": {"status": resp.status_code}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_libraries() -> Dict[str, Any]:
    return {"success": True, "data": {"requests": HAS_REQUESTS}, "error": None}
