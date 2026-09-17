"""toolkit_121_code_obfuscator.py
Basic Python code obfuscation and deobfuscation tools.
"""
import ast
import base64
import zlib
import re
import random
import string
import json

def encode_to_base64_exec(code: str) -> dict:
    """Encode Python code as base64 exec payload."""
    try:
        encoded = base64.b64encode(code.encode('utf-8')).decode()
        payload = 'import base64; exec(base64.b64decode("' + encoded + '").decode())'
        return {'success': True, 'data': payload, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def decode_base64_exec(payload: str) -> dict:
    """Decode a base64 exec payload back to code."""
    try:
        m = re.search(r'base64\.b64decode\(["\']([^"\']+ )["\']\)', payload)
        if not m:
            m = re.search(r'b64decode\(["\']([A-Za-z0-9+/=]+)["\']\)', payload)
        if m:
            decoded = base64.b64decode(m.group(1)).decode('utf-8')
            return {'success': True, 'data': decoded, 'error': None}
        return {'success': False, 'data': None, 'error': 'No base64 payload found'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def compress_and_encode(code: str) -> dict:
    """Compress code with zlib then base64 encode."""
    try:
        compressed = zlib.compress(code.encode('utf-8'), level=9)
        encoded = base64.b64encode(compressed).decode()
        payload = 'import base64,zlib; exec(zlib.decompress(base64.b64decode("' + encoded + '")).decode())'
        return {'success': True, 'data': payload, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def decompress_encoded(payload: str) -> dict:
    """Decompress a zlib+base64 payload."""
    try:
        m = re.search(r'b64decode\(["\']([A-Za-z0-9+/=]+)["\']\)', payload)
        if m:
            compressed = base64.b64decode(m.group(1))
            code = zlib.decompress(compressed).decode('utf-8')
            return {'success': True, 'data': code, 'error': None}
        return {'success': False, 'data': None, 'error': 'No encoded payload found'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def remove_comments(code: str) -> dict:
    """Remove all comments from Python code."""
    try:
        lines = []
        for line in code.splitlines():
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if '#' in line:
                idx = line.find('#')
                if idx > 0 and line[idx-1] != "'" and line[idx-1] != '"':
                    line = line[:idx].rstrip()
            if line:
                lines.append(line)
        return {'success': True, 'data': chr(10).join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def remove_docstrings(code: str) -> dict:
    """Remove all docstrings from Python code."""
    try:
        tree = ast.parse(code)
        class _DocRemover(ast.NodeTransformer):
            def _remove_doc(self, node):
                if (node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str)):
                    node.body = node.body[1:] or [ast.Pass()]
                self.generic_visit(node)
                return node
            def visit_FunctionDef(self, node): return self._remove_doc(node)
            def visit_AsyncFunctionDef(self, node): return self._remove_doc(node)
            def visit_ClassDef(self, node): return self._remove_doc(node)
            def visit_Module(self, node): return self._remove_doc(node)
        new_tree = _DocRemover().visit(tree)
        ast.fix_missing_locations(new_tree)
        return {'success': True, 'data': ast.unparse(new_tree), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def mangle_names(code: str, prefix: str = '_x') -> dict:
    """Replace local variable names with short mangled names."""
    try:
        tree = ast.parse(code)
        class _Counter:
            count = 0
            mapping = {}
        def _mangle(name):
            if name not in _Counter.mapping:
                _Counter.mapping[name] = prefix + str(_Counter.count)
                _Counter.count += 1
            return _Counter.mapping[name]
        preserve = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                preserve.add(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        preserve.add(alias.name.split('.')[0])
                        if alias.asname:
                            preserve.add(alias.asname)
                else:
                    for alias in node.names:
                        preserve.add(alias.name)
                        if alias.asname:
                            preserve.add(alias.asname)
        class _Mangler(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id not in preserve and not node.id.startswith('__') and node.id not in dir(__builtins__):
                    node.id = _mangle(node.id)
                return node
        new_tree = _Mangler().visit(tree)
        ast.fix_missing_locations(new_tree)
        return {'success': True, 'data': {'code': ast.unparse(new_tree), 'mapping': _Counter.mapping}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def string_to_hex_literals(code: str) -> dict:
    """Replace string literals with hex escape equivalents."""
    try:
        def _to_hex(m):
            s = m.group(1)
            return '"' + ''.join('\\x' + format(ord(c), '02x') for c in s) + '"'
        result = re.sub(r'"([^"\\\n]{1,50})"', _to_hex, code)
        return {'success': True, 'data': result, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def minify_python(code: str) -> dict:
    """Minify Python code — remove blank lines and comments."""
    try:
        no_comments = remove_comments(code)
        if not no_comments['success']:
            return no_comments
        no_docs = remove_docstrings(no_comments['data'])
        if not no_docs['success']:
            return no_docs
        lines = [l for l in no_docs['data'].splitlines() if l.strip()]
        return {'success': True, 'data': chr(10).join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_random_name(length: int = 8, prefix: str = '_') -> dict:
    """Generate a random Python-valid identifier."""
    try:
        chars = string.ascii_lowercase + string.digits
        name = prefix + ''.join(random.choices(chars, k=length))
        return {'success': True, 'data': name, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def detect_obfuscation(code: str) -> dict:
    """Detect common obfuscation patterns in Python code."""
    try:
        indicators = []
        if re.search(r'base64\.b64decode', code): indicators.append('base64_exec')
        if re.search(r'zlib\.decompress', code): indicators.append('zlib_compression')
        if re.search(r'exec\(', code): indicators.append('dynamic_exec')
        if re.search(r'eval\(', code): indicators.append('eval_usage')
        if re.search(r'__import__', code): indicators.append('dynamic_import')
        if re.search(r'\\x[0-9a-fA-F]{2}', code): indicators.append('hex_string_escapes')
        if re.search(r'chr\(\d+\)', code): indicators.append('chr_concatenation')
        short_names = re.findall(r'\b[a-z_]{1,3}\b', code)
        if len(short_names) > 50: indicators.append('short_variable_names')
        return {'success': True, 'data': {'indicators': indicators, 'likely_obfuscated': len(indicators) > 1}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
