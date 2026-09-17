"""toolkit_98_language_server_client.py
Interact with Language Server Protocol (LSP) servers for code intelligence.
"""
import json
import subprocess
import sys
import os
import threading
import time
import re
from pathlib import Path

def check_lsp_available(server: str = 'pyright') -> dict:
    """Check if an LSP server is installed."""
    try:
        servers = {'pyright': ['pyright-langserver', '--version'], 'pylsp': [sys.executable, '-m', 'pylsp', '--version'], 'ruff': ['ruff', '--version'], 'clangd': ['clangd', '--version'], 'rust-analyzer': ['rust-analyzer', '--version'], 'typescript': ['typescript-language-server', '--version']}
        cmd = servers.get(server, [server, '--version'])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return {'success': True, 'data': {'available': result.returncode == 0, 'server': server, 'version': result.stdout.strip() or result.stderr.strip()}, 'error': None}
    except FileNotFoundError:
        return {'success': True, 'data': {'available': False, 'server': server}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def install_pyright() -> dict:
    """Install Pyright LSP server via npm."""
    try:
        result = subprocess.run(['npm', 'install', '-g', 'pyright'], capture_output=True, text=True, timeout=60)
        return {'success': result.returncode == 0, 'data': {'installed': result.returncode == 0, 'output': result.stdout[:500]}, 'error': result.stderr[:200] if result.returncode != 0 else None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def install_pylsp() -> dict:
    """Install Python LSP server (pylsp) via pip."""
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', 'python-lsp-server'], capture_output=True, text=True, timeout=60)
        return {'success': result.returncode == 0, 'data': result.stdout[:300], 'error': result.stderr[:200] if result.returncode != 0 else None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def analyze_with_pyright(code: str, filename: str = 'temp.py') -> dict:
    """Type-check Python code using Pyright."""
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False, encoding='utf-8', prefix='pyright_') as f:
            f.write(code); fname = f.name
        result = subprocess.run(['pyright', '--outputjson', fname], capture_output=True, text=True, timeout=20)
        os.unlink(fname)
        try:
            data = json.loads(result.stdout)
            diags = data.get('generalDiagnostics', [])
            errors = [{'line': d.get('range',{}).get('start',{}).get('line',0)+1, 'message': d.get('message',''), 'severity': d.get('severity',''), 'rule': d.get('rule','')} for d in diags]
            return {'success': True, 'data': {'diagnostics': errors, 'error_count': data.get('errorCount',0), 'warning_count': data.get('warningCount',0)}, 'error': None}
        except:
            lines = [l for l in result.stdout.splitlines() if '.py:' in l or 'error:' in l.lower()]
            return {'success': True, 'data': {'output': lines[:20]}, 'error': None}
    except FileNotFoundError:
        return {'success': False, 'data': None, 'error': 'Pyright not installed. Run: npm install -g pyright'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def analyze_with_ruff(code: str) -> dict:
    """Lint Python code with Ruff."""
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False, encoding='utf-8') as f:
            f.write(code); fname = f.name
        result = subprocess.run(['ruff', 'check', '--output-format=json', fname], capture_output=True, text=True, timeout=15)
        os.unlink(fname)
        try:
            issues = json.loads(result.stdout)
            return {'success': True, 'data': {'issues': issues, 'count': len(issues)}, 'error': None}
        except:
            return {'success': True, 'data': {'raw': result.stdout[:1000]}, 'error': None}
    except FileNotFoundError:
        return {'success': False, 'data': None, 'error': 'Ruff not installed. Run: pip install ruff'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def format_with_ruff(code: str) -> dict:
    """Format Python code with Ruff formatter."""
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False, encoding='utf-8') as f:
            f.write(code); fname = f.name
        subprocess.run(['ruff', 'format', fname], capture_output=True, text=True, timeout=10)
        with open(fname, encoding='utf-8') as f:
            formatted = f.read()
        os.unlink(fname)
        return {'success': True, 'data': formatted, 'error': None}
    except FileNotFoundError:
        return {'success': False, 'data': None, 'error': 'Ruff not installed. Run: pip install ruff'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def format_with_black(code: str, line_length: int = 88) -> dict:
    """Format Python code with Black."""
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False, encoding='utf-8') as f:
            f.write(code); fname = f.name
        result = subprocess.run([sys.executable, '-m', 'black', '--line-length', str(line_length), fname], capture_output=True, text=True, timeout=15)
        if result.returncode in (0, 1):
            with open(fname, encoding='utf-8') as f:
                formatted = f.read()
            os.unlink(fname)
            return {'success': True, 'data': formatted, 'error': None}
        os.unlink(fname)
        return {'success': False, 'data': None, 'error': result.stderr[:500]}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_code_outline(file_path: str) -> dict:
    """Get function and class outline for a Python file using AST."""
    try:
        import ast
        with open(file_path, encoding='utf-8') as f:
            code = f.read()
        tree = ast.parse(code)
        outline = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
                outline.append({'type': 'class', 'name': node.name, 'line': node.lineno, 'methods': methods})
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                outline.append({'type': 'function', 'name': node.name, 'line': node.lineno})
        outline.sort(key=lambda x: x['line'])
        return {'success': True, 'data': outline, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def run_type_checking_mypy(code: str) -> dict:
    """Type-check Python code with mypy."""
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False, encoding='utf-8') as f:
            f.write(code); fname = f.name
        result = subprocess.run([sys.executable, '-m', 'mypy', '--ignore-missing-imports', '--no-error-summary', fname], capture_output=True, text=True, timeout=20)
        os.unlink(fname)
        lines = result.stdout.splitlines()
        errors = [l for l in lines if 'error:' in l or 'warning:' in l]
        return {'success': True, 'data': {'issues': errors, 'count': len(errors), 'passed': result.returncode == 0}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_installed_formatters() -> dict:
    """Check which code formatters are installed."""
    try:
        formatters = {'black': [sys.executable, '-m', 'black', '--version'], 'ruff': ['ruff', '--version'], 'autopep8': [sys.executable, '-m', 'autopep8', '--version'], 'isort': [sys.executable, '-m', 'isort', '--version'], 'yapf': [sys.executable, '-m', 'yapf', '--version'], 'prettier': ['prettier', '--version'], 'clang-format': ['clang-format', '--version']}
        results = {}
        for name, cmd in formatters.items():
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                results[name] = {'installed': r.returncode == 0, 'version': (r.stdout + r.stderr).strip().split('\n')[0][:50]}
            except FileNotFoundError:
                results[name] = {'installed': False, 'version': ''}
        return {'success': True, 'data': results, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
