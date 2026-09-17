import os
import io
import base64
import colorsys
from typing import Dict, Any, List, Tuple, Optional, Union
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageEnhance, ImageDraw, ImageFont, ImageOps, ImageFilter


def _success(data: Any = None, message: str = "Operation successful") -> Dict[str, Any]:
    """Standard success response format."""
    return {"success": True, "message": message, "data": data, "error": None}


def _failure(error_msg: str) -> Dict[str, Any]:
    """Standard failure response format."""
    return {"success": False, "message": error_msg, "data": None, "error": error_msg}


def _parse_color(color: Union[str, Tuple[int, int, int]]) -> Tuple[int, int, int]:
    """Parse hex or RGB tuple to RGB tuple."""
    if isinstance(color, str):
        color = color.lstrip("#")
        if len(color) == 6:
            return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        raise ValueError("Unsupported color format. Use hex (#RRGGBB) or RGB tuple.")
    if isinstance(color, tuple) and len(color) == 3:
        return color
    raise ValueError("Color must be a hex string or (R, G, B) tuple.")


def _load_pil(filepath: Union[str, Path]) -> Image.Image:
    """Load an image using Pillow with validation."""
    p = Path(filepath).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Image not found: {p}")
    try:
        return Image.open(p)
    except Exception as e:
        raise ValueError(f"Failed to open image: {e}")


def open_image(filepath: str) -> Dict[str, Any]:
    """Open an image file and return its PIL object and metadata."""
    try:
        img = _load_pil(filepath)
        return _success(
            data={"image": img, "path": str(filepath), "size": img.size, "mode": img.mode},
            message="Image opened successfully"
        )
    except Exception as e:
        return _failure(str(e))


