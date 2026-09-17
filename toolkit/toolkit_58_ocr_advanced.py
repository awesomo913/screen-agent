"""
toolkit_58_ocr_advanced.py
Advanced OCR operations: structured data extraction from screenshots,
table recognition, form field detection, number/date OCR,
and region-based recognition. Uses pytesseract + Pillow.
"""
from __future__ import annotations
import os
import re
from typing import Any, Dict, List

try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

def check_ocr() -> Dict[str, Any]:
    return {"success": True, "data": {"pytesseract": HAS_OCR, "mss": HAS_MSS}, "error": None}

def _preprocess(img, enhance: bool = True):
    """Preprocess image for better OCR accuracy."""
    img = img.convert("L")
    if enhance:
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = img.filter(ImageFilter.SHARPEN)
    return img

def read_text_from_image(image_path: str, lang: str = "eng", enhance: bool = True) -> Dict[str, Any]:
    try:
        if not HAS_OCR:
            return {"success": False, "data": None, "error": "pytesseract not installed"}
        img = Image.open(image_path)
        img = _preprocess(img, enhance)
        text = pytesseract.image_to_string(img, lang=lang)
        return {"success": True, "data": {"text": text.strip(), "chars": len(text.strip())}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def read_text_from_region(x: int, y: int, width: int, height: int, lang: str = "eng") -> Dict[str, Any]:
    try:
        if not HAS_OCR or not HAS_MSS:
            return {"success": False, "data": None, "error": "pytesseract and mss required"}
        with mss.mss() as sct:
            region = {"top": y, "left": x, "width": width, "height": height}
            screenshot = sct.grab(region)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        img = _preprocess(img)
        text = pytesseract.image_to_string(img, lang=lang)
        return {"success": True, "data": {"text": text.strip(), "region": {"x": x, "y": y, "w": width, "h": height}}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def read_numbers_from_image(image_path: str) -> Dict[str, Any]:
    try:
        if not HAS_OCR:
            return {"success": False, "data": None, "error": "pytesseract not installed"}
        img = Image.open(image_path)
        img = _preprocess(img)
        config = r"--oem 3 --psm 6 outputbase digits"
        text = pytesseract.image_to_string(img, config=config)
        numbers = re.findall(r"-?\d+\.?\d*", text)
        return {"success": True, "data": {"numbers": [float(n) for n in numbers], "raw_text": text.strip()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_ocr_data(image_path: str, lang: str = "eng") -> Dict[str, Any]:
    """Get detailed OCR data with word positions and confidence scores."""
    try:
        if not HAS_OCR:
            return {"success": False, "data": None, "error": "pytesseract not installed"}
        img = Image.open(image_path)
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
        words = []
        for i, word in enumerate(data["text"]):
            if word.strip() and int(data["conf"][i]) > 0:
                words.append({
                    "text": word,
                    "conf": int(data["conf"][i]),
                    "x": data["left"][i],
                    "y": data["top"][i],
                    "w": data["width"][i],
                    "h": data["height"][i]
                })
        return {"success": True, "data": {"words": words, "count": len(words)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_text_location(image_path: str, search_text: str, lang: str = "eng") -> Dict[str, Any]:
    """Find where specific text appears in an image."""
    try:
        if not HAS_OCR:
            return {"success": False, "data": None, "error": "pytesseract not installed"}
        r = get_ocr_data(image_path, lang)
        if not r["success"]:
            return r
        matches = [w for w in r["data"]["words"] if search_text.lower() in w["text"].lower()]
        return {"success": True, "data": {"matches": matches, "count": len(matches)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def screenshot_and_read_text(lang: str = "eng") -> Dict[str, Any]:
    """Take full screenshot and extract all text."""
    try:
        if not HAS_OCR or not HAS_MSS:
            return {"success": False, "data": None, "error": "pytesseract and mss required"}
        with mss.mss() as sct:
            screen = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", screen.size, screen.bgra, "raw", "BGRX")
        img = _preprocess(img)
        text = pytesseract.image_to_string(img, lang=lang)
        return {"success": True, "data": {"text": text.strip(), "chars": len(text.strip())}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_table_from_image(image_path: str) -> Dict[str, Any]:
    """Attempt to extract table structure from an image via OCR."""
    try:
        if not HAS_OCR:
            return {"success": False, "data": None, "error": "pytesseract not installed"}
        img = Image.open(image_path)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        rows: dict = {}
        for i, word in enumerate(data["text"]):
            if word.strip():
                row_key = data["top"][i] // 20
                if row_key not in rows:
                    rows[row_key] = []
                rows[row_key].append({"text": word, "x": data["left"][i]})
        table = []
        for row_key in sorted(rows.keys()):
            row = sorted(rows[row_key], key=lambda w: w["x"])
            table.append([w["text"] for w in row])
        return {"success": True, "data": {"rows": len(table), "table": table}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def read_handwriting(image_path: str) -> Dict[str, Any]:
    """OCR optimized for handwritten text."""
    try:
        if not HAS_OCR:
            return {"success": False, "data": None, "error": "pytesseract not installed"}
        img = Image.open(image_path)
        img = ImageOps.grayscale(img)
        img = ImageEnhance.Contrast(img).enhance(3.0)
        img = img.filter(ImageFilter.SMOOTH)
        text = pytesseract.image_to_string(img, config="--oem 1 --psm 3")
        return {"success": True, "data": {"text": text.strip()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def batch_ocr_folder(folder: str, lang: str = "eng", output_folder: str = "") -> Dict[str, Any]:
    try:
        if not HAS_OCR:
            return {"success": False, "data": None, "error": "pytesseract not installed"}
        exts = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
        results = []
        for f in os.listdir(folder):
            if any(f.lower().endswith(e) for e in exts):
                fp = os.path.join(folder, f)
                r = read_text_from_image(fp, lang)
                result = {"file": f, "text": r["data"]["text"] if r["success"] else "", "success": r["success"]}
                results.append(result)
                if output_folder and r["success"]:
                    os.makedirs(output_folder, exist_ok=True)
                    txt_path = os.path.join(output_folder, os.path.splitext(f)[0] + ".txt")
                    with open(txt_path, "w", encoding="utf-8") as tf:
                        tf.write(r["data"]["text"])
        return {"success": True, "data": {"processed": len(results), "results": results}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_available_languages() -> Dict[str, Any]:
    try:
        if not HAS_OCR:
            return {"success": False, "data": None, "error": "pytesseract not installed"}
        langs = pytesseract.get_languages(config="")
        return {"success": True, "data": langs, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
