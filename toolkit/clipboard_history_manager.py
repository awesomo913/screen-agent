#!/usr/bin/env python3
"""Desktop Clipboard History Manager - Track, search, and manage clipboard history with screen automation."""

import os, sys, time, json, argparse, threading, hashlib, re
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import pyautogui, pyperclip
from PIL import Image, ImageGrab
try:
    from pynput import keyboard
except ImportError:
    keyboard = None
try:
    import win32clipboard, win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

@dataclass
class ClipboardEntry:
    id: int
    content: str
    content_type: str = "text"
    source_app: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    pinned: bool = False
    tags: List[str] = field(default_factory=list)
    hash: str = ""
    image_path: Optional[str] = None

class ClipboardMonitor:
    def __init__(self, config_path=None, storage_dir=None, max_entries=500):
        self.config_path = config_path or os.path.expanduser("~/.clipboard_history_config.json")
        self.storage_dir = storage_dir or os.path.expanduser("~/clipboard_history")
        os.makedirs(self.storage_dir, exist_ok=True)
        self.history: List[ClipboardEntry] = []
        self.max_entries = max_entries
        self.next_id = 1
        self.monitoring = False
        self.last_hash = ""
        self.poll_interval = 0.5
        self._lock = threading.Lock()
        self.callbacks = []
        self.load_history()

    def load_history(self):
        hist_file = os.path.join(self.storage_dir, "clipboard_history.json")
        if os.path.exists(hist_file):
            with open(hist_file, "r") as f:
                data = json.load(f)
            for entry_data in data.get("entries", []):
                self.history.append(ClipboardEntry(**entry_data))
            self.next_id = data.get("next_id", len(self.history) + 1)

    def save_history(self):
        hist_file = os.path.join(self.storage_dir, "clipboard_history.json")
        data = {"next_id": self.next_id, "entries": []}
        for e in self.history[-self.max_entries:]:
            data["entries"].append({
                "id": e.id, "content": e.content[:5000], "content_type": e.content_type,
                "source_app": e.source_app, "timestamp": e.timestamp,
                "pinned": e.pinned, "tags": e.tags, "hash": e.hash, "image_path": e.image_path
            })
        with open(hist_file, "w") as f:
            json.dump(data, f, indent=2)

    def get_clipboard_content(self):
        try:
            text = pyperclip.paste()
            if text:
                content_hash = hashlib.md5(text.encode()).hexdigest()
                return text, "text", content_hash
        except:
            pass
        try:
            img = ImageGrab.grabclipboard()
            if img and isinstance(img, Image.Image):
                img_hash = hashlib.md5(img.tobytes()[:4096]).hexdigest()
                return "[IMAGE]", "image", img_hash
        except:
            pass
        return None, None, None

    def _save_clipboard_image(self, entry_id):
        try:
            img = ImageGrab.grabclipboard()
            if img and isinstance(img, Image.Image):
                path = os.path.join(self.storage_dir, f"clip_img_{entry_id}.png")
                img.save(path)
                return path
        except:
            pass
        return None

    def add_entry(self, content, content_type="text", source_app=""):
        content_hash = hashlib.md5(content.encode() if isinstance(content, str) else content).hexdigest()
        if self.history and self.history[-1].hash == content_hash:
            return None
        entry = ClipboardEntry(
            id=self.next_id, content=content if isinstance(content, str) else "[IMAGE]",
            content_type=content_type, source_app=source_app, hash=content_hash
        )
        if content_type == "image":
            entry.image_path = self._save_clipboard_image(entry.id)
        with self._lock:
            self.history.append(entry)
            self.next_id += 1
            if len(self.history) > self.max_entries:
                non_pinned = [e for e in self.history if not e.pinned]
                if non_pinned:
                    self.history.remove(non_pinned[0])
        for cb in self.callbacks:
            cb(entry)
        return entry

    def start_monitoring(self):
        self.monitoring = True
        print(f"Clipboard monitoring started (interval={self.poll_interval}s)")
        print(f"History: {len(self.history)} entries")
        print("Press Ctrl+C to stop")
        try:
            while self.monitoring:
                content, ctype, chash = self.get_clipboard_content()
                if content and chash != self.last_hash:
                    self.last_hash = chash
                    entry = self.add_entry(content, ctype)
                    if entry:
                        preview = content[:60].replace('\n', ' ') if ctype == "text" else "[IMAGE]"
                        print(f"  [{entry.timestamp[11:19]}] #{entry.id}: {preview}")
                        self.save_history()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            self.monitoring = False
        self.save_history()
        print(f"Monitoring stopped. Total entries: {len(self.history)}")

    def search(self, query, max_results=20):
        results = []
        query_lower = query.lower()
        for entry in reversed(self.history):
            if entry.content_type == "text" and query_lower in entry.content.lower():
                results.append(entry)
                if len(results) >= max_results:
                    break
        return results

    def get_recent(self, count=10):
        return list(reversed(self.history[-count:]))

    def get_by_id(self, entry_id):
        for e in self.history:
            if e.id == entry_id:
                return e
        return None

    def paste_entry(self, entry_id):
        entry = self.get_by_id(entry_id)
        if not entry:
            print(f"Entry #{entry_id} not found")
            return
        if entry.content_type == "text":
            pyperclip.copy(entry.content)
            time.sleep(0.1)
            pyautogui.hotkey("ctrl", "v")
            print(f"Pasted entry #{entry_id}")
        elif entry.content_type == "image" and entry.image_path:
            if HAS_WIN32:
                img = Image.open(entry.image_path)
                import io
                output = io.BytesIO()
                img.convert("RGB").save(output, "BMP")
                data = output.getvalue()[14:]
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_DIB, data)
                win32clipboard.CloseClipboard()
                pyautogui.hotkey("ctrl", "v")

    def pin_entry(self, entry_id, pinned=True):
        entry = self.get_by_id(entry_id)
        if entry:
            entry.pinned = pinned
            self.save_history()
            print(f"Entry #{entry_id} {'pinned' if pinned else 'unpinned'}")

    def tag_entry(self, entry_id, tags):
        entry = self.get_by_id(entry_id)
        if entry:
            entry.tags = list(set(entry.tags + tags))
            self.save_history()

    def delete_entry(self, entry_id):
        self.history = [e for e in self.history if e.id != entry_id]
        self.save_history()

    def clear_history(self, keep_pinned=True):
        if keep_pinned:
            self.history = [e for e in self.history if e.pinned]
        else:
            self.history = []
        self.save_history()
        print("History cleared")

    def export_history(self, output_path, format="json"):
        data = [{"id": e.id, "content": e.content[:1000], "type": e.content_type,
                  "timestamp": e.timestamp, "pinned": e.pinned, "tags": e.tags}
                 for e in self.history]
        if format == "json":
            with open(output_path, "w") as f:
                json.dump(data, f, indent=2)
        elif format == "txt":
            with open(output_path, "w") as f:
                for e in self.history:
                    f.write(f"--- #{e.id} [{e.timestamp}] ---\n{e.content}\n\n")
        print(f"Exported {len(data)} entries to {output_path}")

    def get_stats(self):
        total = len(self.history)
        text_count = sum(1 for e in self.history if e.content_type == "text")
        image_count = sum(1 for e in self.history if e.content_type == "image")
        pinned = sum(1 for e in self.history if e.pinned)
        avg_len = sum(len(e.content) for e in self.history if e.content_type == "text") / max(1, text_count)
        return {"total": total, "text": text_count, "images": image_count,
                "pinned": pinned, "avg_text_length": int(avg_len)}

    def setup_hotkeys(self):
        if not keyboard:
            print("pynput required")
            return
        print("Clipboard hotkeys active:")
        print("  Ctrl+Shift+V: Show recent 10")
        print("  Ctrl+Shift+1-9: Paste from history")
        print("  ESC: Exit")
        current_keys = set()
        def on_press(key):
            current_keys.add(key)
            try:
                if keyboard.Key.ctrl_l in current_keys and keyboard.Key.shift in current_keys:
                    if hasattr(key, 'char') and key.char == 'v':
                        recent = self.get_recent(10)
                        for e in recent:
                            preview = e.content[:50].replace('\n', ' ')
                            print(f"  #{e.id}: {preview}")
                    elif hasattr(key, 'char') and key.char in '123456789':
                        idx = int(key.char) - 1
                        recent = self.get_recent(9)
                        if idx < len(recent):
                            self.paste_entry(recent[idx].id)
                if key == keyboard.Key.esc:
                    return False
            except:
                pass
        def on_release(key):
            current_keys.discard(key)
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()

