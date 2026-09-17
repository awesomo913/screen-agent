from __future__ import annotations

import base64
import datetime as dt
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Union

import pyperclip
from PIL import Image, ImageGrab


ClipboardItem = Dict[str, Any]

_HISTORY: List[ClipboardItem] = []
_HISTORY_RUNNING = False
_HISTORY_THREAD: Optional[threading.Thread] = None
_MONITOR_RUNNING = False
_MONITOR_THREAD: Optional[threading.Thread] = None
_LAST_CLIPBOARD_VALUE: Optional[str] = None
_LOCK = threading.RLock()


def _ok(**kwargs: Any) -> Dict[str, Any]:
    return {"success": True, "timestamp": dt.datetime.utcnow().isoformat(), **kwargs}


def _err(message: str, **kwargs: Any) -> Dict[str, Any]:
    return {"success": False, "error": message, "timestamp": dt.datetime.utcnow().isoformat(), **kwargs}


def _add_history(content: Any, fmt: str) -> None:
    with _LOCK:
        _HISTORY.append(
            {
                "content": content,
                "format": fmt,
                "timestamp": dt.datetime.utcnow().isoformat(),
            }
        )


def copy_text(text: str) -> Dict[str, Any]:
    try:
        pyperclip.copy(text)
        _add_history(text, "text")
        return _ok(format="text", length=len(text))
    except Exception as e:
        return _err(str(e))


def paste_text() -> Dict[str, Any]:
    try:
        text = pyperclip.paste()
        return _ok(content=text, format="text")
    except Exception as e:
        return _err(str(e))


def copy_image(image_path: Union[str, Path]) -> Dict[str, Any]:
    try:
        path = Path(image_path)
        img = Image.open(path)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        pyperclip.copy(f"__IMAGE_BASE64__:{encoded}")
        _add_history(encoded, "image")
        return _ok(format="image", size=img.size)
    except Exception as e:
        return _err(str(e))


def paste_image(output_path: Union[str, Path]) -> Dict[str, Any]:
    try:
        raw = pyperclip.paste()
        if not str(raw).startswith("__IMAGE_BASE64__:"):
            return _err("Clipboard does not contain an encoded image")
        data = base64.b64decode(str(raw).split(":", 1)[1])
        img = Image.open(io.BytesIO(data))
        out = Path(output_path)
        img.save(out)
        return _ok(path=str(out), size=img.size)
    except Exception as e:
        return _err(str(e))


def copy_file_path(file_path: Union[str, Path]) -> Dict[str, Any]:
    try:
        path = str(Path(file_path).resolve())
        pyperclip.copy(path)
        _add_history(path, "file_path")
        return _ok(path=path)
    except Exception as e:
        return _err(str(e))


def paste_file_path() -> Dict[str, Any]:
    return paste_text()


def copy_html(html_content: str) -> Dict[str, Any]:
    return copy_text(f"__HTML__:{html_content}")


def paste_html() -> Dict[str, Any]:
    try:
        raw = pyperclip.paste()
        if str(raw).startswith("__HTML__:"):
            return _ok(content=str(raw)[9:], format="html")
        return _err("Clipboard does not contain HTML")
    except Exception as e:
        return _err(str(e))


def get_clipboard_format() -> Dict[str, Any]:
    try:
        raw = pyperclip.paste()
        s = str(raw)
        if s.startswith("__IMAGE_BASE64__:"):
            fmt = "image"
        elif s.startswith("__HTML__:"):
            fmt = "html"
        elif s.startswith("__JSON__:"):
            fmt = "json"
        else:
            fmt = "text"
        return _ok(format=fmt)
    except Exception as e:
        return _err(str(e))


def clear_clipboard() -> Dict[str, Any]:
    return copy_text("")


def clipboard_has_text() -> Dict[str, Any]:
    try:
        return _ok(has_text=bool(pyperclip.paste()))
    except Exception as e:
        return _err(str(e))


def clipboard_has_image() -> Dict[str, Any]:
    try:
        return _ok(has_image=str(pyperclip.paste()).startswith("__IMAGE_BASE64__:"))
    except Exception as e:
        return _err(str(e))


def copy_json(data: Any) -> Dict[str, Any]:
    try:
        payload = json.dumps(data, ensure_ascii=False)
        pyperclip.copy(f"__JSON__:{payload}")
        _add_history(data, "json")
        return _ok(format="json")
    except Exception as e:
        return _err(str(e))


def paste_json() -> Dict[str, Any]:
    try:
        raw = str(pyperclip.paste())
        if not raw.startswith("__JSON__:"):
            return _err("Clipboard does not contain JSON")
        return _ok(data=json.loads(raw[9:]))
    except Exception as e:
        return _err(str(e))


def copy_base64(data: bytes) -> Dict[str, Any]:
    try:
        encoded = base64.b64encode(data).decode()
        pyperclip.copy(encoded)
        _add_history(encoded, "base64")
        return _ok(length=len(encoded))
    except Exception as e:
        return _err(str(e))


def paste_base64() -> Dict[str, Any]:
    try:
        raw = pyperclip.paste()
        return _ok(data=base64.b64decode(raw))
    except Exception as e:
        return _err(str(e))


def clipboard_history_start(max_items: int = 100) -> Dict[str, Any]:
    global _HISTORY_RUNNING, _HISTORY_THREAD
    if _HISTORY_RUNNING:
        return _ok(message="history already running")

    _HISTORY_RUNNING = True

    def worker() -> None:
        last = None
        while _HISTORY_RUNNING:
            try:
                current = pyperclip.paste()
                if current != last:
                    _add_history(current, "auto")
                    with _LOCK:
                        del _HISTORY[:-max_items]
                    last = current
            except Exception:
                pass
            time.sleep(0.5)

    _HISTORY_THREAD = threading.Thread(target=worker, daemon=True)
    _HISTORY_THREAD.start()
    return _ok(max_items=max_items)


