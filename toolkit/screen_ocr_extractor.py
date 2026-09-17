#!/usr/bin/env python3
"""Screen OCR Text Extractor - Extract and process text from any screen area
Select regions, extract text, translate, save to clipboard, monitor for changes.
Works with any application - games, PDFs, images, foreign language apps.
"""

import pyautogui
import time
import sys
import json
import logging
import argparse
import threading
from pathlib import Path
from datetime import datetime
try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
try:
    import pyperclip
    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ScreenOCR")


class OCRPreprocessor:
    """Image preprocessing to improve OCR accuracy."""

    @staticmethod
    def enhance_contrast(image, factor=2.0):
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(factor)

    @staticmethod
    def enhance_sharpness(image, factor=2.0):
        enhancer = ImageEnhance.Sharpness(image)
        return enhancer.enhance(factor)

    @staticmethod
    def grayscale(image):
        return image.convert("L")

    @staticmethod
    def threshold(image, thresh=128):
        gray = image.convert("L")
        return gray.point(lambda x: 255 if x > thresh else 0, "1")

    @staticmethod
    def invert(image):
        if HAS_CV2:
            arr = np.array(image)
            inverted = cv2.bitwise_not(arr)
            return Image.fromarray(inverted)
        from PIL import ImageOps
        return ImageOps.invert(image.convert("RGB"))

    @staticmethod
    def scale_up(image, factor=2):
        w, h = image.size
        return image.resize((w * factor, h * factor), Image.LANCZOS)

    @staticmethod
    def denoise(image):
        if HAS_CV2:
            arr = np.array(image)
            denoised = cv2.fastNlMeansDenoisingColored(arr, None, 10, 10, 7, 21)
            return Image.fromarray(denoised)
        return image.filter(ImageFilter.MedianFilter(3))

    @staticmethod
    def deskew(image):
        if not HAS_CV2:
            return image
        arr = np.array(image)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
        if lines is None:
            return image
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2-y1, x2-x1))
            if abs(angle) < 45:
                angles.append(angle)
        if not angles:
            return image
        median_angle = np.median(angles)
        h, w = arr.shape[:2]
        center = (w//2, h//2)
        matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(arr, matrix, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return Image.fromarray(rotated)


class ScreenOCR:
    """Main screen OCR text extraction engine."""

    def __init__(self, lang="eng", tesseract_path=None):
        if not HAS_OCR:
            raise ImportError("pytesseract and Pillow required")
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        self.lang = lang
        self.preprocessor = OCRPreprocessor()
        self.extraction_history = []

    def capture_region(self, x, y, width, height):
        """Capture a screen region as PIL Image."""
        return pyautogui.screenshot(region=(x, y, width, height))

    def capture_fullscreen(self):
        """Capture the entire screen."""
        return pyautogui.screenshot()

    def interactive_select_region(self):
        """Let user select a region by clicking two corners."""
        print("Click the TOP-LEFT corner of the region...")
        while True:
            if pyautogui.mouseDown():
                x1, y1 = pyautogui.position()
                break
            time.sleep(0.05)
        time.sleep(0.5)
        print("Click the BOTTOM-RIGHT corner of the region...")
        while True:
            if pyautogui.mouseDown():
                x2, y2 = pyautogui.position()
                break
            time.sleep(0.05)
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        x = min(x1, x2)
        y = min(y1, y2)
        return (x, y, width, height)

    def extract_text(self, image, preprocess=True, config=""):
        """Extract text from an image with optional preprocessing."""
        if preprocess:
            image = self.preprocessor.enhance_contrast(image)
            image = self.preprocessor.enhance_sharpness(image)
            image = self.preprocessor.scale_up(image)
        text = pytesseract.image_to_string(image, lang=self.lang, config=config)
        self.extraction_history.append({
            "timestamp": datetime.now().isoformat(),
            "text": text.strip(),
            "chars": len(text.strip())
        })
        return text.strip()

    def extract_structured(self, image, preprocess=True):
        """Extract text with position data."""
        if preprocess:
            image = self.preprocessor.enhance_contrast(image)
            image = self.preprocessor.scale_up(image)
        data = pytesseract.image_to_data(image, lang=self.lang, output_type=pytesseract.Output.DICT)
        results = []
        for i in range(len(data["text"])):
            if data["text"][i].strip() and data["conf"][i] > 30:
                results.append({
                    "text": data["text"][i].strip(),
                    "x": data["left"][i], "y": data["top"][i],
                    "width": data["width"][i], "height": data["height"][i],
                    "confidence": data["conf"][i],
                    "block": data["block_num"][i],
                    "line": data["line_num"][i],
                    "word": data["word_num"][i]
                })
        return results

    def extract_from_region(self, x, y, width, height, preprocess=True):
        """Extract text from a specific screen region."""
        image = self.capture_region(x, y, width, height)
        return self.extract_text(image, preprocess=preprocess)

    def extract_numbers(self, image):
        """Extract only numbers from image."""
        config = "--psm 7 -c tessedit_char_whitelist=0123456789.,- "
        return self.extract_text(image, config=config)

    def extract_to_clipboard(self, x, y, width, height):
        """Extract text from region and copy to clipboard."""
        text = self.extract_from_region(x, y, width, height)
        if HAS_CLIPBOARD and text:
            pyperclip.copy(text)
            logger.info(f"Copied {len(text)} chars to clipboard")
        return text

    def batch_extract(self, regions):
        """Extract text from multiple regions."""
        results = []
        for region in regions:
            text = self.extract_from_region(*region)
            results.append({"region": region, "text": text})
        return results

    def monitor_region(self, x, y, width, height, interval=2.0, duration=60, on_change=None):
        """Monitor a screen region for text changes."""
        logger.info(f"Monitoring region ({x},{y},{width},{height}) for {duration}s")
        last_text = ""
        start = time.time()
        changes = []
        while time.time() - start < duration:
            text = self.extract_from_region(x, y, width, height)
            if text != last_text:
                change = {
                    "timestamp": datetime.now().isoformat(),
                    "old_text": last_text[:100],
                    "new_text": text[:100]
                }
                changes.append(change)
                logger.info(f"Text changed: {text[:50]}")
                if on_change:
                    on_change(last_text, text)
                last_text = text
            time.sleep(interval)
        return changes

    def save_extraction(self, text, filepath):
        """Save extracted text to a file."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info(f"Saved extraction to {filepath}")

    def save_history(self, filepath="ocr_history.json"):
        """Save extraction history."""
        with open(filepath, "w") as f:
            json.dump(self.extraction_history, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Screen OCR Text Extractor")
    subparsers = parser.add_subparsers(dest="command")

    region_p = subparsers.add_parser("region", help="Extract from screen region")
    region_p.add_argument("--x", type=int, required=True)
    region_p.add_argument("--y", type=int, required=True)
    region_p.add_argument("--width", type=int, required=True)
    region_p.add_argument("--height", type=int, required=True)
    region_p.add_argument("--clipboard", action="store_true")
    region_p.add_argument("--save", type=str, help="Save to file")

    full_p = subparsers.add_parser("fullscreen", help="Extract from full screen")
    full_p.add_argument("--save", type=str)

    select_p = subparsers.add_parser("select", help="Interactive region select")

    monitor_p = subparsers.add_parser("monitor", help="Monitor region for changes")
    monitor_p.add_argument("--x", type=int, required=True)
    monitor_p.add_argument("--y", type=int, required=True)
    monitor_p.add_argument("--width", type=int, required=True)
    monitor_p.add_argument("--height", type=int, required=True)
    monitor_p.add_argument("--interval", type=float, default=2.0)
    monitor_p.add_argument("--duration", type=float, default=60)

    args = parser.parse_args()
    ocr = ScreenOCR()

    if args.command == "region":
        if args.clipboard:
            text = ocr.extract_to_clipboard(args.x, args.y, args.width, args.height)
        else:
            text = ocr.extract_from_region(args.x, args.y, args.width, args.height)
        print(text)
        if args.save:
            ocr.save_extraction(text, args.save)
    elif args.command == "fullscreen":
        img = ocr.capture_fullscreen()
        text = ocr.extract_text(img)
        print(text)
        if args.save:
            ocr.save_extraction(text, args.save)
    elif args.command == "select":
        print("Select a region on screen...")
        time.sleep(2)
        region = ocr.interactive_select_region()
        text = ocr.extract_from_region(*region)
        print(f"Region: {region}")
        print(f"Text: {text}")
        if HAS_CLIPBOARD:
            pyperclip.copy(text)
            print("(Copied to clipboard)")
    elif args.command == "monitor":
        changes = ocr.monitor_region(args.x, args.y, args.width, args.height,
                                     interval=args.interval, duration=args.duration)
        print(f"Detected {len(changes)} text changes")
        for c in changes:
            print(f"  [{c['timestamp']}] {c['new_text'][:60]}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
