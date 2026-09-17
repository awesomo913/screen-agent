# form_filler.py
"""
Screen‑Agent Toolkit – Form filler utilities

Supported drivers:
    * Selenium WebDriver (any browser)
    * Playwright Page (sync API)

Features:
    - Detect fields in a form (static + dynamic)
    - Fill every common HTML input type
    - Auto‑fill from a data map or JSON payload
    - Generate realistic fake data
    - Submit, validate, clear, save/restore state
    - Simple captcha handling (placeholder)
    - Batch processing of many forms
"""

from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple, Union

from bs4 import BeautifulSoup
from faker import Faker
from lxml import etree

# Selenium imports (optional – guard against missing library)
try:
    from selenium.webdriver.remote.webdriver import WebDriver as SeleniumDriver
    from selenium.common.exceptions import (
        NoSuchElementException,
        ElementNotInteractableException,
        WebDriverException,
    )
except Exception:  # pragma: no cover
    SeleniumDriver = None  # type: ignore

# Playwright imports (sync API)
try:
    from playwright.sync_api import Page as PlaywrightPage, sync_playwright
    from playwright.sync_api import Error as PlaywrightError
except Exception:  # pragma: no cover
    PlaywrightPage = None  # type: ignore

# --------------------------------------------------------------------------- #
# Helper utilities
# --------------------------------------------------------------------------- #
_fake = Faker()
_fake.seed_instance(0)  # deterministic for testing, remove for true randomness


def _is_selenium(driver: Any) -> bool:
    """Return True if `driver` looks like a Selenium WebDriver."""
    return SeleniumDriver is not None and isinstance(driver, SeleniumDriver)


def _is_playwright(driver: Any) -> bool:
    """Return True if `driver` looks like a Playwright Page."""
    return PlaywrightPage is not None and isinstance(driver, PlaywrightPage)


def _find_element(
    driver: Any, selector: str
) -> Tuple[Union[Any, None], Dict[str, Any]]:
    """
    Locate a single element using CSS selector.
    Returns (element, meta) where meta contains ``found`` and an optional ``error``.
    """
    meta: Dict[str, Any] = {"found": False, "selector": selector}
    try:
        if _is_selenium(driver):
            element = driver.find_element("css selector", selector)
        elif _is_playwright(driver):
            element = driver.query_selector(selector)
        else:
            raise TypeError("Unsupported driver type")
        meta["found"] = True
        return element, meta
    except (NoSuchElementException, PlaywrightError) as exc:
        meta["error"] = str(exc)
        return None, meta
    except Exception as exc:  # pragma: no cover
        meta["error"] = f"Unexpected: {exc}"
        return None, meta


def _execute_js(driver: Any, script: str, *args) -> Any:
    """Execute JavaScript on the underlying page."""
    if _is_selenium(driver):
        return driver.execute_script(script, *args)
    elif _is_playwright(driver):
        return driver.evaluate(script, *args)
    else:
        raise TypeError("Unsupported driver type")


# --------------------------------------------------------------------------- #
# Core detection
# --------------------------------------------------------------------------- #
def detect_form_fields(page_source: str) -> Dict[str, Any]:
    """
    Parse `page_source` with BeautifulSoup + lxml and return a dict mapping
    field ``name`` → ``type`` (e.g. ``text``, ``email``, ``select`` …).

    Returns:
        {
            "fields": {
                "username": "text",
                "password": "password",
                "country": "select",
                ...
            },
            "errors": []
        }
    """
    result: Dict[str, Any] = {"fields": {}, "errors": []}
    try:
        soup = BeautifulSoup(page_source, "lxml")
        form = soup.find("form")
        if not form:
            result["errors"].append("No <form> element found.")
            return result

        for input_tag in form.find_all(["input", "select", "textarea"]):
            name = input_tag.get("name") or input_tag.get("id")
            if not name:
                continue
            tag_name = input_tag.name.lower()
            if tag_name == "input":
                input_type = input_tag.get("type", "text").lower()
                result["fields"][name] = input_type
            elif tag_name == "select":
                result["fields"][name] = "select"
            elif tag_name == "textarea":
                result["fields"][name] = "textarea"
    except Exception as exc:  # pragma: no cover
        result["errors"].append(str(exc))
    return result


