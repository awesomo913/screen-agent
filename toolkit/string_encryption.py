"""
string_encryption.py

Production-ready cryptography and encoding toolkit for screen agents.
Supports hashing, symmetric encryption, HMAC, encoding/decoding, 
compression, and standard string obfuscation.

Returns standardized Dict[str, Any] wrappers:
  - Success: {"success": True, "result": <value>}
  - Error:   {"success": False, "error": "<message>"}

Dependencies:
  pip install cryptography bcrypt
"""

import hashlib
import base64
import hmac
import secrets
import zlib
import uuid
import string
import codecs
from typing import Dict, Any

from cryptography.fernet import Fernet

# Optional: bcrypt is external but standard for password hashing
try:
    import bcrypt
except ImportError:
    bcrypt = None


def _fmt_result(data: Any) -> Dict[str, Any]:
    return {"success": True, "result": data}


def _fmt_error(msg: str) -> Dict[str, Any]:
    return {"success": False, "error": str(msg)}


# =============================================================================
# Hashing
# =============================================================================

def hash_md5(text: str) -> Dict[str, Any]:
    try:
        return _fmt_result(hashlib.md5(text.encode("utf-8")).hexdigest())
    except Exception as e:
        return _fmt_error(e)


def hash_sha256(text: str) -> Dict[str, Any]:
    try:
        return _fmt_result(hashlib.sha256(text.encode("utf-8")).hexdigest())
    except Exception as e:
        return _fmt_error(e)


def hash_sha512(text: str) -> Dict[str, Any]:
    try:
        return _fmt_result(hashlib.sha512(text.encode("utf-8")).hexdigest())
    except Exception as e:
        return _fmt_error(e)


def hash_bcrypt(text: str, rounds: int = 12) -> Dict[str, Any]:
    if bcrypt is None:
        return _fmt_error("bcrypt library not installed. Run: pip install bcrypt")
    try:
        if not (4 <= rounds <= 31):
            return _fmt_error("Rounds must be between 4 and 31")
        salt = bcrypt.gensalt(rounds=rounds)
        hashed = bcrypt.hashpw(text.encode("utf-8"), salt)
        return _fmt_result(hashed.decode("utf-8"))
    except Exception as e:
        return _fmt_error(e)


def verify_bcrypt(text: str, hashed: str) -> Dict[str, Any]:
    if bcrypt is None:
        return _fmt_error("bcrypt library not installed. Run: pip install bcrypt")
    try:
        is_valid = bcrypt.checkpw(text.encode("utf-8"), hashed.encode("utf-8"))
        return _fmt_result(is_valid)
    except Exception as e:
        return _fmt_error(e)


# =============================================================================
# Encoding / Decoding
# =============================================================================

def encode_base64(text: str) -> Dict[str, Any]:
    try:
        return _fmt_result(base64.b64encode(text.encode("utf-8")).decode("utf-8"))
    except Exception as e:
        return _fmt_error(e)


def decode_base64(encoded: str) -> Dict[str, Any]:
    try:
        return _fmt_result(base64.b64decode(encoded).decode("utf-8"))
    except Exception as e:
        return _fmt_error(f"Invalid Base64 string: {e}")


def encode_base32(text: str) -> Dict[str, Any]:
    try:
        return _fmt_result(base64.b32encode(text.encode("utf-8")).decode("utf-8"))
    except Exception as e:
        return _fmt_error(e)


def decode_base32(encoded: str) -> Dict[str, Any]:
    try:
        return _fmt_result(base64.b32decode(encoded).decode("utf-8"))
    except Exception as e:
        return _fmt_error(f"Invalid Base32 string: {e}")


def encode_hex(text: str) -> Dict[str, Any]:
    try:
        return _fmt_result(text.encode("utf-8").hex())
    except Exception as e:
        return _fmt_error(e)


def decode_hex(hex_string: str) -> Dict[str, Any]:
    try:
        return _fmt_result(bytes.fromhex(hex_string).decode("utf-8"))
    except Exception as e:
        return _fmt_error(f"Invalid hex string: {e}")


# =============================================================================
# Symmetric Encryption (Fernet)
# =============================================================================

def encrypt_fernet(text: str, key: str = "") -> Dict[str, Any]:
    try:
        key_provided = bool(key)
        if not key_provided:
            key = Fernet.generate_key().decode("utf-8")
        
        f = Fernet(key.encode("utf-8"))
        encrypted = f.encrypt(text.encode("utf-8")).decode("utf-8")
        payload = {"encrypted": encrypted}
        if not key_provided:
            payload["generated_key"] = key
        return _fmt_result(payload)
    except Exception as e:
        return _fmt_error(e)


def decrypt_fernet(encrypted: str, key: str) -> Dict[str, Any]:
    try:
        f = Fernet(key.encode("utf-8"))
        decrypted = f.decrypt(encrypted.encode("utf-8")).decode("utf-8")
        return _fmt_result(decrypted)
    except Exception as e:
        return _fmt_error(f"Decryption failed (check key & data): {e}")


# =============================================================================
# Generators
# =============================================================================

