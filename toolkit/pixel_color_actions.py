import os
import time
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Union, Optional, Any

import mss
import pyautogui
import colorsys
import numpy as np
from PIL import Image

# System Safety: Cap maximum returned locations to prevent memory overflow on large screens
MAX_LOCATIONS_LIMIT = 5000

def _standardize_return(status: str, data: Any = None, message: str = "") -> Dict[str, Any]:
    """Helper to ensure all returns follow the same Dict structure."""
    res = {"status": status}
    if data is not None:
        res["data"] = data
    if message:
        res["message"] = message
    return res

def _capture_screen_numpy(region: Optional[Tuple[int, int, int, int]] = None) -> np.ndarray:
    """
    Captures the screen or region using mss for high performance.
    Returns RGB numpy array. Region: (left, top, width, height).
    """
    with mss.mss() as sct:
        if region:
            monitor = {"left": region[0], "top": region[1], "width": region[2], "height": region[3]}
        else:
            monitor = sct.monitors[1]  # Primary monitor
        
        # Grab screen, convert to numpy array (returns BGRA)
        img = np.array(sct.grab(monitor))
        
        # Drop Alpha channel and convert BGR to RGB
        rgb_img = img[:, :, :3][:, :, ::-1]
        return rgb_img

# --- 1. Color Conversion & Math Utilities ---

def rgb_to_hex(r: int, g: int, b: int) -> Dict[str, Any]:
    try:
        hex_val = f"#{r:02x}{g:02x}{b:02x}".upper()
        return _standardize_return("success", data=hex_val)
    except Exception as e:
        return _standardize_return("error", message=str(e))

def hex_to_rgb(hex_color: str) -> Dict[str, Any]:
    try:
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return _standardize_return("success", data=rgb)
    except Exception as e:
        return _standardize_return("error", message=str(e))

def rgb_to_hsv(r: int, g: int, b: int) -> Dict[str, Any]:
    try:
        hsv = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        return _standardize_return("success", data={"h": hsv[0], "s": hsv[1], "v": hsv[2]})
    except Exception as e:
        return _standardize_return("error", message=str(e))

def hsv_to_rgb(h: float, s: float, v: float) -> Dict[str, Any]:
    try:
        rgb = colorsys.hsv_to_rgb(h, s, v)
        data = (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
        return _standardize_return("success", data=data)
    except Exception as e:
        return _standardize_return("error", message=str(e))

def color_distance(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> Dict[str, Any]:
    try:
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(rgb1, rgb2)))
        return _standardize_return("success", data=dist)
    except Exception as e:
        return _standardize_return("error", message=str(e))

def compare_colors(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int], tolerance: float = 10.0) -> Dict[str, Any]:
    try:
        dist_res = color_distance(rgb1, rgb2)
        if dist_res["status"] == "error": return dist_res
        is_match = dist_res["data"] <= tolerance
        return _standardize_return("success", data={"match": is_match, "distance": dist_res["data"]})
    except Exception as e:
        return _standardize_return("error", message=str(e))

def get_color_name(r: int, g: int, b: int) -> Dict[str, Any]:
    try:
        # A basic map for demonstration; in production, expand this or use a library like webcolors
        colors = {
            (255, 0, 0): "Red", (0, 255, 0): "Green", (0, 0, 255): "Blue",
            (255, 255, 255): "White", (0, 0, 0): "Black", (128, 128, 128): "Gray"
        }
        name = colors.get((r, g, b), rgb_to_hex(r, g, b)["data"])
        return _standardize_return("success", data=name)
    except Exception as e:
        return _standardize_return("error", message=str(e))

def find_nearest_color(target_rgb: Tuple[int, int, int], palette: List[Tuple[int, int, int]]) -> Dict[str, Any]:
    try:
        nearest = min(palette, key=lambda c: color_distance(target_rgb, c)["data"])
        return _standardize_return("success", data=nearest)
    except Exception as e:
        return _standardize_return("error", message=str(e))

# --- 2. Single Pixel Operations ---

def get_pixel_rgb(x: int, y: int) -> Dict[str, Any]:
    try:
        # pyautogui is safe for single pixel lookups
        rgb = pyautogui.pixel(x, y)
        return _standardize_return("success", data=rgb)
    except Exception as e:
        return _standardize_return("error", message=str(e))

