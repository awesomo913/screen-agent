"""
clipboard_image_tools.py - In-place clipboard image manipulation.

Operates directly on the Windows clipboard image (DIB format) without
requiring files on disk.  Useful for quick edits: grab a screenshot,
resize / crop / rotate / blur it, then paste directly.

Dependencies: Pillow, pywin32
"""

import io
import base64
from typing import Dict, Any, Optional, Tuple, Union

try:
    from PIL import Image, ImageOps, ImageStat, ImageFilter, ImageGrab
except ImportError:
    Image = None
    ImageGrab = None
    ImageOps = None
    ImageStat = None
    ImageFilter = None

try:
    import win32clipboard
    import win32con
except ImportError:
    win32clipboard = None
    win32con = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data: Any = None, message: str = "OK") -> Dict[str, Any]:
    return {"success": True, "data": data, "error": None, "message": message}


def _err(error: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "error": error, "message": error}


def _check_deps() -> Optional[Dict[str, Any]]:
    """Return an error dict if dependencies are missing, else None."""
    if Image is None or ImageGrab is None:
        return _err("Pillow library is not installed or fully available.")
    if win32clipboard is None or win32con is None:
        return _err("pywin32 library is not installed or fully available.")
    return None


def _get_image() -> "Image.Image":
    """Grab the current clipboard image.  Raises on failure."""
    img = ImageGrab.grabclipboard()
    if img is None:
        raise ValueError("No image found in clipboard.")
    if isinstance(img, list):
        raise ValueError("Clipboard contains file paths, not image data.")
    return img


def _set_image(img: "Image.Image") -> None:
    """Write a PIL Image into the clipboard as DIB."""
    output = io.BytesIO()
    img.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]  # strip BMP file header → raw DIB
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, data)
    finally:
        win32clipboard.CloseClipboard()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_clipboard_image_size() -> Dict[str, Any]:
    """Get the width and height of the clipboard image."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        img = _get_image()
        w, h = img.size
        return _ok(data={"width": w, "height": h}, message=f"Clipboard image is {w}x{h}")
    except Exception as e:
        return _err(str(e))


def has_image_in_clipboard() -> Dict[str, Any]:
    """Check whether the clipboard currently holds an image."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        _get_image()
        return _ok(data={"has_image": True}, message="Clipboard contains an image")
    except ValueError:
        return _ok(data={"has_image": False}, message="No image in clipboard")
    except Exception as e:
        return _err(str(e))


def save_clipboard_image(filepath: str, image_format: str = "PNG") -> Dict[str, Any]:
    """Save the current clipboard image to a file."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        img = _get_image()
        img.save(filepath, format=image_format.upper())
        return _ok(data={"filepath": filepath, "format": image_format},
                   message=f"Clipboard image saved to {filepath}")
    except Exception as e:
        return _err(str(e))


def load_image_to_clipboard(filepath: str) -> Dict[str, Any]:
    """Load an image file into the Windows clipboard."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        img = Image.open(filepath)
        _set_image(img)
        return _ok(data={"filepath": filepath, "size": img.size},
                   message=f"Image loaded to clipboard from {filepath}")
    except Exception as e:
        return _err(str(e))


def get_clipboard_image_base64(image_format: str = "PNG") -> Dict[str, Any]:
    """Return the clipboard image encoded as a base64 string."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        img = _get_image()
        buf = io.BytesIO()
        img.save(buf, format=image_format.upper())
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return _ok(data={"base64": b64, "format": image_format},
                   message="Clipboard image encoded to base64")
    except Exception as e:
        return _err(str(e))


def set_clipboard_image_base64(b64_string: str) -> Dict[str, Any]:
    """Decode a base64 string and place the image in the clipboard."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        image_data = base64.b64decode(b64_string)
        img = Image.open(io.BytesIO(image_data))
        _set_image(img)
        return _ok(data={"size": img.size}, message="Base64 image set in clipboard")
    except Exception as e:
        return _err(str(e))


