"""toolkit_78_docstring_generator.py
Auto-generate Python docstrings and function stubs for code.
"""
import ast
import re
import json
import inspect
import textwrap

def _parse_function(code: str):
    try:
        tree = ast.parse(code)
        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        return funcs
    except Exception:
        return []

def generate_google_docstring(func_name: str, params: list, returns: str = '', description: str = '') -> dict:
    """Generate a Google-style docstring stub."""
    try:
        lines = ['"""' + (description or func_name + '.')]
        if params:
            lines.append('')
            lines.append('Args:')
            for p in params:
                if isinstance(p, dict):
                    lines.append('    ' + p.get('name','param') + ' (' + p.get('type','Any') + '): ' + p.get('desc','TODO'))
                else:
                    lines.append('    ' + str(p) + ' (Any): TODO')
        if returns:
            lines.append('')
            lines.append('Returns:')
            lines.append('    ' + returns)
        lines.append('"""')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_numpy_docstring(func_name: str, params: list, returns: str = '', description: str = '') -> dict:
    """Generate a NumPy-style docstring stub."""
    try:
        lines = ['"""' + (description or func_name + '.'), '']
        if params:
            lines.append('Parameters')
            lines.append('----------')
            for p in params:
                if isinstance(p, dict):
                    lines.append(p.get('name','param') + ' : ' + p.get('type','Any'))
                    lines.append('    ' + p.get('desc','TODO'))
                else:
                    lines.append(str(p) + ' : Any')
                    lines.append('    TODO')
        if returns:
            lines.append('')
            lines.append('Returns')
            lines.append('-------')
            lines.append(returns)
        lines.append('"""')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_sphinx_docstring(func_name: str, params: list, returns: str = '', description: str = '') -> dict:
    """Generate a Sphinx/reST-style docstring stub."""
    try:
        lines = ['"""' + (description or func_name + '.')]
        for p in params:
            if isinstance(p, dict):
                lines.append(':param ' + p.get('name','param') + ': ' + p.get('desc','TODO'))
                lines.append(':type ' + p.get('name','param') + ': ' + p.get('type','Any'))
            else:
                lines.append(':param ' + str(p) + ': TODO')
        if returns:
            lines.append(':return: ' + returns)
        lines.append('"""')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def extract_functions_from_code(code: str) -> dict:
    """Parse Python code and extract function signatures."""
    try:
        tree = ast.parse(code)
        results = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = []
                for arg in node.args.args:
                    annotation = ''
                    if arg.annotation:
                        try:
                            annotation = ast.unparse(arg.annotation)
                        except:
                            pass
                    args.append({'name': arg.arg, 'type': annotation or 'Any'})
                returns = ''
                if node.returns:
                    try:
                        returns = ast.unparse(node.returns)
                    except:
                        pass
                existing_docstring = ''
                if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                    existing_docstring = node.body[0].value.s
                results.append({'name': node.name, 'args': args, 'returns': returns, 'lineno': node.lineno, 'has_docstring': bool(existing_docstring), 'existing_docstring': existing_docstring})
        return {'success': True, 'data': results, 'error': None}
    except SyntaxError as e:
        return {'success': False, 'data': None, 'error': 'Syntax error: ' + str(e)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def add_docstrings_to_code(code: str, style: str = 'google') -> dict:
    """Add missing docstrings to all functions in Python code."""
    try:
        funcs = extract_functions_from_code(code)
        if not funcs['success']:
            return funcs
        lines = code.splitlines()
        insertions = []
        for func in funcs['data']:
            if not func['has_docstring']:
                lineno = func['lineno']
                indent = '    '
                params = [p['name'] for p in func['args'] if p['name'] != 'self']
                if style == 'google':
                    ds = generate_google_docstring(func['name'], func['args'], func['returns'])
                elif style == 'numpy':
                    ds = generate_numpy_docstring(func['name'], func['args'], func['returns'])
                else:
                    ds = generate_sphinx_docstring(func['name'], func['args'], func['returns'])
                if ds['success']:
                    insertions.append((lineno, indent + ds['data'].replace('\n', '\n' + indent)))
        for line_idx, doc in sorted(insertions, reverse=True):
            lines.insert(line_idx, doc)
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_function_stub(name: str, params: list, return_type: str = 'dict', async_func: bool = False) -> dict:
    """Generate a function stub with type hints."""
    try:
        prefix = 'async def ' if async_func else 'def '
        param_strs = []
        for p in params:
            if isinstance(p, dict):
                ann = p.get('type','Any')
                default = p.get('default','')
                pstr = p.get('name','param') + ': ' + ann
                if default:
                    pstr += ' = ' + str(default)
                param_strs.append(pstr)
            else:
                param_strs.append(str(p))
        sig = prefix + name + '(' + ', '.join(param_strs) + ') -> ' + (return_type or 'None') + ':'
        body = '    """TODO: implement ' + name + '."""\n    raise NotImplementedError'
        return {'success': True, 'data': sig + '\n' + body, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def find_undocumented_functions(code: str) -> dict:
    """Find functions in Python code that lack docstrings."""
    try:
        result = extract_functions_from_code(code)
        if not result['success']:
            return result
        undocumented = [f for f in result['data'] if not f['has_docstring']]
        return {'success': True, 'data': {'undocumented': [f['name'] for f in undocumented], 'count': len(undocumented), 'total': len(result['data'])}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_class_stub(class_name: str, methods: list, base_class: str = '') -> dict:
    """Generate a Python class stub."""
    try:
        parent = '(' + base_class + ')' if base_class else ''
        lines = ['class ' + class_name + parent + ':']
        lines.append('    """' + class_name + ' class."""')
        lines.append('')
        lines.append('    def __init__(self):')
        lines.append('        """Initialize ' + class_name + '."""')
        lines.append('        pass')
        for method in methods:
            lines.append('')
            if isinstance(method, dict):
                mname = method.get('name', 'method')
                mparams = method.get('params', [])
                param_str = ', '.join(['self'] + [str(p) for p in mparams])
                lines.append('    def ' + mname + '(' + param_str + '):')
                lines.append('        """' + mname + '."""; pass')
            else:
                lines.append('    def ' + str(method) + '(self):')
                lines.append('        """' + str(method) + '."""; pass')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_module_header(module_name: str, description: str, author: str = '', version: str = '1.0.0') -> dict:
    """Generate a standard module header with docstring."""
    try:
        import datetime
        year = datetime.datetime.now().year
        lines = [
            '"""',
            module_name + '.py',
            '',
            description,
            '"""',
            '',
        ]
        if author:
            lines.insert(-1, '__author__ = "' + author + '"')
        lines.append('__version__ = "' + version + '"')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def extract_class_structure(code: str) -> dict:
    """Extract class and method structure from Python code."""
    try:
        tree = ast.parse(code)
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append({'name': item.name, 'args': [a.arg for a in item.args.args]})
                classes.append({'name': node.name, 'lineno': node.lineno, 'methods': methods, 'bases': [ast.unparse(b) for b in node.bases]})
        return {'success': True, 'data': classes, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
