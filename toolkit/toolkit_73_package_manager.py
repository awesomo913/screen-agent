"""toolkit_73_package_manager.py
Manage Python packages via pip — install, uninstall, upgrade, search, audit.
"""
import subprocess
import sys
import json
import re
import urllib.request

def _pip(args: list, timeout: int = 60) -> dict:
    try:
        result = subprocess.run([sys.executable, '-m', 'pip'] + args + ['--no-color'], capture_output=True, text=True, timeout=timeout)
        return {'stdout': result.stdout, 'stderr': result.stderr, 'code': result.returncode}
    except subprocess.TimeoutExpired:
        return {'stdout': '', 'stderr': 'Timeout', 'code': -1}
    except Exception as e:
        return {'stdout': '', 'stderr': str(e), 'code': -1}

def install_package(package: str, upgrade: bool = False, quiet: bool = True) -> dict:
    """Install a Python package via pip."""
    try:
        args = ['install', package]
        if upgrade:
            args.append('--upgrade')
        if quiet:
            args.append('-q')
        r = _pip(args)
        success = r['code'] == 0
        return {'success': success, 'data': {'stdout': r['stdout'], 'stderr': r['stderr']}, 'error': None if success else r['stderr']}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def uninstall_package(package: str) -> dict:
    """Uninstall a Python package."""
    try:
        r = _pip(['uninstall', package, '-y'])
        success = r['code'] == 0
        return {'success': success, 'data': r['stdout'], 'error': None if success else r['stderr']}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def upgrade_package(package: str) -> dict:
    """Upgrade a specific package."""
    return install_package(package, upgrade=True)

def upgrade_all_packages() -> dict:
    """List outdated packages and upgrade each."""
    try:
        r = _pip(['list', '--outdated', '--format=json'])
        if r['code'] != 0:
            return {'success': False, 'data': None, 'error': r['stderr']}
        outdated = json.loads(r['stdout'])
        results = []
        for pkg in outdated:
            name = pkg['name']
            res = install_package(name, upgrade=True)
            results.append({'package': name, 'success': res['success']})
        return {'success': True, 'data': results, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_installed(filter_str: str = '') -> dict:
    """List installed packages, optionally filtering by name."""
    try:
        r = _pip(['list', '--format=json'])
        if r['code'] != 0:
            return {'success': False, 'data': None, 'error': r['stderr']}
        pkgs = json.loads(r['stdout'])
        if filter_str:
            pkgs = [p for p in pkgs if filter_str.lower() in p['name'].lower()]
        return {'success': True, 'data': pkgs, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_outdated() -> dict:
    """List outdated packages."""
    try:
        r = _pip(['list', '--outdated', '--format=json'])
        if r['code'] != 0:
            return {'success': False, 'data': None, 'error': r['stderr']}
        return {'success': True, 'data': json.loads(r['stdout']), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def is_installed(package: str) -> dict:
    """Check if a package is installed."""
    try:
        r = _pip(['show', package])
        installed = r['code'] == 0 and bool(r['stdout'].strip())
        info = {}
        for line in r['stdout'].splitlines():
            if ':' in line:
                k, _, v = line.partition(':')
                info[k.strip().lower()] = v.strip()
        return {'success': True, 'data': {'installed': installed, 'info': info}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def show_package(package: str) -> dict:
    """Show detailed info about an installed package."""
    try:
        r = _pip(['show', package])
        if r['code'] != 0:
            return {'success': False, 'data': None, 'error': 'Package not found: ' + package}
        info = {}
        for line in r['stdout'].splitlines():
            if ':' in line:
                k, _, v = line.partition(':')
                info[k.strip().lower()] = v.strip()
        return {'success': True, 'data': info, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def freeze_requirements() -> dict:
    """Output installed packages in requirements.txt format."""
    try:
        r = _pip(['freeze'])
        if r['code'] == 0:
            lines = [l for l in r['stdout'].splitlines() if l.strip()]
            return {'success': True, 'data': {'requirements': lines, 'text': '\n'.join(lines)}, 'error': None}
        return {'success': False, 'data': None, 'error': r['stderr']}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def install_from_requirements(requirements_path: str) -> dict:
    """Install packages from a requirements.txt file."""
    try:
        r = _pip(['install', '-r', requirements_path], timeout=120)
        success = r['code'] == 0
        return {'success': success, 'data': r['stdout'], 'error': None if success else r['stderr']}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_pypi_info(package: str) -> dict:
    """Fetch package info from PyPI JSON API."""
    try:
        url = 'https://pypi.org/pypi/' + package + '/json'
        req = urllib.request.Request(url, headers={'Accept':'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        info = data.get('info', {})
        return {'success': True, 'data': {'name': info.get('name'), 'version': info.get('version'), 'summary': info.get('summary'), 'author': info.get('author'), 'license': info.get('license'), 'home_page': info.get('home_page'), 'requires_python': info.get('requires_python'), 'classifiers': info.get('classifiers',[])[:5]}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def search_pypi(query: str, max_results: int = 10) -> dict:
    """Search PyPI using the Simple API (name-only search)."""
    try:
        url = 'https://pypi.org/search/?q=' + urllib.request.quote(query) + '&format=json'
        req = urllib.request.Request('https://pypi.org/search/?q=' + urllib.request.quote(query), headers={'Accept':'application/json','User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        packages = re.findall(r'class="package-snippet__name"[^>]*>\s*([\w.-]+)\s*<', html)
        packages = list(dict.fromkeys(packages))[:max_results]
        return {'success': True, 'data': packages, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_package_versions(package: str) -> dict:
    """Get all available versions of a package from PyPI."""
    try:
        url = 'https://pypi.org/pypi/' + package + '/json'
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        versions = sorted(data.get('releases', {}).keys(), reverse=True)
        return {'success': True, 'data': {'package': package, 'versions': versions[:20], 'latest': data['info'].get('version')}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_virtualenv(path: str) -> dict:
    """Create a Python virtual environment at path."""
    try:
        result = subprocess.run([sys.executable, '-m', 'venv', path], capture_output=True, text=True, timeout=30)
        success = result.returncode == 0
        return {'success': success, 'data': {'path': path}, 'error': None if success else result.stderr}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_pip_version() -> dict:
    """Get current pip version."""
    try:
        r = _pip(['--version'])
        return {'success': True, 'data': r['stdout'].strip(), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def install_packages_batch(packages: list) -> dict:
    """Install multiple packages at once."""
    try:
        if not packages:
            return {'success': False, 'data': None, 'error': 'No packages specified'}
        r = _pip(['install'] + packages, timeout=120)
        success = r['code'] == 0
        return {'success': success, 'data': {'stdout': r['stdout'], 'packages': packages}, 'error': None if success else r['stderr']}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def audit_packages() -> dict:
    """Check installed packages for known vulnerabilities using pip-audit."""
    try:
        result = subprocess.run([sys.executable, '-m', 'pip_audit', '--format=json'], capture_output=True, text=True, timeout=60)
        if result.returncode in (0, 1):
            try:
                data = json.loads(result.stdout)
                return {'success': True, 'data': data, 'error': None}
            except:
                pass
        return {'success': False, 'data': None, 'error': result.stderr or 'pip-audit not installed'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