# --------------------------------------------------------------------------- #
# Individual field fillers
# --------------------------------------------------------------------------- #
def fill_text_field(driver: Any, selector: str, value: str) -> Dict[str, Any]:
    """
    Fill a generic ``<input type="text">`` (or ``email``, ``url`` …) field.
    """
    element, meta = _find_element(driver, selector)
    if not element:
        return {"success": False, "msg": "Element not found", **meta}
    try:
        element.clear()
        element.send_keys(value)
        return {"success": True, "msg": "Text entered", **meta}
    except (ElementNotInteractableException, PlaywrightError) as exc:
        return {"success": False, "msg": str(exc), **meta}


def fill_select_dropdown(driver: Any, selector: str, value: str) -> Dict[str, Any]:
    """
    Select an ``<option>`` by visible text or value.
    """
    element, meta = _find_element(driver, selector)
    if not element:
        return {"success": False, "msg": "Select element not found", **meta}
    try:
        if _is_selenium(driver):
            from selenium.webdriver.support.ui import Select

            select = Select(element)
            try:
                select.select_by_visible_text(value)
            except NoSuchElementException:
                select.select_by_value(value)
        else:  # Playwright
            # Playwright's `select_option` works with value strings
            element.select_option(label=value)  # try label first
            # fallback to value if label fails – ignore errors
            element.select_option(value=value)
        return {"success": True, "msg": "Option selected", **meta}
    except Exception as exc:  # pragma: no cover
        return {"success": False, "msg": str(exc), **meta}


def fill_checkbox(driver: Any, selector: str, checked: bool) -> Dict[str, Any]:
    """Check or uncheck a checkbox."""
    element, meta = _find_element(driver, selector)
    if not element:
        return {"success": False, "msg": "Checkbox not found", **meta}
    try:
        is_checked = element.is_selected() if _is_selenium(driver) else element.is_checked()
        if checked != is_checked:
            element.click()
        return {"success": True, "msg": f"Checkbox set to {checked}", **meta}
    except Exception as exc:  # pragma: no cover
        return {"success": False, "msg": str(exc), **meta}


def fill_radio_button(driver: Any, selector: str, value: str) -> Dict[str, Any]:
    """
    Choose a radio button inside a group by its ``value`` attribute.
    ``selector`` should point to the *group* (e.g. ``name=gender``).
    """
    # Find all radios matching the selector (group)
    elements, meta = [], {"found": False, "selector": selector}
    try:
        if _is_selenium(driver):
            elements = driver.find_elements("css selector", selector)
        else:
            elements = driver.query_selector_all(selector)
        meta["found"] = True
    except Exception as exc:  # pragma: no cover
        meta["error"] = str(exc)

    if not elements:
        return {"success": False, "msg": "Radio group not found", **meta}

    for el in elements:
        el_val = el.get_attribute("value") if _is_selenium(driver) else el.get_attribute("value")
        if el_val == value:
            try:
                el.click()
                return {"success": True, "msg": f"Radio set to {value}", **meta}
            except Exception as exc:  # pragma: no cover
                return {"success": False, "msg": str(exc), **meta}
    return {"success": False, "msg": f"Radio with value '{value}' not found", **meta}


def fill_textarea(driver: Any, selector: str, text: str) -> Dict[str, Any]:
    """Enter multi‑line text into a <textarea>."""
    element, meta = _find_element(driver, selector)
    if not element:
        return {"success": False, "msg": "Textarea not found", **meta}
    try:
        element.clear()
        element.send_keys(text)
        return {"success": True, "msg": "Textarea filled", **meta}
    except Exception as exc:  # pragma: no cover
        return {"success": False, "msg": str(exc), **meta}


def fill_date_field(driver: Any, selector: str, date_str: str) -> Dict[str, Any]:
    """Set a value for <input type='date'> (ISO format)."""
    element, meta = _find_element(driver, selector)
    if not element:
        return {"success": False, "msg": "Date field not found", **meta}
    try:
        element.clear()
        element.send_keys(date_str)
        return {"success": True, "msg": f"Date set to {date_str}", **meta}
    except Exception as exc:  # pragma: no cover
        return {"success": False, "msg": str(exc), **meta}


