# encryption_actions.py
"""
A comprehensive toolbox for cryptographic, encoding, and utility operations
used by the Screen Agent Toolkit.

All functions return a dictionary with the following schema:

{
    "success": bool,            # True if the operation succeeded
    "result": Any | None,       # The value produced by the call (if any)
    "error": str | None         # Human‑readable error message (if any)
}
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import struct
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# --------------------------------------------------------------------------- #
# Helper utilities
# --------------------------------------------------------------------------- #
def _wrap(success: bool, result: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
    """Standardised return wrapper."""
    return {"success": success, "result": result, "error": error}


# --------------------------------------------------------------------------- #
# Hashing utilities
# --------------------------------------------------------------------------- #
def hash_text(text: str, algorithm: str = "sha256") -> Dict[str, Any]:
    """
    Hash a UTF‑8 string using the requested algorithm.

    Supported: md5, sha1, sha224, sha256, sha384, sha512.
    """
    try:
        h = hashlib.new(algorithm)
        h.update(text.encode("utf-8"))
        return _wrap(True, h.hexdigest())
    except ValueError as exc:
        return _wrap(False, error=f"Unsupported algorithm '{algorithm}': {exc}")


def hash_file(file_path: Union[str, os.PathLike], algorithm: str = "sha256") -> Dict[str, Any]:
    """
    Compute the hash of a file in a memory‑efficient streaming fashion.
    """
    try:
        h = hashlib.new(algorithm)
    except ValueError as exc:
        return _wrap(False, error=f"Unsupported algorithm '{algorithm}': {exc}")

    path = Path(file_path)
    if not path.is_file():
        return _wrap(False, error=f"File not found: {path}")

    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return _wrap(True, h.hexdigest())
    except OSError as exc:
        return _wrap(False, error=str(exc))


def verify_hash(text: str, expected_hash: str, algorithm: str = "sha256") -> Dict[str, Any]:
    """
    Verify that the hash of *text* matches *expected_hash*.
    """
    got = hash_text(text, algorithm)
    if not got["success"]:
        return got
    match = hmac.compare_digest(got["result"], expected_hash.lower())
    return _wrap(True, match)


# --------------------------------------------------------------------------- #
# HMAC utilities
# --------------------------------------------------------------------------- #
def hmac_sign(message: Union[str, bytes], key: Union[str, bytes], algorithm: str = "sha256") -> Dict[str, Any]:
    """
    Produce an HMAC signature (Base64 encoded) of *message* using *key*.
    """
    try:
        if isinstance(message, str):
            message = message.encode("utf-8")
        if isinstance(key, str):
            key = key.encode("utf-8")
        mac = hmac.new(key, message, getattr(hashlib, algorithm))
        signature = base64.b64encode(mac.digest()).decode("ascii")
        return _wrap(True, signature)
    except (AttributeError, ValueError) as exc:
        return _wrap(False, error=f"Invalid algorithm '{algorithm}': {exc}")


def hmac_verify(message: Union[str, bytes], signature: str, key: Union[str, bytes], algorithm: str = "sha256") -> Dict[str, Any]:
    """
    Verify an HMAC signature (expects Base64 encoded *signature*).
    """
    signed = hmac_sign(message, key, algorithm)
    if not signed["success"]:
        return signed
    try:
        expected = base64.b64decode(signature)
    except binascii.Error as exc:
        return _wrap(False, error=f"Invalid Base64 signature: {exc}")

    valid = hmac.compare_digest(base64.b64decode(signed["result"]), expected)
    return _wrap(True, valid)


# --------------------------------------------------------------------------- #
# Base64 / URL‑safe / Hex utilities
# --------------------------------------------------------------------------- #
def base64_encode(data: Union[str, bytes]) -> Dict[str, Any]:
    """Encode data as a Base64 string."""
    try:
        if isinstance(data, str):
            data = data.encode("utf-8")
        encoded = base64.b64encode(data).decode("ascii")
        return _wrap(True, encoded)
    except Exception as exc:
        return _wrap(False, error=str(exc))


def base64_decode(encoded: str) -> Dict[str, Any]:
    """Decode a Base64 string to raw bytes."""
    try:
        decoded = base64.b64decode(encoded)
        return _wrap(True, decoded)
    except binascii.Error as exc:
        return _wrap(False, error=f"Base64 decoding error: {exc}")


def url_safe_encode(data: Union[str, bytes]) -> Dict[str, Any]:
    """URL‑safe Base64 encoding (no padding)."""
    try:
        if isinstance(data, str):
            data = data.encode("utf-8")
        encoded = base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")
        return _wrap(True, encoded)
    except Exception as exc:
        return _wrap(False, error=str(exc))


def url_safe_decode(encoded: str) -> Dict[str, Any]:
    """Decode a URL‑safe Base64 string (adds padding as needed)."""
    try:
        padding = "=" * (-len(encoded) % 4)
        decoded = base64.urlsafe_b64decode(encoded + padding)
        return _wrap(True, decoded)
    except binascii.Error as exc:
        return _wrap(False, error=f"URL‑safe Base64 decoding error: {exc}")


def hex_encode(data: Union[str, bytes]) -> Dict[str, Any]:
    """Hexadecimal representation of data."""
    try:
        if isinstance(data, str):
            data = data.encode("utf-8")
        encoded = binascii.hexlify(data).decode("ascii")
        return _wrap(True, encoded)
    except Exception as exc:
        return _wrap(False, error=str(exc))


def hex_decode(hex_str: str) -> Dict[str, Any]:
    """Decode a hex string back to bytes."""
    try:
        decoded = binascii.unhexlify(hex_str)
        return _wrap(True, decoded)
    except (binascii.Error, ValueError) as exc:
        return _wrap(False, error=f"Hex decoding error: {exc}")


# --------------------------------------------------------------------------- #
# Random generation helpers
# --------------------------------------------------------------------------- #
def generate_random_bytes(length: int) -> Dict[str, Any]:
    """Generate *length* cryptographically‑secure random bytes."""
    if length < 0:
        return _wrap(False, error="Length must be non‑negative")
    try:
        data = secrets.token_bytes(length)
        return _wrap(True, data)
    except Exception as exc:
        return _wrap(False, error=str(exc))


def generate_random_string(length: int, charset: str = "ascii_letters+digits") -> Dict[str, Any]:
    """
    Generate a random string of *length* from *charset*.

    ``charset`` can be:
        - "ascii_letters"
        - "digits"
        - "hex"
        - custom string of characters
        - combination separated by '+' (e.g. "ascii_letters+digits")
    """
    import string

    if length < 0:
        return _wrap(False, error="Length must be non‑negative")

    sets: Dict[str, str] = {
        "ascii_letters": string.ascii_letters,
        "digits": string.digits,
        "hex": string.hexdigits.lower(),
    }

    try:
        parts = charset.split("+")
        pool = "".join(sets.get(p, p) for p in parts)
        if not pool:
            return _wrap(False, error="Character set resolved to empty")
        result = "".join(secrets.choice(pool) for _ in range(length))
        return _wrap(True, result)
    except Exception as exc:
        return _wrap(False, error=str(exc))


def generate_password(
    length: int = 12,
    uppercase: bool = True,
    lowercase: bool = True,
    digits: bool = True,
    special: bool = True,
) -> Dict[str, Any]:
    """Generate a password that respects the requested character classes."""
    import string

    if length <= 0:
        return _wrap(False, error="Length must be > 0")

    categories: List[str] = []
    if uppercase:
        categories.append(string.ascii_uppercase)
    if lowercase:
        categories.append(string.ascii_lowercase)
    if digits:
        categories.append(string.digits)
    if special:
        categories.append(string.punctuation)

    if not categories:
        return _wrap(False, error="At least one character class must be enabled")

    # Ensure at least one char from each chosen category
    password_chars = [secrets.choice(cat) for cat in categories]

    all_allowed = "".join(categories)
    while len(password_chars) < length:
        password_chars.append(secrets.choice(all_allowed))

    # Shuffle to avoid predictable placement
    secrets.SystemRandom().shuffle(password_chars)
    password = "".join(password_chars)
    return _wrap(True, password)


def generate_uuid() -> Dict[str, Any]:
    """Return a stringified UUID4."""
    return _wrap(True, str(uuid.uuid4()))


def generate_token(length: int = 32) -> Dict[str, Any]:
    """Generate a URL‑safe token."""
    if length <= 0:
        return _wrap(False, error="Length must be positive")
    token = secrets.token_urlsafe(length)
    return _wrap(True, token)


def generate_api_key(prefix: str = "sk_") -> Dict[str, Any]:
    """Create an API key consisting of a prefix and a random token."""
    token_res = generate_token(32)
    if not token_res["success"]:
        return token_res
    return _wrap(True, f"{prefix}{token_res['result']}")


# --------------------------------------------------------------------------- #
# XOR / simple symmetric operations
# --------------------------------------------------------------------------- #
def xor_encrypt(data: Union[str, bytes], key: Union[str, bytes]) -> Dict[str, Any]:
    """XOR encrypt *data* with *key*. Returns raw bytes."""
    try:
        if isinstance(data, str):
            data = data.encode("utf-8")
        if isinstance(key, str):
            key = key.encode("utf-8")
        encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return _wrap(True, encrypted)
    except Exception as exc:
        return _wrap(False, error=str(exc))


def xor_decrypt(encrypted: Union[str, bytes], key: Union[str, bytes]) -> Dict[str, Any]:
    """XOR decryption – operation is symmetric."""
    return xor_encrypt(encrypted, key)  # identical algorithm


# --------------------------------------------------------------------------- #
# Classical ciphers
# --------------------------------------------------------------------------- #
def _caesar_shift_char(ch: str, shift: int) -> str:
    if "a" <= ch <= "z":
        return chr((ord(ch) - 97 + shift) % 26 + 97)
    if "A" <= ch <= "Z":
        return chr((ord(ch) - 65 + shift) % 26 + 65)
    return ch


def caesar_cipher(text: str, shift: int) -> Dict[str, Any]:
    """Encode *text* using a Caesar shift."""
    try:
        shifted = "".join(_caesar_shift_char(ch, shift) for ch in text)
        return _wrap(True, shifted)
    except Exception as exc:
        return _wrap(False, error=str(exc))


def caesar_decipher(text: str, shift: int) -> Dict[str, Any]:
    """Decode a Caesar‑shifted *text* (negative shift)."""
    return caesar_cipher(text, -shift)


def vigenere_encrypt(text: str, key: str) -> Dict[str, Any]:
    """Encrypt *text* with a Vigenère cipher using *key*."""
    try:
        if not key:
            return _wrap(False, error="Key must be non‑empty")
        result = []
        ki = 0
        for ch in text:
            k = ord(key[ki % len(key)].lower()) - 97
            result.append(_caesar_shift_char(ch, k))
            if ch.isalpha():
                ki += 1
        return _wrap(True, "".join(result))
    except Exception as exc:
        return _wrap(False, error=str(exc))


def vigenere_decrypt(text: str, key: str) -> Dict[str, Any]:
    """Decrypt *text* that was encrypted with the Vigenère cipher."""
    try:
        if not key:
            return _wrap(False, error="Key must be non‑empty")
        result = []
        ki = 0
        for ch in text:
            k = -(ord(key[ki % len(key)].lower()) - 97)
            result.append(_caesar_shift_char(ch, k))
            if ch.isalpha():
                ki += 1
        return _wrap(True, "".join(result))
    except Exception as exc:
        return _wrap(False, error=str(exc))


def rot13(text: str) -> Dict[str, Any]:
    """Apply ROT13 transformation."""
    try:
        trans = str.maketrans(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
            "NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm",
        )
        return _wrap(True, text.translate(trans))
    except Exception as exc:
        return _wrap(False, error=str(exc))


# --------------------------------------------------------------------------- #
# Checksums & CRC
# --------------------------------------------------------------------------- #
def checksum_file(file_path: Union[str, os.PathLike]) -> Dict[str, Any]:
    """
    Convenience wrapper returning SHA‑256 checksum of a file.
    """
    return hash_file(file_path, "sha256")


def crc32(data: Union[str, bytes]) -> Dict[str, Any]:
    """Calculate CRC‑32 (as unsigned 32‑bit integer)."""
    try:
        if isinstance(data, str):
            data = data.encode("utf-8")
        checksum = binascii.crc32(data) & 0xFFFFFFFF
        return _wrap(True, f"{checksum:08x}")
    except Exception as exc:
        return _wrap(False, error=str(exc))


# --------------------------------------------------------------------------- #
# Direct hash shortcuts
# --------------------------------------------------------------------------- #
def md5_hash(text: str) -> Dict[str, Any]:
    return hash_text(text, "md5")


def sha256_hash(text: str) -> Dict[str, Any]:
    return hash_text(text, "sha256")


def sha512_hash(text: str) -> Dict[str, Any]:
    return hash_text(text, "sha512")


# --------------------------------------------------------------------------- #
# PBKDF2 helpers
# --------------------------------------------------------------------------- #
def generate_salt(length: int = 16) -> Dict[str, Any]:
    """Generate a random salt (hex encoded)."""
    if length <= 0:
        return _wrap(False, error="Length must be positive")
    salt_bytes = secrets.token_bytes(length)
    salt_hex = binascii.hexlify(salt_bytes).decode("ascii")
    return _wrap(True, salt_hex)


def pbkdf2_hash(password: str, salt: Union[str, bytes], iterations: int = 100_000) -> Dict[str, Any]:
    """
    Derive a key using PBKDF2‑HMAC‑SHA256. Returns hex‑encoded derived key.
    """
    try:
        if isinstance(salt, str):
            salt = binascii.unhexlify(salt)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return _wrap(True, binascii.hexlify(dk).decode("ascii"))
    except (binascii.Error, ValueError) as exc:
        return _wrap(False, error=f"Invalid salt: {exc}")
    except Exception as exc:
        return _wrap(False, error=str(exc))


def verify_pbkdf2(password: str, hashed: str, salt: Union[str, bytes], iterations: int = 100_000) -> Dict[str, Any]:
    """Validate a password against a previously derived PBKDF2 hash."""
    derived = pbkdf2_hash(password, salt, iterations)
    if not derived["success"]:
        return derived
    is_match = hmac.compare_digest(derived["result"], hashed.lower())
    return _wrap(True, is_match)


# --------------------------------------------------------------------------- #
# Simple JWT (no expiration, compact)
# --------------------------------------------------------------------------- #
def encode_jwt_simple(payload: Dict[str, Any], secret: str) -> Dict[str, Any]:
    """
    Encode a JWT using HS256. Header is fixed; no claim validation performed.
    """
    try:
        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = url_safe_encode(json.dumps(header, separators=(",", ":"))).get("result")
        payload_b64 = url_safe_encode(json.dumps(payload, separators=(",", ":"))).get("result")
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
        token = f"{header_b64}.{payload_b64}.{signature_b64}"
        return _wrap(True, token)
    except Exception as exc:
        return _wrap(False, error=str(exc))


def decode_jwt_simple(token: str, secret: str) -> Dict[str, Any]:
    """
    Decode a JWT generated by ``encode_jwt_simple`` and verify its signature.
    Returns the payload dict.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return _wrap(False, error="Invalid token structure")
        header_b64, payload_b64, signature_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_sig = base64.urlsafe_b64encode(
            hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        ).decode("ascii").rstrip("=")

        if not hmac.compare_digest(expected_sig, signature_b64):
            return _wrap(False, error="Signature verification failed")

        payload_bytes = base64.urlsafe_b64decode(payload_b64 + "===")
        payload = json.loads(payload_bytes.decode("utf-8"))
        return _wrap(True, payload)
    except (binascii.Error, json.JSONDecodeError) as exc:
        return _wrap(False, error=f"Decoding error: {exc}")
    except Exception as exc:
        return _wrap(False, error=str(exc))


