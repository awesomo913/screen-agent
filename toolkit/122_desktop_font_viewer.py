#!/usr/bin/env python3
"""Desktop Font Viewer - Browse, preview, and manage system fonts on-screen."""

import pyautogui
import time
import json
import os
import argparse
import threading
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import subprocess


@dataclass
class FontInfo:
    """Information about a system font."""
    font_path: str
    family: str
    style: str = "Regular"
    weight: str = "400"
    italic: bool = False
    bold: bool = False
    monospace: bool = False
    tags: List[str] = field(default_factory=list)
    favorite: bool = False
    preview_text: str = "The quick brown fox jumps over the lazy dog"
    added_at: str = ""


@dataclass
class FontCollection:
    """A named collection of fonts."""
    collection_id: str
    name: str
    font_paths: List[str] = field(default_factory=list)
    description: str = ""
    created_at: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class FontPreviewConfig:
    """Configuration for font preview generation."""
    text: str = "AaBbCcDd 0123 !@#$"
    font_size: int = 32
    bg_color: Tuple[int, int, int] = (255, 255, 255)
    fg_color: Tuple[int, int, int] = (0, 0, 0)
    image_width: int = 600
    image_height: int = 80
    padding: int = 10
    show_name: bool = True


class SystemFontScanner:
    """Scans system for installed fonts."""

    FONT_DIRS_WINDOWS = [
        "C:\Windows\Fonts",
        os.path.expanduser("~\AppData\Local\Microsoft\Windows\Fonts")
    ]
    FONT_DIRS_LINUX = [
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        os.path.expanduser("~/.fonts"),
        os.path.expanduser("~/.local/share/fonts")
    ]
    FONT_DIRS_MAC = [
        "/Library/Fonts",
        "/System/Library/Fonts",
        os.path.expanduser("~/Library/Fonts")
    ]

    def get_font_dirs(self) -> List[str]:
        if os.name == 'nt':
            return self.FONT_DIRS_WINDOWS
        elif os.uname().sysname == 'Darwin':
            return self.FONT_DIRS_MAC
        else:
            return self.FONT_DIRS_LINUX

    def scan_fonts(self) -> List[FontInfo]:
        fonts = []
        extensions = {'.ttf', '.otf', '.ttc', '.woff', '.woff2'}
        seen_families = set()

        for font_dir in self.get_font_dirs():
            dir_path = Path(font_dir)
            if not dir_path.exists():
                continue
            for font_file in dir_path.rglob("*"):
                if font_file.suffix.lower() not in extensions:
                    continue
                try:
                    family, style = self._get_font_info(str(font_file))
                    is_bold = any(w in style.lower() for w in ['bold', 'heavy', 'black', 'demi'])
                    is_italic = any(w in style.lower() for w in ['italic', 'oblique', 'slant'])
                    is_mono = any(w in family.lower() for w in
                                  ['mono', 'console', 'code', 'courier', 'typewriter',
                                   'terminal', 'fixed'])
                    font_info = FontInfo(
                        font_path=str(font_file),
                        family=family,
                        style=style,
                        bold=is_bold,
                        italic=is_italic,
                        monospace=is_mono,
                        added_at=datetime.now().isoformat()
                    )
                    fonts.append(font_info)
                except Exception:
                    pass

        print(f"Found {len(fonts)} fonts in {len(self.get_font_dirs())} directories")
        return fonts

    def _get_font_info(self, font_path: str) -> Tuple[str, str]:
        try:
            from PIL import ImageFont as PILFont
            font = PILFont.truetype(font_path, 12)
            if hasattr(font, 'getname'):
                family, style = font.getname()
                return family or Path(font_path).stem, style or "Regular"
        except Exception:
            pass
        name = Path(font_path).stem
        parts = name.replace('-', ' ').replace('_', ' ').split()
        style_words = ['bold', 'italic', 'light', 'regular', 'medium', 'thin',
                       'black', 'heavy', 'condensed', 'expanded', 'oblique']
        style_parts = []
        family_parts = []
        for part in parts:
            if part.lower() in style_words:
                style_parts.append(part)
            else:
                family_parts.append(part)
        family = ' '.join(family_parts) or name
        style = ' '.join(style_parts) or "Regular"
        return family, style


