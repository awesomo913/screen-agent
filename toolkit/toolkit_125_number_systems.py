"""toolkit_125_number_systems.py
Convert between number systems — binary, octal, hex, decimal, arbitrary base. BCD, IEEE754 float bits.
"""
import os, sys, re, json, subprocess
import struct, math, datetime, hashlib, hmac, base64
from pathlib import Path

def to_binary(n: int) -> dict:
    """Convert integer to binary string."""
    try: return {"success": True, "data": bin(n), "error": None}
    except Exception as e: return {"success": False, "data": None, "error": str(e)}
def to_octal(n: int) -> dict:
    """Convert integer to octal string."""
    try: return {"success": True, "data": oct(n), "error": None}
    except Exception as e: return {"success": False, "data": None, "error": str(e)}
def to_hex(n: int) -> dict:
    """Convert integer to hex string."""
    try: return {"success": True, "data": hex(n), "error": None}
    except Exception as e: return {"success": False, "data": None, "error": str(e)}
def from_binary(s: str) -> dict:
    """Parse binary string to integer."""
    try: return {"success": True, "data": int(s, 2), "error": None}
    except Exception as e: return {"success": False, "data": None, "error": str(e)}
def from_hex(s: str) -> dict:
    """Parse hex string to integer."""
    try: return {"success": True, "data": int(s, 16), "error": None}
    except Exception as e: return {"success": False, "data": None, "error": str(e)}
def from_octal(s: str) -> dict:
    """Parse octal string to integer."""
    try: return {"success": True, "data": int(s, 8), "error": None}
    except Exception as e: return {"success": False, "data": None, "error": str(e)}
def to_base(n: int, base: int) -> dict:
    """Convert integer to arbitrary base (2-36)."""
    try:
        chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if n == 0: return {"success": True, "data": "0", "error": None}
        result = ""
        while n > 0: n, r = divmod(n, base); result = chars[r] + result
        return {"success": True, "data": result, "error": None}
    except Exception as e: return {"success": False, "data": None, "error": str(e)}
def from_base(s: str, base: int) -> dict:
    """Parse integer from arbitrary base."""
    try: return {"success": True, "data": int(s, base), "error": None}
    except Exception as e: return {"success": False, "data": None, "error": str(e)}
def convert_all_bases(n: int) -> dict:
    """Convert integer to binary, octal, decimal, hex at once."""
    try: return {"success": True, "data": {"decimal": n, "binary": bin(n)[2:], "octal": oct(n)[2:], "hex": hex(n)[2:]}, "error": None}
    except Exception as e: return {"success": False, "data": None, "error": str(e)}
def float_to_ieee754(f: float) -> dict:
    """Show IEEE 754 bit representation of a float."""
    try:
        bits = struct.pack(">f", f)
        binary = "".join(format(b, "08b") for b in bits)
        sign = binary[0]; exp = binary[1:9]; mantissa = binary[9:]
        return {"success": True, "data": {"binary": binary, "sign": sign, "exponent": exp, "mantissa": mantissa, "hex": bits.hex()}, "error": None}
    except Exception as e: return {"success": False, "data": None, "error": str(e)}
def int_to_bcd(n: int) -> dict:
    """Convert integer to Binary Coded Decimal."""
    try:
        bcd = " ".join(format(int(d), "04b") for d in str(n))
        return {"success": True, "data": bcd, "error": None}
    except Exception as e: return {"success": False, "data": None, "error": str(e)}
def bitwise_ops(a: int, b: int) -> dict:
    """Perform all bitwise operations on two integers."""
    try: return {"success": True, "data": {"and": a & b, "or": a | b, "xor": a ^ b, "not_a": ~a, "left_shift": a << 1, "right_shift": a >> 1}, "error": None}
    except Exception as e: return {"success": False, "data": None, "error": str(e)}
def count_bits(n: int) -> dict:
    """Count set bits (popcount) in an integer."""
    try: return {"success": True, "data": bin(n).count("1"), "error": None}
    except Exception as e: return {"success": False, "data": None, "error": str(e)}
def is_power_of_two(n: int) -> dict:
    """Check if n is a power of two."""
    try: return {"success": True, "data": n > 0 and (n & (n - 1)) == 0, "error": None}
    except Exception as e: return {"success": False, "data": None, "error": str(e)}
def two_complement(n: int, bits: int = 8) -> dict:
    """Get two's complement representation."""
    try:
        if n >= 0: return {"success": True, "data": format(n, "0" + str(bits) + "b"), "error": None}
        result = (1 << bits) + n
        return {"success": True, "data": format(result, "0" + str(bits) + "b"), "error": None}
    except Exception as e: return {"success": False, "data": None, "error": str(e)}