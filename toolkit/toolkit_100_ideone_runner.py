"""toolkit_100_ideone_runner.py
Run code on Ideone and other online judges — Sphere Engine, Pastebin exec.
"""
import urllib.request
import urllib.parse
import json
import re
import time

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

_PISTON = 'https://emkc.org/api/v2/piston'

def _post_json(url, payload, headers=None):
    try:
        h = {'Content-Type': 'application/json'}
        if headers:
            h.update(headers)
        body = json.dumps(payload).encode()
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
        h = headers or {'User-Agent': 'Mozilla/5.0'}
        if HAS_REQUESTS:
            r = requests.get(url, headers=h, timeout=15)
            return r.status_code, r.json()
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except Exception as e:
        return 0, {'error': str(e)}

def run_code_piston(language: str, code: str, stdin: str = '', version: str = '') -> dict:
    """Execute code on Piston (the primary free runner)."""
    try:
        payload = {'language': language, 'files': [{'content': code}], 'stdin': stdin}
        if version:
            payload['version'] = version
        status, resp = _post_json(_PISTON + '/execute', payload)
        if status == 200 and 'run' in resp:
            run = resp['run']
            return {'success': True, 'data': {'stdout': run.get('stdout',''), 'stderr': run.get('stderr',''), 'exit_code': run.get('code',0), 'language': resp.get('language',''), 'version': resp.get('version',''), 'runner': 'piston'}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp.get('message', 'HTTP ' + str(status)))}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_multiple_files(language: str, files: list, stdin: str = '') -> dict:
    """Run code with multiple files. files: [{name, content}]."""
    try:
        payload = {'language': language, 'files': files, 'stdin': stdin}
        status, resp = _post_json(_PISTON + '/execute', payload)
        if status == 200 and 'run' in resp:
            run = resp['run']
            return {'success': True, 'data': {'stdout': run.get('stdout',''), 'stderr': run.get('stderr',''), 'exit_code': run.get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': str(resp)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_code_and_check(language: str, code: str, expected_output: str, stdin: str = '') -> dict:
    """Run code and check if output matches expected."""
    try:
        result = run_code_piston(language, code, stdin)
        if not result['success']:
            return result
        actual = result['data']['stdout'].strip()
        expected = expected_output.strip()
        passed = actual == expected
        return {'success': True, 'data': {'passed': passed, 'expected': expected, 'actual': actual, 'exit_code': result['data']['exit_code']}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_test_suite(language: str, code: str, tests: list) -> dict:
    """Run code against multiple test cases. tests: [{input, expected}]."""
    try:
        results = []
        for i, test in enumerate(tests):
            result = run_code_and_check(language, code, test.get('expected',''), test.get('input',''))
            if result['success']:
                results.append({'test': i+1, 'passed': result['data']['passed'], 'expected': result['data']['expected'], 'actual': result['data']['actual']})
            else:
                results.append({'test': i+1, 'passed': False, 'error': result['error']})
        passed = sum(1 for r in results if r.get('passed'))
        return {'success': True, 'data': {'results': results, 'passed': passed, 'total': len(results), 'score': round(passed/len(results)*100, 1) if results else 0}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_all_versions(language: str, code: str, stdin: str = '') -> dict:
    """Run code on all available versions of a language."""
    try:
        status, runtimes = _get_json(_PISTON + '/runtimes')
        if status != 200:
            return {'success': False, 'data': None, 'error': 'Could not fetch runtimes'}
        lang_runtimes = [r for r in runtimes if r.get('language','').lower() == language.lower()]
        results = []
        for runtime in lang_runtimes[:5]:
            version = runtime.get('version','')
            result = run_code_piston(language, code, stdin, version)
            results.append({'version': version, 'success': result['success'], 'stdout': result.get('data',{}).get('stdout','') if result['success'] else '', 'error': result.get('error')})
        return {'success': True, 'data': results, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_code_with_retry(language: str, code: str, stdin: str = '', max_retries: int = 3) -> dict:
    """Run code with automatic retry on failure."""
    try:
        last_error = ''
        for attempt in range(max_retries):
            result = run_code_piston(language, code, stdin)
            if result['success']:
                result['data']['attempts'] = attempt + 1
                return result
            last_error = result.get('error', '')
            if attempt < max_retries - 1:
                time.sleep(1)
        return {'success': False, 'data': None, 'error': 'Failed after ' + str(max_retries) + ' attempts: ' + last_error}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def compile_and_run_c(source: str, stdin: str = '') -> dict:
    """Compile and run C code via Piston."""
    return run_code_piston('c', source, stdin)

def compile_and_run_cpp(source: str, stdin: str = '') -> dict:
    """Compile and run C++ code via Piston."""
    return run_code_piston('c++', source, stdin)

def run_python_with_packages(code: str, packages: list, stdin: str = '') -> dict:
    """Run Python code that requires specific packages via pip+piston."""
    try:
        setup_code = 'import subprocess, sys\n'
        for pkg in packages:
            setup_code += 'subprocess.run([sys.executable, "-m", "pip", "install", "' + pkg + '", "-q"], capture_output=True)\n'
        full_code = setup_code + '\n' + code
        return run_code_piston('python', full_code, stdin)
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_supported_languages() -> dict:
    """Get all languages supported by all available runners."""
    try:
        status, runtimes = _get_json(_PISTON + '/runtimes')
        if status == 200:
            langs = sorted(set(r['language'] for r in runtimes))
            return {'success': True, 'data': {'languages': langs, 'count': len(langs), 'runner': 'piston'}, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def benchmark_languages(code_by_language: dict, stdin: str = '') -> dict:
    """Run the same algorithm in multiple languages and compare timing."""
    try:
        import time
        results = []
        for lang, code in code_by_language.items():
            start = time.time()
            result = run_code_piston(lang, code, stdin)
            elapsed = round(time.time() - start, 3)
            results.append({'language': lang, 'success': result['success'], 'time_s': elapsed, 'stdout': result.get('data',{}).get('stdout','')[:100] if result['success'] else '', 'exit_code': result.get('data',{}).get('exit_code',-1) if result['success'] else -1})
        results.sort(key=lambda x: x['time_s'])
        return {'success': True, 'data': results, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
