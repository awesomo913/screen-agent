"""
print_queue.py - Print spool and job management.

Extends the basic printer listing with queue inspection, job control,
and spool service management via PowerShell.  Zero third-party deps.
"""

import json
import subprocess
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data: Any = None, message: str = "OK") -> Dict[str, Any]:
    return {"success": True, "data": data, "error": None, "message": message}


def _err(error: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "error": error, "message": error}


def _ps(cmd: str, timeout: int = 15) -> str:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    if r.returncode != 0 and r.stderr.strip():
        raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout.strip()


def _ps_json(cmd: str, timeout: int = 15):
    raw = _ps(cmd + " | ConvertTo-Json -Depth 3 -Compress", timeout)
    if not raw:
        return []
    data = json.loads(raw)
    return data if isinstance(data, list) else [data]


# ---------------------------------------------------------------------------
# Print Jobs
# ---------------------------------------------------------------------------

def get_print_jobs(printer_name: Optional[str] = None) -> Dict[str, Any]:
    """List all active print jobs, optionally filtered by printer."""
    try:
        if printer_name:
            cmd = f'Get-PrintJob -PrinterName "{printer_name}"'
        else:
            # Get jobs from all printers
            cmd = 'Get-Printer | ForEach-Object { Get-PrintJob -PrinterName $_.Name 2>$null } '
        jobs = _ps_json(cmd)
        results = []
        for j in jobs:
            results.append({
                "id": j.get("Id"),
                "document": j.get("DocumentName"),
                "status": j.get("JobStatus"),
                "printer": j.get("PrinterName"),
                "user": j.get("UserName"),
                "pages": j.get("TotalPages"),
                "size": j.get("Size"),
                "submitted": j.get("SubmittedTime"),
            })
        return _ok({"jobs": results, "count": len(results)},
                    f"Found {len(results)} print jobs")
    except Exception as e:
        return _err(str(e))


def cancel_print_job(printer_name: str, job_id: int) -> Dict[str, Any]:
    """Cancel a specific print job by ID."""
    try:
        _ps(f'Remove-PrintJob -PrinterName "{printer_name}" -ID {job_id}')
        return _ok({"printer": printer_name, "job_id": job_id},
                    f"Cancelled job {job_id} on '{printer_name}'")
    except Exception as e:
        return _err(str(e))


def cancel_all_print_jobs(printer_name: str) -> Dict[str, Any]:
    """Cancel all print jobs on a specific printer."""
    try:
        _ps(f'Get-PrintJob -PrinterName "{printer_name}" | Remove-PrintJob')
        return _ok({"printer": printer_name},
                    f"All jobs cancelled on '{printer_name}'")
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Printer Control
# ---------------------------------------------------------------------------

def pause_printer(printer_name: str) -> Dict[str, Any]:
    """Pause a printer (stops processing queued jobs)."""
    try:
        _ps(f'(Get-WmiObject Win32_Printer -Filter "Name=\'{printer_name}\'").Pause()')
        return _ok({"printer": printer_name}, f"Printer '{printer_name}' paused")
    except Exception as e:
        return _err(str(e))


def resume_printer(printer_name: str) -> Dict[str, Any]:
    """Resume a paused printer."""
    try:
        _ps(f'(Get-WmiObject Win32_Printer -Filter "Name=\'{printer_name}\'").Resume()')
        return _ok({"printer": printer_name}, f"Printer '{printer_name}' resumed")
    except Exception as e:
        return _err(str(e))


def get_printer_status(printer_name: str) -> Dict[str, Any]:
    """Get detailed status of a specific printer."""
    try:
        data = _ps_json(
            f'Get-Printer -Name "{printer_name}" | Select-Object Name,DriverName,'
            f'PortName,Shared,Published,Type,PrinterStatus'
        )
        if data:
            return _ok(data[0], f"Status for '{printer_name}'")
        return _err(f"Printer '{printer_name}' not found")
    except Exception as e:
        return _err(str(e))


def get_printer_config(printer_name: str) -> Dict[str, Any]:
    """Get print configuration (duplex, collate, color mode)."""
    try:
        data = _ps_json(
            f'Get-PrintConfiguration -PrinterName "{printer_name}" | '
            f'Select-Object PrinterName,DuplexingMode,Collate,Color'
        )
        if data:
            return _ok(data[0], f"Config for '{printer_name}'")
        return _err(f"Configuration not available for '{printer_name}'")
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Spooler Service
# ---------------------------------------------------------------------------

def restart_print_spooler() -> Dict[str, Any]:
    """Restart the Windows Print Spooler service (clears stuck jobs)."""
    try:
        _ps("Restart-Service -Name Spooler -Force", timeout=20)
        return _ok(None, "Print Spooler service restarted")
    except Exception as e:
        return _err(str(e))


def get_spooler_status() -> Dict[str, Any]:
    """Check the Print Spooler service status."""
    try:
        data = _ps_json(
            'Get-Service Spooler | Select-Object Name,Status,StartType'
        )
        if data:
            return _ok(data[0], f"Spooler status: {data[0].get('Status')}")
        return _err("Could not query spooler service")
    except Exception as e:
        return _err(str(e))


def clear_spool_directory() -> Dict[str, Any]:
    """Stop spooler, clear the spool directory, restart spooler.
    Fixes stuck/corrupted print jobs."""
    try:
        _ps("Stop-Service -Name Spooler -Force", timeout=10)
        _ps(
            'Remove-Item -Path "$env:SystemRoot\\System32\\spool\\PRINTERS\\*" '
            '-Force -ErrorAction SilentlyContinue',
            timeout=10,
        )
        _ps("Start-Service -Name Spooler", timeout=10)
        return _ok(None, "Spool directory cleared and spooler restarted")
    except Exception as e:
        return _err(str(e))
