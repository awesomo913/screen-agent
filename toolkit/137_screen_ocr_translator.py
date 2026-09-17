#!/usr/bin/env python3
"""
137_screen_ocr_translator.py
Screen-control OCR translator: captures screen regions, extracts text via OCR,
translates using free APIs, and overlays translated text on screen.
"""

import pyautogui
import pytesseract
import argparse
import time
import os
import re
import json
import threading
import logging
import urllib.request
import urllib.parse
from PIL import Image, ImageGrab, ImageDraw, ImageFont, ImageEnhance
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path
import win32gui
import win32con
import tkinter as tk
from tkinter import ttk

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.2

DATA_DIR = Path.home() / "OCRTranslatorData"
DATA_DIR.mkdir(exist_ok=True)

SUPPORTED_LANGS = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "it": "Italian", "pt": "Portuguese", "ru": "Russian", "zh": "Chinese",
    "ja": "Japanese", "ko": "Korean", "ar": "Arabic", "hi": "Hindi",
    "nl": "Dutch", "pl": "Polish", "tr": "Turkish", "sv": "Swedish",
    "da": "Danish", "fi": "Finnish", "no": "Norwegian", "uk": "Ukrainian"
}

TESSERACT_LANGS = {
    "en": "eng", "es": "spa", "fr": "fra", "de": "deu", "it": "ita",
    "pt": "por", "ru": "rus", "zh": "chi_sim", "ja": "jpn", "ko": "kor",
    "ar": "ara", "hi": "hin", "nl": "nld", "pl": "pol", "tr": "tur"
}

@dataclass
class TranslationRecord:
    original_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    confidence: float
    region: Optional[Dict]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    rec_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S%f"))

@dataclass
class TranslateConfig:
    source_lang: str = "auto"
    target_lang: str = "en"
    ocr_lang: str = "eng"
    show_overlay: bool = True
    save_history: bool = True
    overlay_opacity: float = 0.9
    font_size: int = 13
    overlay_bg: str = "#1a1a2e"
    overlay_fg: str = "#e0e0e0"

class OCREngine:
    def __init__(self):
        tc = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if os.path.exists(tc):
            pytesseract.pytesseract.tesseract_cmd = tc

    def capture_region(self, x: int, y: int, w: int, h: int) -> Image.Image:
        return ImageGrab.grab(bbox=(x, y, x+w, y+h))

    def capture_full(self) -> Image.Image:
        return ImageGrab.grab()

    def extract_text(self, img: Image.Image, lang: str = "eng") -> Tuple[str, float]:
        enh = ImageEnhance.Contrast(img).enhance(1.5)
        enh = enh.convert('L')
        try:
            data = pytesseract.image_to_data(
                enh, lang=lang, output_type=pytesseract.Output.DICT,
                config='--psm 6'
            )
            words = []
            confs = []
            for i, t in enumerate(data['text']):
                if t.strip():
                    c = int(data['conf'][i])
                    if c > 20:
                        words.append(t)
                        confs.append(c)
            text = ' '.join(words)
            avg_conf = sum(confs) / len(confs) if confs else 0.0
            return text, avg_conf / 100.0
        except Exception as e:
            log.error(f"OCR error: {e}")
            try:
                text = pytesseract.image_to_string(img, config='--psm 6')
                return text.strip(), 0.5
            except Exception:
                return "", 0.0

    def extract_blocks(self, img: Image.Image, lang: str = "eng") -> List[Dict]:
        enh = ImageEnhance.Contrast(img).enhance(1.5).convert('L')
        try:
            data = pytesseract.image_to_data(enh, lang=lang, output_type=pytesseract.Output.DICT)
            blocks = {}
            for i, t in enumerate(data['text']):
                if not t.strip():
                    continue
                block_num = data['block_num'][i]
                if block_num not in blocks:
                    blocks[block_num] = {
                        'text': [], 'x': data['left'][i], 'y': data['top'][i],
                        'x2': data['left'][i]+data['width'][i],
                        'y2': data['top'][i]+data['height'][i]
                    }
                blocks[block_num]['text'].append(t)
                blocks[block_num]['x2'] = max(blocks[block_num]['x2'],
                                              data['left'][i]+data['width'][i])
                blocks[block_num]['y2'] = max(blocks[block_num]['y2'],
                                              data['top'][i]+data['height'][i])
            result = []
            for bn, b in blocks.items():
                result.append({
                    'text': ' '.join(b['text']),
                    'x': b['x'], 'y': b['y'],
                    'w': b['x2']-b['x'], 'h': b['y2']-b['y']
                })
            return result
        except Exception:
            return []

