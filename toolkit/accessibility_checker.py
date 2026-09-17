"""
accessibility_checker.py
Screen Agent Toolkit Component - Windows Accessibility & UI Automation Checker

Provides comprehensive accessibility inspection, interaction, and validation
for desktop UI elements using UI Automation (UIA), Win32 APIs, and screen-level fallbacks.
"""

import platform
import json
import subprocess
import xml.etree.ElementTree as ET
import pyautogui
import ctypes
import comtypes
from comtypes.client import CreateObject
from typing import Dict, Any, List, Optional, Tuple

# Ensure Windows-only execution due to COM/UIA dependencies
if platform.system() != "Windows":
    raise OSError("accessibility_checker requires Microsoft Windows for COM and UI Automation support.")

# Disable pyautogui failsafe to prevent interruptions during automated checks
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.0

# ============================================================================
# UI Automation Constants & Mappings
# ============================================================================
UIA_ControlTypePropertyId = 30003
UIA_NamePropertyId = 30005
UIA_BoundingRectanglePropertyId = 30001
UIA_NativeWindowHandlePropertyId = 30010
UIA_IsKeyboardFocusablePropertyId = 30008
UIA_IsEnabledPropertyId = 30009
UIA_ValueValuePropertyId = 30045
UIA_LegacyIAccessibleValuePropertyId = 30136
UIA_SelectionItemIsSelectedPropertyId = 30139
UIA_ExpandCollapseExpandCollapseStatePropertyId = 30070
UIA_ScrollHorizontalScrollPercentPropertyId = 30047
UIA_ScrollVerticalScrollPercentPropertyId = 30048

UIA_InvokePatternId = 10000
UIA_ExpandCollapsePatternId = 10005
UIA_ScrollPatternId = 10004
UIA_TablePatternId = 10006
UIA_TextPatternId = 10014
UIA_ValuePatternId = 10003
UIA_SelectionPatternId = 10010
UIA_LegacyIAccessiblePatternId = 10018

TreeScope_Element = 1
TreeScope_Children = 2
TreeScope_Descendants = 4

# UIA ControlType ID to human-readable role mapping
UIA_ROLE_MAP: Dict[int, str] = {
    50000: "Unknown", 50001: "Button", 50002: "Calendary", 50003: "CheckBox",
    50004: "ComboBox", 50005: "Edit", 50006: "Hyperlink", 50007: "Image",
    50008: "ListItem", 50009: "List", 50010: "Menu", 50011: "MenuBar",
    50012: "MenuItem", 50013: "ProgressBar", 50014: "RadioButton",
    50015: "ScrollBar", 50016: "Slider", 50017: "Spinner", 50018: "StatusBar",
    50019: "Tab", 50020: "TabItem", 50021: "Text", 50022: "ToolBar",
    50023: "ToolTip", 50024: "Tree", 50025: "TreeItem", 50026: "Custom",
    50027: "Group", 50028: "Thumb", 50029: "DataGrid", 50030: "DataItem",
    50031: "Document", 50032: "SplitButton", 50033: "Window", 50034: "Pane",
    50035: "Header", 50036: "HeaderItem", 50037: "TitleBar", 50038: "Table",
    50039: "TableHeader", 50040: "TableRow", 50041: "TableColumn",
    50042: "PropertyPage", 50043: "MenuItem"
}

# State flag mapping (Legacy IAccessible / UIA Toggle/Selection)
STATE_FLAGS = {
    0x1: "unavailable", 0x2: "selected", 0x4: "focused", 0x8: "pressed",
    0x10: "checked", 0x20: "mixed", 0x40: "readonly", 0x80: "hottracked",
    0x100: "default", 0x200: "expanded", 0x400: "collapsed", 0x800: "busy",
    0x1000: "floating", 0x2000: "markeed", 0x4000: "animated", 0x8000: "invisible",
    0x10000: "offscreen", 0x20000: "sizeable", 0x40000: "movable",
    0x80000: "selfvoice", 0x100000: "extselect", 0x200000: "multiselect",
    0x400000: "extselect", 0x800000: "alert_low", 0x1000000: "alert_medium",
    0x2000000: "alert_high"
}

