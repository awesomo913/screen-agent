"""
toolkit_11_usb_devices.py
Enumerate, inspect, and manage USB devices on Windows via PowerShell/WMI.
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

def list_usb_devices() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -like 'USB*'} | Select-Object Name,DeviceID,Status,Class | ConvertTo-Json -Depth 3")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_all_usb_devices() -> Dict[str, Any]:
    """Includes disconnected USB devices."""
    try:
        out = _run_ps("Get-PnpDevice | Where-Object {$_.InstanceId -like 'USB*'} | Select-Object Name,DeviceID,Status,Class | ConvertTo-Json -Depth 3")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_usb_storage_devices() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-PnpDevice -PresentOnly -Class DiskDrive | Where-Object {$_.InstanceId -like 'USB*'} | Select-Object Name,DeviceID,Status | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_usb_hubs() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-PnpDevice -PresentOnly -Class USB | Where-Object {$_.Name -like '*Hub*'} | Select-Object Name,DeviceID,Status | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_usb_device_details(device_id: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-PnpDeviceProperty -InstanceId "' + device_id + '" | Select-Object KeyName,Data | ConvertTo-Json -Depth 3')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def disable_usb_device(device_id: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Disable-PnpDevice -InstanceId "' + device_id + '" -Confirm:$false; "OK"')
        return {"success": True, "data": "Device disabled: " + device_id, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def enable_usb_device(device_id: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Enable-PnpDevice -InstanceId "' + device_id + '" -Confirm:$false; "OK"')
        return {"success": True, "data": "Device enabled: " + device_id, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def eject_usb_drive(drive_letter: str) -> Dict[str, Any]:
    try:
        script = '''
$dl = "''' + drive_letter.rstrip("\\").rstrip("/") + '''"
$shell = New-Object -ComObject Shell.Application
$folder = $shell.Namespace(17)
$item = $folder.ParseName($dl)
$item.InvokeVerb("Eject")
"OK"
'''
        out = _run_ps(script)
        return {"success": True, "data": "Eject sent to " + drive_letter, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_removable_drives() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_LogicalDisk | Where-Object {$_.DriveType -eq 2} | Select-Object DeviceID,VolumeName,Size,FreeSpace | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_usb_serial_devices() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-PnpDevice -PresentOnly -Class Ports | Where-Object {$_.InstanceId -like 'USB*'} | Select-Object Name,DeviceID,Status | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def count_usb_devices() -> Dict[str, Any]:
    try:
        out = _run_ps("(Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -like 'USB*'}).Count")
        count = int(out.strip()) if out.strip().isdigit() else 0
        return {"success": True, "data": count, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_usb_device_by_class(device_class: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-PnpDevice -PresentOnly -Class "' + device_class + '" | Where-Object {$_.InstanceId -like "USB*"} | Select-Object Name,DeviceID,Status | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def search_usb_by_name(keyword: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -like "USB*" -and $_.Name -like "*' + keyword + '*"} | Select-Object Name,DeviceID,Status,Class | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_problematic_usb_devices() -> Dict[str, Any]:
    try:
        out = _run_ps('Get-PnpDevice | Where-Object {$_.InstanceId -like "USB*" -and $_.Status -ne "OK"} | Select-Object Name,DeviceID,Status,Class | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_usb_audio_devices() -> Dict[str, Any]:
    try:
        out = _run_ps('Get-PnpDevice -PresentOnly -Class "AudioEndpoint" | Where-Object {$_.InstanceId -like "USB*"} | Select-Object Name,DeviceID,Status | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_usb_cameras() -> Dict[str, Any]:
    try:
        out = _run_ps('Get-PnpDevice -PresentOnly | Where-Object {($_.Class -eq "Camera" -or $_.Class -eq "Image") -and $_.InstanceId -like "USB*"} | Select-Object Name,DeviceID,Status | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_usb_hid_devices() -> Dict[str, Any]:
    try:
        out = _run_ps('Get-PnpDevice -PresentOnly -Class "HIDClass" | Where-Object {$_.InstanceId -like "USB*"} | Select-Object Name,DeviceID,Status | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def uninstall_usb_device(device_id: str) -> Dict[str, Any]:
    try:
        out = _run_ps('$d = Get-PnpDevice -InstanceId "' + device_id + '"; $d | Remove-PnpDevice -Confirm:$false; "OK"')
        return {"success": True, "data": "Device uninstalled: " + device_id, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_usb_vendor_product(device_id: str) -> Dict[str, Any]:
    """Extract VID and PID from device ID string."""
    try:
        vid, pid = "", ""
        if "VID_" in device_id.upper():
            vid_idx = device_id.upper().index("VID_") + 4
            vid = device_id[vid_idx:vid_idx+4]
        if "PID_" in device_id.upper():
            pid_idx = device_id.upper().index("PID_") + 4
            pid = device_id[pid_idx:pid_idx+4]
        return {"success": True, "data": {"vendor_id": vid, "product_id": pid, "device_id": device_id}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
