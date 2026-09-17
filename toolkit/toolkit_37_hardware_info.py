"""
toolkit_37_hardware_info.py
Detailed hardware inventory: CPU, GPU, motherboard, RAM slots,
storage controllers, PCI devices, BIOS info via WMI/PowerShell.
"""
from __future__ import annotations
import subprocess
import json
import platform
from typing import Any, Dict, List

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()

def get_cpu_details() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_Processor | Select-Object Name,Manufacturer,Architecture,MaxClockSpeed,NumberOfCores,NumberOfLogicalProcessors,L2CacheSize,L3CacheSize,ProcessorId,SocketDesignation | ConvertTo-Json -Depth 3")
        data = json.loads(out) if out else None
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_gpu_info() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion,VideoModeDescription,CurrentRefreshRate,AdapterCompatibility | ConvertTo-Json -Depth 3")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        for d in data:
            if d.get("AdapterRAM"):
                d["AdapterRAM_MB"] = round(int(d["AdapterRAM"]) / 1048576, 0)
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_motherboard_info() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_BaseBoard | Select-Object Manufacturer,Product,Version,SerialNumber | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_bios_info() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_BIOS | Select-Object Manufacturer,Name,Version,SMBIOSBIOSVersion,ReleaseDate,SerialNumber | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_ram_slots() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_PhysicalMemory | Select-Object BankLabel,DeviceLocator,Capacity,Speed,Manufacturer,PartNumber,MemoryType,FormFactor | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        for d in data:
            if d.get("Capacity"):
                d["Capacity_GB"] = round(int(d["Capacity"]) / 1073741824, 1)
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_storage_controllers() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_IDEController,Win32_SCSIController,Win32_StorageVolume -ErrorAction SilentlyContinue | Select-Object Name,Manufacturer,DeviceID | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_disk_drives() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_DiskDrive | Select-Object Model,InterfaceType,Size,MediaType,SerialNumber,FirmwareRevision,Partitions | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        for d in data:
            if d.get("Size"):
                d["Size_GB"] = round(int(d["Size"]) / 1073741824, 1)
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_pci_devices() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_PnPEntity | Where-Object {$_.PNPClass -eq 'Display' -or $_.PNPClass -eq 'Net' -or $_.PNPClass -eq 'SCSIAdapter'} | Select-Object Name,PNPClass,DeviceID | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_network_adapters_hardware() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_NetworkAdapter | Where-Object {$_.PhysicalAdapter -eq $true} | Select-Object Name,Manufacturer,MACAddress,Speed,AdapterType | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_system_chassis() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_SystemEnclosure | Select-Object Manufacturer,Model,SerialNumber,ChassisTypes | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_computer_system() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_ComputerSystem | Select-Object Manufacturer,Model,Name,Domain,TotalPhysicalMemory,SystemType,NumberOfProcessors,NumberOfLogicalProcessors | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else None
        if data and data.get("TotalPhysicalMemory"):
            data["TotalPhysicalMemory_GB"] = round(int(data["TotalPhysicalMemory"]) / 1073741824, 1)
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_monitor_info() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_DesktopMonitor | Select-Object Name,ScreenWidth,ScreenHeight,MonitorManufacturer,MonitorType,DeviceID | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_battery_hardware() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-WmiObject Win32_Battery | Select-Object Name,Manufacturer,EstimatedChargeRemaining,FullChargeCapacity,DesignCapacity,BatteryStatus | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_full_hardware_summary() -> Dict[str, Any]:
    """Collect all hardware info in one call."""
    try:
        summary = {}
        for key, fn in [("cpu", get_cpu_details), ("gpu", get_gpu_info),
                         ("motherboard", get_motherboard_info), ("bios", get_bios_info),
                         ("ram", get_ram_slots), ("disks", get_disk_drives),
                         ("system", get_computer_system)]:
            r = fn()
            summary[key] = r["data"] if r["success"] else {"error": r["error"]}
        return {"success": True, "data": summary, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
