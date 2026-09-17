"""
display_gamma.py - GDI gamma ramp brightness control.

Universal software-level brightness that works on ALL displays (laptops,
external monitors, HDMI) by manipulating the GPU's color lookup tables via
gdi32.dll GetDeviceGammaRamp / SetDeviceGammaRamp.

Zero third-party dependencies.
"""

import ctypes
import ctypes.wintypes
from typing import Any, Dict, Tuple

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data: Any = None, message: str = "OK") -> Dict[str, Any]:
    return {"success": True, "data": data, "error": None, "message": message}


def _err(error: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "error": error, "message": error}


# GDI gamma ramp: 3 channels x 256 WORDs
_GAMMA_RAMP = (ctypes.wintypes.WORD * 256) * 3


def _get_dc():
    """Get the device context for the entire screen."""
    return ctypes.windll.user32.GetDC(0)


def _release_dc(hdc):
    ctypes.windll.user32.ReleaseDC(0, hdc)


# ---------------------------------------------------------------------------
# Core Gamma Functions
# ---------------------------------------------------------------------------

def get_gamma_ramp() -> Dict[str, Any]:
    """Read the current gamma ramp values (R, G, B arrays of 256 values)."""
    try:
        hdc = _get_dc()
        ramp = _GAMMA_RAMP()
        ok = ctypes.windll.gdi32.GetDeviceGammaRamp(hdc, ctypes.byref(ramp))
        _release_dc(hdc)
        if not ok:
            return _err("GetDeviceGammaRamp failed (unsupported driver)")
        # Return first/mid/last values as summary
        r0, r128, r255 = ramp[0][0], ramp[0][128], ramp[0][255]
        g0, g128, g255 = ramp[1][0], ramp[1][128], ramp[1][255]
        b0, b128, b255 = ramp[2][0], ramp[2][128], ramp[2][255]
        # Estimate brightness from midpoint relative to linear
        linear_mid = 32768  # 128 * 256
        estimated = round(r128 / linear_mid * 100) if linear_mid else 100
        return _ok({
            "estimated_brightness": min(estimated, 100),
            "red": {"start": r0, "mid": r128, "end": r255},
            "green": {"start": g0, "mid": g128, "end": g255},
            "blue": {"start": b0, "mid": b128, "end": b255},
        }, f"Gamma ramp read (est. brightness: {min(estimated, 100)}%)")
    except Exception as e:
        return _err(str(e))


def set_gamma_brightness(level: int) -> Dict[str, Any]:
    """Set software brightness (0-100%). Applies to all connected displays."""
    try:
        if not 0 <= level <= 100:
            return _err("Level must be 0-100")
        factor = level / 100.0
        hdc = _get_dc()
        ramp = _GAMMA_RAMP()
        for i in range(256):
            val = min(65535, int(i * 256 * factor))
            ramp[0][i] = val  # Red
            ramp[1][i] = val  # Green
            ramp[2][i] = val  # Blue
        ok = ctypes.windll.gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp))
        _release_dc(hdc)
        if not ok:
            return _err("SetDeviceGammaRamp failed (driver rejected)")
        return _ok({"brightness": level}, f"Brightness set to {level}%")
    except Exception as e:
        return _err(str(e))


def set_color_temperature(temperature: int) -> Dict[str, Any]:
    """Adjust display color temperature (warm/cool). 1000-10000 Kelvin."""
    try:
        if not 1000 <= temperature <= 10000:
            return _err("Temperature must be 1000-10000 K")
        r, g, b = _kelvin_to_rgb(temperature)
        hdc = _get_dc()
        ramp = _GAMMA_RAMP()
        for i in range(256):
            base = i * 256
            ramp[0][i] = min(65535, int(base * r))
            ramp[1][i] = min(65535, int(base * g))
            ramp[2][i] = min(65535, int(base * b))
        ok = ctypes.windll.gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp))
        _release_dc(hdc)
        if not ok:
            return _err("SetDeviceGammaRamp failed")
        return _ok({"temperature_k": temperature, "rgb_factors": (r, g, b)},
                    f"Color temperature set to {temperature}K")
    except Exception as e:
        return _err(str(e))


def reset_gamma() -> Dict[str, Any]:
    """Reset gamma ramp to default linear values (100% brightness, neutral)."""
    try:
        hdc = _get_dc()
        ramp = _GAMMA_RAMP()
        for i in range(256):
            val = i * 256
            ramp[0][i] = val
            ramp[1][i] = val
            ramp[2][i] = val
        ok = ctypes.windll.gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp))
        _release_dc(hdc)
        if not ok:
            return _err("SetDeviceGammaRamp failed")
        return _ok(None, "Gamma ramp reset to default (linear)")
    except Exception as e:
        return _err(str(e))


def apply_custom_gamma(red: float, green: float, blue: float) -> Dict[str, Any]:
    """Apply per-channel gamma multipliers (0.0-1.0 each)."""
    try:
        for name, val in [("red", red), ("green", green), ("blue", blue)]:
            if not 0.0 <= val <= 1.0:
                return _err(f"{name} must be 0.0-1.0")
        hdc = _get_dc()
        ramp = _GAMMA_RAMP()
        for i in range(256):
            base = i * 256
            ramp[0][i] = min(65535, int(base * red))
            ramp[1][i] = min(65535, int(base * green))
            ramp[2][i] = min(65535, int(base * blue))
        ok = ctypes.windll.gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(ramp))
        _release_dc(hdc)
        if not ok:
            return _err("SetDeviceGammaRamp failed")
        return _ok({"red": red, "green": green, "blue": blue},
                    f"Custom gamma applied (R={red}, G={green}, B={blue})")
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Color temperature helpers
# ---------------------------------------------------------------------------

def _kelvin_to_rgb(kelvin: int) -> Tuple[float, float, float]:
    """Approximate Kelvin color temperature to RGB multipliers (0-1)."""
    temp = kelvin / 100.0
    # Red
    if temp <= 66:
        r = 1.0
    else:
        r = max(0.0, min(1.0, 1.292936 * ((temp - 60) ** -0.1332047592)))
    # Green
    if temp <= 66:
        g = max(0.0, min(1.0, 0.390082 * (temp - 2) ** 0.0755148492 - 0.631841 + 0.8))
    else:
        g = max(0.0, min(1.0, 1.129891 * ((temp - 60) ** -0.0755148492)))
    # Blue
    if temp >= 66:
        b = 1.0
    elif temp <= 19:
        b = 0.0
    else:
        b = max(0.0, min(1.0, 0.543207 * (temp - 10) ** 0.0755148492 - 0.397 + 0.3))
    return (r, g, b)
