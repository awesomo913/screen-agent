"""toolkit_77_markdown_tools.py
Convert, parse and validate Markdown — render to HTML, extract headings/links.
"""
import re
import urllib.request
import json

try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

def md_to_html_local(markdown_text: str, extensions: list = []) -> dict:
    """Convert Markdown to HTML using python-markdown library."""
    try:
        if HAS_MARKDOWN:
            exts = extensions or ['tables', 'fenced_code', 'nl2br']
            html = markdown.markdown(markdown_text, extensions=exts)
            return {'success': True, 'data': html, 'error': None}
        return {'success': False, 'data': None, 'error': 'python-markdown not installed. Run: pip install markdown'}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def md_to_html_github(markdown_text: str) -> dict:
    """Convert Markdown to HTML via GitHub API (public, rate-limited)."""
    try:
        payload = json.dumps({'text': markdown_text, 'mode': 'markdown'}).encode()
        req = urllib.request.Request('https://api.github.com/markdown', data=payload, headers={'Content-Type':'application/json','Accept':'application/vnd.github+json','User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8')
        return {'success': True, 'data': html, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def md_to_html_basic(markdown_text: str) -> dict:
    """Basic Markdown to HTML conversion using regex (no dependencies)."""
    try:
        text = markdown_text
        text = re.sub(r'^#{6}\s+(.+)$', r'<h6>\1</h6>', text, flags=re.MULTILINE)
        text = re.sub(r'^#{5}\s+(.+)$', r'<h5>\1</h5>', text, flags=re.MULTILINE)
        text = re.sub(r'^#{4}\s+(.+)$', r'<h4>\1</h4>', text, flags=re.MULTILINE)
        text = re.sub(r'^#{3}\s+(.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^#{2}\s+(.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
        text = re.sub(r'!\[([^\]]+)\]\(([^)]+)\)', r'<img alt="\1" src="\2">', text)
        text = re.sub(r'^[-*+]\s+(.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
        text = re.sub(r'^>\s+(.+)$', r'<blockquote>\1</blockquote>', text, flags=re.MULTILINE)
        text = re.sub(r'\n\n', '</p><p>', text)
        text = '<p>' + text + '</p>'
        return {'success': True, 'data': text, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def extract_headings(markdown_text: str) -> dict:
    """Extract all headings from Markdown and return as TOC."""
    try:
        pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        headings = []
        for m in pattern.finditer(markdown_text):
            level = len(m.group(1))
            text = m.group(2).strip()
            anchor = re.sub(r'[^\w\s-]', '', text.lower()).strip().replace(' ', '-')
            headings.append({'level': level, 'text': text, 'anchor': '#' + anchor})
        return {'success': True, 'data': headings, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def extract_links(markdown_text: str) -> dict:
    """Extract all links from Markdown."""
    try:
        inline = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', markdown_text)
        ref_defs = re.findall(r'^\[([^\]]+)\]:\s*(.+)$', markdown_text, re.MULTILINE)
        links = [{'text': t, 'url': u, 'type': 'inline'} for t, u in inline]
        links += [{'text': t, 'url': u.strip(), 'type': 'reference'} for t, u in ref_defs]
        return {'success': True, 'data': links, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def extract_images(markdown_text: str) -> dict:
    """Extract all image references from Markdown."""
    try:
        images = re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', markdown_text)
        return {'success': True, 'data': [{'alt': a, 'src': s} for a, s in images], 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def extract_code_blocks(markdown_text: str) -> dict:
    """Extract fenced code blocks from Markdown."""
    try:
        pattern = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
        blocks = []
        for m in pattern.finditer(markdown_text):
            blocks.append({'language': m.group(1) or 'text', 'code': m.group(2).strip()})
        inline = re.findall(r'`([^`]+)`', markdown_text)
        return {'success': True, 'data': {'fenced_blocks': blocks, 'inline_code': inline}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def extract_tables(markdown_text: str) -> dict:
    """Extract Markdown tables and parse as list of dicts."""
    try:
        table_pattern = re.compile(r'(\|.+\|\n\|[-| :]+\|\n(?:\|.+\|\n?)+)', re.MULTILINE)
        tables = []
        for m in table_pattern.finditer(markdown_text):
            lines = [l for l in m.group().splitlines() if l.strip()]
            headers = [h.strip() for h in lines[0].split('|') if h.strip()]
            rows = []
            for line in lines[2:]:
                cells = [c.strip() for c in line.split('|') if c.strip()]
                if cells:
                    rows.append(dict(zip(headers, cells)))
            tables.append({'headers': headers, 'rows': rows})
        return {'success': True, 'data': tables, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def md_word_count(markdown_text: str) -> dict:
    """Count words in Markdown (excluding markup)."""
    try:
        text = re.sub(r'```.*?```', '', markdown_text, flags=re.DOTALL)
        text = re.sub(r'`[^`]+`', '', text)
        text = re.sub(r'#+ ', '', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = re.sub(r'[*_~]', '', text)
        words = text.split()
        return {'success': True, 'data': {'words': len(words), 'chars': len(text)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def generate_toc(markdown_text: str) -> dict:
    """Generate a table of contents in Markdown from headings."""
    try:
        result = extract_headings(markdown_text)
        if not result['success']:
            return result
        lines = []
        for h in result['data']:
            indent = '  ' * (h['level'] - 1)
            lines.append(indent + '- [' + h['text'] + '](' + h['anchor'] + ')')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def validate_links(markdown_text: str, check_http: bool = False) -> dict:
    """Validate links in Markdown — find broken/empty ones."""
    try:
        links_result = extract_links(markdown_text)
        if not links_result['success']:
            return links_result
        issues = []
        for link in links_result['data']:
            url = link['url']
            if not url or url.startswith('javascript:'):
                issues.append({'url': url, 'issue': 'invalid or empty URL'})
            elif check_http and url.startswith('http'):
                try:
                    req = urllib.request.Request(url, method='HEAD', headers={'User-Agent':'Mozilla/5.0'})
                    urllib.request.urlopen(req, timeout=5)
                except Exception as e:
                    issues.append({'url': url, 'issue': str(e)})
        return {'success': True, 'data': {'total': len(links_result['data']), 'issues': issues}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def html_to_md_basic(html_text: str) -> dict:
    """Basic HTML to Markdown conversion."""
    try:
        text = html_text
        text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1', text, flags=re.DOTALL)
        text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1', text, flags=re.DOTALL)
        text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1', text, flags=re.DOTALL)
        text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL)
        text = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', text, flags=re.DOTALL)
        text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text, flags=re.DOTALL)
        text = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', text, flags=re.DOTALL)
        text = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', text, flags=re.DOTALL)
        text = re.sub(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.DOTALL)
        text = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*src="([^"]*)"[^>]*/>', r'![\1](\2)', text)
        text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1', text, flags=re.DOTALL)
        text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n', text, flags=re.DOTALL)
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return {'success': True, 'data': text.strip(), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def md_to_pdf_url(markdown_text: str) -> dict:
    """Get a URL to render Markdown as PDF (using md2pdf.io)."""
    try:
        import urllib.parse
        encoded = urllib.parse.quote(markdown_text)
        url = 'https://md2pdf.netlify.app/?md=' + encoded[:2000]
        return {'success': True, 'data': {'url': url, 'note': 'Open URL in browser to get PDF'}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
