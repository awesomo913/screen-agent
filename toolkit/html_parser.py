"""
html_parser.py - Production-grade HTML parsing and manipulation toolkit for screen agents.

Supported libraries: bs4, lxml, html.parser, re, json, urllib, css_select, pathlib.
All functions return a consistent Dict[str, Any] structure with type hints and robust error handling.
"""

from typing import Dict, Any, List, Optional, Union, Tuple
import re
import json
import urllib.parse
from pathlib import Path
from bs4 import BeautifulSoup, Tag, NavigableString, Comment
import lxml
import html.parser
import cssselect as css_select

# ---------------------------------------------------------------------------
# Standardized Return Helper
# ---------------------------------------------------------------------------
def _result(success: bool, data: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
    """Standard response wrapper for all toolkit functions."""
    return {"success": success, "data": data, "error": error}

# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------
def _get_soup(html: str, parser: str = "lxml") -> BeautifulSoup:
    """Safe BeautifulSoup initialization with fallback."""
    try:
        return BeautifulSoup(html, parser)
    except Exception:
        return BeautifulSoup(html, "html.parser")

def _resolve_url(url: Optional[str], base_url: Optional[str] = None) -> str:
    """Resolve relative URLs using urllib.parse."""
    if not url:
        return ""
    try:
        return urllib.parse.urljoin(base_url or "", url.strip())
    except Exception:
        return url

def _tag_to_dict(tag: Tag) -> Dict[str, Any]:
    """Serialize a BS4 Tag to a clean dictionary."""
    return {
        "tag": tag.name,
        "attrs": dict(tag.attrs) if tag.attrs else {},
        "text": tag.get_text(separator=" ", strip=True)
    }

def _validate_css_selector(selector: str) -> bool:
    """Validate CSS selector syntax using css_select."""
    try:
        css_select.GenericTranslator().css_to_xpath(selector)
        return True
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Core Parsing & Query Functions
# ---------------------------------------------------------------------------
def parse_html(html_string: str) -> Dict[str, Any]:
    """Parse raw HTML string and return structural metadata."""
    try:
        soup = _get_soup(html_string)
        return _result(True, data={
            "status": "parsed",
            "root_element": soup.name,
            "encoding": soup.original_encoding or "utf-8",
            "element_count": len(list(soup.descendants)),
            "preview": soup.prettify(formatter="html")[:200]
        })
    except Exception as e:
        return _result(False, error=f"Failed to parse HTML string: {e}")

def parse_html_file(filepath: Union[str, Path]) -> Dict[str, Any]:
    """Read and parse an HTML file from disk using pathlib."""
    try:
        path = Path(filepath)
        if not path.is_file():
            return _result(False, error=f"File not found: {filepath}")
        html = path.read_text(encoding="utf-8", errors="ignore")
        return parse_html(html)
    except Exception as e:
        return _result(False, error=f"File I/O error: {e}")

def find_elements(html: str, selector: str) -> Dict[str, Any]:
    """Find all elements matching a CSS selector."""
    if _validate_css_selector(selector):
        try:
            soup = _get_soup(html)
            matches = soup.select(selector)
            return _result(True, data=[_tag_to_dict(t) for t in matches])
        except Exception as e:
            return _result(False, error=f"Selector execution failed: {e}")
    return _result(False, error=f"Invalid CSS selector: {selector}")

def find_by_id(html: str, element_id: str) -> Dict[str, Any]:
    """Find a single element by ID attribute."""
    try:
        soup = _get_soup(html)
        elem = soup.find(id=element_id)
        return _result(True, data=_tag_to_dict(elem) if elem else None)
    except Exception as e:
        return _result(False, error=f"ID search failed: {e}")

def find_by_class(html: str, class_name: str) -> Dict[str, Any]:
    """Find all elements matching a CSS class."""
    try:
        soup = _get_soup(html)
        # class_ handles multi-class attributes safely
        matches = soup.find_all(class_=class_name)
        return _result(True, data=[_tag_to_dict(t) for t in matches])
    except Exception as e:
        return _result(False, error=f"Class search failed: {e}")

def find_by_tag(html: str, tag_name: str) -> Dict[str, Any]:
    """Find all elements by HTML tag name."""
    try:
        soup = _get_soup(html)
        matches = soup.find_all(tag_name)
        return _result(True, data=[_tag_to_dict(t) for t in matches])
    except Exception as e:
        return _result(False, error=f"Tag search failed: {e}")

def find_by_attribute(html: str, attr: str, value: str) -> Dict[str, Any]:
    """Find elements matching a specific attribute value."""
    try:
        soup = _get_soup(html)
        selector = f'[{attr}="{value}"]'
        if _validate_css_selector(selector):
            matches = soup.select(selector)
            return _result(True, data=[_tag_to_dict(t) for t in matches])
        return _result(False, error=f"Invalid attribute selector for {attr}")
    except Exception as e:
        return _result(False, error=f"Attribute search failed: {e}")

# ---------------------------------------------------------------------------
# Content Extraction Functions
# ---------------------------------------------------------------------------
def extract_text(html: str, selector: Optional[str] = None) -> Dict[str, Any]:
    """Extract sanitized text content, optionally scoped by CSS selector."""
    try:
        soup = _get_soup(html)
        if selector:
            if not _validate_css_selector(selector):
                return _result(False, error="Invalid selector")
            elements = soup.select(selector)
            text = "\n".join(el.get_text(separator="\n", strip=True) for el in elements)
        else:
            text = soup.get_text(separator="\n", strip=True)
        # Collapse multiple newlines/whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text).strip()
        return _result(True, data=text)
    except Exception as e:
        return _result(False, error=f"Text extraction failed: {e}")

def extract_links(html: str, base_url: str) -> Dict[str, Any]:
    """Extract all hyperlinks with resolved absolute URLs."""
    try:
        soup = _get_soup(html)
        anchors = soup.select("a[href]")
        links = []
        for a in anchors:
            href = a.get("href", "")
            link_dict = {
                "href": _resolve_url(href, base_url),
                "original_href": href,
                "text": a.get_text(strip=True),
                "attrs": dict(a.attrs)
            }
            links.append(link_dict)
        return _result(True, data={"count": len(links), "links": links})
    except Exception as e:
        return _result(False, error=f"Link extraction failed: {e}")

def extract_images(html: str, base_url: str) -> Dict[str, Any]:
    """Extract all image sources with resolved absolute URLs."""
    try:
        soup = _get_soup(html)
        imgs = soup.select("img[src]")
        images = []
        for img in imgs:
            src = img.get("src", "")
            images.append({
                "src": _resolve_url(src, base_url),
                "original_src": src,
                "alt": img.get("alt", ""),
                "attrs": dict(img.attrs)
            })
        return _result(True, data={"count": len(images), "images": images})
    except Exception as e:
        return _result(False, error=f"Image extraction failed: {e}")

def extract_tables(html: str) -> Dict[str, Any]:
    """Extract HTML tables into structured 2D arrays."""
    try:
        soup = _get_soup(html)
        tables = []
        for table in soup.select("table"):
            rows_data = []
            for tr in table.select("tr"):
                cells = [td.get_text(separator=" ", strip=True) for td in tr.select("td, th")]
                if any(cells):  # skip completely empty rows
                    rows_data.append(cells)
            tables.append(rows_data)
        return _result(True, data={"count": len(tables), "tables": tables})
    except Exception as e:
        return _result(False, error=f"Table extraction failed: {e}")

def extract_forms(html: str) -> Dict[str, Any]:
    """Extract form structures including actions, methods, and input fields."""
    try:
        soup = _get_soup(html)
        forms = []
        for form in soup.select("form"):
            inputs = []
            for inp in form.select("input, select, textarea"):
                inputs.append({
                    "tag": inp.name,
                    "name": inp.get("name", ""),
                    "type": inp.get("type", "text" if inp.name == "input" else None),
                    "value": inp.get("value", "")
                })
            forms.append({
                "action": _resolve_url(form.get("action", "")),
                "method": form.get("method", "get").upper(),
                "inputs": inputs
            })
        return _result(True, data={"count": len(forms), "forms": forms})
    except Exception as e:
        return _result(False, error=f"Form extraction failed: {e}")

def extract_meta_tags(html: str) -> Dict[str, Any]:
    """Extract <meta> tags into key-value pairs."""
    try:
        soup = _get_soup(html)
        metas = []
        for meta in soup.select("meta"):
            entry = {}
            for key in ("name", "property", "charset", "http-equiv"):
                val = meta.get(key)
                if val:
                    entry[key] = val
            entry["content"] = meta.get("content", "")
            metas.append(entry)
        return _result(True, data={"count": len(metas), "meta_tags": metas})
    except Exception as e:
        return _result(False, error=f"Meta extraction failed: {e}")

def extract_scripts(html: str) -> Dict[str, Any]:
    """Separate inline JS and external script references."""
    try:
        soup = _get_soup(html)
        inline = []
        external = []
        for script in soup.select("script"):
            src = script.get("src")
            if src:
                external.append(_resolve_url(src))
            elif script.string:
                t = script.string.strip()
                if t:
                    inline.append(t)
        return _result(True, data={"inline_count": len(inline), "external_count": len(external), "data": {"inline": inline, "external": external}})
    except Exception as e:
        return _result(False, error=f"Script extraction failed: {e}")

def extract_styles(html: str) -> Dict[str, Any]:
    """Extract inline CSS and external stylesheet URLs."""
    try:
        soup = _get_soup(html)
        blocks = [tag.string.strip() for tag in soup.select("style") if tag.string and tag.string.strip()]
        links = [_resolve_url(t.get("href", "")) for t in soup.select('link[rel="stylesheet"]') if t.get("href")]
        return _result(True, data={"inline_count": len(blocks), "external_count": len(links), "data": {"inline": blocks, "external": links}})
    except Exception as e:
        return _result(False, error=f"Style extraction failed: {e}")

# ---------------------------------------------------------------------------
# DOM Modification Functions
# ---------------------------------------------------------------------------
def modify_element(html: str, selector: str, modifications: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply modifications to matching elements.
    modifications: {"tag": str, "attrs": dict, "text": str, "clear_children": bool}
    """
    try:
        soup = _get_soup(html)
        elements = soup.select(selector)
        if not elements:
            return _result(True, data={"modified": 0, "html": html})
        
        for el in elements:
            if "tag" in modifications:
                el.name = modifications["tag"]
            if "attrs" in modifications:
                for k, v in modifications["attrs"].items():
                    el.attrs[k] = v
                # Remove attrs set to None
                el.attrs = {k: v for k, v in el.attrs.items() if v is not None}
            if "text" in modifications:
                el.string = modifications["text"]
            if modifications.get("clear_children"):
                el.clear()
                
        return _result(True, data={"modified": len(elements), "html": str(soup)})
    except Exception as e:
        return _result(False, error=f"Element modification failed: {e}")

def remove_elements(html: str, selector: str) -> Dict[str, Any]:
    """Remove all elements matching the selector from the DOM."""
    try:
        soup = _get_soup(html)
        elements = soup.select(selector)
        count = len(elements)
        for el in elements:
            el.decompose()
        return _result(True, data={"removed": count, "html": str(soup)})
    except Exception as e:
        return _result(False, error=f"Element removal failed: {e}")

def add_element(html: str, parent_selector: str, new_element: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Add a new element to all matching parent selectors.
    new_element: HTML string or dict {"tag": str, "attrs": dict, "text": str}
    """
    try:
        soup = _get_soup(html)
        parents = soup.select(parent_selector)
        if not parents:
            return _result(False, error="No parent elements found")
            
        count = 0
        for parent in parents:
            if isinstance(new_element, str):
                frag = BeautifulSoup(new_element, "lxml")
                for node in frag.children:
                    if isinstance(node, (Tag, NavigableString)):
                        parent.append(node)
            else:
                tag = Tag(builder=soup.builder, name=new_element.get("tag", "div"), attrs=new_element.get("attrs", {}))
                if "text" in new_element:
                    tag.string = new_element["text"]
                parent.append(tag)
            count += 1
            
        return _result(True, data={"added_to": count, "html": str(soup)})
    except Exception as e:
        return _result(False, error=f"Add element failed: {e}")

# ---------------------------------------------------------------------------
# Transformation & Formatting Functions
# ---------------------------------------------------------------------------
def clean_html(html: str, allowed_tags: List[str]) -> Dict[str, Any]:
    """Remove all tags not in allowed_tags, preserving text content."""
    try:
        soup = _get_soup(html)
        allowed = set(t.lower() for t in allowed_tags)
        for tag in soup.find_all(True):
            if tag.name not in allowed:
                tag.unwrap()
        return _result(True, data=str(soup))
    except Exception as e:
        return _result(False, error=f"HTML cleaning failed: {e}")

def html_to_text(html: str) -> Dict[str, Any]:
    """Convert HTML to clean plain text."""
    try:
        soup = _get_soup(html)
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return _result(True, data=text)
    except Exception as e:
        return _result(False, error=f"Text conversion failed: {e}")

def html_to_markdown(html: str) -> Dict[str, Any]:
    """Convert HTML to basic Markdown structure."""
    def _convert_node(node: Union[Tag, NavigableString]) -> str:
        if isinstance(node, Comment):
            return ""
        if isinstance(node, NavigableString):
            return node.string or ""
            
        tag_name = node.name.lower()
        inner = "".join(_convert_node(c) for c in node.children)
        
        if tag_name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag_name[1])
            return f"\n{'#' * level} {inner.strip()}\n"
        if tag_name in ("p", "div", "section", "article", "header", "footer"):
            return f"\n{inner.strip()}\n"
        if tag_name == "br":
            return "\n"
        if tag_name == "ul":
            return f"\n{inner}\n"
        if tag_name == "ol":
            return f"\n{inner}\n"
        if tag_name == "li":
            prefix = "- " if node.parent.name == "ul" else "1. "
            return f"{prefix}{inner.strip()}\n"
        if tag_name in ("strong", "b"):
            return f" **{inner.strip()}** "
        if tag_name in ("em", "i"):
            return f" *{inner.strip()}* "
        if tag_name in ("code", "kbd"):
            return f" `{inner.strip()}` "
        if tag_name == "pre":
            return f"\n```\n{inner}\n```\n"
        if tag_name == "a":
            href = node.get("href", "")
            return f" [{inner.strip()}]({href}) "
        if tag_name == "img":
            src = node.get("src", "")
            alt = node.get("alt", "image")
            return f"![{alt}]({src}) "
        return inner.rstrip()

    try:
        soup = _get_soup(html)
        # Remove scripts/styles first
        for elem in soup(["script", "style", "noscript"]):
            elem.decompose()
        md = _convert_node(soup)
        md = re.sub(r'\n{3,}', '\n\n', md).strip()
        return _result(True, data=md)
    except Exception as e:
        return _result(False, error=f"Markdown conversion failed: {e}")

def minify_html(html: str) -> Dict[str, Any]:
    """Remove comments and collapse whitespace for minimal size."""
    try:
        soup = _get_soup(html)
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        html_str = str(soup)
        # Remove whitespace between tags
        html_str = re.sub(r'>\s+<', '><', html_str)
        # Collapse multiple spaces
        html_str = re.sub(r'\s+', ' ', html_str)
        return _result(True, data=html_str)
    except Exception as e:
        return _result(False, error=f"Minification failed: {e}")

def prettify_html(html: str) -> Dict[str, Any]:
    """Format HTML with proper indentation."""
    try:
        soup = _get_soup(html)
        return _result(True, data=soup.prettify(formatter="html"))
    except Exception as e:
        return _result(False, error=f"Prettification failed: {e}")

def validate_html(html: str) -> Dict[str, Any]:
    """Validate HTML structure and report warnings using html.parser."""
    class ValidationParser(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.errors: List[str] = []
            self.stack: List[str] = []
            self.void_elements = set(html.parser.HTMLParser.VOID_ELEMENTS)
            
        def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
            if tag not in self.void_elements:
                self.stack.append(tag)
        def handle_endtag(self, tag: str):
            if self.stack and self.stack[-1] == tag:
                self.stack.pop()
            elif tag in self.void_elements:
                self.errors.append(f"Unexpected closing tag: <{tag}>")
            else:
                self.errors.append(f"Mismatched closing tag: <{tag}>")
        def handle_data(self, data: str):
            pass # Ignore text for validation

    try:
        parser = ValidationParser()
        parser.feed(html)
        
        warnings = []
        if parser.stack:
            warnings.append(f"Unclosed tags: {', '.join(parser.stack)}")
        warnings.extend(parser.errors)
        
        is_valid = len(warnings) == 0
        return _result(True, data={
            "is_valid": is_valid,
            "warnings": warnings if warnings else ["HTML structure is well-formed."],
            "error_count": len(warnings)
        })
    except Exception as e:
        return _result(False, error=f"Validation failed: {e}")

def extract_structured_data(html: str) -> Dict[str, Any]:
    """Extract JSON-LD and microdata from <script> tags."""
    try:
        soup = _get_soup(html)
        structured = []
        
        # JSON-LD
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                if script.string:
                    data = json.loads(script.string.strip())
                    structured.append({"type": "json_ld", "data": data})
            except json.JSONDecodeError:
                continue
                
        # Microdata fallback (basic extraction)
        for item in soup.select('[itemscope]'):
            item_type = item.get("itemtype", "")
            props = {}
            for prop in item.select("[itemprop]"):
                k = prop.get("itemprop")
                v = prop.get("content") or prop.get_text(strip=True)
                if k:
                    props[k] = v
            if props:
                structured.append({"type": "microdata", "itemtype": item_type, "properties": props})
                
        return _result(True, data={"count": len(structured), "structured_data": structured})
    except Exception as e:
        return _result(False, error=f"Structured data extraction failed: {e}")