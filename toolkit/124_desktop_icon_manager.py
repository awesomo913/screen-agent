#!/usr/bin/env python3
"""Desktop Icon Manager - Organize, resize, and automate desktop icon layouts."""

import pyautogui
import time
import json
import os
import argparse
import threading
import ctypes
import ctypes.wintypes
import subprocess
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont


@dataclass
class DesktopIcon:
    """Information about a desktop icon."""
    icon_id: str
    name: str
    x: int
    y: int
    width: int = 64
    height: int = 64
    file_path: str = ""
    icon_type: str = "file"
    shortcut_target: str = ""
    last_accessed: str = ""
    category: str = "general"
    hidden: bool = False


@dataclass
class IconLayout:
    """A saved desktop icon layout."""
    layout_id: str
    name: str
    icons: List[DesktopIcon] = field(default_factory=list)
    description: str = ""
    created_at: str = ""
    screen_width: int = 1920
    screen_height: int = 1080
    wallpaper: str = ""


@dataclass
class IconGrid:
    """Grid configuration for icon organization."""
    columns: int = 8
    rows: int = 6
    cell_width: int = 80
    cell_height: int = 80
    margin_left: int = 10
    margin_top: int = 10
    spacing_x: int = 10
    spacing_y: int = 10


class DesktopController:
    """Controls desktop icon operations using Win32 API."""

    def __init__(self):
        self._user32 = ctypes.windll.user32 if os.name == 'nt' else None

    def get_desktop_hwnd(self) -> int:
        if not self._user32:
            return 0
        try:
            progman = self._user32.FindWindowW("Progman", None)
            if progman:
                return progman
            desktop = self._user32.GetDesktopWindow()
            return desktop
        except Exception:
            return 0

    def get_icons(self) -> List[DesktopIcon]:
        icons = []
        if os.name == 'nt':
            icons = self._get_windows_icons()
        elif os.name == 'posix':
            icons = self._get_linux_icons()
        return icons

    def _get_windows_icons(self) -> List[DesktopIcon]:
        desktop_paths = [
            os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
            os.path.join(os.environ.get('PUBLIC', r'C:\Users\Public'), 'Desktop')
        ]
        icons = []
        for desktop_path in desktop_paths:
            if not os.path.exists(desktop_path):
                continue
            for item in os.listdir(desktop_path):
                full_path = os.path.join(desktop_path, item)
                iid = f"icon_{len(icons)}"
                icons.append(DesktopIcon(
                    icon_id=iid,
                    name=os.path.splitext(item)[0],
                    x=0, y=0,
                    file_path=full_path,
                    icon_type='shortcut' if item.endswith('.lnk') else 'file'
                ))
        return icons

    def _get_linux_icons(self) -> List[DesktopIcon]:
        desktop_path = os.path.expanduser("~/Desktop")
        icons = []
        if os.path.exists(desktop_path):
            for item in os.listdir(desktop_path):
                full_path = os.path.join(desktop_path, item)
                iid = f"icon_{len(icons)}"
                icons.append(DesktopIcon(
                    icon_id=iid,
                    name=os.path.splitext(item)[0],
                    x=0, y=0,
                    file_path=full_path,
                    icon_type='file'
                ))
        return icons

    def create_shortcut(self, name: str, target: str,
                         desktop_x: int = 0, desktop_y: int = 0) -> bool:
        if os.name != 'nt':
            return False
        try:
            desktop = os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop')
            shortcut_path = os.path.join(desktop, f"{name}.lnk")
            script = f'''
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut("{shortcut_path}")
$lnk.TargetPath = "{target}"
$lnk.Save()
'''
            result = subprocess.run(['powershell', '-Command', script],
                                    capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            print(f"Shortcut creation error: {e}")
            return False

    def hide_all_icons(self):
        try:
            if os.name == 'nt':
                hwnd = self._user32.FindWindowW("SHELLDLL_DefView", None)
                if hwnd:
                    self._user32.SendMessageW(hwnd, 0x0111, 0x7402, 0)
                    print("Desktop icons hidden")
        except Exception as e:
            print(f"Error hiding icons: {e}")

    def show_all_icons(self):
        try:
            if os.name == 'nt':
                hwnd = self._user32.FindWindowW("SHELLDLL_DefView", None)
                if hwnd:
                    self._user32.SendMessageW(hwnd, 0x0111, 0x7402, 0)
                    print("Desktop icons shown")
        except Exception as e:
            print(f"Error showing icons: {e}")

    def auto_arrange_icons(self):
        try:
            if os.name == 'nt':
                hwnd = self._user32.FindWindowW("SHELLDLL_DefView", None)
                if hwnd:
                    self._user32.SendMessageW(hwnd, 0x0111, 0x7402, 0)
                    print("Auto-arranged icons")
        except Exception as e:
            print(f"Error auto-arranging: {e}")

    def right_click_desktop(self):
        screen_w, screen_h = pyautogui.size()
        pyautogui.rightClick(screen_w // 2, screen_h // 2)
        time.sleep(0.3)


class IconLayoutManager:
    """Manages icon layouts and organization."""

    def __init__(self, controller: DesktopController):
        self.controller = controller

    def capture_layout(self, name: str) -> IconLayout:
        icons = self.controller.get_icons()
        screen_w, screen_h = pyautogui.size()
        lid = f"layout_{int(time.time())}"
        layout = IconLayout(
            layout_id=lid, name=name,
            icons=icons,
            created_at=datetime.now().isoformat(),
            screen_width=screen_w,
            screen_height=screen_h
        )
        print(f"Layout captured: {name} ({len(icons)} icons)")
        return layout

    def organize_grid(self, icons: List[DesktopIcon],
                       grid: IconGrid) -> List[DesktopIcon]:
        positioned = []
        for i, icon in enumerate(icons):
            col = i % grid.columns
            row = i // grid.columns
            if row >= grid.rows:
                break
            icon.x = grid.margin_left + col * (grid.cell_width + grid.spacing_x)
            icon.y = grid.margin_top + row * (grid.cell_height + grid.spacing_y)
            positioned.append(icon)
        return positioned

    def organize_by_type(self, icons: List[DesktopIcon]) -> Dict[str, List[DesktopIcon]]:
        grouped: Dict[str, List[DesktopIcon]] = {}
        for icon in icons:
            ext = Path(icon.file_path).suffix.lower() if icon.file_path else ''
            if icon.icon_type == 'shortcut' or ext == '.lnk':
                group = 'shortcuts'
            elif ext in ['.exe', '.msi', '.app']:
                group = 'applications'
            elif ext in ['.txt', '.doc', '.docx', '.pdf', '.xls', '.xlsx']:
                group = 'documents'
            elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg']:
                group = 'images'
            elif ext in ['.mp4', '.avi', '.mkv', '.mov', '.mp3', '.wav']:
                group = 'media'
            elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
                group = 'archives'
            elif ext in ['.py', '.js', '.html', '.css', '.java', '.cpp', '.h']:
                group = 'code'
            else:
                group = 'other'
            grouped.setdefault(group, []).append(icon)
        return grouped


class IconVisualizer:
    """Creates visual maps of desktop icon layouts."""

    def visualize_layout(self, layout: IconLayout,
                          output: Optional[str] = None) -> str:
        sw = min(layout.screen_width, 1200)
        sh = min(layout.screen_height, 800)
        scale_x = sw / max(layout.screen_width, 1)
        scale_y = sh / max(layout.screen_height, 1)

        img = Image.new('RGB', (sw, sh), (40, 40, 60))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("arial.ttf", 9)
        except Exception:
            font = ImageFont.load_default()

        type_colors = {
            'shortcut': (100, 180, 255),
            'file': (150, 255, 150),
            'folder': (255, 220, 80),
            'applications': (255, 120, 120),
            'other': (200, 200, 200)
        }

        for icon in layout.icons:
            x = int(icon.x * scale_x)
            y = int(icon.y * scale_y)
            w = int(icon.width * scale_x)
            h = int(icon.height * scale_y)
            w = max(w, 20)
            h = max(h, 20)
            color = type_colors.get(icon.icon_type, (180, 180, 180))
            draw.rectangle([x, y, x+w, y+h], fill=color, outline=(255, 255, 255))
            name = icon.name[:8]
            draw.text((x+2, y+2), name, fill=(0, 0, 0), font=font)

        title = f"Desktop Layout: {layout.name} | {len(layout.icons)} icons"
        draw.text((10, sh - 20), title, fill=(200, 200, 200), font=font)

        if not output:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = f"desktop_layout_{ts}.png"
        img.save(output)
        print(f"Layout visualization: {output}")
        return output

    def screenshot_desktop(self, output: Optional[str] = None) -> str:
        ss = pyautogui.screenshot()
        if not output:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = f"desktop_screenshot_{ts}.png"
        ss.save(output)
        print(f"Desktop screenshot: {output}")
        return output


class DesktopIconManager:
    """Main desktop icon management application."""

    def __init__(self, data_dir: str = "icon_manager_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.layouts: Dict[str, IconLayout] = {}
        self.controller = DesktopController()
        self.layout_manager = IconLayoutManager(self.controller)
        self.visualizer = IconVisualizer()
        self._load_layouts()

    def _load_layouts(self):
        lf = self.data_dir / "layouts.json"
        if lf.exists():
            try:
                with open(lf, 'r') as f:
                    data = json.load(f)
                for lid, ldata in data.items():
                    icons = [DesktopIcon(**i) for i in ldata.pop('icons', [])]
                    layout = IconLayout(**ldata)
                    layout.icons = icons
                    self.layouts[lid] = layout
                print(f"Loaded {len(self.layouts)} desktop layouts")
            except Exception as e:
                print(f"Error loading layouts: {e}")

    def _save_layouts(self):
        lf = self.data_dir / "layouts.json"
        data = {}
        for lid, layout in self.layouts.items():
            d = asdict(layout)
            data[lid] = d
        with open(lf, 'w') as f:
            json.dump(data, f, indent=2)

    def save_current_layout(self, name: str) -> IconLayout:
        layout = self.layout_manager.capture_layout(name)
        self.layouts[layout.layout_id] = layout
        self._save_layouts()
        return layout

    def organize_grid(self, cols: int = 8, rows: int = 6):
        icons = self.controller.get_icons()
        grid = IconGrid(columns=cols, rows=rows)
        positioned = self.layout_manager.organize_grid(icons, grid)
        print(f"Grid organization: {len(positioned)} icons positioned in {cols}x{rows} grid")
        for icon in positioned:
            print(f"  {icon.name}: ({icon.x}, {icon.y})")

    def organize_by_type(self):
        icons = self.controller.get_icons()
        grouped = self.layout_manager.organize_by_type(icons)
        print("Icons organized by type:")
        for group, items in sorted(grouped.items()):
            print(f"  {group}: {len(items)} icons")
            for item in items:
                print(f"    - {item.name}")

    def visualize(self, layout_id: Optional[str] = None,
                   output: Optional[str] = None) -> str:
        if layout_id and layout_id in self.layouts:
            layout = self.layouts[layout_id]
        else:
            layout = self.layout_manager.capture_layout("current")
        if not output:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = str(self.data_dir / f"desktop_{ts}.png")
        return self.visualizer.visualize_layout(layout, output=output)

    def screenshot(self, output: Optional[str] = None) -> str:
        if not output:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = str(self.data_dir / f"desktop_ss_{ts}.png")
        return self.visualizer.screenshot_desktop(output=output)

    def create_shortcut(self, name: str, target: str):
        success = self.controller.create_shortcut(name, target)
        print(f"Shortcut {'created' if success else 'failed'}: {name} -> {target}")

    def hide_icons(self):
        self.controller.hide_all_icons()

    def show_icons(self):
        self.controller.show_all_icons()

    def auto_arrange(self):
        self.controller.auto_arrange_icons()

    def list_icons(self):
        icons = self.controller.get_icons()
        print(f"Desktop Icons ({len(icons)}):")
        for icon in icons:
            print(f"  {icon.name}")
            if icon.file_path:
                print(f"    {icon.file_path}")

    def list_layouts(self):
        if not self.layouts:
            print("No saved layouts.")
            return
        print(f"Saved Layouts ({len(self.layouts)}):")
        for lid, layout in self.layouts.items():
            print(f"  [{lid}] {layout.name} ({len(layout.icons)} icons) - {layout.created_at[:19]}")

    def delete_layout(self, layout_id: str):
        if layout_id in self.layouts:
            del self.layouts[layout_id]
            self._save_layouts()
            print(f"Layout deleted: {layout_id}")


def main():
    parser = argparse.ArgumentParser(description='Desktop Icon Manager')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    subparsers.add_parser('list-icons', help='List desktop icons')

    save_p = subparsers.add_parser('save', help='Save current layout')
    save_p.add_argument('name', help='Layout name')

    subparsers.add_parser('list-layouts', help='List saved layouts')

    grid_p = subparsers.add_parser('grid', help='Organize icons in grid')
    grid_p.add_argument('--cols', type=int, default=8)
    grid_p.add_argument('--rows', type=int, default=6)

    subparsers.add_parser('by-type', help='Organize icons by file type')

    vis_p = subparsers.add_parser('visualize', help='Visualize icon layout')
    vis_p.add_argument('--layout', help='Layout ID (current if not specified)')
    vis_p.add_argument('--output', help='Output path')

    subparsers.add_parser('screenshot', help='Take desktop screenshot')

    sc_p = subparsers.add_parser('shortcut', help='Create desktop shortcut')
    sc_p.add_argument('name', help='Shortcut name')
    sc_p.add_argument('target', help='Target path')

    subparsers.add_parser('hide', help='Hide all desktop icons')
    subparsers.add_parser('show', help='Show all desktop icons')
    subparsers.add_parser('auto-arrange', help='Auto-arrange icons')

    del_p = subparsers.add_parser('delete', help='Delete saved layout')
    del_p.add_argument('layout_id', help='Layout ID')

    args = parser.parse_args()
    mgr = DesktopIconManager()

    if args.command == 'list-icons':
        mgr.list_icons()
    elif args.command == 'save':
        mgr.save_current_layout(args.name)
    elif args.command == 'list-layouts':
        mgr.list_layouts()
    elif args.command == 'grid':
        mgr.organize_grid(cols=args.cols, rows=args.rows)
    elif args.command == 'by-type':
        mgr.organize_by_type()
    elif args.command == 'visualize':
        mgr.visualize(layout_id=args.layout, output=args.output)
    elif args.command == 'screenshot':
        mgr.screenshot()
    elif args.command == 'shortcut':
        mgr.create_shortcut(args.name, args.target)
    elif args.command == 'hide':
        mgr.hide_icons()
    elif args.command == 'show':
        mgr.show_icons()
    elif args.command == 'auto-arrange':
        mgr.auto_arrange()
    elif args.command == 'delete':
        mgr.delete_layout(args.layout_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