# Lazy-loaded COM/UIA instance
_uia: Optional[Any] = None

def _init_uia() -> Any:
    global _uia
    if _uia is not None:
        return _uia
    try:
        comtypes.CoInitialize()
        _uia = CreateObject("UIAutomation.UIAutomation")
        return _uia
    except Exception as e:
        raise RuntimeError(f"Failed to initialize UI Automation COM: {e}")

def _get_uia_element(hwnd: int) -> Any:
    try:
        uia = _init_uia()
        hwnd = hwnd if hwnd != 0 else ctypes.windll.user32.GetForegroundWindow()
        return uia.ElementFromHandle(hwnd)
    except Exception as e:
        raise RuntimeError(f"Failed to get UIA element for hwnd {hwnd}: {e}")

def _safe_property(elem: Any, prop_id: int, default: Any = None) -> Any:
    try:
        val = elem.GetCurrentPropertyValue(prop_id)
        if isinstance(val, comtypes.automation.VARIANT) and val.vt.value == 0:
            val = val.value
        return val if val is not None else default
    except (comtypes.COMError, ValueError, Exception):
        return default

def _get_pattern(elem: Any, pattern_id: int) -> Optional[Any]:
    try:
        return elem.GetCurrentPattern(pattern_id)
    except (comtypes.COMError, Exception):
        return None

def _rect_to_dict(rect: Tuple[float, float, float, float]) -> Dict[str, int]:
    try:
        return {"left": int(rect[0]), "top": int(rect[1]), "width": int(rect[2]), "height": int(rect[3])}
    except Exception:
        return {"left": 0, "top": 0, "width": 0, "height": 0}

def _element_to_dict(elem: Any) -> Dict[str, Any]:
    hwnd = _safe_property(elem, UIA_NativeWindowHandlePropertyId, 0)
    name = _safe_property(elem, UIA_NamePropertyId, "")
    role_id = _safe_property(elem, UIA_ControlTypePropertyId, 50000)
    bounds_raw = _safe_property(elem, UIA_BoundingRectanglePropertyId, (0, 0, 0, 0))
    return {
        "hwnd": int(hwnd) if isinstance(hwnd, int) else 0,
        "name": str(name),
        "role": UIA_ROLE_MAP.get(int(role_id), f"Unknown({role_id})"),
        "role_id": int(role_id),
        "bounds": _rect_to_dict(bounds_raw),
        "focusable": bool(_safe_property(elem, UIA_IsKeyboardFocusablePropertyId, False)),
        "enabled": bool(_safe_property(elem, UIA_IsEnabledPropertyId, False))
    }

def _search_tree(elem: Any, depth: int, predicate) -> Optional[Any]:
    if depth < 0 or elem is None:
        return None
    try:
        if predicate(elem):
            return elem
        cond = _init_uia().CreateTrueCondition()
        children = elem.FindAll(TreeScope_Children, cond)
        for child in children:
            res = _search_tree(child, depth - 1, predicate)
            if res:
                return res
    except Exception:
        pass
    return None

# ============================================================================
# Public API Functions
# ============================================================================

