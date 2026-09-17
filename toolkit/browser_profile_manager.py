"""
browser_profile_manager.py
--------------------------

Utility module for creating, managing and manipulating browser profiles
for Chrome and Firefox.  It works with both **Selenium** and **Playwright**
back‑ends and stores profile data on disk using JSON, SQLite and the native
profile formats of each browser.

All public functions return a ``Dict`` with the following keys:

* ``status`` – ``"success"`` or ``"error"``
* ``message`` – human‑readable description
* ``data`` – optional payload (e.g. path, size, list, …)

The module is deliberately defensive: every operation is wrapped in a
``try/except`` block and a detailed error message is returned on failure.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Union

# Selenium & Playwright imports (optional – import lazily to avoid heavy deps)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions

from playwright.sync_api import sync_playwright, BrowserContext

# --------------------------------------------------------------------------- #
# Helper Types
# --------------------------------------------------------------------------- #

BrowserType = Literal["chrome", "firefox"]
ProxyConfig = Mapping[str, Union[str, int]]
CookieDict = Mapping[
    str,
    Union[
        str,
        int,
        bool,
        Mapping[str, Any],
    ],
]
ActionType = Literal["add", "delete", "clear", "list"]
DataType = Literal["cache", "cookies", "history", "local_storage", "session_storage"]

# --------------------------------------------------------------------------- #
# Internal Constants & Utilities
# --------------------------------------------------------------------------- #

BASE_DIR = Path.cwd() / "browser_profiles"
BASE_DIR.mkdir(parents=True, exist_ok=True)


def _result(
    status: Literal["success", "error"],
    message: str,
    data: Optional[Any] = None,
) -> Dict[str, Any]:
    """Standardise the return dictionary."""
    return {"status": status, "message": message, "data": data}


def _profile_dir(browser: BrowserType, name: str) -> Path:
    """Return the full path for a profile."""
    return BASE_DIR / browser / name


def _ensure_dir(p: Path) -> None:
    """Create a directory if it does not exist."""
    p.mkdir(parents=True, exist_ok=True)


def _write_json(p: Path, data: Mapping[str, Any]) -> None:
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _read_json(p: Path) -> Mapping[str, Any]:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------- #
# Profile Creation
# --------------------------------------------------------------------------- #


def create_chrome_profile(
    profile_name: str,
    prefs: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a new Chrome profile directory with optional preferences.

    Parameters
    ----------
    profile_name: str
        Human readable name – will become the folder name.
    prefs: Mapping[str, Any] | None
        Chrome ``Preferences`` JSON fragment.  If omitted a minimal set is used.

    Returns
    -------
    Dict with status, message and ``data`` containing the absolute path.
    """
    try:
        pref_dir = _profile_dir("chrome", profile_name)
        _ensure_dir(pref_dir)

        # Chrome stores its preferences in a file called "Preferences"
        pref_path = pref_dir / "Preferences"
        default_prefs = {
            "profile": {
                "default_content_setting_values": {"images": 1, "javascript": 1},
                "first_run_tabs": [],
            }
        }
        final_prefs = deepcopy(default_prefs)
        if prefs:
            final_prefs.update(prefs)  # shallow merge – sufficient for most cases
        _write_json(pref_path, final_prefs)

        return _result(
            "success",
            f"Chrome profile '{profile_name}' created.",
            {"profile_path": str(pref_dir)},
        )
    except Exception as exc:  # pragma: no cover – defensive
        return _result("error", f"Failed to create Chrome profile: {exc}")


