"""
toolkit_10_printer_manager.py
Manage Windows printers, print queues, and print jobs via WMI/PowerShell.
"""
from __future__ import annotations
import subprocess
import json
import os
from typing import Any, Dict, List

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()

def list_printers() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-Printer | Select-Object Name,DriverName,PortName,Shared,PrinterStatus,Default | ConvertTo-Json -Depth 3")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_default_printer() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-Printer | Where-Object {$_.Default -eq $true} | Select-Object Name,DriverName,PortName | ConvertTo-Json")
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_default_printer(printer_name: str) -> Dict[str, Any]:
    try:
        script = '(New-Object -ComObject WScript.Network).SetDefaultPrinter("' + printer_name + '"); "OK"'
        out = _run_ps(script)
        return {"success": "OK" in out, "data": out.strip(), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_printer_status(printer_name: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-Printer -Name "' + printer_name + '" | Select-Object Name,PrinterStatus,JobCount | ConvertTo-Json')
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_print_jobs(printer_name: str = "") -> Dict[str, Any]:
    try:
        if printer_name:
            out = _run_ps('Get-PrintJob -PrinterName "' + printer_name + '" | Select-Object Id,DocumentName,UserName,JobStatus,TotalPages,SubmittedTime | ConvertTo-Json -Depth 3')
        else:
            out = _run_ps("Get-Printer | ForEach-Object { Get-PrintJob -PrinterName $_.Name -ErrorAction SilentlyContinue } | Select-Object Id,DocumentName,UserName,JobStatus,TotalPages,SubmittedTime | ConvertTo-Json -Depth 3")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def cancel_print_job(printer_name: str, job_id: int) -> Dict[str, Any]:
    try:
        _run_ps('Remove-PrintJob -PrinterName "' + printer_name + '" -ID ' + str(job_id))
        return {"success": True, "data": "Job cancelled", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def cancel_all_print_jobs(printer_name: str) -> Dict[str, Any]:
    try:
        _run_ps('Get-PrintJob -PrinterName "' + printer_name + '" | Remove-PrintJob')
        return {"success": True, "data": "All jobs cancelled for " + printer_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def pause_printer(printer_name: str) -> Dict[str, Any]:
    try:
        _run_ps('Suspend-Printer -Name "' + printer_name + '"')
        return {"success": True, "data": "Printer paused: " + printer_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def resume_printer(printer_name: str) -> Dict[str, Any]:
    try:
        _run_ps('Resume-Printer -Name "' + printer_name + '"')
        return {"success": True, "data": "Printer resumed: " + printer_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_printer_drivers() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-PrinterDriver | Select-Object Name,DriverVersion,Manufacturer | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_printer_ports() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-PrinterPort | Select-Object Name,PrinterHostAddress,PortNumber,Protocol | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def add_tcp_printer_port(port_name: str, printer_ip: str, port_number: int = 9100) -> Dict[str, Any]:
    try:
        _run_ps('Add-PrinterPort -Name "' + port_name + '" -PrinterHostAddress "' + printer_ip + '" -PortNumber ' + str(port_number))
        return {"success": True, "data": "Port added: " + port_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def install_network_printer(printer_name: str, driver_name: str, port_name: str) -> Dict[str, Any]:
    try:
        _run_ps('Add-Printer -Name "' + printer_name + '" -DriverName "' + driver_name + '" -PortName "' + port_name + '"')
        return {"success": True, "data": "Printer installed: " + printer_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def remove_printer(printer_name: str) -> Dict[str, Any]:
    try:
        _run_ps('Remove-Printer -Name "' + printer_name + '"')
        return {"success": True, "data": "Printer removed: " + printer_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_printer_config(printer_name: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-PrintConfiguration -PrinterName "' + printer_name + '" | Select-Object Collate,Color,DuplexingMode,PaperSize,PrintQuality | ConvertTo-Json')
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_duplex_mode(printer_name: str, duplex: str = "TwoSidedLongEdge") -> Dict[str, Any]:
    try:
        _run_ps('Set-PrintConfiguration -PrinterName "' + printer_name + '" -DuplexingMode "' + duplex + '"')
        return {"success": True, "data": "Duplex set to " + duplex, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def print_test_page(printer_name: str) -> Dict[str, Any]:
    try:
        script = "$p = Get-WmiObject Win32_Printer -Filter 'Name=\"" + printer_name + "\"'; $p.PrintTestPage() | Out-Null"
        _run_ps(script)
        return {"success": True, "data": "Test page sent to " + printer_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_printer_count() -> Dict[str, Any]:
    try:
        out = _run_ps("(Get-Printer).Count")
        count = int(out.strip()) if out.strip().isdigit() else 0
        return {"success": True, "data": count, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_shared_printers() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-Printer | Where-Object {$_.Shared -eq $true} | Select-Object Name,ShareName,DriverName | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def clear_print_spooler() -> Dict[str, Any]:
    try:
        out = _run_ps('Stop-Service -Name Spooler -Force; Remove-Item "$env:SystemRoot\\System32\\spool\\PRINTERS\\*" -Force -ErrorAction SilentlyContinue; Start-Service -Name Spooler; "OK"')
        return {"success": True, "data": "Print spooler cleared and restarted", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_spooler_status() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-Service -Name Spooler | Select-Object Status,StartType | ConvertTo-Json")
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def rename_printer(old_name: str, new_name: str) -> Dict[str, Any]:
    try:
        _run_ps('Rename-Printer -Name "' + old_name + '" -NewName "' + new_name + '"')
        return {"success": True, "data": "Renamed to " + new_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_print_job_count(printer_name: str) -> Dict[str, Any]:
    try:
        out = _run_ps('(Get-PrintJob -PrinterName "' + printer_name + '" -ErrorAction SilentlyContinue).Count')
        count = int(out.strip()) if out.strip().isdigit() else 0
        return {"success": True, "data": count, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
