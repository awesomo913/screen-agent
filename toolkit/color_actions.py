import colorsys
import re
import math
import json
import struct
import random
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image

# Standard CSS/SVG color names mapping (subset for production use)
_CSS_COLOR_NAMES: Dict[str, str] = {
    "aliceblue": "#f0f8ff", "antiquewhite": "#faebd7", "aqua": "#00ffff", "aquamarine": "#7fffd4",
    "azure": "#f0ffff", "beige": "#f5f5dc", "bisque": "#ffe4c4", "black": "#000000",
    "blanchedalmond": "#ffebcd", "blue": "#0000ff", "blueviolet": "#8a2be2", "brown": "#a52a2a",
    "burlywood": "#deb887", "cadetblue": "#5f9ea0", "chartreuse": "#7fff00", "chocolate": "#d2691e",
    "coral": "#ff7f50", "cornflowerblue": "#6495ed", "cornsilk": "#fff8dc", "crimson": "#dc143c",
    "cyan": "#00ffff", "darkblue": "#00008b", "darkcyan": "#008b8b", "darkgoldenrod": "#b8860b",
    "darkgray": "#a9a9a9", "darkgrey": "#a9a9a9", "darkgreen": "#006400", "darkkhaki": "#bdb76b",
    "darkmagenta": "#8b008b", "darkolivegreen": "#556b2f", "darkorange": "#ff8c00", "darkorchid": "#9932cc",
    "darkred": "#8b0000", "darksalmon": "#e9967a", "darkseagreen": "#8fbc8f", "darkslateblue": "#483d8b",
    "darkslategray": "#2f4f4f", "darkslategrey": "#2f4f4f", "darkturquoise": "#00ced1", "darkviolet": "#9400d3",
    "deeppink": "#ff1493", "deepskyblue": "#00bfff", "dimgray": "#696969", "dimgrey": "#696969",
    "dodgerblue": "#1e90ff", "firebrick": "#b22222", "floralwhite": "#fffaf0", "forestgreen": "#228b22",
    "fuchsia": "#ff00ff", "gainsboro": "#dcdcdc", "ghostwhite": "#f8f8ff", "gold": "#ffd700",
    "goldenrod": "#daa520", "gray": "#808080", "grey": "#808080", "green": "#008000",
    "greenyellow": "#adff2f", "honeydew": "#f0fff0", "hotpink": "#ff69b4", "indianred": "#cd5c5c",
    "indigo": "#4b0082", "ivory": "#fffff0", "khaki": "#f0e68c", "lavender": "#e6e6fa",
    "lavenderblush": "#fff0f5", "lawngreen": "#7cfc00", "lemonchiffon": "#fffacd", "lightblue": "#add8e6",
    "lightcoral": "#f08080", "lightcyan": "#e0ffff", "lightgoldenrodyellow": "#fafad2", "lightgray": "#d3d3d3",
    "lightgrey": "#d3d3d3", "lightgreen": "#90ee90", "lightpink": "#ffb6c1", "lightsalmon": "#ffa07a",
    "lightseagreen": "#20b2aa", "lightskyblue": "#87cefa", "lightslategray": "#778899", "lightslategrey": "#778899",
    "lightsteelblue": "#b0c4de", "lightyellow": "#ffffe0", "lime": "#00ff00", "limegreen": "#32cd32",
    "linen": "#faf0e6", "magenta": "#ff00ff", "maroon": "#800000", "mediumaquamarine": "#66cdaa",
    "mediumblue": "#0000cd", "mediumorchid": "#ba55d3", "mediumpurple": "#9370db", "mediumseagreen": "#3cb371",
    "mediumslateblue": "#7b68ee", "mediumspringgreen": "#00fa9a", "mediumturquoise": "#48d1cc", "mediumvioletred": "#c71585",
    "midnightblue": "#191970", "mintcream": "#f5fffa", "mistyrose": "#ffe4e1", "moccasin": "#ffe4b5",
    "navajowhite": "#ffdead", "navy": "#000080", "oldlace": "#fdf5e6", "olive": "#808000",
    "olivedrab": "#6b8e23", "orange": "#ffa500", "orangered": "#ff4500", "orchid": "#da70d6",
    "palegoldenrod": "#eee8aa", "palegreen": "#98fb98", "paleturquoise": "#afeeee", "palevioletred": "#db7093",
    "papayawhip": "#ffefd5", "peachpuff": "#ffdab9", "peru": "#cd853f", "pink": "#ffc0cb",
    "plum": "#dda0dd", "powderblue": "#b0e0e6", "purple": "#800080", "rebeccapurple": "#663399",
    "red": "#ff0000", "rosybrown": "#bc8f8f", "royalblue": "#4169e1", "saddlebrown": "#8b4513",
    "salmon": "#fa8072", "sandybrown": "#f4a460", "seagreen": "#2e8b57", "seashell": "#fff5ee",
    "sienna": "#a0522d", "silver": "#c0c0c0", "skyblue": "#87ceeb", "slateblue": "#6a5acd",
    "slategray": "#708090", "slategrey": "#708090", "snow": "#fffafa", "springgreen": "#00ff7f",
    "steelblue": "#4682b4", "tan": "#d2b48c", "teal": "#008080", "thistle": "#d8bfd8",
    "tomato": "#ff6347", "turquoise": "#40e0d0", "violet": "#ee82ee", "wheat": "#f5deb3",
    "white": "#ffffff", "whitesmoke": "#f5f5f5", "yellow": "#ffff00", "yellowgreen": "#9acd32"
}

_HEX_TO_NAMES: Dict[str, str] = {v: k for k, v in _CSS_COLOR_NAMES.items()}
_HEX_PATTERN = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))