class FontPreviewer:
    """Generates font preview images."""

    def __init__(self, config: Optional[FontPreviewConfig] = None):
        self.config = config or FontPreviewConfig()

    def generate_preview(self, font_info: FontInfo,
                          output_path: Optional[str] = None,
                          config: Optional[FontPreviewConfig] = None) -> Optional[str]:
        cfg = config or self.config
        try:
            img = Image.new('RGB',
                            (cfg.image_width, cfg.image_height),
                            cfg.bg_color)
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype(font_info.font_path, cfg.font_size)
            except Exception:
                try:
                    font = ImageFont.load_default()
                except Exception:
                    return None

            if cfg.show_name:
                try:
                    name_font = ImageFont.truetype(font_info.font_path,
                                                    max(10, cfg.font_size // 3))
                    name_text = f"{font_info.family} {font_info.style}"
                    draw.text((cfg.padding, cfg.padding), name_text,
                              fill=(150, 150, 150), font=name_font)
                    text_y = cfg.padding + cfg.font_size // 2
                except Exception:
                    text_y = cfg.padding
            else:
                text_y = cfg.padding

            draw.text((cfg.padding, text_y), cfg.text,
                      fill=cfg.fg_color, font=font)

            if not output_path:
                safe_name = font_info.family.replace(' ', '_').replace('/', '_')
                output_path = f"preview_{safe_name}_{font_info.style}.png"

            img.save(output_path)
            return output_path
        except Exception as e:
            print(f"Preview error for {font_info.family}: {e}")
            return None

    def generate_comparison(self, fonts: List[FontInfo],
                             text: str = "Sample Text 123",
                             font_size: int = 24,
                             output_path: Optional[str] = None) -> Optional[str]:
        if not fonts:
            return None
        row_height = font_size + 20
        label_width = 200
        text_width = 500
        total_width = label_width + text_width + 20
        total_height = row_height * len(fonts) + 60

        img = Image.new('RGB', (total_width, total_height), (245, 245, 245))
        draw = ImageDraw.Draw(img)

        try:
            label_font = ImageFont.truetype("arial.ttf", 11)
        except Exception:
            label_font = ImageFont.load_default()

        draw.text((10, 15), f"Font Comparison - '{text}'",
                  fill=(50, 50, 50), font=label_font)
        draw.line([(0, 40), (total_width, 40)], fill=(200, 200, 200))

        for i, font_info in enumerate(fonts):
            y = 50 + i * row_height
            bg = (255, 255, 255) if i % 2 == 0 else (248, 248, 248)
            draw.rectangle([0, y, total_width, y + row_height], fill=bg)
            name_text = f"{font_info.family[:25]} {font_info.style[:10]}"
            draw.text((10, y + 5), name_text, fill=(80, 80, 80), font=label_font)
            try:
                preview_font = ImageFont.truetype(font_info.font_path, font_size)
                draw.text((label_width + 10, y + 3), text,
                          fill=(0, 0, 0), font=preview_font)
            except Exception:
                draw.text((label_width + 10, y + 3), text,
                          fill=(180, 180, 180), font=label_font)

        if not output_path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"font_comparison_{ts}.png"
        img.save(output_path)
        print(f"Comparison saved: {output_path}")
        return output_path

    def generate_alphabet_sheet(self, font_info: FontInfo,
                                  output_path: Optional[str] = None) -> Optional[str]:
        chars = ("ABCDEFGHIJKLMNOPQRSTUVWXYZ\n"
                 "abcdefghijklmnopqrstuvwxyz\n"
                 "0123456789\n"
                 "!@#$%^&*()_+-=[]{}|;':\",./<>?")
        try:
            img = Image.new('RGB', (900, 350), (255, 255, 255))
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype(font_info.font_path, 28)
                small_font = ImageFont.truetype(font_info.font_path, 14)
            except Exception:
                font = ImageFont.load_default()
                small_font = font

            title = f"{font_info.family} {font_info.style} - Alphabet Sheet"
            draw.text((10, 10), title, fill=(50, 50, 50), font=small_font)
            draw.line([(0, 35), (900, 35)], fill=(200, 200, 200))

            y = 45
            for line in chars.split('\n'):
                draw.text((10, y), line, fill=(0, 0, 0), font=font)
                y += 70

            if not output_path:
                safe_name = font_info.family.replace(' ', '_')
                output_path = f"alphabet_{safe_name}.png"
            img.save(output_path)
            return output_path
        except Exception as e:
            print(f"Alphabet sheet error: {e}")
            return None


class DesktopFontViewer:
    """Main font viewer and manager application."""

    def __init__(self, data_dir: str = "font_viewer_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.previews_dir = self.data_dir / "previews"
        self.previews_dir.mkdir(exist_ok=True)
        self.fonts: Dict[str, FontInfo] = {}
        self.collections: Dict[str, FontCollection] = {}
        self.scanner = SystemFontScanner()
        self.previewer = FontPreviewer()
        self._load_data()

    def _load_data(self):
        df = self.data_dir / "fonts.json"
        if df.exists():
            try:
                with open(df, 'r') as f:
                    data = json.load(f)
                for fp, fdata in data.get('fonts', {}).items():
                    self.fonts[fp] = FontInfo(**fdata)
                for cid, cdata in data.get('collections', {}).items():
                    self.collections[cid] = FontCollection(**cdata)
                print(f"Loaded {len(self.fonts)} fonts, {len(self.collections)} collections")
            except Exception as e:
                print(f"Error loading data: {e}")

    def _save_data(self):
        df = self.data_dir / "fonts.json"
        data = {
            'fonts': {fp: asdict(f) for fp, f in self.fonts.items()},
            'collections': {cid: asdict(c) for cid, c in self.collections.items()}
        }
        with open(df, 'w') as f:
            json.dump(data, f, indent=2)

    def scan_system(self) -> int:
        fonts = self.scanner.scan_fonts()
        for font in fonts:
            self.fonts[font.font_path] = font
        self._save_data()
        return len(fonts)

    def search_fonts(self, query: str, style_filter: str = "",
                      mono_only: bool = False) -> List[FontInfo]:
        query_lower = query.lower()
        results = []
        for font in self.fonts.values():
            if query_lower and query_lower not in font.family.lower():
                if query_lower not in font.style.lower():
                    if not any(query_lower in t.lower() for t in font.tags):
                        continue
            if style_filter and style_filter.lower() not in font.style.lower():
                continue
            if mono_only and not font.monospace:
                continue
            results.append(font)
        return sorted(results, key=lambda f: f.family)

    def preview_font(self, font_path: str, text: str = "",
                      size: int = 36) -> Optional[str]:
        if font_path not in self.fonts:
            font_info = FontInfo(font_path=font_path,
                                  family=Path(font_path).stem,
                                  style="Regular")
        else:
            font_info = self.fonts[font_path]
        if text:
            font_info.preview_text = text
        safe = font_info.family.replace(' ', '_').replace('/', '_')
        output = str(self.previews_dir / f"preview_{safe}.png")
        cfg = FontPreviewConfig(text=text or font_info.preview_text,
                                 font_size=size)
        return self.previewer.generate_preview(font_info, output_path=output, config=cfg)

    def compare_fonts(self, font_paths: List[str], text: str = "Sample 123",
                       output: Optional[str] = None) -> Optional[str]:
        fonts = [self.fonts.get(fp,
                                  FontInfo(font_path=fp, family=Path(fp).stem, style=""))
                 for fp in font_paths]
        if not output:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = str(self.previews_dir / f"comparison_{ts}.png")
        return self.previewer.generate_comparison(fonts, text=text, output_path=output)

    def generate_sheet(self, font_path: str) -> Optional[str]:
        if font_path not in self.fonts:
            font_info = FontInfo(font_path=font_path,
                                  family=Path(font_path).stem, style="")
        else:
            font_info = self.fonts[font_path]
        safe = font_info.family.replace(' ', '_')
        output = str(self.previews_dir / f"sheet_{safe}.png")
        return self.previewer.generate_alphabet_sheet(font_info, output_path=output)

    def create_collection(self, name: str, font_paths: List[str],
                           description: str = "") -> FontCollection:
        cid = f"col_{int(time.time())}"
        col = FontCollection(
            collection_id=cid, name=name, font_paths=font_paths,
            description=description, created_at=datetime.now().isoformat()
        )
        self.collections[cid] = col
        self._save_data()
        print(f"Collection created: {name} ({len(font_paths)} fonts)")
        return col

    def toggle_favorite(self, font_path: str):
        if font_path in self.fonts:
            self.fonts[font_path].favorite = not self.fonts[font_path].favorite
            self._save_data()
            state = "favorited" if self.fonts[font_path].favorite else "unfavorited"
            print(f"{state}: {self.fonts[font_path].family}")

    def list_fonts(self, query: str = "", mono_only: bool = False,
                    favorites_only: bool = False, limit: int = 50):
        fonts = list(self.fonts.values())
        if query:
            fonts = self.search_fonts(query, mono_only=mono_only)
        elif mono_only:
            fonts = [f for f in fonts if f.monospace]
        if favorites_only:
            fonts = [f for f in fonts if f.favorite]
        fonts = sorted(fonts, key=lambda f: f.family)[:limit]
        print(f"Fonts ({len(fonts)}):")
        for f in fonts:
            tags = []
            if f.bold:
                tags.append("bold")
            if f.italic:
                tags.append("italic")
            if f.monospace:
                tags.append("mono")
            if f.favorite:
                tags.append("★")
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            print(f"  {f.family} {f.style}{tag_str}")
            print(f"    {f.font_path}")


def main():
    parser = argparse.ArgumentParser(description='Desktop Font Viewer')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    subparsers.add_parser('scan', help='Scan system for fonts')

    list_p = subparsers.add_parser('list', help='List fonts')
    list_p.add_argument('--query', default='', help='Search query')
    list_p.add_argument('--mono', action='store_true', help='Monospace only')
    list_p.add_argument('--favorites', action='store_true')
    list_p.add_argument('--limit', type=int, default=50)

    prev_p = subparsers.add_parser('preview', help='Preview a font')
    prev_p.add_argument('font_path', help='Path to font file')
    prev_p.add_argument('--text', default='', help='Preview text')
    prev_p.add_argument('--size', type=int, default=36)

    cmp_p = subparsers.add_parser('compare', help='Compare multiple fonts')
    cmp_p.add_argument('fonts', nargs='+', help='Font file paths')
    cmp_p.add_argument('--text', default='Sample Text 123')
    cmp_p.add_argument('--output', help='Output path')

    sheet_p = subparsers.add_parser('sheet', help='Generate alphabet sheet')
    sheet_p.add_argument('font_path', help='Font file path')

    fav_p = subparsers.add_parser('favorite', help='Toggle favorite')
    fav_p.add_argument('font_path', help='Font file path')

    col_p = subparsers.add_parser('collection', help='Create font collection')
    col_p.add_argument('name', help='Collection name')
    col_p.add_argument('fonts', nargs='+', help='Font file paths')

    args = parser.parse_args()
    viewer = DesktopFontViewer()

    if args.command == 'scan':
        count = viewer.scan_system()
        print(f"Scan complete: {count} fonts found")
    elif args.command == 'list':
        viewer.list_fonts(query=args.query, mono_only=args.mono,
                          favorites_only=args.favorites, limit=args.limit)
    elif args.command == 'preview':
        path = viewer.preview_font(args.font_path, text=args.text, size=args.size)
        if path:
            print(f"Preview: {path}")
    elif args.command == 'compare':
        path = viewer.compare_fonts(args.fonts, text=args.text, output=args.output)
        if path:
            print(f"Comparison: {path}")
    elif args.command == 'sheet':
        path = viewer.generate_sheet(args.font_path)
        if path:
            print(f"Sheet: {path}")
    elif args.command == 'favorite':
        viewer.toggle_favorite(args.font_path)
    elif args.command == 'collection':
        viewer.create_collection(args.name, args.fonts)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
