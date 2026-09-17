import psutil
import ctypes
import subprocess
import platform
import os
import time
import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# ============================================================================
# Module Constants & State
# ============================================================================
_OS = platform.system().lower()
IS_WINDOWS = _OS == "windows"
IS_DARWIN = _OS == "darwin"
IS_LINUX = _OS == "linux"

_STATE_DIR = Path.home() / ".screen_agent_toolkit"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_SLEEP_LOCK_FILE = _STATE_DIR / "sleep_prevention.lock"
_THREAD_STATES: Dict[str, threading.Thread] = {}
_THREAD_LOCK = threading.Lock()

# Windows Constants (ctypes)
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
ES_AWAYMODE_REQUIRED = 0x00000040

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]

# ============================================================================
# Internal Helpers
# ============================================================================
def _result(status: str, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Standardized response dictionary."""
    return {
        "status": status,
        "message": message,
        "data": data or {},
        "timestamp": datetime.now().isoformat()
    }

def _run_cmd(cmd: List[str], timeout: int = 15, capture: bool = True) -> Dict[str, Any]:
    """Execute subprocess command with error handling."""
    try:
        result = subprocess.run(
            cmd, capture_output=capture, text=True, check=True, timeout=timeout
        )
        return {
            "success": True,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out", "returncode": -1}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": e.stderr.strip() or str(e), "returncode": e.returncode}
    except FileNotFoundError:
        return {"success": False, "error": f"Executable not found: {cmd[0]}", "returncode": -2}
    except Exception as e:
        return {"success": False, "error": str(e), "returncode": -3}

def _parse_time_str(time_str: str) -> float:
    """Parse HH:MM format to seconds delay from now."""
    try:
        target = datetime.strptime(time_str, "%H:%M").replace(tzinfo=datetime.now().astimezone().tzinfo)
        now = datetime.now().astimezone()
        delay = (target - now).total_seconds()
        if delay < 0:
            delay += 86400  # Next day
        return max(0, delay)
    except ValueError:
        raise ValueError("Invalid time format. Expected HH:MM")

# ============================================================================
# Core Functions
# ============================================================================

def shutdown_system(delay: int = 0, force: bool = False) -> Dict[str, Any]:
    try:
        if IS_WINDOWS:
            cmd = ["shutdown", "/s", "/t", str(delay)] + (["/f"] if force else [])
        elif IS_LINUX or IS_DARWIN:
            cmd = ["shutdown", "-h", f"+{delay}"] if delay > 0 else ["shutdown", "-h", "now"]
            if force:
                cmd.append("-f")  # Darwin uses -f, Linux may ignore
        res = _run_cmd(cmd)
        return _result("success" if res["success"] else "error",
                       "System shutdown initiated" if res["success"] else res.get("error", "Unknown error"),
                       {"delay": delay, "force": force})
    except Exception as e:
        return _result("error", str(e))

def restart_system(delay: int = 0, force: bool = False) -> Dict[str, Any]:
    try:
        if IS_WINDOWS:
            cmd = ["shutdown", "/r", "/t", str(delay)] + (["/f"] if force else [])
        elif IS_LINUX or IS_DARWIN:
            cmd = ["shutdown", "-r", f"+{delay}"] if delay > 0 else ["shutdown", "-r", "now"]
            if force:
                cmd.append("-f")
        res = _run_cmd(cmd)
        return _result("success" if res["success"] else "error",
                       "System restart initiated" if res["success"] else res.get("error", "Unknown error"),
                       {"delay": delay, "force": force})
    except Exception as e:
        return _result("error", str(e))

def sleep_system() -> Dict[str, Any]:
    try:
        if IS_WINDOWS:
            res = _run_cmd(["powershell", "-Command", "(Add-Type -MemberDefinition '[DllImport(\"powrprof.dll\")] public static extern bool SetSuspendState(bool, bool, bool);' -Name 'Win32' -Namespace 'Win32' -PassThru)::SetSuspendState(0, 0, 0)"])
        elif IS_LINUX:
            res = _run_cmd(["systemctl", "suspend"])
        elif IS_DARWIN:
            res = _run_cmd(["pmset", "sleepnow"])
        else:
            return _result("error", "Unsupported OS for sleep")
        return _result("success" if res["success"] else "error",
                       "Sleep initiated" if res["success"] else res.get("error", "Unknown error"))
    except Exception as e:
        return _result("error", str(e))

def hibernate_system() -> Dict[str, Any]:
    try:
        if IS_WINDOWS:
            res = _run_cmd(["shutdown", "/h", "/f"])
        elif IS_LINUX:
            res = _run_cmd(["systemctl", "hibernate"])
        elif IS_DARWIN:
            # macOS safe sleep
            res = _run_cmd(["sudo", "pmset", "hibernatemode", "25"])
            if res["success"]:
                res = _run_cmd(["pmset", "sleepnow"])
        else:
            return _result("error", "Unsupported OS for hibernate")
        return _result("success" if res["success"] else "error",
                       "Hibernate initiated" if res["success"] else res.get("error", "Unknown error"))
    except Exception as e:
        return _result("error", str(e))

def lock_screen() -> Dict[str, Any]:
    try:
        if IS_WINDOWS:
            res = _run_cmd(["rundll32.exe", "user32.dll,LockWorkStation"])
        elif IS_LINUX:
            res = _run_cmd(["xdg-screensaver", "lock"]) or _run_cmd(["gnome-screensaver-command", "-l"])
        elif IS_DARWIN:
            res = _run_cmd(["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"])
        else:
            return _result("error", "Unsupported OS")
        return _result("success" if res["success"] else "error",
                       "Screen locked" if res["success"] else res.get("error", "Unknown error"))
    except Exception as e:
        return _result("error", str(e))

def log_off_user() -> Dict[str, Any]:
    try:
        if IS_WINDOWS:
            res = _run_cmd(["shutdown", "/l"])
        elif IS_LINUX:
            # Safer session termination
            res = _run_cmd(["loginctl", "terminate-session", os.environ.get("XDG_SESSION_ID", "1")])
        elif IS_DARWIN:
            res = _run_cmd(["osascript", "-e", "tell application \"System Events\" to log out"])
        else:
            return _result("error", "Unsupported OS")
        return _result("success" if res["success"] else "error",
                       "Logoff initiated" if res["success"] else res.get("error", "Unknown error"))
    except Exception as e:
        return _result("error", str(e))

def cancel_shutdown() -> Dict[str, Any]:
    try:
        if IS_WINDOWS:
            res = _run_cmd(["shutdown", "/a"])
        elif IS_LINUX or IS_DARWIN:
            res = _run_cmd(["shutdown", "-c"])
        else:
            return _result("error", "Unsupported OS")
        return _result("success" if res["success"] else "error",
                       "Shutdown cancelled" if res["success"] else res.get("error", "Unknown error"))
    except Exception as e:
        return _result("error", str(e))

def get_battery_status() -> Dict[str, Any]:
    try:
        batt = psutil.sensors_battery()
        if batt is None:
            return _result("error", "Battery information not available")
        return _result("success", "Battery status retrieved", {
            "percent": batt.percent,
            "secsleft": batt.secsleft if batt.secsleft != psutil.POWER_TIME_UNLIMITED else -1,
            "power_plugged": batt.power_plugged,
            "is_charging": batt.power_plugged and batt.secsleft == psutil.POWER_TIME_UNLIMITED
        })
    except Exception as e:
        return _result("error", str(e))

def get_power_plan() -> Dict[str, Any]:
    try:
        if not IS_WINDOWS:
            return _result("warning", "Power plans are Windows-specific", {"os": _OS})
        res = _run_cmd(["powercfg", "/getactivescheme"])
        if not res["success"]:
            return _result("error", res.get("error", "Failed to get power plan"))
        
        # Parse: Power Scheme GUID: xxx (Plan Name) *
        line = res["stdout"].strip()
        parts = line.split(":")
        if len(parts) >= 2:
            guid_part = parts[1].split("(")[0].strip()
            name_part = line.split("(")[-1].replace(")", "").strip()
            return _result("success", "Active plan retrieved", {"guid": guid_part, "name": name_part})
        return _result("error", "Unexpected output format")
    except Exception as e:
        return _result("error", str(e))

def set_power_plan(plan_name: str) -> Dict[str, Any]:
    try:
        if not IS_WINDOWS:
            return _result("warning", "Power plans are Windows-specific", {"os": _OS})
        plans_res = _run_cmd(["powercfg", "/list"])
        if not plans_res["success"]:
            return _result("error", "Failed to list plans")
        
        target_guid = None
        for ln in plans_res["stdout"].splitlines():
            if plan_name.lower() in ln.lower():
                # Extract GUID: typically starts after colon or at specific index
                if ":" in ln:
                    target_guid = ln.split(":")[1].split()[0].strip()
                break
        if not target_guid:
            return _result("error", f"Plan '{plan_name}' not found")
            
        res = _run_cmd(["powercfg", "/setactive", target_guid])
        return _result("success" if res["success"] else "error",
                       f"Set to {plan_name}" if res["success"] else res.get("error", "Failed"),
                       {"guid": target_guid})
    except Exception as e:
        return _result("error", str(e))

def list_power_plans() -> Dict[str, Any]:
    try:
        if not IS_WINDOWS:
            return _result("warning", "Power plans are Windows-specific", {"os": _OS, "plans": []})
        res = _run_cmd(["powercfg", "/list"])
        if not res["success"]:
            return _result("error", res.get("error", "Failed to list plans"))
        plans = []
        for line in res["stdout"].splitlines():
            if "://" in line or "Power Scheme GUID" in line:
                cleaned = line.replace("*", "").strip()
                parts = cleaned.split("(", 1)
                plans.append({
                    "name": parts[1].replace(")", "").strip() if len(parts) > 1 else "Unknown",
                    "desc": parts[0].split(":")[-1].strip()
                })
        return _result("success", "Plans listed", {"plans": plans})
    except Exception as e:
        return _result("error", str(e))

def get_screen_brightness() -> Dict[str, Any]:
    try:
        if IS_WINDOWS:
            # Using WMI via PowerShell for brightness
            res = _run_cmd(["powershell", "-Command", "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness"])
            if res["success"]:
                return _result("success", "Brightness retrieved", {"level": int(res["stdout"].strip())})
        elif IS_LINUX:
            res = _run_cmd(["brightnessctl", "get"], capture=True)
            if res["success"]:
                # Returns raw value, need max for percentage
                res_max = _run_cmd(["brightnessctl", "max"])
                if res_max["success"]:
                    cur = int(res["stdout"].strip())
                    mx = int(res_max["stdout"].strip())
                    return _result("success", "Brightness retrieved", {"level": int((cur / mx) * 100)})
        elif IS_DARWIN:
            res = _run_cmd(["brightness", "-l"])
            if res["success"] and "brightness" in res["stdout"]:
                # Parse "brightness 0.50"
                val = float(res["stdout"].split("brightness")[-1].strip())
                return _result("success", "Brightness retrieved", {"level": int(val * 100)})
        return _result("error", "Unsupported OS or missing brightness utilities")
    except Exception as e:
        return _result("error", str(e))

def set_screen_brightness(level: int) -> Dict[str, Any]:
    try:
        level = max(0, min(100, level))
        if IS_WINDOWS:
            # PowerShell WMI set
            script = f'$b = Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness; $b.SetBrightness($null, {level})'
            res = _run_cmd(["powershell", "-Command", script])
        elif IS_LINUX:
            res = _run_cmd(["brightnessctl", "set", f"{level}%"])
        elif IS_DARWIN:
            f_val = level / 100.0
            res = _run_cmd(["brightness", str(f_val)])
        else:
            return _result("error", "Unsupported OS")
        return _result("success" if res["success"] else "error",
                       f"Brightness set to {level}%" if res["success"] else res.get("error", "Failed"))
    except Exception as e:
        return _result("error", str(e))

def get_idle_time() -> Dict[str, Any]:
    try:
        if IS_WINDOWS:
            last_input = LASTINPUTINFO()
            last_input.cbSize = ctypes.sizeof(last_input)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input))
            tick = ctypes.windll.kernel32.GetTickCount()
            idle_ms = (tick - last_input.dwTime) % (2**32)
            return _result("success", "Idle time retrieved", {"seconds": idle_ms / 1000.0, "milliseconds": idle_ms})
        elif IS_LINUX:
            res = _run_cmd(["xprintidle"])
            if res["success"]:
                return _result("success", "Idle time retrieved", {"milliseconds": int(res["stdout"]), "seconds": int(res["stdout"]) / 1000.0})
            return _result("error", "xprintidle not found")
        elif IS_DARWIN:
            res = _run_cmd(["ioreg", "-c", "IOHIDSystem", "-r", "-d", "1", "-k", "HIDIdleTime"])
            if res["success"]:
                for line in res["stdout"].splitlines():
                    if "HIDIdleTime" in line:
                        ns = int(line.split("=")[-1].strip().replace(",", ""))
                        return _result("success", "Idle time retrieved", {"seconds": ns / 1_000_000_000.0, "nano_seconds": ns})
            return _result("error", "Failed to parse ioreg output")
        return _result("error", "Unsupported OS")
    except Exception as e:
        return _result("error", str(e))

def prevent_sleep(duration: int) -> Dict[str, Any]:
    """Prevent system sleep for duration seconds. Falls back to thread on non-Windows."""
    try:
        if IS_WINDOWS:
            # SetThreadExecutionState
            flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            ctypes.windll.kernel32.SetThreadExecutionState(flags)
        else:
            # Cross-platform thread fallback
            with _THREAD_LOCK:
                active = _THREAD_STATES.get("prevent")
                if active and active.is_alive():
                    active.stop_flag = True  # custom flag
                _THREAD_STATES["prevent"] = None

            stop_event = threading.Event()
            def _keep_awake():
                start = time.time()
                while time.time() - start < duration and not stop_event.is_set():
                    if IS_LINUX:
                        _run_cmd(["xdg-screensaver", "reset"], timeout=5)
                    elif IS_DARWIN:
                        _run_cmd(["caffeinate", "-u", "-t", "60"], timeout=60)
                    time.sleep(55)
            t = threading.Thread(target=_keep_awake, daemon=True)
            t.stop_flag = False
            t.start()
            with _THREAD_LOCK:
                _THREAD_STATES["prevent"] = t
        
        # Record state
        _SLEEP_LOCK_FILE.write_text(json.dumps({"until": time.time() + duration, "active": True}))
        return _result("success", f"Sleep prevented for {duration}s", {"duration": duration, "mode": "native" if IS_WINDOWS else "threaded"})
    except Exception as e:
        return _result("error", str(e))

def allow_sleep() -> Dict[str, Any]:
    try:
        if IS_WINDOWS:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        else:
            with _THREAD_LOCK:
                t = _THREAD_STATES.get("prevent")
                if t and t.is_alive():
                    t.stop_flag = True
                    t.join(timeout=2)
                _SLEEP_LOCK_FILE.write_text(json.dumps({"active": False, "cleared": time.time()}))
                return _result("success", "Sleep allowed", {"thread_stopped": True})
        _SLEEP_LOCK_FILE.write_text(json.dumps({"active": False, "cleared": time.time()}))
        return _result("success", "Sleep allowed", {"mode": "native" if IS_WINDOWS else "threaded"})
    except Exception as e:
        return _result("error", str(e))

def schedule_shutdown(time_str: str) -> Dict[str, Any]:
    try:
        delay = int(_parse_time_str(time_str))
        return shutdown_system(delay)
    except ValueError as ve:
        return _result("error", str(ve))
    except Exception as e:
        return _result("error", str(e))

def schedule_restart(time_str: str) -> Dict[str, Any]:
    try:
        delay = int(_parse_time_str(time_str))
        return restart_system(delay)
    except ValueError as ve:
        return _result("error", str(ve))
    except Exception as e:
        return _result("error", str(e))

def get_uptime() -> Dict[str, Any]:
    try:
        boot_ts = psutil.boot_time()
        up_seconds = time.time() - boot_ts
        return _result("success", "Uptime retrieved", {
            "seconds": up_seconds,
            "human": str(timedelta(seconds=int(up_seconds))),
            "boot_timestamp": boot_ts
        })
    except Exception as e:
        return _result("error", str(e))

def get_last_boot_time() -> Dict[str, Any]:
    try:
        boot_ts = psutil.boot_time()
        return _result("success", "Boot time retrieved", {
            "timestamp": boot_ts,
            "iso": datetime.fromtimestamp(boot_ts).isoformat()
        })
    except Exception as e:
        return _result("error", str(e))

def get_power_events(count: int = 10) -> Dict[str, Any]:
    try:
        if IS_WINDOWS:
            query = f"*[System[Provider[@Name='Microsoft-Windows-Kernel-Power'] or Provider[@Name='Microsoft-Windows-Power-Troubleshooter']]]"
            res = _run_cmd(["wevtutil", "qe", "System", f"/q:{query}", f"/c:{count}", "/f:Json"], timeout=20)
            if res["success"]:
                events = []
                for line in res["stdout"].splitlines():
                    if not line.strip(): continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                return _result("success", f"Retrieved {len(events)} power events", {"events": events, "source": "EventLog"})
            return _result("error", res.get("error", "Failed to query events"))
        elif IS_LINUX:
            res = _run_cmd(["journalctl", "-k", "--no-pager", "--output=short-iso", "-n", str(count), "-g", "power|suspend|hibernate"], timeout=10)
            if res["success"]:
                lines = [l for l in res["stdout"].splitlines() if l.strip()]
                return _result("success", f"Retrieved {len(lines)} journal entries", {"events": lines, "source": "journalctl"})
            return _result("error", "journalctl failed")
        elif IS_DARWIN:
            res = _run_cmd(["log", "show", "--predicate", 'eventMessage contains "power"', "--last", f"{count}m", "--style", "json"], timeout=15)
            if res["success"]:
                try:
                    data = json.loads(res["stdout"])
                    return _result("success", "Retrieved power logs", {"events": data, "source": "log"})
                except json.JSONDecodeError:
                    return _result("success", "Raw logs retrieved", {"raw": res["stdout"]})
        return _result("error", "Unsupported OS for power events")
    except Exception as e:
        return _result("error", str(e))

def set_display_timeout(minutes: int) -> Dict[str, Any]:
    try:
        minutes = max(1, minutes)
        if IS_WINDOWS:
            ac_res = _run_cmd(["powercfg", "/change", "monitor-timeout-ac", str(minutes)])
            dc_res = _run_cmd(["powercfg", "/change", "monitor-timeout-dc", str(minutes)])
            return _result("success" if ac_res["success"] and dc_res["success"] else "error",
                           "Display timeout updated")
        elif IS_LINUX:
            res = _run_cmd(["xset", "dpms", "0", "0", "0"])  # Reset
            if res["success"]:
                res2 = _run_cmd(["xset", "dpms", "0", "0", str(minutes * 60)])
                return _result("success" if res2["success"] else "error",
                               "Display timeout updated (requires X11)")
            return _result("error", "xset failed")
        elif IS_DARWIN:
            res = _run_cmd(["pmset", "displaysleep", str(minutes)])
            return _result("success" if res["success"] else "error",
                           "Display sleep set" if res["success"] else res.get("error"))
        return _result("error", "Unsupported OS")
    except Exception as e:
        return _result("error", str(e))

def set_sleep_timeout(minutes: int) -> Dict[str, Any]:
    try:
        minutes = max(1, minutes)
        if IS_WINDOWS:
            ac_res = _run_cmd(["powercfg", "/change", "standby-timeout-ac", str(minutes)])
            dc_res = _run_cmd(["powercfg", "/change", "standby-timeout-dc", str(minutes)])
            return _result("success" if ac_res["success"] and dc_res["success"] else "error",
                           "System sleep timeout updated")
        elif IS_LINUX:
            res = _run_cmd(["systemd-inhibit", "--what=sleep", "--mode=block", "true"]) # Placeholder logic, actual requires logind
            # Fallback to pm-utils or xset for simplicity in toolkit context
            return _result("warning", "Linux sleep timeout requires session manager config", {"recommendation": "Use systemd/logind"})
        elif IS_DARWIN:
            res = _run_cmd(["pmset", "sleep", str(minutes)])
            return _result("success" if res["success"] else "error",
                           "System sleep set" if res["success"] else res.get("error"))
        return _result("error", "Unsupported OS")
    except Exception as e:
        return _result("error", str(e))

def enable_wake_timers(enabled: bool) -> Dict[str, Any]:
    try:
        if IS_WINDOWS:
            val = "1" if enabled else "0"
            # GUIDs for SUB_SLEEP and RTCWAKE
            res_ac = _run_cmd(["powercfg", "/setacvalueindex", "SCHEME_CURRENT", "238c9fa8-0aad-41ed-83f4-97be242c8f20", "bd3b718a-0680-4d9d-8ab2-e1d2b4ac806d", val])
            res_dc = _run_cmd(["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", "238c9fa8-0aad-41ed-83f4-97be242c8f20", "bd3b718a-0680-4d9d-8ab2-e1d2b4ac806d", val])
            apply = _run_cmd(["powercfg", "/setactive", "SCHEME_CURRENT"])
            return _result("success" if all(r["success"] for r in [res_ac, res_dc, apply]) else "error",
                           f"Wake timers {'enabled' if enabled else 'disabled'}")
        elif IS_LINUX or IS_DARWIN:
            return _result("warning", "Wake timers handled by OS/hardware on Unix. Use `rtcwake` or `pmset` manually.", {"os": _OS})
        return _result("error", "Unsupported OS")
    except Exception as e:
        return _result("error", str(e))

def get_thermal_info() -> Dict[str, Any]:
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return _result("warning", "No thermal sensors detected", {"sensors": {}})
        
        data = {}
        for chip, entries in temps.items():
            data[chip] = [{"label": e.label or "unnamed", "current": e.current, "high": e.high, "critical": e.critical} for e in entries]
        return _result("success", "Thermal info retrieved", {"sensors": data, "unit": "celsius"})
    except Exception as e:
        return _result("error", str(e))