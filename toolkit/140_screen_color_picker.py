#!/usr/bin/env python3
"""
140_screen_color_picker.py
Screen-control color picker: captures pixel/region colors from screen,
builds palettes, converts formats, and shows a floating color inspector.
"""

import pyautogui
import argparse
import time
import os
import re
import json
import threading
import logging
import colorsys
from PIL import Image, ImageGrab, ImageDraw, ImageFont
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path
import win32gui
import win32con
import win32api
import tkinter as tk
from tkinter import ttk
from pynput import keyboard as pynput_kb
from pynput import mouse as pynput_m

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

DATA_DIR = Path.home() / "ColorPickerData"
DATA_DIR.mkdir(exist_ok=True)

@dataclass
class ColorSample:
    r: int
    g: int
    b: int
    x: int = 0
    y: int = 0
    label: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    sample_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S%f"))

    @property
    def hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}".upper()

    @property
    def hsl(self) -> Tuple[float, float, float]:
        h, l, s = colorsys.rgb_to_hls(self.r/255, self.g/255, self.b/255)
        return (h*360, s*100, l*100)

    @property
    def hsv(self) -> Tuple[float, float, float]:
        h, s, v = colorsys.rgb_to_hsv(self.r/255, self.g/255, self.b/255)
        return (h*360, s*100, v*100)

    @property
    def cmyk(self) -> Tuple[float, float, float, float]:
        r, g, b = self.r/255, self.g/255, self.b/255
        k = 1 - max(r, g, b)
        if k == 1:
            return (0, 0, 0, 100)
        c = (1 - r - k) / (1 - k) * 100
        m = (1 - g - k) / (1 - k) * 100
        y = (1 - b - k) / (1 - k) * 100
        return (c, m, y, k * 100)

    @property
    def css_rgb(self) -> str:
        return f"rgb({self.r}, {self.g}, {self.b})"

    @property
    def css_hsl(self) -> str:
        h, s, l = self.hsl
        return f"hsl({h:.0f}, {s:.0f}%, {l:.0f}%)"

    @property
    def name(self) -> str:
        return self._find_nearest_name()

    def _find_nearest_name(self) -> str:
        NAMED_COLORS = {
            "Red": (255,0,0), "Green": (0,128,0), "Blue": (0,0,255),
            "White": (255,255,255), "Black": (0,0,0), "Yellow": (255,255,0),
            "Cyan": (0,255,255), "Magenta": (255,0,255), "Orange": (255,165,0),
            "Pink": (255,192,203), "Purple": (128,0,128), "Brown": (139,69,19),
            "Gray": (128,128,128), "Navy": (0,0,128), "Lime": (0,255,0),
            "Teal": (0,128,128), "Maroon": (128,0,0), "Olive": (128,128,0),
            "Silver": (192,192,192), "Gold": (255,215,0), "Indigo": (75,0,130),
            "Violet": (238,130,238), "Coral": (255,127,80), "Salmon": (250,128,114),
            "Beige": (245,245,220), "Ivory": (255,255,240), "Crimson": (220,20,60)
        }
        best_name = "Unknown"
        best_dist = float('inf')
        for cname, (cr, cg, cb) in NAMED_COLORS.items():
            dist = ((self.r-cr)**2 + (self.g-cg)**2 + (self.b-cb)**2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_name = cname
        return best_name

@dataclass
class ColorPalette:
    palette_id: str
    name: str
    colors: List[ColorSample]
    description: str = ""
    created: str = field(default_factory=lambda: datetime.now().isoformat())

class ScreenColorExtractor:
    def get_pixel(self, x: int, y: int) -> ColorSample:
        img = ImageGrab.grab(bbox=(x, y, x+1, y+1))
        r, g, b = img.getpixel((0, 0))[:3]
        return ColorSample(r=r, g=g, b=b, x=x, y=y)

    def get_cursor_pixel(self) -> ColorSample:
        x, y = pyautogui.position()
        return self.get_pixel(x, y)

    def get_region_dominant(self, x: int, y: int, w: int, h: int,
                             count: int = 5) -> List[ColorSample]:
        img = ImageGrab.grab(bbox=(x, y, x+w, y+h))
        img_small = img.resize((max(1, w//4), max(1, h//4)), Image.LANCZOS)
        img_rgb = img_small.convert('RGB')
        pixels = list(img_rgb.getdata())
        freq: Dict[Tuple,int] = {}
        for p in pixels:
            r, g, b = p[0]//16*16, p[1]//16*16, p[2]//16*16
            freq[(r,g,b)] = freq.get((r,g,b), 0) + 1
        sorted_colors = sorted(freq.items(), key=lambda x: -x[1])
        samples = []
        for (r,g,b), _ in sorted_colors[:count]:
            samples.append(ColorSample(r=r, g=g, b=b, x=x, y=y))
        return samples

    def get_region_average(self, x: int, y: int, w: int, h: int) -> ColorSample:
        img = ImageGrab.grab(bbox=(x, y, x+w, y+h))
        img_rgb = img.convert('RGB')
        pixels = list(img_rgb.getdata())
        n = len(pixels)
        if not n:
            return ColorSample(0, 0, 0, x, y)
        r = sum(p[0] for p in pixels) // n
        g = sum(p[1] for p in pixels) // n
        b = sum(p[2] for p in pixels) // n
        return ColorSample(r=r, g=g, b=b, x=x, y=y)

    def extract_palette_from_screenshot(self, count: int = 8) -> List[ColorSample]:
        img = ImageGrab.grab()
        img_small = img.resize((320, 180), Image.LANCZOS).convert('RGB')
        pixels = list(img_small.getdata())
        freq: Dict[Tuple,int] = {}
        for p in pixels:
            r, g, b = p[0]//32*32, p[1]//32*32, p[2]//32*32
            freq[(r,g,b)] = freq.get((r,g,b), 0) + 1
        sorted_colors = sorted(freq.items(), key=lambda x: -x[1])
        samples = []
        for (r,g,b), _ in sorted_colors:
            if len(samples) >= count:
                break
            too_close = False
            for s in samples:
                dist = ((s.r-r)**2 + (s.g-g)**2 + (s.b-b)**2)**0.5
                if dist < 60:
                    too_close = True
                    break
            if not too_close:
                samples.append(ColorSample(r=r, g=g, b=b))
        return samples[:count]

class ColorConverter:
    def hex_to_rgb(self, hex_str: str) -> Tuple[int,int,int]:
        h = hex_str.lstrip('#')
        if len(h) == 3:
            h = ''.join(c*2 for c in h)
        return int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)

    def rgb_to_hex(self, r: int, g: int, b: int) -> str:
        return f"#{r:02X}{g:02X}{b:02X}"

    def rgb_to_hsl(self, r: int, g: int, b: int) -> Tuple[float,float,float]:
        h, l, s = colorsys.rgb_to_hls(r/255, g/255, b/255)
        return (h*360, s*100, l*100)

    def hsl_to_rgb(self, h: float, s: float, l: float) -> Tuple[int,int,int]:
        r, g, b = colorsys.hls_to_rgb(h/360, l/100, s/100)
        return (int(r*255), int(g*255), int(b*255))

    def complementary(self, r: int, g: int, b: int) -> Tuple[int,int,int]:
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        h2 = (h + 0.5) % 1.0
        r2, g2, b2 = colorsys.hsv_to_rgb(h2, s, v)
        return (int(r2*255), int(g2*255), int(b2*255))

    def triadic(self, r: int, g: int, b: int) -> List[Tuple[int,int,int]]:
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        results = []
        for offset in [1/3, 2/3]:
            h2 = (h + offset) % 1.0
            r2, g2, b2 = colorsys.hsv_to_rgb(h2, s, v)
            results.append((int(r2*255), int(g2*255), int(b2*255)))
        return results

    def generate_shades(self, r: int, g: int, b: int, count: int = 5) -> List[Tuple[int,int,int]]:
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        shades = []
        for i in range(count):
            v2 = max(0.1, v - (i * 0.15))
            r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v2)
            shades.append((int(r2*255), int(g2*255), int(b2*255)))
        return shades

    def generate_tints(self, r: int, g: int, b: int, count: int = 5) -> List[Tuple[int,int,int]]:
        h, l, s = colorsys.rgb_to_hls(r/255, g/255, b/255)
        tints = []
        for i in range(count):
            l2 = min(0.95, l + (i * 0.15))
            r2, g2, b2 = colorsys.hls_to_rgb(h, l2, s)
            tints.append((int(r2*255), int(g2*255), int(b2*255)))
        return tints

class PaletteStorage:
    def __init__(self):
        self.path = DATA_DIR / "palettes.json"
        self.palettes: List[ColorPalette] = []
        self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path) as f:
                data = json.load(f)
            for d in data:
                colors = [ColorSample(**c) for c in d.pop('colors', [])]
                p = ColorPalette(**d)
                p.colors = colors
                self.palettes.append(p)

    def _save(self):
        with open(self.path, 'w') as f:
            json.dump([asdict(p) for p in self.palettes], f, indent=2)

    def add(self, palette: ColorPalette):
        self.palettes.append(palette)
        self._save()

    def get(self, name: str) -> Optional[ColorPalette]:
        for p in self.palettes:
            if p.name == name or p.palette_id == name:
                return p
        return None

    def list_all(self):
        if not self.palettes:
            print("No palettes.")
            return
        for p in self.palettes:
            print(f"  {p.palette_id[:12]}  {p.name}  ({len(p.colors)} colors)")

class FloatingInspector(tk.Tk):
    def __init__(self, extractor: ScreenColorExtractor):
        super().__init__()
        self.extractor = extractor
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.93)
        self.geometry("260x140+10+10")
        self.configure(bg="#1a1a2e")
        self._build_ui()
        self._running = True
        self._update_loop()
        self.bind("<ButtonPress-1>", self._start_drag)
        self.bind("<B1-Motion>", self._drag)
        self._samples: List[ColorSample] = []

    def _build_ui(self):
        bg = "#1a1a2e"
        fg = "#e0e0e0"
        acc = "#4fc3f7"
        tk.Label(self, text="Color Inspector", font=("Arial",9,"bold"),
                 bg=bg, fg=acc).pack(pady=(6,2))
        self.color_box = tk.Label(self, bg="#888888", width=20, height=3)
        self.color_box.pack(padx=8, pady=2)
        self.hex_label = tk.Label(self, text="#??????", font=("Courier",11,"bold"),
                                   bg=bg, fg=fg)
        self.hex_label.pack()
        self.rgb_label = tk.Label(self, text="rgb(0, 0, 0)", font=("Courier",8),
                                   bg=bg, fg="#aaaaaa")
        self.rgb_label.pack()
        self.hsl_label = tk.Label(self, text="hsl(0, 0%, 0%)", font=("Courier",8),
                                   bg=bg, fg="#aaaaaa")
        self.hsl_label.pack()
        btn_f = tk.Frame(self, bg=bg)
        btn_f.pack(pady=4)
        tk.Button(btn_f, text="Copy HEX",
                  command=lambda: self._copy(self.hex_label.cget("text")),
                  bg="#333", fg=fg, font=("Arial",8), relief="flat").pack(side="left", padx=3)
        tk.Button(btn_f, text="Save",
                  command=self._save_current,
                  bg="#226622", fg="white", font=("Arial",8), relief="flat").pack(side="left", padx=3)
        tk.Button(btn_f, text="X",
                  command=self.quit,
                  bg="#883333", fg="white", font=("Arial",8), relief="flat").pack(side="left", padx=3)

    def _update_loop(self):
        if not self._running:
            return
        try:
            sample = self.extractor.get_cursor_pixel()
            self.color_box.configure(bg=sample.hex)
            self.hex_label.configure(text=sample.hex)
            self.rgb_label.configure(text=sample.css_rgb)
            h, s, l = sample.hsl
            self.hsl_label.configure(text=f"hsl({h:.0f}, {s:.0f}%, {l:.0f}%)")
            self._current = sample
        except Exception:
            pass
        self.after(100, self._update_loop)

    def _start_drag(self, event):
        self._dx, self._dy = event.x, event.y

    def _drag(self, event):
        x = self.winfo_x() + event.x - self._dx
        y = self.winfo_y() + event.y - self._dy
        self.geometry(f"+{x}+{y}")

    def _copy(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text.strip())

    def _save_current(self):
        if hasattr(self, '_current'):
            self._samples.append(self._current)
            log.info(f"Saved: {self._current.hex}")

    def get_saved_samples(self) -> List[ColorSample]:
        return self._samples

