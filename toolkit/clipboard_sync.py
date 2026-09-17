"""
clipboard_sync.py - Production Clipboard Synchronization Module for Screen Agent Toolkit
"""

import win32clipboard
import win32con
import ctypes
from ctypes import wintypes
import pyperclip
from PIL import Image
import io
import json
import base64
import threading
import time
import hashlib
import pathlib
import os
import pickle
import re
from typing import Dict, Any, Callable, Optional, List, Union

# ---------------------------------------------------------------------------
# Type Aliases & Constants
# ---------------------------------------------------------------------------
ResultDict = Dict[str, Any]
TransformationFunc = Union[Callable[[str], str], str]

CF_UNICODETEXT = 13
CF_DIB = 8
CF_HDROP = 15
CF_RTF_HANDLE = None
CF_HTML_HANDLE = None

# ---------------------------------------------------------------------------
# Module-Level State & Thread Control
# ---------------------------------------------------------------------------
_history: List[Dict[str, Any]] = []
_history_lock = threading.Lock()
_watch_thread: Optional[threading.Thread] = None
_stop_watch_event = threading.Event()
_sync_thread: Optional[threading.Thread] = None
_stop_sync_event = threading.Event()
_max_history: int = 1000
_last_clip_hash: str = ""

def _get_html_format_handle() -> int:
    global CF_HTML_HANDLE
    if CF_HTML_HANDLE is None:
        CF_HTML_HANDLE = win32clipboard.RegisterClipboardFormat("HTML Format")
    return CF_HTML_HANDLE

def _get_rtf_format_handle() -> int:
    global CF_RTF_HANDLE
    if CF_RTF_HANDLE is None:
        CF_RTF_HANDLE = win32clipboard.RegisterClipboardFormat("Rich Text Format")
    return CF_RTF_HANDLE

# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------
def _safe_clipboard_op(func: Callable[..., Any]) -> callable:
    """Decorator to ensure Open/Close clipboard safely."""
    def wrapper(*args, **kwargs) -> ResultDict:
        try:
            win32clipboard.OpenClipboard()
            return func(*args, **kwargs)
        except Exception as e:
            return {"success": False, "error": str(e), "data": None, "message": "Clipboard operation failed"}
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
    return wrapper

def _compute_clip_hash() -> str:
    """Compute a deterministic hash of the current clipboard contents across common formats."""
    try:
        win32clipboard.OpenClipboard()
        hasher = hashlib.sha256()
        for fmt in [CF_UNICODETEXT, CF_DIB, _get_html_format_handle(), CF_HDROP]:
            try:
                data = win32clipboard.GetClipboardData(fmt)
                hasher.update(str(fmt).encode())
                hasher.update(str(data).encode())
            except Exception:
                continue
        win32clipboard.CloseClipboard()
        return hasher.hexdigest()
    except Exception:
        return ""

# ---------------------------------------------------------------------------
# Core Clipboard Functions
# ---------------------------------------------------------------------------

@_safe_clipboard_op
def copy_text(text: str) -> ResultDict:
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(text, CF_UNICODETEXT)
    return {"success": True, "message": "Text copied to clipboard", "data": None}

def paste_text() -> ResultDict:
    try:
        win32clipboard.OpenClipboard()
        try:
            text = win32clipboard.GetClipboardData(CF_UNICODETEXT)
            return {"success": True, "data": text, "message": "Text pasted"}
        except Exception as e:
            return {"success": False, "error": str(e), "data": None, "message": "Failed to paste text"}
        finally:
            win32clipboard.CloseClipboard()
    except Exception as e:
        return {"success": False, "error": str(e), "data": None, "message": "Clipboard access failed"}

@_safe_clipboard_op
def copy_image(image_path: str) -> ResultDict:
    img_path = pathlib.Path(image_path)
    if not img_path.exists():
        return {"success": False, "error": "File not found", "data": None, "message": f"Image path {image_path} does not exist"}
    with Image.open(img_path) as img:
        img = img.convert("RGBA") if img.mode != "RGBA" else img
        buf = io.BytesIO()
        img.save(buf, format="BMP")
        dib_data = buf.getvalue()[14:]  # Strip BMP file header to get DIB
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(CF_DIB, dib_data)
    return {"success": True, "message": "Image copied to clipboard", "data": None}

