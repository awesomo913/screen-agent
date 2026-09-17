"""toolkit_101_code_sharing.py
Share code via Pastebin, paste.ee, dpaste and other free paste services.
"""
import urllib.request
import urllib.parse
import json
import re
import webbrowser

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

def _post(url, data, headers=None, json_payload=False):
    try:
        h = headers or {'User-Agent': 'Mozilla/5.0'}
        if json_payload:
            body = json.dumps(data).encode()
            h['Content-Type'] = 'application/json'
        else:
            body = urllib.parse.urlencode(data).encode()
            h.setdefault('Content-Type', 'application/x-www-form-urlencoded')
        if HAS_REQUESTS:
            if json_payload:
                r = requests.post(url, json=data, headers=h, timeout=15)
            else:
                r = requests.post(url, data=data, headers=h, timeout=15)
            return r.status_code, r.text
        req = urllib.request.Request(url, data=body, headers=h)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return 0, str(e)

def paste_to_pastebin(code: str, title: str = '', format_str: str = 'python', api_key: str = '', expire: str = '1H') -> dict:
    """Create a Pastebin paste. expire: N=never, 10M, 1H, 1D, 1W, 2W, 1M, 6M, 1Y."""
    try:
        if not api_key:
            return {'success': False, 'data': None, 'error': 'Pastebin API key required (get free at pastebin.com/api)'}
        data = {'api_dev_key': api_key, 'api_option': 'paste', 'api_paste_code': code, 'api_paste_name': title, 'api_paste_format': format_str, 'api_paste_expire_date': expire, 'api_paste_private': '0'}
        status, resp = _post('https://pastebin.com/api/api_post.php', data)
        if status == 200 and resp.startswith('http'):
            return {'success': True, 'data': {'url': resp, 'raw_url': resp.replace('pastebin.com/', 'pastebin.com/raw/')}, 'error': None}
        return {'success': False, 'data': None, 'error': resp[:200]}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def paste_to_dpaste(code: str, language: str = 'python', title: str = '', expiry_days: int = 7) -> dict:
    """Create a dpaste.com paste (no auth needed)."""
    try:
        data = {'content': code, 'syntax': language, 'title': title or 'Screen Agent Paste', 'expiry_days': str(expiry_days)}
        status, resp = _post('https://dpaste.com/api/v2/', data)
        if status == 201 or (status == 200 and resp.startswith('http')):
            url = resp.strip()
            return {'success': True, 'data': {'url': url, 'raw_url': url + '.txt'}, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status) + ': ' + resp[:200]}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def paste_to_pastee(code: str, language: str = 'python', title: str = '', api_key: str = '') -> dict:
    """Create a paste.ee paste (free tier available)."""
    try:
        payload = {'sections': [{'name': title or 'Code', 'syntax': language, 'contents': code}]}
        headers = {'Application-Key': api_key} if api_key else {}
        headers['Content-Type'] = 'application/json'
        status, resp = _post('https://api.paste.ee/v1/pastes', payload, headers, json_payload=True)
        if status == 201:
            try:
                data = json.loads(resp)
                return {'success': True, 'data': {'url': data.get('link',''), 'id': data.get('id','')}, 'error': None}
            except:
                return {'success': True, 'data': {'raw': resp[:200]}, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def share_via_github_gist(code: str, filename: str = 'code.py', description: str = '', token: str = '', public: bool = True) -> dict:
    """Share code as a GitHub Gist."""
    try:
        payload = {'description': description or 'Code shared by Screen Agent', 'public': public, 'files': {filename: {'content': code}}}
        headers = {'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        status, resp = _post('https://api.github.com/gists', payload, headers, json_payload=True)
        if status == 201:
            data = json.loads(resp)
            return {'success': True, 'data': {'url': data.get('html_url',''), 'raw_url': list(data.get('files',{}).values())[0].get('raw_url','') if data.get('files') else '', 'id': data.get('id','')}, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_paste_from_gist(gist_id: str, token: str = '') -> dict:
    """Fetch a GitHub Gist by ID."""
    try:
        url = 'https://api.github.com/gists/' + gist_id
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'Mozilla/5.0'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        files = {name: f.get('content','') for name, f in data.get('files',{}).items()}
        return {'success': True, 'data': {'description': data.get('description',''), 'files': files, 'url': data.get('html_url',''), 'created': data.get('created_at','')}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def open_in_browser(url: str) -> dict:
    """Open a URL in the default web browser."""
    try:
        webbrowser.open(url)
        return {'success': True, 'data': {'opened': url}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_share_links(code: str, language: str = 'python') -> dict:
    """Generate multiple share link options for code."""
    try:
        encoded = urllib.parse.quote(code[:2000])
        links = {
            'carbon': 'https://carbon.now.sh/?code=' + encoded,
            'replit': 'https://replit.com/languages/' + language,
            'onecompiler': 'https://onecompiler.com/' + ({'python': 'python', 'javascript': 'javascript', 'java': 'java', 'c++': 'cpp', 'c': 'c', 'go': 'go', 'rust': 'rust'}.get(language, language)),
            'godbolt': 'https://godbolt.org/',
            'pythonanywhere': 'https://www.pythonanywhere.com/',
        }
        return {'success': True, 'data': links, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def save_snippet_locally(code: str, filename: str, directory: str = '.') -> dict:
    """Save a code snippet to a local file."""
    try:
        import os
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code)
        return {'success': True, 'data': {'path': path, 'size': len(code)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def encode_for_url(code: str) -> dict:
    """URL-encode code for embedding in share links."""
    try:
        import base64
        encoded_b64 = base64.urlsafe_b64encode(code.encode()).decode()
        encoded_url = urllib.parse.quote(code)
        return {'success': True, 'data': {'url_encoded': encoded_url[:500], 'base64': encoded_b64[:500], 'note': 'truncated to 500 chars for safety'}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