def get_pixel_color(x: int, y: int) -> Dict[str, Any]:
    # Alias for get_pixel_rgb for naming consistency requested
    return get_pixel_rgb(x, y)

def get_pixel_hex(x: int, y: int) -> Dict[str, Any]:
    try:
        rgb_res = get_pixel_rgb(x, y)
        if rgb_res["status"] == "error": return rgb_res
        return rgb_to_hex(*rgb_res["data"])
    except Exception as e:
        return _standardize_return("error", message=str(e))

def get_pixel_hsv(x: int, y: int) -> Dict[str, Any]:
    try:
        rgb_res = get_pixel_rgb(x, y)
        if rgb_res["status"] == "error": return rgb_res
        return rgb_to_hsv(*rgb_res["data"])
    except Exception as e:
        return _standardize_return("error", message=str(e))

def color_match(x: int, y: int, target_rgb: Tuple[int, int, int], tolerance: int = 0) -> Dict[str, Any]:
    try:
        rgb_res = get_pixel_rgb(x, y)
        if rgb_res["status"] == "error": return rgb_res
        return compare_colors(rgb_res["data"], target_rgb, tolerance)
    except Exception as e:
        return _standardize_return("error", message=str(e))

# --- 3. Screen Search Operations ---

def find_color_on_screen(rgb: Tuple[int, int, int], tolerance: int = 0, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
    try:
        img = _capture_screen_numpy(region)
        target = np.array(rgb)
        
        if tolerance == 0:
            matches = np.where(np.all(img == target, axis=-1))
        else:
            matches = np.where(np.all(np.abs(img - target) <= tolerance, axis=-1))
            
        if len(matches[0]) > 0:
            # Return first match. Add region offset if applicable
            y, x = int(matches[0][0]), int(matches[1][0])
            if region:
                x += region[0]
                y += region[1]
            return _standardize_return("success", data={"x": x, "y": y})
        
        return _standardize_return("success", data=None, message="Color not found")
    except Exception as e:
        return _standardize_return("error", message=str(e))

def find_all_color_locations(rgb: Tuple[int, int, int], tolerance: int = 0, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
    try:
        img = _capture_screen_numpy(region)
        target = np.array(rgb)
        
        if tolerance == 0:
            matches = np.where(np.all(img == target, axis=-1))
        else:
            matches = np.where(np.all(np.abs(img - target) <= tolerance, axis=-1))
            
        coords = list(zip(matches[1].tolist(), matches[0].tolist())) # (x, y)
        
        if region:
            coords = [(x + region[0], y + region[1]) for x, y in coords]
            
        if len(coords) > MAX_LOCATIONS_LIMIT:
            coords = coords[:MAX_LOCATIONS_LIMIT]
            return _standardize_return("success", data=coords, message=f"Results truncated to {MAX_LOCATIONS_LIMIT} for safety.")
            
        return _standardize_return("success", data=coords)
    except Exception as e:
        return _standardize_return("error", message=str(e))

# --- 4. Timing and State Actions ---

def wait_for_color(x: int, y: int, target_rgb: Tuple[int, int, int], timeout: float = 10.0, tolerance: int = 0) -> Dict[str, Any]:
    try:
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            match_res = color_match(x, y, target_rgb, tolerance)
            if match_res["status"] == "success" and match_res["data"]["match"]:
                return _standardize_return("success", data=True)
            time.sleep(0.1)
        return _standardize_return("success", data=False, message="Timeout reached")
    except Exception as e:
        return _standardize_return("error", message=str(e))

def detect_color_change(x: int, y: int, delay: float = 1.0) -> Dict[str, Any]:
    try:
        color1 = get_pixel_rgb(x, y)["data"]
        time.sleep(delay)
        color2 = get_pixel_rgb(x, y)["data"]
        changed = color1 != color2
        return _standardize_return("success", data={"changed": changed, "old": color1, "new": color2})
    except Exception as e:
        return _standardize_return("error", message=str(e))

def monitor_pixel_color(x: int, y: int, duration: float = 5.0, interval: float = 0.5) -> Dict[str, Any]:
    try:
        start_time = time.time()
        history = []
        last_color = None
        
        while (time.time() - start_time) < duration:
            current = get_pixel_rgb(x, y)["data"]
            if current != last_color:
                history.append({"time": time.time(), "rgb": current})
                last_color = current
            time.sleep(interval)
            
        return _standardize_return("success", data=history)
    except Exception as e:
        return _standardize_return("error", message=str(e))

# --- 5. Region Analysis ---

def get_dominant_color(region: Tuple[int, int, int, int]) -> Dict[str, Any]:
    try:
        img = _capture_screen_numpy(region)
        pixels = img.reshape(-1, 3)
        colors, counts = np.unique(pixels, axis=0, return_counts=True)
        dominant = colors[counts.argmax()]
        return _standardize_return("success", data=tuple(dominant.tolist()))
    except Exception as e:
        return _standardize_return("error", message=str(e))

def get_average_color(region: Tuple[int, int, int, int]) -> Dict[str, Any]:
    try:
        img = _capture_screen_numpy(region)
        avg_color = img.mean(axis=(0, 1))
        return _standardize_return("success", data=tuple(avg_color.astype(int).tolist()))
    except Exception as e:
        return _standardize_return("error", message=str(e))

def get_color_palette(region: Tuple[int, int, int, int], top_n: int = 5) -> Dict[str, Any]:
    try:
        img = _capture_screen_numpy(region)
        pixels = img.reshape(-1, 3)
        colors, counts = np.unique(pixels, axis=0, return_counts=True)
        
        # Sort by frequency
        sorted_indices = np.argsort(-counts)
        top_colors = colors[sorted_indices][:top_n]
        
        palette = [tuple(c.tolist()) for c in top_colors]
        return _standardize_return("success", data=palette)
    except Exception as e:
        return _standardize_return("error", message=str(e))

def sample_region_colors(region: Tuple[int, int, int, int], grid_size: int = 3) -> Dict[str, Any]:
    try:
        img = _capture_screen_numpy(region)
        h, w = img.shape[:2]
        samples = []
        
        for y in np.linspace(0, h-1, grid_size, dtype=int):
            for x in np.linspace(0, w-1, grid_size, dtype=int):
                samples.append(tuple(img[y, x].tolist()))
                
        return _standardize_return("success", data=samples)
    except Exception as e:
        return _standardize_return("error", message=str(e))

def get_color_histogram(region: Tuple[int, int, int, int], bins: int = 16) -> Dict[str, Any]:
    try:
        img = _capture_screen_numpy(region)
        hist_r, _ = np.histogram(img[:, :, 0], bins=bins, range=(0, 256))
        hist_g, _ = np.histogram(img[:, :, 1], bins=bins, range=(0, 256))
        hist_b, _ = np.histogram(img[:, :, 2], bins=bins, range=(0, 256))
        
        data = {
            "r": hist_r.tolist(),
            "g": hist_g.tolist(),
            "b": hist_b.tolist()
        }
        return _standardize_return("success", data=data)
    except Exception as e:
        return _standardize_return("error", message=str(e))

def create_color_mask(region: Tuple[int, int, int, int], target_rgb: Tuple[int, int, int], tolerance: int = 10) -> Dict[str, Any]:
    try:
        img = _capture_screen_numpy(region)
        target = np.array(target_rgb)
        mask = np.all(np.abs(img - target) <= tolerance, axis=-1)
        
        # Return 2D binary list (1 for match, 0 for no match)
        return _standardize_return("success", data=mask.astype(int).tolist())
    except Exception as e:
        return _standardize_return("error", message=str(e))

def export_color_map(region: Tuple[int, int, int, int], filepath: str = "colormap.json") -> Dict[str, Any]:
    try:
        palette_res = get_color_palette(region, top_n=20)
        if palette_res["status"] == "error": return palette_res
        
        export_data = {
            "region": region,
            "timestamp": time.time(),
            "colors": palette_res["data"]
        }
        
        out_path = Path(filepath)
        out_path.write_text(json.dumps(export_data, indent=2))
        return _standardize_return("success", data=str(out_path.absolute()))
    except Exception as e:
        return _standardize_return("error", message=str(e))

if __name__ == "__main__":
    # Internal test/validation module
    print("Module initialized successfully. Example call:")
    print(get_pixel_color(100, 100))