@_safe_clipboard_op
def paste_image(output_path: str) -> ResultDict:
    try:
        if not win32clipboard.IsClipboardFormatAvailable(CF_DIB):
            return {"success": False, "error": "No DIB format in clipboard", "data": None, "message": "Clipboard does not contain a compatible image"}
        dib_data = win32clipboard.GetClipboardData(CF_DIB)
        buf = io.BytesIO()
        # Reconstruct BMP header
        buf.write(b"BM")
        buf.write(ctypes.c_uint32(14 + len(dib_data)).value.to_bytes(4, "little"))
        buf.write(b"\x00\x00\x00\x00")
        buf.write(ctypes.c_uint32(14).value.to_bytes(4, "little"))
        buf.write(dib_data)
        buf.seek(0)
        with Image.open(buf) as img:
            out_path = pathlib.Path(output_path)
            img.save(out_path)
        return {"success": True, "message": "Image pasted and saved", "data": str(out_path)}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None, "message": "Failed to paste image"}

def _build_html_clipboard(html_content: str) -> bytes:
    header = "Version:1.0\nStartHTML:{:08}\nEndHTML:{:08}\nStartFragment:{:08}\nEndFragment:{:08}\n<html><body>" \
             "<!--StartFragment-->{html}<!--EndFragment--></body></html>"
    placeholder = "00000000"
    template = header.format(
        html_content=html_content.replace("{html}", placeholder[:8]),
        StartHTML=0, EndHTML=0, StartFragment=0, EndFragment=0
    )
    prefix = "Version:1.0\n"
    frag_start_idx = template.find("<!--StartFragment-->") + len("<!--StartFragment-->")
    frag_end_idx = template.find("<!--EndFragment-->")
    content = f"{prefix}" + template
    start_html = len(prefix)
    end_html = len(content)
    start_frag = content.find("<!--StartFragment-->") - len(prefix) + 8 # Adjust for structure
    # Simplified reliable calculation
    final = (
        f"Version:1.0\n"
        f"StartHTML:{str(start_html).zfill(8)}\n"
        f"StartFragment:{str(frag_start_idx).zfill(8)}\n"
        f"EndFragment:{str(frag_end_idx).zfill(8)}\n"
        f"EndHTML:{str(end_html).zfill(8)}\n"
        f"{html_content}"
    )
    return final.encode("utf-8")

@_safe_clipboard_op
def copy_html(html_content: str) -> ResultDict:
    raw_data = _build_html_clipboard(html_content)
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(_get_html_format_handle(), raw_data)
    return {"success": True, "message": "HTML copied to clipboard", "data": None}

@_safe_clipboard_op
def paste_html() -> ResultDict:
    try:
        if not win32clipboard.IsClipboardFormatAvailable(_get_html_format_handle()):
            return {"success": False, "error": "No HTML format in clipboard", "data": None, "message": "Clipboard does not contain HTML"}
        raw = win32clipboard.GetClipboardData(_get_html_format_handle())
        try:
            text = raw.decode("utf-8", errors="ignore")
            start_match = re.search(r"StartFragm(?:ent)?:(\d{8})", text)
            end_match = re.search(r"EndFragm(?:ent)?:(\d{8})", text)
            if start_match and end_match:
                start = int(start_match.group(1))
                end = int(end_match.group(1))
                fragment = text[start:end]
                return {"success": True, "data": fragment, "message": "HTML fragment pasted"}
            return {"success": True, "data": text, "message": "Full HTML pasted"}
        except Exception as e:
            return {"success": False, "error": str(e), "data": None, "message": "Failed to decode HTML"}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None, "message": "Clipboard access failed"}

def _build_hdrop_data(paths: List[str]) -> bytes:
    # DROPFILES structure: pFiles(4), pt(8), fNC(4), fWide(4) = 20 bytes
    header = ctypes.create_string_buffer(20)
    ctypes.memmove(header, ctypes.c_uint32(20).value.to_bytes(4, "little"), 4)
    ctypes.memmove(ctypes.addressof(header) + 16, ctypes.c_uint32(1).value.to_bytes(4, "little"), 4) # fWide = True
    path_str = "\0".join(paths) + "\0\0"
    path_bytes = path_str.encode("utf-16-le")
    return bytes(header) + path_bytes

