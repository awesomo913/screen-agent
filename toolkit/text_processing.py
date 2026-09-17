import re
import difflib
import textwrap
import unicodedata
import string
import collections
import hashlib
import json
import csv
import io
from typing import Dict, List, Any, Optional, Callable, Union


def _format_response(status: str, result: Any, error: Optional[str] = None) -> Dict[str, Any]:
    """Standardized response dictionary factory for consistent toolkit returns."""
    return {"status": status, "result": result, "error": error}


def find_and_replace(text: str, pattern: str, replacement: str, regex: bool = True) -> Dict[str, Any]:
    """Find and replace patterns in text, optionally using regex."""
    try:
        if regex:
            result, count = re.subn(pattern, replacement, text)
        else:
            result = text.replace(pattern, replacement)
            count = text.count(pattern)
        return _format_response("success", {"text": result, "replacements_made": count})
    except re.error as e:
        return _format_response("error", None, f"Regex error: {e}")
    except Exception as e:
        return _format_response("error", None, str(e))


def extract_emails(text: str) -> Dict[str, Any]:
    """Extract unique email addresses from text."""
    try:
        pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        emails = list(set(re.findall(pattern, text)))
        return _format_response("success", {"emails": sorted(emails), "count": len(emails)})
    except Exception as e:
        return _format_response("error", None, str(e))


def extract_urls(text: str) -> Dict[str, Any]:
    """Extract unique URLs from text."""
    try:
        pattern = r'https?://(?:[a-zA-Z0-9$\-_.+!*\'(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+(?:\?[^\s]*)?'
        urls = list(set(re.findall(pattern, text)))
        return _format_response("success", {"urls": sorted(urls), "count": len(urls)})
    except Exception as e:
        return _format_response("error", None, str(e))


def extract_phone_numbers(text: str) -> Dict[str, Any]:
    """Extract unique phone numbers from text (supports common intl/local formats)."""
    try:
        pattern = r'(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        phones = list(set(re.findall(pattern, text)))
        return _format_response("success", {"phone_numbers": sorted(phones), "count": len(phones)})
    except Exception as e:
        return _format_response("error", None, str(e))


def extract_dates(text: str) -> Dict[str, Any]:
    """Extract date-like strings from text."""
    try:
        pattern = r'\b\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}\b'
        dates = re.findall(pattern, text)
        return _format_response("success", {"dates": dates, "count": len(dates)})
    except Exception as e:
        return _format_response("error", None, str(e))


def extract_numbers(text: str) -> Dict[str, Any]:
    """Extract numeric values from text, converting to int/float where possible."""
    try:
        pattern = r'[-+]?\d*\.\d+|\d+'
        raw_numbers = re.findall(pattern, text)
        parsed: List[Union[int, float, str]] = []
        for n in raw_numbers:
            try:
                parsed.append(float(n) if '.' in n else int(n))
            except ValueError:
                parsed.append(n)
        return _format_response("success", {"numbers": parsed, "count": len(parsed)})
    except Exception as e:
        return _format_response("error", None, str(e))


def word_count(text: str) -> Dict[str, Any]:
    """Count words in the text."""
    try:
        words = re.findall(r'\b\w+\b', text)
        return _format_response("success", {"count": len(words)})
    except Exception as e:
        return _format_response("error", None, str(e))


def char_count(text: str, include_spaces: bool = True) -> Dict[str, Any]:
    """Count characters in the text, optionally including spaces."""
    try:
        count = len(text) if include_spaces else len(text.replace(" ", ""))
        return _format_response("success", {"count": count})
    except Exception as e:
        return _format_response("error", None, str(e))


def line_count(text: str) -> Dict[str, Any]:
    """Count lines in the text."""
    try:
        lines = text.splitlines()
        return _format_response("success", {"count": len(lines)})
    except Exception as e:
        return _format_response("error", None, str(e))


def sentence_count(text: str) -> Dict[str, Any]:
    """Approximate sentence count based on standard terminators."""
    try:
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        return _format_response("success", {"count": len(sentences)})
    except Exception as e:
        return _format_response("error", None, str(e))


def text_diff(text1: str, text2: str) -> Dict[str, Any]:
    """Generate a unified diff between two strings."""
    try:
        diff_lines = list(difflib.unified_diff(text1.splitlines(), text2.splitlines(), n=3))
        buffer = io.StringIO()
        buffer.writelines(f"{line}\n" for line in diff_lines if not line.endswith("\n"))
        diff_str = buffer.getvalue()
        return _format_response(
            "success", 
            {"diff": diff_str if diff_str.strip() else "No differences found.", "change_lines": len(diff_lines)}
        )
    except Exception as e:
        return _format_response("error", None, str(e))


def fuzzy_match(text: str, candidates: List[str], threshold: float = 0.6) -> Dict[str, Any]:
    """Find candidates matching the target text above a similarity threshold."""
    try:
        if not (0.0 <= threshold <= 1.0):
            return _format_response("error", None, "Threshold must be between 0.0 and 1.0.")
        matches = []
        for cand in candidates:
            ratio = difflib.SequenceMatcher(None, text.lower(), cand.lower()).ratio()
            if ratio >= threshold:
                matches.append({"candidate": cand, "similarity_ratio": round(ratio, 4)})
        matches.sort(key=lambda x: x["similarity_ratio"], reverse=True)
        return _format_response("success", {"matches": matches, "count": len(matches)})
    except Exception as e:
        return _format_response("error", None, str(e))


