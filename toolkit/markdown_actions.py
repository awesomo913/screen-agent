"""
markdown_actions.py
Production-grade Markdown processing toolkit for screen agents.
Uses: markdown, re, html, bs4, pygments
"""

import re
import os
import html
import textwrap
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

import markdown
from bs4 import BeautifulSoup
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
from pygments.styles import get_style_by_name

# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _result(success: bool, data: Any = None, error: Optional[str] = None) -> Dict:
    """Standardized response dictionary."""
    return {"success": success, "data": data, "error": error}


# ---------------------------------------------------------------------------
# Core Conversion Functions
# ---------------------------------------------------------------------------

def md_to_html(md_text: str) -> Dict:
    """Convert Markdown string to HTML using the `markdown` library."""
    try:
        extensions = ['extra', 'fenced_code', 'codehilite', 'tables', 'toc', 'meta']
        html_out = markdown.markdown(md_text, extensions=extensions)
        return _result(True, html_out)
    except Exception as e:
        return _result(False, error=str(e))


def html_to_md(html_text: str) -> Dict:
    """Convert HTML string to Markdown using BS4 recursive traversal."""
    def _convert(elem: Any) -> str:
        if isinstance(elem, str):
            return html.unescape(elem)
        
        tag = getattr(elem, 'name', None)
        children_text = "".join(_convert(c) for c in elem.children if c)

        if tag is None:
            return children_text
        if tag in ('h1',):   return f"# {children_text}\n\n"
        if tag in ('h2',):   return f"## {children_text}\n\n"
        if tag in ('h3',):   return f"### {children_text}\n\n"
        if tag in ('h4',):   return f"#### {children_text}\n\n"
        if tag in ('h5',):   return f"##### {children_text}\n\n"
        if tag in ('h6',):   return f"###### {children_text}\n\n"
        if tag == 'p':       return f"{children_text}\n\n"
        if tag == 'br':      return "  \n"
        if tag in ('b', 'strong'):  return f"**{elem.get_text(strip=True)}**"
        if tag in ('i', 'em'):      return f"*{elem.get_text(strip=True)}*"
        if tag == 'code':    return f"`{elem.get_text(strip=False)}`"
        if tag == 'pre':
            code_node = elem.find('code')
            code_txt = code_node.get_text(strip=False) if code_node else elem.get_text(strip=False)
            return f"```\n{code_txt}\n```\n\n"
        if tag == 'a':
            href = elem.get('href', '#')
            return f"[{elem.get_text(strip=True)}]({href})"
        if tag == 'img':
            return f"![{elem.get('alt', '')}]({elem.get('src', '')})"
        if tag == 'ul':
            return "".join(f"- {_convert(li)}\n" for li in elem.find_all('li', recursive=False)) + "\n"
        if tag == 'ol':
            return "".join(f"{i}. {_convert(li)}\n" for i, li in enumerate(elem.find_all('li', recursive=False), 1)) + "\n"
        return children_text

    try:
        soup = BeautifulSoup(html_text, 'html.parser')
        md_output = "".join(_convert(child) for child in soup.children if child)
        return _result(True, md_output)
    except Exception as e:
        return _result(False, error=str(e))


def convert_md_to_pdf(md_text: str, output_path: str) -> Dict:
    """Convert Markdown to PDF. Falls back to pandoc CLI if weasyprint is unavailable."""
    try:
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_md = out_path.with_suffix('.tmp.md')
        tmp_md.write_text(md_text, encoding='utf-8')

        try:
            from weasyprint import HTML
            h_html = markdown.markdown(md_text, extensions=['extra', 'tables'])
            HTML(string=h_html).write_pdf(str(out_path))
        except ImportError:
            cmd = ['pandoc', str(tmp_md), '-o', str(out_path), '--pdf-engine=xelatex']
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        finally:
            if tmp_md.exists():
                tmp_md.unlink()
                
        return _result(True, str(out_path))
    except Exception as e:
        return _result(False, error=f"PDF conversion requires 'weasyprint' or 'pandoc'. Error: {str(e)}")


def batch_convert_md(input_dir: str, output_dir: str, format: str = "html") -> Dict:
    """Convert all .md files in a directory to the specified format."""
    try:
        in_p = Path(input_dir)
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)

        converted_files = []
        for f in in_p.glob("*.md"):
            content = f.read_text(encoding='utf-8')
            
            if format == "html":
                res = md_to_html(content)
                ext = ".html"
            elif format == "txt":
                res = strip_md_formatting(content)
                ext = ".txt"
            else:
                return _result(False, error=f"Unsupported format: {format}")

            if res["success"]:
                dest = out_p / (f.stem + ext)
                dest.write_text(str(res["data"]), encoding='utf-8')
                converted_files.append(str(dest))
                
        return _result(True, converted_files)
    except Exception as e:
        return _result(False, error=str(e))


