"""
toolkit_41_web_scraper.py
Fetch and parse web pages: HTTP requests, HTML parsing, link extraction,
text extraction, table parsing, and form discovery. Soft-import requests/bs4.
"""
from __future__ import annotations
import urllib.request
import urllib.error
import urllib.parse
import html.parser
import re
import json
from typing import Any, Dict, List

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

def _get_url(url: str, timeout: int = 15) -> tuple:
    """Fetch URL using requests or urllib fallback. Returns (content_str, status_code, error)."""
    try:
        if HAS_REQUESTS:
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            return resp.text, resp.status_code, None
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace"), resp.status, None
    except Exception as e:
        return None, None, str(e)

def fetch_page(url: str, timeout: int = 15) -> Dict[str, Any]:
    try:
        content, status, error = _get_url(url, timeout)
        if error:
            return {"success": False, "data": None, "error": error}
        return {"success": True, "data": {"url": url, "status": status, "length": len(content), "content": content[:10000]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_page_title(url: str) -> Dict[str, Any]:
    try:
        content, status, error = _get_url(url)
        if error:
            return {"success": False, "data": None, "error": error}
        m = re.search(r"<title[^>]*>([^<]+)</title>", content, re.IGNORECASE)
        title = m.group(1).strip() if m else ""
        return {"success": True, "data": {"title": title, "url": url}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_text_from_url(url: str) -> Dict[str, Any]:
    try:
        content, status, error = _get_url(url)
        if error:
            return {"success": False, "data": None, "error": error}
        if HAS_BS4:
            soup = BeautifulSoup(content, "html.parser")
            for tag in soup(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
        else:
            text = re.sub(r"<[^>]+>", "", content)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return {"success": True, "data": {"text": text[:5000], "chars": len(text)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_links(url: str) -> Dict[str, Any]:
    try:
        content, status, error = _get_url(url)
        if error:
            return {"success": False, "data": None, "error": error}
        if HAS_BS4:
            soup = BeautifulSoup(content, "html.parser")
            links = [{"href": a.get("href", ""), "text": a.get_text(strip=True)} for a in soup.find_all("a", href=True)]
        else:
            raw = re.findall(r'href=["\']([^"\']+)["\']', content, re.IGNORECASE)
            links = [{"href": h, "text": ""} for h in raw]
        base = url
        abs_links = []
        for link in links:
            href = link["href"]
            if href.startswith("http"):
                abs_links.append(link)
            elif href.startswith("/"):
                parsed = urllib.parse.urlparse(base)
                link["href"] = parsed.scheme + "://" + parsed.netloc + href
                abs_links.append(link)
        return {"success": True, "data": {"count": len(abs_links), "links": abs_links[:100]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_images(url: str) -> Dict[str, Any]:
    try:
        content, status, error = _get_url(url)
        if error:
            return {"success": False, "data": None, "error": error}
        if HAS_BS4:
            soup = BeautifulSoup(content, "html.parser")
            imgs = [{"src": img.get("src", ""), "alt": img.get("alt", "")} for img in soup.find_all("img")]
        else:
            srcs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE)
            imgs = [{"src": s, "alt": ""} for s in srcs]
        return {"success": True, "data": {"count": len(imgs), "images": imgs[:100]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_meta_tags(url: str) -> Dict[str, Any]:
    try:
        content, status, error = _get_url(url)
        if error:
            return {"success": False, "data": None, "error": error}
        if HAS_BS4:
            soup = BeautifulSoup(content, "html.parser")
            meta = {}
            for tag in soup.find_all("meta"):
                name = tag.get("name") or tag.get("property", "")
                content_ = tag.get("content", "")
                if name:
                    meta[name] = content_
        else:
            metas = re.findall(r'<meta[^>]+>', content, re.IGNORECASE)
            meta = {}
            for m in metas:
                nm = re.search(r'name=["\']([^"\']+)["\']', m, re.IGNORECASE)
                ct = re.search(r'content=["\']([^"\']+)["\']', m, re.IGNORECASE)
                if nm and ct:
                    meta[nm.group(1)] = ct.group(1)
        return {"success": True, "data": meta, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_tables(url: str) -> Dict[str, Any]:
    try:
        content, status, error = _get_url(url)
        if error:
            return {"success": False, "data": None, "error": error}
        if not HAS_BS4:
            return {"success": False, "data": None, "error": "BeautifulSoup4 required (pip install beautifulsoup4)"}
        soup = BeautifulSoup(content, "html.parser")
        tables = []
        for table in soup.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                rows.append(cells)
            tables.append(rows)
        return {"success": True, "data": {"table_count": len(tables), "tables": tables[:5]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_status_code(url: str) -> Dict[str, Any]:
    try:
        _, status, error = _get_url(url)
        if error:
            return {"success": False, "data": None, "error": error}
        return {"success": True, "data": {"url": url, "status_code": status}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def post_json(url: str, data: dict, headers: dict = {}) -> Dict[str, Any]:
    try:
        if not HAS_REQUESTS:
            return {"success": False, "data": None, "error": "requests not installed (pip install requests)"}
        hdrs = {"Content-Type": "application/json", **headers}
        resp = requests.post(url, json=data, headers=hdrs, timeout=15)
        try:
            resp_data = resp.json()
        except Exception:
            resp_data = resp.text
        return {"success": True, "data": {"status": resp.status_code, "response": resp_data}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_json(url: str, params: dict = {}) -> Dict[str, Any]:
    try:
        if not HAS_REQUESTS:
            return {"success": False, "data": None, "error": "requests not installed"}
        resp = requests.get(url, params=params, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        return {"success": True, "data": {"status": resp.status_code, "json": resp.json()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def download_file(url: str, output_path: str) -> Dict[str, Any]:
    try:
        if HAS_REQUESTS:
            resp = requests.get(url, stream=True, timeout=30)
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(65536):
                    f.write(chunk)
        else:
            urllib.request.urlretrieve(url, output_path)
        size = os.path.getsize(output_path) if os.path.isfile(output_path) else 0
        import os
        return {"success": os.path.isfile(output_path), "data": {"saved": output_path, "size_kb": round(size/1024, 1)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_libraries() -> Dict[str, Any]:
    return {"success": True, "data": {"requests": HAS_REQUESTS, "beautifulsoup4": HAS_BS4}, "error": None}
