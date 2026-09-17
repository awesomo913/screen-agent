"""toolkit_122_http_client_tools.py
Full-featured HTTP client — cookies, sessions, auth, retries, multipart uploads.
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import base64
import time
import os
import re
from http.cookiejar import CookieJar

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

_session_cookies = CookieJar()
_session_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_session_cookies))

def get(url: str, headers: dict = {}, params: dict = {}, timeout: int = 15, verify_ssl: bool = True) -> dict:
    """Make an HTTP GET request."""
    try:
        if params:
            url = url + '?' + urllib.parse.urlencode(params)
        if HAS_REQUESTS:
            r = requests.get(url, headers=headers, timeout=timeout, verify=verify_ssl)
            return {'success': True, 'data': {'status': r.status_code, 'body': r.text[:10000], 'headers': dict(r.headers), 'url': r.url}, 'error': None}
        req = urllib.request.Request(url, headers=headers)
        with _session_opener.open(req, timeout=timeout) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            return {'success': True, 'data': {'status': resp.status, 'body': body[:10000], 'headers': dict(resp.headers), 'url': url}, 'error': None}
    except urllib.error.HTTPError as e:
        return {'success': False, 'data': {'status': e.code, 'body': e.read().decode('utf-8', errors='replace')}, 'error': 'HTTP ' + str(e.code)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def post(url: str, data=None, json_data: dict = {}, headers: dict = {}, timeout: int = 15) -> dict:
    """Make an HTTP POST request."""
    try:
        h = dict(headers)
        if json_data:
            body = json.dumps(json_data).encode()
            h.setdefault('Content-Type', 'application/json')
        elif data and isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode()
            h.setdefault('Content-Type', 'application/x-www-form-urlencoded')
        elif data and isinstance(data, str):
            body = data.encode()
        else:
            body = b''
        if HAS_REQUESTS:
            kw = {'headers': h, 'timeout': timeout}
            if json_data:
                kw['json'] = json_data
            elif data:
                kw['data'] = data
            r = requests.post(url, **kw)
            return {'success': True, 'data': {'status': r.status_code, 'body': r.text[:10000], 'headers': dict(r.headers)}, 'error': None}
        req = urllib.request.Request(url, data=body, headers=h)
        with _session_opener.open(req, timeout=timeout) as resp:
            return {'success': True, 'data': {'status': resp.status, 'body': resp.read().decode('utf-8', errors='replace')[:10000], 'headers': dict(resp.headers)}, 'error': None}
    except urllib.error.HTTPError as e:
        return {'success': False, 'data': {'status': e.code, 'body': e.read().decode('utf-8', errors='replace')}, 'error': 'HTTP ' + str(e.code)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def put(url: str, json_data: dict = {}, headers: dict = {}, timeout: int = 15) -> dict:
    """Make an HTTP PUT request."""
    try:
        h = dict(headers); h.setdefault('Content-Type', 'application/json')
        body = json.dumps(json_data).encode()
        if HAS_REQUESTS:
            r = requests.put(url, json=json_data, headers=h, timeout=timeout)
            return {'success': True, 'data': {'status': r.status_code, 'body': r.text[:5000]}, 'error': None}
        req = urllib.request.Request(url, data=body, headers=h, method='PUT')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {'success': True, 'data': {'status': resp.status, 'body': resp.read().decode()[:5000]}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def delete(url: str, headers: dict = {}, timeout: int = 15) -> dict:
    """Make an HTTP DELETE request."""
    try:
        if HAS_REQUESTS:
            r = requests.delete(url, headers=headers, timeout=timeout)
            return {'success': True, 'data': {'status': r.status_code, 'body': r.text[:2000]}, 'error': None}
        req = urllib.request.Request(url, headers=headers, method='DELETE')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {'success': True, 'data': {'status': resp.status}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def patch(url: str, json_data: dict = {}, headers: dict = {}, timeout: int = 15) -> dict:
    """Make an HTTP PATCH request."""
    try:
        if HAS_REQUESTS:
            r = requests.patch(url, json=json_data, headers=headers, timeout=timeout)
            return {'success': True, 'data': {'status': r.status_code, 'body': r.text[:5000]}, 'error': None}
        body = json.dumps(json_data).encode()
        h = dict(headers); h['Content-Type'] = 'application/json'
        req = urllib.request.Request(url, data=body, headers=h, method='PATCH')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {'success': True, 'data': {'status': resp.status}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def head(url: str, headers: dict = {}, timeout: int = 10) -> dict:
    """Make an HTTP HEAD request and return headers only."""
    try:
        if HAS_REQUESTS:
            r = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
            return {'success': True, 'data': {'status': r.status_code, 'headers': dict(r.headers)}, 'error': None}
        req = urllib.request.Request(url, headers=headers, method='HEAD')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {'success': True, 'data': {'status': resp.status, 'headers': dict(resp.headers)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_json(url: str, headers: dict = {}, timeout: int = 15) -> dict:
    """GET request and parse response as JSON."""
    try:
        result = get(url, headers=headers, timeout=timeout)
        if result['success']:
            body = result['data']['body']
            data = json.loads(body)
            result['data']['json'] = data
        return result
    except json.JSONDecodeError as e:
        return {'success': False, 'data': None, 'error': 'JSON parse error: ' + str(e)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def set_basic_auth(headers: dict, username: str, password: str) -> dict:
    """Add Basic auth header to a headers dict."""
    try:
        creds = base64.b64encode((username + ':' + password).encode()).decode()
        headers['Authorization'] = 'Basic ' + creds
        return {'success': True, 'data': headers, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def set_bearer_token(headers: dict, token: str) -> dict:
    """Add Bearer token auth header."""
    try:
        headers['Authorization'] = 'Bearer ' + token
        return {'success': True, 'data': headers, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_with_retry(url: str, max_retries: int = 3, backoff: float = 1.0, timeout: int = 15) -> dict:
    """GET request with automatic retry on failure."""
    try:
        last_error = ''
        for i in range(max_retries):
            result = get(url, timeout=timeout)
            if result['success']:
                result['data']['attempts'] = i + 1
                return result
            last_error = result.get('error', '')
            if i < max_retries - 1:
                time.sleep(backoff * (i + 1))
        return {'success': False, 'data': None, 'error': 'Failed after ' + str(max_retries) + ' retries: ' + last_error}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def download_file(url: str, output_path: str, chunk_size: int = 8192) -> dict:
    """Download a file from URL to disk."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        if HAS_REQUESTS:
            with requests.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(output_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        f.write(chunk)
        else:
            urllib.request.urlretrieve(url, output_path)
        size = os.path.getsize(output_path)
        return {'success': True, 'data': {'path': output_path, 'size': size}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def check_url_alive(url: str, timeout: int = 5) -> dict:
    """Check if a URL is reachable."""
    try:
        start = time.time()
        result = head(url, timeout=timeout)
        latency = round((time.time() - start) * 1000, 2)
        alive = result['success'] or (result.get('data', {}) or {}).get('status', 0) < 500
        return {'success': True, 'data': {'alive': alive, 'status': (result.get('data') or {}).get('status'), 'latency_ms': latency}, 'error': None}
    except Exception as e:
        return {'success': True, 'data': {'alive': False, 'error': str(e)}, 'error': None}

def get_response_headers(url: str) -> dict:
    """Get all HTTP response headers from a URL."""
    return head(url)
