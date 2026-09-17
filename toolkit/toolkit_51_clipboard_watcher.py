"""
toolkit_51_clipboard_watcher.py
Monitor clipboard changes, log history, filter by content type,
auto-transform clipboard content, and trigger actions on copy events.
Distinct from clipboard_advanced (basic ops) and clipboard_history_manager.
Focuses on real-time monitoring and transformation pipelines.
"""
from __future__ import annotations
import time
import threading
import re
import json
from typing import Any, Dict, List

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

try:
    import win32clipboard
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

_clipboard_log: list = []
_monitoring = False
_monitor_thread = None

def get_clipboard_text() -> Dict[str, Any]:
    try:
        if HAS_PYPERCLIP:
            text = pyperclip.paste()
            return {"success": True, "data": text, "error": None}
        if HAS_WIN32:
            win32clipboard.OpenClipboard()
            try:
                text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
            return {"success": True, "data": text, "error": None}
        return {"success": False, "data": None, "error": "No clipboard library available"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_clipboard_text(text: str) -> Dict[str, Any]:
    try:
        if HAS_PYPERCLIP:
            pyperclip.copy(text)
            return {"success": True, "data": "Clipboard set", "error": None}
        if HAS_WIN32:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            return {"success": True, "data": "Clipboard set", "error": None}
        return {"success": False, "data": None, "error": "No clipboard library"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_clipboard_length() -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]:
            return r
        return {"success": True, "data": len(r["data"] or ""), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clipboard_contains_url() -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]: return r
        text = r["data"] or ""
        urls = re.findall(r"https?://[^\s]+", text)
        return {"success": True, "data": {"contains_url": bool(urls), "urls": urls}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clipboard_contains_email() -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]: return r
        text = r["data"] or ""
        emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
        return {"success": True, "data": {"contains_email": bool(emails), "emails": emails}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clipboard_is_json() -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]: return r
        text = (r["data"] or "").strip()
        try:
            parsed = json.loads(text)
            return {"success": True, "data": {"is_json": True, "type": type(parsed).__name__}, "error": None}
        except Exception:
            return {"success": True, "data": {"is_json": False}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clipboard_to_uppercase() -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]: return r
        upper = (r["data"] or "").upper()
        return set_clipboard_text(upper)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clipboard_to_lowercase() -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]: return r
        lower = (r["data"] or "").lower()
        return set_clipboard_text(lower)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clipboard_strip_whitespace() -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]: return r
        stripped = " ".join((r["data"] or "").split())
        return set_clipboard_text(stripped)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clipboard_remove_duplicates_lines() -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]: return r
        lines = (r["data"] or "").splitlines()
        seen: set = set()
        unique = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique.append(line)
        return set_clipboard_text("\n".join(unique))
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clipboard_sort_lines() -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]: return r
        lines = sorted((r["data"] or "").splitlines())
        return set_clipboard_text("\n".join(lines))
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clipboard_count_words() -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]: return r
        text = r["data"] or ""
        words = re.findall(r"\b\w+\b", text)
        return {"success": True, "data": {"words": len(words), "lines": text.count("\n") + 1, "chars": len(text)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clipboard_replace(find: str, replace_with: str) -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]: return r
        replaced = (r["data"] or "").replace(find, replace_with)
        set_clipboard_text(replaced)
        return {"success": True, "data": {"replacements": (r["data"] or "").count(find)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clipboard_regex_replace(pattern: str, replacement: str) -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]: return r
        result, count = re.subn(pattern, replacement, r["data"] or "")
        set_clipboard_text(result)
        return {"success": True, "data": {"replacements": count}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clipboard_extract_lines_matching(pattern: str) -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]: return r
        lines = (r["data"] or "").splitlines()
        matches = [l for l in lines if re.search(pattern, l)]
        set_clipboard_text("\n".join(matches))
        return {"success": True, "data": {"matched_lines": len(matches)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clipboard_append_text(text: str) -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]: return r
        combined = (r["data"] or "") + text
        return set_clipboard_text(combined)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clipboard_prepend_text(text: str) -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]: return r
        combined = text + (r["data"] or "")
        return set_clipboard_text(combined)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clipboard_to_snake_case() -> Dict[str, Any]:
    try:
        r = get_clipboard_text()
        if not r["success"]: return r
        text = r["data"] or ""
        s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
        s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
        s = re.sub(r"[\s\-]+", "_", s).lower()
        return set_clipboard_text(s)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
