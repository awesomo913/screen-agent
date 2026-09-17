"""
window_control.py - Deterministic Windows desktop automation via pywinauto.

Controls any Windows application by element name, type, and automation ID —
no screenshot guessing. Uses the UIA (UI Automation) backend for modern apps.

Falls back gracefully if pywinauto is not installed.
"""

import os
import re
import time
from typing import Any, Dict, List, Optional

try:
    from pywinauto import Application, Desktop, findwindows
    from pywinauto.controls.uiawrapper import UIAWrapper
    _PYWINAUTO = True
except ImportError:
    _PYWINAUTO = False

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data: Any = None, message: str = "OK") -> Dict[str, Any]:
    return {"success": True, "data": data, "error": None, "message": message}


def _err(error: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "error": error, "message": error}


def _check() -> Optional[Dict[str, Any]]:
    if not _PYWINAUTO:
        return _err("pywinauto not installed. Run: pip install pywinauto")
    return None


def _get_window(title: str):
    """Find and return a window wrapper by title substring."""
    app = Application(backend="uia").connect(title_re=f".*{re.escape(title)}.*", timeout=5)
    return app.window(title_re=f".*{re.escape(title)}.*")


# ---------------------------------------------------------------------------
# Window Discovery
# ---------------------------------------------------------------------------

def win_list_windows() -> Dict[str, Any]:
    """List all visible top-level windows with titles and process info."""
    chk = _check()
    if chk:
        return chk
    try:
        desktop = Desktop(backend="uia")
        windows = []
        for w in desktop.windows():
            title = w.window_text()
            if not title or not title.strip():
                continue
            try:
                pid = w.process_id()
            except Exception:
                pid = 0
            rect = w.rectangle()
            windows.append({
                "title": title,
                "pid": pid,
                "class": w.friendly_class_name(),
                "rect": {"left": rect.left, "top": rect.top,
                         "right": rect.right, "bottom": rect.bottom},
                "visible": w.is_visible(),
            })
        return _ok({"windows": windows, "count": len(windows)},
                    f"{len(windows)} windows found")
    except Exception as e:
        return _err(str(e))


def win_find_window(title: str) -> Dict[str, Any]:
    """Find a window by title substring. Returns its details."""
    chk = _check()
    if chk:
        return chk
    try:
        w = _get_window(title)
        rect = w.rectangle()
        return _ok({
            "title": w.window_text(),
            "class": w.friendly_class_name(),
            "rect": {"left": rect.left, "top": rect.top,
                     "right": rect.right, "bottom": rect.bottom},
            "enabled": w.is_enabled(),
            "visible": w.is_visible(),
        }, f"Found: {w.window_text()}")
    except Exception as e:
        return _err(f"Window '{title}' not found: {e}")


def win_focus_window(title: str) -> Dict[str, Any]:
    """Bring a window to the foreground and focus it."""
    chk = _check()
    if chk:
        return chk
    try:
        w = _get_window(title)
        w.set_focus()
        return _ok({"title": w.window_text()}, f"Focused: {w.window_text()}")
    except Exception as e:
        return _err(str(e))


def win_close_window(title: str) -> Dict[str, Any]:
    """Close a window gracefully."""
    chk = _check()
    if chk:
        return chk
    try:
        w = _get_window(title)
        name = w.window_text()
        w.close()
        return _ok({"title": name}, f"Closed: {name}")
    except Exception as e:
        return _err(str(e))


def win_wait_for_window(title: str, timeout: int = 10) -> Dict[str, Any]:
    """Wait for a window to appear within timeout seconds."""
    chk = _check()
    if chk:
        return chk
    try:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                w = _get_window(title)
                return _ok({"title": w.window_text()},
                            f"Window appeared: {w.window_text()}")
            except Exception:
                time.sleep(0.5)
        return _err(f"Window '{title}' did not appear within {timeout}s")
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Control Discovery
# ---------------------------------------------------------------------------

def win_get_controls(title: str, control_type: str = "") -> Dict[str, Any]:
    """List all controls in a window. Optionally filter by type (Button, Edit, etc.)."""
    chk = _check()
    if chk:
        return chk
    try:
        w = _get_window(title)
        kwargs = {}
        if control_type:
            kwargs["control_type"] = control_type
        controls = []
        for child in w.descendants(**kwargs):
            name = child.window_text()
            ct = child.friendly_class_name()
            try:
                auto_id = child.automation_id()
            except Exception:
                auto_id = ""
            if not name and not auto_id:
                continue
            controls.append({
                "name": name[:100] if name else "",
                "type": ct,
                "auto_id": auto_id,
                "enabled": child.is_enabled(),
                "visible": child.is_visible(),
            })
        # Limit to 80 to avoid overwhelming the LLM
        return _ok({"controls": controls[:80], "total": len(controls)},
                    f"{len(controls)} controls in '{title}'" +
                    (f" (type={control_type})" if control_type else ""))
    except Exception as e:
        return _err(str(e))