def save_image(image: Union[Image.Image, np.ndarray, str, Path], output: str, 
               format: str, quality: int = 95) -> Dict[str, Any]:
    """Save an image to disk with specified format and quality."""
    try:
        if isinstance(image, (str, Path)):
            img = _load_pil(image)
        elif isinstance(image, np.ndarray):
            img = Image.fromarray(image)
        elif isinstance(image, Image.Image):
            img = image
        else:
            raise TypeError("Unsupported image type. Expect PIL Image, numpy array, or file path.")
        
        out_path = Path(output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Normalize format
        fmt = format.upper().replace(".", "").replace("JPEG", "JPG")
        
        if fmt in ("JPEG", "JPG") and img.mode == "RGBA":
            img = img.convert("RGB")
            
        img.save(str(out_path), format=fmt, quality=quality, optimize=True)
        return _success(data={"path": str(out_path), "size": out_path.stat().st_size}, 
                        message="Image saved successfully")
    except Exception as e:
        return _failure(str(e))


def resize_image(filepath: str, width: int, height: int, output: str) -> Dict[str, Any]:
    """Resize an image to exact dimensions."""
    try:
        img = _load_pil(filepath).resize((width, height), Image.Resampling.LANCZOS)
        return save_image(img, output, img.format or "PNG", 95)
    except Exception as e:
        return _failure(str(e))


def crop_image(filepath: str, box: Tuple[int, int, int, int], output: str) -> Dict[str, Any]:
    """Crop an image using (left, upper, right, lower) box."""
    try:
        if len(box) != 4:
            raise ValueError("Box must be a tuple of 4 integers: (left, upper, right, lower)")
        img = _load_pil(filepath).crop(box)
        return save_image(img, output, img.format or "PNG", 95)
    except Exception as e:
        return _failure(str(e))


def rotate_image(filepath: str, angle: float, output: str) -> Dict[str, Any]:
    """Rotate an image by a given angle."""
    try:
        img = _load_pil(filepath).rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
        return save_image(img, output, img.format or "PNG", 95)
    except Exception as e:
        return _failure(str(e))


def flip_image(filepath: str, direction: str, output: str) -> Dict[str, Any]:
    """Flip image horizontally, vertically, or both."""
    try:
        img = _load_pil(filepath)
        direction = direction.lower()
        if direction == "horizontal":
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif direction == "vertical":
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        elif direction == "both":
            img = img.transpose(Image.Transpose.ROTATE_180)
        else:
            raise ValueError("Direction must be 'horizontal', 'vertical', or 'both'")
        return save_image(img, output, img.format or "PNG", 95)
    except Exception as e:
        return _failure(str(e))


def convert_format(filepath: str, target_format: str, output: str) -> Dict[str, Any]:
    """Convert image to a different format."""
    try:
        img = _load_pil(filepath)
        return save_image(img, output, target_format, 95)
    except Exception as e:
        return _failure(str(e))


def apply_filter(filepath: str, filter_name: str, output: str) -> Dict[str, Any]:
    """Apply a standard image filter."""
    try:
        img = _load_pil(filepath)
        filters_map = {
            "blur": ImageFilter.BLUR,
            "contour": ImageFilter.CONTOUR,
            "detail": ImageFilter.DETAIL,
            "edge_enhance": ImageFilter.EDGE_ENHANCE,
            "edge_enhance_more": ImageFilter.EDGE_ENHANCE_MORE,
            "emboss": ImageFilter.EMBOSS,
            "find_edges": ImageFilter.FIND_EDGES,
            "sharpen": ImageFilter.SHARPEN,
            "smooth": ImageFilter.SMOOTH,
            "smooth_more": ImageFilter.SMOOTH_MORE,
            "gaussian_blur": ImageFilter.GaussianBlur(radius=3),
        }
        flt = filter_name.lower().replace(" ", "_")
        if flt not in filters_map:
            raise ValueError(f"Unsupported filter: {filter_name}. Options: {list(filters_map.keys())}")
        img = img.filter(filters_map[flt])
        return save_image(img, output, img.format or "PNG", 95)
    except Exception as e:
        return _failure(str(e))


def adjust_brightness(filepath: str, factor: float, output: str) -> Dict[str, Any]:
    """Adjust image brightness (0.0 = black, 1.0 = original)."""
    try:
        img = _load_pil(filepath)
        enhancer = ImageEnhance.Brightness(img)
        return save_image(enhancer.enhance(factor), output, img.format or "PNG", 95)
    except Exception as e:
        return _failure(str(e))


def adjust_contrast(filepath: str, factor: float, output: str) -> Dict[str, Any]:
    """Adjust image contrast (0.0 = gray, 1.0 = original)."""
    try:
        img = _load_pil(filepath)
        enhancer = ImageEnhance.Contrast(img)
        return save_image(enhancer.enhance(factor), output, img.format or "PNG", 95)
    except Exception as e:
        return _failure(str(e))


def adjust_saturation(filepath: str, factor: float, output: str) -> Dict[str, Any]:
    """Adjust image saturation (0.0 = grayscale, 1.0 = original)."""
    try:
        img = _load_pil(filepath)
        enhancer = ImageEnhance.Color(img)
        return save_image(enhancer.enhance(factor), output, img.format or "PNG", 95)
    except Exception as e:
        return _failure(str(e))


def blur_image(filepath: str, radius: float, output: str) -> Dict[str, Any]:
    """Apply Gaussian blur."""
    try:
        img = _load_pil(filepath)
        img = img.filter(ImageFilter.GaussianBlur(radius=max(0.1, radius)))
        return save_image(img, output, img.format or "PNG", 95)
    except Exception as e:
        return _failure(str(e))


def sharpen_image(filepath: str, factor: float, output: str) -> Dict[str, Any]:
    """Adjust sharpness (0.0 = blurred, 1.0 = original, >1.0 = sharpened)."""
    try:
        img = _load_pil(filepath)
        enhancer = ImageEnhance.Sharpness(img)
        return save_image(enhancer.enhance(factor), output, img.format or "PNG", 95)
    except Exception as e:
        return _failure(str(e))


def add_border(filepath: str, width: int, color: Union[str, Tuple[int, int, int]], output: str) -> Dict[str, Any]:
    """Add a solid border around the image."""
    try:
        img = _load_pil(filepath)
        rgb_color = _parse_color(color)
        img = ImageOps.expand(img, border=width, fill=rgb_color)
        return save_image(img, output, img.format or "PNG", 95)
    except Exception as e:
        return _failure(str(e))


def overlay_images(base: str, overlay: str, position: Tuple[int, int], opacity: float, output: str) -> Dict[str, Any]:
    """Overlay an image on top of another with opacity."""
    try:
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("Opacity must be between 0.0 and 1.0")
            
        base_img = _load_pil(base).convert("RGBA")
        overlay_img = _load_pil(overlay).convert("RGBA")
        
        if opacity < 1.0:
            overlay_img = Image.blend(Image.new("RGBA", overlay_img.size, (0, 0, 0, 0)), overlay_img, opacity)
            
        base_img.paste(overlay_img, position, overlay_img)
        return save_image(base_img, output, base_img.format or "PNG", 95)
    except Exception as e:
        return _failure(str(e))


def create_collage(images: List[str], cols: int, spacing: int, output: str) -> Dict[str, Any]:
    """Create a grid collage from a list of images."""
    try:
        if not images:
            raise ValueError("Image list cannot be empty")
        if cols < 1:
            raise ValueError("Columns must be >= 1")
            
        pills = [_load_pil(p) for p in images]
        rows = (len(pills) + cols - 1) // cols
        
        # Resize all to max dimensions for uniform cells
        max_w = max(img.width for img in pills)
        max_h = max(img.height for img in pills)
        
        canvas_w = cols * (max_w + spacing) - spacing
        canvas_h = rows * (max_h + spacing) - spacing
        collage = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
        
        for idx, img in enumerate(pills):
            img = img.convert("RGBA").resize((max_w, max_h), Image.Resampling.LANCZOS)
            r, c = divmod(idx, cols)
            x = c * (max_w + spacing)
            y = r * (max_h + spacing)
            collage.paste(img, (x, y), img)
            
        return save_image(collage, output, "PNG", 95)
    except Exception as e:
        return _failure(str(e))


def get_dominant_colors(filepath: str, count: int = 5) -> Dict[str, Any]:
    """Extract dominant colors using K-Means clustering."""
    try:
        img = _load_pil(filepath).convert("RGB")
        img_np = np.array(img)
        pixel_data = img_np.reshape((-1, 3)).astype(np.float32)
        
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 200, 0.1)
        _, labels, centers = cv2.kmeans(pixel_data, count, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        
        # Convert to hex and sort by hue using colorsys
        hex_colors = [f"#{int(c[0]):02x}{int(c[1]):02x}{int(c[2]):02x}" for c in centers]
        
        def sort_key(hex_code: str):
            r, g, b = int(hex_code[1:3], 16), int(hex_code[3:5], 16), int(hex_code[5:7], 16)
            h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
            return h  # Sort by hue
            
        sorted_colors = [c for _, c in sorted(zip(hex_colors, range(len(hex_colors))), key=lambda x: x[0])]
        final_hex = [hex_colors[i] for i in sorted(range(len(sorted_colors)), key=lambda x: sort_key(hex_colors[x]))]
            
        return _success(data={"colors": final_hex}, message="Dominant colors extracted")
    except Exception as e:
        return _failure(str(e))


def remove_background(filepath: str, output: str) -> Dict[str, Any]:
    """Remove image background using GrabCut."""
    try:
        img_cv = cv2.imread(str(Path(filepath).resolve()))
        if img_cv is None:
            raise ValueError("Failed to load image with OpenCV")
            
        h, w = img_cv.shape[:2]
        mask = np.zeros((h, w), np.uint8)
        bgd = np.zeros((1, 65), np.float64)
        fgd = np.zeros((1, 65), np.float64)
        
        # Assume foreground is in the center rectangle
        rect = (w // 10, h // 10, w * 8 // 10, h * 8 // 10)
        cv2.grabCut(img_cv, mask, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
        
        mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype("uint8")
        result = img_cv * mask2[:, :, np.newaxis]
        
        # Convert back to PIL and add alpha channel
        result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(result_rgb)
        mask_alpha = Image.fromarray((mask2 * 255).astype(np.uint8), mode="L")
        pil_img.putalpha(mask_alpha)
        
        return save_image(pil_img, output, "PNG", 95)
    except Exception as e:
        return _failure(str(e))


def add_watermark_text(filepath: str, text: str, position: Tuple[int, int], output: str) -> Dict[str, Any]:
    """Add semi-transparent text watermark."""
    try:
        img = _load_pil(filepath).convert("RGBA")
        txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)
        
        # Try standard fonts, fallback to default
        try:
            font = ImageFont.truetype("arial.ttf", int(img.width * 0.05))
        except (IOError, OSError):
            font = ImageFont.load_default()
            
        draw.text(position, text, font=font, fill=(255, 255, 255, 128))
        watermarked = Image.alpha_composite(img, txt_layer)
        return save_image(watermarked, output, "PNG", 95)
    except Exception as e:
        return _failure(str(e))


def batch_resize(directory: str, width: int, height: int, output_dir: str) -> Dict[str, Any]:
    """Resize all images in a directory and save to output directory."""
    try:
        src = Path(directory).resolve()
        dst = Path(output_dir).resolve()
        dst.mkdir(parents=True, exist_ok=True)
        
        if not src.is_dir():
            raise NotADirectoryError(f"Directory not found: {src}")
            
        supported = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}
        files = [f for f in src.iterdir() if f.suffix.lower() in supported]
        
        results = []
        for f in files:
            out_path = dst / f.name
            try:
                res = resize_image(str(f), width, height, str(out_path))
                results.append({"file": f.name, "success": res["success"], "error": res.get("error")})
            except Exception as e:
                results.append({"file": f.name, "success": False, "error": str(e)})
                
        return _success(data=results, message="Batch resize completed")
    except Exception as e:
        return _failure(str(e))


def image_to_base64(filepath: str) -> Dict[str, Any]:
    """Convert image file to base64 string."""
    try:
        p = Path(filepath).resolve()
        if not p.is_file():
            raise FileNotFoundError(f"File not found: {p}")
            
        with open(p, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            
        # Determine MIME type
        mime = "image/png"
        ext = p.suffix.lower()
        ext_to_mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
        mime = ext_to_mime.get(ext, mime)
        
        return _success(data={"base64": b64, "mime": mime}, message="Image encoded to base64")
    except Exception as e:
        return _failure(str(e))


def base64_to_image(b64_data: str, output: str) -> Dict[str, Any]:
    """Decode base64 string to image file."""
    try:
        # Handle data URI prefix if present
        if "," in b64_data:
            b64_data = b64_data.split(",", 1)[1]
            
        img_data = base64.b64decode(b64_data)
        p = Path(output).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(img_data)
        return _success(data={"path": str(p), "size": p.stat().st_size}, message="Base64 decoded to image")
    except Exception as e:
        return _failure(str(e))


def get_image_info(filepath: str) -> Dict[str, Any]:
    """Extract comprehensive image metadata."""
    try:
        img = _load_pil(filepath)
        p = Path(filepath).resolve()
        stat = p.stat()
        return _success(
            data={
                "path": str(p),
                "filename": p.name,
                "format": img.format,
                "mode": img.mode,
                "size": img.size,
                "width": img.width,
                "height": img.height,
                "file_size_bytes": stat.st_size,
                "channels": 3 if img.mode in ("RGB", "HSV") else 1 if img.mode == "L" else 4,
            },
            message="Image info retrieved"
        )
    except Exception as e:
        return _failure(str(e))


def compare_images(img1: str, img2: str) -> Dict[str, Any]:
    """Compare two images for structural/pixel similarity."""
    try:
        im1 = _load_pil(img1).convert("L").resize((256, 256))
        im2 = _load_pil(img2).convert("L").resize((256, 256))
        
        arr1 = np.array(im1).astype(float)
        arr2 = np.array(im2).astype(float)
        
        mse = np.mean((arr1 - arr2) ** 2)
        if mse == 0:
            similarity = 100.0
        else:
            max_pixel = 255.0
            similarity = max(0, 100 - np.sqrt(mse) / max_pixel * 100)
            
        return _success(data={"mse": float(mse), "similarity_percentage": float(similarity)}, 
                        message="Images compared")
    except Exception as e:
        return _failure(str(e))


def create_gif(images: List[str], output: str, duration: int) -> Dict[str, Any]:
    """Create an animated GIF from a list of images."""
    try:
        if not images:
            raise ValueError("Image list cannot be empty")
            
        frames = []
        for p in images:
            img = _load_pil(p).convert("RGB")
            frames.append(img)
            
        out_path = Path(output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        frames[0].save(
            str(out_path),
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=int(duration),
            loop=0,
            optimize=True
        )
        return _success(data={"path": str(out_path), "frames": len(frames), "size_bytes": out_path.stat().st_size},
                        message="GIF created successfully")
    except Exception as e:
        return _failure(str(e))