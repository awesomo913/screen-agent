"""
toolkit_16_task_scheduler.py
Query, create, enable, disable, and delete Windows Scheduled Tasks via PowerShell.
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

def list_scheduled_tasks(folder: str = "\\") -> Dict[str, Any]:
    try:
        out = _run_ps('Get-ScheduledTask -TaskPath "' + folder + '*" | Select-Object TaskName,TaskPath,State,Description | ConvertTo-Json -Depth 3')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_task_info(task_name: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-ScheduledTask -TaskName "' + task_name + '" | Select-Object TaskName,TaskPath,State,Description,Author | ConvertTo-Json -Depth 3')
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_task_run_info(task_name: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-ScheduledTaskInfo -TaskName "' + task_name + '" | Select-Object LastRunTime,NextRunTime,LastTaskResult,NumberOfMissedRuns | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_running_tasks() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-ScheduledTask | Where-Object {$_.State -eq 'Running'} | Select-Object TaskName,TaskPath,State | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_disabled_tasks() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-ScheduledTask | Where-Object {$_.State -eq 'Disabled'} | Select-Object TaskName,TaskPath | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def enable_task(task_name: str) -> Dict[str, Any]:
    try:
        _run_ps('Enable-ScheduledTask -TaskName "' + task_name + '"')
        return {"success": True, "data": "Task enabled: " + task_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def disable_task(task_name: str) -> Dict[str, Any]:
    try:
        _run_ps('Disable-ScheduledTask -TaskName "' + task_name + '"')
        return {"success": True, "data": "Task disabled: " + task_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def run_task_now(task_name: str) -> Dict[str, Any]:
    try:
        _run_ps('Start-ScheduledTask -TaskName "' + task_name + '"')
        return {"success": True, "data": "Task started: " + task_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def stop_task(task_name: str) -> Dict[str, Any]:
    try:
        _run_ps('Stop-ScheduledTask -TaskName "' + task_name + '"')
        return {"success": True, "data": "Task stopped: " + task_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def delete_task(task_name: str) -> Dict[str, Any]:
    try:
        _run_ps('Unregister-ScheduledTask -TaskName "' + task_name + '" -Confirm:$false')
        return {"success": True, "data": "Task deleted: " + task_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_daily_task(task_name: str, program_path: str, time: str = "09:00", description: str = "") -> Dict[str, Any]:
    """Create a simple daily scheduled task. time format: HH:MM"""
    try:
        script = '''
$action = New-ScheduledTaskAction -Execute "''' + program_path + '''"
$trigger = New-ScheduledTaskTrigger -Daily -At "''' + time + '''"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName "''' + task_name + '''" -Action $action -Trigger $trigger -Settings $settings -Description "''' + description + '''" -Force
"OK"
'''
        out = _run_ps(script)
        return {"success": True, "data": "Daily task created: " + task_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_startup_task(task_name: str, program_path: str, description: str = "") -> Dict[str, Any]:
    try:
        script = '''
$action = New-ScheduledTaskAction -Execute "''' + program_path + '''"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName "''' + task_name + '''" -Action $action -Trigger $trigger -Settings $settings -Description "''' + description + '''" -Force
"OK"
'''
        out = _run_ps(script)
        return {"success": True, "data": "Startup task created: " + task_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_interval_task(task_name: str, program_path: str, interval_minutes: int = 60) -> Dict[str, Any]:
    try:
        script = '''
$action = New-ScheduledTaskAction -Execute "''' + program_path + '''"
$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes ''' + str(interval_minutes) + ''') -Once -At (Get-Date)
$settings = New-ScheduledTaskSettingsSet
Register-ScheduledTask -TaskName "''' + task_name + '''" -Action $action -Trigger $trigger -Settings $settings -Force
"OK"
'''
        out = _run_ps(script)
        return {"success": True, "data": "Interval task created: " + task_name + " every " + str(interval_minutes) + " min", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_task_action(task_name: str) -> Dict[str, Any]:
    try:
        script = '(Get-ScheduledTask -TaskName "' + task_name + '").Actions | Select-Object Execute,Arguments,WorkingDirectory | ConvertTo-Json -Depth 2'
        out = _run_ps(script)
        data = json.loads(out) if out else None
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_task_trigger(task_name: str) -> Dict[str, Any]:
    try:
        script = '(Get-ScheduledTask -TaskName "' + task_name + '").Triggers | ConvertTo-Json -Depth 3'
        out = _run_ps(script)
        data = json.loads(out) if out else None
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def search_tasks_by_name(keyword: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-ScheduledTask | Where-Object {$_.TaskName -like "*' + keyword + '*"} | Select-Object TaskName,TaskPath,State | ConvertTo-Json -Depth 2')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def count_tasks() -> Dict[str, Any]:
    try:
        out = _run_ps("(Get-ScheduledTask).Count")
        total = int(out.strip()) if out.strip().isdigit() else 0
        out2 = _run_ps("(Get-ScheduledTask | Where-Object {$_.State -eq 'Ready'}).Count")
        ready = int(out2.strip()) if out2.strip().isdigit() else 0
        return {"success": True, "data": {"total": total, "ready": ready}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