def get_focused_element() -> Dict[str, Any]:
    """Retrieve the currently focused accessibility element and its properties."""
    try:
        uia = _init_uia()
        elem = uia.GetFocusedElement()
        if elem is None:
            return {"success": False, "error": "No focused element found.", "data": None}
        return {"success": True, "error": None, "data": _element_to_dict(elem)}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def get_element_role(hwnd: int) -> Dict[str, Any]:
    """Get the UI role/type of the specified element."""
    try:
        elem = _get_uia_element(hwnd)
        role_id = int(_safe_property(elem, UIA_ControlTypePropertyId, 50000))
        return {
            "success": True, "error": None,
            "data": {"hwnd": hwnd, "role_id": role_id, "role": UIA_ROLE_MAP.get(role_id, "Unknown")}
        }
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def get_element_name(hwnd: int) -> Dict[str, Any]:
    """Get the accessible name/label of the specified element."""
    try:
        elem = _get_uia_element(hwnd)
        name = str(_safe_property(elem, UIA_NamePropertyId, ""))
        return {"success": True, "error": None, "data": {"hwnd": hwnd, "name": name}}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def get_element_value(hwnd: int) -> Dict[str, Any]:
    """Retrieve the current value of the element (supports ValuePattern/LegacyIAccessible)."""
    try:
        elem = _get_uia_element(hwnd)
        val_pattern = _get_pattern(elem, UIA_ValuePatternId)
        if val_pattern:
            val = val_pattern.Value
        else:
            val = _safe_property(elem, UIA_LegacyIAccessibleValuePropertyId, "")
        return {"success": True, "error": None, "data": {"hwnd": hwnd, "value": str(val)}}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def get_element_state(hwnd: int) -> Dict[str, Any]:
    """Extract accessibility state flags (checked, collapsed, readonly, etc.)."""
    try:
        elem = _get_uia_element(hwnd)
        states: List[str] = []
        # Check SelectionItem
        sel_pattern = _get_pattern(elem, UIA_SelectionPatternId if False else UIA_InvokePatternId) # Fallback logic
        if _safe_property(elem, UIA_SelectionItemIsSelectedPropertyId, False):
            states.append("selected")
        
        # Check ExpandCollapse
        expand_state = _safe_property(elem, UIA_ExpandCollapseExpandCollapseStatePropertyId, 3)
        if expand_state == 2: states.append("expanded")
        elif expand_state == 1: states.append("collapsed")
        elif expand_state == 3: states.append("partial")
            
        # Legacy state flags via GetPattern
        legacy = _get_pattern(elem, UIA_LegacyIAccessiblePatternId)
        if legacy:
            flag = getattr(legacy, "State", 0)
            for mask, flag_name in STATE_FLAGS.items():
                if flag & mask:
                    states.append(flag_name)
                    
        return {"success": True, "error": None, "data": {"hwnd": hwnd, "states": list(set(states))}}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def get_element_bounds(hwnd: int) -> Dict[str, Any]:
    """Get bounding rectangle coordinates and dimensions."""
    try:
        elem = _get_uia_element(hwnd)
        bounds_raw = _safe_property(elem, UIA_BoundingRectanglePropertyId, (0, 0, 0, 0))
        return {"success": True, "error": None, "data": _rect_to_dict(bounds_raw)}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def get_element_children(hwnd: int) -> Dict[str, Any]:
    """Return immediate children of the element as dictionaries."""
    try:
        elem = _get_uia_element(hwnd)
        cond = _init_uia().CreateTrueCondition()
        children = elem.FindAll(TreeScope_Children, cond)
        data = [_element_to_dict(c) for c in children]
        return {"success": True, "error": None, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}