# ---------------------------------------------------------------------------
# Parsing & Extraction Functions
# ---------------------------------------------------------------------------

def parse_headers(md_text: str) -> Dict:
    """Extract all markdown headers with level, text, and positional data."""
    try:
        pattern = re.compile(r'^(#{1,6})\s+(.+?)(?:\s*\{#[^}]+\})?\s*$', re.MULTILINE)
        headers = []
        for m in pattern.finditer(md_text):
            headers.append({
                "level": len(m.group(1)),
                "text": m.group(2).strip(),
                "start": m.start(),
                "end": m.end()
            })
        return _result(True, headers)
    except Exception as e:
        return _result(False, error=str(e))


def extract_links(md_text: str) -> Dict:
    """Extract standard markdown links: [text](url)"""
    try:
        pattern = re.compile(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)')
        links = [{"text": m.group(1), "url": m.group(2)} for m in pattern.finditer(md_text)]
        return _result(True, links)
    except Exception as e:
        return _result(False, error=str(e))


def extract_images(md_text: str) -> Dict:
    """Extract markdown images: ![alt](url)"""
    try:
        pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
        imgs = [{"alt": m.group(1), "url": m.group(2)} for m in pattern.finditer(md_text)]
        return _result(True, imgs)
    except Exception as e:
        return _result(False, error=str(e))


def extract_code_blocks(md_text: str) -> Dict:
    """Extract fenced code blocks with language specifier."""
    try:
        pattern = re.compile(r'```(\w*)\s*\n(.*?)```', re.DOTALL)
        blocks = [{"language": m.group(1).strip() or "text", "code": m.group(2)} for m in pattern.finditer(md_text)]
        return _result(True, blocks)
    except Exception as e:
        return _result(False, error=str(e))


def parse_frontmatter(md_text: str) -> Dict:
    """Parse YAML/frontmatter block at the top of the markdown."""
    try:
        pattern = re.compile(r'^---\s*$\n(.*?)^---\s*$', re.MULTILINE | re.DOTALL)
        match = pattern.match(md_text)
        if not match:
            return _result(False, error="No frontmatter block found.")
            
        fm_text = match.group(1)
        try:
            import yaml
            metadata = yaml.safe_load(fm_text) or {}
        except ImportError:
            metadata = {}
            for line in fm_text.strip().splitlines():
                if ": " in line:
                    k, v = line.split(": ", 1)
                    metadata[k.strip()] = v.strip()
                    
        remaining = md_text[match.end():].strip()
        return _result(True, {"metadata": metadata, "remaining_md": remaining})
    except Exception as e:
        return _result(False, error=str(e))


def find_broken_links(md_text: str) -> Dict:
    """Check extracted links for HTTP 4xx/5xx responses or timeouts."""
    try:
        links_res = extract_links(md_text)
        if not links_res["success"]: return links_res
        
        results = {"working": [], "broken": [], "skipped": []}
        headers = {'User-Agent': 'Mozilla/5.0 ScreenAgent/1.0'}
        
        for link in links_res["data"]:
            url = link["url"]
            if url.startswith(('#', '/', 'mailto:', 'tel:', 'javascript:')):
                results["skipped"].append(url)
                continue
            if not url.startswith(('http://', 'https://')):
                url = "https://" + url if '//' not in url else url
                
            try:
                req = urllib.request.Request(url, headers=headers, method='HEAD')
                resp = urllib.request.urlopen(req, timeout=5)
                if resp.getcode() < 400:
                    results["working"].append(url)
                else:
                    results["broken"].append(url)
            except Exception:
                results["broken"].append(url)
                
        return _result(True, results)
    except Exception as e:
        return _result(False, error=str(e))


# ---------------------------------------------------------------------------
# Manipulation & Generation Functions
# ---------------------------------------------------------------------------

def generate_toc(md_text: str, max_depth: int = 3) -> Dict:
    """Generate a Markdown Table of Contents from headers."""
    try:
        headers_res = parse_headers(md_text)
        if not headers_res["success"]: return headers_res
        
        toc_lines = []
        for h in headers_res["data"]:
            if h["level"] > max_depth: continue
            indent = "  " * (h["level"] - 1)
            slug = re.sub(r'[^\w\s-]', '', h["text"].lower()).strip().replace(' ', '-')
            toc_lines.append(f"{indent}- [{h['text']}](#{slug})")
            
        return _result(True, "\n".join(toc_lines))
    except Exception as e:
        return _result(False, error=str(e))


