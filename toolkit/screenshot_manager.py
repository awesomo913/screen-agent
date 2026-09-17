"""
Screenshot Manager – a tiny “screen‑agent” toolkit.

Provides a rich set of utilities for capturing, processing and analysing
screenshots. All public functions return a ``dict`` with (at least) the
following keys:

* ``success`` – ``bool`` indicating whether the operation succeeded.
* ``path``    – path to the generated file (if any).
* ``data``    – auxiliary data such as base64 strings, OCR text, etc.
* ``error``   – human‑readable error message when ``success`` is ``False``.

The implementation is deliberately defensive: every external call is
wrapped in ``try/except`` blocks and the caller never receives an uncaught
exception.
"""

# --------------------------------------------------------------------------- #
# Imports
# --------------------------------------------------------------------------- #
from __future__ import annotations

import base64
import io
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple, Union

import cv2
import numpy as np
import mss
import mss.tools
import pyautogui
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance

# optional OCR – fails gracefully if pytesseract is not installed
try:
    import pytesseract  # type: ignore
except Exception:  # pragma: no cover
    pytesseract = None  # type: ignore

# --------------------------------------------------------------------------- #
# Helper utilities
# --------------------------------------------------------------------------- #


def _ensure_dir(path: Union[str, Path]) -> None:
    """Create parent directories if they do not exist."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)


def _to_path(path: Union[str, Path]) -> Path:
    return Path(path).expanduser().resolve()


def _pil_image_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _base64_encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _load_image(path: Union[str, Path]) -> Image.Image:
    return Image.open(_to_path(path)).convert("RGB")


def _as_numpy(img: Image.Image) -> np.ndarray:
    return np.array(img)


def _return(success: bool, *, path: Union[str, Path, None] = None,
            data: Any = None, error: str | None = None) -> Dict[str, Any]:
    """Standardised return dictionary."""
    return {
        "success": success,
        "path": str(path) if path else None,
        "data": data,
        "error": error,
    }


# --------------------------------------------------------------------------- #
# Core screenshot functions
# --------------------------------------------------------------------------- #


def take_screenshot(region: Tuple[int, int, int, int],
                    output_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Capture a region of the primary monitor.

    Parameters
    ----------
    region: (left, top, width, height)
    output_path: where to store the PNG file.

    Returns
    -------
    dict – ``success`` and ``path``.
    """
    try:
        _ensure_dir(output_path)
        with mss.mss() as sct:
            monitor = {"left": region[0],
                       "top": region[1],
                       "width": region[2],
                       "height": region[3]}
            img = sct.grab(monitor)
            mss.tools.to_png(img.rgb, img.size, output=_to_path(output_path))
        return _return(True, path=output_path)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def take_full_screenshot(output_path: Union[str, Path]) -> Dict[str, Any]:
    """Capture the whole primary monitor."""
    try:
        _ensure_dir(output_path)
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # 0 = all monitors, 1 = primary
            img = sct.grab(monitor)
            mss.tools.to_png(img.rgb, img.size, output=_to_path(output_path))
        return _return(True, path=output_path)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def screenshot_active_window(output_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Capture the currently active (foreground) window using *pyautogui*.

    Note
    ----
    This works on Windows/macOS/Linux where the OS supplies a
    ``pyautogui.getActiveWindow``‑like API.  On platforms where this is not
    available the function falls back to a full‑screen capture.
    """
    try:
        _ensure_dir(output_path)
        # pyautogui does not expose active‑window geometry directly,
        # but the ``window`` module (available on recent versions) does.
        win = pyautogui.getActiveWindow()
        if win is None:  # pragma: no cover
            # fallback – capture the full screen
            return take_full_screenshot(output_path)

        region = (win.left, win.top, win.width, win.height)
        return take_screenshot(region, output_path)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def screenshot_monitor(monitor_index: int,
                       output_path: Union[str, Path]) -> Dict[str, Any]:
    """Capture an arbitrary monitor (0 = all monitors)."""
    try:
        _ensure_dir(output_path)
        with mss.mss() as sct:
            if monitor_index < 0 or monitor_index >= len(sct.monitors):
                raise ValueError("Invalid monitor index.")
            monitor = sct.monitors[monitor_index]
            img = sct.grab(monitor)
            mss.tools.to_png(img.rgb, img.size, output=_to_path(output_path))
        return _return(True, path=output_path)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def screenshot_element(driver: Any,
                       selector: str,
                       output_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Take a screenshot of a Selenium element.

    Parameters
    ----------
    driver: Selenium WebDriver instance.
    selector: CSS selector (or XPath) that uniquely identifies the element.
    output_path: destination PNG.

    Returns
    -------
    dict – ``success`` and ``path``.
    """
    try:
        _ensure_dir(output_path)

        # Selenium can give us a PNG of the whole page.
        png = driver.get_screenshot_as_png()
        page_img = Image.open(io.BytesIO(png)).convert("RGB")

        # Locate the element.
        element = driver.find_element_by_css_selector(selector)
        location = element.location_once_scrolled_into_view
        size = element.size
        left = int(location["x"])
        top = int(location["y"])
        right = left + int(size["width"])
        bottom = top + int(size["height"])

        cropped = page_img.crop((left, top, right, bottom))
        cropped.save(_to_path(output_path), format="PNG")
        return _return(True, path=output_path)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def screenshot_to_base64(region: Tuple[int, int, int, int]) -> Dict[str, Any]:
    """
    Capture a region and return the image as a base64‑encoded string.

    Returns
    -------
    dict – ``success`` and ``data`` (the base64 string).
    """
    try:
        with mss.mss() as sct:
            monitor = {"left": region[0],
                       "top": region[1],
                       "width": region[2],
                       "height": region[3]}
            img = sct.grab(monitor)
            raw = _pil_image_to_bytes(Image.frombytes("RGB", img.size, img.rgb))
            b64 = _base64_encode(raw)
        return _return(True, data=b64)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


# --------------------------------------------------------------------------- #
# Image comparison / detection utilities
# --------------------------------------------------------------------------- #


def compare_screenshots(img1_path: Union[str, Path],
                        img2_path: Union[str, Path],
                        threshold: float = 0.01) -> Dict[str, Any]:
    """
    Compute a simple pixel‑wise difference ratio.

    ``threshold`` is the maximum allowed ratio of differing pixels.
    """
    try:
        img1 = cv2.imread(str(_to_path(img1_path)), cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imread(str(_to_path(img2_path)), cv2.IMREAD_GRAYSCALE)

        if img1 is None or img2 is None:
            raise FileNotFoundError("One of the images could not be read.")

        if img1.shape != img2.shape:
            raise ValueError("Images must have identical dimensions.")

        diff = cv2.absdiff(img1, img2)
        non_zero = np.count_nonzero(diff)
        total = diff.size
        ratio = non_zero / total

        data = {"diff_ratio": ratio, "within_threshold": ratio <= threshold}
        return _return(True, data=data)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def find_image_on_screen(template_path: Union[str, Path],
                         confidence: float = 0.8) -> Dict[str, Any]:
    """
    Locate a template image on the current screen using OpenCV template
    matching. Returns the top‑left corner of the best match.
    """
    try:
        # capture full screen
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            img = sct.grab(monitor)
            screenshot = np.array(Image.frombytes("RGB", img.size, img.rgb))

        template = cv2.imread(str(_to_path(template_path)), cv2.IMREAD_COLOR)
        if template is None:
            raise FileNotFoundError("Template image not found.")

        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val < confidence:
            return _return(False, error="Template not found with required confidence.")

        top_left = max_loc
        w, h = template.shape[1], template.shape[0]
        data = {"position": {"x": top_left[0], "y": top_left[1], "w": w, "h": h},
                "confidence": float(max_val)}
        return _return(True, data=data)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def wait_for_image(template_path: Union[str, Path],
                   timeout: float = 10.0,
                   interval: float = 0.5) -> Dict[str, Any]:
    """
    Poll the screen until ``template_path`` appears or ``timeout`` expires.
    """
    start = time.time()
    while time.time() - start < timeout:
        found = find_image_on_screen(template_path, confidence=0.8)
        if found["success"]:
            return found
        time.sleep(interval)
    return _return(False, error="Timeout waiting for image.")


# --------------------------------------------------------------------------- #
# Image processing utilities
# --------------------------------------------------------------------------- #


def crop_screenshot(image_path: Union[str, Path],
                    box: Tuple[int, int, int, int],
                    output: Union[str, Path]) -> Dict[str, Any]:
    """Crop ``image_path`` to ``box`` = (left, top, right, bottom)."""
    try:
        _ensure_dir(output)
        img = _load_image(image_path)
        cropped = img.crop(box)
        cropped.save(_to_path(output), format="PNG")
        return _return(True, path=output)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def resize_screenshot(image_path: Union[str, Path],
                      size: Tuple[int, int],
                      output: Union[str, Path]) -> Dict[str, Any]:
    """Resize the image to ``size`` (width, height)."""
    try:
        _ensure_dir(output)
        img = _load_image(image_path)
        resized = img.resize(size, Image.LANCZOS)
        resized.save(_to_path(output), format="PNG")
        return _return(True, path=output)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def annotate_screenshot(image_path: Union[str, Path],
                        annotations: List[Dict[str, Any]],
                        output: Union[str, Path]) -> Dict[str, Any]:
    """
    Draw geometric annotations on ``image_path``.

    Each annotation dict must contain a ``type`` key (``'rect'``, ``'ellipse'``,
    ``'line'``) and the corresponding geometry fields.
    """
    try:
        _ensure_dir(output)
        img = _load_image(image_path).convert("RGBA")
        draw = ImageDraw.Draw(img)

        for ann in annotations:
            typ = ann.get("type")
            if typ == "rect":
                draw.rectangle(ann["bbox"], outline=ann.get("color", "red"),
                               width=ann.get("width", 3))
            elif typ == "ellipse":
                draw.ellipse(ann["bbox"], outline=ann.get("color", "blue"),
                             width=ann.get("width", 3))
            elif typ == "line":
                draw.line(ann["points"], fill=ann.get("color", "green"),
                          width=ann.get("width", 2))
            else:
                raise ValueError(f"Unsupported annotation type: {typ}")

        img.save(_to_path(output), format="PNG")
        return _return(True, path=output)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def highlight_region(image_path: Union[str, Path],
                    region: Tuple[int, int, int, int],
                    color: str = "yellow",
                    output: Union[str, Path] = None) -> Dict[str, Any]:
    """
    Draw a semi‑transparent rectangle over ``region``.
    ``region`` = (left, top, right, bottom).
    """
    try:
        out_path = output or Path(image_path).with_name("highlighted.png")
        _ensure_dir(out_path)

        img = _load_image(image_path).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle(region, fill=ImageColor.getrgb(color) + (80,))

        combined = Image.alpha_composite(img, overlay)
        combined.save(_to_path(out_path), format="PNG")
        return _return(True, path=out_path)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def add_text_overlay(image_path: Union[str, Path],
                     text: str,
                     position: Tuple[int, int],
                     output: Union[str, Path]) -> Dict[str, Any]:
    """
    Render ``text`` onto ``image_path`` at ``position``.
    Uses a default TrueType font; falls back to a basic bitmap font if not found.
    """
    try:
        _ensure_dir(output)
        img = _load_image(image_path).convert("RGBA")
        draw = ImageDraw.Draw(img)

        # Try a common TrueType font, otherwise fall back.
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except Exception:
            font = ImageFont.load_default()

        draw.text(position, text, font=font, fill=(255, 255, 255, 255))
        img.save(_to_path(output), format="PNG")
        return _return(True, path=output)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def screenshot_diff(before_path: Union[str, Path],
                   after_path: Union[str, Path],
                   output: Union[str, Path]) -> Dict[str, Any]:
    """
    Produce a visual diff between two screenshots (highlights changed pixels).
    """
    try:
        _ensure_dir(output)
        img1 = _load_image(before_path)
        img2 = _load_image(after_path)

        if img1.size != img2.size:
            raise ValueError("Images must share the same dimensions.")

        diff = ImageChops.difference(img1, img2)
        # Amplify difference for visibility
        enhanced = ImageEnhance.Brightness(diff).enhance(2.0)
        enhanced.save(_to_path(output), format="PNG")
        return _return(True, path=output)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def capture_scrolling_screenshot(driver: Any,
                                 output: Union[str, Path]) -> Dict[str, Any]:
    """
    Stitch together a full‑page screenshot by scrolling the page.
    Works only with browsers that expose ``window.scrollBy``.
    """
    try:
        _ensure_dir(output)

        # First, get page height
        total_height = driver.execute_script(
            "return Math.max(document.body.scrollHeight, "
            "document.documentElement.scrollHeight,"
            "document.body.offsetHeight, document.documentElement.offsetHeight,"
            "document.body.clientHeight, document.documentElement.clientHeight);"
        )
        viewport_height = driver.execute_script("return window.innerHeight;")
        stitched = Image.new("RGB", (driver.get_window_size()["width"], total_height))
        offset = 0

        while offset < total_height:
            driver.execute_script(f"window.scrollTo(0, {offset});")
            time.sleep(0.3)  # give the browser time to render
            png = driver.get_screenshot_as_png()
            img = Image.open(io.BytesIO(png)).convert("RGB")
            stitched.paste(img, (0, offset))
            offset += viewport_height

        stitched.save(_to_path(output), format="PNG")
        return _return(True, path=output)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def record_screen_region(region: Tuple[int, int, int, int],
                         duration: float,
                         output: Union[str, Path],
                         fps: int = 10) -> Dict[str, Any]:
    """
    Record a short video of ``region`` for ``duration`` seconds.
    The result is an MP4 file encoded with OpenCV.
    """
    try:
        _ensure_dir(output)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        width, height = region[2], region[3]
        out = cv2.VideoWriter(str(_to_path(output)), fourcc, fps, (width, height))

        frames = int(duration * fps)
        with mss.mss() as sct:
            monitor = {"left": region[0],
                       "top": region[1],
                       "width": width,
                       "height": height}
            for _ in range(frames):
                img = sct.grab(monitor)
                frame = np.array(Image.frombytes("RGB", img.size, img.rgb))
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                out.write(frame)
                time.sleep(1 / fps)

        out.release()
        return _return(True, path=output)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def ocr_screenshot(image_path: Union[str, Path],
                   lang: str = "eng") -> Dict[str, Any]:
    """
    Run Tesseract OCR on the supplied image. Returns the extracted text.
    """
    if pytesseract is None:  # pragma: no cover
        return _return(False, error="pytesseract not installed.")
    try:
        img = _load_image(image_path)
        text = pytesseract.image_to_string(img, lang=lang)
        return _return(True, data=text)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def detect_ui_elements(image_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Very naïve UI element detection using Canny edges + contour analysis.
    Returns a list of bounding boxes.
    """
    try:
        img = cv2.imread(str(_to_path(image_path)), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise FileNotFoundError("Image could not be read.")
        edged = cv2.Canny(img, 50, 150)
        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        boxes = [cv2.boundingRect(c) for c in contours]
        data = [{"x": int(x), "y": int(y), "w": int(w), "h": int(h)} for x, y, w, h in boxes]
        return _return(True, data=data)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def batch_screenshots(regions: List[Tuple[int, int, int, int]],
                     output_dir: Union[str, Path]) -> Dict[str, Any]:
    """
    Capture many regions in one go. Returns the list of generated file paths.
    """
    try:
        out_dir = _to_path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        with mss.mss() as sct:
            for idx, region in enumerate(regions):
                monitor = {"left": region[0],
                           "top": region[1],
                           "width": region[2],
                           "height": region[3]}
                img = sct.grab(monitor)
                file_path = out_dir / f"screenshot_{idx}.png"
                mss.tools.to_png(img.rgb, img.size, output=file_path)
                paths.append(str(file_path))
        return _return(True, data=paths)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def timed_screenshots(interval: float,
                     count: int,
                     output_dir: Union[str, Path]) -> Dict[str, Any]:
    """
    Take ``count`` screenshots spaced by ``interval`` seconds.
    """
    try:
        out_dir = _to_path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            for i in range(count):
                img = sct.grab(monitor)
                ts = int(time.time() * 1000)
                file_path = out_dir / f"timed_{i}_{ts}.png"
                mss.tools.to_png(img.rgb, img.size, output=file_path)
                paths.append(str(file_path))
                if i < count - 1:
                    time.sleep(interval)
        return _return(True, data=paths)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def screenshot_to_pdf(image_paths: List[Union[str, Path]],
                     output: Union[str, Path]) -> Dict[str, Any]:
    """
    Convert a list of images to a single PDF file.
    """
    try:
        _ensure_dir(output)
        pil_images = [_load_image(p).convert("RGB") for p in image_paths]
        if not pil_images:
            raise ValueError("No images supplied.")
        first, rest = pil_images[0], pil_images[1:]
        first.save(_to_path(output), save_all=True, append_images=rest)
        return _return(True, path=output)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def get_pixel_color(x: int, y: int) -> Dict[str, Any]:
    """
    Return the colour of a screen pixel as an (R, G, B) tuple.
    """
    try:
        rgb = pyautogui.pixel(x, y)  # returns (R, G, B)
        return _return(True, data={"r": rgb[0], "g": rgb[1], "b": rgb[2]})
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def measure_element(image_path: Union[str, Path],
                    region: Tuple[int, int, int, int]) -> Dict[str, Any]:
    """
    Return width & height of a given ``region`` inside ``image_path``.
    """
    try:
        img = _load_image(image_path)
        left, top, right, bottom = region
        width = right - left
        height = bottom - top
        return _return(True, data={"width": width, "height": height})
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))


def create_thumbnail(image_path: Union[str, Path],
                    size: Tuple[int, int],
                    output: Union[str, Path]) -> Dict[str, Any]:
    """
    Generate a thumbnail of ``size`` (max width, max height) preserving aspect.
    """
    try:
        _ensure_dir(output)
        img = _load_image(image_path)
        img.thumbnail(size, Image.ANTIALIAS)
        img.save(_to_path(output), format="PNG")
        return _return(True, path=output)
    except Exception as exc:  # pragma: no cover
        return _return(False, error=str(exc))