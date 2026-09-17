"""toolkit_120_pypi_downloader.py
Download packages from PyPI, inspect wheels, extract metadata.
"""
import urllib.request
import urllib.parse
import json
import os
import re
import zipfile
import subprocess
import sys

def get_package_info(package: str, version: str = '') -> dict:
    """Fetch full package info from PyPI JSON API."""
    try:
        path = '/pypi/' + package + '/' + version + '/json' if version else '/pypi/' + package + '/json'
        req = urllib.request.Request('https://pypi.org' + path, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        info = data['info']
        return {'success': True, 'data': {'name': info.get('name'), 'version': info.get('version'), 'summary': info.get('summary'), 'author': info.get('author'), 'license': info.get('license'), 'requires_python': info.get('requires_python'), 'keywords': info.get('keywords'), 'classifiers': info.get('classifiers', [])[:5], 'project_urls': info.get('project_urls', {}), 'requires_dist': info.get('requires_dist', [])[:10]}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_latest_version(package: str) -> dict:
    """Get the latest version of a PyPI package."""
    try:
        req = urllib.request.Request('https://pypi.org/pypi/' + package + '/json')
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        latest = data['info']['version']
        return {'success': True, 'data': {'package': package, 'latest': latest}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_package_versions(package: str, max_versions: int = 20) -> dict:
    """List available versions for a PyPI package."""
    try:
        req = urllib.request.Request('https://pypi.org/pypi/' + package + '/json')
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        versions = sorted(data.get('releases', {}).keys(), reverse=True)[:max_versions]
        return {'success': True, 'data': {'package': package, 'versions': versions}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_download_url(package: str, version: str = '', distribution: str = 'sdist') -> dict:
    """Get download URL for a package. distribution: sdist or wheel."""
    try:
        path = '/pypi/' + package + '/' + version + '/json' if version else '/pypi/' + package + '/json'
        req = urllib.request.Request('https://pypi.org' + path)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        ver = version or data['info']['version']
        urls = data.get('releases', {}).get(ver, [])
        if not urls:
            urls = [u for u in data.get('urls', [])]
        dist_types = {'wheel': 'bdist_wheel', 'sdist': 'sdist'}
        target_type = dist_types.get(distribution, distribution)
        matches = [u for u in urls if u.get('packagetype') == target_type]
        if not matches:
            matches = urls
        if matches:
            url_info = matches[0]
            return {'success': True, 'data': {'url': url_info.get('url'), 'filename': url_info.get('filename'), 'size': url_info.get('size'), 'md5': url_info.get('md5_digest'), 'python_version': url_info.get('python_version')}, 'error': None}
        return {'success': False, 'data': None, 'error': 'No download found'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def download_package(package: str, output_dir: str = '.', version: str = '') -> dict:
    """Download a package source distribution."""
    try:
        url_result = get_download_url(package, version, 'sdist')
        if not url_result['success']:
            url_result = get_download_url(package, version, 'wheel')
        if not url_result['success']:
            return url_result
        url = url_result['data']['url']
        filename = url_result['data']['filename']
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)
        urllib.request.urlretrieve(url, output_path)
        size = os.path.getsize(output_path)
        return {'success': True, 'data': {'path': output_path, 'filename': filename, 'size': size}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def inspect_wheel(wheel_path: str) -> dict:
    """Inspect contents of a .whl (zip) file."""
    try:
        with zipfile.ZipFile(wheel_path) as zf:
            names = zf.namelist()
            metadata = ''
            for name in names:
                if name.endswith('METADATA') or name.endswith('PKG-INFO'):
                    metadata = zf.read(name).decode('utf-8', errors='replace')[:2000]
                    break
            return {'success': True, 'data': {'files': names[:50], 'total_files': len(names), 'metadata_preview': metadata[:500]}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_package_dependencies(package: str, version: str = '') -> dict:
    """Get declared dependencies for a package."""
    try:
        result = get_package_info(package, version)
        if not result['success']:
            return result
        deps = result['data'].get('requires_dist', [])
        parsed = []
        for dep in (deps or []):
            m = re.match(r'^([A-Za-z0-9_.-]+)', dep)
            if m:
                parsed.append({'name': m.group(1), 'full': dep})
        return {'success': True, 'data': {'dependencies': parsed, 'count': len(parsed)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def search_pypi_packages(query: str, max_results: int = 10) -> dict:
    """Search for packages on PyPI."""
    try:
        q = urllib.parse.quote_plus(query)
        req = urllib.request.Request('https://pypi.org/search/?q=' + q, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        names = re.findall(r'class="package-snippet__name"[^>]*>\s*([\w.\-]+)\s*</span>', html)[:max_results]
        descs = re.findall(r'class="package-snippet__description"[^>]*>\s*([^<]{1,200})\s*</p>', html)[:max_results]
        results = [{'name': n, 'description': descs[i] if i < len(descs) else '', 'url': 'https://pypi.org/project/' + n} for i, n in enumerate(names)]
        return {'success': True, 'data': results, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def compare_package_versions(package: str, v1: str, v2: str) -> dict:
    """Compare two versions of a package — find new/removed dependencies."""
    try:
        info1 = get_package_dependencies(package, v1)
        info2 = get_package_dependencies(package, v2)
        if not info1['success'] or not info2['success']:
            return {'success': False, 'data': None, 'error': 'Could not fetch one or both versions'}
        deps1 = set(d['name'] for d in info1['data']['dependencies'])
        deps2 = set(d['name'] for d in info2['data']['dependencies'])
        return {'success': True, 'data': {'added': list(deps2 - deps1), 'removed': list(deps1 - deps2), 'same': list(deps1 & deps2), 'v1': v1, 'v2': v2}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_package_stats(package: str) -> dict:
    """Get download stats for a package from pypistats.org."""
    try:
        url = 'https://pypistats.org/api/packages/' + package.lower() + '/recent'
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return {'success': True, 'data': data.get('data', {}), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def install_from_url(url: str) -> dict:
    """Install a package directly from a URL."""
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', url, '-q'], capture_output=True, text=True, timeout=60)
        return {'success': result.returncode == 0, 'data': result.stdout, 'error': result.stderr if result.returncode != 0 else None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_changelog_url(package: str) -> dict:
    """Try to find the changelog URL for a package."""
    try:
        result = get_package_info(package)
        if not result['success']:
            return result
        urls = result['data'].get('project_urls', {})
        for key in ['Changelog', 'CHANGELOG', 'Release Notes', 'History', 'Changes']:
            if key in urls:
                return {'success': True, 'data': {'url': urls[key], 'key': key}, 'error': None}
        home = urls.get('Homepage', '')
        if 'github.com' in home:
            return {'success': True, 'data': {'url': home + '/blob/main/CHANGELOG.md', 'key': 'inferred_github'}, 'error': None}
        return {'success': True, 'data': {'url': None, 'note': 'Changelog URL not found in metadata'}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
