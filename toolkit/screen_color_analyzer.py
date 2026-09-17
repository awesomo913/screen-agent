#!/usr/bin/env python3
"""Screen Color Analyzer - Analyze colors on screen, extract palettes, and identify UI elements."""

import os, sys, time, json, argparse, math, colorsys
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from collections import Counter
import pyautogui
from PIL import Image, ImageDraw
try:
    from pynput import mouse, keyboard
except ImportError:
    mouse = keyboard = None
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

@dataclass
class ColorInfo:
    rgb: Tuple[int,int,int]
    hex: str
    hsl: Tuple[float,float,float]
    name: str = ""
    count: int = 0
    percentage: float = 0.0

@dataclass
class ColorPalette:
    name: str
    colors: List[ColorInfo] = field(default_factory=list)
    source: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

class ColorUtils:
    NAMED_COLORS = {
        (255,0,0):"Red",(0,255,0):"Green",(0,0,255):"Blue",(255,255,0):"Yellow",
        (255,0,255):"Magenta",(0,255,255):"Cyan",(255,255,255):"White",(0,0,0):"Black",
        (128,128,128):"Gray",(255,165,0):"Orange",(128,0,128):"Purple",(165,42,42):"Brown",
        (255,192,203):"Pink",(0,128,0):"DarkGreen",(0,0,128):"Navy",(128,0,0):"Maroon",
    }
    @staticmethod
    def rgb_to_hex(r,g,b): return f"#{r:02x}{g:02x}{b:02x}"
    @staticmethod
    def hex_to_rgb(h):
        h=h.lstrip('#')
        return tuple(int(h[i:i+2],16) for i in (0,2,4))
    @staticmethod
    def rgb_to_hsl(r,g,b):
        h,l,s = colorsys.rgb_to_hls(r/255,g/255,b/255)
        return round(h*360,1),round(s*100,1),round(l*100,1)
    @staticmethod
    def color_distance(c1,c2):
        return math.sqrt(sum((a-b)**2 for a,b in zip(c1,c2)))
    @classmethod
    def nearest_named(cls,rgb):
        best_name,best_dist = "Unknown",float('inf')
        for named_rgb,name in cls.NAMED_COLORS.items():
            d = cls.color_distance(rgb,named_rgb)
            if d < best_dist:
                best_dist,best_name = d,name
        return best_name
    @staticmethod
    def is_similar(c1,c2,threshold=30):
        return ColorUtils.color_distance(c1,c2) < threshold
    @staticmethod
    def contrast_ratio(c1,c2):
        def luminance(rgb):
            vals = []
            for c in rgb:
                c = c/255
                vals.append(c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4)
            return 0.2126*vals[0] + 0.7152*vals[1] + 0.0722*vals[2]
        l1,l2 = luminance(c1),luminance(c2)
        lighter,darker = max(l1,l2),min(l1,l2)
        return round((lighter+0.05)/(darker+0.05),2)
    @staticmethod
    def complementary(rgb):
        h,l,s = colorsys.rgb_to_hls(rgb[0]/255,rgb[1]/255,rgb[2]/255)
        h = (h+0.5)%1.0
        r,g,b = colorsys.hls_to_rgb(h,l,s)
        return (int(r*255),int(g*255),int(b*255))

