"""toolkit_95_dependency_analyzer.py
Analyze Python project dependencies — find imports, check versions, detect conflicts.
"""
import os
import re
import json
import subprocess
import sys
from pathlib import Path
import urllib.request

def find_imports_in_file(file_path: str) -> dict:
    """Parse a Python file and extract all imports."""
    try:
        with open(file_path, encoding='utf-8') as f:
            code = f.read()
        import ast
        tree = ast.parse(code)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({'module': alias.name.split('.')[0], 'full': alias.name, 'type': 'import', 'line': node.lineno})
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append({'module': node.module.split('.')[0], 'full': node.module, 'type': 'from', 'line': node.lineno})
        return {'success': True, 'data': imports, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def find_all_imports_in_project(project_path: str) -> dict:
    """Find all imports across all Python files in a project."""
    try:
        all_imports = {}
        for py_file in Path(project_path).rglob('*.py'):
            rel_path = str(py_file.relative_to(project_path))
            result = find_imports_in_file(str(py_file))
            if result['success']:
                for imp in result['data']:
                    mod = imp['module']
                    if mod not in all_imports:
                        all_imports[mod] = []
                    all_imports[mod].append(rel_path)
        return {'success': True, 'data': all_imports, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def check_missing_dependencies(project_path: str) -> dict:
    """Find imports that are not in requirements.txt."""
    try:
        import ast
        stdlib_modules = set(sys.stdlib_module_names) if hasattr(sys, 'stdlib_module_names') else set()
        result = find_all_imports_in_project(project_path)
        if not result['success']:
            return result
        all_imports = set(result['data'].keys())
        req_file = os.path.join(project_path, 'requirements.txt')
        declared = set()
        if os.path.exists(req_file):
            with open(req_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        pkg = re.split(r'[>=<!;]', line)[0].strip().lower().replace('-','_')
                        declared.add(pkg)
        missing = []
        for imp in all_imports:
            if imp.lower() in stdlib_modules:
                continue
            if imp.lower() not in declared and imp.lower().replace('-','_') not in declared:
                missing.append(imp)
        return {'success': True, 'data': {'missing': missing, 'count': len(missing)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def parse_requirements(file_path: str) -> dict:
    """Parse requirements.txt and return structured list."""
    try:
        with open(file_path, encoding='utf-8') as f:
            lines = f.readlines()
        packages = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            m = re.match(r'([A-Za-z0-9_.-]+)\s*([>=<!~]+)?\s*([A-Za-z0-9._*]+)?', line)
            if m:
                packages.append({'name': m.group(1), 'operator': m.group(2) or '', 'version': m.group(3) or '', 'raw': line})
        return {'success': True, 'data': packages, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_requirements(project_path: str, output_path: str = '') -> dict:
    """Generate requirements.txt from project imports using pip show."""
    try:
        result = find_all_imports_in_project(project_path)
        if not result['success']:
            return result
        stdlib = set(sys.stdlib_module_names) if hasattr(sys, 'stdlib_module_names') else set()
        external = [m for m in result['data'] if m not in stdlib]
        verified = []
        for pkg in external:
            r = subprocess.run([sys.executable, '-m', 'pip', 'show', pkg], capture_output=True, text=True)
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    if line.startswith('Version:'):
                        version = line.split(':',1)[1].strip()
                        verified.append(pkg + '>=' + version)
                        break
        content = '\n'.join(verified)
        if output_path:
            with open(output_path, 'w') as f:
                f.write(content)
        return {'success': True, 'data': {'requirements': verified, 'output_path': output_path}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def check_vulnerability(package: str, version: str = '') -> dict:
    """Check a package for known vulnerabilities via OSV.dev API."""
    try:
        payload = json.dumps({'package': {'name': package, 'ecosystem': 'PyPI'}, 'version': version}).encode()
        req = urllib.request.Request('https://api.osv.dev/v1/query', data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        vulns = data.get('vulns', [])
        return {'success': True, 'data': {'package': package, 'version': version, 'vulnerabilities': [{'id': v['id'], 'summary': v.get('summary','')} for v in vulns], 'count': len(vulns)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def audit_all_dependencies() -> dict:
    """Check all installed packages for vulnerabilities via OSV."""
    try:
        r = subprocess.run([sys.executable, '-m', 'pip', 'list', '--format=json'], capture_output=True, text=True)
        if r.returncode != 0:
            return {'success': False, 'data': None, 'error': r.stderr}
        packages = json.loads(r.stdout)
        issues = []
        for pkg in packages[:20]:
            result = check_vulnerability(pkg['name'], pkg['version'])
            if result['success'] and result['data']['count'] > 0:
                issues.append(result['data'])
        return {'success': True, 'data': {'vulnerable_packages': issues, 'checked': min(20, len(packages)), 'total_installed': len(packages)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def compare_requirements(file1: str, file2: str) -> dict:
    """Compare two requirements.txt files and find differences."""
    try:
        r1 = parse_requirements(file1)
        r2 = parse_requirements(file2)
        if not r1['success'] or not r2['success']:
            return {'success': False, 'data': None, 'error': 'Failed to parse requirements files'}
        pkgs1 = {p['name'].lower(): p for p in r1['data']}
        pkgs2 = {p['name'].lower(): p for p in r2['data']}
        only_in_1 = [v for k, v in pkgs1.items() if k not in pkgs2]
        only_in_2 = [v for k, v in pkgs2.items() if k not in pkgs1]
        version_diffs = []
        for k in set(pkgs1) & set(pkgs2):
            if pkgs1[k]['version'] != pkgs2[k]['version']:
                version_diffs.append({'package': k, 'v1': pkgs1[k]['version'], 'v2': pkgs2[k]['version']})
        return {'success': True, 'data': {'only_in_file1': only_in_1, 'only_in_file2': only_in_2, 'version_differences': version_diffs}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_package_license(package: str) -> dict:
    """Get the license of an installed package."""
    try:
        r = subprocess.run([sys.executable, '-m', 'pip', 'show', package], capture_output=True, text=True)
        if r.returncode == 0:
            info = {}
            for line in r.stdout.splitlines():
                k, _, v = line.partition(':')
                info[k.strip().lower()] = v.strip()
            return {'success': True, 'data': {'package': package, 'license': info.get('license', 'Unknown'), 'version': info.get('version', '')}, 'error': None}
        return {'success': False, 'data': None, 'error': 'Package not found'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_all_licenses() -> dict:
    """Get licenses for all installed packages."""
    try:
        r = subprocess.run([sys.executable, '-m', 'pip', 'list', '--format=json'], capture_output=True, text=True)
        packages = json.loads(r.stdout) if r.returncode == 0 else []
        results = []
        for pkg in packages:
            result = get_package_license(pkg['name'])
            if result['success']:
                results.append(result['data'])
        return {'success': True, 'data': results, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
