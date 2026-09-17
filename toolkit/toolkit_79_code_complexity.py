"""toolkit_79_code_complexity.py
Analyze code complexity — cyclomatic complexity, halstead metrics, coupling.
"""
import ast
import re
import math
from collections import defaultdict

def cyclomatic_complexity(code: str) -> dict:
    """Calculate cyclomatic complexity of Python code."""
    try:
        tree = ast.parse(code)
        results = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity = 1
                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With, ast.Assert)):
                        complexity += 1
                    elif isinstance(child, ast.BoolOp):
                        complexity += len(child.values) - 1
                    elif isinstance(child, (ast.comprehension,)):
                        complexity += 1 + len(child.ifs)
                level = 'low' if complexity <= 5 else ('medium' if complexity <= 10 else 'high')
                results.append({'function': node.name, 'complexity': complexity, 'level': level, 'line': node.lineno})
        total = sum(r['complexity'] for r in results)
        return {'success': True, 'data': {'functions': results, 'total': total, 'average': round(total/len(results),2) if results else 0}, 'error': None}
    except SyntaxError as e:
        return {'success': False, 'data': None, 'error': 'Syntax error: ' + str(e)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def count_functions(code: str) -> dict:
    """Count functions, classes, and methods in Python code."""
    try:
        tree = ast.parse(code)
        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        methods = []
        for cls in classes:
            for item in cls.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append({'class': cls.name, 'method': item.name})
        top_level_funcs = [f for f in funcs if f.name not in [m['method'] for m in methods]]
        return {'success': True, 'data': {'functions': len(top_level_funcs), 'classes': len(classes), 'methods': len(methods), 'total_callables': len(funcs)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def analyze_imports(code: str) -> dict:
    """Analyze import statements in Python code."""
    try:
        tree = ast.parse(code)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({'module': alias.name, 'alias': alias.asname, 'type': 'import'})
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    imports.append({'module': module, 'name': alias.name, 'alias': alias.asname, 'type': 'from'})
        stdlib_hints = {'os','sys','re','json','math','datetime','pathlib','subprocess','collections','itertools','functools','typing','abc','io','time','random','hashlib','base64','urllib','http','shutil','tempfile','threading','multiprocessing','logging','unittest','copy','string','struct','socket','ssl','email','csv','xml','html','configparser','argparse','contextlib','enum','dataclasses','traceback','warnings'}
        for imp in imports:
            imp['likely_stdlib'] = imp['module'].split('.')[0] in stdlib_hints
        return {'success': True, 'data': {'imports': imports, 'total': len(imports), 'stdlib_count': sum(1 for i in imports if i.get('likely_stdlib'))}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def find_long_functions(code: str, max_lines: int = 50) -> dict:
    """Find functions that exceed a line length threshold."""
    try:
        tree = ast.parse(code)
        long_funcs = []
        code_lines = code.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_line = getattr(node, 'end_lineno', node.lineno + 10)
                length = end_line - node.lineno + 1
                if length > max_lines:
                    long_funcs.append({'name': node.name, 'start': node.lineno, 'end': end_line, 'lines': length})
        return {'success': True, 'data': {'long_functions': long_funcs, 'count': len(long_funcs)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def find_nested_functions(code: str, max_depth: int = 2) -> dict:
    """Find deeply nested functions."""
    try:
        results = []
        def _check(node, depth=0, parent=''):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if depth > 0:
                    results.append({'name': node.name, 'depth': depth, 'parent': parent, 'line': node.lineno})
                for child in ast.iter_child_nodes(node):
                    _check(child, depth + 1, node.name)
            else:
                for child in ast.iter_child_nodes(node):
                    _check(child, depth, parent)
        tree = ast.parse(code)
        _check(tree)
        deep = [r for r in results if r['depth'] >= max_depth]
        return {'success': True, 'data': {'nested': deep, 'count': len(deep)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def count_global_variables(code: str) -> dict:
    """Count module-level variable assignments."""
    try:
        tree = ast.parse(code)
        globals_list = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        globals_list.append({'name': target.id, 'line': node.lineno})
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                globals_list.append({'name': node.target.id, 'line': node.lineno})
        return {'success': True, 'data': {'globals': globals_list, 'count': len(globals_list)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_function_call_graph(code: str) -> dict:
    """Build a simple call graph of function->functions it calls."""
    try:
        tree = ast.parse(code)
        graph = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                calls = set()
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Name):
                            calls.add(child.func.id)
                        elif isinstance(child.func, ast.Attribute):
                            calls.add(child.func.attr)
                graph[node.name] = list(calls)
        return {'success': True, 'data': graph, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def find_dead_code(code: str) -> dict:
    """Find unreachable code after return/raise/continue/break."""
    try:
        tree = ast.parse(code)
        dead_lines = []
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for i, stmt in enumerate(func.body[:-1]):
                if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                    next_stmt = func.body[i+1]
                    dead_lines.append({'after': type(stmt).__name__, 'line': getattr(next_stmt, 'lineno', '?'), 'in_function': func.name})
        return {'success': True, 'data': {'dead_code': dead_lines, 'count': len(dead_lines)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def analyze_exception_handling(code: str) -> dict:
    """Analyze try/except patterns in code."""
    try:
        tree = ast.parse(code)
        handlers = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    exc_type = ''
                    if handler.type:
                        try:
                            exc_type = ast.unparse(handler.type)
                        except:
                            exc_type = 'Unknown'
                    else:
                        exc_type = 'bare except'
                    is_pass = len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass)
                    handlers.append({'exception': exc_type, 'line': handler.lineno, 'empty_handler': is_pass})
        return {'success': True, 'data': {'handlers': handlers, 'total': len(handlers), 'empty_handlers': sum(1 for h in handlers if h['empty_handler']), 'bare_excepts': sum(1 for h in handlers if h['exception'] == 'bare except')}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_code_summary(code: str) -> dict:
    """Get a full summary report of code quality metrics."""
    try:
        lines = code.splitlines()
        blank = sum(1 for l in lines if not l.strip())
        comments = sum(1 for l in lines if l.strip().startswith('#'))
        code_lines = len(lines) - blank - comments
        tree = ast.parse(code)
        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        complexity_result = cyclomatic_complexity(code)
        avg_cc = complexity_result['data']['average'] if complexity_result['success'] else 0
        return {'success': True, 'data': {'lines_total': len(lines), 'lines_code': code_lines, 'lines_blank': blank, 'lines_comment': comments, 'functions': len(funcs), 'classes': len(classes), 'avg_cyclomatic_complexity': avg_cc}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