class TranslationEngine:
    def translate_mymemory(self, text: str, source: str, target: str) -> Optional[str]:
        if not text.strip():
            return None
        try:
            langpair = f"{source}|{target}" if source != "auto" else f"auto|{target}"
            encoded = urllib.parse.quote(text[:500])
            url = f"https://api.mymemory.translated.net/get?q={encoded}&langpair={langpair}"
            req = urllib.request.Request(url, headers={'User-Agent': 'OCRTranslator/1.0'})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
            translated = data.get('responseData', {}).get('translatedText', '')
            if translated and "QUERY LENGTH LIMIT" not in translated.upper():
                return translated
        except Exception as e:
            log.warning(f"MyMemory error: {e}")
        return None

    def translate_libre(self, text: str, source: str, target: str) -> Optional[str]:
        try:
            data = json.dumps({
                "q": text[:1000],
                "source": source if source != "auto" else "auto",
                "target": target,
                "format": "text"
            }).encode('utf-8')
            req = urllib.request.Request(
                "https://libretranslate.com/translate",
                data=data,
                headers={'Content-Type': 'application/json', 'User-Agent': 'OCRTranslator/1.0'}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                result = json.loads(resp.read().decode())
            return result.get('translatedText')
        except Exception as e:
            log.warning(f"LibreTranslate error: {e}")
        return None

    def translate(self, text: str, source: str, target: str) -> str:
        if not text.strip() or source == target:
            return text
        result = self.translate_mymemory(text, source, target)
        if result:
            return result
        result = self.translate_libre(text, source, target)
        if result:
            return result
        return f"[Translation unavailable] {text}"

class TranslationOverlay(tk.Toplevel):
    def __init__(self, parent: tk.Tk, original: str, translated: str,
                 config: TranslateConfig, position: Tuple[int,int] = (100, 100)):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", config.overlay_opacity)
        self.configure(bg=config.overlay_bg)
        self._build(original, translated, config, position)
        self._dragging = False
        self._drag_x = 0
        self._drag_y = 0
        self.bind("<ButtonPress-1>", self._start_drag)
        self.bind("<B1-Motion>", self._drag)

    def _build(self, original: str, translated: str,
               config: TranslateConfig, pos: Tuple[int,int]):
        bg = config.overlay_bg
        fg = config.overlay_fg
        acc = "#4fc3f7"
        tk.Label(self, text="Translation", font=("Arial",9,"bold"),
                 bg=bg, fg=acc).pack(padx=8, pady=(6,2))
        orig_frame = tk.Frame(self, bg=bg)
        orig_frame.pack(fill="x", padx=8)
        tk.Label(orig_frame, text="Original:", font=("Arial",8,"bold"),
                 bg=bg, fg="#888888").pack(anchor="w")
        orig_text = tk.Label(orig_frame, text=original[:300],
                             font=("Arial", config.font_size - 2),
                             bg=bg, fg="#999999", wraplength=360, justify="left")
        orig_text.pack(anchor="w", pady=2)
        tk.Frame(self, bg="#333", height=1).pack(fill="x", padx=8, pady=4)
        trans_frame = tk.Frame(self, bg=bg)
        trans_frame.pack(fill="x", padx=8)
        tk.Label(trans_frame, text="Translated:", font=("Arial",8,"bold"),
                 bg=bg, fg=acc).pack(anchor="w")
        trans_text = tk.Label(trans_frame, text=translated[:500],
                              font=("Arial", config.font_size),
                              bg=bg, fg=fg, wraplength=360, justify="left")
        trans_text.pack(anchor="w", pady=2)
        btn_frame = tk.Frame(self, bg=bg)
        btn_frame.pack(fill="x", padx=8, pady=6)
        tk.Button(btn_frame, text="Copy", command=lambda: self._copy(translated),
                  bg="#333", fg=fg, font=("Arial",8), relief="flat", padx=6).pack(side="left")
        tk.Button(btn_frame, text="Close", command=self.destroy,
                  bg="#883333", fg="white", font=("Arial",8), relief="flat",
                  padx=6).pack(side="right")
        self.update_idletasks()
        w = max(380, self.winfo_reqwidth())
        h = self.winfo_reqheight()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = min(pos[0] + 20, sw - w - 10)
        y = min(pos[1] + 20, sh - h - 60)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _copy(self, text: str):
        try:
            import pyperclip
            pyperclip.copy(text)
        except Exception:
            self.clipboard_clear()
            self.clipboard_append(text)

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag(self, event):
        x = self.winfo_x() + event.x - self._drag_x
        y = self.winfo_y() + event.y - self._drag_y
        self.geometry(f"+{x}+{y}")

class TranslationHistory:
    def __init__(self):
        self.path = DATA_DIR / "translation_history.jsonl"

    def save(self, record: TranslationRecord):
        with open(self.path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def load_recent(self, n: int = 20) -> List[TranslationRecord]:
        records = []
        if self.path.exists():
            with open(self.path, encoding='utf-8') as f:
                for line in f:
                    try:
                        records.append(TranslationRecord(**json.loads(line)))
                    except Exception:
                        pass
        return records[-n:]

class RegionSelector:
    def select(self) -> Optional[Tuple[int,int,int,int]]:
        print("Move cursor to START position, then press ENTER")
        print("Move cursor to END position, then press ENTER")
        print("Press ESC to cancel")
        import pynput.keyboard as kb
        positions = []
        done = threading.Event()

        def on_key(key):
            if key == kb.Key.enter:
                pos = pyautogui.position()
                positions.append(pos)
                print(f"Position {len(positions)}: {pos}")
                if len(positions) >= 2:
                    done.set()
                    return False
            elif key == kb.Key.esc:
                done.set()
                return False

        listener = kb.Listener(on_press=on_key)
        listener.start()
        done.wait(timeout=30)
        listener.stop()

        if len(positions) >= 2:
            x1, y1 = positions[0]
            x2, y2 = positions[1]
            return (min(x1,x2), min(y1,y2), abs(x2-x1), abs(y2-y1))
        return None

class ScreenTranslator:
    def __init__(self, config: TranslateConfig):
        self.config = config
        self.ocr = OCREngine()
        self.translator = TranslationEngine()
        self.history = TranslationHistory()
        self._root: Optional[tk.Tk] = None

    def translate_region(self, x: int, y: int, w: int, h: int) -> TranslationRecord:
        img = self.ocr.capture_region(x, y, w, h)
        tess_lang = TESSERACT_LANGS.get(self.config.source_lang, "eng")
        text, conf = self.ocr.extract_text(img, tess_lang)
        log.info(f"OCR text ({conf:.2f}): {text[:100]}")
        translated = self.translator.translate(text, self.config.source_lang,
                                               self.config.target_lang)
        record = TranslationRecord(
            original_text=text,
            translated_text=translated,
            source_lang=self.config.source_lang,
            target_lang=self.config.target_lang,
            confidence=conf,
            region={"x":x,"y":y,"w":w,"h":h}
        )
        if self.config.save_history:
            self.history.save(record)
        return record

    def translate_clipboard(self) -> Optional[str]:
        try:
            import pyperclip
            text = pyperclip.paste()
            if text:
                return self.translator.translate(text, self.config.source_lang,
                                                 self.config.target_lang)
        except Exception:
            pass
        return None

    def show_overlay(self, record: TranslationRecord):
        if not self._root:
            self._root = tk.Tk()
            self._root.withdraw()
        r = record.region or {}
        pos = (r.get('x', 100), r.get('y', 100))
        overlay = TranslationOverlay(self._root, record.original_text,
                                     record.translated_text, self.config, pos)
        self._root.mainloop()

    def continuous_mode(self, interval: float = 3.0,
                        region: Optional[Tuple[int,int,int,int]] = None):
        if not region:
            print("No region specified for continuous mode, using full screen")
        print(f"Continuous translate every {interval}s. Press Ctrl+C to stop.")
        last_text = ""
        try:
            while True:
                try:
                    if region:
                        x, y, w, h = region
                    else:
                        x, y, w, h = 0, 0, *pyautogui.size()
                    img = self.ocr.capture_region(x, y, w, h)
                    tl = TESSERACT_LANGS.get(self.config.source_lang, "eng")
                    text, conf = self.ocr.extract_text(img, tl)
                    text = text.strip()
                    if text and text != last_text and len(text) > 5:
                        translated = self.translator.translate(
                            text, self.config.source_lang, self.config.target_lang)
                        print(f"\n[{datetime.now().strftime('%H:%M:%S')}]")
                        print(f"  Original: {text[:150]}")
                        print(f"  Translated: {translated[:150]}")
                        last_text = text
                except Exception as e:
                    log.error(f"Continuous error: {e}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped.")

def main():
    parser = argparse.ArgumentParser(description="Screen OCR Translator")
    sub = parser.add_subparsers(dest="cmd")

    p_translate = sub.add_parser("translate", help="Translate a screen region")
    p_translate.add_argument("--region", nargs=4, type=int, metavar=("X","Y","W","H"))
    p_translate.add_argument("--select", action="store_true", help="Interactively select region")
    p_translate.add_argument("--source", default="auto")
    p_translate.add_argument("--target", default="en")
    p_translate.add_argument("--show-overlay", action="store_true")

    p_clip = sub.add_parser("clipboard", help="Translate clipboard content")
    p_clip.add_argument("--source", default="auto")
    p_clip.add_argument("--target", default="en")

    p_text = sub.add_parser("text", help="Translate provided text")
    p_text.add_argument("text")
    p_text.add_argument("--source", default="auto")
    p_text.add_argument("--target", default="en")

    p_continuous = sub.add_parser("continuous", help="Continuously translate screen")
    p_continuous.add_argument("--interval", type=float, default=3.0)
    p_continuous.add_argument("--region", nargs=4, type=int, metavar=("X","Y","W","H"))
    p_continuous.add_argument("--source", default="auto")
    p_continuous.add_argument("--target", default="en")

    sub.add_parser("history", help="Show translation history")
    sub.add_parser("langs", help="List supported languages")

    args = parser.parse_args()

    if args.cmd == "translate":
        cfg = TranslateConfig(source_lang=args.source, target_lang=args.target)
        translator = ScreenTranslator(cfg)
        if args.select:
            selector = RegionSelector()
            region = selector.select()
            if not region:
                print("Region selection cancelled")
                return
            x, y, w, h = region
        elif args.region:
            x, y, w, h = args.region
        else:
            sw, sh = pyautogui.size()
            x, y, w, h = 0, 0, sw, sh
        record = translator.translate_region(x, y, w, h)
        print(f"Original  ({record.confidence:.2f}): {record.original_text[:200]}")
        print(f"Translated ({record.target_lang}): {record.translated_text[:200]}")
        if args.show_overlay:
            translator.show_overlay(record)

    elif args.cmd == "clipboard":
        cfg = TranslateConfig(source_lang=args.source, target_lang=args.target)
        t = ScreenTranslator(cfg)
        result = t.translate_clipboard()
        print(f"Translated: {result}" if result else "No clipboard content")

    elif args.cmd == "text":
        cfg = TranslateConfig(source_lang=args.source, target_lang=args.target)
        t = TranslationEngine()
        result = t.translate(args.text, args.source, args.target)
        print(f"Original:   {args.text}")
        print(f"Translated: {result}")

    elif args.cmd == "continuous":
        cfg = TranslateConfig(source_lang=args.source, target_lang=args.target)
        t = ScreenTranslator(cfg)
        region = tuple(args.region) if args.region else None
        t.continuous_mode(args.interval, region)

    elif args.cmd == "history":
        h = TranslationHistory()
        records = h.load_recent(20)
        if not records:
            print("No history.")
            return
        for r in records:
            print(f"[{r.timestamp[:16]}] {r.source_lang}->{r.target_lang}: "
                  f"{r.original_text[:50]} => {r.translated_text[:50]}")

    elif args.cmd == "langs":
        print("Supported languages:")
        for code, name in SUPPORTED_LANGS.items():
            print(f"  {code:<6} {name}")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