def format_table(headers: List[str], rows: List[List[str]]) -> Dict:
    """Generate a Markdown table with proper alignment and escaping."""
    try:
        if not headers: return _result(False, error="Headers cannot be empty")
        max_cols = max(len(headers), max((len(r) for r in rows), default=0))
        padded_headers = headers + [""] * (max_cols - len(headers))
        padded_rows = [r + [""] * (max_cols - len(r)) for r in rows]

        escaped_headers = [html.escape(str(h)).replace("|", "\\|") for h in padded_headers]
        escaped_rows = [[html.escape(str(c)).replace("|", "\\|") for c in r] for r in padded_rows]

        lines = [f"| {' | '.join(escaped_headers)} |"]
        lines.append(f"| {' | '.join(['---'] * max_cols)} |")
        for r in escaped_rows:
            lines.append(f"| {' | '.join(r)} |")
            
        return _result(True, "\n".join(lines))
    except Exception as e:
        return _result(False, error=str(e))


def merge_md_files(file_paths: List[str]) -> Dict:
    """Merge multiple markdown files into a single document."""
    try:
        contents = []
        for fp in file_paths:
            p = Path(fp)
            if not p.is_file():
                return _result(False, error=f"File not found: {fp}")
            contents.append(p.read_text(encoding='utf-8'))
        return _result(True, "\n\n---\n\n".join(contents))
    except Exception as e:
        return _result(False, error=str(e))


def split_by_headers(md_text: str, level: int = 2) -> Dict:
    """Split markdown into sections based on a specific header level."""
    try:
        prefix = '#' * level
        escaped_prefix = re.escape(prefix)
        pattern = re.compile(r'^(' + escaped_prefix + r'\s+.+?)\s*\{?#?.+\}?\s*$', re.MULTILINE)
        parts = pattern.split(md_text)
        
        sections = []
        current_header = "root"
        current_content = ""
        
        for part in parts:
            if part.startswith(prefix):
                if current_content.strip() or current_header != "root":
                    sections.append({"header": current_header, "content": current_content.strip()})
                current_header = part.strip('# ').strip()
                current_content = ""
            else:
                current_content += part
                
        if current_content.strip() or current_header != "root":
            sections.append({"header": current_header, "content": current_content.strip()})
            
        return _result(True, sections)
    except Exception as e:
        return _result(False, error=str(e))


def add_header_ids(md_text: str) -> Dict:
    """Append markdown anchor IDs to headers: # Title {#title}"""
    try:
        def _match_repl(m: re.Match) -> str:
            full = m.group(0)
            hashes = m.group(1)
            text = m.group(2).strip()
            if '{#' in full: return full
            slug = re.sub(r'[^\w\s-]', '', text.lower()).strip().replace(' ', '-')
            return f"{hashes} {text} {{#{slug}}}"
            
        pattern = re.compile(r'^(\#{1,6})\s+(.+?)(?:\s*\{#.+\})?\s*$', re.MULTILINE)
        return _result(True, pattern.sub(_match_repl, md_text))
    except Exception as e:
        return _result(False, error=str(e))


def highlight_code_blocks(md_text: str, theme: str = "monokai") -> Dict:
    """Syntax highlight code blocks using Pygments and return HTML-embedded markdown."""
    try:
        style = get_style_by_name(theme)
        formatter = HtmlFormatter(style=style, linenos=False, cssclass='pygments-highlight')
        
        def _hl_block(m: re.Match) -> str:
            lang = m.group(1).strip() or "text"
            code = m.group(2)
            try:
                lexer = get_lexer_by_name(lang, stripall=True)
            except Exception:
                lexer = guess_lexer(code)
            highlighted = highlight(code, lexer, formatter)
            return f"<style>{formatter.get_style_defs('.pygments-highlight')}</style>\n{highlighted}"
            
        pattern = re.compile(r'```(\w*)\s*\n(.*?)```', re.DOTALL)
        return _result(True, pattern.sub(_hl_block, md_text))
    except Exception as e:
        return _result(False, error=str(e))