def main():
    parser = argparse.ArgumentParser(description="Desktop Clipboard History Manager")
    parser.add_argument("--config", help="Config file")
    parser.add_argument("--storage", help="Storage directory")
    parser.add_argument("--max", type=int, default=500)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("monitor", help="Start clipboard monitoring")
    recent_p = subparsers.add_parser("recent", help="Show recent entries")
    recent_p.add_argument("-n", type=int, default=10)
    search_p = subparsers.add_parser("search", help="Search clipboard history")
    search_p.add_argument("query")
    paste_p = subparsers.add_parser("paste", help="Paste entry by ID")
    paste_p.add_argument("id", type=int)
    pin_p = subparsers.add_parser("pin", help="Pin an entry")
    pin_p.add_argument("id", type=int)
    unpin_p = subparsers.add_parser("unpin", help="Unpin an entry")
    unpin_p.add_argument("id", type=int)
    del_p = subparsers.add_parser("delete", help="Delete an entry")
    del_p.add_argument("id", type=int)
    clear_p = subparsers.add_parser("clear", help="Clear history")
    clear_p.add_argument("--include-pinned", action="store_true")
    export_p = subparsers.add_parser("export", help="Export history")
    export_p.add_argument("output")
    export_p.add_argument("--format", choices=["json", "txt"], default="json")
    subparsers.add_parser("stats", help="Show statistics")
    subparsers.add_parser("hotkeys", help="Start hotkey listener")
    args = parser.parse_args()
    mgr = ClipboardMonitor(config_path=args.config, storage_dir=args.storage, max_entries=args.max)
    if args.command == "monitor":
        mgr.start_monitoring()
    elif args.command == "recent":
        for e in mgr.get_recent(args.n):
            pin = "[PIN]" if e.pinned else ""
            preview = e.content[:70].replace('\n', ' ')
            print(f"  #{e.id} {pin} [{e.timestamp[11:19]}] {preview}")
    elif args.command == "search":
        for e in mgr.search(args.query):
            print(f"  #{e.id} [{e.timestamp[11:19]}] {e.content[:70].replace(chr(10), ' ')}")
    elif args.command == "paste":
        mgr.paste_entry(args.id)
    elif args.command == "pin":
        mgr.pin_entry(args.id, True)
    elif args.command == "unpin":
        mgr.pin_entry(args.id, False)
    elif args.command == "delete":
        mgr.delete_entry(args.id)
    elif args.command == "clear":
        mgr.clear_history(not args.include_pinned)
    elif args.command == "export":
        mgr.export_history(args.output, args.format)
    elif args.command == "stats":
        stats = mgr.get_stats()
        for k, v in stats.items():
            print(f"  {k}: {v}")
    elif args.command == "hotkeys":
        mgr.setup_hotkeys()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
