"""toolkit_72_github_api.py
Interact with GitHub API — repos, gists, issues, search code.
"""
import json
import urllib.request
import urllib.parse
import urllib.error

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

_BASE = 'https://api.github.com'

def _get(path, token=''):
    try:
        headers = {'Accept':'application/vnd.github+json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        url = _BASE + path
        if HAS_REQUESTS:
            r = requests.get(url, headers=headers, timeout=15)
            return r.status_code, r.json()
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except Exception as e:
        return 0, {'error': str(e)}

def _post(path, payload, token=''):
    try:
        headers = {'Accept':'application/vnd.github+json','Content-Type':'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        url = _BASE + path
        data = json.dumps(payload).encode()
        if HAS_REQUESTS:
            r = requests.post(url, headers=headers, json=payload, timeout=15)
            return r.status_code, r.json()
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except Exception as e:
        return 0, {'error': str(e)}

def get_user(username: str, token: str = '') -> dict:
    """Get GitHub user profile."""
    try:
        status, data = _get('/users/' + username, token)
        if status == 200:
            return {'success': True, 'data': {'login': data.get('login'), 'name': data.get('name'), 'bio': data.get('bio'), 'public_repos': data.get('public_repos'), 'followers': data.get('followers'), 'following': data.get('following'), 'url': data.get('html_url')}, 'error': None}
        return {'success': False, 'data': None, 'error': data.get('message', 'HTTP ' + str(status))}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_repos(username: str, token: str = '', per_page: int = 30) -> dict:
    """List public repos for a user."""
    try:
        status, data = _get('/users/' + username + '/repos?per_page=' + str(per_page) + '&sort=updated', token)
        if status == 200:
            repos = [{'name': r['name'], 'description': r.get('description'), 'stars': r.get('stargazers_count',0), 'language': r.get('language'), 'url': r.get('html_url')} for r in data]
            return {'success': True, 'data': repos, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_repo(owner: str, repo: str, token: str = '') -> dict:
    """Get repo details."""
    try:
        status, data = _get('/repos/' + owner + '/' + repo, token)
        if status == 200:
            return {'success': True, 'data': {'name': data.get('name'), 'description': data.get('description'), 'stars': data.get('stargazers_count',0), 'forks': data.get('forks_count',0), 'language': data.get('language'), 'open_issues': data.get('open_issues_count',0), 'url': data.get('html_url'), 'default_branch': data.get('default_branch')}, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_issues(owner: str, repo: str, state: str = 'open', token: str = '') -> dict:
    """List issues for a repo."""
    try:
        status, data = _get('/repos/' + owner + '/' + repo + '/issues?state=' + state + '&per_page=30', token)
        if status == 200:
            issues = [{'number': i['number'], 'title': i['title'], 'state': i['state'], 'author': i['user']['login'], 'url': i['html_url']} for i in data if 'pull_request' not in i]
            return {'success': True, 'data': issues, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_issue(owner: str, repo: str, title: str, body: str = '', token: str = '') -> dict:
    """Create a GitHub issue."""
    try:
        status, data = _post('/repos/' + owner + '/' + repo + '/issues', {'title': title, 'body': body}, token)
        if status == 201:
            return {'success': True, 'data': {'number': data.get('number'), 'url': data.get('html_url')}, 'error': None}
        return {'success': False, 'data': None, 'error': data.get('message', 'HTTP ' + str(status))}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def search_repos(query: str, sort: str = 'stars', per_page: int = 10, token: str = '') -> dict:
    """Search GitHub repositories."""
    try:
        q = urllib.parse.quote(query)
        status, data = _get('/search/repositories?q=' + q + '&sort=' + sort + '&per_page=' + str(per_page), token)
        if status == 200:
            items = [{'name': r['full_name'], 'description': r.get('description'), 'stars': r.get('stargazers_count',0), 'language': r.get('language'), 'url': r.get('html_url')} for r in data.get('items', [])]
            return {'success': True, 'data': {'total': data.get('total_count',0), 'items': items}, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def search_code(query: str, token: str = '') -> dict:
    """Search code on GitHub (requires token)."""
    try:
        q = urllib.parse.quote(query)
        status, data = _get('/search/code?q=' + q + '&per_page=10', token)
        if status == 200:
            items = [{'path': i.get('path'), 'repo': i['repository']['full_name'], 'url': i.get('html_url')} for i in data.get('items', [])]
            return {'success': True, 'data': {'total': data.get('total_count',0), 'items': items}, 'error': None}
        return {'success': False, 'data': None, 'error': data.get('message', 'HTTP ' + str(status))}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_file_content(owner: str, repo: str, path: str, token: str = '') -> dict:
    """Get file content from a GitHub repo."""
    try:
        import base64
        status, data = _get('/repos/' + owner + '/' + repo + '/contents/' + path, token)
        if status == 200 and data.get('encoding') == 'base64':
            content = base64.b64decode(data['content']).decode('utf-8', errors='replace')
            return {'success': True, 'data': {'content': content, 'size': data.get('size'), 'sha': data.get('sha')}, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_commits(owner: str, repo: str, per_page: int = 10, token: str = '') -> dict:
    """List recent commits for a repo."""
    try:
        status, data = _get('/repos/' + owner + '/' + repo + '/commits?per_page=' + str(per_page), token)
        if status == 200:
            commits = [{'sha': c['sha'][:7], 'message': c['commit']['message'].split('\n')[0], 'author': c['commit']['author']['name'], 'date': c['commit']['author']['date']} for c in data]
            return {'success': True, 'data': commits, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_releases(owner: str, repo: str, token: str = '') -> dict:
    """List releases for a repo."""
    try:
        status, data = _get('/repos/' + owner + '/' + repo + '/releases?per_page=10', token)
        if status == 200:
            releases = [{'tag': r['tag_name'], 'name': r.get('name'), 'published': r.get('published_at'), 'url': r.get('html_url')} for r in data]
            return {'success': True, 'data': releases, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def create_gist(description: str, filename: str, content: str, public: bool = True, token: str = '') -> dict:
    """Create a GitHub Gist."""
    try:
        status, data = _post('/gists', {'description': description, 'public': public, 'files': {filename: {'content': content}}}, token)
        if status == 201:
            return {'success': True, 'data': {'id': data.get('id'), 'url': data.get('html_url')}, 'error': None}
        return {'success': False, 'data': None, 'error': data.get('message', 'HTTP ' + str(status))}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_gist(gist_id: str, token: str = '') -> dict:
    """Get a Gist by ID."""
    try:
        status, data = _get('/gists/' + gist_id, token)
        if status == 200:
            files = {name: f.get('content','') for name, f in data.get('files',{}).items()}
            return {'success': True, 'data': {'description': data.get('description'), 'files': files, 'url': data.get('html_url')}, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_rate_limit(token: str = '') -> dict:
    """Check GitHub API rate limit."""
    try:
        status, data = _get('/rate_limit', token)
        if status == 200:
            core = data.get('resources', {}).get('core', {})
            search = data.get('resources', {}).get('search', {})
            return {'success': True, 'data': {'core': core, 'search': search}, 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def list_branches(owner: str, repo: str, token: str = '') -> dict:
    """List branches in a repo."""
    try:
        status, data = _get('/repos/' + owner + '/' + repo + '/branches', token)
        if status == 200:
            return {'success': True, 'data': [{'name': b['name'], 'sha': b['commit']['sha'][:7]} for b in data], 'error': None}
        return {'success': False, 'data': None, 'error': str(data)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_trending_repos(language: str = '', since: str = 'daily') -> dict:
    """Get trending repos from GitHub Trending (unofficial scrape)."""
    try:
        url = 'https://github.com/trending'
        if language:
            url += '/' + urllib.parse.quote(language)
        url += '?since=' + since
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        import re
        repos = re.findall(r'href="/([\w.-]+/[\w.-]+)".*?class="[^"]*f6[^"]*"', html)
        repos = list(dict.fromkeys(repos))[:20]
        return {'success': True, 'data': {'repos': repos, 'count': len(repos)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