# --------------------------------------------------------------------------- #
# File XOR encryption / decryption
# --------------------------------------------------------------------------- #
def encrypt_file_xor(file_path: Union[str, os.PathLike], key: Union[str, bytes], output_path: Union[str, os.PathLike]) -> Dict[str, Any]:
    """Encrypt a file with a simple XOR cipher and write to *output_path*."""
    try:
        if isinstance(key, str):
            key = key.encode("utf-8")
        inp = Path(file_path)
        out = Path(output_path)
        if not inp.is_file():
            return _wrap(False, error=f"Input file not found: {inp}")
        with inp.open("rb") as fin, out.open("wb") as fout:
            i = 0
            while chunk := fin.read(8192):
                encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(chunk, start=i))
                i += len(chunk)
                fout.write(encrypted)
        return _wrap(True, str(out))
    except OSError as exc:
        return _wrap(False, error=str(exc))


def decrypt_file_xor(file_path: Union[str, os.PathLike], key: Union[str, bytes], output_path: Union[str, os.PathLike]) -> Dict[str, Any]:
    """Decrypt a XOR‑encrypted file (operation is symmetric)."""
    return encrypt_file_xor(file_path, key, output_path)


# --------------------------------------------------------------------------- #
# Secure compare & misc helpers
# --------------------------------------------------------------------------- #
def secure_compare(a: Union[str, bytes], b: Union[str, bytes]) -> Dict[str, Any]:
    """Constant‑time comparison."""
    try:
        if isinstance(a, str):
            a = a.encode("utf-8")
        if isinstance(b, str):
            b = b.encode("utf-8")
        result = hmac.compare_digest(a, b)
        return _wrap(True, result)
    except Exception as exc:
        return _wrap(False, error=str(exc))


