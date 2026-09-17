"""toolkit_80_replit_runner.py
Run code on Replit and other free online code executors via browser automation helpers.
"""
import json
import urllib.request
import urllib.parse
import re
import subprocess
import os
import sys
import tempfile
import webbrowser

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

_PISTON = 'https://emkc.org/api/v2/piston'
_JUDGE0 = 'https://judge0-ce.p.rapidapi.com'
_WANDBOX = 'https://wandbox.org/api'

def _post_json(url, payload, headers=None):
    try:
        body = json.dumps(payload).encode()
        h = {'Content-Type': 'application/json'}
        if headers:
            h.update(headers)
        if HAS_REQUESTS:
            r = requests.post(url, json=payload, headers=h, timeout=30)
            return r.status_code, r.json() if r.text else {}
        req = urllib.request.Request(url, data=body, headers=h)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except Exception as e:
        return 0, {'error': str(e)}

def _get_json(url, headers=None):
    try:
        h = headers or {}
        if HAS_REQUESTS:
            r = requests.get(url, headers=h, timeout=15)
            return r.status_code, r.json()
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except Exception as e:
        return 0, {'error': str(e)}

def run_piston(language: str, code: str, stdin: str = '', version: str = '') -> dict:
    """Execute code via Piston free code runner API."""
    try:
        payload = {'language': language, 'files': [{'content': code}], 'stdin': stdin}
        if version:
            payload['version'] = version
        status, resp = _post_json(_PISTON + '/execute', payload)
        if status == 200 and 'run' in resp:
            run = resp['run']
            return {'success': True, 'data': {'stdout': run.get('stdout',''), 'stderr': run.get('stderr',''), 'exit_code': run.get('code',0), 'language': resp.get('language',''), 'version': resp.get('version','')}, 'error': None}
        return {'success': False, 'data': None, 'error': resp.get('message', 'HTTP ' + str(status))}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_piston_runtimes() -> dict:
    """List all supported runtimes on Piston."""
    try:
        status, data = _get_json(_PISTON + '/runtimes')
        if status == 200:
            return {'success': True, 'data': [{'language': r['language'], 'version': r['version']} for r in data], 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_wandbox(language: str, code: str, compiler: str = '', options: str = '') -> dict:
    """Execute code via Wandbox (C++, Python, Ruby, Rust, Go, etc.)."""
    try:
        payload = {'code': code, 'options': options}
        if compiler:
            payload['compiler'] = compiler
        else:
            default_compilers = {'c++': 'gcc-head', 'python': 'cpython-3.11.0', 'ruby': 'ruby-head', 'rust': 'rust-head', 'go': 'go-head', 'java': 'openjdk-head', 'haskell': 'ghc-head'}
            payload['compiler'] = default_compilers.get(language.lower(), language)
        status, resp = _post_json(_WANDBOX + '/compile.json', payload)
        if status == 200:
            return {'success': True, 'data': {'stdout': resp.get('program_output',''), 'stderr': resp.get('program_error','') + resp.get('compiler_error',''), 'exit_code': resp.get('status', 0), 'compiler': resp.get('compiler','')}, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_wandbox_compilers(language: str = '') -> dict:
    """List available Wandbox compilers."""
    try:
        status, data = _get_json(_WANDBOX + '/list.json')
        if status == 200:
            if language:
                data = [c for c in data if language.lower() in c.get('language','').lower()]
            result = [{'name': c['name'], 'language': c.get('language',''), 'version': c.get('version','')} for c in data]
            return {'success': True, 'data': result, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_tio(language: str, code: str, stdin: str = '') -> dict:
    """Run code on TIO (Try It Online) via API."""
    try:
        import zlib, base64
        lang_map = {'python': 'python3', 'python3': 'python3', 'javascript': 'javascript-node', 'ruby': 'ruby', 'perl': 'perl5', 'php': 'php', 'java': 'java-openjdk', 'c': 'c-gcc', 'c++': 'cpp-gcc', 'haskell': 'haskell-ghc', 'lua': 'lua', 'r': 'r'}
        tio_lang = lang_map.get(language.lower(), language)
        payload = 'Vlang\x001\x00' + tio_lang + '\x00F.code.tio\x00' + str(len(code.encode())) + '\x00' + code + '\x00F.input.tio\x00' + str(len(stdin.encode())) + '\x00' + stdin + '\x00Vargs\x000\x00R'
        compressed = base64.b64encode(zlib.compress(payload.encode())[2:-4]).decode()
        url = 'https://tio.run/cgi-bin/run/api/'
        body = compressed.encode()
        req = urllib.request.Request(url, data=body, method='POST')
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
        parts = raw.split('\n')
        stdout = raw[:raw.find('\n')] if '\n' in raw else raw
        return {'success': True, 'data': {'output': raw[:500], 'raw_length': len(raw)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def open_code_in_browser(language: str, code: str, runner: str = 'replit') -> dict:
    """Open code in a browser-based IDE. runners: replit, carbon, pastebin."""
    try:
        if runner == 'carbon':
            encoded = urllib.parse.quote(code[:2000])
            url = 'https://carbon.now.sh/?code=' + encoded
        elif runner == 'replit':
            encoded = urllib.parse.quote(code[:2000])
            url = 'https://replit.com/languages/' + language.lower()
        elif runner == 'onecompiler':
            lang_map = {'python': 'python', 'javascript': 'javascript', 'java': 'java', 'c': 'c', 'c++': 'cpp', 'ruby': 'ruby', 'go': 'go', 'rust': 'rust'}
            lang = lang_map.get(language.lower(), language.lower())
            url = 'https://onecompiler.com/' + lang
        elif runner == 'godbolt':
            url = 'https://godbolt.org/'
        else:
            url = 'https://replit.com/languages/' + language.lower()
        webbrowser.open(url)
        return {'success': True, 'data': {'url': url, 'opened': True}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_replit_languages() -> dict:
    """Return list of supported Replit language URLs."""
    try:
        languages = ['python', 'javascript', 'typescript', 'java', 'cpp', 'c', 'ruby', 'go', 'rust', 'php', 'swift', 'kotlin', 'scala', 'r', 'lua', 'haskell', 'perl', 'bash', 'csharp', 'html', 'css']
        result = [{'language': l, 'url': 'https://replit.com/languages/' + l} for l in languages]
        return {'success': True, 'data': result, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def share_code_as_gist(code: str, filename: str, token: str = '', description: str = '') -> dict:
    """Create a GitHub Gist and return the URL."""
    try:
        headers = {'Accept': 'application/vnd.github+json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        payload = {'description': description or 'Code shared by Screen Agent', 'public': True, 'files': {filename: {'content': code}}}
        status, resp = _post_json('https://api.github.com/gists', payload, headers)
        if status == 201:
            return {'success': True, 'data': {'url': resp.get('html_url'), 'id': resp.get('id'), 'raw_url': list(resp.get('files',{}).values())[0].get('raw_url','') if resp.get('files') else ''}, 'error': None}
        return {'success': False, 'data': None, 'error': resp.get('message','HTTP ' + str(status))}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def save_and_run_local(code: str, language: str = 'python', stdin: str = '', timeout: int = 10) -> dict:
    """Save code to temp file and run locally."""
    try:
        ext_map = {'python': '.py', 'javascript': '.js', 'ruby': '.rb', 'bash': '.sh', 'lua': '.lua', 'r': '.r', 'php': '.php'}
        cmd_map = {'python': [sys.executable], 'javascript': ['node'], 'ruby': ['ruby'], 'bash': ['bash'], 'lua': ['lua'], 'r': ['Rscript'], 'php': ['php']}
        suffix = ext_map.get(language, '.txt')
        cmd = cmd_map.get(language)
        if not cmd:
            return run_piston(language, code, stdin)
        with tempfile.NamedTemporaryFile(suffix=suffix, mode='w', delete=False, encoding='utf-8') as f:
            f.write(code); fname = f.name
        result = subprocess.run(cmd + [fname], input=stdin, capture_output=True, text=True, timeout=timeout)
        os.unlink(fname)
        return {'success': True, 'data': {'stdout': result.stdout, 'stderr': result.stderr, 'exit_code': result.returncode, 'runner': 'local'}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def benchmark_code(code: str, language: str = 'python', runs: int = 3) -> dict:
    """Run code multiple times and return average execution time via Piston."""
    try:
        import time
        times = []
        last_output = {}
        for _ in range(runs):
            start = time.time()
            result = run_piston(language, code)
            elapsed = time.time() - start
            if result['success']:
                times.append(elapsed)
                last_output = result['data']
        if times:
            return {'success': True, 'data': {'runs': len(times), 'avg_time_s': round(sum(times)/len(times),3), 'min_s': round(min(times),3), 'max_s': round(max(times),3), 'last_output': last_output}, 'error': None}
        return {'success': False, 'data': None, 'error': 'All runs failed'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_with_fallback(language: str, code: str, stdin: str = '') -> dict:
    """Try local execution first, fall back to Piston API."""
    try:
        local = save_and_run_local(code, language, stdin, timeout=5)
        if local['success'] and local['data'].get('runner') == 'local':
            local['data']['fallback_used'] = False
            return local
        result = run_piston(language, code, stdin)
        if result['success']:
            result['data']['fallback_used'] = True
        return result
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
