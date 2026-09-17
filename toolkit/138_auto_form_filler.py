#!/usr/bin/env python3
"""
138_auto_form_filler.py
Screen-control auto form filler: reads form templates, locates fields via OCR,
auto-fills data, validates and submits, supports tab order navigation.
"""

import pyautogui
import pytesseract
import argparse
import time
import os
import re
import json
import logging
from PIL import Image, ImageGrab, ImageEnhance
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path
import win32gui
import win32con

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3

DATA_DIR = Path.home() / "AutoFormFillerData"
DATA_DIR.mkdir(exist_ok=True)

@dataclass
class FormField:
    name: str
    label: str
    value: str
    field_type: str = "text"
    required: bool = False
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    tab_index: int = 0
    options: List[str] = field(default_factory=list)
    validation: str = ""

@dataclass
class FormTemplate:
    template_id: str
    name: str
    description: str
    fields: List[FormField]
    submit_label: str = "Submit"
    cancel_label: str = "Cancel"
    url_pattern: str = ""
    window_title_pattern: str = ""
    created: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class FormProfile:
    profile_id: str
    name: str
    data: Dict[str, str]
    description: str = ""
    created: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class FillResult:
    template_name: str
    profile_name: str
    fields_filled: int
    fields_failed: int
    fields_skipped: int
    submitted: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    errors: List[str] = field(default_factory=list)