def fill_file_upload(driver: Any, selector: str, filepath: Union[str, Path]) -> Dict[str, Any]:
    """Upload a file; `filepath` must exist."""
    element, meta = _find_element(driver, selector)
    if not element:
        return {"success": False, "msg": "File input not found", **meta}
    path = Path(filepath).expanduser().resolve()
    if not path.is_file():
        return {"success": False, "msg": f"File does not exist: {path}", **meta}
    try:
        element.send_keys(str(path))
        return {"success": True, "msg": f"Uploaded {path.name}", **meta}
    except Exception as exc:  # pragma: no cover
        return {"success": False, "msg": str(exc), **meta}


def fill_hidden_field(driver: Any, selector: str, value: str) -> Dict[str, Any]:
    """Set a hidden input's value via JavaScript."""
    element, meta = _find_element(driver, selector)
    if not element:
        return {"success": False, "msg": "Hidden field not found", **meta}
    try:
        script = "arguments[0].value = arguments[1];"
        _execute_js(driver, script, element, value)
        return {"success": True, "msg": "Hidden value set", **meta}
    except Exception as exc:  # pragma: no cover
        return {"success": False, "msg": str(exc), **meta}


def fill_range_slider(driver: Any, selector: str, value: Union[int, float]) -> Dict[str, Any]:
    """Set a <input type='range'> using JavaScript (as Selenium cannot always drag)."""
    element, meta = _find_element(driver, selector)
    if not element:
        return {"success": False, "msg": "Range slider not found", **meta}
    try:
        script = "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input'));"
        _execute_js(driver, script, element, value)
        return {"success": True, "msg": f"Range set to {value}", **meta}
    except Exception as exc:  # pragma: no cover
        return {"success": False, "msg": str(exc), **meta}


def fill_multi_select(driver: Any, selector: str, values: Sequence[str]) -> Dict[str, Any]:
    """Select multiple options in a <select multiple>."""
    element, meta = _find_element(driver, selector)
    if not element:
        return {"success": False, "msg": "Multi‑select not found", **meta}
    try:
        if _is_selenium(driver):
            from selenium.webdriver.support.ui import Select

            select = Select(element)
            select.deselect_all()
            for v in values:
                select.select_by_visible_text(v)
        else:  # Playwright
            element.select_option([{"label": v} for v in values])
        return {"success": True, "msg": f"Selected {len(values)} options", **meta}
    except Exception as exc:  # pragma: no cover
        return {"success": False, "msg": str(exc), **meta}


def fill_color_picker(driver: Any, selector: str, color: str) -> Dict[str, Any]:
    """Set a color input (expects a CSS hex value)."""
    element, meta = _find_element(driver, selector)
    if not element:
        return {"success": False, "msg": "Color picker not found", **meta}
    try:
        script = "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input'));"
        _execute_js(driver, script, element, color)
        return {"success": True, "msg": f"Color set to {color}", **meta}
    except Exception as exc:  # pragma: no cover
        return {"success": False, "msg": str(exc), **meta}


def fill_autocomplete(
    driver: Any,
    selector: str,
    value: str,
    wait: float = 0.5,
) -> Dict[str, Any]:
    """
    Fill an autocomplete-enabled field. The function types the value,
    waits for suggestions and then presses ENTER.
    """
    element, meta = _find_element(driver, selector)
    if not element:
        return {"success": False, "msg": "Autocomplete field not found", **meta}
    try:
        element.clear()
        element.send_keys(value)
        time.sleep(wait)
        element.send_keys("\ue007")  # ENTER key
        return {"success": True, "msg": "Autocomplete entered", **meta}
    except Exception as exc:  # pragma: no cover
        return {"success": False, "msg": str(exc), **meta}


def fill_captcha_field(driver: Any, selector: str, value: str) -> Dict[str, Any]:
    """
    Very naive captcha filler – for tests only. Real captchas need external services.
    """
    # Re‑use regular text field logic
    return fill_text_field(driver, selector, value)


