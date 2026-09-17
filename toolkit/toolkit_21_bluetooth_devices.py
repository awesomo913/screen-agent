"""
toolkit_21_bluetooth_devices.py
Enumerate, inspect, and manage Bluetooth devices on Windows via PowerShell/WMI.
"""
from __future__ import annotations
import subprocess
import json
from typing import Any, Dict, List

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()

def list_bluetooth_devices() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -like 'BTHENUM*' -or $_.InstanceId -like 'BTH*'} | Select-Object Name,DeviceID,Status,Class | ConvertTo-Json -Depth 3")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_all_bluetooth_devices() -> Dict[str, Any]:
    """Includes disconnected/previously paired devices."""
    try:
        out = _run_ps("Get-PnpDevice | Where-Object {$_.InstanceId -like 'BTHENUM*' -or $_.InstanceId -like 'BTH*'} | Select-Object Name,DeviceID,Status,Class | ConvertTo-Json -Depth 3")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_bluetooth_adapters() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-PnpDevice -PresentOnly | Where-Object {$_.Class -eq 'Bluetooth' -and ($_.Name -like '*Adapter*' -or $_.Name -like '*Radio*' -or $_.Name -like '*Controller*')} | Select-Object Name,DeviceID,Status | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_paired_devices() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-PnpDevice | Where-Object {$_.Class -eq 'Bluetooth' -and $_.Status -eq 'OK'} | Select-Object Name,DeviceID,Status | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_bluetooth_device_details(device_id: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-PnpDeviceProperty -InstanceId "' + device_id + '" | Select-Object KeyName,Data | ConvertTo-Json -Depth 3')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def disable_bluetooth_device(device_id: str) -> Dict[str, Any]:
    try:
        _run_ps('Disable-PnpDevice -InstanceId "' + device_id + '" -Confirm:$false')
        return {"success": True, "data": "Bluetooth device disabled", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def enable_bluetooth_device(device_id: str) -> Dict[str, Any]:
    try:
        _run_ps('Enable-PnpDevice -InstanceId "' + device_id + '" -Confirm:$false')
        return {"success": True, "data": "Bluetooth device enabled", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def remove_bluetooth_device(device_id: str) -> Dict[str, Any]:
    try:
        _run_ps('$d = Get-PnpDevice -InstanceId "' + device_id + '"; $d | Remove-PnpDevice -Confirm:$false')
        return {"success": True, "data": "Bluetooth device removed/unpaired", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def is_bluetooth_enabled() -> Dict[str, Any]:
    try:
        out = _run_ps("(Get-PnpDevice -PresentOnly | Where-Object {$_.Class -eq 'Bluetooth' -and $_.Status -eq 'OK'}).Count")
        count = int(out.strip()) if out.strip().isdigit() else 0
        return {"success": True, "data": {"bluetooth_present": count > 0, "adapter_count": count}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_bluetooth_audio_devices() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-PnpDevice -PresentOnly | Where-Object {($_.InstanceId -like 'BTHENUM*') -and ($_.Class -eq 'AudioEndpoint' -or $_.Name -like '*Headset*' -or $_.Name -like '*Headphone*' -or $_.Name -like '*Speaker*')} | Select-Object Name,DeviceID,Status | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_bluetooth_input_devices() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-PnpDevice -PresentOnly | Where-Object {($_.InstanceId -like 'BTHENUM*') -and ($_.Class -eq 'HIDClass' -or $_.Class -eq 'Mouse' -or $_.Class -eq 'Keyboard')} | Select-Object Name,DeviceID,Status,Class | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def search_bluetooth_by_name(keyword: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-PnpDevice | Where-Object {($_.InstanceId -like "BTHENUM*" -or $_.InstanceId -like "BTH*") -and $_.Name -like "*' + keyword + '*"} | Select-Object Name,DeviceID,Status,Class | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def count_bluetooth_devices() -> Dict[str, Any]:
    try:
        out = _run_ps("(Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -like 'BTHENUM*' -or $_.InstanceId -like 'BTH*'}).Count")
        count = int(out.strip()) if out.strip().isdigit() else 0
        return {"success": True, "data": count, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_problematic_bt_devices() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-PnpDevice | Where-Object {($_.InstanceId -like 'BTHENUM*') -and $_.Status -ne 'OK'} | Select-Object Name,DeviceID,Status | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_bluetooth_driver_info() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_PnPSignedDriver | Where-Object {$_.DeviceClass -eq 'Bluetooth'} | Select-Object DeviceName,DriverVersion,Manufacturer | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def open_bluetooth_settings() -> Dict[str, Any]:
    try:
        subprocess.Popen(["explorer", "ms-settings:bluetooth"])
        return {"success": True, "data": "Opened Bluetooth settings", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
