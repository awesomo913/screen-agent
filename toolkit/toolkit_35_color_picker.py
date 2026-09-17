"""
toolkit_35_color_picker.py
Color conversion, analysis, and palette tools: HEX, RGB, HSL, HSV, CMYK,
color naming, contrast checking, palette generation. Stdlib only.
"""
from __future__ import annotations
import colorsys
import math
from typing import Any, Dict, List

def hex_to_rgb(hex_color: str) -> Dict[str, Any]:
    try:
        h = hex_color.lstrip("#")
        if len(h) == 3:
            h = "".join(c*2 for c in h)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return {"success": True, "data": {"r": r, "g": g, "b": b}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def rgb_to_hex(r: int, g: int, b: int) -> Dict[str, Any]:
    try:
        hex_color = "#{:02X}{:02X}{:02X}".format(int(r), int(g), int(b))
        return {"success": True, "data": hex_color, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def rgb_to_hsl(r: int, g: int, b: int) -> Dict[str, Any]:
    try:
        r_, g_, b_ = r / 255.0, g / 255.0, b / 255.0
        h, l, s = colorsys.rgb_to_hls(r_, g_, b_)
        return {"success": True, "data": {"h": round(h * 360, 1), "s": round(s * 100, 1), "l": round(l * 100, 1)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def hsl_to_rgb(h: float, s: float, l: float) -> Dict[str, Any]:
    try:
        r, g, b = colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
        return {"success": True, "data": {"r": round(r * 255), "g": round(g * 255), "b": round(b * 255)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def rgb_to_hsv(r: int, g: int, b: int) -> Dict[str, Any]:
    try:
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        return {"success": True, "data": {"h": round(h * 360, 1), "s": round(s * 100, 1), "v": round(v * 100, 1)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def hsv_to_rgb(h: float, s: float, v: float) -> Dict[str, Any]:
    try:
        r, g, b = colorsys.hsv_to_rgb(h / 360.0, s / 100.0, v / 100.0)
        return {"success": True, "data": {"r": round(r * 255), "g": round(g * 255), "b": round(b * 255)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def rgb_to_cmyk(r: int, g: int, b: int) -> Dict[str, Any]:
    try:
        if r == 0 and g == 0 and b == 0:
            return {"success": True, "data": {"c": 0, "m": 0, "y": 0, "k": 100}, "error": None}
        r_, g_, b_ = r / 255.0, g / 255.0, b / 255.0
        k = 1 - max(r_, g_, b_)
        c = (1 - r_ - k) / (1 - k)
        m = (1 - g_ - k) / (1 - k)
        y = (1 - b_ - k) / (1 - k)
        return {"success": True, "data": {"c": round(c * 100, 1), "m": round(m * 100, 1), "y": round(y * 100, 1), "k": round(k * 100, 1)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def cmyk_to_rgb(c: float, m: float, y: float, k: float) -> Dict[str, Any]:
    try:
        r = 255 * (1 - c / 100) * (1 - k / 100)
        g = 255 * (1 - m / 100) * (1 - k / 100)
        b = 255 * (1 - y / 100) * (1 - k / 100)
        return {"success": True, "data": {"r": round(r), "g": round(g), "b": round(b)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def color_info(hex_color: str) -> Dict[str, Any]:
    """All representations of a color from hex input."""
    try:
        rgb = hex_to_rgb(hex_color)
        if not rgb["success"]:
            return rgb
        r, g, b = rgb["data"]["r"], rgb["data"]["g"], rgb["data"]["b"]
        hsl = rgb_to_hsl(r, g, b)["data"]
        hsv = rgb_to_hsv(r, g, b)["data"]
        cmyk = rgb_to_cmyk(r, g, b)["data"]
        luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
        return {"success": True, "data": {
            "hex": hex_color.upper() if hex_color.startswith("#") else "#" + hex_color.upper(),
            "rgb": {"r": r, "g": g, "b": b},
            "hsl": hsl,
            "hsv": hsv,
            "cmyk": cmyk,
            "luminance": round(luminance, 4),
            "is_dark": luminance < 0.5
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def contrast_ratio(hex1: str, hex2: str) -> Dict[str, Any]:
    """Calculate WCAG contrast ratio between two colors."""
    try:
        def relative_lum(hex_c):
            rgb = hex_to_rgb(hex_c)["data"]
            vals = []
            for v in [rgb["r"], rgb["g"], rgb["b"]]:
                s = v / 255.0
                vals.append(s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4)
            return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]
        l1 = relative_lum(hex1)
        l2 = relative_lum(hex2)
        ratio = (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)
        return {"success": True, "data": {
            "ratio": round(ratio, 2),
            "wcag_aa_normal": ratio >= 4.5,
            "wcag_aa_large": ratio >= 3.0,
            "wcag_aaa_normal": ratio >= 7.0,
            "wcag_aaa_large": ratio >= 4.5
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def generate_color_palette(base_hex: str, count: int = 5) -> Dict[str, Any]:
    """Generate analogous colors by rotating hue."""
    try:
        rgb = hex_to_rgb(base_hex)["data"]
        hsv = rgb_to_hsv(rgb["r"], rgb["g"], rgb["b"])["data"]
        h, s, v = hsv["h"], hsv["s"], hsv["v"]
        step = 360 / count
        palette = []
        for i in range(count):
            new_h = (h + step * i) % 360
            new_rgb = hsv_to_rgb(new_h, s, v)["data"]
            hex_out = rgb_to_hex(new_rgb["r"], new_rgb["g"], new_rgb["b"])["data"]
            palette.append(hex_out)
        return {"success": True, "data": palette, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def complementary_color(hex_color: str) -> Dict[str, Any]:
    try:
        rgb = hex_to_rgb(hex_color)["data"]
        hsv = rgb_to_hsv(rgb["r"], rgb["g"], rgb["b"])["data"]
        comp_h = (hsv["h"] + 180) % 360
        comp_rgb = hsv_to_rgb(comp_h, hsv["s"], hsv["v"])["data"]
        comp_hex = rgb_to_hex(comp_rgb["r"], comp_rgb["g"], comp_rgb["b"])["data"]
        return {"success": True, "data": {"original": hex_color, "complementary": comp_hex}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def lighten_color(hex_color: str, amount: float = 20.0) -> Dict[str, Any]:
    try:
        rgb = hex_to_rgb(hex_color)["data"]
        hsl = rgb_to_hsl(rgb["r"], rgb["g"], rgb["b"])["data"]
        new_l = min(100, hsl["l"] + amount)
        new_rgb = hsl_to_rgb(hsl["h"], hsl["s"], new_l)["data"]
        new_hex = rgb_to_hex(new_rgb["r"], new_rgb["g"], new_rgb["b"])["data"]
        return {"success": True, "data": new_hex, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def darken_color(hex_color: str, amount: float = 20.0) -> Dict[str, Any]:
    try:
        rgb = hex_to_rgb(hex_color)["data"]
        hsl = rgb_to_hsl(rgb["r"], rgb["g"], rgb["b"])["data"]
        new_l = max(0, hsl["l"] - amount)
        new_rgb = hsl_to_rgb(hsl["h"], hsl["s"], new_l)["data"]
        new_hex = rgb_to_hex(new_rgb["r"], new_rgb["g"], new_rgb["b"])["data"]
        return {"success": True, "data": new_hex, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def mix_colors(hex1: str, hex2: str, ratio: float = 0.5) -> Dict[str, Any]:
    """Mix two colors by the given ratio (0.0 = all hex1, 1.0 = all hex2)."""
    try:
        rgb1 = hex_to_rgb(hex1)["data"]
        rgb2 = hex_to_rgb(hex2)["data"]
        r = round(rgb1["r"] * (1 - ratio) + rgb2["r"] * ratio)
        g = round(rgb1["g"] * (1 - ratio) + rgb2["g"] * ratio)
        b = round(rgb1["b"] * (1 - ratio) + rgb2["b"] * ratio)
        mixed_hex = rgb_to_hex(r, g, b)["data"]
        return {"success": True, "data": {"mixed": mixed_hex, "r": r, "g": g, "b": b}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def color_distance(hex1: str, hex2: str) -> Dict[str, Any]:
    """Euclidean distance between two colors in RGB space."""
    try:
        rgb1 = hex_to_rgb(hex1)["data"]
        rgb2 = hex_to_rgb(hex2)["data"]
        dist = math.sqrt((rgb1["r"]-rgb2["r"])**2 + (rgb1["g"]-rgb2["g"])**2 + (rgb1["b"]-rgb2["b"])**2)
        return {"success": True, "data": round(dist, 2), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