def _parse_hex(hex_color: str) -> Tuple[int, int, int, int]:
    """Parse hex string to (r, g, b, a) values (0-255). Alpha defaults to 255."""
    if not isinstance(hex_color, str):
        raise ValueError("Hex color must be a string.")
    match = _HEX_PATTERN.match(hex_color.strip())
    if not match:
        raise ValueError(f"Invalid hex format: {hex_color}")
    
    h = match.group(1).upper()
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    if len(h) == 6:
        h += "FF"
    
    # Pack/Unpack using struct for strict byte validation
    try:
        bytes_val = bytes.fromhex(h)
        r, g, b, a = struct.unpack("BBBB", bytes_val)
        return r, g, b, a
    except struct.error as e:
        raise ValueError(f"Hex parsing failed: {e}")


def _format_hex(r: int, g: int, b: int) -> str:
    """Format RGB (0-255) to #RRGGBB hex string."""
    return f"#{r:02X}{g:02X}{b:02X}"


def _relative_luminance(r: int, g: int, b: int) -> float:
    """Calculate WCAG relative luminance."""
    def _linearize(c: int) -> float:
        srgb = c / 255.0
        return srgb / 12.92 if srgb <= 0.04045 else math.pow((srgb + 0.055) / 1.055, 2.4)
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def hex_to_rgb(hex_color: str) -> Dict[str, Any]:
    """Convert hex color to RGB dictionary."""
    try:
        r, g, b, _ = _parse_hex(hex_color)
        return {"success": True, "data": {"r": r, "g": g, "b": b}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


def rgb_to_hex(r: int, g: int, b: int) -> Dict[str, Any]:
    """Convert RGB (0-255) to hex string."""
    try:
        r, g, b = int(_clamp(r, 0, 255)), int(_clamp(g, 0, 255)), int(_clamp(b, 0, 255))
        return {"success": True, "data": {"hex": _format_hex(r, g, b)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


def rgb_to_hsl(r: int, g: int, b: int) -> Dict[str, Any]:
    """Convert RGB (0-255) to HSL (H:0-360, S:0-100, L:0-100)."""
    try:
        r_n, g_n, b_n = r / 255.0, g / 255.0, b / 255.0
        h, l, s = colorsys.rgb_to_hls(r_n, g_n, b_n)
        return {
            "success": True,
            "data": {"h": round(h * 360), "s": round(s * 100, 2), "l": round(l * 100, 2)},
            "error": None
        }
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


def hsl_to_rgb(h: float, s: float, l: float) -> Dict[str, Any]:
    """Convert HSL (H:0-360, S:0-100, L:0-100) to RGB (0-255)."""
    try:
        h_n = (h % 360) / 360.0
        s_n = _clamp(s, 0, 100) / 100.0
        l_n = _clamp(l, 0, 100) / 100.0
        r_n, g_n, b_n = colorsys.hls_to_rgb(h_n, l_n, s_n)
        r, g, b = int(round(r_n * 255)), int(round(g_n * 255)), int(round(b_n * 255))
        return {"success": True, "data": {"r": r, "g": g, "b": b}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


def rgb_to_hsv(r: int, g: int, b: int) -> Dict[str, Any]:
    """Convert RGB (0-255) to HSV (H:0-360, S:0-100, V:0-100)."""
    try:
        r_n, g_n, b_n = r / 255.0, g / 255.0, b / 255.0
        h, s, v = colorsys.rgb_to_hsv(r_n, g_n, b_n)
        return {
            "success": True,
            "data": {"h": round(h * 360), "s": round(s * 100, 2), "v": round(v * 100, 2)},
            "error": None
        }
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


def hsv_to_rgb(h: float, s: float, v: float) -> Dict[str, Any]:
    """Convert HSV (H:0-360, S:0-100, V:0-100) to RGB (0-255)."""
    try:
        h_n = (h % 360) / 360.0
        s_n = _clamp(s, 0, 100) / 100.0
        v_n = _clamp(v, 0, 100) / 100.0
        r_n, g_n, b_n = colorsys.hsv_to_rgb(h_n, s_n, v_n)
        r, g, b = int(round(r_n * 255)), int(round(g_n * 255)), int(round(b_n * 255))
        return {"success": True, "data": {"r": r, "g": g, "b": b}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


def rgb_to_cmyk(r: int, g: int, b: int) -> Dict[str, Any]:
    """Convert RGB (0-255) to CMYK (0-100)."""
    try:
        r_n, g_n, b_n = r / 255.0, g / 255.0, b / 255.0
        k = 1.0 - max(r_n, g_n, b_n)
        if k == 1.0:
            c = m = y = 0.0
        else:
            c = (1.0 - r_n - k) / (1.0 - k)
            m = (1.0 - g_n - k) / (1.0 - k)
            y = (1.0 - b_n - k) / (1.0 - k)
        return {
            "success": True,
            "data": {"c": round(c * 100, 2), "m": round(m * 100, 2), "y": round(y * 100, 2), "k": round(k * 100, 2)},
            "error": None
        }
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


def cmyk_to_rgb(c: float, m: float, y: float, k: float) -> Dict[str, Any]:
    """Convert CMYK (0-100) to RGB (0-255)."""
    try:
        c_n, m_n, y_n, k_n = _clamp(c, 0, 100)/100.0, _clamp(m, 0, 100)/100.0, _clamp(y, 0, 100)/100.0, _clamp(k, 0, 100)/100.0
        r = 255 * (1 - c_n) * (1 - k_n)
        g = 255 * (1 - m_n) * (1 - k_n)
        b = 255 * (1 - y_n) * (1 - k_n)
        return {
            "success": True,
            "data": {"r": round(r), "g": round(g), "b": round(b)},
            "error": None
        }
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}