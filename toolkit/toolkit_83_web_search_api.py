"""toolkit_83_web_search_api.py
Search the web via free/public APIs — DuckDuckGo, Brave, Serper, SerpAPI.
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
        h = headers or {'User-Agent': 'Mozilla/5.0'}
        if HAS_REQUESTS:
            r = requests.get(url, headers=h, timeout=15)
            return r.status_code, r.text
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return 0, str(e)

def _get_json(url, headers=None):
    status, text = _get(url, headers)
    try:
        return status, json.loads(text)
    except:
        return status, {'raw': text}

def search_duckduckgo(query: str, max_results: int = 10) -> dict:
    """Search via DuckDuckGo Instant Answer API."""
    try:
        q = urllib.parse.quote_plus(query)
        url = 'https://api.duckduckgo.com/?q=' + q + '&format=json&no_html=1&skip_disambig=1'
        status, data = _get_json(url)
        if status == 200:
            results = []
            for r in data.get('RelatedTopics', [])[:max_results]:
                if 'Text' in r and 'FirstURL' in r:
                    results.append({'title': r['Text'][:100], 'url': r['FirstURL']})
            return {'success': True, 'data': {'abstract': data.get('AbstractText',''), 'abstract_url': data.get('AbstractURL',''), 'answer': data.get('Answer',''), 'related': results, 'query': query}, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def search_duckduckgo_html(query: str, max_results: int = 10) -> dict:
    """Scrape DuckDuckGo HTML search results."""
    try:
        q = urllib.parse.quote_plus(query)
        url = 'https://html.duckduckgo.com/html/?q=' + q
        status, html = _get(url, {'User-Agent': 'Mozilla/5.0'})
        if status == 200:
            titles = re.findall(r'class="result__a"[^>]*>([^<]+)<', html)
            urls = re.findall(r'href="(https?://[^"]+)"', html)
            snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', html)
            results = []
            for i in range(min(max_results, len(titles), len(urls))):
                results.append({'title': titles[i].strip() if i < len(titles) else '', 'url': urls[i] if i < len(urls) else '', 'snippet': snippets[i].strip() if i < len(snippets) else ''})
            return {'success': True, 'data': results, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def search_bing(query: str, api_key: str, max_results: int = 10) -> dict:
    """Search via Bing Web Search API (requires API key)."""
    try:
        q = urllib.parse.quote_plus(query)
        url = 'https://api.bing.microsoft.com/v7.0/search?q=' + q + '&count=' + str(max_results)
        status, data = _get_json(url, {'Ocp-Apim-Subscription-Key': api_key})
        if status == 200:
            items = data.get('webPages', {}).get('value', [])
            results = [{'title': i.get('name',''), 'url': i.get('url',''), 'snippet': i.get('snippet','')} for i in items]
            return {'success': True, 'data': results, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def search_serper(query: str, api_key: str, max_results: int = 10) -> dict:
    """Search via Serper.dev Google Search API."""
    try:
        import json
        body = json.dumps({'q': query, 'num': max_results}).encode()
        req = urllib.request.Request('https://google.serper.dev/search', data=body, headers={'X-API-KEY': api_key, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        results = [{'title': r.get('title',''), 'url': r.get('link',''), 'snippet': r.get('snippet','')} for r in data.get('organic', [])]
        return {'success': True, 'data': results, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def search_wikipedia(query: str, max_results: int = 5) -> dict:
    """Search Wikipedia articles."""
    try:
        q = urllib.parse.quote_plus(query)
        url = 'https://en.wikipedia.org/w/api.php?action=search&list=search&srsearch=' + q + '&srlimit=' + str(max_results) + '&format=json'
        status, data = _get_json(url)
        if status == 200:
            items = data.get('query', {}).get('search', [])
            results = [{'title': i['title'], 'snippet': re.sub(r'<[^>]+>','',i.get('snippet','')), 'url': 'https://en.wikipedia.org/wiki/' + urllib.parse.quote(i['title'].replace(' ','_'))} for i in items]
            return {'success': True, 'data': results, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_wikipedia_summary(title: str) -> dict:
    """Get Wikipedia article summary."""
    try:
        t = urllib.parse.quote(title.replace(' ','_'))
        url = 'https://en.wikipedia.org/api/rest_v1/page/summary/' + t
        status, data = _get_json(url)
        if status == 200:
            return {'success': True, 'data': {'title': data.get('title',''), 'extract': data.get('extract',''), 'url': data.get('content_urls',{}).get('desktop',{}).get('page',''), 'thumbnail': data.get('thumbnail',{}).get('source','') if data.get('thumbnail') else ''}, 'error': None}
        return {'success': False, 'data': None, 'error': 'Article not found: ' + title}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def search_npm(query: str, max_results: int = 10) -> dict:
    """Search npm packages."""
    try:
        q = urllib.parse.quote_plus(query)
        url = 'https://registry.npmjs.org/-/v1/search?text=' + q + '&size=' + str(max_results)
        status, data = _get_json(url)
        if status == 200:
            packages = [{'name': o['package']['name'], 'description': o['package'].get('description',''), 'version': o['package'].get('version',''), 'url': 'https://www.npmjs.com/package/' + o['package']['name']} for o in data.get('objects',[])]
            return {'success': True, 'data': packages, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def search_pypi(query: str) -> dict:
    """Search PyPI packages."""
    try:
        q = urllib.parse.quote_plus(query)
        url = 'https://pypi.org/search/?q=' + q
        status, html = _get(url, {'User-Agent': 'Mozilla/5.0'})
        if status == 200:
            names = re.findall(r'class="package-snippet__name"[^>]*>\s*([\w.\-]+)\s*</span>', html)[:10]
            descs = re.findall(r'class="package-snippet__description"[^>]*>\s*([^<]{1,200})\s*</p>', html)[:10]
            results = [{'name': n, 'description': descs[i] if i < len(descs) else '', 'url': 'https://pypi.org/project/' + n} for i, n in enumerate(names)]
            return {'success': True, 'data': results, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def fetch_url_content(url: str, max_chars: int = 5000) -> dict:
    """Fetch and clean text content from a URL."""
    try:
        status, html = _get(url)
        if status == 200:
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return {'success': True, 'data': {'text': text[:max_chars], 'url': url, 'total_chars': len(text)}, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def get_page_title_and_description(url: str) -> dict:
    """Get title and meta description from a web page."""
    try:
        status, html = _get(url)
        if status == 200:
            title_m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
            desc_m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^\'"]+)', html, re.IGNORECASE)
            if not desc_m:
                desc_m = re.search(r'<meta[^>]*content=["\']([^\'"]+)["\'][^>]*name=["\']description', html, re.IGNORECASE)
            return {'success': True, 'data': {'title': title_m.group(1).strip() if title_m else '', 'description': desc_m.group(1).strip() if desc_m else '', 'url': url}, 'error': None}
        return {'success': False, 'data': None, 'error': 'HTTP ' + str(status)}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
