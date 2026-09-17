"""
toolkit_27_image_metadata.py
Read and write EXIF/metadata from image files: GPS, camera info,
timestamps, dimensions, color profiles. Uses Pillow (soft-import).
"""
from __future__ import annotations
import os
import struct
from pathlib import Path
from typing import Any, Dict, List

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    HAS_PIEXIF = False

def _check_pil() -> bool:
    return HAS_PIL

def get_image_info(path: str) -> Dict[str, Any]:
    """Get basic image properties: size, mode, format."""
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        with Image.open(path) as img:
            return {"success": True, "data": {
                "path": path,
                "format": img.format,
                "mode": img.mode,
                "width": img.width,
                "height": img.height,
                "size_kb": round(os.path.getsize(path) / 1024, 1)
            }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_exif_data(path: str) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        with Image.open(path) as img:
            raw = img._getexif()
            if not raw:
                return {"success": True, "data": {}, "error": None}
            exif = {}
            for tag_id, value in raw.items():
                tag = TAGS.get(tag_id, str(tag_id))
                if isinstance(value, bytes):
                    try:
                        value = value.decode("utf-8", errors="replace")
                    except Exception:
                        value = str(value)
                exif[tag] = str(value) if not isinstance(value, (str, int, float, bool, list, dict)) else value
            return {"success": True, "data": exif, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_gps_coordinates(path: str) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        with Image.open(path) as img:
            raw = img._getexif()
            if not raw:
                return {"success": True, "data": None, "error": None}
        gps_tag = None
        for tag_id, value in raw.items():
            if TAGS.get(tag_id) == "GPSInfo":
                gps_tag = value
                break
        if not gps_tag:
            return {"success": True, "data": None, "error": None}
        gps = {GPSTAGS.get(k, k): v for k, v in gps_tag.items()}

        def _to_decimal(vals, ref):
            d = float(vals[0])
            m = float(vals[1])
            s = float(vals[2])
            decimal = d + m / 60 + s / 3600
            if ref in ("S", "W"):
                decimal = -decimal
            return round(decimal, 6)

        lat = _to_decimal(gps.get("GPSLatitude", [0,0,0]), gps.get("GPSLatitudeRef", "N"))
        lon = _to_decimal(gps.get("GPSLongitude", [0,0,0]), gps.get("GPSLongitudeRef", "E"))
        alt = float(gps["GPSAltitude"]) if "GPSAltitude" in gps else None
        return {"success": True, "data": {"latitude": lat, "longitude": lon, "altitude_m": alt}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_camera_info(path: str) -> Dict[str, Any]:
    try:
        exif_result = get_exif_data(path)
        if not exif_result["success"]:
            return exif_result
        exif = exif_result["data"]
        camera_fields = ["Make", "Model", "LensModel", "Software", "FNumber",
                         "ExposureTime", "ISOSpeedRatings", "FocalLength", "Flash",
                         "WhiteBalance", "DateTime", "DateTimeOriginal"]
        camera = {k: exif[k] for k in camera_fields if k in exif}
        return {"success": True, "data": camera, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_image_date(path: str) -> Dict[str, Any]:
    try:
        exif_result = get_exif_data(path)
        if not exif_result["success"]:
            return exif_result
        exif = exif_result["data"]
        date_fields = ["DateTimeOriginal", "DateTimeDigitized", "DateTime"]
        for field in date_fields:
            if field in exif:
                return {"success": True, "data": {"field": field, "date": exif[field]}, "error": None}
        stat = os.stat(path)
        return {"success": True, "data": {"field": "file_mtime", "date": str(stat.st_mtime)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def strip_exif(input_path: str, output_path: str) -> Dict[str, Any]:
    """Remove all EXIF data from an image (privacy)."""
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        with Image.open(input_path) as img:
            data = list(img.getdata())
            clean = Image.new(img.mode, img.size)
            clean.putdata(data)
            clean.save(output_path)
        return {"success": True, "data": {"saved": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_image_dimensions(path: str) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        with Image.open(path) as img:
            w, h = img.size
            return {"success": True, "data": {"width": w, "height": h, "aspect_ratio": round(w/h, 3), "megapixels": round(w*h/1e6, 2)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_color_mode(path: str) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        with Image.open(path) as img:
            return {"success": True, "data": {"mode": img.mode, "bands": img.getbands()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def batch_get_image_info(folder: str, recursive: bool = False) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}
        results = []
        paths = []
        if recursive:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if Path(f).suffix.lower() in exts:
                        paths.append(os.path.join(root, f))
        else:
            for f in os.listdir(folder):
                if Path(f).suffix.lower() in exts:
                    paths.append(os.path.join(folder, f))
        for p in paths[:200]:
            info = get_image_info(p)
            if info["success"]:
                results.append(info["data"])
        return {"success": True, "data": {"count": len(results), "images": results}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_images_without_gps(folder: str) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        no_gps = []
        exts = {".jpg", ".jpeg"}
        for root, dirs, files in os.walk(folder):
            for f in files:
                if Path(f).suffix.lower() in exts:
                    p = os.path.join(root, f)
                    gps = get_gps_coordinates(p)
                    if gps["success"] and gps["data"] is None:
                        no_gps.append(p)
        return {"success": True, "data": {"count": len(no_gps), "files": no_gps[:100]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_pil_available() -> Dict[str, Any]:
    return {"success": True, "data": {"pillow": HAS_PIL, "piexif": HAS_PIEXIF}, "error": None}
