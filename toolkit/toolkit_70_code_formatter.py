"""toolkit_70_code_formatter.py
Format/beautify code using online formatters and local stdlib tools.
"""
import json
import re
import urllib.request
import urllib.parse

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

def _post(url, payload, headers=None):
    try:
        if HAS_REQUESTS:
            r = requests.post(url, json=payload, headers=headers or {}, timeout=20)
            return r.status_code, r.text
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode()
    except Exception as e:
        return 0, str(e)

def format_json(code: str, indent: int = 4) -> dict:
    """Format/pretty-print JSON string."""
    try:
        parsed = json.loads(code)
        return {'success': True, 'data': json.dumps(parsed, indent=indent, ensure_ascii=False), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def minify_json(code: str) -> dict:
    """Minify JSON string."""
    try:
        parsed = json.loads(code)
        return {'success': True, 'data': json.dumps(parsed, separators=(',',':'), ensure_ascii=False), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def format_python_via_api(code: str) -> dict:
    """Format Python code via black.vercel.app API."""
    try:
        status, resp = _post('https://black.vercel.app/format', {'source': code})
        if status == 200:
            try:
                data = json.loads(resp)
                return {'success': True, 'data': data.get('formatted_code', resp), 'error': None}
            except:
                return {'success': True, 'data': resp, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def format_python_local(code: str) -> dict:
    """Format Python using autopep8 if installed, else basic indent fix."""
    try:
        import autopep8
        return {'success': True, 'data': autopep8.fix_code(code), 'error': None}
    except ImportError:
        pass
    try:
        import subprocess, sys, tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as f:
            f.write(code); fname = f.name
        subprocess.run([sys.executable, '-m', 'autopep8', '--in-place', fname], capture_output=True)
        with open(fname) as f:
            result = f.read()
        os.unlink(fname)
        return {'success': True, 'data': result, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def format_xml(code: str, indent: str = '  ') -> dict:
    """Format/pretty-print XML."""
    try:
        import xml.dom.minidom
        dom = xml.dom.minidom.parseString(code.encode())
        return {'success': True, 'data': dom.toprettyxml(indent=indent), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def format_html(code: str) -> dict:
    """Basic HTML formatting — indent tags."""
    try:
        from html.parser import HTMLParser
        lines = []
        depth = 0
        void_tags = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
        tag_re = re.compile(r'<(/?)([a-zA-Z][^\s>]*)([^>]*)(/?)>')
        tokens = re.split(r'(<[^>]+>)', code)
        for tok in tokens:
            tok = tok.strip()
            if not tok:
                continue
            m = tag_re.match(tok)
            if m:
                closing, tag, attrs, self_close = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
                if closing:
                    depth = max(0, depth - 1)
                    lines.append('  ' * depth + tok)
                elif self_close or tag in void_tags:
                    lines.append('  ' * depth + tok)
                else:
                    lines.append('  ' * depth + tok)
                    depth += 1
            else:
                lines.append('  ' * depth + tok)
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def format_sql(code: str) -> dict:
    """Basic SQL formatting — uppercase keywords and newlines."""
    try:
        keywords = ['SELECT','FROM','WHERE','JOIN','LEFT JOIN','RIGHT JOIN','INNER JOIN','ON','GROUP BY','ORDER BY','HAVING','LIMIT','INSERT INTO','VALUES','UPDATE','SET','DELETE','CREATE TABLE','DROP TABLE','ALTER TABLE','AND','OR','NOT','IN','IS NULL','IS NOT NULL','UNION','UNION ALL','WITH','AS']
        result = code
        for kw in sorted(keywords, key=len, reverse=True):
            result = re.sub(r'(?i)\b' + re.escape(kw) + r'\b', '\n' + kw + ' ', result)
        result = re.sub(r'\n{2,}', '\n', result).strip()
        return {'success': True, 'data': result, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def format_css(code: str) -> dict:
    """Basic CSS formatting — one property per line."""
    try:
        result = re.sub(r';', ';\n  ', code)
        result = re.sub(r'\{', ' {\n  ', result)
        result = re.sub(r'\}', '\n}\n', result)
        result = re.sub(r'\n{3,}', '\n\n', result)
        return {'success': True, 'data': result.strip(), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def minify_css(code: str) -> dict:
    """Minify CSS by removing whitespace and comments."""
    try:
        result = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        result = re.sub(r'\s+', ' ', result)
        result = re.sub(r'\s*([{}:;,>+~])\s*', r'\1', result)
        return {'success': True, 'data': result.strip(), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def minify_html(code: str) -> dict:
    """Minify HTML by collapsing whitespace."""
    try:
        result = re.sub(r'<!--.*?-->', '', code, flags=re.DOTALL)
        result = re.sub(r'>\s+<', '><', result)
        result = re.sub(r'\s{2,}', ' ', result)
        return {'success': True, 'data': result.strip(), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def format_toml(code: str) -> dict:
    """Validate and re-format TOML (requires tomllib/tomli)."""
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        data = tomllib.loads(code)
        try:
            import tomli_w
            return {'success': True, 'data': tomli_w.dumps(data), 'error': None}
        except ImportError:
            return {'success': True, 'data': json.dumps(data, indent=2, default=str), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def format_yaml(code: str) -> dict:
    """Format YAML (requires PyYAML)."""
    try:
        import yaml
        data = yaml.safe_load(code)
        return {'success': True, 'data': yaml.dump(data, default_flow_style=False, allow_unicode=True), 'error': None}
    except ImportError:
        return {'success': False, 'data': None, 'error': 'PyYAML not installed'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def normalize_line_endings(code: str, style: str = 'lf') -> dict:
    """Convert line endings. style: lf, crlf, cr."""
    try:
        code = code.replace('\r\n','\n').replace('\r','\n')
        if style == 'crlf':
            code = code.replace('\n','\r\n')
        elif style == 'cr':
            code = code.replace('\n','\r')
        return {'success': True, 'data': code, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def remove_trailing_whitespace(code: str) -> dict:
    """Strip trailing whitespace from each line."""
    try:
        lines = [l.rstrip() for l in code.splitlines()]
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def tabs_to_spaces(code: str, tab_size: int = 4) -> dict:
    """Convert tabs to spaces."""
    try:
        return {'success': True, 'data': code.expandtabs(tab_size), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def spaces_to_tabs(code: str, tab_size: int = 4) -> dict:
    """Convert leading spaces to tabs."""
    try:
        lines = []
        for line in code.splitlines():
            stripped = line.lstrip(' ')
            num_spaces = len(line) - len(stripped)
            tabs = num_spaces // tab_size
            spaces = num_spaces % tab_size
            lines.append('\t' * tabs + ' ' * spaces + stripped)
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def sort_imports(code: str) -> dict:
    """Sort Python import statements alphabetically."""
    try:
        lines = code.splitlines()
        imports = [l for l in lines if l.strip().startswith('import ') or l.strip().startswith('from ')]
        rest = [l for l in lines if not (l.strip().startswith('import ') or l.strip().startswith('from '))]
        imports.sort()
        return {'success': True, 'data': '\n'.join(imports + [''] + rest), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def detect_language(code: str) -> dict:
    """Heuristically detect programming language of a code snippet."""
    try:
        checks = [
            ('python', [r'def \w+\(', r'import \w+', r'print\(', r'^#!']),
            ('javascript', [r'function \w+\(', r'const ', r'let ', r'var ', r'=>']),
            ('java', [r'public class', r'System\.out', r'void main']),
            ('cpp', [r'#include <', r'std::', r'cout <<']),
            ('c', [r'#include <stdio', r'printf\(', r'int main\(']),
            ('html', [r'<html', r'<!DOCTYPE', r'<div', r'<body']),
            ('css', [r'\{.*:.*;', r'@media', r'margin:', r'padding:']),
            ('sql', [r'SELECT .* FROM', r'INSERT INTO', r'CREATE TABLE']),
            ('rust', [r'fn main\(\)', r'let mut', r'println!']),
            ('go', [r'package main', r'func main\(\)', r'fmt\.Println']),
            ('ruby', [r'def \w+', r'puts ', r'end$', r'require ']),
            ('php', [r'<\?php', r'echo ', r'\$\w+']),
            ('bash', [r'^#!/bin/bash', r'\$\(', r'echo ', r'if \[']),
        ]
        scores = {}
        for lang, patterns in checks:
            scores[lang] = sum(1 for p in patterns if re.search(p, code, re.MULTILINE))
        best = max(scores, key=lambda k: scores[k])
        return {'success': True, 'data': {'language': best if scores[best] > 0 else 'unknown', 'scores': scores}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