@_safe_clipboard_op
def copy_files(file_paths: Union[str, List[str]]) -> ResultDict:
    paths = [file_paths] if isinstance(file_paths, str) else file_paths
    abs_paths = [str(pathlib.Path(p).resolve()) for p in paths if os.path.exists(p)]
    if not abs_paths:
        return {"success": False, "error": "No valid files found", "data": None, "message": "Invalid or missing file paths"}
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(CF_HDROP, _build_hdrop_data(abs_paths))
    return {"success": True, "message": "Files copied to clipboard", "data": None}

@_safe_clipboard_op
def paste_files() -> ResultDict:
    try:
        if not win32clipboard.IsClipboardFormatAvailable(CF_HDROP):
            return {"success": False, "error": "No file list in clipboard", "data": None, "message": "Clipboard does not contain file references"}
        hdrop = win32clipboard.GetClipboardData(CF_HDROP)
        buffer_offset = ctypes.c_uint32.from_buffer_copy(hdrop[0:4]).value
        paths = hdrop[buffer_offset:].decode("utf-16-le").rstrip("\0").split("\0")
        return {"success": True, "data": paths, "message": "File paths pasted"}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None, "message": "Failed to paste files"}

@_safe_clipboard_op
def get_clipboard_format() -> ResultDict:
    formats = []
    fmt = 0
    while True:
        fmt = win32clipboard.EnumClipboardFormats(fmt)
        if fmt == 0:
            break
        name = win32clipboard.GetClipboardFormatName(fmt) or f"CF_{fmt}"
        formats.append({"id": fmt, "name": name})
    return {"success": True, "data": formats, "message": "Formats retrieved"}

@_safe_clipboard_op
def clear_clipboard() -> ResultDict:
    win32clipboard.EmptyClipboard()
    return {"success": True, "message": "Clipboard cleared", "data": None}

# ---------------------------------------------------------------------------
# History & Monitoring
# ---------------------------------------------------------------------------
def clipboard_history_start(max_items: int = 100) -> ResultDict:
    global _max_history, _history_lock, _last_clip_hash
    _max_history = max_items
    _last_clip_hash = _compute_clip_hash()
    if _watch_thread and _watch_thread.is_alive():
        return {"success": False, "error": "History already running", "data": None, "message": "Cannot start history while watcher is active"}
    
    def _history_worker():
        global _last_clip_hash
        while not _stop_watch_event.is_set():
            current_hash = _compute_clip_hash()
            if current_hash and current_hash != _last_clip_hash:
                entry = {"timestamp": time.time(), "hash": current_hash}
                try:
                    win32clipboard.OpenClipboard()
                    if win32clipboard.IsClipboardFormatAvailable(CF_UNICODETEXT):
                        entry["type"] = "text"
                        entry["data"] = win32clipboard.GetClipboardData(CF_UNICODETEXT)
                    elif win32clipboard.IsClipboardFormatAvailable(CF_DIB):
                        entry["type"] = "image"
                        entry["data"] = "<image_bytes>"
                    else:
                        entry["type"] = "other"
                        entry["data"] = str(win32clipboard.EnumClipboardFormats(0))[:100]
                    win32clipboard.CloseClipboard()
                except:
                    entry["type"] = "unknown"
                    entry["data"] = None
                
                with _history_lock:
                    _history.append(entry)
                    if len(_history) > _max_history:
                        _history.pop(0)
                _last_clip_hash = current_hash
            time.sleep(0.2)

    _stop_watch_event.clear()
    _watch_thread = threading.Thread(target=_history_worker, daemon=True)
    _watch_thread.start()
    return {"success": True, "message": f"History tracking started (max_items={max_items})", "data": None}

def clipboard_history_stop() -> ResultDict:
    _stop_watch_event.set()
    if _watch_thread:
        _watch_thread.join(timeout=2.0)
    _stop_watch_event.clear()
    return {"success": True, "message": "History tracking stopped", "data": None}