def remove_duplicates(text: str, delimiter: str = "\n") -> Dict[str, Any]:
    """Remove duplicate lines/items while preserving original order."""
    try:
        if not delimiter:
            delimiter = "\n"
        parts = text.split(delimiter)
        unique = list(collections.OrderedDict.fromkeys(parts))
        return _format_response("success", {"text": delimiter.join(unique), "removed_count": len(parts) - len(unique)})
    except Exception as e:
        return _format_response("error", None, str(e))


def sort_lines(text: str, reverse: bool = False, key: Optional[Callable[[str], Any]] = None) -> Dict[str, Any]:
    """Sort lines in the text based on an optional key function."""
    try:
        lines = text.splitlines()
        sorted_lines = sorted(lines, key=key, reverse=reverse)
        return _format_response("success", {"text": "\n".join(sorted_lines)})
    except Exception as e:
        return _format_response("error", None, str(e))


def wrap_text(text: str, width: int = 70) -> Dict[str, Any]:
    """Wrap text to a specified width."""
    try:
        wrapped = textwrap.fill(text, width=width, replace_whitespace=False, break_long_words=True)
        return _format_response("success", {"text": wrapped})
    except Exception as e:
        return _format_response("error", None, str(e))


def truncate_text(text: str, max_length: int, suffix: str = "...") -> Dict[str, Any]:
    """Truncate text to max_length, appending a suffix if truncation occurs."""
    try:
        if len(text) <= max_length:
            return _format_response("success", {"text": text, "truncated": False})
        cut_length = max(0, max_length - len(suffix))
        result = text[:cut_length] + suffix
        return _format_response("success", {"text": result, "truncated": True})
    except Exception as e:
        return _format_response("error", None, str(e))


def slugify(text: str) -> Dict[str, Any]:
    """Convert text to a URL-friendly slug."""
    try:
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
        text = re.sub(r'[^\w\s-]', '', text.lower())
        text = re.sub(r'[\s_]+', '-', text)
        text = re.sub(r'-+', '-', text).strip('-')
        return _format_response("success", {"slug": text})
    except Exception as e:
        return _format_response("error", None, str(e))


def camel_to_snake(text: str) -> Dict[str, Any]:
    """Convert CamelCase or PascalCase to snake_case."""
    try:
        s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', text)
        result = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        return _format_response("success", {"converted": result})
    except Exception as e:
        return _format_response("error", None, str(e))


def snake_to_camel(text: str) -> Dict[str, Any]:
    """Convert snake_case to lowerCamelCase."""
    try:
        components = text.split('_')
        result = components[0] + ''.join(x.title() for x in components[1:])
        return _format_response("success", {"converted": result})
    except Exception as e:
        return _format_response("error", None, str(e))


def title_case(text: str) -> Dict[str, Any]:
    """Convert text to Title Case."""
    try:
        result = string.capwords(text)
        return _format_response("success", {"converted": result})
    except Exception as e:
        return _format_response("error", None, str(e))


def remove_html_tags(text: str) -> Dict[str, Any]:
    """Strip HTML/XML tags from text."""
    try:
        result = re.compile(r'<[^>]+>').sub('', text)
        return _format_response("success", {"text": result})
    except Exception as e:
        return _format_response("error", None, str(e))


def escape_html(text: str) -> Dict[str, Any]:
    """Escape special HTML characters in text."""
    try:
        escape_map = {'&': '&amp;', '"': '&quot;', "'": '&#x27;', '>': '&gt;', '<': '&lt;'}
        result = "".join(escape_map.get(c, c) for c in text)
        return _format_response("success", {"text": result})
    except Exception as e:
        return _format_response("error", None, str(e))


def normalize_whitespace(text: str) -> Dict[str, Any]:
    """Collapse multiple whitespace characters into single spaces and strip edges."""
    try:
        result = re.sub(r'\s+', ' ', text).strip()
        return _format_response("success", {"text": result})
    except Exception as e:
        return _format_response("error", None, str(e))


def generate_hash(text: str, algorithm: str = "sha256") -> Dict[str, Any]:
    """Generate a cryptographic hash of the text."""
    try:
        h = hashlib.new(algorithm)
        h.update(text.encode('utf-8'))
        return _format_response("success", {"hash": h.hexdigest(), "algorithm": algorithm})
    except ValueError as e:
        return _format_response("error", None, f"Unsupported algorithm '{algorithm}': {e}")
    except Exception as e:
        return _format_response("error", None, str(e))


def template_render(template: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    """Render a template string by replacing {key} placeholders with values."""
    try:
        def _replacer(match: re.Match) -> str:
            key = match.group(1)
            if key not in variables:
                return match.group(0)
            val = variables[key]
            if isinstance(val, (dict, list)):
                return json.dumps(val)
            if isinstance(val, (list, tuple)) and len(val) > 0 and isinstance(val[0], str):
                buf = io.StringIO()
                writer = csv.writer(buf)
                writer.writerow(list(val))
                return buf.getvalue().strip()
            return str(val)

        rendered = re.sub(r'\{(\w+)\}', _replacer, template)
        return _format_response("success", {"text": rendered})
    except Exception as e:
        return _format_response("error", None, str(e))