def generate_key(length: int = 32) -> Dict[str, Any]:
    try:
        if length < 1:
            return _fmt_error("Key length must be >= 1")
        return _fmt_result(secrets.token_hex(length))
    except Exception as e:
        return _fmt_error(e)


def generate_password(length: int = 16, uppercase: bool = True, digits: bool = True, special: bool = True) -> Dict[str, Any]:
    try:
        if length < 1:
            return _fmt_error("Password length must be >= 1")
        
        required_chars = int(uppercase) + int(digits) + int(special)
        if length < required_chars:
            return _fmt_error(f"Length too short for selected character sets (min {required_chars})")

        pool = string.ascii_lowercase
        forced = []
        if uppercase:
            pool += string.ascii_uppercase
            forced.append(secrets.choice(string.ascii_uppercase))
        if digits:
            pool += string.digits
            forced.append(secrets.choice(string.digits))
        if special:
            pool += string.punctuation
            forced.append(secrets.choice(string.punctuation))

        remaining = [secrets.choice(pool) for _ in range(length - len(forced))]
        password_list = forced + remaining
        secrets.SystemRandom().shuffle(password_list)
        return _fmt_result("".join(password_list))
    except Exception as e:
        return _fmt_error(e)


def generate_token(length: int = 32) -> Dict[str, Any]:
    try:
        return _fmt_result(secrets.token_urlsafe(length))
    except Exception as e:
        return _fmt_error(e)


def generate_uuid() -> Dict[str, Any]:
    try:
        return _fmt_result(str(uuid.uuid4()))
    except Exception as e:
        return _fmt_error(e)


# =============================================================================
# HMAC
# =============================================================================

def hmac_sign(message: str, key: str, algorithm: str = "sha256") -> Dict[str, Any]:
    try:
        sig = hmac.new(key.encode("utf-8"), message.encode("utf-8"), algorithm).hexdigest()
        return _fmt_result(sig)
    except Exception as e:
        return _fmt_error(f"HMAC signing failed (unsupported algorithm?): {e}")


def hmac_verify(message: str, key: str, signature: str, algorithm: str = "sha256") -> Dict[str, Any]:
    try:
        expected = hmac.new(key.encode("utf-8"), message.encode("utf-8"), algorithm).hexdigest()
        is_valid = hmac.compare_digest(expected, signature)
        return _fmt_result(is_valid)
    except Exception as e:
        return _fmt_error(f"HMAC verification failed: {e}")


# =============================================================================
# Classical & Lightweight Ciphers
# =============================================================================

def rot13(text: str) -> Dict[str, Any]:
    try:
        return _fmt_result(codecs.encode(text, "rot_13"))
    except Exception as e:
        return _fmt_error(e)


def caesar_cipher(text: str, shift: int = 3) -> Dict[str, Any]:
    try:
        shift = shift % 26
        result = []
        for char in text:
            if char.isalpha():
                base = ord("A") if char.isupper() else ord("a")
                result.append(chr((ord(char) - base + shift) % 26 + base))
            else:
                result.append(char)
        return _fmt_result("".join(result))
    except Exception as e:
        return _fmt_error(e)


def xor_encrypt(text: str, key: str) -> Dict[str, Any]:
    """XOR encryption returns Base64 to ensure byte-safe string transport."""
    if not key:
        return _fmt_error("Key cannot be empty")
    try:
        key_bytes = key.encode("utf-8")
        text_bytes = text.encode("utf-8")
        xored = bytes([t ^ key_bytes[i % len(key_bytes)] for i, t in enumerate(text_bytes)])
        return _fmt_result(base64.b64encode(xored).decode("utf-8"))
    except Exception as e:
        return _fmt_error(e)


# =============================================================================
# Compression
# =============================================================================

def compress_string(text: str) -> Dict[str, Any]:
    "Returns Base64-encoded compressed data for safe string transport."
    try:
        compressed = zlib.compress(text.encode("utf-8"))
        return _fmt_result(base64.b64encode(compressed).decode("utf-8"))
    except Exception as e:
        return _fmt_error(e)


def decompress_string(compressed: str) -> Dict[str, Any]:
    try:
        raw = base64.b64decode(compressed)
        return _fmt_result(zlib.decompress(raw).decode("utf-8"))
    except Exception as e:
        return _fmt_error(f"Decompression failed: {e}")


# =============================================================================
# Obfuscation
# =============================================================================

def obfuscate_email(email: str) -> Dict[str, Any]:
    try:
        if "@" not in email:
            return _fmt_error("Invalid email format: missing '@'")
        
        local, domain = email.rsplit("@", 1)
        domain_parts = domain.split(".")
        tld = domain_parts[-1]
        d_name = ".".join(domain_parts[:-1]) if len(domain_parts) > 1 else ""

        def _mask(s: str) -> str:
            if not s:
                return ""
            if len(s) <= 2:
                return s[0] + ("*" if len(s) > 1 else "")
            return s[0] + s[1] + "*" * (len(s) - 3) + s[-1]
        
        l_masked = _mask(local)
        d_masked = _mask(d_name)
        result = f"{l_masked}@{d_masked}.{tld}" if d_masked else f"{l_masked}@{tld}"
        return _fmt_result(result)
    except Exception as e:
        return _fmt_error(e)