"""
regex_actions.py - Regex pattern matching, testing, and extraction toolkit.
Dependencies: re (stdlib)
"""

import re
from typing import Dict, List, Any, Optional


def _format_response(status: str, result: Any, error: Optional[str] = None) -> Dict[str, Any]:
    return {"status": status, "result": result, "error": error}


def regex_match(text: str, pattern: str, flags: int = 0) -> Dict[str, Any]:
    """Test whether a regex pattern matches text and return match details."""
    try:
        m = re.search(pattern, text, flags)
        if m:
            return _format_response("success", {
                "matched": True, "match": m.group(),
                "start": m.start(), "end": m.end(),
                "groups": list(m.groups()),
                "groupdict": m.groupdict(),
            })
        return _format_response("success", {"matched": False})
    except re.error as e:
        return _format_response("error", None, f"Regex error: {e}")


def regex_find_all(text: str, pattern: str, flags: int = 0) -> Dict[str, Any]:
    """Find all occurrences of a regex pattern in text."""
    try:
        matches = re.findall(pattern, text, flags)
        return _format_response("success", {"matches": matches, "count": len(matches)})
    except re.error as e:
        return _format_response("error", None, f"Regex error: {e}")


def regex_replace(text: str, pattern: str, replacement: str, flags: int = 0, max_count: int = 0) -> Dict[str, Any]:
    """Replace regex pattern matches in text."""
    try:
        result, count = re.subn(pattern, replacement, text, count=max_count, flags=flags)
        return _format_response("success", {"text": result, "replacements": count})
    except re.error as e:
        return _format_response("error", None, f"Regex error: {e}")


def regex_split(text: str, pattern: str, max_split: int = 0, flags: int = 0) -> Dict[str, Any]:
    """Split text by a regex pattern."""
    try:
        parts = re.split(pattern, text, maxsplit=max_split, flags=flags)
        return _format_response("success", {"parts": parts, "count": len(parts)})
    except re.error as e:
        return _format_response("error", None, f"Regex error: {e}")


def regex_validate(pattern: str) -> Dict[str, Any]:
    """Validate whether a regex pattern compiles without errors."""
    try:
        compiled = re.compile(pattern)
        return _format_response("success", {
            "valid": True, "pattern": pattern,
            "groups": compiled.groups, "groupindex": dict(compiled.groupindex),
        })
    except re.error as e:
        return _format_response("success", {"valid": False, "error": str(e)})


def regex_extract_groups(text: str, pattern: str, flags: int = 0) -> Dict[str, Any]:
    """Extract all named and positional capture groups from all matches."""
    try:
        results = []
        for m in re.finditer(pattern, text, flags):
            results.append({
                "match": m.group(), "start": m.start(), "end": m.end(),
                "groups": list(m.groups()), "groupdict": m.groupdict(),
            })
        return _format_response("success", {"matches": results, "count": len(results)})
    except re.error as e:
        return _format_response("error", None, f"Regex error: {e}")


def regex_escape(text: str) -> Dict[str, Any]:
    """Escape special regex characters in a string."""
    try:
        escaped = re.escape(text)
        return _format_response("success", {"escaped": escaped})
    except Exception as e:
        return _format_response("error", None, str(e))
