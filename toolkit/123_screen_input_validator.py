#!/usr/bin/env python3
"""Screen Input Validator - Validate and test input fields on-screen using OCR and automation."""

import pyautogui
import time
import json
import os
import argparse
import threading
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Callable
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont


@dataclass
class ValidationRule:
    """A rule for validating input field content."""
    rule_id: str
    name: str
    rule_type: str
    pattern: str = ""
    min_length: int = 0
    max_length: int = 0
    min_value: float = 0.0
    max_value: float = 0.0
    required: bool = True
    allowed_chars: str = ""
    forbidden_chars: str = ""
    custom_message: str = ""
    case_sensitive: bool = False


@dataclass
class InputField:
    """A screen input field to validate."""
    field_id: str
    name: str
    region: Tuple[int, int, int, int]
    validation_rules: List[str] = field(default_factory=list)
    label: str = ""
    expected_value: str = ""
    click_to_activate: bool = True
    tab_to_next: bool = True
    description: str = ""


@dataclass
class ValidationResult:
    """Result of validating a single field."""
    result_id: str
    field_id: str
    field_name: str
    actual_value: str
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: str = ""
    screenshot_path: str = ""
    duration_ms: float = 0.0


@dataclass
class TestSuite:
    """A suite of field validation tests."""
    suite_id: str
    name: str
    fields: List[str] = field(default_factory=list)
    description: str = ""
    created_at: str = ""
    pass_count: int = 0
    fail_count: int = 0
    last_run: str = ""


class OCRFieldReader:
    """Reads text from input fields using OCR."""

    def __init__(self):
        self._ocr_available = False
        try:
            import pytesseract
            self._ocr_available = True
        except ImportError:
            pass

    def read_field(self, region: Tuple[int, int, int, int],
                   preprocess: bool = True) -> str:
        screenshot = pyautogui.screenshot(region=region)
        if not self._ocr_available:
            return ""
        import pytesseract
        if preprocess:
            screenshot = self._preprocess(screenshot)
        config = '--oem 3 --psm 7'
        text = pytesseract.image_to_string(screenshot, config=config).strip()
        return text

    def _preprocess(self, img: Image.Image) -> Image.Image:
        from PIL import ImageEnhance, ImageFilter
        gray = img.convert('L')
        enhanced = ImageEnhance.Contrast(gray).enhance(2.0)
        sharpened = enhanced.filter(ImageFilter.SHARPEN)
        threshold = sharpened.point(lambda x: 0 if x < 140 else 255)
        scaled = threshold.resize(
            (threshold.width * 2, threshold.height * 2),
            Image.LANCZOS
        )
        return scaled

    def read_multiple(self, fields: List[InputField]) -> Dict[str, str]:
        results = {}
        for field_obj in fields:
            text = self.read_field(field_obj.region)
            results[field_obj.field_id] = text
            print(f"  Read {field_obj.name}: '{text[:50]}'")
        return results