def resize_clipboard_image(width: int, height: int) -> Dict[str, Any]:
    """Resize the clipboard image in-place."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        if width <= 0 or height <= 0:
            return _err("Width and height must be strictly positive.")
        img = _get_image()
        resized = img.resize((width, height), Image.Resampling.LANCZOS)
        _set_image(resized)
        return _ok(data={"new_width": width, "new_height": height},
                   message=f"Clipboard image resized to {width}x{height}")
    except Exception as e:
        return _err(str(e))


def crop_clipboard_image(left: int, top: int, right: int, bottom: int) -> Dict[str, Any]:
    """Crop the clipboard image in-place."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        if left >= right or top >= bottom:
            return _err("Invalid crop dimensions (left < right and top < bottom required).")
        img = _get_image()
        cropped = img.crop((left, top, right, bottom))
        _set_image(cropped)
        return _ok(data={"left": left, "top": top, "right": right, "bottom": bottom},
                   message="Clipboard image cropped")
    except Exception as e:
        return _err(str(e))


def rotate_clipboard_image(degrees: int) -> Dict[str, Any]:
    """Rotate the clipboard image in-place (counter-clockwise)."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        img = _get_image()
        rotated = img.rotate(degrees, expand=True)
        _set_image(rotated)
        return _ok(data={"degrees": degrees}, message=f"Clipboard image rotated {degrees}°")
    except Exception as e:
        return _err(str(e))


def flip_clipboard_image_horizontal() -> Dict[str, Any]:
    """Mirror the clipboard image horizontally."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        img = _get_image()
        _set_image(ImageOps.mirror(img))
        return _ok(data={"flipped": "horizontal"}, message="Clipboard image flipped horizontally")
    except Exception as e:
        return _err(str(e))


def flip_clipboard_image_vertical() -> Dict[str, Any]:
    """Flip the clipboard image vertically."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        img = _get_image()
        _set_image(ImageOps.flip(img))
        return _ok(data={"flipped": "vertical"}, message="Clipboard image flipped vertically")
    except Exception as e:
        return _err(str(e))


def convert_clipboard_image_to_grayscale() -> Dict[str, Any]:
    """Convert the clipboard image to grayscale in-place."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        img = _get_image()
        gray = img.convert("L")
        _set_image(gray)
        return _ok(data={"converted": "grayscale"}, message="Clipboard image converted to grayscale")
    except Exception as e:
        return _err(str(e))


def get_clipboard_image_average_color() -> Dict[str, Any]:
    """Return the average (mean) RGB colour of the clipboard image."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        img = _get_image().convert("RGB")
        stat = ImageStat.Stat(img)
        r, g, b = [int(m) for m in stat.mean]
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        return _ok(data={"r": r, "g": g, "b": b, "hex": hex_color},
                   message=f"Average colour: ({r}, {g}, {b})")
    except Exception as e:
        return _err(str(e))


def invert_clipboard_image_colors() -> Dict[str, Any]:
    """Invert (negate) the colours of the clipboard image."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        img = _get_image().convert("RGB")
        inverted = ImageOps.invert(img)
        _set_image(inverted)
        return _ok(data={"inverted": True}, message="Clipboard image colours inverted")
    except Exception as e:
        return _err(str(e))


def blur_clipboard_image(radius: int = 3) -> Dict[str, Any]:
    """Apply Gaussian blur to the clipboard image."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        if radius <= 0:
            return _err("Radius must be strictly positive.")
        img = _get_image()
        blurred = img.filter(ImageFilter.GaussianBlur(radius))
        _set_image(blurred)
        return _ok(data={"blurred_radius": radius}, message=f"Clipboard image blurred (r={radius})")
    except Exception as e:
        return _err(str(e))


def add_clipboard_image_border(border_size: int, color: str = "#000000") -> Dict[str, Any]:
    """Add a solid-colour border around the clipboard image."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        if border_size <= 0:
            return _err("Border size must be strictly positive.")
        img = _get_image()
        bordered = ImageOps.expand(img, border=border_size, fill=color)
        _set_image(bordered)
        return _ok(data={"border_size": border_size, "color": color},
                   message=f"Border ({border_size}px, {color}) added")
    except Exception as e:
        return _err(str(e))


def create_blank_image_in_clipboard(width: int, height: int, color: str = "#FFFFFF") -> Dict[str, Any]:
    """Place a blank solid-colour image into the clipboard."""
    dep = _check_deps()
    if dep:
        return dep
    try:
        if width <= 0 or height <= 0:
            return _err("Width and height must be strictly positive.")
        img = Image.new("RGB", (width, height), color)
        _set_image(img)
        return _ok(data={"width": width, "height": height, "color": color},
                   message=f"Blank {width}x{height} image ({color}) placed in clipboard")
    except Exception as e:
        return _err(str(e))