def clipboard_history_stop() -> Dict[str, Any]:
    global _HISTORY_RUNNING
    _HISTORY_RUNNING = False
    return _ok()


def get_clipboard_history() -> Dict[str, Any]:
    return _ok(history=list(_HISTORY))


def clear_clipboard_history() -> Dict[str, Any]:
    with _LOCK:
        _HISTORY.clear()
    return _ok()


def search_clipboard_history(query: str) -> Dict[str, Any]:
    matches = [i for i in _HISTORY if query.lower() in str(i["content"]).lower()]
    return _ok(results=matches)


def copy_multiple(items: List[Any]) -> Dict[str, Any]:
    return copy_json(items)


def paste_from_history(index: int) -> Dict[str, Any]:
    try:
        item = _HISTORY[index]
        pyperclip.copy(str(item["content"]))
        return _ok(item=item)
    except Exception as e:
        return _err(str(e))


def copy_rich_text(text: str, html: str) -> Dict[str, Any]:
    return copy_json({"text": text, "html": html, "type": "rich_text"})


def paste_rich_text() -> Dict[str, Any]:
    return paste_json()


def copy_screenshot_region(x: int, y: int, width: int, height: int) -> Dict[str, Any]:
    try:
        img = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return copy_base64(buf.getvalue())
    except Exception as e:
        return _err(str(e))


def copy_to_file(output_path: Union[str, Path]) -> Dict[str, Any]:
    try:
        content = pyperclip.paste()
        path = Path(output_path)
        path.write_text(str(content), encoding="utf-8")
        return _ok(path=str(path))
    except Exception as e:
        return _err(str(e))


def paste_from_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    try:
        content = Path(file_path).read_text(encoding="utf-8")
        return copy_text(content)
    except Exception as e:
        return _err(str(e))


def monitor_clipboard(callback: Callable[[str], None], interval: float = 0.5) -> Dict[str, Any]:
    global _MONITOR_RUNNING, _MONITOR_THREAD
    if _MONITOR_RUNNING:
        return _ok(message="monitor already running")
    _MONITOR_RUNNING = True

    def worker() -> None:
        last = None
        while _MONITOR_RUNNING:
            try:
                current = pyperclip.paste()
                if current != last:
                    callback(current)
                    last = current
            except Exception:
                pass
            time.sleep(interval)

    _MONITOR_THREAD = threading.Thread(target=worker, daemon=True)
    _MONITOR_THREAD.start()
    return _ok(interval=interval)


def stop_clipboard_monitor() -> Dict[str, Any]:
    global _MONITOR_RUNNING
    _MONITOR_RUNNING = False
    return _ok()


def transform_clipboard(func: Callable[[str], str]) -> Dict[str, Any]:
    try:
        content = pyperclip.paste()
        transformed = func(content)
        pyperclip.copy(transformed)
        return _ok(content=transformed)
    except Exception as e:
        return _err(str(e))


def clipboard_diff(text1: str, text2: str) -> Dict[str, Any]:
    set1, set2 = set(text1.splitlines()), set(text2.splitlines())
    return _ok(added=list(set2 - set1), removed=list(set1 - set2))


def merge_clipboard_items(indices: List[int], separator: str = "\n") -> Dict[str, Any]:
    try:
        merged = separator.join(str(_HISTORY[i]["content"]) for i in indices)
        pyperclip.copy(merged)
        return _ok(content=merged)
    except Exception as e:
        return _err(str(e))


def export_clipboard_history(output_path: Union[str, Path]) -> Dict[str, Any]:
    try:
        path = Path(output_path)
        path.write_text(json.dumps(_HISTORY, ensure_ascii=False, indent=2), encoding="utf-8")
        return _ok(path=str(path))
    except Exception as e:
        return _err(str(e))


def import_clipboard_history(file_path: Union[str, Path]) -> Dict[str, Any]:
    try:
        global _HISTORY
        _HISTORY = json.loads(Path(file_path).read_text(encoding="utf-8"))
        return _ok(count=len(_HISTORY))
    except Exception as e:
        return _err(str(e))


def copy_formatted_code(code: str, language: str) -> Dict[str, Any]:
    fenced = f"```{language}\n{code}\n```"
    return copy_text(fenced)


def copy_table_data(headers: List[str], rows: List[List[Any]]) -> Dict[str, Any]:
    lines = [",".join(headers)] + [",".join(map(str, row)) for row in rows]
    return copy_text("\n".join(lines))


def paste_as_plain_text() -> Dict[str, Any]:
    return paste_text()


def smart_paste(target_format: str) -> Dict[str, Any]:
    try:
        content = pyperclip.paste()
        if target_format == "json":
            return _ok(data=json.loads(content))
        if target_format == "base64":
            return _ok(data=base64.b64decode(content))
        return _ok(content=str(content))
    except Exception as e:
        return _err(str(e))


def clipboard_size() -> Dict[str, Any]:
    try:
        content = str(pyperclip.paste())
        return _ok(size_bytes=len(content.encode("utf-8")))
    except Exception as e:
        return _err(str(e))


def copy_url(url: str) -> Dict[str, Any]:
    if not (url.startswith("http://") or url.startswith("https://")):
        return _err("Invalid URL")
    return copy_text(url)