def strip_md_formatting(md_text: str) -> Dict:
    """Remove all markdown syntax and return plain text."""
    try:
        text = md_text
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`[^`]+`', '', text)
        text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'[*_]{2,4}([^*_]+)[*_]{2,4}', r'\1', text)
        text = re.sub(r'[*_]', '', text)
        text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[-*]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
        
        lines = [line for line in text.splitlines() if line.strip()]
        return _result(True, html.unescape('\n'.join(lines)))
    except Exception as e:
        return _result(False, error=str(e))


def count_words(md_text: str) -> Dict:
    """Count words and characters in cleaned markdown."""
    try:
        clean_res = strip_md_formatting(md_text)
        if not clean_res["success"]:
            return clean_res
            
        text = clean_res["data"]
        words = len(re.findall(r'\b\w+\b', text))
        chars = len(text)
        return _result(True, {"word_count": words, "char_count": chars})
    except Exception as e:
        return _result(False, error=str(e))


def generate_md_from_dict(data: dict, title: str = "") -> Dict:
    """Recursively convert a dictionary to a Markdown structure."""
    try:
        def _dict_to_md(d: dict, indent: int = 0) -> List[str]:
            lines = []
            for k, v in d.items():
                prefix = "  " * indent
                if isinstance(v, dict):
                    lines.append(f"{prefix}- **{html.escape(str(k))}**")
                    lines.extend(_dict_to_md(v, indent + 1))
                elif isinstance(v, list):
                    lines.append(f"{prefix}- **{html.escape(str(k))}**")
                    for item in v:
                        lines.append(f"{prefix}  - {html.escape(str(item))}")
                else:
                    lines.append(f"{prefix}- **{html.escape(str(k))}**: {html.escape(str(v))}")
            return lines

        output = []
        if title:
            output.append(f"# {title}\n")
        output.extend(_dict_to_md(data))
        return _result(True, "\n".join(output))
    except Exception as e:
        return _result(False, error=str(e))


def create_checklist(items: list, checked: list = None) -> Dict:
    """Generate a markdown checklist with optional checked state."""
    try:
        checked_set = set(checked or [])
        lines = []
        for item in items:
            mark = "x" if str(item) in checked_set else " "
            lines.append(f"- [{mark}] {html.escape(str(item))}")
        return _result(True, "\n".join(lines))
    except Exception as e:
        return _result(False, error=str(e))


def insert_section(md_text: str, section: str, after_header: str = "") -> Dict:
    """Insert a markdown section immediately after a target header."""
    try:
        if not after_header:
            return _result(True, section + "\n\n" + md_text)
            
        pattern = re.compile(rf'^(#{1,6})\s+{re.escape(after_header)}\s*{{?#?.*}}?\s*$', re.MULTILINE | re.IGNORECASE)
        match = pattern.search(md_text)
        if not match:
            return _result(False, error=f"Header '{after_header}' not found.")
            
        end_pos = match.end()
        new_text = md_text[:end_pos] + "\n\n" + section + "\n\n" + md_text[end_pos:]
        return _result(True, new_text)
    except Exception as e:
        return _result(False, error=str(e))


def remove_section(md_text: str, header: str) -> Dict:
    """Remove a header and its section up to the next header of equal/lower level."""
    try:
        match = re.search(rf'^(#{1,6})\s+{re.escape(header)}\s*{{?#?.*}}?\s*$', md_text, re.MULTILINE | re.IGNORECASE)
        if not match:
            return _result(False, error=f"Header '{header}' not found.")
            
        curr_level = len(match.group(1))
        start = match.start()
        lines = md_text[start:].splitlines(True)
        end_offset = len(md_text) - start
        
        for i, line in enumerate(lines[1:], 1):
            m = re.match(r'^(#{1,6})\s+', line)
            if m and len(m.group(1)) <= curr_level:
                end_offset = sum(len(l) for l in lines[:i])
                break
                
        new_text = md_text[:start] + md_text[start + end_offset:]
        return _result(True, new_text.strip())
    except Exception as e:
        return _result(False, error=str(e))


def convert_tabs_to_spaces(md_text: str, spaces: int = 4) -> Dict:
    """Convert tab indentation to space indentation."""
    try:
        space_str = ' ' * spaces
        converted_lines = [line.replace('\t', space_str) for line in md_text.splitlines()]
        return _result(True, '\n'.join(converted_lines))
    except Exception as e:
        return _result(False, error=str(e))


def wrap_text(md_text: str, width: int = 80) -> Dict:
    """Apply text wrapping while preserving markdown paragraph breaks."""
    try:
        paragraphs = re.split(r'\n\n+', md_text)
        wrapped = []
        for para in paragraphs:
            if para.strip():
                wrapped.append(textwrap.fill(para, width=width, replace_whitespace=False, expand_tabs=False))
        return _result(True, '\n\n'.join(wrapped))
    except Exception as e:
        return _result(False, error=str(e))