def mask_string(text: str, visible_chars: int = 4, mask_char: str = "*") -> Dict[str, Any]:
    """
    Mask all but the last *visible_chars* characters of *text*.
    """
    if visible_chars < 0:
        return _wrap(False, error="visible_chars must be non‑negative")
    if len(text) <= visible_chars:
        return _wrap(True, text)
    masked = mask_char * (len(text) - visible_chars) + text[-visible_chars:]
    return _wrap(True, masked)


def obfuscate_email(email: str) -> Dict[str, Any]:
    """
    Simple email obfuscation: keep first character of the local part,
    replace the rest with asterisks, keep domain unchanged.
    """
    try:
        local, domain = email.split("@", 1)
        if len(local) == 0:
            return _wrap(False, error="Invalid email address")
        obf_local = local[0] + "*" * (len(local) - 1)
        return _wrap(True, f"{obf_local}@{domain}")
    except ValueError:
        return _wrap(False, error="Invalid email format")


def generate_otp(length: int = 6) -> Dict[str, Any]:
    """One‑Time Password consisting of digits."""
    if length <= 0:
        return _wrap(False, error="Length must be positive")
    otp = "".join(secrets.choice("0123456789") for _ in range(length))
    return _wrap(True, otp)


def verify_otp(otp: str, expected: str) -> Dict[str, Any]:
    """Constant‑time OTP verification."""
    return secure_compare(otp, expected)


