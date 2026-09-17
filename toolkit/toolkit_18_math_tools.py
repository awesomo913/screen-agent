"""
toolkit_18_math_tools.py
Mathematical utilities: statistics, unit conversions, number formatting,
geometry, and combinatorics. Zero external dependencies (stdlib only).
"""
from __future__ import annotations
import math
import statistics
from typing import Any, Dict, List

def describe_stats(numbers: list) -> Dict[str, Any]:
    """Compute descriptive statistics for a list of numbers."""
    try:
        if not numbers:
            return {"success": False, "data": None, "error": "Empty list"}
        n = list(map(float, numbers))
        result = {
            "count": len(n),
            "sum": sum(n),
            "mean": statistics.mean(n),
            "median": statistics.median(n),
            "mode": statistics.mode(n) if len(set(n)) < len(n) else None,
            "variance": statistics.variance(n) if len(n) > 1 else 0,
            "stdev": statistics.stdev(n) if len(n) > 1 else 0,
            "min": min(n),
            "max": max(n),
            "range": max(n) - min(n),
        }
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def percentile(numbers: list, p: float) -> Dict[str, Any]:
    """Compute the p-th percentile (0-100)."""
    try:
        n = sorted(map(float, numbers))
        if not n:
            return {"success": False, "data": None, "error": "Empty list"}
        k = (len(n) - 1) * p / 100
        lo, hi = int(k), math.ceil(k)
        frac = k - lo
        val = n[lo] * (1 - frac) + n[hi] * frac if lo != hi else n[lo]
        return {"success": True, "data": val, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def normalize(numbers: list) -> Dict[str, Any]:
    """Min-max normalize a list to [0, 1]."""
    try:
        n = list(map(float, numbers))
        lo, hi = min(n), max(n)
        if lo == hi:
            return {"success": True, "data": [0.0] * len(n), "error": None}
        result = [(x - lo) / (hi - lo) for x in n]
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clamp(value: float, minimum: float, maximum: float) -> Dict[str, Any]:
    try:
        return {"success": True, "data": max(minimum, min(maximum, value)), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def round_to(value: float, decimals: int = 2) -> Dict[str, Any]:
    try:
        return {"success": True, "data": round(value, decimals), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def is_prime(n: int) -> Dict[str, Any]:
    try:
        if n < 2:
            return {"success": True, "data": False, "error": None}
        if n < 4:
            return {"success": True, "data": True, "error": None}
        if n % 2 == 0 or n % 3 == 0:
            return {"success": True, "data": False, "error": None}
        i = 5
        while i * i <= n:
            if n % i == 0 or n % (i + 2) == 0:
                return {"success": True, "data": False, "error": None}
            i += 6
        return {"success": True, "data": True, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def primes_up_to(limit: int) -> Dict[str, Any]:
    """Sieve of Eratosthenes."""
    try:
        sieve = [True] * (limit + 1)
        sieve[0] = sieve[1] = False
        for i in range(2, int(limit**0.5) + 1):
            if sieve[i]:
                for j in range(i*i, limit + 1, i):
                    sieve[j] = False
        primes = [i for i, v in enumerate(sieve) if v]
        return {"success": True, "data": primes, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def factorial(n: int) -> Dict[str, Any]:
    try:
        return {"success": True, "data": math.factorial(n), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def fibonacci(n: int) -> Dict[str, Any]:
    """Return first n Fibonacci numbers."""
    try:
        if n <= 0:
            return {"success": True, "data": [], "error": None}
        seq = [0, 1]
        while len(seq) < n:
            seq.append(seq[-1] + seq[-2])
        return {"success": True, "data": seq[:n], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def gcd(a: int, b: int) -> Dict[str, Any]:
    try:
        return {"success": True, "data": math.gcd(a, b), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def lcm(a: int, b: int) -> Dict[str, Any]:
    try:
        return {"success": True, "data": math.lcm(a, b), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def convert_temperature(value: float, from_unit: str, to_unit: str) -> Dict[str, Any]:
    """Convert between C, F, K."""
    try:
        f = from_unit.upper()[0]
        t = to_unit.upper()[0]
        if f == "C": celsius = value
        elif f == "F": celsius = (value - 32) * 5 / 9
        elif f == "K": celsius = value - 273.15
        else: return {"success": False, "data": None, "error": "Unknown unit: " + from_unit}
        if t == "C": result = celsius
        elif t == "F": result = celsius * 9 / 5 + 32
        elif t == "K": result = celsius + 273.15
        else: return {"success": False, "data": None, "error": "Unknown unit: " + to_unit}
        return {"success": True, "data": round(result, 4), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def convert_length(value: float, from_unit: str, to_unit: str) -> Dict[str, Any]:
    """Convert length. Units: m, km, cm, mm, inch, ft, yd, mile."""
    try:
        to_meters = {"m": 1, "km": 1000, "cm": 0.01, "mm": 0.001,
                     "inch": 0.0254, "ft": 0.3048, "yd": 0.9144, "mile": 1609.344}
        fu = from_unit.lower().rstrip("s")
        tu = to_unit.lower().rstrip("s")
        if fu not in to_meters: return {"success": False, "data": None, "error": "Unknown unit: " + from_unit}
        if tu not in to_meters: return {"success": False, "data": None, "error": "Unknown unit: " + to_unit}
        meters = value * to_meters[fu]
        result = meters / to_meters[tu]
        return {"success": True, "data": round(result, 6), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def convert_weight(value: float, from_unit: str, to_unit: str) -> Dict[str, Any]:
    """Convert weight. Units: kg, g, mg, lb, oz, ton."""
    try:
        to_kg = {"kg": 1, "g": 0.001, "mg": 0.000001, "lb": 0.453592, "oz": 0.0283495, "ton": 1000, "tonne": 1000}
        fu = from_unit.lower(); tu = to_unit.lower()
        if fu not in to_kg: return {"success": False, "data": None, "error": "Unknown unit: " + from_unit}
        if tu not in to_kg: return {"success": False, "data": None, "error": "Unknown unit: " + to_unit}
        kg = value * to_kg[fu]
        result = kg / to_kg[tu]
        return {"success": True, "data": round(result, 6), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def convert_data_size(value: float, from_unit: str, to_unit: str) -> Dict[str, Any]:
    """Convert data sizes. Units: B, KB, MB, GB, TB, KiB, MiB, GiB, TiB."""
    try:
        to_bytes = {"B": 1, "KB": 1000, "MB": 1e6, "GB": 1e9, "TB": 1e12,
                    "KIB": 1024, "MIB": 1048576, "GIB": 1073741824, "TIB": 1099511627776}
        fu = from_unit.upper(); tu = to_unit.upper()
        if fu not in to_bytes: return {"success": False, "data": None, "error": "Unknown unit: " + from_unit}
        if tu not in to_bytes: return {"success": False, "data": None, "error": "Unknown unit: " + to_unit}
        bytes_val = value * to_bytes[fu]
        result = bytes_val / to_bytes[tu]
        return {"success": True, "data": round(result, 4), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def format_bytes(n_bytes: int) -> Dict[str, Any]:
    """Human-readable byte size string."""
    try:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if n_bytes < 1024:
                return {"success": True, "data": str(round(n_bytes, 2)) + " " + unit, "error": None}
            n_bytes /= 1024
        return {"success": True, "data": str(round(n_bytes, 2)) + " PB", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def combinations(n: int, r: int) -> Dict[str, Any]:
    try:
        return {"success": True, "data": math.comb(n, r), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def permutations_count(n: int, r: int) -> Dict[str, Any]:
    try:
        return {"success": True, "data": math.perm(n, r), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def circle_area(radius: float) -> Dict[str, Any]:
    try:
        return {"success": True, "data": round(math.pi * radius ** 2, 6), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def distance_2d(x1: float, y1: float, x2: float, y2: float) -> Dict[str, Any]:
    try:
        d = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        return {"success": True, "data": round(d, 6), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def logarithm(value: float, base: float = 2.718281828) -> Dict[str, Any]:
    try:
        result = math.log(value, base)
        return {"success": True, "data": round(result, 8), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def base_convert(value: str, from_base: int, to_base: int) -> Dict[str, Any]:
    """Convert integer string between bases (2-36)."""
    try:
        decimal = int(value, from_base)
        if to_base == 10:
            return {"success": True, "data": str(decimal), "error": None}
        digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        result = ""
        n = decimal
        while n:
            result = digits[n % to_base] + result
            n //= to_base
        return {"success": True, "data": result or "0", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def moving_average(numbers: list, window: int = 3) -> Dict[str, Any]:
    try:
        n = list(map(float, numbers))
        result = []
        for i in range(len(n)):
            start = max(0, i - window + 1)
            result.append(sum(n[start:i+1]) / (i - start + 1))
        return {"success": True, "data": [round(v, 4) for v in result], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}