"""
toolkit_46_password_tools.py
Password generation, strength analysis, hashing, and secure string
operations. No external dependencies (stdlib only).
"""
from __future__ import annotations
import random
import string
import hashlib
import secrets
import re
from typing import Any, Dict, List

def generate_password(length: int = 16, use_upper: bool = True, use_lower: bool = True,
                       use_digits: bool = True, use_symbols: bool = True, exclude_ambiguous: bool = False) -> Dict[str, Any]:
    try:
        chars = ""
        if use_lower:
            chars += string.ascii_lowercase
        if use_upper:
            chars += string.ascii_uppercase
        if use_digits:
            chars += string.digits
        if use_symbols:
            chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"
        if exclude_ambiguous:
            for c in "0O1lI|":
                chars = chars.replace(c, "")
        if not chars:
            return {"success": False, "data": None, "error": "No character set selected"}
        password = "".join(secrets.choice(chars) for _ in range(length))
        return {"success": True, "data": password, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def generate_passphrase(word_count: int = 4, separator: str = "-", capitalize: bool = True) -> Dict[str, Any]:
    """Generate a memorable passphrase from random words."""
    try:
        word_list = [
            "apple", "brave", "cloud", "dance", "eagle", "flame", "grace", "horse",
            "input", "jewel", "knife", "lemon", "magic", "night", "ocean", "piano",
            "queen", "river", "stone", "tiger", "ultra", "vivid", "water", "xenon",
            "yacht", "zebra", "amber", "burst", "crisp", "drift", "ember", "frost",
            "gleam", "haven", "ivory", "jolt", "lunar", "marsh", "noble", "oxide",
            "prism", "quest", "razor", "swift", "torch", "unity", "vapor", "whirl"
        ]
        words = [secrets.choice(word_list) for _ in range(word_count)]
        if capitalize:
            words = [w.capitalize() for w in words]
        passphrase = separator.join(words)
        return {"success": True, "data": passphrase, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def generate_pin(length: int = 6) -> Dict[str, Any]:
    try:
        pin = "".join(secrets.choice(string.digits) for _ in range(length))
        return {"success": True, "data": pin, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def generate_token(length: int = 32) -> Dict[str, Any]:
    """Generate a cryptographically secure URL-safe token."""
    try:
        return {"success": True, "data": secrets.token_urlsafe(length), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def generate_hex_key(bytes_count: int = 32) -> Dict[str, Any]:
    try:
        return {"success": True, "data": secrets.token_hex(bytes_count), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_password_strength(password: str) -> Dict[str, Any]:
    try:
        length = len(password)
        has_upper = bool(re.search(r"[A-Z]", password))
        has_lower = bool(re.search(r"[a-z]", password))
        has_digit = bool(re.search(r"\d", password))
        has_symbol = bool(re.search(r"[^a-zA-Z0-9]", password))
        score = 0
        if length >= 8: score += 1
        if length >= 12: score += 1
        if length >= 16: score += 1
        if has_upper: score += 1
        if has_lower: score += 1
        if has_digit: score += 1
        if has_symbol: score += 1
        if length >= 20: score += 1
        level = "very weak" if score <= 2 else "weak" if score <= 3 else "fair" if score <= 4 else "strong" if score <= 6 else "very strong"
        return {"success": True, "data": {
            "score": score, "max_score": 8, "strength": level,
            "length": length, "has_upper": has_upper, "has_lower": has_lower,
            "has_digit": has_digit, "has_symbol": has_symbol
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def hash_password(password: str, salt: str = "") -> Dict[str, Any]:
    try:
        if not salt:
            salt = secrets.token_hex(16)
        combined = salt + password
        h = hashlib.sha256(combined.encode()).hexdigest()
        return {"success": True, "data": {"hash": h, "salt": salt}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def verify_password_hash(password: str, stored_hash: str, salt: str) -> Dict[str, Any]:
    try:
        computed = hashlib.sha256((salt + password).encode()).hexdigest()
        match = computed == stored_hash
        return {"success": True, "data": {"match": match}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def generate_uuid() -> Dict[str, Any]:
    try:
        import uuid
        return {"success": True, "data": str(uuid.uuid4()), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def generate_multiple_passwords(count: int = 5, length: int = 16) -> Dict[str, Any]:
    try:
        passwords = []
        for _ in range(count):
            r = generate_password(length)
            if r["success"]:
                passwords.append(r["data"])
        return {"success": True, "data": passwords, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_password_common(password: str) -> Dict[str, Any]:
    """Check if password is in a short list of common passwords."""
    try:
        common = {
            "password", "123456", "password1", "12345678", "qwerty", "abc123",
            "monkey", "1234567", "letmein", "trustno1", "dragon", "baseball",
            "iloveyou", "master", "sunshine", "ashley", "bailey", "passw0rd",
            "shadow", "123123", "654321", "superman", "qazwsx", "michael",
            "football", "passwd", "admin", "welcome", "login", "1234", "test"
        }
        is_common = password.lower() in common
        return {"success": True, "data": {"is_common": is_common}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def mask_password(password: str, visible_chars: int = 2) -> Dict[str, Any]:
    try:
        if len(password) <= visible_chars * 2:
            masked = "*" * len(password)
        else:
            masked = password[:visible_chars] + "*" * (len(password) - visible_chars * 2) + password[-visible_chars:]
        return {"success": True, "data": masked, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def estimate_crack_time(password: str) -> Dict[str, Any]:
    """Rough estimate of brute-force time at 1 billion guesses/sec."""
    try:
        charset = 0
        if re.search(r"[a-z]", password): charset += 26
        if re.search(r"[A-Z]", password): charset += 26
        if re.search(r"\d", password): charset += 10
        if re.search(r"[^a-zA-Z0-9]", password): charset += 32
        if charset == 0: charset = 26
        combinations = charset ** len(password)
        guesses_per_second = 1_000_000_000
        seconds = combinations / guesses_per_second
        if seconds < 60:
            time_str = str(round(seconds, 1)) + " seconds"
        elif seconds < 3600:
            time_str = str(round(seconds / 60, 1)) + " minutes"
        elif seconds < 86400:
            time_str = str(round(seconds / 3600, 1)) + " hours"
        elif seconds < 31536000:
            time_str = str(round(seconds / 86400, 1)) + " days"
        else:
            time_str = str(round(seconds / 31536000, 1)) + " years"
        return {"success": True, "data": {"estimated_time": time_str, "combinations": combinations, "charset_size": charset}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
