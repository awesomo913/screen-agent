#!/usr/bin/env python3
"""Screen OCR Batch Processor - Extract text from screen regions and images in batch."""
import os, sys, time, json, argparse, csv
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import pyautogui
from PIL import Image, ImageEnhance, ImageFilter
try:
    import pytesseract; HAS_TESSERACT = True
except ImportError: HAS_TESSERACT = False

@dataclass
class OCRResult:
    source: str; text: str; confidence: float = 0.0; language: str = "eng"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat()); region: Optional[Tuple] = None

class ImagePreprocessor:
    def grayscale(self, img): return img.convert("L")
    def threshold(self, img, thresh=128):
        gray = self.grayscale(img)
        return gray.point(lambda p: 255 if p > thresh else 0)
    def enhance_contrast(self, img, factor=2.0):
        return ImageEnhance.Contrast(img).enhance(factor)
    def sharpen(self, img): return img.filter(ImageFilter.SHARPEN)
    def denoise(self, img): return img.filter(ImageFilter.MedianFilter(3))
    def resize(self, img, scale=2.0):
        w, h = img.size; return img.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
    def auto_preprocess(self, img):
        img = self.resize(img, 2.0)
        img = self.enhance_contrast(img, 1.5)
        img = self.sharpen(img)
        return img

class OCREngine:
    def __init__(self, language="eng", preprocess=True):
        self.language = language; self.preprocess = preprocess
        self.preprocessor = ImagePreprocessor()
    def extract_text(self, image, config=""):
        if not HAS_TESSERACT: return OCRResult(source="unknown", text="pytesseract not installed")
        if self.preprocess: image = self.preprocessor.auto_preprocess(image)
        custom_config = config or "--oem 3 --psm 6"
        text = pytesseract.image_to_string(image, lang=self.language, config=custom_config).strip()
        data = pytesseract.image_to_data(image, lang=self.language, output_type=pytesseract.Output.DICT, config=custom_config)
        confs = [int(c) for c in data["conf"] if int(c) > 0]
        avg_conf = sum(confs) / len(confs) if confs else 0
        return OCRResult(source="image", text=text, confidence=round(avg_conf, 1), language=self.language)
    def extract_from_region(self, x, y, width, height, config=""):
        img = pyautogui.screenshot(region=(x, y, width, height))
        result = self.extract_text(img, config)
        result.source = "screen"; result.region = (x, y, width, height)
        return result
    def extract_structured(self, image):
        if not HAS_TESSERACT: return []
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, lang=self.language)
        words = []
        for i in range(len(data["text"])):
            if data["text"][i].strip():
                words.append({"text": data["text"][i], "x": data["left"][i], "y": data["top"][i],
                               "w": data["width"][i], "h": data["height"][i], "conf": data["conf"][i]})
        return words

class BatchOCRProcessor:
    def __init__(self, output_dir=None, language="eng"):
        self.output_dir = output_dir or os.path.expanduser("~/ocr_output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.engine = OCREngine(language=language)
        self.results: List[OCRResult] = []
    def process_image(self, image_path):
        img = Image.open(image_path)
        result = self.engine.extract_text(img)
        result.source = image_path
        self.results.append(result)
        return result
    def process_directory(self, directory, extensions=None):
        extensions = extensions or [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif"]
        files = sorted(f for f in Path(directory).rglob("*") if f.suffix.lower() in extensions)
        print("Processing " + str(len(files)) + " images...")
        for i, fpath in enumerate(files):
            result = self.process_image(str(fpath))
            print("  [" + str(i+1) + "/" + str(len(files)) + "] " + fpath.name + ": " + str(len(result.text)) + " chars (conf=" + str(result.confidence) + "%)")
        return self.results
    def process_screen_regions(self, regions):
        for name, (x, y, w, h) in regions.items():
            result = self.engine.extract_from_region(x, y, w, h)
            result.source = name
            self.results.append(result)
            print("  " + name + ": " + result.text[:80])
        return self.results
    def monitor_region(self, x, y, w, h, interval=2.0, duration=60, on_change=None):
        print("Monitoring region for " + str(duration) + "s...")
        last_text = ""
        end = time.time() + duration
        while time.time() < end:
            result = self.engine.extract_from_region(x, y, w, h)
            if result.text != last_text:
                print("  [" + datetime.now().strftime("%H:%M:%S") + "] Changed: " + result.text[:60])
                self.results.append(result); last_text = result.text
                if on_change: on_change(result)
            time.sleep(interval)
    def export_results(self, output_path=None, format="json"):
        output_path = output_path or os.path.join(self.output_dir, "ocr_results." + format)
        data = [{"source": r.source, "text": r.text, "confidence": r.confidence,
                  "timestamp": r.timestamp} for r in self.results]
        if format == "json":
            with open(output_path, "w") as f: json.dump(data, f, indent=2)
        elif format == "csv":
            with open(output_path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["source","text","confidence","timestamp"])
                w.writeheader(); w.writerows(data)
        elif format == "txt":
            with open(output_path, "w") as f:
                for r in self.results:
                    f.write("--- " + r.source + " ---\n" + r.text + "\n\n")
        print("Exported " + str(len(data)) + " results to " + output_path)

def main():
    parser = argparse.ArgumentParser(description="Screen OCR Batch Processor")
    parser.add_argument("--output-dir"); parser.add_argument("--lang", default="eng")
    subparsers = parser.add_subparsers(dest="command")
    img_p = subparsers.add_parser("image"); img_p.add_argument("path")
    dir_p = subparsers.add_parser("directory"); dir_p.add_argument("path")
    dir_p.add_argument("--ext", nargs="+", default=[".png",".jpg"])
    reg_p = subparsers.add_parser("region")
    reg_p.add_argument("x",type=int); reg_p.add_argument("y",type=int)
    reg_p.add_argument("width",type=int); reg_p.add_argument("height",type=int)
    mon_p = subparsers.add_parser("monitor")
    mon_p.add_argument("x",type=int); mon_p.add_argument("y",type=int)
    mon_p.add_argument("width",type=int); mon_p.add_argument("height",type=int)
    mon_p.add_argument("--interval",type=float,default=2.0); mon_p.add_argument("--duration",type=float,default=60)
    screen_p = subparsers.add_parser("screen", help="OCR full screen")
    args = parser.parse_args()
    proc = BatchOCRProcessor(output_dir=args.output_dir, language=args.lang)
    if args.command == "image":
        r = proc.process_image(args.path)
        print("Text:\n" + r.text); print("Confidence: " + str(r.confidence) + "%")
    elif args.command == "directory":
        proc.process_directory(args.path, args.ext); proc.export_results()
    elif args.command == "region":
        r = proc.engine.extract_from_region(args.x, args.y, args.width, args.height)
        print("Text:\n" + r.text)
    elif args.command == "monitor":
        proc.monitor_region(args.x, args.y, args.width, args.height, args.interval, args.duration)
        proc.export_results()
    elif args.command == "screen":
        img = pyautogui.screenshot()
        r = proc.engine.extract_text(img)
        print("Screen text:\n" + r.text[:500])
    else: parser.print_help()

if __name__ == "__main__":
    main()
