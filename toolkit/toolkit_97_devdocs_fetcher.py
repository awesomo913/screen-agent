"""toolkit_97_devdocs_fetcher.py
Fetch programming documentation from DevDocs, MDN, and language refs.
"""
import urllib.request
import urllib.parse
import json
import re

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

def _get(url, headers=None):
    try:
        h = {'User-Agent': 'Mozilla/5.0'}
        if headers:
            h.update(headers)
        if HAS_REQUESTS:
            r = requests.get(url, headers=h, timeout=15)
            return r.status_code, r.text
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return 0, str(e)

def _get_json(url):
    status, text = _get(url)
    try:
        return status, json.loads(text)
    except:
        return status, {'raw': text[:500]}

def search_devdocs(query: str, doc: str = 'python~3.11') -> dict:
    """Search DevDocs for a query in a specific documentation set."""
    try:
        q = urllib.parse.quote_plus(query)
        url = 'https://devdocs.io/docs/' + urllib.parse.quote(doc) + '/index.json'
        status, data = _get_json(url)
        if status == 200 and 'entries' in data:
            entries = data['entries']
            q_lower = query.lower()
            matches = [e for e in entries if q_lower in e.get('name','').lower() or q_lower in e.get('path','').lower()]
            matches = sorted(matches, key=lambda e: len(e.get('name','')))[:10]
            return {'success': True, 'data': [{'name': e['name'], 'type': e.get('type',''), 'path': e.get('path',''), 'url': 'https://devdocs.io/' + doc + '/' + e.get('path','')} for e in matches], 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_devdocs_sets() -> dict:
    """List available documentation sets on DevDocs."""
    try:
        status, data = _get_json('https://devdocs.io/docs/docs.json')
        if status == 200:
            docs = [{'name': d.get('name',''), 'slug': d.get('slug',''), 'version': d.get('release','')} for d in data if 'slug' in d]
            return {'success': True, 'data': docs, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_mdn_docs(query: str) -> dict:
    """Search MDN Web Docs for a JavaScript/HTML/CSS topic."""
    try:
        q = urllib.parse.quote_plus(query)
        url = 'https://developer.mozilla.org/api/v1/search?q=' + q + '&locale=en-US&size=5'
        status, data = _get_json(url)
        if status == 200:
            results = [{'title': r.get('title',''), 'summary': r.get('summary','')[:200], 'url': 'https://developer.mozilla.org' + r.get('mdn_url','')} for r in data.get('documents',[])]
            return {'success': True, 'data': results, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_python_docs(symbol: str) -> dict:
    """Get Python documentation for a built-in or stdlib symbol."""
    try:
        q = urllib.parse.quote_plus(symbol)
        url = 'https://docs.python.org/3/search.html?q=' + q + '&check_keywords=yes&area=default'
        status, html = _get(url)
        if status == 200:
            links = re.findall(r'href="(/3/[^"]+)".*?<b>([^<]+)</b>', html)
            results = [{'title': t, 'url': 'https://docs.python.org' + u} for u, t in links[:5]]
            return {'success': True, 'data': results, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_python_builtin_help(func_name: str) -> dict:
    """Get help text for a Python built-in using help() via subprocess."""
    try:
        import subprocess, sys
        code = 'import pydoc; print(pydoc.render_doc(' + repr(func_name) + ', renderer=pydoc.plaintext))'
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return {'success': True, 'data': result.stdout[:3000], 'error': None}
        return {'success': False, 'data': None, 'error': result.stderr[:500]}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_npm_readme(package: str) -> dict:
    """Get README/description of an npm package."""
    try:
        url = 'https://registry.npmjs.org/' + urllib.parse.quote(package, safe='')
        status, data = _get_json(url)
        if status == 200:
            latest = data.get('dist-tags', {}).get('latest', '')
            versions = data.get('versions', {})
            latest_info = versions.get(latest, {})
            return {'success': True, 'data': {'name': data.get('name'), 'description': data.get('description',''), 'latest_version': latest, 'homepage': latest_info.get('homepage',''), 'repository': latest_info.get('repository',{}).get('url','') if isinstance(latest_info.get('repository'), dict) else latest_info.get('repository',''), 'keywords': data.get('keywords',[])[:10]}, 'error': None}
        return {'success': False, 'data': None, 'error': 'Package not found'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_rust_docs(query: str) -> dict:
    """Search Rust standard library docs."""
    try:
        q = urllib.parse.quote_plus(query)
        url = 'https://doc.rust-lang.org/std/?search=' + q
        status, html = _get(url)
        if status == 200:
            results = re.findall(r'href="([^"]+)"[^>]*>([^<]+)</a>', html)[:10]
            return {'success': True, 'data': [{'name': n, 'url': 'https://doc.rust-lang.org/std/' + u if not u.startswith('http') else u} for u, n in results if n.strip()], 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def explain_http_status(code: int) -> dict:
    """Explain an HTTP status code."""
    try:
        codes = {100: 'Continue', 101: 'Switching Protocols', 200: 'OK', 201: 'Created', 202: 'Accepted', 204: 'No Content', 301: 'Moved Permanently', 302: 'Found', 304: 'Not Modified', 400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found', 405: 'Method Not Allowed', 408: 'Request Timeout', 409: 'Conflict', 410: 'Gone', 413: 'Content Too Large', 422: 'Unprocessable Content', 429: 'Too Many Requests', 500: 'Internal Server Error', 501: 'Not Implemented', 502: 'Bad Gateway', 503: 'Service Unavailable', 504: 'Gateway Timeout'}
        category = {1: 'Informational', 2: 'Success', 3: 'Redirection', 4: 'Client Error', 5: 'Server Error'}.get(code // 100, 'Unknown')
        return {'success': True, 'data': {'code': code, 'name': codes.get(code, 'Unknown'), 'category': category}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def lookup_error_code(code: str, language: str = 'python') -> dict:
    """Look up what an error code means for a given language."""
    try:
        q = urllib.parse.quote_plus(language + ' ' + code + ' error')
        url = 'https://api.duckduckgo.com/?q=' + q + '&format=json&no_html=1'
        status, data = _get_json(url)
        if status == 200:
            return {'success': True, 'data': {'code': code, 'language': language, 'abstract': data.get('AbstractText',''), 'answer': data.get('Answer','')}, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_go_pkg_docs(pkg_path: str) -> dict:
    """Fetch Go package documentation from pkg.go.dev."""
    try:
        url = 'https://pkg.go.dev/' + urllib.parse.quote(pkg_path, safe='/') + '?tab=doc'
        status, html = _get(url)
        if status == 200:
            title = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            synopsis = re.search(r'class="Documentation-overview"[^>]*>.*?<p>(.*?)</p>', html, re.DOTALL)
            return {'success': True, 'data': {'package': pkg_path, 'title': title.group(1).strip() if title else '', 'synopsis': re.sub(r'<[^>]+>','',synopsis.group(1)).strip()[:500] if synopsis else '', 'url': url}, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_pypi_classifiers() -> dict:
    """Get list of valid PyPI trove classifiers."""
    try:
        status, html = _get('https://pypi.org/classifiers/')
        if status == 200:
            classifiers = re.findall(r'<li[^>]*>([^<]+)</li>', html)
            classifiers = [c.strip() for c in classifiers if '::' in c]
            return {'success': True, 'data': classifiers[:50], 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
