"""
browser_control.py - Deterministic browser automation via Chrome DevTools Protocol.

Controls Chrome/Edge by CSS selector — no screenshot guessing. Connects via
websocket to a browser launched with --remote-debugging-port.

Imports the CDP client from the sibling gemini_coder_web project. Falls back
gracefully if that project is not present.
"""

import base64
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Import CDP client from gemini_coder_web
# ---------------------------------------------------------------------------
_CDP_AVAILABLE = False
_cdp_module = None

_ai_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_gcw_path = os.path.join(_ai_root, "gemini_coder_web")

if os.path.isdir(_gcw_path) and _gcw_path not in sys.path:
    sys.path.insert(0, _ai_root)

try:
    from gemini_coder_web.cdp_client import (
        CDPConnection,
        discover_cdp_targets,
        find_target_by_url,
        find_target_by_title,
        is_cdp_available,
        DEFAULT_CDP_PORT,
    )
    _CDP_AVAILABLE = True
except ImportError:
    CDPConnection = None
    DEFAULT_CDP_PORT = 9222

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_conn: Optional["CDPConnection"] = None


def _ok(data: Any = None, message: str = "OK") -> Dict[str, Any]:
    return {"success": True, "data": data, "error": None, "message": message}


def _err(error: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "error": error, "message": error}


def _check() -> Optional[Dict[str, Any]]:
    if not _CDP_AVAILABLE:
        return _err("CDP client not available (gemini_coder_web not found)")
    return None


def _need_conn() -> Optional[Dict[str, Any]]:
    chk = _check()
    if chk:
        return chk
    if _conn is None or not _conn.is_connected:
        return _err("Not connected. Call cdp_connect() or cdp_connect_tab() first.")
    return None


# ---------------------------------------------------------------------------
# Connection Management
# ---------------------------------------------------------------------------

