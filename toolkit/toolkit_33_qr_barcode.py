"""
toolkit_33_qr_barcode.py
Generate and decode QR codes and barcodes. Soft-imports qrcode and pyzbar/zxing.
"""
from __future__ import annotations
import os
from typing import Any, Dict, List

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

try:
    from pyzbar import pyzbar
    HAS_PYZBAR = True
except ImportError:
    HAS_PYZBAR = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import barcode
    from barcode.writer import ImageWriter
    HAS_BARCODE = True
except ImportError:
    HAS_BARCODE = False

def generate_qr_code(data: str, output_path: str, size: int = 10, error_correction: str = "L") -> Dict[str, Any]:
    try:
        if not HAS_QRCODE:
            return {"success": False, "data": None, "error": "qrcode not installed (pip install qrcode[pil])"}
        ec_map = {"L": qrcode.constants.ERROR_CORRECT_L,
                  "M": qrcode.constants.ERROR_CORRECT_M,
                  "Q": qrcode.constants.ERROR_CORRECT_Q,
                  "H": qrcode.constants.ERROR_CORRECT_H}
        qr = qrcode.QRCode(
            version=1,
            error_correction=ec_map.get(error_correction.upper(), qrcode.constants.ERROR_CORRECT_L),
            box_size=size,
            border=4
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(output_path)
        return {"success": True, "data": {"saved": output_path, "data": data}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def generate_qr_url(url: str, output_path: str) -> Dict[str, Any]:
    return generate_qr_code(url, output_path)

def generate_qr_wifi(ssid: str, password: str, output_path: str, security: str = "WPA") -> Dict[str, Any]:
    """Generate a WiFi QR code scannable by phones."""
    wifi_string = "WIFI:T:" + security + ";S:" + ssid + ";P:" + password + ";;"
    return generate_qr_code(wifi_string, output_path)

def generate_qr_contact(name: str, phone: str, email: str, output_path: str) -> Dict[str, Any]:
    """Generate a vCard QR code."""
    vcard = "BEGIN:VCARD\nVERSION:3.0\nFN:" + name + "\nTEL:" + phone + "\nEMAIL:" + email + "\nEND:VCARD"
    return generate_qr_code(vcard, output_path)

def decode_qr_from_file(image_path: str) -> Dict[str, Any]:
    try:
        if not HAS_PIL:
            return {"success": False, "data": None, "error": "Pillow not installed"}
        if not HAS_PYZBAR:
            return {"success": False, "data": None, "error": "pyzbar not installed (pip install pyzbar)"}
        img = Image.open(image_path)
        codes = pyzbar.decode(img)
        result = [{"type": c.type, "data": c.data.decode("utf-8", errors="replace")} for c in codes]
        return {"success": True, "data": {"count": len(result), "codes": result}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def decode_qr_from_screenshot() -> Dict[str, Any]:
    """Take a screenshot and decode any QR codes visible."""
    try:
        if not HAS_PIL or not HAS_PYZBAR:
            return {"success": False, "data": None, "error": "Pillow and pyzbar required"}
        import mss
        with mss.mss() as sct:
            screen = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", screen.size, screen.bgra, "raw", "BGRX")
        codes = pyzbar.decode(img)
        result = [{"type": c.type, "data": c.data.decode("utf-8", errors="replace")} for c in codes]
        return {"success": True, "data": {"count": len(result), "codes": result}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def generate_barcode(data: str, barcode_type: str, output_path: str) -> Dict[str, Any]:
    """Generate a barcode image. types: code128, code39, ean13, ean8, isbn13, etc."""
    try:
        if not HAS_BARCODE:
            return {"success": False, "data": None, "error": "python-barcode not installed (pip install python-barcode[images])"}
        bc_class = barcode.get_barcode_class(barcode_type)
        bc = bc_class(data, writer=ImageWriter())
        saved = bc.save(output_path.rstrip(".png"))
        return {"success": True, "data": {"saved": saved}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_barcode_formats() -> Dict[str, Any]:
    try:
        if not HAS_BARCODE:
            return {"success": False, "data": None, "error": "python-barcode not installed"}
        return {"success": True, "data": list(barcode.PROVIDED_BARCODES), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_qr_code_info(image_path: str) -> Dict[str, Any]:
    """Get detailed info about decoded barcode/QR codes in an image."""
    try:
        if not HAS_PIL or not HAS_PYZBAR:
            return {"success": False, "data": None, "error": "Pillow and pyzbar required"}
        img = Image.open(image_path)
        codes = pyzbar.decode(img)
        result = []
        for c in codes:
            result.append({
                "type": c.type,
                "data": c.data.decode("utf-8", errors="replace"),
                "rect": {"left": c.rect.left, "top": c.rect.top, "width": c.rect.width, "height": c.rect.height},
                "quality": c.quality
            })
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_libraries() -> Dict[str, Any]:
    return {"success": True, "data": {
        "qrcode": HAS_QRCODE,
        "pyzbar": HAS_PYZBAR,
        "pillow": HAS_PIL,
        "barcode": HAS_BARCODE
    }, "error": None}

def generate_qr_email(email: str, subject: str, output_path: str) -> Dict[str, Any]:
    mailto = "mailto:" + email + "?subject=" + subject.replace(" ", "%20")
    return generate_qr_code(mailto, output_path)

def generate_qr_phone(phone: str, output_path: str) -> Dict[str, Any]:
    return generate_qr_code("tel:" + phone, output_path)

def generate_qr_sms(phone: str, message: str, output_path: str) -> Dict[str, Any]:
    sms = "smsto:" + phone + ":" + message
    return generate_qr_code(sms, output_path)

def generate_qr_text(text: str, output_path: str) -> Dict[str, Any]:
    return generate_qr_code(text, output_path)

def batch_decode_folder(folder: str) -> Dict[str, Any]:
    """Decode QR codes/barcodes from all images in a folder."""
    try:
        if not HAS_PIL or not HAS_PYZBAR:
            return {"success": False, "data": None, "error": "Pillow and pyzbar required"}
        exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"}
        results = []
        for f in os.listdir(folder):
            if any(f.lower().endswith(e) for e in exts):
                fp = os.path.join(folder, f)
                r = decode_qr_from_file(fp)
                if r["success"] and r["data"]["codes"]:
                    results.append({"file": f, "codes": r["data"]["codes"]})
        return {"success": True, "data": {"files_with_codes": len(results), "results": results}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
