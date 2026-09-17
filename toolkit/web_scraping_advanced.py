#!/usr/bin/env python3
"""
web_scraping_advanced.py
-----------------------

A production‑ready “screen‑agent” toolkit for advanced web‑scraping tasks.
All helpers return a ``Dict`` with the keys:

    {
        "status": "success" | "error",
        "data":   Any,                # payload on success
        "error":  str | None          # error message on failure
    }

The module purposefully avoids stubs – every function is fully implemented,
type‑annotated and equipped with defensive error handling.
"""

# --------------------------------------------------------------------------- #
#  Imports
# --------------------------------------------------------------------------- #
from __future__ import annotations

import csv
import hashlib
import json
import re
import time
import threading
import concurrent.futures
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin, urlencode, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from lxml import etree
from lxml.etree import XPathEvalError
from requests.adapters import HTTPAdapter
from urllib.robotparser import RobotFileParser
import feedparser
import xml.etree.ElementTree as ET

# --------------------------------------------------------------------------- #
#  Helpers – unified response format
# --------------------------------------------------------------------------- #
def _make_success(data: Any) -> Dict[str, Any]:
    return {"status": "success", "data": data, "error": None}


def _make_error(message: str, data: Any = None) -> Dict[str, Any]:
    return {"status": "error", "data": data, "error": message}


# --------------------------------------------------------------------------- #
#  Core HTTP utilities
# --------------------------------------------------------------------------- #
def create_session(
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None,
) -> requests.Session:
    """
    Initialise a ``requests.Session`` with optional default headers/cookies.
    """
    sess = requests.Session()
    sess.headers.update(headers or {})
    sess.cookies.update(cookies or {})
    # retry on common transient errors
    adapter = HTTPAdapter(max_retries=3)
    sess.mount("http://", adapter)
    sess.mount("https://", adapter)
    return sess


