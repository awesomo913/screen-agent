"""
tray_icon.py - Production-ready System Tray Agent Toolkit
Dependencies: pystray, Pillow (PIL), threading, tkinter, os, json
"""

import os
import json
import time
import threading
import tempfile
from typing import Callable, Dict, Any, List, Optional, Tuple, Union

import pystray
from PIL import Image, ImageDraw, ImageFont


class _TrayManager:
    """Internal singleton managing the system tray state and pystray interactions."""
    _instance: Optional["_TrayManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "_TrayManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self.icon: Optional[pystray.Icon] = None
        self.is_running: bool = False
        self.is_visible: bool = False
        self.tooltip: str = "Agent"
        self.menu_items: List[Dict[str, Any]] = []
        self.click_callback: Optional[Callable] = None
        self.double_click_callback: Optional[Callable] = None
        self._click_timer: Optional[threading.Timer] = None
        self._animation_thread: Optional[threading.Thread] = None
        self._animation_stop_event = threading.Event()
        self._initialized = True

    def _build_menu(self) -> Optional[pystray.Menu]:
        """Rebuilds pystray Menu from internal state."""
        def _create_item(item: Dict[str, Any]) -> Optional[pystray.MenuItem]:
            if item.get("type") == "separator":
                return pystray.Menu.SEPARATOR
            
            label = item["label"]
            enabled = item.get("enabled", True)
            checked = item.get("checked", False)
            callback = item.get("callback")
            
            if item.get("type") == "submenu":
                sub_items = []
                for si in item.get("submenu_items", []):
                    sub_item = _create_item(si)
                    if sub_item:
                        sub_items.append(sub_item)
                return pystray.MenuItem(label, pystray.Menu(*sub_items), enabled=enabled)
            
            return pystray.MenuItem(label, callback if callback else lambda: None, enabled=enabled, checked=checked)

        items = [_create_item(i) for i in self.menu_items]
        items = [i for i in items if i is not None]
        return pystray.Menu(*items) if items else None

    def _on_click(self, button) -> None:
        """Handles left-click and double-click detection."""
        if hasattr(button, 'name') and button.name != 'left':
            return
        
        if self._click_timer and self._click_timer.is_alive():
            self._click_timer.cancel()
            self._click_timer = None
            if self.double_click_callback:
                try:
                    self.double_click_callback()
                except Exception:
                    pass
        else:
            def _trigger_single() -> None:
                if self.click_callback:
                    try:
                        self.click_callback()
                    except Exception:
                        pass
            self._click_timer = threading.Timer(0.25, _trigger_single)
            self._click_timer.start()

    def _animation_loop(self, frames: List[Image.Image], interval: float) -> None:
        """Background thread for icon animation."""
        self._animation_stop_event.clear()
        while not self._animation_stop_event.is_set():
            for frame in frames:
                if self._animation_stop_event.is_set() or not self.is_visible:
                    break
                try:
                    if self.icon:
                        self.icon.icon = frame
                    time.sleep(interval)
                except Exception:
                    break


# Global manager instance
_manager = _TrayManager()


def create_tray_icon(title: str = "Agent", icon_path: str = "") -> Dict[str, Any]:
    """Initialize and start the system tray icon."""
    try:
        _manager.tooltip = title
        img = None
        if icon_path and os.path.exists(icon_path):
            img = Image.open(icon_path)
        if img is None:
            img = Image.new("RGBA", (64, 64), (0, 100, 255, 255))
        
        menu = _manager._build_menu()
        _manager.icon = pystray.Icon(title, img, title, menu)
        _manager.icon.on_click = lambda icon, button: _manager._on_click(button)
        _manager.is_visible = True
        _manager.is_running = True
        return {"status": "success", "message": "Tray icon created", "data": {"title": title, "visible": True}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def set_tray_tooltip(tooltip: str) -> Dict[str, Any]:
    """Update the tooltip text."""
    try:
        _manager.tooltip = tooltip
        if _manager.icon:
            try:
                _manager.icon.title = tooltip
            except AttributeError:
                pass  # Some backends don't support runtime tooltip updates
        return {"status": "success", "message": "Tooltip updated", "data": {"tooltip": tooltip}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def set_tray_icon(icon_path: str) -> Dict[str, Any]:
    """Change the tray icon at runtime."""
    try:
        if not os.path.exists(icon_path):
            return {"status": "error", "message": f"Icon not found: {icon_path}"}
        img = Image.open(icon_path)
        if _manager.icon:
            _manager.icon.icon = img
        return {"status": "success", "message": "Icon updated", "data": {"path": icon_path}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def add_menu_item(label: str, callback: Callable[..., Any] = None) -> Dict[str, Any]:
    """Add a standard menu item."""
    try:
        _manager.menu_items.append({
            "label": label, "callback": callback, "type": "item",
            "enabled": True, "checked": False
        })
        if _manager.icon and _manager.icon.menu:
            _manager.icon.menu = _manager._build_menu()
        return {"status": "success", "message": "Menu item added", "data": {"label": label}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def add_submenu(label: str, items: list) -> Dict[str, Any]:
    """Add a submenu with nested items."""
    try:
        _manager.menu_items.append({
            "label": label, "callback": None, "type": "submenu",
            "enabled": True, "submenu_items": items
        })
        if _manager.icon and _manager.icon.menu:
            _manager.icon.menu = _manager._build_menu()
        return {"status": "success", "message": "Submenu added", "data": {"label": label, "count": len(items)}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def add_separator() -> Dict[str, Any]:
    """Add a visual separator to the menu."""
    try:
        _manager.menu_items.append({"label": "separator", "type": "separator"})
        if _manager.icon and _manager.icon.menu:
            _manager.icon.menu = _manager._build_menu()
        return {"status": "success", "message": "Separator added"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def remove_menu_item(label: str) -> Dict[str, Any]:
    """Remove a menu item by label."""
    try:
        initial_len = len(_manager.menu_items)
        _manager.menu_items = [i for i in _manager.menu_items if i.get("label") != label]
        removed = len(_manager.menu_items) < initial_len
        if _manager.icon and _manager.icon.menu:
            _manager.icon.menu = _manager._build_menu()
        return {"status": "success", "message": "Item removed" if removed else "Item not found", "data": {"removed": removed}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def update_menu_item(label: str, new_label: str = "") -> Dict[str, Any]:
    """Update an existing menu item's label."""
    try:
        for item in _manager.menu_items:
            if item.get("label") == label:
                item["label"] = new_label
                if _manager.icon and _manager.icon.menu:
                    _manager.icon.menu = _manager._build_menu()
                return {"status": "success", "message": "Item updated", "data": {"old": label, "new": new_label}}
        return {"status": "error", "message": "Item not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def show_notification(title: str, message: str, timeout: int = 5) -> Dict[str, Any]:
    """Show a transient desktop notification using tkinter."""
    try:
        def _run_notification():
            root = tk.Tk()
            root.withdraw()
            win = tk.Toplevel(root)
            win.overrideredirect(True)
            win.attributes('-topmost', True)
            win.config(bg="#2c3e50")
            lbl_title = tk.Label(win, text=title, bg="#2c3e50", fg="#ecf0f1", font=("Segoe UI", 10, "bold"))
            lbl_msg = tk.Label(win, text=message, bg="#2c3e50", fg="#bdc3c7", font=("Segoe UI", 9), justify=tk.LEFT)
            lbl_title.pack(pady=(8, 2), padx=12, anchor="w")
            lbl_msg.pack(pady=(0, 8), padx=12, anchor="w")
            win.update_idletasks()
            w, h = win.winfo_width() + 4, win.winfo_height() + 4
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            win.geometry(f"{w}x{h}+{sw-w-20}+{sh-h-20}")
            win.after(int(timeout * 1000), win.destroy)
            root.mainloop()

        threading.Thread(target=_run_notification, daemon=True).start()
        return {"status": "success", "message": "Notification triggered", "data": {"title": title, "timeout": timeout}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def set_menu_checked(label: str, checked: bool) -> Dict[str, Any]:
    """Toggle checked state for a menu item."""
    try:
        updated = False
        for item in _manager.menu_items:
            if item.get("label") == label:
                item["checked"] = checked
                updated = True
        if _manager.icon and _manager.icon.menu:
            _manager.icon.menu = _manager._build_menu()
        return {"status": "success", "message": "State updated" if updated else "Item not found", "data": {"checked": checked}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def enable_menu_item(label: str, enabled: bool) -> Dict[str, Any]:
    """Enable or disable a menu item."""
    try:
        updated = False
        for item in _manager.menu_items:
            if item.get("label") == label:
                item["enabled"] = enabled
                updated = True
        if _manager.icon and _manager.icon.menu:
            _manager.icon.menu = _manager._build_menu()
        return {"status": "success", "message": "State updated" if updated else "Item not found", "data": {"enabled": enabled}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def create_icon_from_text(text: str, bg_color: str = "blue", fg_color: str = "white") -> Dict[str, Any]:
    """Generate a PIL icon from text."""
    try:
        img = Image.new("RGBA", (64, 64), bg_color)
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 32)
        except IOError:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((64 - w) / 2, (64 - h) / 2), text, fill=fg_color, font=font)
        
        fd, path = tempfile.mkstemp(suffix=".png", prefix="tray_text_icon_")
        os.close(fd)
        img.save(path)
        return {"status": "success", "message": "Text icon created", "data": {"path": path, "format": "PNG"}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def create_icon_from_color(color: str, size: Tuple[int, int] = (64, 64)) -> Dict[str, Any]:
    """Generate a solid-color PIL icon."""
    try:
        img = Image.new("RGBA", size, color)
        fd, path = tempfile.mkstemp(suffix=".png", prefix="tray_color_icon_")
        os.close(fd)
        img.save(path)
        return {"status": "success", "message": "Color icon created", "data": {"path": path, "size": size}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def show_tray() -> Dict[str, Any]:
    """Make tray icon visible."""
    try:
        _manager.is_visible = True
        if _manager.icon and not _manager.is_running:
            _manager.icon.run()
            _manager.is_running = True
        return {"status": "success", "message": "Tray shown", "data": {"visible": True}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def hide_tray() -> Dict[str, Any]:
    """Hide tray icon without destroying."""
    try:
        _manager.is_visible = False
        if _manager.icon:
            try:
                _manager.icon.remove()
            except Exception:
                pass
        return {"status": "success", "message": "Tray hidden", "data": {"visible": False}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def destroy_tray() -> Dict[str, Any]:
    """Cleanly stop and destroy the tray icon."""
    try:
        _manager._animation_stop_event.set()
        if _manager._click_timer:
            _manager._click_timer.cancel()
        if _manager.icon:
            try:
                _manager.icon.stop()
            except Exception:
                pass
        _manager.is_running = False
        _manager.is_visible = False
        _manager.icon = None
        return {"status": "success", "message": "Tray destroyed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_tray_status() -> Dict[str, Any]:
    """Return current state of the tray manager."""
    try:
        return {
            "status": "success",
            "data": {
                "running": _manager.is_running,
                "visible": _manager.is_visible,
                "tooltip": _manager.tooltip,
                "menu_items_count": len(_manager.menu_items),
                "animation_active": _manager._animation_thread is not None and _manager._animation_thread.is_alive()
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def set_click_callback(callback: Callable) -> Dict[str, Any]:
    """Set callback for single left-click."""
    try:
        _manager.click_callback = callback
        return {"status": "success", "message": "Single-click callback registered"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def set_double_click_callback(callback: Callable) -> Dict[str, Any]:
    """Set callback for double left-click detection."""
    try:
        _manager.double_click_callback = callback
        return {"status": "success", "message": "Double-click callback registered"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def animate_icon(frames: List[Image.Image], interval: float = 0.5) -> Dict[str, Any]:
    """Start continuous icon animation."""
    try:
        _manager._animation_stop_event.set()
        if _manager._animation_thread:
            _manager._animation_thread.join(timeout=2.0)
        _manager._animation_stop_event.clear()
        _manager._animation_thread = threading.Thread(
            target=_manager._animation_loop, args=(frames, interval), daemon=True
        )
        _manager._animation_thread.start()
        return {"status": "success", "message": "Animation started", "data": {"frames": len(frames), "interval": interval}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def stop_animation() -> Dict[str, Any]:
    """Stop ongoing icon animation."""
    try:
        _manager._animation_stop_event.set()
        if _manager._animation_thread:
            _manager._animation_thread.join(timeout=2.0)
            _manager._animation_thread = None
        return {"status": "success", "message": "Animation stopped"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def create_progress_icon(progress: float, color: str = "green") -> Dict[str, Any]:
    """Generate a circular progress indicator icon."""
    try:
        progress = max(0.0, min(1.0, progress))
        size = 64
        img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, size-4, size-4], fill="#e0e0e0")
        if progress > 0:
            draw.pieslice([4, 4, size-4, size-4], start=-90, end=(-90 + 360 * progress), fill=color)
        
        fd, path = tempfile.mkstemp(suffix=".png", prefix="tray_progress_")
        os.close(fd)
        img.save(path)
        return {"status": "success", "message": "Progress icon created", "data": {"path": path, "progress": progress}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def set_tray_visible(visible: bool) -> Dict[str, Any]:
    """Toggle tray visibility."""
    try:
        _manager.is_visible = visible
        if visible and _manager.icon and not _manager.is_running:
            _manager.icon.run()
            _manager.is_running = True
        elif not visible and _manager.icon:
            try:
                _manager.icon.remove()
            except Exception:
                pass
        return {"status": "success", "message": f"Tray visibility set to {visible}", "data": {"visible": visible}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_menu_items() -> Dict[str, Any]:
    """Return current menu configuration as JSON-serializable dict."""
    try:
        serializable = json.loads(json.dumps([{
            "label": i["label"], "type": i["type"],
            "enabled": i.get("enabled", True), "checked": i.get("checked", False)
        } for i in _manager.menu_items]))
        return {"status": "success", "data": {"items": serializable}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def run_tray_loop(blocking: bool = False) -> Dict[str, Any]:
    """Start the pystray event loop."""
    try:
        if not _manager.icon:
            return {"status": "error", "message": "Icon not initialized. Call create_tray_icon first."}
        
        if blocking:
            _manager.icon.run()
            return {"status": "success", "message": "Tray loop finished (blocking)"}
        else:
            if not _manager.is_running:
                _manager.is_running = True
                threading.Thread(target=_manager.icon.run, daemon=True).start()
            return {"status": "success", "message": "Tray loop started in background"}
    except Exception as e:
        _manager.is_running = False
        return {"status": "error", "message": str(e)}