class RuleEngine:
    """Evaluates validation rules against field values."""

    def validate(self, value: str, rule: ValidationRule) -> Tuple[bool, str]:
        error_msg = rule.custom_message

        if rule.required and not value.strip():
            return False, error_msg or f"{rule.name}: Field is required"

        if not value.strip() and not rule.required:
            return True, ""

        if rule.rule_type == "email":
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+.[a-zA-Z]{2,}$'
            if not re.match(pattern, value):
                return False, error_msg or f"{rule.name}: Invalid email format"

        elif rule.rule_type == "url":
            pattern = r'^https?://[^s/$.?#].[^s]*$'
            if not re.match(pattern, value):
                return False, error_msg or f"{rule.name}: Invalid URL format"

        elif rule.rule_type == "phone":
            cleaned = re.sub(r'[s-()+]', '', value)
            if not cleaned.isdigit() or len(cleaned) < 7 or len(cleaned) > 15:
                return False, error_msg or f"{rule.name}: Invalid phone number"

        elif rule.rule_type == "integer":
            try:
                int_val = int(value)
                if rule.min_value != 0 and int_val < rule.min_value:
                    return False, error_msg or f"{rule.name}: Value must be >= {int(rule.min_value)}"
                if rule.max_value != 0 and int_val > rule.max_value:
                    return False, error_msg or f"{rule.name}: Value must be <= {int(rule.max_value)}"
            except ValueError:
                return False, error_msg or f"{rule.name}: Must be an integer"

        elif rule.rule_type == "float":
            try:
                float_val = float(value)
                if rule.min_value != 0 and float_val < rule.min_value:
                    return False, error_msg or f"{rule.name}: Value must be >= {rule.min_value}"
                if rule.max_value != 0 and float_val > rule.max_value:
                    return False, error_msg or f"{rule.name}: Value must be <= {rule.max_value}"
            except ValueError:
                return False, error_msg or f"{rule.name}: Must be a number"

        elif rule.rule_type == "date":
            from datetime import datetime as dt
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']:
                try:
                    dt.strptime(value, fmt)
                    return True, ""
                except ValueError:
                    pass
            return False, error_msg or f"{rule.name}: Invalid date format"

        elif rule.rule_type == "regex":
            flags = 0 if rule.case_sensitive else re.IGNORECASE
            if not re.match(rule.pattern, value, flags):
                return False, error_msg or f"{rule.name}: Does not match pattern"

        elif rule.rule_type == "length":
            ln = len(value)
            if rule.min_length > 0 and ln < rule.min_length:
                return False, error_msg or f"{rule.name}: Min length {rule.min_length}"
            if rule.max_length > 0 and ln > rule.max_length:
                return False, error_msg or f"{rule.name}: Max length {rule.max_length}"

        elif rule.rule_type == "alphanumeric":
            check = value if rule.case_sensitive else value.lower()
            if not check.replace(' ', '').isalnum():
                return False, error_msg or f"{rule.name}: Must be alphanumeric"

        elif rule.rule_type == "not_empty":
            if not value.strip():
                return False, error_msg or f"{rule.name}: Cannot be empty"

        elif rule.rule_type == "exact":
            comp_val = value if rule.case_sensitive else value.lower()
            comp_pat = rule.pattern if rule.case_sensitive else rule.pattern.lower()
            if comp_val != comp_pat:
                return False, error_msg or f"{rule.name}: Expected '{rule.pattern}'"

        elif rule.rule_type == "contains":
            check_val = value if rule.case_sensitive else value.lower()
            check_pat = rule.pattern if rule.case_sensitive else rule.pattern.lower()
            if check_pat not in check_val:
                return False, error_msg or f"{rule.name}: Must contain '{rule.pattern}'"

        elif rule.rule_type == "starts_with":
            if not value.startswith(rule.pattern):
                return False, error_msg or f"{rule.name}: Must start with '{rule.pattern}'"

        elif rule.rule_type == "ends_with":
            if not value.endswith(rule.pattern):
                return False, error_msg or f"{rule.name}: Must end with '{rule.pattern}'"

        elif rule.rule_type == "allowed_chars":
            for char in value:
                if char not in rule.allowed_chars:
                    return False, error_msg or f"{rule.name}: Invalid char '{char}'"

        elif rule.rule_type == "forbidden_chars":
            for char in value:
                if char in rule.forbidden_chars:
                    return False, error_msg or f"{rule.name}: Forbidden char '{char}'"

        if rule.min_length > 0 and len(value) < rule.min_length:
            return False, error_msg or f"{rule.name}: Too short (min {rule.min_length})"
        if rule.max_length > 0 and len(value) > rule.max_length:
            return False, error_msg or f"{rule.name}: Too long (max {rule.max_length})"

        return True, ""