class ScreenColorAnalyzer:
    def __init__(self, output_dir=None):
        self.output_dir = output_dir or os.path.expanduser("~/color_analysis")
        os.makedirs(self.output_dir, exist_ok=True)
        self.palettes: List[ColorPalette] = []
        self.utils = ColorUtils()

    def get_pixel_color(self, x, y):
        img = pyautogui.screenshot(region=(x,y,1,1))
        rgb = img.getpixel((0,0))[:3]
        return ColorInfo(rgb=rgb, hex=self.utils.rgb_to_hex(*rgb),
                         hsl=self.utils.rgb_to_hsl(*rgb), name=self.utils.nearest_named(rgb))

    def analyze_region(self, x, y, width, height, max_colors=20, threshold=30):
        img = pyautogui.screenshot(region=(x,y,width,height))
        pixels = list(img.getdata())
        total = len(pixels)
        if HAS_NUMPY:
            arr = np.array(pixels)[:,:3]
            unique, counts = np.unique(arr, axis=0, return_counts=True)
            color_counts = sorted(zip(map(tuple,unique),counts), key=lambda x:-x[1])
        else:
            counter = Counter(tuple(p[:3]) for p in pixels)
            color_counts = counter.most_common(max_colors*5)
        merged = []
        for rgb, count in color_counts:
            found = False
            for existing in merged:
                if self.utils.is_similar(rgb, existing[0], threshold):
                    existing[1] += count
                    found = True
                    break
            if not found:
                merged.append([rgb, count])
        merged.sort(key=lambda x:-x[1])
        colors = []
        for rgb, count in merged[:max_colors]:
            colors.append(ColorInfo(
                rgb=rgb, hex=self.utils.rgb_to_hex(*rgb),
                hsl=self.utils.rgb_to_hsl(*rgb), name=self.utils.nearest_named(rgb),
                count=count, percentage=round(count/total*100,2)
            ))
        return colors

    def extract_palette(self, name, x=None, y=None, width=None, height=None, num_colors=8):
        if x is not None:
            colors = self.analyze_region(x,y,width,height,num_colors)
        else:
            sw,sh = pyautogui.size()
            colors = self.analyze_region(0,0,sw,sh,num_colors)
        palette = ColorPalette(name=name, colors=colors, source=f"screen({x},{y},{width},{height})")
        self.palettes.append(palette)
        return palette

    def create_palette_image(self, palette, output_path=None):
        swatch_w, swatch_h = 120, 80
        cols = min(len(palette.colors), 4)
        rows = math.ceil(len(palette.colors)/cols)
        img_w = cols*swatch_w + 20
        img_h = rows*(swatch_h+30) + 40
        img = Image.new("RGB",(img_w,img_h),(255,255,255))
        draw = ImageDraw.Draw(img)
        draw.text((10,10), palette.name, fill=(0,0,0))
        for i, color in enumerate(palette.colors):
            col = i % cols
            row = i // cols
            x = col*swatch_w + 10
            y = row*(swatch_h+30) + 35
            draw.rectangle([x,y,x+swatch_w-5,y+swatch_h], fill=color.rgb, outline=(0,0,0))
            draw.text((x,y+swatch_h+2), f"{color.hex}", fill=(0,0,0))
            draw.text((x,y+swatch_h+14), f"{color.percentage:.1f}%", fill=(100,100,100))
        out = output_path or os.path.join(self.output_dir, f"palette_{palette.name}.png")
        img.save(out)
        return out

    def interactive_picker(self):
        if not mouse or not keyboard:
            print("pynput required")
            return []
        picked = []
        print("Click to pick colors. ESC to finish.")
        def on_click(x,y,button,pressed):
            if pressed and button == mouse.Button.left:
                color = self.get_pixel_color(x,y)
                picked.append(color)
                print(f"  ({x},{y}): {color.hex} RGB{color.rgb} - {color.name}")
        def on_press(key):
            if key == keyboard.Key.esc:
                return False
        ml = mouse.Listener(on_click=on_click)
        kl = keyboard.Listener(on_press=on_press)
        ml.start(); kl.start(); kl.join(); ml.stop()
        return picked

    def check_contrast(self, color1_hex, color2_hex):
        c1 = self.utils.hex_to_rgb(color1_hex)
        c2 = self.utils.hex_to_rgb(color2_hex)
        ratio = self.utils.contrast_ratio(c1,c2)
        aa_normal = ratio >= 4.5
        aa_large = ratio >= 3.0
        aaa_normal = ratio >= 7.0
        aaa_large = ratio >= 4.5
        return {"ratio":ratio, "AA_normal":aa_normal, "AA_large":aa_large,
                "AAA_normal":aaa_normal, "AAA_large":aaa_large}

    def find_dominant_regions(self, target_color, tolerance=40, min_area=100):
        sw,sh = pyautogui.size()
        img = pyautogui.screenshot()
        if not HAS_NUMPY:
            return []
        arr = np.array(img)[:,:,:3]
        diff = np.sqrt(np.sum((arr.astype(float) - np.array(target_color).astype(float))**2, axis=2))
        mask = diff < tolerance
        regions = []
        visited = np.zeros(mask.shape, dtype=bool)
        for y in range(0,mask.shape[0],10):
            for x in range(0,mask.shape[1],10):
                if mask[y,x] and not visited[y,x]:
                    ys,xs = np.where(mask[max(0,y-50):min(mask.shape[0],y+50),
                                          max(0,x-50):min(mask.shape[1],x+50)])
                    if len(ys) >= min_area:
                        regions.append({"x":x,"y":y,"pixel_count":len(ys)})
                        visited[max(0,y-50):min(mask.shape[0],y+50),
                                max(0,x-50):min(mask.shape[1],x+50)] = True
        return regions

    def export_palette(self, palette, format="json", output_path=None):
        data = {"name":palette.name, "created":palette.created_at, "colors":[]}
        for c in palette.colors:
            data["colors"].append({"hex":c.hex, "rgb":list(c.rgb), "hsl":list(c.hsl),
                                    "name":c.name, "percentage":c.percentage})
        out = output_path or os.path.join(self.output_dir, f"palette_{palette.name}.{format}")
        if format == "json":
            with open(out,"w") as f: json.dump(data,f,indent=2)
        elif format == "css":
            with open(out,"w") as f:
                f.write(f"/* Palette: {palette.name} */\n:root {{\n")
                for i,c in enumerate(palette.colors):
                    f.write(f"  --color-{i+1}: {c.hex}; /* {c.name} */\n")
                f.write("}\n")
        elif format == "scss":
            with open(out,"w") as f:
                for i,c in enumerate(palette.colors):
                    f.write(f"$color-{i+1}: {c.hex}; // {c.name}\n")
        print(f"Exported to {out}")

