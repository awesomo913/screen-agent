"""
toolkit_52_image_converter.py
Convert, resize, crop, rotate, compress, and batch-process images using Pillow.
Distinct from image_processing (filters/effects) - focuses on format conversion
and geometric transformations.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, List

try:
    from PIL import Image, ImageOps, ImageFilter, ExifTags
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

SUPPORTED_FORMATS = ["PNG", "JPEG", "JPG", "BMP", "GIF", "TIFF", "WEBP", "ICO"]

def check_pil() -> Dict[str, Any]:
    return {"success": True, "data": {"pillow": HAS_PIL, "formats": SUPPORTED_FORMATS}, "error": None}

def convert_format(input_path: str, output_path: str, quality: int = 85) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        with Image.open(input_path) as img:
            fmt = Path(output_path).suffix.lstrip(".").upper()
            if fmt == "JPG": fmt = "JPEG"
            if img.mode == "RGBA" and fmt == "JPEG":
                img = img.convert("RGB")
            save_kwargs = {"quality": quality} if fmt in ("JPEG", "WEBP") else {}
            img.save(output_path, format=fmt, **save_kwargs)
        return {"success": True, "data": {"saved": output_path, "format": fmt}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def resize_image(input_path: str, output_path: str, width: int, height: int, keep_aspect: bool = True) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        with Image.open(input_path) as img:
            if keep_aspect:
                img.thumbnail((width, height), Image.LANCZOS)
            else:
                img = img.resize((width, height), Image.LANCZOS)
            img.save(output_path)
        return {"success": True, "data": {"saved": output_path, "size": list(img.size)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def resize_by_percent(input_path: str, output_path: str, percent: float) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        with Image.open(input_path) as img:
            new_w = int(img.width * percent / 100)
            new_h = int(img.height * percent / 100)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            img.save(output_path)
        return {"success": True, "data": {"saved": output_path, "new_size": [new_w, new_h]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def crop_image(input_path: str, output_path: str, left: int, top: int, right: int, bottom: int) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        with Image.open(input_path) as img:
            cropped = img.crop((left, top, right, bottom))
            cropped.save(output_path)
        return {"success": True, "data": {"saved": output_path, "crop_size": [right-left, bottom-top]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def rotate_image(input_path: str, output_path: str, degrees: float, expand: bool = True) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        with Image.open(input_path) as img:
            rotated = img.rotate(degrees, expand=expand)
            rotated.save(output_path)
        return {"success": True, "data": {"saved": output_path, "degrees": degrees}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def flip_image(input_path: str, output_path: str, direction: str = "horizontal") -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        with Image.open(input_path) as img:
            if direction.lower() == "horizontal":
                flipped = ImageOps.mirror(img)
            else:
                flipped = ImageOps.flip(img)
            flipped.save(output_path)
        return {"success": True, "data": {"saved": output_path, "direction": direction}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def compress_image(input_path: str, output_path: str, max_size_kb: int = 200) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        quality = 85
        with Image.open(input_path) as img:
            if img.mode == "RGBA":
                img = img.convert("RGB")
            while quality > 10:
                img.save(output_path, "JPEG", quality=quality, optimize=True)
                if os.path.getsize(output_path) <= max_size_kb * 1024:
                    break
                quality -= 10
        final_size = round(os.path.getsize(output_path) / 1024, 1)
        return {"success": True, "data": {"saved": output_path, "quality": quality, "size_kb": final_size}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def add_watermark_text(input_path: str, output_path: str, text: str, position: str = "bottom-right", opacity: int = 128) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        from PIL import ImageDraw, ImageFont
        with Image.open(input_path).convert("RGBA") as img:
            overlay = Image.new("RGBA", img.size, (0,0,0,0))
            draw = ImageDraw.Draw(overlay)
            try:
                font = ImageFont.truetype("arial.ttf", max(12, img.width // 40))
            except Exception:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0,0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad = 10
            if position == "bottom-right":
                pos = (img.width - tw - pad, img.height - th - pad)
            elif position == "bottom-left":
                pos = (pad, img.height - th - pad)
            elif position == "top-right":
                pos = (img.width - tw - pad, pad)
            elif position == "center":
                pos = ((img.width - tw) // 2, (img.height - th) // 2)
            else:
                pos = (pad, pad)
            draw.text(pos, text, fill=(255, 255, 255, opacity), font=font)
            combined = Image.alpha_composite(img, overlay)
            combined.convert("RGB").save(output_path)
        return {"success": True, "data": {"saved": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def convert_to_grayscale(input_path: str, output_path: str) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        with Image.open(input_path) as img:
            gray = ImageOps.grayscale(img)
            gray.save(output_path)
        return {"success": True, "data": {"saved": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_thumbnail(input_path: str, output_path: str, max_size: int = 128) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        with Image.open(input_path) as img:
            img.thumbnail((max_size, max_size), Image.LANCZOS)
            img.save(output_path)
        return {"success": True, "data": {"saved": output_path, "size": list(img.size)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def batch_convert(input_folder: str, output_folder: str, output_format: str, quality: int = 85) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        import os
        os.makedirs(output_folder, exist_ok=True)
        exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"}
        fmt = output_format.lstrip(".").upper()
        if fmt == "JPG": fmt = "JPEG"
        ext_out = "." + output_format.lstrip(".")
        count = 0
        for f in os.listdir(input_folder):
            if Path(f).suffix.lower() in exts:
                inp = os.path.join(input_folder, f)
                out = os.path.join(output_folder, Path(f).stem + ext_out)
                convert_format(inp, out, quality)
                count += 1
        return {"success": True, "data": {"converted": count, "output_folder": output_folder}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def batch_resize(input_folder: str, output_folder: str, width: int, height: int, keep_aspect: bool = True) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        import os
        os.makedirs(output_folder, exist_ok=True)
        exts = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}
        count = 0
        for f in os.listdir(input_folder):
            if Path(f).suffix.lower() in exts:
                inp = os.path.join(input_folder, f)
                out = os.path.join(output_folder, f)
                resize_image(inp, out, width, height, keep_aspect)
                count += 1
        return {"success": True, "data": {"resized": count}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