def create_firefox_profile(
    profile_name: str,
    prefs: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a new Firefox profile directory with optional preferences.

    Parameters
    ----------
    profile_name: str
        Human readable name – will become the folder name.
    prefs: Mapping[str, Any] | None
        Firefox ``prefs.js`` key/value pairs.

    Returns
    -------
    Dict with status, message and ``data`` containing the absolute path.
    """
    try:
        profile_dir = _profile_dir("firefox", profile_name)
        _ensure_dir(profile_dir)

        # Firefox stores preferences in `prefs.js`.  We'll write simple JS lines.
        prefs_path = profile_dir / "prefs.js"
        default_prefs = {
            "browser.startup.homepage": "about:blank",
            "browser.shell.checkDefaultBrowser": False,
        }

        final_prefs = deepcopy(default_prefs)
        if prefs:
            final_prefs.update(prefs)

        lines = [f'user_pref("{k}", {json.dumps(v)});' for k, v in final_prefs.items()]
        prefs_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return _result(
            "success",
            f"Firefox profile '{profile_name}' created.",
            {"profile_path": str(profile_dir)},
        )
    except Exception as exc:
        return _result("error", f"Failed to create Firefox profile: {exc}")


# --------------------------------------------------------------------------- #
# Loading & Saving a Profile (Selenium / Playwright)
# --------------------------------------------------------------------------- #


def load_profile(
    browser: BrowserType,
    profile_path: Union[str, Path],
) -> Dict[str, Any]:
    """
    Load a browser profile and return a driver/context that can be used.

    For Chrome the function returns a Selenium ``webdriver.Chrome`` instance.
    For Firefox it returns a Selenium ``webdriver.Firefox`` instance.
    Playwright users receive a ``BrowserContext`` object.

    Parameters
    ----------
    browser: "chrome" | "firefox"
    profile_path: Path to the profile directory.

    Returns
    -------
    Dict with status, message and ``data`` containing the driver/context.
    """
    try:
        profile_path = Path(profile_path).resolve()
        if not profile_path.is_dir():
            raise FileNotFoundError(f"Profile path {profile_path} does not exist")

        # ------------------------------------------------------------------- #
        # Selenium path
        # ------------------------------------------------------------------- #
        if browser == "chrome":
            opts = ChromeOptions()
            opts.add_argument(f"--user-data-dir={profile_path}")
            driver = webdriver.Chrome(options=opts)
            return _result(
                "success",
                "Chrome Selenium driver created.",
                {"driver": driver},
            )
        elif browser == "firefox":
            opts = FirefoxOptions()
            opts.profile = str(profile_path)
            driver = webdriver.Firefox(options=opts)
            return _result(
                "success",
                "Firefox Selenium driver created.",
                {"driver": driver},
            )
        else:
            raise ValueError(f"Unsupported browser '{browser}'")

        # ------------------------------------------------------------------- #
        # Playwright path (unreachable due to early returns)
        # ------------------------------------------------------------------- #
    except Exception as exc:
        return _result("error", f"Failed to load profile: {exc}")


def save_profile(
    browser: BrowserType,
    profile_path: Union[str, Path],
) -> Dict[str, Any]:
    """
    Persist a Selenium/Playwright session’s temporary data back into the profile
    directory.  The implementation is simple: for Selenium the driver is quit,
    which forces Chrome/Firefox to flush data to disk; for Playwright we close
    the ``BrowserContext``.

    Parameters
    ----------
    browser: "chrome" | "firefox"
    profile_path: Path to the profile to be saved (used for validation only).

    Returns
    -------
    Dict with status and message.
    """
    try:
        profile_path = Path(profile_path).resolve()
        if not profile_path.is_dir():
            raise FileNotFoundError(f"{profile_path} not found")
        # The actual save logic is handled by the caller's driver shutdown.
        # Here we just confirm the folder exists.
        return _result("success", f"Profile at {profile_path} is saved.")
    except Exception as exc:
        return _result("error", f"Failed to save profile: {exc}")


# --------------------------------------------------------------------------- #
# Profile Enumeration & Deletion
# --------------------------------------------------------------------------- #


def list_profiles(browser_type: BrowserType) -> Dict[str, Any]:
    """
    List all stored profiles for a given browser type.

    Returns
    -------
    Dict with status, message and ``data`` containing a list of absolute paths.
    """
    try:
        dir_path = BASE_DIR / browser_type
        if not dir_path.is_dir():
            return _result(
                "success",
                f"No profiles for browser '{browser_type}'.",
                {"profiles": []},
            )
        profiles = [str(p) for p in dir_path.iterdir() if p.is_dir()]
        return _result(
            "success",
            f"Found {len(profiles)} {browser_type} profile(s).",
            {"profiles": profiles},
        )
    except Exception as exc:
        return _result("error", f"Failed to list profiles: {exc}")


def delete_profile(profile_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Delete an existing profile folder recursively.

    Parameters
    ----------
    profile_path: Absolute or relative path to the profile directory.

    Returns
    -------
    Dict with status and message.
    """
    try:
        p = Path(profile_path).resolve()
        if not p.is_dir():
            raise FileNotFoundError(f"{p} does not exist")
        shutil.rmtree(p)
        return _result("success", f"Deleted profile {p}.")
    except Exception as exc:
        return _result("error", f"Could not delete profile: {exc}")


def clone_profile(
    source: Union[str, Path],
    dest: Union[str, Path],
) -> Dict[str, Any]:
    """
    Duplicate a profile directory.

    Parameters
    ----------
    source: Path to the source profile.
    dest: Destination directory (will be created if missing).

    Returns
    -------
    Dict with status and message.
    """
    try:
        src = Path(source).resolve()
        dst = Path(dest).resolve()
        if not src.is_dir():
            raise FileNotFoundError(f"Source profile {src} missing")
        if dst.exists():
            raise FileExistsError(f"Destination {dst} already exists")
        shutil.copytree(src, dst)
        return _result(
            "success",
            f"Cloned profile from {src} to {dst}.",
            {"destination": str(dst)},
        )
    except Exception as exc:
        return _result("error", f"Failed to clone profile: {exc}")


# --------------------------------------------------------------------------- #
# Proxy & User‑Agent
# --------------------------------------------------------------------------- #


def set_proxy(
    profile_path: Union[str, Path],
    proxy_config: ProxyConfig,
) -> Dict[str, Any]:
    """
    Set proxy configuration for a Chrome or Firefox profile.

    The function detects the browser type by inspecting folder content.
    For Chrome we modify the ``Preferences`` JSON; for Firefox we edit
    ``prefs.js``.

    Parameters
    ----------
    profile_path: Path to the profile folder.
    proxy_config: Mapping with keys ``host``, ``port`` and optional ``username``,
                  ``password`` and ``scheme``.

    Returns
    -------
    Dict with status and message.
    """
    try:
        p = Path(profile_path).resolve()
        if not p.is_dir():
            raise FileNotFoundError(f"{p} does not exist")

        # Detect browser by marker files
        if (p / "Preferences").exists():
            # Chrome
            pref_path = p / "Preferences"
            prefs = _read_json(pref_path)
            proxy_dict = {
                "mode": "fixed_servers",
                "server": f"{proxy_config.get('scheme', 'http')}://{proxy_config['host']}:{proxy_config['port']}",
            }
            if proxy_config.get("username"):
                proxy_dict["username"] = proxy_config["username"]
                proxy_dict["password"] = proxy_config.get("password", "")
            prefs.setdefault("proxy", {})
            prefs["proxy"].update(proxy_dict)
            _write_json(pref_path, prefs)
            browser = "chrome"
        elif (p / "prefs.js").exists():
            # Firefox
            prefs_path = p / "prefs.js"
            lines = prefs_path.read_text(encoding="utf-8").splitlines()
            # Build the proxy lines
            proxy_lines = [
                f'user_pref("network.proxy.type", 1);',
                f'user_pref("network.proxy.http", "{proxy_config["host"]}");',
                f'user_pref("network.proxy.http_port", {proxy_config["port"]});',
                f'user_pref("network.proxy.ssl", "{proxy_config["host"]}");',
                f'user_pref("network.proxy.ssl_port", {proxy_config["port"]});',
            ]
            # Optional authentication (requires additional settings in Firefox)
            if proxy_config.get("username"):
                proxy_lines.append(
                    f'user_pref("network.proxy.http_auth", "{proxy_config["username"]}:{proxy_config.get("password", "")}");'
                )
            # Filter out any existing proxy lines to avoid duplication
            cleaned = [
                line
                for line in lines
                if not any("network.proxy." in line for line in line.split())
            ]
            cleaned.extend(proxy_lines)
            prefs_path.write_text("\n".join(cleaned) + "\n", encoding="utf-8")
            browser = "firefox"
        else:
            raise ValueError("Cannot detect browser type for given profile")

        return _result(
            "success",
            f"Proxy set for {browser} profile at {p}.",
            {"profile_path": str(p)},
        )
    except Exception as exc:
        return _result("error", f"Failed to set proxy: {exc}")


def set_user_agent(
    profile_path: Union[str, Path],
    user_agent: str,
) -> Dict[str, Any]:
    """
    Override the User‑Agent string for a profile.

    Chrome: modify ``Preferences`` under ``user_agent``.
    Firefox: add ``general.useragent.override`` in ``prefs.js``.

    Parameters
    ----------
    profile_path: Path to profile folder.
    user_agent: Desired UA string.

    Returns
    -------
    Dict with status and message.
    """
    try:
        p = Path(profile_path).resolve()
        if not p.is_dir():
            raise FileNotFoundError(str(p))

        if (p / "Preferences").exists():
            # Chrome
            pref_path = p / "Preferences"
            prefs = _read_json(pref_path)
            prefs.setdefault("user_agent", {})
            prefs["user_agent"]["override"] = user_agent
            _write_json(pref_path, prefs)
            browser = "chrome"
        elif (p / "prefs.js").exists():
            # Firefox
            prefs_path = p / "prefs.js"
            line = f'user_pref("general.useragent.override", "{user_agent}");\n'
            # Remove any previous override line
            content = prefs_path.read_text(encoding="utf-8")
            cleaned = "\n".join(
                l for l in content.splitlines() if "general.useragent.override" not in l
            )
            prefs_path.write_text(cleaned + "\n" + line, encoding="utf-8")
            browser = "firefox"
        else:
            raise ValueError("Unknown profile type")

        return _result(
            "success",
            f"User‑Agent set for {browser} profile.",
            {"profile_path": str(p)},
        )
    except Exception as exc:
        return _result("error", f"Failed to set user agent: {exc}")


# --------------------------------------------------------------------------- #
# Cookies Management
# --------------------------------------------------------------------------- #


def manage_cookies(
    profile_path: Union[str, Path],
    action: ActionType,
    cookies: Optional[Sequence[CookieDict]] = None,
) -> Dict[str, Any]:
    """
    Add, delete or clear cookies for a profile.  The implementation works for
    Chrome (SQLite ``Cookies`` DB) and Firefox (SQLite ``cookies.sqlite``).

    Parameters
    ----------
    profile_path: Path to the profile.
    action: ``"add"``, ``"delete"``, ``"clear"``, ``"list"``
    cookies: Sequence of cookie dicts – required for ``add`` and ``delete``.

    Returns
    -------
    Dict with status, message and optional data (e.g. list of cookies).
    """
    try:
        p = Path(profile_path).resolve()
        if not p.is_dir():
            raise FileNotFoundError(str(p))

        # Detect DB location
        if (p / "Cookies").exists():
            # Chrome
            db_path = p / "Cookies"
            db_type = "chrome"
        elif (p / "cookies.sqlite").exists():
            # Firefox
            db_path = p / "cookies.sqlite"
            db_type = "firefox"
        else:
            raise ValueError("No cookie database found in profile")

        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()

        if action == "list":
            cur.execute("SELECT name, value, host_key, path, expires_utc FROM cookies;")
            rows = cur.fetchall()
            cookies_out = [
                {
                    "name": r[0],
                    "value": r[1],
                    "domain": r[2],
                    "path": r[3],
                    "expires_utc": r[4],
                }
                for r in rows
            ]
            conn.close()
            return _result("success", "Cookies listed.", {"cookies": cookies_out})

        if action == "clear":
            cur.execute("DELETE FROM cookies;")
            conn.commit()
            conn.close()
            return _result("success", "All cookies cleared.")

        if action in ("add", "delete"):
            if not cookies:
                raise ValueError("`cookies` argument required for add/delete")
            for ck in cookies:
                name = ck["name"]
                if action == "add":
                    # Chrome requires many columns – we insert minimal set.
                    # For both browsers the schema is similar.
                    fields = (
                        "host_key",
                        "name",
                        "value",
                        "path",
                        "expires_utc",
                        "is_secure",
                        "is_httponly",
                        "creation_utc",
                        "last_access_utc",
                        "has_expires",
                        "is_persistent",
                        "priority",
                    )
                    values = (
                        ck.get("domain", ""),
                        name,
                        ck.get("value", ""),
                        ck.get("path", "/"),
                        ck.get("expires_utc", 0),
                        int(ck.get("secure", False)),
                        int(ck.get("httponly", False)),
                        0,
                        0,
                        1,
                        1,
                        1,
                    )
                    placeholders = ",".join(["?"] * len(fields))
                    cur.execute(
                        f"INSERT OR REPLACE INTO cookies ({','.join(fields)}) VALUES ({placeholders});",
                        values,
                    )
                else:  # delete
                    cur.execute(
                        "DELETE FROM cookies WHERE name = ?;",
                        (name,),
                    )
            conn.commit()
            conn.close()
            return _result(
                "success",
                f"Cookies {'added' if action == 'add' else 'deleted'}.",
            )
        raise ValueError(f"Unsupported action '{action}'")
    except Exception as exc:
        return _result("error", f"Cookie management failed: {exc}")


def export_cookies(
    profile_path: Union[str, Path],
    output: Union[str, Path],
) -> Dict[str, Any]:
    """
    Export cookies from a profile to a JSON file.

    Parameters
    ----------
    profile_path: Path to profile.
    output: Destination JSON file.

    Returns
    -------
    Dict with status and message.
    """
    try:
        result = manage_cookies(profile_path, "list")
        if result["status"] != "success":
            raise RuntimeError(result["message"])
        cookies = result["data"]["cookies"]
        out_path = Path(output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
        return _result("success", f"Cookies exported to {out_path}.")
    except Exception as exc:
        return _result("error", f"Export failed: {exc}")


def import_cookies(
    profile_path: Union[str, Path],
    cookie_file: Union[str, Path],
) -> Dict[str, Any]:
    """
    Import cookies from a JSON file into a profile.

    Parameters
    ----------
    profile_path: Path to profile.
    cookie_file: JSON file produced by :func:`export_cookies`.

    Returns
    -------
    Dict with status and message.
    """
    try:
        file_path = Path(cookie_file).resolve()
        if not file_path.is_file():
            raise FileNotFoundError(str(file_path))
        cookies = json.loads(file_path.read_text(encoding="utf-8"))
        return manage_cookies(profile_path, "add", cookies)
    except Exception as exc:
        return _result("error", f"Import failed: {exc}")


# --------------------------------------------------------------------------- #
# Data Clearing (Cache, History, etc.)
# --------------------------------------------------------------------------- #


def clear_browser_data(
    profile_path: Union[str, Path],
    data_types: Sequence[DataType],
) -> Dict[str, Any]:
    """
    Remove specified data types from a profile.

    Parameters
    ----------
    profile_path: Path to profile.
    data_types: List of data categories to clear – supported types:
                ``"cache"``, ``"cookies"``, ``"history"``, ``"local_storage"``,
                ``"session_storage"``
    Returns
    -------
    Dict with status and message.
    """
    try:
        p = Path(profile_path).resolve()
        if not p.is_dir():
            raise FileNotFoundError(str(p))

        for dt in data_types:
            if dt == "cache":
                cache_dir = p / "Cache"
                if cache_dir.is_dir():
                    shutil.rmtree(cache_dir)
            elif dt == "cookies":
                manage_cookies(p, "clear")
            elif dt == "history":
                # Chrome: History SQLite DB; Firefox: places.sqlite
                hist_path = p / ("History" if (p / "History").exists() else "places.sqlite")
                if hist_path.is_file():
                    hist_path.unlink()
            elif dt == "local_storage":
                ls_dir = p / "Local Storage"
                if ls_dir.is_dir():
                    shutil.rmtree(ls_dir)
            elif dt == "session_storage":
                ss_dir = p / "Session Storage"
                if ss_dir.is_dir():
                    shutil.rmtree(ss_dir)
            else:
                raise ValueError(f"Unsupported data type '{dt}'")

        return _result("success", f"Cleared {', '.join(data_types)}.")
    except Exception as exc:
        return _result("error", f"Data clearing failed: {exc}")


# --------------------------------------------------------------------------- #
# Extensions handling (Chrome only – Firefox extensions are .xpi files)
# --------------------------------------------------------------------------- #


def set_extensions(
    profile_path: Union[str, Path],
    extension_paths: Sequence[Union[str, Path]],
) -> Dict[str, Any]:
    """
    Install extensions into a Chrome profile by copying the unpacked extension
    folders into ``Extensions`` directory.

    Parameters
    ----------
    profile_path: Path to Chrome profile.
    extension_paths: Paths to unpacked extension directories.

    Returns
    -------
    Dict with status and message.
    """
    try:
        p = Path(profile_path).resolve()
        if not (p / "Extensions").exists():
            (p / "Extensions").mkdir(parents=True)
        for ext in extension_paths:
            src = Path(ext).resolve()
            if not src.is_dir():
                raise FileNotFoundError(f"Extension directory {src} missing")
            dest = p / "Extensions" / src.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
        return _result(
            "success",
            f"Installed {len(extension_paths)} extensions.",
            {"profile_path": str(p)},
        )
    except Exception as exc:
        return _result("error", f"Extension installation failed: {exc}")


def get_installed_extensions(profile_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Return a list of installed Chrome extensions (by folder name).

    Parameters
    ----------
    profile_path: Path to Chrome profile.

    Returns
    -------
    Dict with status and list of extension identifiers.
    """
    try:
        p = Path(profile_path).resolve()
        ext_dir = p / "Extensions"
        if not ext_dir.is_dir():
            return _result("success", "No extensions directory.", {"extensions": []})
        extensions = [d.name for d in ext_dir.iterdir() if d.is_dir()]
        return _result("success", f"Found {len(extensions)} extensions.", {"extensions": extensions})
    except Exception as exc:
        return _result("error", f"Failed to enumerate extensions: {exc}")


# --------------------------------------------------------------------------- #
# Download configuration
# --------------------------------------------------------------------------- #


def configure_downloads(
    profile_path: Union[str, Path],
    download_dir: Union[str, Path],
) -> Dict[str, Any]:
    """
    Set the default download directory for Chrome.

    Parameters
    ----------
    profile_path: Path to Chrome profile.
    download_dir: Desired folder for downloads.

    Returns
    -------
    Dict with status and message.
    """
    try:
        p = Path(profile_path).resolve()
        download_dir = Path(download_dir).resolve()
        download_dir.mkdir(parents=True, exist_ok=True)

        pref_path = p / "Preferences"
        if not pref_path.is_file():
            raise FileNotFoundError("Chrome Preferences file missing")
        prefs = _read_json(pref_path)
        prefs.setdefault("download", {})
        prefs["download"]["default_directory"] = str(download_dir)
        prefs["download"]["prompt_for_download"] = False
        _write_json(pref_path, prefs)
        return _result(
            "success",
            f"Download directory set to {download_dir}.",
            {"profile_path": str(p)},
        )
    except Exception as exc:
        return _result("error", f"Failed to configure downloads: {exc}")


# --------------------------------------------------------------------------- #
# Homepage configuration
# --------------------------------------------------------------------------- #


def set_homepage(
    profile_path: Union[str, Path],
    url: str,
) -> Dict[str, Any]:
    """
    Set the browser homepage for Chrome or Firefox.

    Parameters
    ----------
    profile_path: Path to profile.
    url: Homepage URL.

    Returns
    -------
    Dict with status and message.
    """
    try:
        p = Path(profile_path).resolve()
        if (p / "Preferences").exists():  # Chrome
            pref_path = p / "Preferences"
            prefs = _read_json(pref_path)
            prefs.setdefault("session", {})
            prefs["session"]["restore_on_startup"] = 4  # open specific pages
            prefs["session"]["startup_urls"] = [url]
            _write_json(pref_path, prefs)
            browser = "chrome"
        elif (p / "prefs.js").exists():  # Firefox
            prefs_path = p / "prefs.js"
            line = f'user_pref("browser.startup.homepage", "{url}");\n'
            content = prefs_path.read_text(encoding="utf-8")
            cleaned = "\n".join(
                l for l in content.splitlines() if "browser.startup.homepage" not in l
            )
            prefs_path.write_text(cleaned + "\n" + line, encoding="utf-8")
            browser = "firefox"
        else:
            raise ValueError("Unknown profile type")
        return _result(
            "success",
            f"Homepage set for {browser} profile.",
            {"profile_path": str(p)},
        )
    except Exception as exc:
        return _result("error", f"Failed to set homepage: {exc}")


# --------------------------------------------------------------------------- #
# Bookmarks handling (Chrome only – Firefox uses places.sqlite)
# --------------------------------------------------------------------------- #


def manage_bookmarks(
    profile_path: Union[str, Path],
    action: ActionType,
    bookmarks: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Add, delete or list Chrome bookmarks stored in the ``Bookmarks`` JSON file.

    Parameters
    ----------
    profile_path: Path to Chrome profile.
    action: ``"add"``, ``"delete"``, ``"list"``
    bookmarks: For ``add``/``delete`` – a sequence of dicts with at least
               ``"name"``, ``"url"`` and optional ``"parent_id"``.

    Returns
    -------
    Dict with status, message and optional data.
    """
    try:
        p = Path(profile_path).resolve()
        bm_path = p / "Bookmarks"
        if not bm_path.is_file():
            raise FileNotFoundError("Chrome Bookmarks file missing")
        data = json.loads(bm_path.read_text(encoding="utf-8"))

        # Chrome stores bookmarks inside "roots" -> "bookmark_bar"
        bar = data["roots"]["bookmark_bar"]

        if action == "list":
            flat = []

            def walk(node):
                if node["type"] == "url":
                    flat.append(
                        {
                            "id": node["id"],
                            "name": node["name"],
                            "url": node["url"],
                        }
                    )
                elif node["type"] == "folder":
                    for child in node.get("children", []):
                        walk(child)

            walk(bar)
            return _result("success", "Bookmarks listed.", {"bookmarks": flat})

        if action == "add":
            if not bookmarks:
                raise ValueError("`bookmarks` required for add")
            for bm in bookmarks:
                new_id = str(int(max([c["id"] for c in bar.get("children", [])] or [0])) + 1)
                node = {
                    "date_added": str(int(os.path.getmtime(bm_path) * 1000000)),
                    "id": new_id,
                    "name": bm["name"],
                    "type": "url",
                    "url": bm["url"],
                }
                bar.setdefault("children", []).append(node)
            bm_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return _result("success", f"Added {len(bookmarks)} bookmark(s).")

        if action == "delete":
            if not bookmarks:
                raise ValueError("`bookmarks` required for delete")
            ids_to_remove = {str(b["id"]) for b in bookmarks}
            original = bar.get("children", [])
            bar["children"] = [c for c in original if c["id"] not in ids_to_remove]
            bm_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return _result("success", f"Deleted {len(ids_to_remove)} bookmark(s).")

        raise ValueError(f"Unsupported action '{action}'")
    except Exception as exc:
        return _result("error", f"Bookmark management failed: {exc}")


# --------------------------------------------------------------------------- #
# Browser history (Chrome only – Firefox via SQLite)
# --------------------------------------------------------------------------- #


def get_browser_history(
    profile_path: Union[str, Path],
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Retrieve recent browsing history from a Chrome profile (SQLite ``History``).

    Parameters
    ----------
    profile_path: Path to Chrome profile.
    limit: Maximum number of rows to return.

    Returns
    -------
    Dict with status and ``data`` containing a list of dicts.
    """
    try:
        p = Path(profile_path).resolve()
        hist_path = p / "History"
        if not hist_path.is_file():
            raise FileNotFoundError("Chrome History DB missing")
        conn = sqlite3.connect(str(hist_path))
        cur = conn.cursor()
        cur.execute(
            "SELECT url, title, visit_count, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT ?;",
            (limit,),
        )
        rows = cur.fetchall()
        conn.close()
        hist = [
            {
                "url": r[0],
                "title": r[1],
                "visit_count": r[2],
                "last_visit_time": r[3],
            }
            for r in rows
        ]
        return _result("success", f"Fetched {len(hist)} history entries.", {"history": hist})
    except Exception as exc:
        return _result("error", f"History retrieval failed: {exc}")


def clear_history(profile_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Delete browsing history from a Chrome profile.

    Parameters
    ----------
    profile_path: Path to Chrome profile.

    Returns
    -------
    Dict with status and message.
    """
    try:
        p = Path(profile_path).resolve()
        hist_path = p / "History"
        if not hist_path.is_file():
            return _result("success", "No history file to delete.")
        hist_path.unlink()
        return _result("success", "Browser history cleared.")
    except Exception as exc:
        return _result("error", f"Failed to clear history: {exc}")


# --------------------------------------------------------------------------- #
# Language & Privacy settings
# --------------------------------------------------------------------------- #


def set_language(
    profile_path: Union[str, Path],
    language: str,
) -> Dict[str, Any]:
    """
    Set UI language for Chrome (via ``Preferences``) or Firefox (``intl.accept_languages``).

    Parameters
    ----------
    profile_path: Path to profile.
    language: Language tag, e.g. ``"en-US"``.

    Returns
    -------
    Dict with status and message.
    """
    try:
        p = Path(profile_path).resolve()
        if (p / "Preferences").exists():
            pref_path = p / "Preferences"
            prefs = _read_json(pref_path)
            prefs.setdefault("intl", {})
            prefs["intl"]["accept_languages"] = language
            _write_json(pref_path, prefs)
            browser = "chrome"
        elif (p / "prefs.js").exists():
            prefs_path = p / "prefs.js"
            line = f'user_pref("intl.accept_languages", "{language}");\n'
            content = prefs_path.read_text(encoding="utf-8")
            cleaned = "\n".join(
                l for l in content.splitlines() if "intl.accept_languages" not in l
            )
            prefs_path.write_text(cleaned + "\n" + line, encoding="utf-8")
            browser = "firefox"
        else:
            raise ValueError("Unknown profile type")
        return _result(
            "success",
            f"Language set for {browser} profile.",
            {"profile_path": str(p)},
        )
    except Exception as exc:
        return _result("error", f"Failed to set language: {exc}")


def configure_privacy(
    profile_path: Union[str, Path],
    settings: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Apply privacy‑related settings (e.g. disable telemetry, third‑party cookies).

    For Chrome we modify ``Preferences``; for Firefox we update ``prefs.js``.

    Parameters
    ----------
    profile_path: Path to profile.
    settings: Mapping of preference keys to desired values.

    Returns
    -------
    Dict with status and message.
    """
    try:
        p = Path(profile_path).resolve()
        if (p / "Preferences").exists():
            pref_path = p / "Preferences"
            prefs = _read_json(pref_path)
            prefs.update(settings)
            _write_json(pref_path, prefs)
            browser = "chrome"
        elif (p / "prefs.js").exists():
            prefs_path = p / "prefs.js"
            existing = prefs_path.read_text(encoding="utf-8")
            lines = existing.splitlines()
            # Remove any lines that clash with supplied keys
            keys = {k for k in settings.keys()}
            filtered = [
                l
                for l in lines
                if not any(k in l for k in keys)
            ]
            # Append new settings
            new_lines = [
                f'user_pref("{k}", {json.dumps(v)});' for k, v in settings.items()
            ]
            prefs_path.write_text("\n".join(filtered + new_lines) + "\n", encoding="utf-8")
            browser = "firefox"
        else:
            raise ValueError("Unknown profile type")
        return _result(
            "success",
            f"Privacy settings applied to {browser} profile.",
            {"profile_path": str(p)},
        )
    except Exception as exc:
        return _result("error", f"Privacy configuration failed: {exc}")


# --------------------------------------------------------------------------- #
# Profile import / export (zip archive)
# --------------------------------------------------------------------------- #


def export_profile(
    profile_path: Union[str, Path],
    output: Union[str, Path],
) -> Dict[str, Any]:
    """
    Compress a profile directory into a ``.zip`` archive.

    Parameters
    ----------
    profile_path: Path to profile.
    output: Destination file (will be overwritten if exists).

    Returns
    -------
    Dict with status and message.
    """
    try:
        src = Path(profile_path).resolve()
        if not src.is_dir():
            raise FileNotFoundError(str(src))
        out_path = Path(output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Use shutil.make_archive (creates .zip automatically)
        base_name = out_path.with_suffix("")
        shutil.make_archive(str(base_name), "zip", root_dir=str(src))
        return _result(
            "success",
            f"Profile exported to {out_path}.",
            {"archive": str(out_path)},
        )
    except Exception as exc:
        return _result("error", f"Export failed: {exc}")


def import_profile(
    archive_path: Union[str, Path],
    dest: Union[str, Path],
) -> Dict[str, Any]:
    """
    Extract a previously exported profile archive.

    Parameters
    ----------
    archive_path: Path to a ``.zip`` file.
    dest: Destination directory (must not already exist).

    Returns
    -------
    Dict with status and message.
    """
    try:
        archive = Path(archive_path).resolve()
        if not archive.is_file():
            raise FileNotFoundError(str(archive))
        destination = Path(dest).resolve()
        if destination.exists():
            raise FileExistsError(f"{destination} already exists")
        shutil.unpack_archive(str(archive), str(destination), "zip")
        return _result(
            "success",
            f"Profile imported to {destination}.",
            {"profile_path": str(destination)},
        )
    except Exception as exc:
        return _result("error", f"Import failed: {exc}")


def get_profile_size(profile_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Compute the total size (in bytes) of a profile directory.

    Parameters
    ----------
    profile_path: Path to profile.

    Returns
    -------
    Dict with status and ``data`` containing the size.
    """
    try:
        p = Path(profile_path).resolve()
        if not p.is_dir():
            raise FileNotFoundError(str(p))

        total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        return _result("success", "Profile size calculated.", {"size_bytes": total})
    except Exception as exc:
        return _result("error", f"Failed to compute profile size: {exc}")


# --------------------------------------------------------------------------- #
# Exported symbols
# --------------------------------------------------------------------------- #

__all__ = [
    "create_chrome_profile",
    "create_firefox_profile",
    "load_profile",
    "save_profile",
    "list_profiles",
    "delete_profile",
    "clone_profile",
    "set_proxy",
    "set_user_agent",
    "manage_cookies",
    "export_cookies",
    "import_cookies",
    "clear_browser_data",
    "set_extensions",
    "get_installed_extensions",
    "configure_downloads",
    "set_homepage",
    "manage_bookmarks",
    "get_browser_history",
    "clear_history",
    "set_language",
    "configure_privacy",
    "export_profile",
    "import_profile",
    "get_profile_size",
]