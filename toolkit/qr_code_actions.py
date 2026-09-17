"""
qr_code_actions.py
Screen Agent Toolkit: Comprehensive QR Code Generation, Decoding & Manipulation Module.
Uses: qrcode, pyzbar, PIL (Pillow), cv2 (OpenCV), base64, io
Returns: Dict[str, Any] for all functions with structured success/error payloads.
"""

import io
import os
import time
import base64
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

import cv2
from PIL import Image, ImageDraw, ImageFont, ImageGrab
import qrcode
import qrcode.image.svg
from pyzbar import pyzbar


def _make_response(success: bool, message: str, data: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
    """Helper to standardize return dictionaries across all functions."""
    return {
        "success": success,
        "message": message,
        "data": data,
        "error": error,
        "timestamp": datetime.utcnow().isoformat()
    }


def _generate_qr_base64(data: str, size: int = 10, border: int = 4, fill: str = "black", back: str = "white") -> Dict[str, Any]:
    """Internal helper to generate QR and return base64 payload."""
    qr = qrcode.QRCode(box_size=size, border=border)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fill, back_color=back).convert("RGB")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return _make_response(True, "QR code generated successfully", {
        "base64": b64,
        "width": img.width,
        "height": img.height
    })


# ==========================================
# Core Generation Functions
# ==========================================

def generate_qr(data: str, size: int = 10, border: int = 4) -> Dict[str, Any]:
    """Generates a standard QR code and returns it as base64 PNG."""
    try:
        return _generate_qr_base64(data, size=size, border=border)
    except Exception as e:
        return _make_response(False, "Failed to generate QR code", error=str(e))


