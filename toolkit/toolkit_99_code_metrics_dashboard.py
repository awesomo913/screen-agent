"""toolkit_99_code_metrics_dashboard.py
Aggregate code quality metrics into a dashboard report.
"""
import os
import re
import ast
import json
import subprocess
import sys
import datetime
from pathlib import Path

def analyze_file(file_path: str) -> dict:
    """Full analysis of a single Python file."""
    try:
        with open(file_path, encoding='utf-8') as f:
            code = f.read()
        lines = code.splitlines()
        blank = sum(1 for l in lines if not l.strip())
        comments = sum(1 for l in lines if l.strip().startswith('#'))
        code_lines = len(lines) - blank - comments
        tree = ast.parse(code)
        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        complexity_total = 0
        for func in funcs:
            cc = 1
            for child in ast.walk(func):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                    cc += 1
                elif isinstance(child, ast.BoolOp):
                    cc += len(child.values) - 1
            complexity_total += cc
        imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        todos = sum(1 for l in lines if re.search(r'#\s*(TODO|FIXME|HACK|XXX)', l, re.IGNORECASE))
        return {'success': True, 'data': {'file': os.path.basename(file_path), 'total_lines': len(lines), 'code_lines': code_lines, 'blank_lines': blank, 'comment_lines': comments, 'functions': len(funcs), 'classes': len(classes), 'imports': len(imports), 'avg_complexity': round(complexity_total/len(funcs),2) if funcs else 0, 'todos': todos}, 'error': None}
    except SyntaxError as e:
        return {'success': False, 'data': None, 'error': 'Syntax error: ' + str(e)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def analyze_project(project_path: str) -> dict:
    """Analyze all Python files in a project directory."""
    try:
        files = list(Path(project_path).rglob('*.py'))
        file_results = []
        for f in files:
            result = analyze_file(str(f))
            if result['success']:
                result['data']['path'] = str(f.relative_to(project_path))
                file_results.append(result['data'])
        if not file_results:
            return {'success': True, 'data': {'files': 0, 'message': 'No Python files found'}, 'error': None}
        total = {'total_files': len(file_results), 'total_lines': sum(f['total_lines'] for f in file_results), 'total_code_lines': sum(f['code_lines'] for f in file_results), 'total_functions': sum(f['functions'] for f in file_results), 'total_classes': sum(f['classes'] for f in file_results), 'total_todos': sum(f['todos'] for f in file_results), 'avg_complexity': round(sum(f['avg_complexity'] for f in file_results)/len(file_results),2), 'files': file_results}
        return {'success': True, 'data': total, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_html_report(project_path: str, output_path: str = '') -> dict:
    """Generate an HTML metrics dashboard for a project."""
    try:
        analysis = analyze_project(project_path)
        if not analysis['success']:
            return analysis
        data = analysis['data']
        today = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        file_rows = ''
        for f in data.get('files', [])[:50]:
            cc_color = 'red' if f['avg_complexity'] > 10 else ('orange' if f['avg_complexity'] > 5 else 'green')
            file_rows += '<tr><td>' + f.get('path','') + '</td><td>' + str(f['total_lines']) + '</td><td>' + str(f['functions']) + '</td><td>' + str(f['classes']) + '</td><td style="color:' + cc_color + '">' + str(f['avg_complexity']) + '</td><td>' + str(f['todos']) + '</td></tr>'
        html = '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Code Metrics</title><style>body{font-family:sans-serif;max-width:1200px;margin:0 auto;padding:20px}table{width:100%;border-collapse:collapse}th,td{border:1px solid #ddd;padding:8px;text-align:left}th{background:#f0f0f0}.metric{display:inline-block;background:#f5f5f5;border-radius:8px;padding:15px 25px;margin:10px;text-align:center}.metric h2{margin:0;font-size:2rem;color:#333}.metric p{margin:0;color:#666}</style></head><body><h1>Code Metrics Dashboard</h1><p>Project: ' + project_path + ' | Generated: ' + today + '</p><div><div class="metric"><h2>' + str(data['total_files']) + '</h2><p>Files</p></div><div class="metric"><h2>' + str(data['total_lines']) + '</h2><p>Total Lines</p></div><div class="metric"><h2>' + str(data['total_functions']) + '</h2><p>Functions</p></div><div class="metric"><h2>' + str(data['total_classes']) + '</h2><p>Classes</p></div><div class="metric"><h2>' + str(data['avg_complexity']) + '</h2><p>Avg Complexity</p></div><div class="metric"><h2>' + str(data['total_todos']) + '</h2><p>TODOs</p></div></div><h2>Files</h2><table><tr><th>File</th><th>Lines</th><th>Functions</th><th>Classes</th><th>Complexity</th><th>TODOs</th></tr>' + file_rows + '</table></body></html>'
        if not output_path:
            output_path = os.path.join(project_path, 'metrics_report.html')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        return {'success': True, 'data': {'path': output_path, 'total_files': data['total_files']}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_json_report(project_path: str, output_path: str = '') -> dict:
    """Generate a JSON metrics report for a project."""
    try:
        analysis = analyze_project(project_path)
        if not analysis['success']:
            return analysis
        report = {'generated_at': datetime.datetime.now().isoformat(), 'project': project_path, 'summary': analysis['data']}
        if not output_path:
            output_path = os.path.join(project_path, 'metrics_report.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        return {'success': True, 'data': {'path': output_path}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def find_complex_functions(project_path: str, threshold: int = 10) -> dict:
    """Find all functions with complexity above threshold."""
    try:
        complex_funcs = []
        for py_file in Path(project_path).rglob('*.py'):
            try:
                with open(py_file, encoding='utf-8') as f:
                    code = f.read()
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        cc = 1
                        for child in ast.walk(node):
                            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                                cc += 1
                        if cc >= threshold:
                            complex_funcs.append({'file': str(py_file.relative_to(project_path)), 'function': node.name, 'line': node.lineno, 'complexity': cc})
            except:
                pass
        complex_funcs.sort(key=lambda x: x['complexity'], reverse=True)
        return {'success': True, 'data': {'functions': complex_funcs, 'count': len(complex_funcs)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def find_largest_files(project_path: str, top_n: int = 10) -> dict:
    """Find largest Python files in a project."""
    try:
        files = []
        for py_file in Path(project_path).rglob('*.py'):
            size = py_file.stat().st_size
            lines = sum(1 for _ in open(py_file, encoding='utf-8', errors='replace'))
            files.append({'file': str(py_file.relative_to(project_path)), 'size_bytes': size, 'lines': lines})
        files.sort(key=lambda x: x['lines'], reverse=True)
        return {'success': True, 'data': files[:top_n], 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def count_todos_in_project(project_path: str) -> dict:
    """Find all TODO/FIXME comments in a project."""
    try:
        todos = []
        pattern = re.compile(r'#\s*(TODO|FIXME|HACK|XXX|NOTE)[:\s]?(.*)', re.IGNORECASE)
        for py_file in Path(project_path).rglob('*.py'):
            with open(py_file, encoding='utf-8', errors='replace') as f:
                for i, line in enumerate(f, 1):
                    m = pattern.search(line)
                    if m:
                        todos.append({'file': str(py_file.relative_to(project_path)), 'line': i, 'type': m.group(1).upper(), 'text': m.group(2).strip()})
        return {'success': True, 'data': {'todos': todos, 'count': len(todos)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_file_change_frequency(project_path: str) -> dict:
    """Use git log to find most frequently changed files."""
    try:
        result = subprocess.run(['git', 'log', '--name-only', '--pretty=format:', '--diff-filter=M'], capture_output=True, text=True, cwd=project_path, timeout=15)
        if result.returncode != 0:
            return {'success': False, 'data': None, 'error': 'Git not available or not a repo'}
        from collections import Counter
        files = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        counts = Counter(files)
        return {'success': True, 'data': {'hotspots': [{'file': f, 'changes': c} for f, c in counts.most_common(20)]}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def check_code_duplication(project_path: str, min_lines: int = 10) -> dict:
    """Find duplicated blocks of code across Python files."""
    try:
        blocks = {}
        for py_file in Path(project_path).rglob('*.py'):
            with open(py_file, encoding='utf-8', errors='replace') as f:
                lines = [l.strip() for l in f.readlines() if l.strip() and not l.strip().startswith('#')]
            for i in range(len(lines) - min_lines + 1):
                block = tuple(lines[i:i+min_lines])
                if block not in blocks:
                    blocks[block] = []
                blocks[block].append({'file': str(py_file.relative_to(project_path)), 'start_line': i+1})
        dupes = [{'locations': v, 'sample': ' '.join(list(k)[:3]) + '...'} for k, v in blocks.items() if len(v) > 1]
        return {'success': True, 'data': {'duplicates': dupes[:20], 'count': len(dupes)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