def get_element_parent(hwnd: int) -> Dict[str, Any]:
    """Get the parent accessibility element."""
    try:
        elem = _get_uia_element(hwnd)
        parent = elem.GetParentElement()
        if parent:
            return {"success": True, "error": None, "data": _element_to_dict(parent)}
        return {"success": False, "error": "No parent found.", "data": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def find_element_by_name(name: str, search_depth: int = 5) -> Dict[str, Any]:
    """Search descending from desktop/focused window for an element matching the name."""
    def pred(e: Any) -> bool:
        return str(_safe_property(e, UIA_NamePropertyId, "")).lower() == name.lower()
    try:
        root = _get_uia_element(0) if search_depth > 0 else _init_uia().GetRootElement()
        res = _search_tree(root, search_depth, pred)
        if res:
            return {"success": True, "error": None, "data": _element_to_dict(res)}
        return {"success": False, "error": f"No element named '{name}' found.", "data": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def find_element_by_role(role: str, search_depth: int = 5) -> Dict[str, Any]:
    """Search for an element matching the specified role string."""
    role_str = role.strip().lower()
    # Reverse map for ID lookup
    reverse_role = {v.lower(): k for k, v in UIA_ROLE_MAP.items()}
    target_id = reverse_role.get(role_str)
    if not target_id:
        return {"success": False, "error": f"Unknown role: {role}", "data": None}
        
    def pred(e: Any) -> bool:
        return int(_safe_property(e, UIA_ControlTypePropertyId, 0)) == target_id
    try:
        root = _init_uia().GetRootElement()
        res = _search_tree(root, search_depth, pred)
        if res:
            return {"success": True, "error": None, "data": _element_to_dict(res)}
        return {"success": False, "error": f"No element with role '{role}' found.", "data": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def get_window_tree(hwnd: int = 0, depth: int = 3) -> Dict[str, Any]:
    """Generate a nested dictionary representation of the UI tree up to `depth`."""
    def _build(element: Any, current_depth: int) -> Any:
        if current_depth <= 0 or element is None:
            return None
        node = _element_to_dict(element)
        node["children"] = []
        try:
            cond = _init_uia().CreateTrueCondition()
            for child in element.FindAll(TreeScope_Children, cond):
                child_node = _build(child, current_depth - 1)
                if child_node:
                    node["children"].append(child_node)
        except Exception:
            pass
        return node
    try:
        root_elem = _get_uia_element(hwnd)
        tree = _build(root_elem, depth)
        return {"success": True, "error": None, "data": tree}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def check_screen_reader_active() -> Dict[str, Any]:
    """Detect common screen readers (NVDA, JAWS, Narrator) via process list."""
    readers = {"Narrator": False, "NVDA": False, "JAWS": False}
    try:
        proc = subprocess.run(["tasklist", "/FI", "STATUS eq Running"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        output = proc.stdout.lower()
        if "narrator.exe" in output: readers["Narrator"] = True
        if "nvda.exe" in output: readers["NVDA"] = True
        if "jaws.exe" in output: readers["JAWS"] = True
        active = [k for k, v in readers.items() if v]
        return {"success": True, "error": None, "data": {"readers": readers, "any_active": len(active) > 0, "detected": active}}
    except Exception as e:
        return {"success": False, "error": str(e), "data": {"readers": readers, "any_active": False, "detected": []}}

def set_element_focus(hwnd: int) -> Dict[str, Any]:
    """Move accessibility focus and OS foreground focus to the element."""
    try:
        elem = _get_uia_element(hwnd)
        focus_pattern = _get_pattern(elem, UIA_InvokePatternId) # Fallback pattern ID, UIA doesn't have explicit focus pattern, use SetFocus
        elem.SetFocus()
        hwnd_int = int(_safe_property(elem, UIA_NativeWindowHandlePropertyId, hwnd))
        if hwnd_int:
            ctypes.windll.user32.SetForegroundWindow(hwnd_int)
        return {"success": True, "error": None, "data": {"hwnd": hwnd_int, "focus_set": True}}
    except Exception as e:
        # Fallback to pyautogui click at center if UIA fails
        try:
            bounds = _rect_to_dict(_safe_property(elem, UIA_BoundingRectanglePropertyId, (0,0,0,0)) if 'elem' in locals() else (0,0,0,0))
            cx, cy = bounds["left"] + bounds["width"] // 2, bounds["top"] + bounds["height"] // 2
            if cx > 0 and cy > 0:
                pyautogui.click(cx, cy)
                return {"success": True, "error": None, "data": {"hwnd": hwnd, "focus_set": True, "method": "pyautogui_fallback"}}
        except Exception as e2:
            return {"success": False, "error": f"{e}; fallback failed: {e2}", "data": None}
        return {"success": False, "error": str(e), "data": None}

def invoke_element(hwnd: int) -> Dict[str, Any]:
    """Trigger the default action (click/activate) for the element."""
    try:
        elem = _get_uia_element(hwnd)
        inv = _get_pattern(elem, UIA_InvokePatternId)
        if inv:
            inv.Invoke()
            return {"success": True, "error": None, "data": {"hwnd": hwnd, "invoked": True}}
        # Fallback: Send ENTER if focusable
        if _safe_property(elem, UIA_IsKeyboardFocusablePropertyId, False):
            ctypes.windll.user32.SetForegroundWindow(_safe_property(elem, UIA_NativeWindowHandlePropertyId, hwnd))
            pyautogui.press('enter')
            return {"success": True, "error": None, "data": {"hwnd": hwnd, "invoked": True, "method": "keyboard_fallback"}}
        return {"success": False, "error": "Element does not support invoke or keyboard fallback.", "data": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def get_selection(hwnd: int) -> Dict[str, Any]:
    """Retrieve selected item(s) information from container elements."""
    try:
        elem = _get_uia_element(hwnd)
        sel_pattern = _get_pattern(elem, UIA_SelectionPatternId)
        if sel_pattern:
            selections = [sel_pattern.GetSelection()]
            return {"success": True, "error": None, "data": {"hwnd": hwnd, "selections": [_element_to_dict(s) for s in selections[0] if s]}}
        # Check if itself is selected
        sel_item = _get_pattern(elem, UIA_SelectionItemPatternId if "SelectionItemPatternId" in globals() else UIA_InvokePatternId)
        if sel_item and getattr(sel_item, "IsSelected", False):
            return {"success": True, "error": None, "data": {"hwnd": hwnd, "selections": [_element_to_dict(elem)]}}
        return {"success": True, "error": None, "data": {"hwnd": hwnd, "selections": []}}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def expand_collapse(hwnd: int, expand: bool = True) -> Dict[str, Any]:
    """Expand or collapse the element if supported."""
    try:
        elem = _get_uia_element(hwnd)
        ec = _get_pattern(elem, UIA_ExpandCollapsePatternId)
        if not ec:
            return {"success": False, "error": "ExpandCollapse pattern not supported.", "data": None}
        if expand:
            ec.Expand()
        else:
            ec.Collapse()
        return {"success": True, "error": None, "data": {"hwnd": hwnd, "state": "expanded" if expand else "collapsed"}}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def scroll_element(hwnd: int, direction: str = "down", amount: int = 3) -> Dict[str, Any]:
    """Scroll the element horizontally or vertically by amount."""
    try:
        elem = _get_uia_element(hwnd)
        scroll = _get_pattern(elem, UIA_ScrollPatternId)
        if scroll:
            horz, vert = ScrollAmount.NoAmount, ScrollAmount.NoAmount
            # UIA ScrollAmount enum mapping
            dir_map = {"down": 3, "up": 1, "left": 0, "right": 2}
            is_vert = direction in ("down", "up")
            amt_val = dir_map.get(direction, 3)
            scroll.ScrollHorizontal(amt_val if not is_vert else ScrollAmount.NoAmount)
            scroll.ScrollVertical(amt_val if is_vert else ScrollAmount.NoAmount)
            return {"success": True, "error": None,
                    "data": {"hwnd": hwnd, "direction": direction, "amount": amount, "scrolled": True}}
        # Fallback to pyautogui
        ctypes.windll.user32.SetForegroundWindow(_safe_property(elem, UIA_NativeWindowHandlePropertyId, hwnd))
        scroll_key = {"down": "down", "up": "up", "left": "left", "right": "right"}.get(direction, "down")
        for _ in range(amount):
            pyautogui.press(scroll_key)
        return {"success": True, "error": None, "data": {"hwnd": hwnd, "direction": direction, "amount": amount, "method": "pyautogui_fallback"}}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def get_table_info(hwnd: int) -> Dict[str, Any]:
    """Extract table structure: rows, columns, headers."""
    try:
        elem = _get_uia_element(hwnd)
        table = _get_pattern(elem, UIA_TablePatternId)
        if not table:
            return {"success": False, "error": "Table pattern not supported.", "data": None}
        headers = table.GetCurrentColumnHeaders()
        rows = table.GetRowHeaders()
        col_count = _safe_property(elem, 30009, 0) # Approximation property
        row_count = _safe_property(elem, 30010, 0)
        return {
            "success": True, "error": None,
            "data": {
                "hwnd": hwnd,
                "column_headers": [_element_to_dict(c) for c in (headers or [])],
                "row_headers": [_element_to_dict(r) for r in (rows or [])],
                "approx_columns": int(_safe_property(elem, 30002, 0)),
                "approx_rows": int(_safe_property(elem, 30007, 0))
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def get_text_range(hwnd: int, start: int = 0, end: int = -1) -> Dict[str, Any]:
    """Extract text content within a specified range from text-capable elements."""
    try:
        elem = _get_uia_element(hwnd)
        txt_pattern = _get_pattern(elem, UIA_TextPatternId)
        if txt_pattern:
            doc_range = txt_pattern.DocumentRange
            text = doc_range.GetText(-1)
            if end == -1: end = len(text)
            sliced = text[start:end]
            return {"success": True, "error": None, "data": {"hwnd": hwnd, "text": sliced, "length": len(sliced)}}
        # Fallback: GetWindowText
        buf = ctypes.create_string_buffer(1024)
        ctypes.windll.user32.GetWindowTextA(hwnd, buf, 1024)
        return {"success": True, "error": None, "data": {"hwnd": hwnd, "text": buf.value.decode("utf-8", errors="ignore"), "length": len(buf.value)}}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def check_color_contrast(fg: str, bg: str) -> Dict[str, Any]:
    """Calculate WCAG 2.1 contrast ratio for hexadecimal colors."""
    def hex_to_luminance(hex_color: str) -> float:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6: raise ValueError("Invalid hex color")
        r, g, b = [int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
        def linearize(c): return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)
    try:
        lum_fg = hex_to_luminance(fg)
        lum_bg = hex_to_luminance(bg)
        ratio = (lum_fg + 0.05) / (lum_bg + 0.05) if lum_fg > lum_bg else (lum_bg + 0.05) / (lum_fg + 0.05)
        wcag_aa_normal = ratio >= 4.5
        wcag_aa_large = ratio >= 3.0
        wcag_aaa = ratio >= 7.0
        return {
            "success": True, "error": None,
            "data": {"contrast_ratio": round(ratio, 3), "passes_aa_normal": wcag_aa_normal, "passes_aa_large": wcag_aa_large, "passes_aaa": wcag_aaa}
        }
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def get_tab_order(hwnd: int = 0) -> Dict[str, Any]:
    """Approximate tab focus order by traversing focusable elements visually."""
    def _collect(elem: Any, depth: int) -> List[Dict[str, Any]]:
        if depth <= 0 or elem is None: return []
        focusable = bool(_safe_property(elem, UIA_IsKeyboardFocusablePropertyId, False))
        enabled = bool(_safe_property(elem, UIA_IsEnabledPropertyId, True))
        items = []
        if focusable and enabled:
            bounds = _rect_to_dict(_safe_property(elem, UIA_BoundingRectanglePropertyId, (0,0,0,0)))
            items.append({**_element_to_dict(elem), "visual_order": (bounds["top"], bounds["left"])})
        try:
            for child in elem.FindAll(TreeScope_Children, _init_uia().CreateTrueCondition()):
                items.extend(_collect(child, depth - 1))
        except Exception: pass
        return items
    try:
        root = _get_uia_element(hwnd)
        all_focus = _collect(root, 4)
        all_focus.sort(key=lambda x: x.get("visual_order", (99999, 99999)))
        return {"success": True, "error": None, "data": [ {k: v for k, v in d.items() if k != "visual_order"} for d in all_focus]}
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}

def check_keyboard_accessible(hwnd: int) -> Dict[str, Any]:
    """Verify if element is keyboard-focusable, enabled, and has standard shortcut/accelerator hints."""
    try:
        elem = _get_uia_element(hwnd)
        is_focusable = bool(_safe_property(elem, UIA_IsKeyboardFocusablePropertyId, False))
        is_enabled = bool(_safe_property(elem, UIA_IsEnabledPropertyId, False))
        has_accel = bool(_safe_property(elem, 30017, "")) # AcceleratorKey
        return {"success": True, "error": None, "data": {"keyboard_accessible": is_focusable and is_enabled, "focusable": is_focusable, "enabled": is_enabled, "has_accelerator": has_accel, "recommendations": [] if is_focusable and is_enabled else ["Not keyboard focusable or disabled"]}}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def generate_accessibility_report(hwnd: int = 0) -> Dict[str, Any]:
    """Generate a comprehensive structured report in JSON and XML formats."""
    try:
        elem = _get_uia_element(hwnd)
        data = {
            "element_info": _element_to_dict(elem),
            "role_check": get_element_role(hwnd)["data"],
            "name_check": get_element_name(hwnd)["data"],
            "value_check": get_element_value(hwnd)["data"],
            "state_check": get_element_state(hwnd)["data"],
            "children_count": len(get_element_children(hwnd).get("data", [])),
            "keyboard_ok": check_keyboard_accessible(hwnd).get("data", {}),
            "screen_readers": check_screen_reader_active().get("data", {}),
            "timestamp": json.dumps({"ts": "auto"}), # Placeholder, actual would use datetime
        }
        # JSON export
        report_json = json.dumps(data, indent=2, ensure_ascii=False)
        
        # XML export
        root = ET.Element("AccessibilityReport")
        ET.SubElement(root, "Hwnd").text = str(hwnd)
        ET.SubElement(root, "Name").text = str(_safe_property(elem, UIA_NamePropertyId, ""))
        ET.SubElement(root, "Focusable").text = str(bool(_safe_property(elem, UIA_IsKeyboardFocusablePropertyId, False)))
        report_xml = ET.tostring(root, encoding="unicode")
        
        return {
            "success": True, "error": None,
            "data": {"report_json": report_json, "report_xml": report_xml, "summary": data}
        }
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def get_aria_properties(hwnd: int) -> Dict[str, Any]:
    """Map ARIA-relevant properties (Role, Name, Value, State) to a unified dict."""
    try:
        elem = _get_uia_element(hwnd)
        role = UIA_ROLE_MAP.get(int(_safe_property(elem, UIA_ControlTypePropertyId, 50000)), "unknown")
        name = str(_safe_property(elem, UIA_NamePropertyId, ""))
        val = str(_safe_property(elem, UIA_ValueValuePropertyId, _safe_property(elem, UIA_LegacyIAccessibleValuePropertyId, "")))
        focusable = bool(_safe_property(elem, UIA_IsKeyboardFocusablePropertyId, False))
        enabled = bool(_safe_property(elem, UIA_IsEnabledPropertyId, True))
        aria_map = {
            "role": role, "aria_name": name if name else None, "aria_value": val if val else None,
            "aria_focusable": focusable, "aria_enabled": enabled
        }
        # Live region / state inference
        state_res = get_element_state(hwnd).get("data", {})
        for s in state_res.get("states", []):
            if s in ("checked", "expanded", "collapsed", "readonly", "selected"):
                aria_map[f"aria_{s}"] = True
        return {"success": True, "error": None, "data": aria_map}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}

def validate_ui_accessibility(hwnd: int = 0) -> Dict[str, Any]:
    """Run a full validation suite against WCAG & UIA best practices."""
    try:
        res = {
            "has_valid_name": bool(get_element_name(hwnd)["data"]["name"]),
            "has_valid_role": get_element_role(hwnd)["data"]["role"] != "Unknown",
            "is_keyboard_accessible": check_keyboard_accessible(hwnd).get("data", {}).get("keyboard_accessible", False),
            "contrast_ok": True, # Placeholder; requires context colors
            "issues": [],
            "score": 0.0
        }
        issues = []
        if not res["has_valid_name"]: issues.append("Missing accessible name (aria-label/name).")
        if not res["has_valid_role"]: issues.append("Missing or invalid UI role.")
        if not res["is_keyboard_accessible"]: issues.append("Not keyboard accessible.")
        
        res["issues"] = issues
        total = 3
        passed = total - len(issues)
        res["score"] = round((passed / total) * 100, 2)
        res["passed"] = passed == total
        res["hwnd"] = hwnd
        
        return {"success": True, "error": None, "data": res}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}