def generate_qr_with_logo(data: str, logo_path: str, size: int = 10) -> Dict[str, Any]:
    """Generates a QR code with a centered logo overlay."""
    try:
        qr = qrcode.QRCode(box_size=size, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        
        logo = Image.open(logo_path).convert("RGBA")
        qr_width = qr_img.width
        logo_target = int(qr_width * 0.20)
        logo.thumbnail((logo_target, logo_target), Image.LANCZOS)
        
        pos = ((qr_width - logo.width) // 2, (qr_img.height - logo.height) // 2)
        mask = Image.new("L", logo.size, 255)
        qr_img.paste(logo, pos, logo)
        
        buffered = io.BytesIO()
        qr_img.convert("RGB").save(buffered, format="PNG")
        b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return _make_response(True, "QR with logo generated", {"base64": b64, "width": qr_img.width, "height": qr_img.height})
    except Exception as e:
        return _make_response(False, "Failed to generate QR with logo", error=str(e))


def generate_styled_qr(data: str, fill_color: str = "black", back_color: str = "white", style: str = "square") -> Dict[str, Any]:
    """Generates a QR code with custom colors. Note: Complex module shapes require external renderers."""
    try:
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color=fill_color, back_color=back_color).convert("RGB")
        
        # Basic style simulation via pixel scaling or mask if needed, 
        # here we apply standard rendering with requested palette.
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return _make_response(True, "Styled QR generated", {"base64": b64, "style_applied": style, "width": img.width})
    except Exception as e:
        return _make_response(False, "Styled QR generation failed", error=str(e))


def generate_micro_qr(data: str) -> Dict[str, Any]:
    """Generates a compact QR code (approximates Micro QR constraints)."""
    try:
        # Micro QR v1-V4 holds ~15-35 alphanumeric chars. Enforce limit.
        if len(data) > 35:
            return _make_response(False, "Data exceeds Micro QR capacity limits (~35 chars)", error="LengthLimitExceeded")
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return _make_response(True, "Compact/Micro QR generated", {"base64": b64})
    except Exception as e:
        return _make_response(False, "Micro QR generation failed", error=str(e))


def generate_qr_svg(data: str, output_path: str) -> Dict[str, Any]:
    """Generates an SVG QR code and saves to file."""
    try:
        qr = qrcode.QRCode(image_factory=qrcode.image.svg.SvgImage)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image()
        with open(output_path, "wb") as f:
            img.save(f)
        return _make_response(True, "SVG QR saved successfully", {"path": output_path})
    except Exception as e:
        return _make_response(False, "SVG generation failed", error=str(e))


def save_qr_to_file(data: str, output_path: str, format: str = "PNG") -> Dict[str, Any]:
    """Generates a QR and saves directly to a file system path."""
    try:
        qr = qrcode.QRCode()
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        dir_path = os.path.dirname(output_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        img.save(output_path, format=format.upper())
        return _make_response(True, "QR saved to file", {"path": output_path, "format": format})
    except Exception as e:
        return _make_response(False, "File save failed", error=str(e))


# ==========================================
# Specialized Payload Generators
# ==========================================

def generate_vcard_qr(name: str, phone: str = "", email: str = "", org: str = "") -> Dict[str, Any]:
    """Generates a QR containing vCard 3.0 data."""
    try:
        vcard = f"BEGIN:VCARD\nVERSION:3.0\nFN:{name}\nTEL:{phone}\nEMAIL:{email}\nORG:{org}\nEND:VCARD"
        return _generate_qr_base64(vcard)
    except Exception as e:
        return _make_response(False, "VCard QR generation failed", error=str(e))


def generate_wifi_qr(ssid: str, password: str, auth_type: str = "WPA") -> Dict[str, Any]:
    """Generates a WiFi connection QR string."""
    try:
        wifi_str = f"WIFI:T:{auth_type};S:{ssid};P:{password};;"
        return _generate_qr_base64(wifi_str)
    except Exception as e:
        return _make_response(False, "WiFi QR generation failed", error=str(e))


def generate_url_qr(url: str, size: int = 10) -> Dict[str, Any]:
    """Generates a standard URL QR code."""
    try:
        return _generate_qr_base64(url, size=size)
    except Exception as e:
        return _make_response(False, "URL QR generation failed", error=str(e))


def generate_email_qr(email: str, subject: str = "", body: str = "") -> Dict[str, Any]:
    """Generates a mailto: URI QR code."""
    try:
        uri = f"mailto:{email}?subject={base64.urlsafe_b64encode(subject.encode()).decode()}&body={base64.urlsafe_b64encode(body.encode()).decode()}"
        # Cleaner fallback without b64 for subjects containing special chars:
        uri_clean = f"mailto:{email}?subject={subject}&body={body}"
        return _generate_qr_base64(uri_clean)
    except Exception as e:
        return _make_response(False, "Email QR generation failed", error=str(e))


def generate_sms_qr(phone: str, message: str = "") -> Dict[str, Any]:
    """Generates an sms: URI QR code."""
    try:
        uri = f"sms:{phone}?body={message}"
        return _generate_qr_base64(uri)
    except Exception as e:
        return _make_response(False, "SMS QR generation failed", error=str(e))


def generate_geo_qr(lat: float, lon: float) -> Dict[str, Any]:
    """Generates a geolocation URI QR code."""
    try:
        uri = f"geo:{lat},{lon}"
        return _generate_qr_base64(uri)
    except Exception as e:
        return _make_response(False, "Geo QR generation failed", error=str(e))


# ==========================================
# Decoding & Screen/Camera Functions
# ==========================================

def decode_qr_from_file(image_path: str) -> Dict[str, Any]:
    """Decodes QR codes from a static image file."""
    try:
        img = Image.open(image_path)
        decoded = pyzbar.decode(img)
        results = [
            {"data": d.data.decode("utf-8"), "type": d.type.decode("utf-8"), "rect": d.rect, "polygon": [tuple(p) for p in d.polygon]}
            for d in decoded
        ]
        return _make_response(True, "File decoded successfully", {"results": results, "count": len(results)})
    except Exception as e:
        return _make_response(False, "File decoding failed", error=str(e))


def decode_qr_from_screen(region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
    """Captures a screen region (or full screen) and decodes QR codes. Region format: (left, top, right, bottom)."""
    try:
        screenshot = ImageGrab.grab(bbox=region)
        decoded = pyzbar.decode(screenshot)
        results = [{"data": d.data.decode("utf-8"), "type": d.type.decode("utf-8"), "rect": d.rect} for d in decoded]
        return _make_response(True, "Screen decoded successfully", {"results": results, "count": len(results)})
    except Exception as e:
        return _make_response(False, "Screen capture/decoding failed. Ensure display server/x11 is available.", error=str(e))


def decode_qr_from_base64(b64_string: str) -> Dict[str, Any]:
    """Decodes QR code data from a base64 encoded image string."""
    try:
        img_bytes = base64.b64decode(b64_string)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        decoded = pyzbar.decode(img)
        results = [{"data": d.data.decode("utf-8"), "type": d.type.decode("utf-8")} for d in decoded]
        return _make_response(True, "Base64 image decoded", {"results": results, "count": len(results)})
    except Exception as e:
        return _make_response(False, "Base64 decoding failed", error=str(e))


def read_qr_from_webcam(camera_id: int = 0, timeout: int = 10) -> Dict[str, Any]:
    """Opens a webcam stream and waits for a QR code until timeout."""
    cap = None
    try:
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            return _make_response(False, "Webcam could not be opened", error="CameraAccessDenied")
        
        start = time.time()
        while time.time() - start < timeout:
            ret, frame = cap.read()
            if not ret:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            decoded = pyzbar.decode(gray)
            if decoded:
                results = [{"data": d.data.decode("utf-8"), "type": d.type.decode("utf-8")} for d in decoded]
                return _make_response(True, "QR detected via webcam", {"results": results})
        return _make_response(False, "No QR code detected within timeout")
    except Exception as e:
        return _make_response(False, "Webcam reading failed", error=str(e))
    finally:
        if cap is not None:
            cap.release()


def batch_decode_qr(image_paths: List[str]) -> Dict[str, Any]:
    """Decodes QR codes from multiple image files."""
    try:
        results = {}
        for path in image_paths:
            img = Image.open(path)
            decoded = pyzbar.decode(img)
            results[path] = [{"data": d.data.decode("utf-8"), "type": d.type.decode("utf-8")} for d in decoded]
        return _make_response(True, "Batch decode complete", {"results": results})
    except Exception as e:
        return _make_response(False, "Batch decode failed", error=str(e))


def validate_qr_data(data: str, max_length: int = 4296) -> Dict[str, Any]:
    """Validates if data fits within standard QR byte limits."""
    try:
        byte_len = len(data.encode("utf-8"))
        is_valid = byte_len <= max_length
        return _make_response(True, "Validation complete", {"valid": is_valid, "byte_length": byte_len, "max_allowed": max_length})
    except Exception as e:
        return _make_response(False, "Data validation failed", error=str(e))


def get_qr_info(image_path: str) -> Dict[str, Any]:
    """Extracts basic metadata and decoded payload from a QR image."""
    try:
        img = Image.open(image_path)
        decoded = pyzbar.decode(img)
        if not decoded:
            return _make_response(False, "No QR code detected in image")
        d = decoded[0]
        return _make_response(True, "QR metadata retrieved", {
            "data": d.data.decode("utf-8"),
            "type": d.type.decode("utf-8"),
            "image_width": img.width,
            "image_height": img.height,
            "mode": img.mode,
            "polygon_points": len(d.polygon),
            "bounding_box": d.rect._asdict()
        })
    except Exception as e:
        return _make_response(False, "Info extraction failed", error=str(e))


# ==========================================
# Batch & Composite Generation
# ==========================================

def batch_generate_qr(data_list: List[str], output_dir: str) -> Dict[str, Any]:
    """Generates multiple QR codes and saves them sequentially to a directory."""
    try:
        os.makedirs(output_dir, exist_ok=True)
        saved_paths = []
        for i, data in enumerate(data_list):
            qr = qrcode.QRCode()
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            path = os.path.join(output_dir, f"qr_{i}.png")
            img.save(path, "PNG")
            saved_paths.append(path)
        return _make_response(True, f"Batch generated {len(saved_paths)} QR codes", {"paths": saved_paths})
    except Exception as e:
        return _make_response(False, "Batch generation failed", error=str(e))


def generate_qr_with_border_text(data: str, text: str, position: str = "bottom") -> Dict[str, Any]:
    """Generates a QR code with a caption/border text rendered via PIL."""
    try:
        qr = qrcode.QRCode()
        qr.add_data(data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except IOError:
            font = ImageFont.load_default()
            
        padding = 15
        qr_w, qr_h = qr_img.size
        txt_h = 20 + padding * 2
        
        if position.lower() == "bottom":
            new_img = Image.new("RGB", (qr_w, qr_h + txt_h), "white")
            new_img.paste(qr_img, (0, 0))
            draw = ImageDraw.Draw(new_img)
            draw.text((10, qr_h + 10), text, fill="black", font=font)
        elif position.lower() == "top":
            new_img = Image.new("RGB", (qr_w, qr_h + txt_h), "white")
            new_img.paste(qr_img, (0, txt_h))
            draw = ImageDraw.Draw(new_img)
            draw.text((10, 10), text, fill="black", font=font)
        else:
            new_img = Image.new("RGB", (qr_w + txt_h, qr_h), "white")
            new_img.paste(qr_img, (20 if position.lower() == "right" else (txt_h + 20), 0))
            draw = ImageDraw.Draw(new_img)
            draw.text((10, 10), text, fill="black", font=font)
            
        buffered = io.BytesIO()
        new_img.save(buffered, format="PNG")
        b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return _make_response(True, "QR with border text generated", {"base64": b64})
    except Exception as e:
        return _make_response(False, "Border text generation failed", error=str(e))


def overlay_qr_on_image(qr_data: str, background_path: str, position: Tuple[int, int] = (0, 0)) -> Dict[str, Any]:
    """Composites a generated QR code onto a background image."""
    try:
        qr = qrcode.QRCode()
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        
        bg = Image.open(background_path).convert("RGBA")
        # Scale QR if it exceeds background
        if qr_img.width > bg.width or qr_img.height > bg.height:
            scale = min(bg.width / qr_img.width, bg.height / qr_img.height) * 0.8
            qr_img = qr_img.resize((int(qr_img.width * scale), int(qr_img.height * scale)), Image.LANCZOS)
            
        bg.paste(qr_img, position, qr_img)
        buffered = io.BytesIO()
        bg.convert("RGB").save(buffered, format="PNG")
        b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return _make_response(True, "QR overlay successful", {"base64": b64})
    except Exception as e:
        return _make_response(False, "Overlay composition failed", error=str(e))


def extract_qr_regions(image_path: str) -> Dict[str, Any]:
    """Extracts and isolates all detected QR regions from a source image."""
    try:
        img = Image.open(image_path).convert("RGB")
        decoded = pyzbar.decode(img)
        crops = []
        for i, d in enumerate(decoded):
            x, y, w, h = d.rect.left, d.rect.top, d.rect.width, d.rect.height
            crop = img.crop((x, y, x + w, y + h))
            buf = io.BytesIO()
            crop.save(buf, format="PNG")
            crops.append({"id": i, "base64": base64.b64encode(buf.getvalue()).decode("utf-8"), "bounding_rect": (x, y, w, h)})
        return _make_response(True, f"Extracted {len(crops)} QR regions", {"regions": crops, "count": len(crops)})
    except Exception as e:
        return _make_response(False, "Region extraction failed", error=str(e))


def generate_qr_pdf(data_list: List[str], output_path: str, labels: Optional[List[str]] = None) -> Dict[str, Any]:
    """Generates a multi-page PDF with tiled QR codes and labels using Pillow."""
    try:
        a4_w, a4_h = 2480, 3508  # 300 DPI A4
        margin = 150
        items_per_page = 4
        pages = []
        labels = labels or [f"Item_{i+1}" for i in range(len(data_list))]
        positions = [(250, 400), (1500, 400), (250, 2000), (1500, 2000)]
        
        try:
            font = ImageFont.truetype("arial.ttf", 28)
        except IOError:
            font = ImageFont.load_default()
            
        for i in range(0, len(data_list), items_per_page):
            page_data = data_list[i:i+items_per_page]
            page_lbls = labels[i:i+items_per_page]
            page_img = Image.new("RGB", (a4_w, a4_h), "white")
            draw = ImageDraw.Draw(page_img)
            
            for j, (d, lbl) in enumerate(zip(page_data, page_lbls)):
                if j >= items_per_page: break
                x, y = positions[j]
                qr = qrcode.QRCode(box_size=10, border=4)
                qr.add_data(d)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
                page_img.paste(qr_img, (x, y))
                draw.text((x, y + qr_img.height + 15), lbl, fill="black", font=font)
            pages.append(page_img)
            
        if pages:
            pages[0].save(output_path, "PDF", save_all=True, append_images=pages[1:], resolution=300)
        return _make_response(True, "PDF generated successfully", {"path": output_path, "page_count": len(pages)})
    except Exception as e:
        return _make_response(False, "PDF generation failed", error=str(e))


def compare_qr_codes(path1: str, path2: str) -> Dict[str, Any]:
    """Compares decoded payloads from two QR code images."""
    try:
        res1 = pyzbar.decode(Image.open(path1))
        res2 = pyzbar.decode(Image.open(path2))
        d1 = res1[0].data.decode("utf-8") if res1 else None
        d2 = res2[0].data.decode("utf-8") if res2 else None
        match = d1 == d2
        img1 = Image.open(path1)
        img2 = Image.open(path2)
        return _make_response(True, "Comparison complete", {
            "paths": [path1, path2],
            "data_match": match,
            "data1": d1,
            "data2": d2,
            "dimensions": {"img1": img1.size, "img2": img2.size}
        })
    except Exception as e:
        return _make_response(False, "Comparison failed", error=str(e))