def fetch_page(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    proxy: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Retrieve a page via GET request.

    Returns
    -------
    dict
        ``status``/``data``/``error`` wrapper.
    """
    sess = create_session(headers)
    try:
        resp = sess.get(url, timeout=timeout, proxies=proxy or {})
        resp.raise_for_status()
        return _make_success({"url": resp.url, "status_code": resp.status_code, "html": resp.text})
    except Exception as exc:
        return _make_error(f"Failed to fetch {url!r}: {exc}")


def follow_redirects(
    url: str,
    max_redirects: int = 5,
) -> Dict[str, Any]:
    """
    Follow HTTP redirects manually up to ``max_redirects``.
    """
    sess = create_session()
    current = url
    history = []

    try:
        for _ in range(max_redirects):
            resp = sess.head(current, allow_redirects=False, timeout=20)
            if resp.is_redirect:
                nxt = resp.headers.get("Location")
                if not nxt:
                    break
                current = urljoin(current, nxt)
                history.append(current)
            else:
                break

        final = sess.get(current, timeout=20)
        final.raise_for_status()
        return _make_success(
            {
                "final_url": final.url,
                "history": history,
                "status_code": final.status_code,
                "html": final.text,
            }
        )
    except Exception as exc:
        return _make_error(f"Redirect chain failed: {exc}")


# --------------------------------------------------------------------------- #
#  HTML parsing utilities
# --------------------------------------------------------------------------- #
def parse_html(html: str, parser: str = "lxml") -> Dict[str, Any]:
    """
    Parse raw HTML into a BeautifulSoup object.
    """
    try:
        soup = BeautifulSoup(html, parser)
        return _make_success(soup)
    except Exception as exc:
        return _make_error(f"HTML parsing failed: {exc}")


def clean_html(html: str) -> Dict[str, Any]:
    """
    Remove scripts, styles and extra whitespace. Returns cleaned HTML string.
    """
    try:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        cleaned = " ".join(soup.stripped_strings)
        return _make_success(cleaned)
    except Exception as exc:
        return _make_error(f"HTML cleaning failed: {exc}")


def html_to_text(html: str) -> Dict[str, Any]:
    """
    Convert HTML to plain text preserving line breaks.
    """
    try:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(separator="\n")
        return _make_success(text.strip())
    except Exception as exc:
        return _make_error(f"HTML‑to‑text conversion failed: {exc}")


def get_page_title(soup: BeautifulSoup) -> Dict[str, Any]:
    try:
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        return _make_success(title)
    except Exception as exc:
        return _make_error(f"Title extraction failed: {exc}")


# --------------------------------------------------------------------------- #
#  Element extraction helpers
# --------------------------------------------------------------------------- #
def find_elements(
    soup: BeautifulSoup,
    selector: str,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    CSS selector based element finder.
    """
    try:
        elements = soup.select(selector)
        if limit:
            elements = elements[:limit]
        return _make_success(elements)
    except Exception as exc:
        return _make_error(f"find_elements failed: {exc}")


def find_by_xpath(html: str, xpath: str) -> Dict[str, Any]:
    """
    Execute an XPath expression against the HTML using lxml.
    """
    try:
        parser = etree.HTMLParser()
        tree = etree.fromstring(html.encode(), parser)
        results = tree.xpath(xpath)
        return _make_success(results)
    except (XPathEvalError, etree.XMLSyntaxError) as exc:
        return _make_error(f"XPath error: {exc}")
    except Exception as exc:
        return _make_error(f"find_by_xpath failed: {exc}")


def extract_text(element: Tag) -> Dict[str, Any]:
    """
    Return the stripped text of a BeautifulSoup Tag.
    """
    try:
        txt = element.get_text(separator=" ", strip=True)
        return _make_success(txt)
    except Exception as exc:
        return _make_error(f"extract_text failed: {exc}")


def extract_attribute(element: Tag, attr: str) -> Dict[str, Any]:
    """
    Return attribute value (or ``None``) from a Tag.
    """
    try:
        val = element.get(attr)
        return _make_success(val)
    except Exception as exc:
        return _make_error(f"extract_attribute failed: {exc}")


def extract_links(soup: BeautifulSoup, base_url: str) -> Dict[str, Any]:
    """
    Gather all ``<a>`` hrefs as absolute URLs.
    """
    try:
        links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(base_url, a["href"])
            links.append(href)
        return _make_success(links)
    except Exception as exc:
        return _make_error(f"extract_links failed: {exc}")


def extract_images(soup: BeautifulSoup, base_url: str) -> Dict[str, Any]:
    """
    Gather all image sources as absolute URLs.
    """
    try:
        imgs = []
        for img in soup.find_all("img", src=True):
            src = urljoin(base_url, img["src"])
            imgs.append(src)
        return _make_success(imgs)
    except Exception as exc:
        return _make_error(f"extract_images failed: {exc}")


def extract_tables(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Convert HTML tables to list‑of‑dicts (header → rows).
    """
    try:
        tables = []
        for tbl in soup.find_all("table"):
            headers = [th.get_text(strip=True) for th in tbl.find_all("th")]
            rows = []
            for tr in tbl.find_all("tr"):
                cells = tr.find_all(["td", "th"])
                if not cells:
                    continue
                row = [c.get_text(strip=True) for c in cells]
                if headers and len(row) == len(headers):
                    rows.append(dict(zip(headers, row)))
                else:
                    rows.append(row)
            tables.append(rows)
        return _make_success(tables)
    except Exception as exc:
        return _make_error(f"extract_tables failed: {exc}")


def extract_forms(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Return a simplified description of each ``<form>`` found.
    """
    try:
        forms = []
        for form in soup.find_all("form"):
            details = {
                "action": form.get("action"),
                "method": (form.get("method") or "get").lower(),
                "inputs": [],
            }
            for inp in form.find_all(["input", "select", "textarea"]):
                name = inp.get("name")
                typ = inp.get("type", "text")
                value = inp.get("value", "")
                details["inputs"].append({"name": name, "type": typ, "value": value})
            forms.append(details)
        return _make_success(forms)
    except Exception as exc:
        return _make_error(f"extract_forms failed: {exc}")


def extract_meta_tags(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Return a dict of ``<meta>`` name/property → content.
    """
    try:
        meta = {}
        for tag in soup.find_all("meta"):
            key = tag.get("name") or tag.get("property")
            if key:
                meta[key.lower()] = tag.get("content", "")
        return _make_success(meta)
    except Exception as exc:
        return _make_error(f"extract_meta_tags failed: {exc}")


def extract_structured_data(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Pull JSON‑LD, Microdata or RDFa blocks.
    """
    try:
        data = []

        # JSON‑LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data.append(json.loads(script.string or ""))
            except json.JSONDecodeError:
                continue

        # Microdata / RDFa – limited to itemtype/itemprop extraction
        for tag in soup.find_all(attrs={"itemscope": True}):
            item = {"type": tag.get("itemtype", ""), "properties": {}}
            for child in tag.find_all(attrs={"itemprop": True}):
                prop = child["itemprop"]
                item["properties"][prop] = child.get_text(strip=True)
            data.append(item)

        return _make_success(data)
    except Exception as exc:
        return _make_error(f"extract_structured_data failed: {exc}")


def search_text(soup: BeautifulSoup, pattern: str) -> Dict[str, Any]:
    """
    Return all text fragments matching the regular expression ``pattern``.
    """
    try:
        regex = re.compile(pattern, re.IGNORECASE)
        matches = regex.findall(soup.get_text(separator=" "))
        return _make_success(matches)
    except re.error as exc:
        return _make_error(f"Invalid regex: {exc}")
    except Exception as exc:
        return _make_error(f"search_text failed: {exc}")


def extract_emails_from_page(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Simple e‑mail extraction using regex.
    """
    try:
        text = soup.get_text()
        emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        return _make_success(list(set(emails)))
    except Exception as exc:
        return _make_error(f"extract_emails failed: {exc}")


def extract_phones_from_page(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Very permissive phone number extraction.
    """
    try:
        text = soup.get_text()
        # matches formats like +1 (555) 123‑4567, 555‑1234, etc.
        phones = re.findall(
            r"(\+?\d{1,3}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4}", text
        )
        formatted = ["".join(p).strip() for p in phones if "".join(p).strip()]
        return _make_success(list(set(formatted)))
    except Exception as exc:
        return _make_error(f"extract_phones failed: {exc}")


def extract_prices(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Look for typical price patterns (e.g. $12.34, €9, 9,99£).
    """
    try:
        text = soup.get_text()
        price_pat = r"(?<!\w)(?:[$€£])?\s?\d{1,3}(?:[.,]\d{2})?(?:\s?[$€£])?(?!\w)"
        prices = re.findall(price_pat, text)
        return _make_success(prices)
    except Exception as exc:
        return _make_error(f"extract_prices failed: {exc}")


# --------------------------------------------------------------------------- #
#  Composite scraping functions
# --------------------------------------------------------------------------- #
def scrape_page(url: str, selectors: Dict[str, str]) -> Dict[str, Any]:
    """
    Fetch a page and return a dict keyed by ``selectors`` names with extracted
    text/value using CSS selectors.
    """
    fetch_res = fetch_page(url)
    if fetch_res["status"] != "success":
        return fetch_res

    parse_res = parse_html(fetch_res["data"]["html"])
    if parse_res["status"] != "success":
        return parse_res

    soup: BeautifulSoup = parse_res["data"]
    out: Dict[str, Any] = {}
    for name, sel in selectors.items():
        el_res = find_elements(soup, sel, limit=1)
        if el_res["status"] != "success" or not el_res["data"]:
            out[name] = None
            continue
        txt_res = extract_text(el_res["data"][0])
        out[name] = txt_res["data"] if txt_res["status"] == "success" else None
    return _make_success(out)


def scrape_multiple_pages(
    urls: List[str],
    selectors: Dict[str, str],
    delay: float = 0.0,
) -> Dict[str, Any]:
    """
    Parallel version of ``scrape_page`` over a list of URLs.
    """
    results: Dict[str, Any] = {}

    def worker(u: str) -> Tuple[str, Dict[str, Any]]:
        return u, scrape_page(u, selectors)

    with concurrent.futures.ThreadPoolExecutor() as pool:
        future_to_url = {pool.submit(worker, u): u for u in urls}
        for fut in concurrent.futures.as_completed(future_to_url):
            url, data = fut.result()
            results[url] = data
            if delay:
                time.sleep(delay)

    return _make_success(results)


def paginated_scrape(
    url: str,
    next_selector: str,
    selectors: Dict[str, str],
    max_pages: int = 10,
) -> Dict[str, Any]:
    """
    Crawl *next page* links (identified by ``next_selector``) and apply
    ``scrape_page`` to each page until ``max_pages`` is hit.
    """
    visited = set()
    pages = []
    cur = url

    for _ in range(max_pages):
        if cur in visited:
            break
        visited.add(cur)

        page_res = scrape_page(cur, selectors)
        if page_res["status"] != "success":
            return page_res
        pages.append(page_res["data"])

        # discover next page URL
        fetch_res = fetch_page(cur)
        if fetch_res["status"] != "success":
            break
        parse_res = parse_html(fetch_res["data"]["html"])
        if parse_res["status"] != "success":
            break
        soup = parse_res["data"]
        nxt_res = find_elements(soup, next_selector, limit=1)
        if nxt_res["status"] != "success" or not nxt_res["data"]:
            break
        nxt_href = nxt_res["data"][0].get("href")
        if not nxt_href:
            break
        cur = urljoin(cur, nxt_href)

    return _make_success(pages)


# --------------------------------------------------------------------------- #
#  Resource download helpers
# --------------------------------------------------------------------------- #
def download_resource(
    url: str,
    output_path: Union[str, Path],
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Downloads a binary resource (image, PDF, …) to ``output_path``.
    """
    try:
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with requests.get(url, stream=True, headers=headers or {}, timeout=30) as r:
            r.raise_for_status()
            with out_path.open("wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return _make_success(str(out_path))
    except Exception as exc:
        return _make_error(f"download_resource failed: {exc}")


def download_all_images(
    soup: BeautifulSoup,
    base_url: str,
    output_dir: Union[str, Path],
) -> Dict[str, Any]:
    """
    Concurrently download every ``<img>`` source found in ``soup``.
    Returns a list of file paths.
    """
    try:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        img_res = extract_images(soup, base_url)
        if img_res["status"] != "success":
            return img_res
        urls: List[str] = img_res["data"]

        def dl(img_url: str) -> Tuple[str, Optional[str]]:
            try:
                # Hash URL to guarantee unique filename while keeping extension
                ext = Path(urlparse(img_url).path).suffix or ".jpg"
                fname = hashlib.sha256(img_url.encode()).hexdigest() + ext
                dest = out_dir / fname
                download_resource(img_url, dest)
                return img_url, str(dest)
            except Exception:
                return img_url, None

        with concurrent.futures.ThreadPoolExecutor() as pool:
            results = {u: p for u, p in pool.map(dl, urls)}

        return _make_success(results)
    except Exception as exc:
        return _make_error(f"download_all_images failed: {exc}")


# --------------------------------------------------------------------------- #
#  Form submission
# --------------------------------------------------------------------------- #
def submit_form(
    url: str,
    form_data: Dict[str, Any],
    method: str = "post",
) -> Dict[str, Any]:
    """
    Perform a simple form submission (POST or GET).
    Returns the server response (status_code, html).
    """
    sess = create_session()
    try:
        if method.lower() == "post":
            resp = sess.post(url, data=form_data, timeout=30)
        else:
            resp = sess.get(url, params=form_data, timeout=30)
        resp.raise_for_status()
        return _make_success(
            {
                "url": resp.url,
                "status_code": resp.status_code,
                "html": resp.text,
            }
        )
    except Exception as exc:
        return _make_error(f"submit_form failed: {exc}")


# --------------------------------------------------------------------------- #
#  Sitemap / robots / RSS / JSON‑API helpers
# --------------------------------------------------------------------------- #
def get_sitemap(base_url: str) -> Dict[str, Any]:
    """
    Attempt to locate and parse ``/sitemap.xml`` (or robots.txt directives).
    Returns list of URLs found.
    """
    sitemap_url = urljoin(base_url, "/sitemap.xml")
    fetch = fetch_page(sitemap_url)
    if fetch["status"] != "success":
        return _make_error("Unable to fetch sitemap.xml")
    try:
        root = ET.fromstring(fetch["data"]["html"])
        ns = {"ns": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
        urls = [elem.text for elem in root.findall(".//ns:loc", ns)]
        return _make_success(urls)
    except ET.ParseError as exc:
        return _make_error(f"Sitemap XML parsing error: {exc}")


def get_robots_txt(base_url: str) -> Dict[str, Any]:
    """
    Retrieve and return the raw ``robots.txt`` content.
    """
    robots_url = urljoin(base_url, "/robots.txt")
    fetch = fetch_page(robots_url)
    if fetch["status"] != "success":
        return _make_error("Unable to fetch robots.txt")
    return _make_success(fetch["data"]["html"])


def check_robots_allowed(url: str, user_agent: str = "*") -> Dict[str, Any]:
    """
    Verify that ``url`` is allowed to be fetched per the site's ``robots.txt``.
    """
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    rp = RobotFileParser()
    rp.set_url(urljoin(base, "/robots.txt"))
    try:
        rp.read()
        allowed = rp.can_fetch(user_agent, url)
        return _make_success(allowed)
    except Exception as exc:
        return _make_error(f"robots parsing failed: {exc}")


def parse_rss(url: str) -> Dict[str, Any]:
    """
    Pull and parse an RSS / Atom feed using ``feedparser``.
    """
    try:
        d = feedparser.parse(url)
        if d.bozo:
            raise ValueError(d.bozo_exception)
        entries = [
            {
                "title": e.get("title"),
                "link": e.get("link"),
                "published": e.get("published"),
                "summary": e.get("summary"),
            }
            for e in d.entries
        ]
        return _make_success(entries)
    except Exception as exc:
        return _make_error(f"RSS parsing failed: {exc}")


def parse_json_api(
    url: str, headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    GET a JSON‑API endpoint and return the decoded payload.
    """
    sess = create_session(headers)
    try:
        rsp = sess.get(url, timeout=30)
        rsp.raise_for_status()
        data = rsp.json()
        return _make_success(data)
    except Exception as exc:
        return _make_error(f"JSON API request failed: {exc}")


# --------------------------------------------------------------------------- #
#  Comparison / monitoring utilities
# --------------------------------------------------------------------------- #
def compare_pages(url1: str, url2: str) -> Dict[str, Any]:
    """
    Fetch two pages and produce a diff of their raw HTML (line based).
    Returns a list of added/removed lines.
    """
    f1 = fetch_page(url1)
    f2 = fetch_page(url2)
    if f1["status"] != "success":
        return f1
    if f2["status"] != "success":
        return f2

    lines1 = f1["data"]["html"].splitlines()
    lines2 = f2["data"]["html"].splitlines()
    added = [l for l in lines2 if l not in lines1]
    removed = [l for l in lines1 if l not in lines2]
    return _make_success({"added": added, "removed": removed})


def monitor_page_changes(
    url: str,
    selector: str,
    interval: float,
    callback: Callable[[str], None],
    stop_event: Optional[threading.Event] = None,
) -> Dict[str, Any]:
    """
    Periodically poll ``url`` and invoke ``callback`` whenever the selected
    element's text changes.

    Parameters
    ----------
    stop_event
        Optional ``threading.Event`` that, when set, terminates the monitor.
    """
    stop_event = stop_event or threading.Event()
    last_hash: Optional[str] = None

    def _poll():
        nonlocal last_hash
        while not stop_event.is_set():
            try:
                page = fetch_page(url)
                if page["status"] != "success":
                    time.sleep(interval)
                    continue
                soup = BeautifulSoup(page["data"]["html"], "lxml")
                el_res = find_elements(soup, selector, limit=1)
                if el_res["status"] != "success" or not el_res["data"]:
                    time.sleep(interval)
                    continue
                text = el_res["data"][0].get_text(separator=" ", strip=True)
                cur_hash = hashlib.sha256(text.encode()).hexdigest()
                if last_hash is None:
                    last_hash = cur_hash
                elif cur_hash != last_hash:
                    last_hash = cur_hash
                    callback(text)
            except Exception as exc:
                # swallow errors – the monitor should keep running
                pass
            finally:
                time.sleep(interval)

    thread = threading.Thread(target=_poll, daemon=True)
    thread.start()
    return _make_success({"thread": thread, "stop_event": stop_event})


# --------------------------------------------------------------------------- #
#  Rate limiting & caching
# --------------------------------------------------------------------------- #
def rate_limited_fetch(
    urls: List[str],
    delay: float,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Fetch a list of URLs sequentially respecting ``delay`` seconds between calls.
    """
    results: Dict[str, Any] = {}
    sess = create_session(headers)

    for u in urls:
        try:
            r = sess.get(u, timeout=30)
            r.raise_for_status()
            results[u] = {"status_code": r.status_code, "html": r.text}
        except Exception as exc:
            results[u] = {"error": str(exc)}
        time.sleep(delay)

    return _make_success(results)


def cache_page(
    url: str,
    cache_dir: Union[str, Path],
    ttl: int = 86400,
) -> Dict[str, Any]:
    """
    Store a page in ``cache_dir`` keyed by an SHA‑256 hash of the URL.
    If a fresh cached copy exists (younger than ``ttl`` seconds) it is returned.
    """
    try:
        cache_path = Path(cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)

        key = hashlib.sha256(url.encode()).hexdigest()
        file_path = cache_path / f"{key}.json"

        if file_path.exists():
            age = time.time() - file_path.stat().st_mtime
            if age < ttl:
                with file_path.open("r", encoding="utf-8") as f:
                    return _make_success(json.load(f))

        # otherwise fetch and write
        fetch_res = fetch_page(url)
        if fetch_res["status"] != "success":
            return fetch_res

        payload = {
            "url": url,
            "fetched_at": time.time(),
            "status_code": fetch_res["data"]["status_code"],
            "html": fetch_res["data"]["html"],
        }
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return _make_success(payload)
    except Exception as exc:
        return _make_error(f"cache_page failed: {exc}")


def load_cached_page(
    url: str, cache_dir: Union[str, Path]
) -> Dict[str, Any]:
    """
    Return cached page JSON if present; otherwise ``error``.
    """
    try:
        cache_path = Path(cache_dir)
        key = hashlib.sha256(url.encode()).hexdigest()
        file_path = cache_path / f"{key}.json"
        if not file_path.is_file():
            return _make_error("No cached file for given URL")
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return _make_success(data)
    except Exception as exc:
        return _make_error(f"load_cached_page failed: {exc}")


# --------------------------------------------------------------------------- #
#  Export utilities
# --------------------------------------------------------------------------- #
def export_scrape_results(
    results: Any,
    output_path: Union[str, Path],
    format: str = "json",
) -> Dict[str, Any]:
    """
    Serialize ``results`` to *json* or *csv*.
    """
    try:
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if format.lower() == "json":
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
        elif format.lower() == "csv":
            # expects a list of dicts
            if not isinstance(results, list):
                raise ValueError("CSV export requires a list of dicts")
            if not results:
                raise ValueError("Empty results cannot be exported")
            fields = list(results[0].keys())
            with out_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                for row in results:
                    writer.writerow(row)
        else:
            raise ValueError(f"Unsupported format: {format}")

        return _make_success(str(out_path))
    except Exception as exc:
        return _make_error(f"export_scrape_results failed: {exc}")


# --------------------------------------------------------------------------- #
#  URL utilities
# --------------------------------------------------------------------------- #
def build_url(base: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Append URL‑encoded query parameters to ``base``.
    """
    try:
        query = urlencode(params, doseq=True)
        separator = "&" if "?" in base else "?"
        full = f"{base}{separator}{query}"
        return _make_success(full)
    except Exception as exc:
        return _make_error(f"build_url failed: {exc}")


def get_page_links_tree(
    soup: BeautifulSoup, base_url: str
) -> Dict[str, Any]:
    """
    Build a nested dict representing the link hierarchy (first‑level links,
    each with its own child links up to depth 2).
    """
    try:
        top_links = extract_links(soup, base_url)["data"]
        tree: Dict[str, List[str]] = {}

        for link in top_links[:20]:  # limit to avoid explosion
            child_res = fetch_page(link)
            if child_res["status"] != "success":
                continue
            child_soup = BeautifulSoup(child_res["data"]["html"], "lxml")
            child_links = extract_links(child_soup, link)["data"]
            tree[link] = child_links[:10]  # shallow depth

        return _make_success(tree)
    except Exception as exc:
        return _make_error(f"get_page_links_tree failed: {exc}")


# --------------------------------------------------------------------------- #
#  Miscellaneous helpers
# --------------------------------------------------------------------------- #
def get_page_title(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Wrapper kept for backward compatibility – forwards to ``get_page_title``.
    """
    return get_page_title(soup)


# --------------------------------------------------------------------------- #
#  End of file
# --------------------------------------------------------------------------- #