def cdp_launch_chrome(url: str = "", port: int = 9222) -> Dict[str, Any]:
    """Launch Chrome with remote debugging enabled on the given port."""
    try:
        chrome_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        chrome = None
        for p in chrome_paths:
            if os.path.isfile(p):
                chrome = p
                break
        if not chrome:
            return _err("Chrome not found in standard locations")

        # Use a separate user-data-dir so CDP works even if Chrome is already open
        cdp_profile = os.path.join(os.environ.get("TEMP", "."), f"chrome_cdp_{port}")
        args = [
            chrome,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={cdp_profile}",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        if url:
            args.append(url)
        subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        time.sleep(3)
        return _ok({"port": port, "url": url},
                    f"Chrome launched on port {port}" + (f" at {url}" if url else ""))
    except Exception as e:
        return _err(str(e))


def cdp_connect(port: int = 9222) -> Dict[str, Any]:
    """Connect to Chrome CDP and list available tabs."""
    chk = _check()
    if chk:
        return chk
    try:
        if not is_cdp_available(port):
            return _err(f"No CDP endpoint on port {port}. Launch Chrome with --remote-debugging-port={port}")
        targets = discover_cdp_targets(port)
        tabs = [{"title": getattr(t, "title", ""), "url": getattr(t, "url", "")}
                for t in targets if getattr(t, "tab_type", "") == "page"]
        return _ok({"tabs": tabs, "count": len(tabs)},
                    f"Connected to CDP on port {port} — {len(tabs)} tabs")
    except Exception as e:
        return _err(str(e))


def cdp_connect_tab(url_pattern: str = "", title_pattern: str = "",
                    port: int = 9222) -> Dict[str, Any]:
    """Connect to a specific browser tab by URL or title substring."""
    chk = _check()
    if chk:
        return chk
    global _conn
    try:
        if not is_cdp_available(port):
            return _err(f"No CDP on port {port}")
        target = None
        if url_pattern:
            target = find_target_by_url(url_pattern, port)
        if not target and title_pattern:
            target = find_target_by_title(title_pattern, port)
        if not target:
            # Fallback: grab first page tab
            targets = discover_cdp_targets(port)
            page_targets = [t for t in targets if getattr(t, "tab_type", "") == "page"]
            if page_targets:
                target = page_targets[0]
        if not target:
            return _err("No matching tab found")
        ws_url = getattr(target, "ws_url", "")
        if not ws_url:
            return _err("Tab has no websocket URL")
        _conn = CDPConnection(ws_url)
        if not _conn.connect():
            _conn = None
            return _err("WebSocket connection failed")
        return _ok({"title": getattr(target, "title", ""), "url": getattr(target, "url", "")},
                    f"Connected to: {getattr(target, 'title', '')[:60]}")
    except Exception as e:
        return _err(str(e))


def cdp_list_tabs(port: int = 9222) -> Dict[str, Any]:
    """List all open browser tabs with titles and URLs."""
    chk = _check()
    if chk:
        return chk
    try:
        targets = discover_cdp_targets(port)
        tabs = [{"title": getattr(t, "title", ""), "url": getattr(t, "url", ""),
                 "id": getattr(t, "target_id", "")}
                for t in targets if getattr(t, "tab_type", "") == "page"]
        return _ok({"tabs": tabs, "count": len(tabs)},
                    f"{len(tabs)} tabs open")
    except Exception as e:
        return _err(str(e))


def cdp_is_connected() -> Dict[str, Any]:
    """Check if CDP connection is active."""
    connected = _conn is not None and _conn.is_connected
    return _ok({"connected": connected},
                "Connected" if connected else "Not connected")


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

def cdp_navigate(url: str) -> Dict[str, Any]:
    """Navigate the connected tab to a URL."""
    chk = _need_conn()
    if chk:
        return chk
    try:
        _conn.send_command("Page.navigate", {"url": url})
        time.sleep(1)
        return _ok({"url": url}, f"Navigated to {url}")
    except Exception as e:
        return _err(str(e))


def cdp_get_page_info() -> Dict[str, Any]:
    """Get current page URL and title."""
    chk = _need_conn()
    if chk:
        return chk
    try:
        url = _conn.evaluate_js("window.location.href")
        title = _conn.evaluate_js("document.title")
        return _ok({"url": url, "title": title}, f"{title} — {url}")
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Element Interaction
# ---------------------------------------------------------------------------

def cdp_find_element(selector: str) -> Dict[str, Any]:
    """Check if a CSS selector matches an element on the page."""
    chk = _need_conn()
    if chk:
        return chk
    try:
        found = _conn.find_element(selector)
        if found:
            text = _conn.get_element_text(selector) or ""
            return _ok({"found": True, "text": text[:200]},
                        f"Found: {selector}")
        return _ok({"found": False}, f"Not found: {selector}")
    except Exception as e:
        return _err(str(e))


def cdp_get_text(selector: str) -> Dict[str, Any]:
    """Get text content of an element by CSS selector."""
    chk = _need_conn()
    if chk:
        return chk
    try:
        text = _conn.get_element_text(selector)
        if text is not None:
            return _ok({"text": text[:2000]}, f"Text ({len(text)} chars)")
        return _err(f"Element not found: {selector}")
    except Exception as e:
        return _err(str(e))


def cdp_get_all_text(selector: str) -> Dict[str, Any]:
    """Get text from ALL elements matching a CSS selector."""
    chk = _need_conn()
    if chk:
        return chk
    try:
        texts = _conn.get_all_elements_text(selector)
        return _ok({"texts": [t[:500] for t in texts], "count": len(texts)},
                    f"{len(texts)} elements matched")
    except Exception as e:
        return _err(str(e))


def cdp_click(selector: str) -> Dict[str, Any]:
    """Click an element by CSS selector."""
    chk = _need_conn()
    if chk:
        return chk
    try:
        ok = _conn.click_element(selector)
        if ok:
            return _ok({"selector": selector}, f"Clicked: {selector}")
        return _err(f"Click failed on: {selector}")
    except Exception as e:
        return _err(str(e))


def cdp_type(selector: str, text: str) -> Dict[str, Any]:
    """Type text into an input/textarea by CSS selector."""
    chk = _need_conn()
    if chk:
        return chk
    try:
        # Detect if contenteditable
        is_ce = _conn.evaluate_js(
            f"!!document.querySelector('{selector}')?.getAttribute('contenteditable')"
        )
        ok = _conn.set_input_value(selector, text, is_contenteditable=bool(is_ce))
        if ok:
            return _ok({"selector": selector, "length": len(text)},
                        f"Typed {len(text)} chars into {selector}")
        return _err(f"Type failed on: {selector}")
    except Exception as e:
        return _err(str(e))


def cdp_press_enter(selector: str = "") -> Dict[str, Any]:
    """Press Enter on the focused or specified element."""
    chk = _need_conn()
    if chk:
        return chk
    try:
        if selector:
            _conn.dispatch_enter_on(selector)
        else:
            _conn.send_command("Input.dispatchKeyEvent", {
                "type": "keyDown", "key": "Enter", "code": "Enter",
                "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13,
            })
            _conn.send_command("Input.dispatchKeyEvent", {
                "type": "keyUp", "key": "Enter", "code": "Enter",
                "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13,
            })
        return _ok(None, "Enter pressed")
    except Exception as e:
        return _err(str(e))


def cdp_run_js(expression: str) -> Dict[str, Any]:
    """Execute JavaScript in the page context and return the result."""
    chk = _need_conn()
    if chk:
        return chk
    try:
        result = _conn.evaluate_js(expression)
        return _ok({"result": result}, "JS executed")
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Page Analysis
# ---------------------------------------------------------------------------

def cdp_get_page_text() -> Dict[str, Any]:
    """Get all visible text from the page body."""
    chk = _need_conn()
    if chk:
        return chk
    try:
        text = _conn.evaluate_js("document.body.innerText")
        return _ok({"text": (text or "")[:5000], "length": len(text or "")},
                    f"Page text: {len(text or '')} chars")
    except Exception as e:
        return _err(str(e))


def cdp_get_links() -> Dict[str, Any]:
    """Get all links on the page (text + href)."""
    chk = _need_conn()
    if chk:
        return chk
    try:
        links = _conn.evaluate_js("""
            Array.from(document.querySelectorAll('a[href]')).slice(0, 100).map(a => ({
                text: (a.innerText || '').trim().substring(0, 100),
                href: a.href
            }))
        """)
        return _ok({"links": links or [], "count": len(links or [])},
                    f"{len(links or [])} links found")
    except Exception as e:
        return _err(str(e))


def cdp_get_form_fields() -> Dict[str, Any]:
    """List all input/select/textarea elements with their types, names, and IDs."""
    chk = _need_conn()
    if chk:
        return chk
    try:
        fields = _conn.evaluate_js("""
            Array.from(document.querySelectorAll('input, select, textarea, [contenteditable="true"]'))
                .slice(0, 50)
                .map(el => ({
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    name: el.name || '',
                    id: el.id || '',
                    placeholder: el.placeholder || '',
                    value: (el.value || el.innerText || '').substring(0, 100),
                    selector: el.id ? '#' + el.id : (el.name ? el.tagName.toLowerCase() + '[name=\"' + el.name + '\"]' : ''),
                    visible: el.offsetParent !== null
                }))
        """)
        return _ok({"fields": fields or [], "count": len(fields or [])},
                    f"{len(fields or [])} form fields found")
    except Exception as e:
        return _err(str(e))


def cdp_fill_form(fields: str) -> Dict[str, Any]:
    """Fill multiple form fields. Pass JSON string: {"selector": "value", ...}."""
    chk = _need_conn()
    if chk:
        return chk
    try:
        if isinstance(fields, str):
            mapping = json.loads(fields)
        else:
            mapping = fields
        filled = []
        for selector, value in mapping.items():
            is_ce = _conn.evaluate_js(
                f"!!document.querySelector('{selector}')?.getAttribute('contenteditable')"
            )
            ok = _conn.set_input_value(selector, str(value), is_contenteditable=bool(is_ce))
            filled.append({"selector": selector, "ok": ok})
        return _ok({"filled": filled}, f"Filled {len(filled)} fields")
    except Exception as e:
        return _err(str(e))


def cdp_scroll(direction: str = "down", amount: int = 500) -> Dict[str, Any]:
    """Scroll the page. Direction: up, down, left, right."""
    chk = _need_conn()
    if chk:
        return chk
    try:
        dx, dy = 0, 0
        d = direction.lower()
        if d == "down":
            dy = amount
        elif d == "up":
            dy = -amount
        elif d == "right":
            dx = amount
        elif d == "left":
            dx = -amount
        _conn.evaluate_js(f"window.scrollBy({dx}, {dy})")
        return _ok({"direction": d, "amount": amount}, f"Scrolled {d} {amount}px")
    except Exception as e:
        return _err(str(e))


def cdp_count_elements(selector: str) -> Dict[str, Any]:
    """Count elements matching a CSS selector."""
    chk = _need_conn()
    if chk:
        return chk
    try:
        count = _conn.evaluate_js(
            f"document.querySelectorAll('{selector}').length"
        )
        return _ok({"count": count, "selector": selector},
                    f"{count} elements match '{selector}'")
    except Exception as e:
        return _err(str(e))