class ScreenInputValidator:
    """Main screen input validation tool."""

    def __init__(self, data_dir: str = "input_validator_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir = self.data_dir / "screenshots"
        self.screenshots_dir.mkdir(exist_ok=True)
        self.rules: Dict[str, ValidationRule] = {}
        self.fields: Dict[str, InputField] = {}
        self.suites: Dict[str, TestSuite] = {}
        self.results: List[ValidationResult] = []
        self.ocr = OCRFieldReader()
        self.engine = RuleEngine()
        self._load_data()

    def _load_data(self):
        df = self.data_dir / "data.json"
        if df.exists():
            try:
                with open(df, 'r') as f:
                    data = json.load(f)
                for rid, rdata in data.get('rules', {}).items():
                    self.rules[rid] = ValidationRule(**rdata)
                for fid, fdata in data.get('fields', {}).items():
                    fdata['region'] = tuple(fdata['region'])
                    self.fields[fid] = InputField(**fdata)
                for sid, sdata in data.get('suites', {}).items():
                    self.suites[sid] = TestSuite(**sdata)
                print(f"Loaded {len(self.rules)} rules, {len(self.fields)} fields")
            except Exception as e:
                print(f"Error loading data: {e}")

    def _save_data(self):
        df = self.data_dir / "data.json"
        fdata = {}
        for fid, f in self.fields.items():
            d = asdict(f)
            d['region'] = list(d['region'])
            fdata[fid] = d
        data = {
            'rules': {rid: asdict(r) for rid, r in self.rules.items()},
            'fields': fdata,
            'suites': {sid: asdict(s) for sid, s in self.suites.items()}
        }
        with open(df, 'w') as f:
            json.dump(data, f, indent=2)

    def add_rule(self, name: str, rule_type: str, pattern: str = "",
                  min_length: int = 0, max_length: int = 0,
                  required: bool = True, custom_message: str = "") -> ValidationRule:
        rid = f"rule_{int(time.time() * 1000)}"
        rule = ValidationRule(
            rule_id=rid, name=name, rule_type=rule_type,
            pattern=pattern, min_length=min_length, max_length=max_length,
            required=required, custom_message=custom_message
        )
        self.rules[rid] = rule
        self._save_data()
        print(f"Rule added: {name} ({rule_type})")
        return rule

    def add_field(self, name: str, x: int, y: int, w: int, h: int,
                   rule_ids: List[str] = None, label: str = "") -> InputField:
        fid = f"field_{int(time.time() * 1000)}"
        field_obj = InputField(
            field_id=fid, name=name, region=(x, y, w, h),
            validation_rules=rule_ids or [], label=label or name
        )
        self.fields[fid] = field_obj
        self._save_data()
        print(f"Field added: {name} at ({x},{y}) {w}x{h}")
        return field_obj

    def validate_field(self, field_id: str,
                        screenshot: bool = True) -> ValidationResult:
        if field_id not in self.fields:
            print(f"Field not found: {field_id}")
            return None
        field_obj = self.fields[field_id]
        start = time.time()
        if field_obj.click_to_activate:
            cx = field_obj.region[0] + field_obj.region[2] // 2
            cy = field_obj.region[1] + field_obj.region[3] // 2
            pyautogui.click(cx, cy, _pause=False)
            time.sleep(0.2)

        actual_value = self.ocr.read_field(field_obj.region)
        errors = []
        warnings = []
        for rule_id in field_obj.validation_rules:
            if rule_id not in self.rules:
                continue
            rule = self.rules[rule_id]
            passed, message = self.engine.validate(actual_value, rule)
            if not passed:
                errors.append(message)

        if field_obj.expected_value:
            if actual_value.strip() != field_obj.expected_value.strip():
                warnings.append(
                    f"Expected '{field_obj.expected_value}', got '{actual_value}'"
                )

        duration_ms = (time.time() - start) * 1000
        result = ValidationResult(
            result_id=f"result_{int(time.time() * 1000)}",
            field_id=field_id,
            field_name=field_obj.name,
            actual_value=actual_value,
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            timestamp=datetime.now().isoformat(),
            duration_ms=round(duration_ms, 2)
        )

        if screenshot:
            ss = pyautogui.screenshot()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            ss_path = str(self.screenshots_dir / f"field_{field_id}_{ts}.png")
            draw = ImageDraw.Draw(ss)
            x, y, w, h = field_obj.region
            color = (0, 200, 0) if result.passed else (200, 0, 0)
            draw.rectangle([x, y, x+w, y+h], outline=color, width=3)
            ss.save(ss_path)
            result.screenshot_path = ss_path

        self.results.append(result)
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {field_obj.name}: '{actual_value[:40]}'")
        for err in errors:
            print(f"    ERROR: {err}")
        for warn in warnings:
            print(f"    WARN: {warn}")
        return result

    def validate_all(self, delay_between: float = 0.5) -> List[ValidationResult]:
        print(f"Validating {len(self.fields)} fields...")
        results = []
        for fid in self.fields:
            result = self.validate_field(fid)
            if result:
                results.append(result)
            time.sleep(delay_between)
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        print(f"\nValidation complete: {passed} PASS, {failed} FAIL")
        return results

    def input_and_validate(self, field_id: str, value: str) -> ValidationResult:
        if field_id not in self.fields:
            print(f"Field not found: {field_id}")
            return None
        field_obj = self.fields[field_id]
        cx = field_obj.region[0] + field_obj.region[2] // 2
        cy = field_obj.region[1] + field_obj.region[3] // 2
        print(f"Typing '{value[:30]}' into {field_obj.name}...")
        pyautogui.click(cx, cy)
        time.sleep(0.2)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.05)
        pyautogui.typewrite(value if value.isascii() else '', interval=0.05)
        if not value.isascii():
            import pyperclip
            pyperclip.copy(value)
            pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)
        return self.validate_field(field_id)

    def generate_report(self, output: Optional[str] = None) -> str:
        if not output:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = str(self.data_dir / f"validation_report_{ts}.json")
        report = {
            'generated_at': datetime.now().isoformat(),
            'total_results': len(self.results),
            'passed': sum(1 for r in self.results if r.passed),
            'failed': sum(1 for r in self.results if not r.passed),
            'results': [asdict(r) for r in self.results[-100:]]
        }
        with open(output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved: {output}")
        return output

    def list_all(self):
        if self.rules:
            print(f"Validation Rules ({len(self.rules)}):")
            for rid, r in self.rules.items():
                print(f"  [{rid}] {r.name} ({r.rule_type})")
                if r.pattern:
                    print(f"    Pattern: {r.pattern}")
        if self.fields:
            print(f"\nInput Fields ({len(self.fields)}):")
            for fid, f in self.fields.items():
                print(f"  [{fid}] {f.name} at {f.region}")
                if f.validation_rules:
                    rule_names = [self.rules[r].name for r in f.validation_rules if r in self.rules]
                    print(f"    Rules: {', '.join(rule_names)}")


def main():
    parser = argparse.ArgumentParser(description='Screen Input Validator')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    rule_p = subparsers.add_parser('rule', help='Add validation rule')
    rule_p.add_argument('name', help='Rule name')
    rule_p.add_argument('type', help='Rule type (email, url, regex, length, integer, etc.)')
    rule_p.add_argument('--pattern', default='', help='Regex or comparison pattern')
    rule_p.add_argument('--min-length', type=int, default=0)
    rule_p.add_argument('--max-length', type=int, default=0)
    rule_p.add_argument('--not-required', action='store_true')
    rule_p.add_argument('--message', default='', help='Custom error message')

    field_p = subparsers.add_parser('field', help='Define input field')
    field_p.add_argument('name', help='Field name')
    field_p.add_argument('x', type=int)
    field_p.add_argument('y', type=int)
    field_p.add_argument('w', type=int)
    field_p.add_argument('h', type=int)
    field_p.add_argument('--rules', nargs='*', default=[], help='Rule IDs to apply')
    field_p.add_argument('--label', default='')

    val_p = subparsers.add_parser('validate', help='Validate a field')
    val_p.add_argument('field_id', help='Field ID (or "all")')

    inp_p = subparsers.add_parser('input', help='Type value and validate')
    inp_p.add_argument('field_id', help='Field ID')
    inp_p.add_argument('value', help='Value to input')

    subparsers.add_parser('report', help='Generate validation report')
    subparsers.add_parser('list', help='List rules and fields')

    args = parser.parse_args()
    validator = ScreenInputValidator()

    if args.command == 'rule':
        validator.add_rule(
            args.name, args.type, pattern=args.pattern,
            min_length=args.min_length, max_length=args.max_length,
            required=not args.not_required, custom_message=args.message
        )
    elif args.command == 'field':
        validator.add_field(args.name, args.x, args.y, args.w, args.h,
                            rule_ids=args.rules, label=args.label)
    elif args.command == 'validate':
        if args.field_id == 'all':
            validator.validate_all()
        else:
            validator.validate_field(args.field_id)
    elif args.command == 'input':
        print("Starting in 3 seconds...")
        time.sleep(3)
        validator.input_and_validate(args.field_id, args.value)
    elif args.command == 'report':
        validator.generate_report()
    elif args.command == 'list':
        validator.list_all()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
