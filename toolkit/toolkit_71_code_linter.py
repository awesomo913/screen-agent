"""toolkit_71_code_linter.py
Lint code via online APIs and local tools — get errors and warnings.
"""
import subprocess
import sys
import os
import json
import tempfile
import re
import urllib.request

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

def _run(cmd, code_text, suffix):
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, mode='w', delete=False, encoding='utf-8') as f:
            f.write(code_text); fname = f.name
        result = subprocess.run(cmd + [fname], capture_output=True, text=True, timeout=20)
        os.unlink(fname)
        return result.stdout + result.stderr, result.returncode
    except Exception as e:
        return str(e), -1

def lint_python_pyflakes(code: str) -> dict:
    """Lint Python with pyflakes."""
    try:
        out, rc = _run([sys.executable, '-m', 'pyflakes'], code, '.py')
        issues = [l for l in out.splitlines() if l.strip()]
        return {'success': True, 'data': {'issues': issues, 'count': len(issues), 'return_code': rc}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def lint_python_pylint(code: str) -> dict:
    """Lint Python with pylint."""
    try:
        out, rc = _run([sys.executable, '-m', 'pylint', '--output-format=text'], code, '.py')
        issues = [l for l in out.splitlines() if re.match(r'.+:\d+:\d+:', l)]
        return {'success': True, 'data': {'issues': issues, 'count': len(issues), 'return_code': rc}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def lint_python_flake8(code: str) -> dict:
    """Lint Python with flake8."""
    try:
        out, rc = _run([sys.executable, '-m', 'flake8', '--max-line-length=120'], code, '.py')
        issues = [l for l in out.splitlines() if l.strip()]
        return {'success': True, 'data': {'issues': issues, 'count': len(issues), 'return_code': rc}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def lint_python_mypy(code: str) -> dict:
    """Type-check Python with mypy."""
    try:
        out, rc = _run([sys.executable, '-m', 'mypy', '--ignore-missing-imports'], code, '.py')
        issues = [l for l in out.splitlines() if l.strip() and 'error:' in l]
        return {'success': True, 'data': {'issues': issues, 'count': len(issues), 'return_code': rc}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def lint_python_bandit(code: str) -> dict:
    """Security-lint Python with bandit."""
    try:
        out, rc = _run([sys.executable, '-m', 'bandit', '-q'], code, '.py')
        issues = [l for l in out.splitlines() if l.strip()]
        return {'success': True, 'data': {'issues': issues, 'count': len(issues), 'return_code': rc}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def check_python_syntax(code: str) -> dict:
    """Check Python syntax using compile()."""
    try:
        compile(code, '<string>', 'exec')
        return {'success': True, 'data': {'valid': True, 'issues': []}, 'error': None}
    except SyntaxError as e:
        return {'success': True, 'data': {'valid': False, 'issues': [{'line': e.lineno, 'msg': e.msg, 'text': e.text}]}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def lint_js_via_piston(code: str) -> dict:
    """Lint JS by running it with Node.js --check via Piston API."""
    try:
        import urllib.request
        payload = json.dumps({'language':'javascript','version':'18.15.0','files':[{'content':code}]}).encode()
        req = urllib.request.Request('https://emkc.org/api/v2/piston/execute', data=payload, headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        run = data.get('run', {})
        stderr = run.get('stderr','')
        issues = [l for l in stderr.splitlines() if l.strip()]
        return {'success': True, 'data': {'issues': issues, 'stdout': run.get('stdout',''), 'code': run.get('code',0)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def check_json_syntax(code: str) -> dict:
    """Validate JSON and report syntax errors."""
    try:
        json.loads(code)
        return {'success': True, 'data': {'valid': True, 'issues': []}, 'error': None}
    except json.JSONDecodeError as e:
        return {'success': True, 'data': {'valid': False, 'issues': [{'line': e.lineno, 'col': e.colno, 'msg': e.msg}]}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def check_xml_syntax(code: str) -> dict:
    """Validate XML and report parse errors."""
    try:
        import xml.etree.ElementTree as ET
        ET.fromstring(code)
        return {'success': True, 'data': {'valid': True, 'issues': []}, 'error': None}
    except ET.ParseError as e:
        return {'success': True, 'data': {'valid': False, 'issues': [str(e)]}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def check_html_structure(code: str) -> dict:
    """Check HTML for unclosed tags."""
    try:
        from html.parser import HTMLParser
        void_tags = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
        class _P(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack = []; self.errors = []
            def handle_starttag(self, tag, attrs):
                if tag not in void_tags:
                    self.stack.append(tag)
            def handle_endtag(self, tag):
                if self.stack and self.stack[-1] == tag:
                    self.stack.pop()
                else:
                    self.errors.append('Unexpected closing tag: ' + tag)
        p = _P()
        p.feed(code)
        for t in p.stack:
            p.errors.append('Unclosed tag: ' + t)
        return {'success': True, 'data': {'valid': len(p.errors)==0, 'issues': p.errors}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def lint_css_basic(code: str) -> dict:
    """Basic CSS lint: find unclosed braces and missing semicolons."""
    try:
        issues = []
        opens = code.count('{')
        closes = code.count('}')
        if opens != closes:
            issues.append('Mismatched braces: ' + str(opens) + ' open vs ' + str(closes) + ' close')
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped and not stripped.endswith(('{','}',',','*/','/*')) and ':' in stripped and not stripped.endswith(';'):
                issues.append('Line ' + str(i) + ': possibly missing semicolon')
        return {'success': True, 'data': {'valid': len(issues)==0, 'issues': issues}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def find_long_lines(code: str, max_len: int = 120) -> dict:
    """Find lines exceeding max_len characters."""
    try:
        issues = [{'line': i+1, 'length': len(l), 'text': l[:80]} for i, l in enumerate(code.splitlines()) if len(l) > max_len]
        return {'success': True, 'data': {'issues': issues, 'count': len(issues)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def find_todo_comments(code: str) -> dict:
    """Find TODO/FIXME/HACK/XXX comments in code."""
    try:
        pattern = re.compile(r'(#|//|/\*)\s*(TODO|FIXME|HACK|XXX|NOTE|BUG)[:\s]?(.*)', re.IGNORECASE)
        results = []
        for i, line in enumerate(code.splitlines(), 1):
            m = pattern.search(line)
            if m:
                results.append({'line': i, 'type': m.group(2).upper(), 'text': m.group(3).strip()})
        return {'success': True, 'data': {'found': results, 'count': len(results)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def count_code_metrics(code: str) -> dict:
    """Count lines of code, comments, blanks."""
    try:
        lines = code.splitlines()
        blanks = sum(1 for l in lines if not l.strip())
        comments = sum(1 for l in lines if l.strip().startswith(('#','//','/*','*','"""',"'''")))
        code_lines = len(lines) - blanks - comments
        return {'success': True, 'data': {'total': len(lines), 'code': code_lines, 'comments': comments, 'blank': blanks}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def find_duplicate_lines(code: str) -> dict:
    """Find duplicate non-blank lines in code."""
    try:
        from collections import Counter
        lines = [l.strip() for l in code.splitlines() if l.strip()]
        counts = Counter(lines)
        dupes = [{'line': l, 'count': c} for l, c in counts.items() if c > 1]
        return {'success': True, 'data': {'duplicates': dupes, 'count': len(dupes)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def check_encoding(file_path: str) -> dict:
    """Detect file encoding."""
    try:
        try:
            import chardet
            with open(file_path, 'rb') as f:
                raw = f.read()
            result = chardet.detect(raw)
            return {'success': True, 'data': result, 'error': None}
        except ImportError:
            pass
        for enc in ['utf-8', 'utf-16', 'latin-1', 'cp1252']:
            try:
                with open(file_path, encoding=enc) as f:
                    f.read()
                return {'success': True, 'data': {'encoding': enc, 'confidence': None}, 'error': None}
            except UnicodeDecodeError:
                pass
        return {'success': False, 'data': None, 'error': 'Could not detect encoding'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
