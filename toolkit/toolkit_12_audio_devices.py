"""
toolkit_12_audio_devices.py
Enumerate and configure Windows audio devices, endpoints, and volume levels
via PowerShell and Windows Core Audio APIs. Complements auto_sound_controller
(which handles media keys/hotkeys) by providing device-level management.
"""
from __future__ import annotations
import subprocess
import json
from typing import Any, Dict, List

try:
    import comtypes
    HAS_COMTYPES = True
except ImportError:
    HAS_COMTYPES = False

try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, IMMDeviceEnumerator
    from comtypes import CLSCTX_ALL
    HAS_PYCAW = True
except ImportError:
    HAS_PYCAW = False

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()

def list_audio_devices() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-PnpDevice -PresentOnly -Class AudioEndpoint | Select-Object Name,DeviceID,Status | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_audio_endpoints() -> Dict[str, Any]:
    try:
        script = """
Add-Type -AssemblyName System.Windows.Forms
$out = @()
$devEnum = [System.Runtime.InteropServices.Marshal]::GetComInterfaceForObject(
    (New-Object -ComObject MMDeviceAPI.MMDeviceEnumerator), [type]::GetTypeFromCLSID([Guid]::NewGuid()))
Get-PnpDevice -PresentOnly -Class AudioEndpoint | ForEach-Object {
    $out += @{Name=$_.Name; DeviceID=$_.DeviceID; Status=$_.Status}
}
$out | ConvertTo-Json -Depth 3
"""
        out = _run_ps("Get-PnpDevice -PresentOnly -Class AudioEndpoint | Select-Object Name,DeviceID,Status | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_default_audio_playback() -> Dict[str, Any]:
    try:
        script = """
$dev = Get-WmiObject Win32_SoundDevice | Where-Object {$_.Status -eq 'OK'} | Select-Object -First 1 -Property Name,DeviceID,Manufacturer,Status
$dev | ConvertTo-Json
"""
        out = _run_ps(script)
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_sound_devices_wmi() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_SoundDevice | Select-Object Name,DeviceID,Manufacturer,Status | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_master_volume() -> Dict[str, Any]:
    try:
        if HAS_PYCAW:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            level = round(volume.GetMasterVolumeLevelScalar() * 100, 1)
            muted = volume.GetMute()
            return {"success": True, "data": {"volume_percent": level, "muted": bool(muted)}, "error": None}
        out = _run_ps("[int](([Windows.Media.Audio.AudioGraph, Windows.Media, ContentType=WindowsRuntime] -and $false) -or (Get-WmiObject -Query 'SELECT * FROM Win32_SoundDevice').Count)")
        return {"success": True, "data": {"volume_percent": None, "note": "pycaw not installed"}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_master_volume(level: float) -> Dict[str, Any]:
    try:
        if not 0 <= level <= 100:
            return {"success": False, "data": None, "error": "Level must be 0-100"}
        if HAS_PYCAW:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            return {"success": True, "data": {"volume_percent": level}, "error": None}
        scalar = level / 100.0
        out = _run_ps("""
$wshShell = New-Object -ComObject WScript.Shell
[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null
""")
        return {"success": False, "data": None, "error": "pycaw not installed; install with: pip install pycaw"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def mute_audio() -> Dict[str, Any]:
    try:
        if HAS_PYCAW:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMute(1, None)
            return {"success": True, "data": "Audio muted", "error": None}
        return {"success": False, "data": None, "error": "pycaw not installed"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def unmute_audio() -> Dict[str, Any]:
    try:
        if HAS_PYCAW:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMute(0, None)
            return {"success": True, "data": "Audio unmuted", "error": None}
        return {"success": False, "data": None, "error": "pycaw not installed"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_audio_sessions() -> Dict[str, Any]:
    """List per-app audio sessions with volume levels."""
    try:
        if not HAS_PYCAW:
            return {"success": False, "data": None, "error": "pycaw not installed"}
        sessions = AudioUtilities.GetAllSessions()
        result = []
        for session in sessions:
            if session.Process:
                result.append({
                    "pid": session.Process.pid,
                    "name": session.Process.name(),
                    "state": session.State
                })
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_app_volume(process_name: str, level: float) -> Dict[str, Any]:
    try:
        if not HAS_PYCAW:
            return {"success": False, "data": None, "error": "pycaw not installed"}
        if not 0 <= level <= 100:
            return {"success": False, "data": None, "error": "Level must be 0-100"}
        from pycaw.pycaw import ISimpleAudioVolume
        sessions = AudioUtilities.GetAllSessions()
        changed = 0
        for session in sessions:
            if session.Process and process_name.lower() in session.Process.name().lower():
                vol = session._ctl.QueryInterface(ISimpleAudioVolume)
                vol.SetMasterVolume(level / 100.0, None)
                changed += 1
        return {"success": True, "data": {"changed_sessions": changed}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def mute_app(process_name: str) -> Dict[str, Any]:
    try:
        if not HAS_PYCAW:
            return {"success": False, "data": None, "error": "pycaw not installed"}
        from pycaw.pycaw import ISimpleAudioVolume
        sessions = AudioUtilities.GetAllSessions()
        changed = 0
        for session in sessions:
            if session.Process and process_name.lower() in session.Process.name().lower():
                vol = session._ctl.QueryInterface(ISimpleAudioVolume)
                vol.SetMute(1, None)
                changed += 1
        return {"success": True, "data": {"muted_sessions": changed}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_microphones() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-PnpDevice -PresentOnly | Where-Object {$_.Class -eq 'AudioEndpoint' -and $_.Name -like '*Microphone*'} | Select-Object Name,DeviceID,Status | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def disable_audio_device(device_id: str) -> Dict[str, Any]:
    try:
        _run_ps('Disable-PnpDevice -InstanceId "' + device_id + '" -Confirm:$false')
        return {"success": True, "data": "Device disabled: " + device_id, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def enable_audio_device(device_id: str) -> Dict[str, Any]:
    try:
        _run_ps('Enable-PnpDevice -InstanceId "' + device_id + '" -Confirm:$false')
        return {"success": True, "data": "Device enabled: " + device_id, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_audio_driver_info() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_SoundDevice | Select-Object Name,DriverVersion,Status,DeviceID | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_pycaw_available() -> Dict[str, Any]:
    return {"success": True, "data": {"pycaw": HAS_PYCAW, "comtypes": HAS_COMTYPES}, "error": None}

def play_system_sound(sound_name: str = "SystemAsterisk") -> Dict[str, Any]:
    """Play a Windows system sound by name (e.g. SystemAsterisk, SystemHand, SystemQuestion)."""
    try:
        import winsound
        mapping = {
            "SystemAsterisk": winsound.MB_ICONASTERISK,
            "SystemHand": winsound.MB_ICONHAND,
            "SystemQuestion": winsound.MB_ICONQUESTION,
            "SystemExclamation": winsound.MB_ICONEXCLAMATION,
            "SystemOk": winsound.MB_OK,
        }
        flag = mapping.get(sound_name, winsound.MB_ICONASTERISK)
        winsound.MessageBeep(flag)
        return {"success": True, "data": "Played: " + sound_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def beep(frequency: int = 1000, duration_ms: int = 500) -> Dict[str, Any]:
    try:
        import winsound
        winsound.Beep(frequency, duration_ms)
        return {"success": True, "data": {"frequency": frequency, "duration_ms": duration_ms}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