def get_clipboard_history(count: int = 10) -> ResultDict:
    with _history_lock:
        result = _history[-count:] if count > 0 else _history[:]
    return {"success": True, "data": result, "message": f"Retrieved {len(result)} history items"}

def search_clipboard_history(pattern: str) -> ResultDict:
    regex = re.compile(pattern, re.IGNORECASE)
    with _history_lock:
        matches = [item for item in _history if "data" in item and isinstance(item["data"], str) and regex.search(item["data"])]
    return {"success": True, "data": matches, "message": f"Found {len(matches)} matches"}

# ---------------------------------------------------------------------------
# State Persistence & Sync
# ---------------------------------------------------------------------------
@_safe_clipboard_op
def save_clipboard_state(filepath: str) -> ResultDict:
    state = {"timestamp": time.time(), "formats": {}}
    try:
        win32clipboard.OpenClipboard()
        fmt = 0
        while True:
            fmt = win32clipboard.EnumClipboardFormats(fmt)
            if fmt == 0: break
            try:
                data = win32clipboard.GetClipboardData(fmt)
                name = win32clipboard.GetClipboardFormatName(fmt) or str(fmt)
                # Base64 encode binary data safely
                if isinstance(data, (bytes, bytearray)):
                    state["formats"][name] = {"type": "binary", "data": base64.b64encode(data).decode("utf-8")}
                else:
                    state["formats"][name] = {"type": "text", "data": data}
            except:
                continue
        win32clipboard.CloseClipboard()
    except Exception as e:
        return {"success": False, "error": str(e), "data": None, "message": "Failed to read clipboard"}

    out_path = pathlib.Path(filepath)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        pickle.dump(state, f)
    return {"success": True, "message": f"Clipboard state saved to {filepath}", "data": None}

def restore_clipboard_state(filepath: str) -> ResultDict:
    in_path = pathlib.Path(filepath)
    if not in_path.exists():
        return {"success": False, "error": "File not found", "data": None, "message": f"State file {filepath} missing"}
    try:
        with open(in_path, "rb") as f:
            state = pickle.load(f)
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        for fmt_name, item in state.get("formats", {}).items():
            try:
                fmt_id = win32clipboard.RegisterClipboardFormat(fmt_name) if not fmt_name.isdigit() else int(fmt_name)
                if item.get("type") == "binary":
                    raw = base64.b64decode(item["data"])
                    win32clipboard.SetClipboardData(fmt_id, raw)
                else:
                    win32clipboard.SetClipboardText(item["data"], fmt_id)
            except:
                continue
        win32clipboard.CloseClipboard()
        return {"success": True, "message": "Clipboard state restored", "data": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None, "message": "Restore failed"}

def watch_clipboard(callback: Callable[[Dict[str, Any]], None], interval: float = 1.0) -> ResultDict:
    global _watch_thread, _stop_watch_event
    if _watch_thread and _watch_thread.is_alive():
        return {"success": False, "error": "Already watching", "data": None, "message": "Stop current watch first"}
    
    _stop_watch_event.clear()
    def _worker():
        last = _compute_clip_hash()
        while not _stop_watch_event.is_set():
            curr = _compute_clip_hash()
            if curr and curr != last:
                try:
                    win32clipboard.OpenClipboard()
                    event = {"timestamp": time.time(), "hash": curr, "formats": []}
                    fmt = 0
                    while True:
                        fmt = win32clipboard.EnumClipboardFormats(fmt)
                        if fmt == 0: break
                        n = win32clipboard.GetClipboardFormatName(fmt) or str(fmt)
                        event["formats"].append(n)
                    win32clipboard.CloseClipboard()
                    callback(event)
                except: pass
                last = curr
            time.sleep(interval)

    _watch_thread = threading.Thread(target=_worker, daemon=True)
    _watch_thread.start()
    return {"success": True, "message": f"Watching clipboard every {interval}s", "data": None}

def stop_watching_clipboard() -> ResultDict:
    _stop_watch_event.set()
    if _watch_thread:
        _watch_thread.join(timeout=2.0)
    _stop_watch_event.clear()
    return {"success": True, "message": "Clipboard watches stopped", "data": None}

