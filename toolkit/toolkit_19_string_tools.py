"""
toolkit_19_string_tools.py
Advanced string manipulation: slugify, truncate, wrap, similarity scoring,
case conversion, padding, pattern detection. Stdlib only.
"""
from __future__ import annotations
import re
import unicodedata
import difflib
import textwrap
import hashlib
from typing import Any, Dict, List

def slugify(text: str, separator: str = "-") -> Dict[str, Any]:
    """Convert text to URL-safe slug."""
    try:
        normalized = unicodedata.normalize("NFKD", text)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^\w\s-]", "", ascii_text.lower())
        slug = re.sub(r"[\s_-]+", separator, slug).strip(separator)
        return {"success": True, "data": slug, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def truncate(text: str, max_length: int = 100, suffix: str = "...") -> Dict[str, Any]:
    try:
        if len(text) <= max_length:
            return {"success": True, "data": text, "error": None}
        cut = max_length - len(suffix)
        return {"success": True, "data": text[:cut] + suffix, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def truncate_words(text: str, max_words: int = 20, suffix: str = "...") -> Dict[str, Any]:
    try:
        words = text.split()
        if len(words) <= max_words:
            return {"success": True, "data": text, "error": None}
        return {"success": True, "data": " ".join(words[:max_words]) + suffix, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def word_wrap(text: str, width: int = 80) -> Dict[str, Any]:
    try:
        wrapped = textwrap.fill(text, width=width)
        return {"success": True, "data": wrapped, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def indent_text(text: str, spaces: int = 4) -> Dict[str, Any]:
    try:
        prefix = " " * spaces
        result = textwrap.indent(text, prefix)
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def pad_left(text: str, width: int, char: str = " ") -> Dict[str, Any]:
    try:
        return {"success": True, "data": text.rjust(width, char[0]), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def pad_right(text: str, width: int, char: str = " ") -> Dict[str, Any]:
    try:
        return {"success": True, "data": text.ljust(width, char[0]), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def pad_center(text: str, width: int, char: str = " ") -> Dict[str, Any]:
    try:
        return {"success": True, "data": text.center(width, char[0]), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def to_camel_case(text: str) -> Dict[str, Any]:
    try:
        words = re.split(r"[\s_\-]+", text.strip())
        result = words[0].lower() + "".join(w.capitalize() for w in words[1:])
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def to_pascal_case(text: str) -> Dict[str, Any]:
    try:
        words = re.split(r"[\s_\-]+", text.strip())
        result = "".join(w.capitalize() for w in words)
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def to_snake_case(text: str) -> Dict[str, Any]:
    try:
        s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
        s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
        s = re.sub(r"[\s\-]+", "_", s)
        return {"success": True, "data": s.lower(), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def to_title_case(text: str) -> Dict[str, Any]:
    try:
        return {"success": True, "data": text.title(), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def similarity_ratio(a: str, b: str) -> Dict[str, Any]:
    """Sequence similarity ratio (0.0-1.0) between two strings."""
    try:
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        return {"success": True, "data": round(ratio, 4), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_close_matches(word: str, possibilities: list, n: int = 3, cutoff: float = 0.6) -> Dict[str, Any]:
    try:
        matches = difflib.get_close_matches(word, possibilities, n=n, cutoff=cutoff)
        return {"success": True, "data": matches, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def count_words(text: str) -> Dict[str, Any]:
    try:
        words = re.findall(r"\b\w+\b", text)
        return {"success": True, "data": {"words": len(words), "chars": len(text), "chars_no_space": len(text.replace(" ", ""))}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def word_frequency(text: str, top_n: int = 10) -> Dict[str, Any]:
    try:
        words = re.findall(r"\b[a-z]+\b", text.lower())
        freq: dict = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return {"success": True, "data": dict(sorted_freq), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def strip_html(html: str) -> Dict[str, Any]:
    try:
        clean = re.sub(r"<[^>]+>", "", html)
        clean = re.sub(r"\s+", " ", clean).strip()
        return {"success": True, "data": clean, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_emails(text: str) -> Dict[str, Any]:
    try:
        pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
        emails = re.findall(pattern, text)
        return {"success": True, "data": list(set(emails)), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_urls(text: str) -> Dict[str, Any]:
    try:
        pattern = r"https?://[^\s<>\"']+"
        urls = re.findall(pattern, text)
        return {"success": True, "data": list(set(urls)), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_numbers(text: str) -> Dict[str, Any]:
    try:
        nums = re.findall(r"-?\d+\.?\d*", text)
        return {"success": True, "data": [float(n) for n in nums], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def reverse_words(text: str) -> Dict[str, Any]:
    try:
        return {"success": True, "data": " ".join(text.split()[::-1]), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def remove_duplicates(items: list) -> Dict[str, Any]:
    try:
        seen: set = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def string_hash(text: str, algorithm: str = "sha256") -> Dict[str, Any]:
    try:
        h = hashlib.new(algorithm)
        h.update(text.encode("utf-8"))
        return {"success": True, "data": h.hexdigest(), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def is_palindrome(text: str) -> Dict[str, Any]:
    try:
        clean = re.sub(r"[^a-z0-9]", "", text.lower())
        return {"success": True, "data": clean == clean[::-1], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def repeat_string(text: str, times: int, separator: str = "") -> Dict[str, Any]:
    try:
        return {"success": True, "data": separator.join([text] * times), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