def entropy_score(text: str) -> Dict[str, Any]:
    """
    Compute Shannon entropy (bits per character) of the supplied *text*.
    """
    try:
        if not text:
            return _wrap(True, 0.0)
        frequency: Dict[str, int] = {}
        for ch in text:
            frequency[ch] = frequency.get(ch, 0) + 1
        entropy = -sum((count / len(text)) * (count / len(text)).bit_length() for count in frequency.values())
        # The above naive implementation is replaced by the proper formula:
        import math

        entropy = -sum((count / len(text)) * math.log2(count / len(text)) for count in frequency.values())
        return _wrap(True, entropy)
    except Exception as exc:
        return _wrap(False, error=str(exc))


def is_strong_password(password: str) -> Dict[str, Any]:
    """
    Basic strength estimator: length ≥ 12 and includes at least three of the
    four character classes (upper, lower, digit, special).
    """
    import string

    try:
        length_ok = len(password) >= 12
        classes = sum(
            [
                any(c in string.ascii_uppercase for c in password),
                any(c in string.ascii_lowercase for c in password),
                any(c in string.digits for c in password),
                any(c in string.punctuation for c in password),
            ]
        )
        strong = length_ok and classes >= 3
        return _wrap(True, strong)
    except Exception as exc:
        return _wrap(False, error=str(exc))


def sanitize_input(text: str) -> Dict[str, Any]:
    """
    Simple sanitiser – HTML‑escape to prevent XSS in web contexts.
    """
    try:
        import html

        escaped = html.escape(text)
        return _wrap(True, escaped)
    except Exception as exc:
        return _wrap(False, error=str(exc))


# --------------------------------------------------------------------------- #
# End of module
# --------------------------------------------------------------------------- #