def main():
    parser = argparse.ArgumentParser(description="Screen Color Analyzer")
    parser.add_argument("--output-dir", help="Output directory")
    subparsers = parser.add_subparsers(dest="command")
    pick_p = subparsers.add_parser("pick", help="Pick pixel color")
    pick_p.add_argument("x", type=int); pick_p.add_argument("y", type=int)
    region_p = subparsers.add_parser("analyze", help="Analyze region colors")
    region_p.add_argument("x",type=int); region_p.add_argument("y",type=int)
    region_p.add_argument("width",type=int); region_p.add_argument("height",type=int)
    region_p.add_argument("--colors",type=int,default=10)
    pal_p = subparsers.add_parser("palette", help="Extract color palette")
    pal_p.add_argument("name"); pal_p.add_argument("--region",nargs=4,type=int)
    pal_p.add_argument("--colors",type=int,default=8); pal_p.add_argument("--image",action="store_true")
    pal_p.add_argument("--export",choices=["json","css","scss"])
    inter_p = subparsers.add_parser("interactive", help="Interactive color picker")
    contrast_p = subparsers.add_parser("contrast", help="Check contrast ratio")
    contrast_p.add_argument("color1"); contrast_p.add_argument("color2")
    find_p = subparsers.add_parser("find-color", help="Find color on screen")
    find_p.add_argument("color", help="Hex color"); find_p.add_argument("--tolerance",type=int,default=40)
    comp_p = subparsers.add_parser("complementary", help="Get complementary color")
    comp_p.add_argument("color")
    args = parser.parse_args()
    analyzer = ScreenColorAnalyzer(output_dir=args.output_dir)
    if args.command == "pick":
        c = analyzer.get_pixel_color(args.x, args.y)
        print(f"Color at ({args.x},{args.y}): {c.hex} RGB{c.rgb} HSL{c.hsl} ({c.name})")
    elif args.command == "analyze":
        colors = analyzer.analyze_region(args.x,args.y,args.width,args.height,args.colors)
        for c in colors:
            bar = "#" * int(c.percentage/2)
            print(f"  {c.hex} {str(c.rgb):>15} {c.percentage:5.1f}% {c.name:<12} {bar}")
    elif args.command == "palette":
        region = tuple(args.region) if args.region else None
        if region:
            pal = analyzer.extract_palette(args.name,*region,args.colors)
        else:
            pal = analyzer.extract_palette(args.name,num_colors=args.colors)
        for c in pal.colors:
            print(f"  {c.hex} {c.name} ({c.percentage:.1f}%)")
        if args.image:
            path = analyzer.create_palette_image(pal)
            print(f"Palette image: {path}")
        if args.export:
            analyzer.export_palette(pal, args.export)
    elif args.command == "interactive":
        colors = analyzer.interactive_picker()
        if colors:
            pal = ColorPalette(name="picked",colors=colors)
            analyzer.create_palette_image(pal)
    elif args.command == "contrast":
        result = analyzer.check_contrast(args.color1, args.color2)
        print(f"Contrast ratio: {result['ratio']}:1")
        print(f"  WCAG AA normal text: {'PASS' if result['AA_normal'] else 'FAIL'}")
        print(f"  WCAG AA large text:  {'PASS' if result['AA_large'] else 'FAIL'}")
        print(f"  WCAG AAA normal text: {'PASS' if result['AAA_normal'] else 'FAIL'}")
        print(f"  WCAG AAA large text:  {'PASS' if result['AAA_large'] else 'FAIL'}")
    elif args.command == "find-color":
        rgb = ColorUtils.hex_to_rgb(args.color)
        regions = analyzer.find_dominant_regions(rgb, args.tolerance)
        print(f"Found {len(regions)} regions with color {args.color}:")
        for r in regions[:20]:
            print(f"  ({r['x']},{r['y']}): {r['pixel_count']} pixels")
    elif args.command == "complementary":
        rgb = ColorUtils.hex_to_rgb(args.color)
        comp = ColorUtils.complementary(rgb)
        print(f"Color: {args.color} -> Complementary: {ColorUtils.rgb_to_hex(*comp)}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
