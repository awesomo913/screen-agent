"""toolkit_69_online_code_runner.py
Runs code snippets via online free execution APIs (Piston, JDoodle, etc.)
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import subprocess
import tempfile
import os
import sys

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

_PISTON_URL = 'https://emkc.org/api/v2/piston'

def _http_post(url, payload, headers=None):
    """Internal HTTP POST helper."""
    try:
        if HAS_REQUESTS:
            r = requests.post(url, json=payload, headers=headers or {}, timeout=30)
            return r.status_code, r.json()
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={'Content-Type':'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except Exception as e:
        return 0, {'error': str(e)}

def _http_get(url):
    try:
        if HAS_REQUESTS:
            r = requests.get(url, timeout=15)
            return r.status_code, r.json()
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except Exception as e:
        return 0, {'error': str(e)}

def run_python(code: str, stdin: str = '', version: str = '3.10.0') -> dict:
    """Run Python code via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'python', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_javascript(code: str, stdin: str = '', version: str = '18.15.0') -> dict:
    """Run JavaScript (Node.js) via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'javascript', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_java(code: str, stdin: str = '', version: str = '15.0.2') -> dict:
    """Run Java code via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'java', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_cpp(code: str, stdin: str = '', version: str = '10.2.0') -> dict:
    """Run C++ code via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'c++', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_c(code: str, stdin: str = '', version: str = '10.2.0') -> dict:
    """Run C code via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'c', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_ruby(code: str, stdin: str = '', version: str = '3.0.1') -> dict:
    """Run Ruby code via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'ruby', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_go(code: str, stdin: str = '', version: str = '1.16.2') -> dict:
    """Run Go code via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'go', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_rust(code: str, stdin: str = '', version: str = '1.50.0') -> dict:
    """Run Rust code via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'rust', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_php(code: str, stdin: str = '', version: str = '8.0.2') -> dict:
    """Run PHP code via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'php', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_typescript(code: str, stdin: str = '', version: str = '5.0.3') -> dict:
    """Run TypeScript code via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'typescript', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_kotlin(code: str, stdin: str = '', version: str = '1.4.31') -> dict:
    """Run Kotlin code via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'kotlin', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_swift(code: str, stdin: str = '', version: str = '5.3.3') -> dict:
    """Run Swift code via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'swift', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_bash(code: str, stdin: str = '', version: str = '5.1.0') -> dict:
    """Run Bash script via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'bash', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_csharp(code: str, stdin: str = '', version: str = '6.12.0') -> dict:
    """Run C# code via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'csharp', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_r(code: str, stdin: str = '', version: str = '4.1.1') -> dict:
    """Run R code via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'r', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_lua(code: str, stdin: str = '', version: str = '5.4.4') -> dict:
    """Run Lua code via Piston API."""
    try:
        status, resp = _http_post(_PISTON_URL + '/execute', {
            'language': 'lua', 'version': version,
            'files': [{'content': code}], 'stdin': stdin
        })
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_language(language: str, code: str, version: str = '', stdin: str = '') -> dict:
    """Run code in any language supported by Piston."""
    try:
        payload = {'language': language, 'files': [{'content': code}], 'stdin': stdin}
        if version:
            payload['version'] = version
        status, resp = _http_post(_PISTON_URL + '/execute', payload)
        if status == 200 and 'run' in resp:
            return {'success': True, 'data': {'stdout': resp['run'].get('stdout',''), 'stderr': resp['run'].get('stderr',''), 'code': resp['run'].get('code',0), 'language': language}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_runtimes() -> dict:
    """List all available runtimes on Piston API."""
    try:
        status, resp = _http_get(_PISTON_URL + '/runtimes')
        if status == 200:
            return {'success': True, 'data': resp, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_code_local(code: str, language: str = 'python', timeout: int = 10) -> dict:
    """Run code locally using installed interpreter as fallback."""
    try:
        suffix_map = {'python':'py','javascript':'js','ruby':'rb','bash':'sh','r':'r','lua':'lua','php':'php'}
        cmd_map = {'python': [sys.executable], 'javascript': ['node'], 'ruby': ['ruby'], 'bash': ['bash'], 'r': ['Rscript'], 'lua': ['lua'], 'php': ['php']}
        suffix = suffix_map.get(language, 'txt')
        cmd = cmd_map.get(language)
        if not cmd:
            return {'success': False, 'data': None, 'error': 'Language not supported for local run'}
        with tempfile.NamedTemporaryFile(suffix='.'+suffix, mode='w', delete=False, encoding='utf-8') as f:
            f.write(code)
            fname = f.name
        result = subprocess.run(cmd + [fname], capture_output=True, text=True, timeout=timeout)
        os.unlink(fname)
        return {'success': True, 'data': {'stdout': result.stdout, 'stderr': result.stderr, 'code': result.returncode}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