class ScreenReader:
    def __init__(self):
        tc = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if os.path.exists(tc):
            pytesseract.pytesseract.tesseract_cmd = tc

    def grab(self, x=0, y=0, w=0, h=0) -> Image.Image:
        if w and h:
            return ImageGrab.grab(bbox=(x, y, x+w, y+h))
        return ImageGrab.grab()

    def find_text_location(self, text: str, confidence: int = 40) -> Optional[Tuple[int,int]]:
        img = self.grab()
        enh = ImageEnhance.Contrast(img).enhance(1.5)
        try:
            data = pytesseract.image_to_data(enh, output_type=pytesseract.Output.DICT)
            for i, w_text in enumerate(data['text']):
                if text.lower() in w_text.lower() and int(data['conf'][i]) > confidence:
                    x = data['left'][i] + data['width'][i] // 2
                    y = data['top'][i] + data['height'][i] // 2
                    return (x, y)
        except Exception as e:
            log.debug(f"OCR location error: {e}")
        return None

    def find_all_text_locations(self, text: str, confidence: int = 40) -> List[Tuple[int,int]]:
        img = self.grab()
        enh = ImageEnhance.Contrast(img).enhance(1.5)
        results = []
        try:
            data = pytesseract.image_to_data(enh, output_type=pytesseract.Output.DICT)
            for i, w_text in enumerate(data['text']):
                if text.lower() in w_text.lower() and int(data['conf'][i]) > confidence:
                    x = data['left'][i] + data['width'][i] // 2
                    y = data['top'][i] + data['height'][i] // 2
                    results.append((x, y))
        except Exception as e:
            log.debug(f"OCR all locations error: {e}")
        return results

    def read_region(self, x: int, y: int, w: int, h: int) -> str:
        img = self.grab(x, y, w, h)
        enh = ImageEnhance.Contrast(img).enhance(1.5).convert('L')
        try:
            return pytesseract.image_to_string(enh, config='--psm 6').strip()
        except Exception:
            return ""

    def wait_for_text(self, text: str, timeout: float = 10.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if self.find_text_location(text):
                return True
            time.sleep(0.5)
        return False

class FieldNavigator:
    def __init__(self, reader: ScreenReader):
        self.reader = reader

    def click_field_by_label(self, label: str,
                              offset_x: int = 200, offset_y: int = 0) -> bool:
        pos = self.reader.find_text_location(label)
        if pos:
            field_x = pos[0] + offset_x
            field_y = pos[1] + offset_y
            pyautogui.click(field_x, field_y)
            time.sleep(0.3)
            return True
        log.warning(f"Label not found: {label}")
        return False

    def click_at(self, x: int, y: int):
        pyautogui.click(x, y)
        time.sleep(0.2)

    def tab_to_next(self):
        pyautogui.press('tab')
        time.sleep(0.2)

    def clear_field(self):
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyautogui.press('delete')
        time.sleep(0.1)

    def type_text(self, text: str, speed: float = 0.04):
        for char in text:
            pyautogui.typewrite(char, interval=speed)
        time.sleep(0.1)

    def select_dropdown(self, label: str, value: str) -> bool:
        pos = self.reader.find_text_location(label)
        if not pos:
            return False
        pyautogui.click(pos[0] + 150, pos[1])
        time.sleep(0.5)
        opt_pos = self.reader.find_text_location(value)
        if opt_pos:
            pyautogui.click(*opt_pos)
            time.sleep(0.3)
            return True
        return False

    def click_checkbox(self, label: str) -> bool:
        pos = self.reader.find_text_location(label)
        if pos:
            pyautogui.click(pos[0] - 20, pos[1])
            time.sleep(0.2)
            return True
        return False

    def click_radio(self, label: str) -> bool:
        pos = self.reader.find_text_location(label)
        if pos:
            pyautogui.click(pos[0] - 15, pos[1])
            time.sleep(0.2)
            return True
        return False

class FormValidator:
    def validate_email(self, value: str) -> bool:
        return bool(re.match(r'^[^@]+@[^@]+\.[^@]+$', value))

    def validate_phone(self, value: str) -> bool:
        cleaned = re.sub(r'[^0-9]', '', value)
        return 7 <= len(cleaned) <= 15

    def validate_date(self, value: str) -> bool:
        patterns = [
            r'^\d{4}-\d{2}-\d{2}$',
            r'^\d{2}/\d{2}/\d{4}$',
            r'^\d{2}-\d{2}-\d{4}$'
        ]
        return any(re.match(p, value) for p in patterns)

    def validate_required(self, value: str) -> bool:
        return bool(value.strip())

    def validate_field(self, field: FormField) -> Tuple[bool, str]:
        value = field.value
        if field.required and not self.validate_required(value):
            return False, f"Field '{field.name}' is required"
        if not value:
            return True, ""
        if field.validation == "email" and not self.validate_email(value):
            return False, f"Invalid email: {value}"
        if field.validation == "phone" and not self.validate_phone(value):
            return False, f"Invalid phone: {value}"
        if field.validation == "date" and not self.validate_date(value):
            return False, f"Invalid date: {value}"
        return True, ""

class FormFiller:
    def __init__(self):
        self.reader = ScreenReader()
        self.navigator = FieldNavigator(self.reader)
        self.validator = FormValidator()

    def fill_field(self, field: FormField) -> bool:
        log.info(f"Filling field '{field.name}' = '{field.value[:30]}'")
        if field.x > 0 and field.y > 0:
            self.navigator.click_at(field.x, field.y)
        else:
            found = self.navigator.click_field_by_label(field.label)
            if not found:
                log.warning(f"Could not find field: {field.label}")
                return False
        time.sleep(0.2)
        if field.field_type == "text":
            self.navigator.clear_field()
            self.navigator.type_text(field.value)
        elif field.field_type == "textarea":
            self.navigator.clear_field()
            self.navigator.type_text(field.value.replace("\\n", "\n"))
        elif field.field_type == "dropdown":
            self.navigator.select_dropdown(field.label, field.value)
        elif field.field_type == "checkbox":
            self.navigator.click_checkbox(field.label)
        elif field.field_type == "radio":
            self.navigator.click_radio(field.value)
        elif field.field_type == "date":
            self.navigator.clear_field()
            self.navigator.type_text(field.value)
        elif field.field_type == "password":
            self.navigator.clear_field()
            self.navigator.type_text(field.value)
        return True

    def fill_form(self, template: FormTemplate, profile: FormProfile,
                  submit: bool = False) -> FillResult:
        filled = 0
        failed = 0
        skipped = 0
        errors = []
        profile_data = profile.data
        fields = sorted(template.fields, key=lambda f: f.tab_index)
        for field in fields:
            if field.name in profile_data:
                field.value = profile_data[field.name]
            elif field.label.lower() in {k.lower(): v for k, v in profile_data.items()}:
                lk = {k.lower(): v for k, v in profile_data.items()}
                field.value = lk.get(field.label.lower(), field.value)
            if not field.value:
                if field.required:
                    errors.append(f"Required field missing: {field.name}")
                    failed += 1
                else:
                    skipped += 1
                continue
            valid, err_msg = self.validator.validate_field(field)
            if not valid:
                errors.append(err_msg)
                failed += 1
                continue
            success = self.fill_field(field)
            if success:
                filled += 1
            else:
                failed += 1
                errors.append(f"Could not fill: {field.name}")
            time.sleep(0.2)
        submitted = False
        if submit and not errors:
            submit_pos = self.reader.find_text_location(template.submit_label)
            if submit_pos:
                pyautogui.click(*submit_pos)
                time.sleep(1.5)
                submitted = True
                log.info("Form submitted")
            else:
                pyautogui.press('enter')
                time.sleep(1.0)
                submitted = True
        return FillResult(
            template_name=template.name,
            profile_name=profile.name,
            fields_filled=filled,
            fields_failed=failed,
            fields_skipped=skipped,
            submitted=submitted,
            errors=errors
        )

class TemplateStorage:
    def __init__(self):
        self.path = DATA_DIR / "templates.json"
        self.templates: Dict[str, FormTemplate] = {}
        self._load_defaults()
        self._load()

    def _load_defaults(self):
        t1 = FormTemplate(
            template_id="login_form",
            name="Login Form",
            description="Generic login form",
            fields=[
                FormField("username", "Username", "", "text", True, tab_index=1),
                FormField("password", "Password", "", "password", True, tab_index=2),
            ],
            submit_label="Login"
        )
        t2 = FormTemplate(
            template_id="contact_form",
            name="Contact Form",
            description="Generic contact form",
            fields=[
                FormField("first_name", "First Name", "", "text", True, tab_index=1),
                FormField("last_name", "Last Name", "", "text", True, tab_index=2),
                FormField("email", "Email", "", "text", True, tab_index=3, validation="email"),
                FormField("phone", "Phone", "", "text", False, tab_index=4, validation="phone"),
                FormField("message", "Message", "", "textarea", True, tab_index=5),
            ],
            submit_label="Send"
        )
        self.templates["login_form"] = t1
        self.templates["contact_form"] = t2

    def _load(self):
        if self.path.exists():
            with open(self.path) as f:
                data = json.load(f)
            for tid, td in data.items():
                fields = [FormField(**f) for f in td.pop('fields', [])]
                t = FormTemplate(**td)
                t.fields = fields
                self.templates[tid] = t

    def _save(self):
        with open(self.path, 'w') as f:
            json.dump({k: asdict(v) for k, v in self.templates.items()}, f, indent=2)

    def get(self, name: str) -> Optional[FormTemplate]:
        return self.templates.get(name)

    def add(self, template: FormTemplate):
        self.templates[template.template_id] = template
        self._save()

    def list_all(self):
        print(f"{'ID':<20} {'Name':<24} {'Fields'}")
        print("-" * 50)
        for tid, t in self.templates.items():
            print(f"{tid:<20} {t.name:<24} {len(t.fields)}")

class ProfileStorage:
    def __init__(self):
        self.path = DATA_DIR / "profiles.json"
        self.profiles: Dict[str, FormProfile] = {}
        self._load_defaults()
        self._load()

    def _load_defaults(self):
        p = FormProfile(
            profile_id="default",
            name="Default Profile",
            data={
                "first_name": "John", "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "555-1234", "username": "johndoe",
                "message": "Hello, I would like more information."
            }
        )
        self.profiles["default"] = p

    def _load(self):
        if self.path.exists():
            with open(self.path) as f:
                data = json.load(f)
            for pid, pd in data.items():
                self.profiles[pid] = FormProfile(**pd)

    def _save(self):
        with open(self.path, 'w') as f:
            json.dump({k: asdict(v) for k, v in self.profiles.items()}, f, indent=2)

    def get(self, name: str) -> Optional[FormProfile]:
        return self.profiles.get(name)

    def add(self, profile: FormProfile):
        self.profiles[profile.profile_id] = profile
        self._save()

    def list_all(self):
        print(f"{'ID':<20} {'Name':<24} {'Fields'}")
        print("-" * 50)
        for pid, p in self.profiles.items():
            print(f"{pid:<20} {p.name:<24} {len(p.data)}")

def main():
    parser = argparse.ArgumentParser(description="Auto Form Filler")
    sub = parser.add_subparsers(dest="cmd")

    p_fill = sub.add_parser("fill", help="Fill a form using template and profile")
    p_fill.add_argument("template")
    p_fill.add_argument("profile")
    p_fill.add_argument("--submit", action="store_true")
    p_fill.add_argument("--delay", type=float, default=3.0, help="Seconds before starting")

    p_tmpl = sub.add_parser("template", help="Manage templates")
    p_tmpl.add_argument("action", choices=["list","show","delete"])
    p_tmpl.add_argument("--id", default=None)

    p_prof = sub.add_parser("profile", help="Manage profiles")
    p_prof.add_argument("action", choices=["list","add","show"])
    p_prof.add_argument("--id", default=None)
    p_prof.add_argument("--name", default="")
    p_prof.add_argument("--data", default="{}", help="JSON data dict")

    p_find = sub.add_parser("find", help="Find text on screen")
    p_find.add_argument("text")

    args = parser.parse_args()
    template_storage = TemplateStorage()
    profile_storage = ProfileStorage()
    filler = FormFiller()

    if args.cmd == "fill":
        template = template_storage.get(args.template)
        if not template:
            print(f"Template not found: {args.template}")
            return
        profile = profile_storage.get(args.profile)
        if not profile:
            print(f"Profile not found: {args.profile}")
            return
        if args.delay > 0:
            print(f"Starting in {args.delay}s... switch to the form window.")
            time.sleep(args.delay)
        result = filler.fill_form(template, profile, args.submit)
        print(f"\nFill Result:")
        print(f"  Template: {result.template_name}")
        print(f"  Profile: {result.profile_name}")
        print(f"  Filled: {result.fields_filled}")
        print(f"  Failed: {result.fields_failed}")
        print(f"  Skipped: {result.fields_skipped}")
        print(f"  Submitted: {result.submitted}")
        if result.errors:
            print(f"  Errors:")
            for e in result.errors:
                print(f"    - {e}")

    elif args.cmd == "template":
        if args.action == "list":
            template_storage.list_all()
        elif args.action == "show":
            t = template_storage.get(args.id)
            if not t:
                print(f"Template not found: {args.id}")
                return
            print(f"Template: {t.name} ({t.template_id})")
            print(f"Description: {t.description}")
            print(f"Submit: {t.submit_label}")
            print("Fields:")
            for f in t.fields:
                print(f"  {f.tab_index}: {f.name} ({f.field_type}) {'[required]' if f.required else ''}")
        elif args.action == "delete":
            if args.id in template_storage.templates:
                del template_storage.templates[args.id]
                template_storage._save()
                print(f"Deleted template: {args.id}")

    elif args.cmd == "profile":
        if args.action == "list":
            profile_storage.list_all()
        elif args.action == "add":
            try:
                data = json.loads(args.data)
            except json.JSONDecodeError:
                print("Invalid JSON for --data")
                return
            pid = args.id or datetime.now().strftime("%Y%m%d%H%M%S")
            p = FormProfile(profile_id=pid, name=args.name or pid, data=data)
            profile_storage.add(p)
            print(f"Profile added: {pid}")
        elif args.action == "show":
            p = profile_storage.get(args.id)
            if not p:
                print(f"Profile not found: {args.id}")
                return
            print(f"Profile: {p.name} ({p.profile_id})")
            for k, v in p.data.items():
                masked = v if k.lower() != "password" else "***"
                print(f"  {k}: {masked}")

    elif args.cmd == "find":
        reader = ScreenReader()
        pos = reader.find_text_location(args.text)
        if pos:
            print(f"Found '{args.text}' at {pos}")
            pyautogui.moveTo(*pos, duration=0.3)
        else:
            print(f"Text not found: {args.text}")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
