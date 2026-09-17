#!/usr/bin/env python3
"""Screen QR Code Tool - Generate, scan, and decode QR codes from screen captures."""

import pyautogui
import time
import json
import os
import argparse
import threading
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont


@dataclass
class QREntry:
    """A generated or scanned QR code entry."""
    entry_id: str
    content: str
    qr_type: str = "url"
    image_path: str = ""
    timestamp: str = ""
    source: str = "generated"
    region: Tuple[int, int, int, int] = (0, 0, 0, 0)
    scan_confidence: float = 0.0
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class QRBatch:
    """A batch of QR codes to generate."""
    batch_id: str
    name: str
    items: List[Dict] = field(default_factory=list)
    output_dir: str = ""
    created_at: str = ""
    completed: int = 0
    failed: int = 0


class QRGenerator:
    """Generates QR code images."""

    def __init__(self):
        self._available = False
        try:
            import qrcode
            self._available = True
        except ImportError:
            print("qrcode library not found. Install with: pip install qrcode[pil]")

    def generate(self, content: str, output_path: str,
                 size: int = 300, error_correction: str = "M",
                 border: int = 4, fg_color: str = "black",
                 bg_color: str = "white") -> bool:
        if not self._available:
            return self._generate_fallback(content, output_path, size)
        try:
            import qrcode
            ec_map = {
                "L": qrcode.constants.ERROR_CORRECT_L,
                "M": qrcode.constants.ERROR_CORRECT_M,
                "Q": qrcode.constants.ERROR_CORRECT_Q,
                "H": qrcode.constants.ERROR_CORRECT_H
            }
            qr = qrcode.QRCode(
                version=None,
                error_correction=ec_map.get(error_correction.upper(),
                                             qrcode.constants.ERROR_CORRECT_M),
                box_size=max(1, size // 40),
                border=border
            )
            qr.add_data(content)
            qr.make(fit=True)
            img = qr.make_image(fill_color=fg_color, back_color=bg_color)
            img = img.resize((size, size), Image.NEAREST)
            img.save(output_path)
            return True
        except Exception as e:
            print(f"QR generation error: {e}")
            return self._generate_fallback(content, output_path, size)

    def _generate_fallback(self, content: str, output_path: str, size: int) -> bool:
        try:
            img = Image.new('RGB', (size, size), 'white')
            draw = ImageDraw.Draw(img)
            draw.rectangle([10, 10, size-10, size-10], outline='black', width=3)
            draw.rectangle([30, 30, size-30, size-30], outline='black', width=2)
            try:
                font = ImageFont.truetype("arial.ttf", 12)
            except Exception:
                font = ImageFont.load_default()
            lines = [content[i:i+30] for i in range(0, min(len(content), 120), 30)]
            y = size // 2 - len(lines) * 8
            for line in lines:
                draw.text((15, y), line, fill='black', font=font)
                y += 18
            draw.text((10, size-25), "QR (fallback)", fill='gray', font=font)
            img.save(output_path)
            return True
        except Exception as e:
            print(f"Fallback QR error: {e}")
            return False

    def generate_wifi(self, ssid: str, password: str, security: str = "WPA",
                      output_path: str = "wifi_qr.png") -> bool:
        content = f"WIFI:T:{security};S:{ssid};P:{password};;"
        return self.generate(content, output_path)

    def generate_vcard(self, name: str, phone: str = "", email: str = "",
                       url: str = "", output_path: str = "vcard_qr.png") -> bool:
        content = f"BEGIN:VCARD\nVERSION:3.0\nFN:{name}\n"
        if phone:
            content += f"TEL:{phone}\n"
        if email:
            content += f"EMAIL:{email}\n"
        if url:
            content += f"URL:{url}\n"
        content += "END:VCARD"
        return self.generate(content, output_path)

    def generate_contact(self, name: str, phone: str, output_path: str = "contact_qr.png") -> bool:
        content = f"MECARD:N:{name};TEL:{phone};;"
        return self.generate(content, output_path)


class QRScanner:
    """Scans and decodes QR codes from images."""

    def __init__(self):
        self._pyzbar_available = False
        self._cv2_available = False
        try:
            from pyzbar import pyzbar
            self._pyzbar_available = True
        except ImportError:
            pass
        try:
            import cv2
            self._cv2_available = True
        except ImportError:
            pass

    def scan_image(self, image_path: str) -> List[Dict]:
        results = []
        if self._pyzbar_available:
            results = self._scan_pyzbar(image_path)
        elif self._cv2_available:
            results = self._scan_cv2(image_path)
        else:
            print("No QR scanner available. Install: pip install pyzbar opencv-python")
        return results

    def _scan_pyzbar(self, image_path: str) -> List[Dict]:
        from pyzbar import pyzbar
        img = Image.open(image_path)
        decoded = pyzbar.decode(img)
        results = []
        for obj in decoded:
            results.append({
                'content': obj.data.decode('utf-8'),
                'type': obj.type,
                'rect': (obj.rect.left, obj.rect.top, obj.rect.width, obj.rect.height),
                'confidence': 1.0
            })
        return results

    def _scan_cv2(self, image_path: str) -> List[Dict]:
        import cv2
        import numpy as np
        img = cv2.imread(image_path)
        detector = cv2.QRCodeDetector()
        data, points, _ = detector.detectAndDecode(img)
        results = []
        if data:
            results.append({
                'content': data,
                'type': 'QRCODE',
                'rect': (0, 0, img.shape[1], img.shape[0]),
                'confidence': 0.9
            })
        return results

    def scan_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> List[Dict]:
        screenshot = pyautogui.screenshot(region=region)
        tmp_path = f"tmp_scan_{int(time.time())}.png"
        screenshot.save(tmp_path)
        try:
            results = self.scan_image(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        return results

    def continuous_scan(self, region: Optional[Tuple[int, int, int, int]] = None,
                         interval: float = 2.0, callback=None) -> List[Dict]:
        found = []
        seen_contents = set()
        print(f"Continuous QR scan started (every {interval}s). Press Ctrl+C to stop.")
        try:
            while True:
                results = self.scan_screen(region=region)
                for r in results:
                    if r['content'] not in seen_contents:
                        seen_contents.add(r['content'])
                        found.append(r)
                        print(f"  Found QR: {r['content'][:80]}")
                        if callback:
                            callback(r)
                time.sleep(interval)
        except KeyboardInterrupt:
            print(f"Scan stopped. Found {len(found)} unique codes.")
        return found


class ScreenQRTool:
    """Main QR code tool."""

    def __init__(self, data_dir: str = "qr_tool_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = self.data_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.history: List[QREntry] = []
        self.generator = QRGenerator()
        self.scanner = QRScanner()
        self._load_history()

    def _load_history(self):
        hf = self.data_dir / "history.json"
        if hf.exists():
            try:
                with open(hf, 'r') as f:
                    data = json.load(f)
                for ed in data:
                    ed['region'] = tuple(ed.get('region', [0, 0, 0, 0]))
                    self.history.append(QREntry(**ed))
            except Exception:
                pass

    def _save_history(self):
        hf = self.data_dir / "history.json"
        data = []
        for e in self.history:
            d = asdict(e)
            d['region'] = list(d['region'])
            data.append(d)
        with open(hf, 'w') as f:
            json.dump(data, f, indent=2)

    def generate_qr(self, content: str, name: str = "", size: int = 300,
                     qr_type: str = "text", error_correction: str = "M") -> Optional[str]:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = name or f"qr_{ts}"
        output = str(self.output_dir / f"{fname}.png")
        success = self.generator.generate(content, output, size=size,
                                           error_correction=error_correction)
        if success:
            entry = QREntry(
                entry_id=f"qr_{int(time.time() * 1000)}",
                content=content, qr_type=qr_type,
                image_path=output, source="generated"
            )
            self.history.append(entry)
            self._save_history()
            print(f"QR generated: {output}")
            return output
        return None

    def generate_wifi_qr(self, ssid: str, password: str, security: str = "WPA") -> Optional[str]:
        output = str(self.output_dir / f"wifi_{ssid}_{int(time.time())}.png")
        success = self.generator.generate_wifi(ssid, password, security, output)
        if success:
            entry = QREntry(
                entry_id=f"qr_{int(time.time() * 1000)}",
                content=f"WIFI:{ssid}", qr_type="wifi",
                image_path=output, source="generated"
            )
            self.history.append(entry)
            self._save_history()
            print(f"WiFi QR generated: {output}")
        return output if success else None

    def scan_file(self, image_path: str) -> List[QREntry]:
        results = self.scanner.scan_image(image_path)
        entries = []
        for r in results:
            entry = QREntry(
                entry_id=f"scan_{int(time.time() * 1000)}",
                content=r['content'], qr_type=r.get('type', 'QRCODE'),
                source="scanned_file",
                scan_confidence=r.get('confidence', 0.0)
            )
            self.history.append(entry)
            entries.append(entry)
            print(f"Scanned: {r['content'][:100]}")
        self._save_history()
        return entries

    def scan_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> List[QREntry]:
        print("Scanning screen for QR codes...")
        results = self.scanner.scan_screen(region=region)
        entries = []
        for r in results:
            entry = QREntry(
                entry_id=f"scan_{int(time.time() * 1000)}",
                content=r['content'], qr_type=r.get('type', 'QRCODE'),
                source="screen_scan",
                scan_confidence=r.get('confidence', 0.0),
                region=region or (0, 0, 0, 0)
            )
            self.history.append(entry)
            entries.append(entry)
            print(f"Found: {r['content'][:80]}")
        if not results:
            print("No QR codes found on screen")
        self._save_history()
        return entries

    def batch_generate(self, items: List[Dict], output_dir: Optional[str] = None) -> str:
        out = Path(output_dir) if output_dir else self.output_dir / f"batch_{int(time.time())}"
        out.mkdir(parents=True, exist_ok=True)
        success_count = 0
        for i, item in enumerate(items, 1):
            content = item.get('content', '')
            name = item.get('name', f"item_{i:03d}")
            size = item.get('size', 300)
            if not content:
                continue
            path = str(out / f"{name}.png")
            if self.generator.generate(content, path, size=size):
                success_count += 1
                print(f"  [{i}/{len(items)}] {name}: OK")
            else:
                print(f"  [{i}/{len(items)}] {name}: FAILED")
        print(f"Batch complete: {success_count}/{len(items)} generated in {out}")
        return str(out)

    def show_history(self, limit: int = 20):
        recent = list(reversed(self.history))[:limit]
        if not recent:
            print("No QR history.")
            return
        print(f"QR History ({len(recent)}):")
        for e in recent:
            print(f"  [{e.entry_id}] [{e.source}] {e.content[:60]}")
            if e.image_path:
                print(f"    File: {e.image_path}")

    def export_history(self, output: Optional[str] = None) -> str:
        if not output:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = str(self.data_dir / f"qr_history_{ts}.json")
        data = []
        for e in self.history:
            d = asdict(e)
            d['region'] = list(d['region'])
            data.append(d)
        with open(output, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"History exported: {output}")
        return output


def main():
    parser = argparse.ArgumentParser(description='Screen QR Code Tool')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    gen_p = subparsers.add_parser('generate', help='Generate QR code')
    gen_p.add_argument('content', help='Content to encode')
    gen_p.add_argument('--name', default='', help='Output filename')
    gen_p.add_argument('--size', type=int, default=300, help='Image size in pixels')
    gen_p.add_argument('--ec', default='M', choices=['L', 'M', 'Q', 'H'])

    wifi_p = subparsers.add_parser('wifi', help='Generate WiFi QR code')
    wifi_p.add_argument('ssid', help='WiFi SSID')
    wifi_p.add_argument('password', help='WiFi password')
    wifi_p.add_argument('--security', default='WPA', choices=['WPA', 'WEP', 'nopass'])

    scan_p = subparsers.add_parser('scan', help='Scan file or screen for QR')
    scan_p.add_argument('--file', help='Image file to scan')
    scan_p.add_argument('--region', nargs=4, type=int, help='x y w h screen region')

    cont_p = subparsers.add_parser('continuous', help='Continuous screen scanning')
    cont_p.add_argument('--interval', type=float, default=2.0)
    cont_p.add_argument('--region', nargs=4, type=int)

    batch_p = subparsers.add_parser('batch', help='Batch generate from JSON file')
    batch_p.add_argument('json_file', help='JSON file with list of {content, name} objects')
    batch_p.add_argument('--output-dir', help='Output directory')

    subparsers.add_parser('history', help='Show QR history')
    subparsers.add_parser('export', help='Export history')

    args = parser.parse_args()
    tool = ScreenQRTool()

    if args.command == 'generate':
        tool.generate_qr(args.content, name=args.name, size=args.size, error_correction=args.ec)
    elif args.command == 'wifi':
        tool.generate_wifi_qr(args.ssid, args.password, security=args.security)
    elif args.command == 'scan':
        if args.file:
            tool.scan_file(args.file)
        else:
            region = tuple(args.region) if args.region else None
            tool.scan_screen(region=region)
    elif args.command == 'continuous':
        region = tuple(args.region) if args.region else None
        tool.scanner.continuous_scan(region=region, interval=args.interval)
    elif args.command == 'batch':
        with open(args.json_file, 'r') as f:
            items = json.load(f)
        tool.batch_generate(items, output_dir=args.output_dir)
    elif args.command == 'history':
        tool.show_history()
    elif args.command == 'export':
        tool.export_history()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