@_safe_clipboard_op
def copy_rich_text(text: str, format: str = "rtf") -> ResultDict:
    if format.lower() != "rtf":
        return {"success": False, "error": "Unsupported format", "data": None, "message": "Only RTF is supported for rich text"}
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(_get_rtf_format_handle(), text.encode("utf-8"))
    return {"success": True, "message": "Rich text copied", "data": None}

@_safe_clipboard_op
def clipboard_to_base64() -> ResultDict:
    try:
        win32clipboard.OpenClipboard()
        for fmt in [CF_UNICODETEXT, CF_DIB, _get_html_format_handle()]:
            try:
                data = win32clipboard.GetClipboardData(fmt)
                if isinstance(data, str): data = data.encode("utf-8")
                return {"success": True, "data": base64.b64encode(data).decode("utf-8"), "message": "Encoded to base64"}
            except: continue
        return {"success": False, "error": "No encodable data", "data": None, "message": "Clipboard empty or unsupported"}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None, "message": "Encoding failed"}
    finally:
        try: win32clipboard.CloseClipboard()
        except: pass

@_safe_clipboard_op
def base64_to_clipboard(b64_data: str, format: str = "text") -> ResultDict:
    try:
        raw = base64.b64decode(b64_data)
        win32clipboard.EmptyClipboard()
        if format.lower() == "text":
            win32clipboard.SetClipboardText(raw.decode("utf-8", errors="ignore"))
        elif format.lower() == "image":
            win32clipboard.SetClipboardData(CF_DIB, raw)
        else:
            win32clipboard.SetClipboardData(win32con.CF_OEMTEXT, raw)
        return {"success": True, "message": f"Base64 decoded and copied as {format}", "data": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None, "message": "Base64 decode failed"}

def sync_clipboard_to_file(filepath: str, interval: float = 5.0) -> ResultDict:
    global _sync_thread, _stop_sync_event
    if _sync_thread and _sync_thread.is_alive():
        return {"success": False, "error": "Sync already running", "data": None, "message": "Stop current sync first"}
    _stop_sync_event.clear()
    def _worker():
        while not _stop_sync_event.is_set():
            try:
                win32clipboard.OpenClipboard()
                state = {"ts": time.time(), "data": None}
                if win32clipboard.IsClipboardFormatAvailable(CF_UNICODETEXT):
                    state["data"] = win32clipboard.GetClipboardData(CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(state, f, default=str)
            except: pass
            time.sleep(interval)
    _sync_thread = threading.Thread(target=_worker, daemon=True)
    _sync_thread.start()
    return {"success": True, "message": f"Syncing clipboard to {filepath} every {interval}s", "data": None}

@_safe_clipboard_op
def merge_clipboard_items(items: Union[str, List[str]], separator: str = "\n") -> ResultDict:
    it = [items] if isinstance(items, str) else items
    merged = separator.join(str(x) for x in it)
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(merged)
    return {"success": True, "message": "Items merged and copied", "data": None}

@_safe_clipboard_op
def transform_clipboard(transformation: TransformationFunc) -> ResultDict:
    try:
        win32clipboard.OpenClipboard()
        original = win32clipboard.GetClipboardData(CF_UNICODETEXT)
        if callable(transformation):
            result = transformation(original)
        elif isinstance(transformation, str):
            result = original.replace("{input}", transformation)
        else:
            raise ValueError("Unsupported transformation type")
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(result)
        return {"success": True, "message": "Clipboard transformed", "data": result}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None, "message": "Transformation failed"}
    finally:
        try: win32clipboard.CloseClipboard()
        except: pass

@_safe_clipboard_op
def get_clipboard_size() -> ResultDict:
    total_bytes = 0
    fmt = 0
    while True:
        fmt = win32clipboard.EnumClipboardFormats(fmt)
        if fmt == 0: break
        try:
            data = win32clipboard.GetClipboardData(fmt)
            if isinstance(data, (bytes, bytearray)):
                total_bytes += len(data)
            elif isinstance(data, str):
                total_bytes += len(data.encode("utf-16-le"))
        except: continue
    return {"success": True, "data": {"bytes": total_bytes, "kb": round(total_bytes / 1024, 2)}, "message": "Size calculated"}