# --------------------------------------------------------------------------- #
# High‑level helpers
# --------------------------------------------------------------------------- #
def auto_fill_form(
    driver: Any,
    form_selector: str,
    data_map: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Iterate over ``data_map`` (field_name → value) and attempt to fill the form.
    """
    result: Dict[str, Any] = {"filled": 0, "failed": 0, "details": []}
    form_element, meta = _find_element(driver, form_selector)
    if not form_element:
        return {"success": False, "msg": "Form not found", **meta}

    for field_name, value in data_map.items():
        # Heuristic selector generation – try name, id, then attribute equals
        selectors = [
            f"[name='{field_name}']",
            f"#{field_name}",
            f"[id='{field_name}']",
        ]
        filled = False
        for sel in selectors:
            # Decide which filler to use based on Python type / content
            if isinstance(value, bool):
                res = fill_checkbox(driver, sel, value)
            elif isinstance(value, (int, float)):
                # Could be range, number, or date – try generic text first
                res = fill_text_field(driver, sel, str(value))
            elif isinstance(value, str):
                # Guess by selector attribute
                try:
                    # Peek at the element type if it exists
                    el, _ = _find_element(driver, sel)
                    if el:
                        typ = el.get_attribute("type") if _is_selenium(driver) else el.get_attribute("type")
                        if typ == "email":
                            res = fill_text_field(driver, sel, value)
                        elif typ == "date":
                            res = fill_date_field(driver, sel, value)
                        elif typ == "color":
                            res = fill_color_picker(driver, sel, value)
                        elif typ == "file":
                            res = fill_file_upload(driver, sel, value)
                        elif typ == "hidden":
                            res = fill_hidden_field(driver, sel, value)
                        elif typ == "range":
                            res = fill_range_slider(driver, sel, float(value))
                        else:
                            res = fill_text_field(driver, sel, value)
                    else:
                        # Fallback to generic text
                        res = fill_text_field(driver, sel, value)
                except Exception:
                    res = fill_text_field(driver, sel, value)
            else:
                # Fallback to JSON dump
                res = fill_text_field(driver, sel, json.dumps(value))

            if res.get("success"):
                filled = True
                result["filled"] += 1
                result["details"].append({"field": field_name, "selector": sel, "status": "ok"})
                break
            else:
                # Continue trying other selectors
                continue
        if not filled:
            result["failed"] += 1
            result["details"].append({"field": field_name, "selector": selectors, "status": "failed"})
    return {"success": result["failed"] == 0, "summary": result}


def fill_form_from_json(
    driver: Any,
    form_selector: str,
    json_data: Union[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    """Accept a JSON string or dict and delegate to :func:`auto_fill_form`."""
    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError as exc:
            return {"success": False, "msg": f"Invalid JSON: {exc}"}
    else:
        data = dict(json_data)
    return auto_fill_form(driver, form_selector, data)


def generate_fake_data(field_types: Mapping[str, str]) -> Dict[str, Any]:
    """
    Produce fake data for a set of ``field_name → type`` mappings.
    Supported types: text, email, url, phone, address, city, zip, company,
    date, datetime, number, bool, color, file (returns a temporary path).
    """
    fake_data: Dict[str, Any] = {}
    for name, typ in field_types.items():
        typ = typ.lower()
        if typ in ("text", "search", "textarea"):
            fake_data[name] = _fake.sentence(nb_words=6)
        elif typ == "email":
            fake_data[name] = _fake.email()
        elif typ == "url":
            fake_data[name] = _fake.url()
        elif typ in ("tel", "phone"):
            fake_data[name] = _fake.phone_number()
        elif typ in ("address", "street"):
            fake_data[name] = _fake.street_address()
        elif typ == "city":
            fake_data[name] = _fake.city()
        elif typ in ("zip", "postalcode"):
            fake_data[name] = _fake.postcode()
        elif typ == "company":
            fake_data[name] = _fake.company()
        elif typ == "date":
            fake_data[name] = _fake.date(pattern="%Y-%m-%d")
        elif typ == "datetime":
            fake_data[name] = _fake.iso8601()
        elif typ in ("number", "int", "float"):
            fake_data[name] = random.randint(0, 1000)
        elif typ == "bool":
            fake_data[name] = random.choice([True, False])
        elif typ == "color":
            fake_data[name] = f"#{random.randint(0, 0xFFFFFF):06x}"
        elif typ == "file":
            # Generate a small temp file
            tmp = Path.cwd() / f".tmp_{name}.txt"
            tmp.write_text(_fake.text(max_nb_chars=100))
            fake_data[name] = str(tmp)
        else:
            # Default to a generic word
            fake_data[name] = _fake.word()
    return fake_data


def smart_field_detection(driver: Any, form_selector: str) -> Dict[str, Any]:
    """
    Combine static detection (HTML parsing) with runtime inspection to
    produce a map of ``field_name → selector``.
    """
    # Step 1 – pull raw HTML from the page
    page_source = driver.page_source if _is_selenium(driver) else driver.content()
    fields_info = detect_form_fields(page_source)

    # Step 2 – build selector map
    selector_map: Dict[str, str] = {}
    for name in fields_info.get("fields", {}):
        # Prefer id > name > generic attribute selector
        for candidate in (f"#{name}", f"[name='{name}']", f"[id='{name}']"):
            el, meta = _find_element(driver, candidate)
            if el and meta.get("found"):
                selector_map[name] = candidate
                break
        else:
            selector_map[name] = f"[name='{name}']"  # fallback
    return {"fields": selector_map, "errors": fields_info.get("errors", [])}


def submit_form(driver: Any, form_selector: str) -> Dict[str, Any]:
    """Attempt to submit the form via button click or native submit."""
    form_el, meta = _find_element(driver, form_selector)
    if not form_el:
        return {"success": False, "msg": "Form not found", **meta}
    try:
        # Prefer a <button type='submit'> inside the form
        submit_btn = form_el.find_element("css selector", "button[type='submit'], input[type='submit']")
        submit_btn.click()
        return {"success": True, "msg": "Form submitted", **meta}
    except Exception:
        # Fallback to JS submit()
        try:
            _execute_js(driver, "arguments[0].submit();", form_el)
            return {"success": True, "msg": "Form submitted via JS", **meta}
        except Exception as exc:  # pragma: no cover
            return {"success": False, "msg": str(exc), **meta}


def validate_form_filled(driver: Any, form_selector: str) -> Dict[str, Any]:
    """
    Checks that required inputs have non‑empty values.
    Returns a list of missing field selectors.
    """
    form_el, meta = _find_element(driver, form_selector)
    if not form_el:
        return {"success": False, "msg": "Form not found", **meta}
    missing: List[str] = []
    try:
        required = form_el.find_elements("css selector", "[required]")
        for el in required:
            val = el.get_attribute("value") if _is_selenium(driver) else el.get_attribute("value")
            if not val:
                # Build a selector for reporting
                name = el.get_attribute("name") or el.get_attribute("id")
                selector = f"[name='{name}']" if name else "unknown"
                missing.append(selector)
    except Exception as exc:  # pragma: no cover
        return {"success": False, "msg": str(exc), **meta}
    return {"success": len(missing) == 0, "missing": missing, **meta}


def clear_form(driver: Any, form_selector: str) -> Dict[str, Any]:
    """Reset all fields in the target form."""
    form_el, meta = _find_element(driver, form_selector)
    if not form_el:
        return {"success": False, "msg": "Form not found", **meta}
    try:
        _execute_js(driver, "arguments[0].reset();", form_el)
        return {"success": True, "msg": "Form cleared", **meta}
    except Exception as exc:  # pragma: no cover
        return {"success": False, "msg": str(exc), **meta}


def save_form_state(driver: Any, form_selector: str) -> Dict[str, Any]:
    """
    Serialize current form values into a dict.
    Useful for later restoration.
    """
    form_el, meta = _find_element(driver, form_selector)
    if not form_el:
        return {"success": False, "msg": "Form not found", **meta}
    state: Dict[str, Any] = {}
    try:
        inputs = form_el.find_elements("css selector", "input, textarea, select")
        for el in inputs:
            name = el.get_attribute("name") or el.get_attribute("id")
            if not name:
                continue
            typ = el.get_attribute("type") if _is_selenium(driver) else el.get_attribute("type")
            if typ in ("checkbox", "radio"):
                checked = el.is_selected() if _is_selenium(driver) else el.is_checked()
                state[name] = checked
            elif typ == "select-multiple":
                # Playwright & Selenium expose selected options differently;
                # use JS to read the values array.
                vals = _execute_js(
                    driver,
                    "return Array.from(arguments[0].selectedOptions).map(o=>o.value);",
                    el,
                )
                state[name] = vals
            else:
                state[name] = el.get_attribute("value")
        return {"success": True, "state": state, **meta}
    except Exception as exc:  # pragma: no cover
        return {"success": False, "msg": str(exc), **meta}


def restore_form_state(driver: Any, form_selector: str, state: Mapping[str, Any]) -> Dict[str, Any]:
    """Write previously saved ``state`` back into the form."""
    form_el, meta = _find_element(driver, form_selector)
    if not form_el:
        return {"success": False, "msg": "Form not found", **meta}
    try:
        for name, value in state.items():
            selector = f"[name='{name}'], #{name}"
            if isinstance(value, bool):
                fill_checkbox(driver, selector, value)
            elif isinstance(value, list):
                fill_multi_select(driver, selector, value)
            else:
                fill_text_field(driver, selector, str(value))
        return {"success": True, "msg": "State restored", **meta}
    except Exception as exc:  # pragma: no cover
        return {"success": False, "msg": str(exc), **meta}


def handle_dynamic_form(
    driver: Any,
    form_selector: str,
    steps: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """
    Process a set of scripted steps for forms that reveal new fields
    after interactions (e.g. clicking “Add another”).
    Each step dict may contain:
        - action: "click" | "fill" | "wait"
        - selector: CSS selector
        - value: payload for fill actions
        - timeout: optional wait time
    """
    result: Dict[str, Any] = {"executed": 0, "errors": []}
    for i, step in enumerate(steps, 1):
        action = step.get("action")
        selector = step.get("selector")
        value = step.get("value")
        timeout = step.get("timeout", 0.5)
        try:
            if action == "click":
                el, _ = _find_element(driver, selector)
                if el:
                    el.click()
                else:
                    raise RuntimeError(f"Step {i}: element not found")
            elif action == "fill":
                # Very naive – attempt generic text fill
                fill_text_field(driver, selector, str(value))
            elif action == "wait":
                time.sleep(float(value))
            else:
                raise ValueError(f"Step {i}: unknown action '{action}'")
            time.sleep(timeout)
            result["executed"] += 1
        except Exception as exc:
            result["errors"].append({"step": i, "error": str(exc)})
    return {"success": len(result["errors"]) == 0, **result}


def batch_fill_forms(
    driver: Any,
    forms_config: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """
    ``forms_config`` is a list where each entry contains:
        - form_selector: CSS selector for the form
        - data: Mapping of field → value **or** a path to a JSON file
        - optional ``use_fake``: bool – generate fake data based on detected fields
    Returns aggregated result.
    """
    summary = {"filled": 0, "failed": 0, "details": []}
    for cfg in forms_config:
        selector = cfg["form_selector"]
        data = cfg.get("data")
        use_fake = cfg.get("use_fake", False)

        if isinstance(data, str) and Path(data).is_file():
            try:
                data = json.loads(Path(data).read_text())
            except Exception as exc:
                summary["failed"] += 1
                summary["details"].append(
                    {"form": selector, "msg": f"Invalid JSON file: {exc}"}
                )
                continue

        if use_fake:
            # Detect fields & generate fake payload
            fields = detect_form_fields(driver.page_source if _is_selenium(driver) else driver.content())
            data = generate_fake_data(fields.get("fields", {}))

        fill_res = auto_fill_form(driver, selector, data or {})
        if fill_res.get("success"):
            summary["filled"] += 1
        else:
            summary["failed"] += 1
        summary["details"].append({"form": selector, "result": fill_res})
    return {"summary": summary}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
__all__ = [
    "detect_form_fields",
    "fill_text_field",
    "fill_select_dropdown",
    "fill_checkbox",
    "fill_radio_button",
    "fill_textarea",
    "fill_date_field",
    "fill_file_upload",
    "fill_hidden_field",
    "fill_range_slider",
    "fill_multi_select",
    "fill_color_picker",
    "fill_autocomplete",
    "fill_captcha_field",
    "auto_fill_form",
    "fill_form_from_json",
    "generate_fake_data",
    "smart_field_detection",
    "submit_form",
    "validate_form_filled",
    "clear_form",
    "save_form_state",
    "restore_form_state",
    "handle_dynamic_form",
    "batch_fill_forms",
]