def win_find_control(title: str, name: str = "", control_type: str = "",
                     auto_id: str = "") -> Dict[str, Any]:
    """Find a specific control in a window by name, type, or automation ID."""
    chk = _check()
    if chk:
        return chk
    try:
        w = _get_window(title)
        kwargs = {}
        if name:
            kwargs["title"] = name
        if control_type:
            kwargs["control_type"] = control_type
        if auto_id:
            kwargs["auto_id"] = auto_id
        if not kwargs:
            return _err("Provide at least one of: name, control_type, auto_id")
        ctrl = w.child_window(**kwargs)
        return _ok({
            "name": ctrl.window_text(),
            "type": ctrl.friendly_class_name(),
            "enabled": ctrl.is_enabled(),
            "visible": ctrl.is_visible(),
        }, f"Found control: {ctrl.window_text() or auto_id}")
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Control Interaction
# ---------------------------------------------------------------------------

def win_click_button(title: str, button_name: str) -> Dict[str, Any]:
    """Click a button by its visible name in a window."""
    chk = _check()
    if chk:
        return chk
    try:
        w = _get_window(title)
        btn = w.child_window(title=button_name, control_type="Button")
        btn.click_input()
        return _ok({"button": button_name}, f"Clicked '{button_name}'")
    except Exception as e:
        return _err(str(e))


def win_type_in_field(title: str, text: str, field_name: str = "",
                      field_auto_id: str = "") -> Dict[str, Any]:
    """Type text into an edit/text field by name or automation ID."""
    chk = _check()
    if chk:
        return chk
    try:
        w = _get_window(title)
        kwargs = {"control_type": "Edit"}
        if field_name:
            kwargs["title"] = field_name
        elif field_auto_id:
            kwargs["auto_id"] = field_auto_id
        field = w.child_window(**kwargs)
        field.set_edit_text(text)
        return _ok({"field": field_name or field_auto_id, "length": len(text)},
                    f"Typed {len(text)} chars")
    except Exception as e:
        return _err(str(e))


def win_get_text(title: str, control_name: str = "") -> Dict[str, Any]:
    """Read text from a control or the whole window."""
    chk = _check()
    if chk:
        return chk
    try:
        w = _get_window(title)
        if control_name:
            ctrl = w.child_window(title=control_name)
            text = ctrl.window_text()
        else:
            # Get all text from the window
            texts = []
            for child in w.descendants():
                t = child.window_text()
                if t and t.strip():
                    texts.append(t.strip())
            text = "\n".join(texts[:100])
        return _ok({"text": text[:3000]}, f"Text: {len(text)} chars")
    except Exception as e:
        return _err(str(e))


def win_select_menu(title: str, menu_path: str) -> Dict[str, Any]:
    """Click a menu item. menu_path is 'Menu->Submenu->Item' format."""
    chk = _check()
    if chk:
        return chk
    try:
        w = _get_window(title)
        w.menu_select(menu_path)
        return _ok({"menu": menu_path}, f"Selected: {menu_path}")
    except Exception as e:
        return _err(str(e))


def win_select_tab(title: str, tab_name: str) -> Dict[str, Any]:
    """Select a tab in a tab control by its visible name."""
    chk = _check()
    if chk:
        return chk
    try:
        w = _get_window(title)
        tab = w.child_window(title=tab_name, control_type="TabItem")
        tab.click_input()
        return _ok({"tab": tab_name}, f"Selected tab: {tab_name}")
    except Exception as e:
        return _err(str(e))


def win_check_checkbox(title: str, checkbox_name: str, check: bool = True) -> Dict[str, Any]:
    """Check or uncheck a checkbox by name."""
    chk_dep = _check()
    if chk_dep:
        return chk_dep
    try:
        w = _get_window(title)
        cb = w.child_window(title=checkbox_name, control_type="CheckBox")
        if check:
            cb.check()
        else:
            cb.uncheck()
        state = "checked" if check else "unchecked"
        return _ok({"checkbox": checkbox_name, "state": state},
                    f"'{checkbox_name}' {state}")
    except Exception as e:
        return _err(str(e))


def win_select_combobox(title: str, combo_name: str, value: str) -> Dict[str, Any]:
    """Select an item in a dropdown/combobox."""
    chk = _check()
    if chk:
        return chk
    try:
        w = _get_window(title)
        combo = w.child_window(title=combo_name, control_type="ComboBox")
        combo.select(value)
        return _ok({"combo": combo_name, "value": value},
                    f"Selected '{value}' in '{combo_name}'")
    except Exception as e:
        return _err(str(e))


def win_send_keys(title: str, keys: str) -> Dict[str, Any]:
    """Send keystrokes to a window using pywinauto syntax.
    Examples: '{ENTER}', '{TAB}', '^a' (Ctrl+A), '%{F4}' (Alt+F4)."""
    chk = _check()
    if chk:
        return chk
    try:
        w = _get_window(title)
        w.type_keys(keys, with_spaces=True)
        return _ok({"keys": keys}, f"Sent keys: {keys}")
    except Exception as e:
        return _err(str(e))