def print_color_info(sample: ColorSample):
    h, s, l = sample.hsl
    hv, sv, vv = sample.hsv
    cm = sample.cmyk
    print(f"Color at ({sample.x}, {sample.y}):")
    print(f"  Name:    {sample.name}")
    print(f"  HEX:     {sample.hex}")
    print(f"  RGB:     rgb({sample.r}, {sample.g}, {sample.b})")
    print(f"  HSL:     hsl({h:.1f}, {s:.1f}%, {l:.1f}%)")
    print(f"  HSV:     hsv({hv:.1f}, {sv:.1f}%, {vv:.1f}%)")
    print(f"  CMYK:    cmyk({cm[0]:.1f}%, {cm[1]:.1f}%, {cm[2]:.1f}%, {cm[3]:.1f}%)")
    print(f"  CSS:     {sample.css_rgb}")

def main():
    parser = argparse.ArgumentParser(description="Screen Color Picker")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("inspect", help="Open floating color inspector")

    p_pick = sub.add_parser("pick", help="Pick color at specific coordinates")
    p_pick.add_argument("x", type=int)
    p_pick.add_argument("y", type=int)

    p_cursor = sub.add_parser("cursor", help="Pick color under cursor after delay")
    p_cursor.add_argument("--delay", type=float, default=3.0)

    p_region = sub.add_parser("region", help="Get dominant colors in region")
    p_region.add_argument("x", type=int)
    p_region.add_argument("y", type=int)
    p_region.add_argument("w", type=int)
    p_region.add_argument("h", type=int)
    p_region.add_argument("--count", type=int, default=5)

    p_palette = sub.add_parser("palette", help="Extract palette from screen")
    p_palette.add_argument("--count", type=int, default=8)
    p_palette.add_argument("--save", default=None, help="Palette name to save as")

    p_convert = sub.add_parser("convert", help="Convert color format")
    p_convert.add_argument("color", help="HEX or r,g,b")
    p_convert.add_argument("--harmony", default="none",
                           choices=["none","complement","triadic","shades","tints"])

    sub.add_parser("list-palettes", help="List saved palettes")

    args = parser.parse_args()
    extractor = ScreenColorExtractor()
    converter = ColorConverter()
    storage = PaletteStorage()

    if args.cmd == "inspect":
        app = FloatingInspector(extractor)
        app.mainloop()
        samples = app.get_saved_samples()
        if samples:
            print(f"Saved {len(samples)} color(s):")
            for s in samples:
                print(f"  {s.hex}  {s.css_rgb}")

    elif args.cmd == "pick":
        sample = extractor.get_pixel(args.x, args.y)
        print_color_info(sample)

    elif args.cmd == "cursor":
        print(f"Move cursor to target color. Picking in {args.delay}s...")
        time.sleep(args.delay)
        sample = extractor.get_cursor_pixel()
        print_color_info(sample)

    elif args.cmd == "region":
        samples = extractor.get_region_dominant(args.x, args.y, args.w, args.h, args.count)
        print(f"Dominant colors in region ({args.x},{args.y},{args.w},{args.h}):")
        for i, s in enumerate(samples):
            print(f"  {i+1}. {s.hex}  {s.css_rgb}  ({s.name})")

    elif args.cmd == "palette":
        print("Extracting palette from screen...")
        samples = extractor.extract_palette_from_screenshot(args.count)
        print(f"Extracted {len(samples)} colors:")
        for s in samples:
            print(f"  {s.hex}  {s.css_rgb}  ({s.name})")
        if args.save:
            pid = datetime.now().strftime("%Y%m%d%H%M%S")
            palette = ColorPalette(palette_id=pid, name=args.save, colors=samples)
            storage.add(palette)
            print(f"Palette '{args.save}' saved ({pid})")

    elif args.cmd == "convert":
        c_str = args.color
        if c_str.startswith('#'):
            r, g, b = converter.hex_to_rgb(c_str)
        elif ',' in c_str:
            parts = [int(x.strip()) for x in c_str.split(',')]
            r, g, b = parts[0], parts[1], parts[2]
        else:
            print(f"Unknown color format: {c_str}")
            return
        sample = ColorSample(r=r, g=g, b=b)
        print_color_info(sample)
        if args.harmony != "none":
            print(f"\n  {args.harmony.title()}:")
            if args.harmony == "complement":
                cr, cg, cb = converter.complementary(r, g, b)
                cs = ColorSample(r=cr, g=cg, b=cb)
                print(f"    {cs.hex}  {cs.css_rgb}")
            elif args.harmony == "triadic":
                for t in converter.triadic(r, g, b):
                    ts = ColorSample(r=t[0], g=t[1], b=t[2])
                    print(f"    {ts.hex}  {ts.css_rgb}")
            elif args.harmony == "shades":
                for sh in converter.generate_shades(r, g, b):
                    ss = ColorSample(r=sh[0], g=sh[1], b=sh[2])
                    print(f"    {ss.hex}  {ss.css_rgb}")
            elif args.harmony == "tints":
                for ti in converter.generate_tints(r, g, b):
                    ts2 = ColorSample(r=ti[0], g=ti[1], b=ti[2])
                    print(f"    {ts2.hex}  {ts2.css_rgb}")

    elif args.cmd == "list-palettes":
        storage.list_all()

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
