"""toolkit_96_codepad_runner.py
Use free online code execution endpoints — codepad.org, ideone, godbolt, codex.
"""
import urllib.request
import urllib.parse
import json
import re
import subprocess
import sys
import tempfile
import os
import time

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

def _post(url, data, headers=None, json_payload=True):
    try:
        h = headers or {}
        if json_payload:
            body = json.dumps(data).encode()
            h['Content-Type'] = 'application/json'
            if HAS_REQUESTS:
                r = requests.post(url, json=data, headers=h, timeout=30)
                return r.status_code, r.text
        else:
            body = urllib.parse.urlencode(data).encode()
            if 'Content-Type' not in h:
                h['Content-Type'] = 'application/x-www-form-urlencoded'
            if HAS_REQUESTS:
                r = requests.post(url, data=data, headers=h, timeout=30)
                return r.status_code, r.text
        req = urllib.request.Request(url, data=body, headers=h)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return 0, str(e)

def run_on_rextester(language: str, code: str, stdin: str = '') -> dict:
    """Run code on Rextester API. language: 1=C#, 5=Python, 17=JS, 4=Java, 7=C++, 6=C."""
    try:
        lang_map = {'csharp': 1, 'vb': 2, 'cpp': 7, 'c': 6, 'python': 5, 'java': 4, 'javascript': 17, 'haskell': 11, 'php': 8, 'ruby': 14, 'perl': 13, 'swift': 37, 'rust': 46}
        lang_id = lang_map.get(language.lower(), 5) if not str(language).isdigit() else int(language)
        status, resp = _post('https://rextester.com/rundotnet/api', {'LanguageChoiceWrapper': lang_id, 'EditorChoiceWrapper': 1, 'DisplayChoiceWrapper': 0, 'Program': code, 'Input': stdin, 'ShowWarnings': False, 'IsInEditMode': False, 'IsLive': False}, json_payload=False)
        if status == 200:
            try:
                data = json.loads(resp)
                return {'success': True, 'data': {'stdout': data.get('Result',''), 'stderr': data.get('Errors',''), 'warnings': data.get('Warnings','')}, 'error': None}
            except:
                return {'success': True, 'data': {'raw': resp[:500]}, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_on_godbolt(source: str, compiler: str = 'g121', options: str = '-O2') -> dict:
    """Compile C/C++ on Compiler Explorer (godbolt.org) and get assembly."""
    try:
        payload = {'source': source, 'options': {'userArguments': options, 'executeParameters': {'args': [], 'stdin': ''}, 'compilerOptions': {'executorRequest': False}, 'filters': {'execute': True, 'intel': True, 'commentOnly': True, 'trim': True}, 'tools': [], 'libraries': []}}
        status, resp = _post('https://godbolt.org/api/compiler/' + compiler + '/compile', payload, {'Accept': 'application/json'})
        if status == 200:
            data = json.loads(resp)
            asm = '\n'.join(l.get('text','') for l in data.get('asm',[])) if isinstance(data.get('asm'), list) else ''
            stdout = '\n'.join(l.get('text','') for l in data.get('execResult',{}).get('stdout',[])) if data.get('execResult') else ''
            stderr = '\n'.join(l.get('text','') for l in data.get('stderr',[])) if data.get('stderr') else ''
            return {'success': True, 'data': {'assembly': asm[:2000], 'stdout': stdout, 'stderr': stderr, 'exit_code': data.get('execResult',{}).get('code',0)}, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_godbolt_compilers(language: str = 'c++') -> dict:
    """List available compilers on Compiler Explorer."""
    try:
        url = 'https://godbolt.org/api/compilers/' + urllib.parse.quote(language)
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        compilers = [{'id': c['id'], 'name': c['name'], 'version': c.get('version','')} for c in data[:20]]
        return {'success': True, 'data': compilers, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_python_in_subprocess(code: str, stdin: str = '', timeout: int = 10, extra_args: list = []) -> dict:
    """Run Python code in an isolated subprocess."""
    try:
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False, encoding='utf-8') as f:
            f.write(code); fname = f.name
        result = subprocess.run([sys.executable] + extra_args + [fname], input=stdin, capture_output=True, text=True, timeout=timeout)
        os.unlink(fname)
        return {'success': True, 'data': {'stdout': result.stdout, 'stderr': result.stderr, 'exit_code': result.returncode}, 'error': None}
    except subprocess.TimeoutExpired:
        return {'success': False, 'data': None, 'error': 'Execution timed out after ' + str(timeout) + 's'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_with_profiling(code: str, timeout: int = 15) -> dict:
    """Run Python code with cProfile and return top functions."""
    try:
        profile_code = 'import cProfile, pstats, io\npr = cProfile.Profile()\npr.enable()\n\n' + code + '\n\npr.disable()\ns = io.StringIO()\nps = pstats.Stats(pr, stream=s).sort_stats("cumulative")\nps.print_stats(10)\nprint(s.getvalue())'
        return run_python_in_subprocess(profile_code, timeout=timeout)
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_with_memory_trace(code: str, timeout: int = 15) -> dict:
    """Run Python code with tracemalloc memory tracking."""
    try:
        mem_code = 'import tracemalloc\ntracemalloc.start()\n\n' + code + '\n\nsnap = tracemalloc.take_snapshot()\nstats = snap.statistics("lineno")\nfor s in stats[:5]:\n    print(s)'
        return run_python_in_subprocess(mem_code, timeout=timeout)
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_code_snippet_online(language: str, code: str, stdin: str = '') -> dict:
    """Try multiple online runners and return first success."""
    try:
        runners = [
            lambda: run_on_rextester(language, code, stdin),
        ]
        if language.lower() in ('python', 'javascript', 'ruby', 'go', 'rust', 'java', 'c++', 'c', 'php'):
            from importlib import import_module
            runners.insert(0, lambda: _piston_run(language, code, stdin))
        for runner in runners:
            try:
                result = runner()
                if result.get('success'):
                    return result
            except:
                pass
        return {'success': False, 'data': None, 'error': 'All online runners failed'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def _piston_run(language, code, stdin=''):
    payload = json.dumps({'language': language, 'files': [{'content': code}], 'stdin': stdin}).encode()
    req = urllib.request.Request('https://emkc.org/api/v2/piston/execute', data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    if 'run' in data:
        return {'success': True, 'data': {'stdout': data['run'].get('stdout',''), 'stderr': data['run'].get('stderr',''), 'exit_code': data['run'].get('code',0)}, 'error': None}
    return {'success': False, 'data': None, 'error': str(data)}

def run_bash_script(script: str, timeout: int = 10) -> dict:
    """Run a bash script string locally."""
    try:
        result = subprocess.run(['bash', '-c', script], capture_output=True, text=True, timeout=timeout, shell=False)
        return {'success': True, 'data': {'stdout': result.stdout, 'stderr': result.stderr, 'exit_code': result.returncode}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_execution_time(code: str, language: str = 'python', runs: int = 5) -> dict:
    """Measure execution time of code via Piston."""
    try:
        times = []
        for _ in range(runs):
            start = time.time()
            _piston_run(language, code)
            times.append(time.time() - start)
        return {'success': True, 'data': {'avg_s': round(sum(times)/len(times),3), 'min_s': round(min(times),3), 'max_s': round(max(times),3), 'runs': runs}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
