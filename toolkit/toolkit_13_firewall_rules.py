"""
toolkit_13_firewall_rules.py
List, create, enable, disable, and remove Windows Firewall rules via PowerShell.
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

def list_firewall_rules(direction: str = "all") -> Dict[str, Any]:
    """direction: 'inbound', 'outbound', or 'all'"""
    try:
        if direction.lower() == "inbound":
            filt = "Where-Object {$_.Direction -eq 'Inbound'} | "
        elif direction.lower() == "outbound":
            filt = "Where-Object {$_.Direction -eq 'Outbound'} | "
        else:
            filt = ""
        out = _run_ps("Get-NetFirewallRule | " + filt + "Select-Object Name,DisplayName,Direction,Action,Enabled,Profile | ConvertTo-Json -Depth 3")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_firewall_rule(rule_name: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-NetFirewallRule -Name "' + rule_name + '" | Select-Object Name,DisplayName,Description,Direction,Action,Enabled,Profile,Protocol | ConvertTo-Json -Depth 3')
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_enabled_rules() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-NetFirewallRule | Where-Object {$_.Enabled -eq $true} | Select-Object Name,DisplayName,Direction,Action,Profile | ConvertTo-Json -Depth 3")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_blocking_rules() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-NetFirewallRule | Where-Object {$_.Action -eq 'Block' -and $_.Enabled -eq $true} | Select-Object Name,DisplayName,Direction,Action | ConvertTo-Json -Depth 3")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def enable_rule(rule_name: str) -> Dict[str, Any]:
    try:
        _run_ps('Set-NetFirewallRule -Name "' + rule_name + '" -Enabled True')
        return {"success": True, "data": "Rule enabled: " + rule_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def disable_rule(rule_name: str) -> Dict[str, Any]:
    try:
        _run_ps('Set-NetFirewallRule -Name "' + rule_name + '" -Enabled False')
        return {"success": True, "data": "Rule disabled: " + rule_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def remove_rule(rule_name: str) -> Dict[str, Any]:
    try:
        _run_ps('Remove-NetFirewallRule -Name "' + rule_name + '"')
        return {"success": True, "data": "Rule removed: " + rule_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def add_inbound_tcp_rule(rule_name: str, display_name: str, port: int, action: str = "Allow") -> Dict[str, Any]:
    try:
        script = 'New-NetFirewallRule -Name "' + rule_name + '" -DisplayName "' + display_name + '" -Direction Inbound -Protocol TCP -LocalPort ' + str(port) + ' -Action ' + action
        out = _run_ps(script)
        return {"success": True, "data": "Inbound TCP rule created on port " + str(port), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def add_outbound_tcp_rule(rule_name: str, display_name: str, port: int, action: str = "Allow") -> Dict[str, Any]:
    try:
        script = 'New-NetFirewallRule -Name "' + rule_name + '" -DisplayName "' + display_name + '" -Direction Outbound -Protocol TCP -RemotePort ' + str(port) + ' -Action ' + action
        out = _run_ps(script)
        return {"success": True, "data": "Outbound TCP rule created on port " + str(port), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def add_program_rule(rule_name: str, display_name: str, program_path: str, direction: str = "Inbound", action: str = "Allow") -> Dict[str, Any]:
    try:
        script = 'New-NetFirewallRule -Name "' + rule_name + '" -DisplayName "' + display_name + '" -Direction ' + direction + ' -Program "' + program_path + '" -Action ' + action
        out = _run_ps(script)
        return {"success": True, "data": "Program rule created for " + program_path, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def block_ip_address(ip_address: str, rule_name: str = "") -> Dict[str, Any]:
    try:
        if not rule_name:
            rule_name = "Block_" + ip_address.replace(".", "_")
        script = 'New-NetFirewallRule -Name "' + rule_name + '" -DisplayName "Block ' + ip_address + '" -Direction Inbound -RemoteAddress "' + ip_address + '" -Action Block'
        out = _run_ps(script)
        return {"success": True, "data": "IP blocked: " + ip_address, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def unblock_ip_address(ip_address: str) -> Dict[str, Any]:
    try:
        rule_name = "Block_" + ip_address.replace(".", "_")
        _run_ps('Remove-NetFirewallRule -Name "' + rule_name + '" -ErrorAction SilentlyContinue')
        return {"success": True, "data": "IP unblocked: " + ip_address, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_firewall_profile_status() -> Dict[str, Any]:
    try:
        out = _run_ps("Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction | ConvertTo-Json -Depth 2")
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def enable_firewall(profile: str = "All") -> Dict[str, Any]:
    try:
        _run_ps('Set-NetFirewallProfile -Profile "' + profile + '" -Enabled True')
        return {"success": True, "data": "Firewall enabled for profile: " + profile, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def disable_firewall(profile: str = "All") -> Dict[str, Any]:
    try:
        _run_ps('Set-NetFirewallProfile -Profile "' + profile + '" -Enabled False')
        return {"success": True, "data": "Firewall disabled for profile: " + profile, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def search_rules_by_name(keyword: str) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*' + keyword + '*"} | Select-Object Name,DisplayName,Direction,Action,Enabled | ConvertTo-Json -Depth 3')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_rules_for_port(port: int) -> Dict[str, Any]:
    try:
        out = _run_ps('Get-NetFirewallPortFilter | Where-Object {$_.LocalPort -eq ' + str(port) + ' -or $_.RemotePort -eq ' + str(port) + '} | Get-NetFirewallRule | Select-Object Name,DisplayName,Direction,Action,Enabled | ConvertTo-Json -Depth 3')
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def count_rules() -> Dict[str, Any]:
    try:
        out = _run_ps("(Get-NetFirewallRule).Count")
        total = int(out.strip()) if out.strip().isdigit() else 0
        out2 = _run_ps("(Get-NetFirewallRule | Where-Object {$_.Enabled -eq $true}).Count")
        enabled = int(out2.strip()) if out2.strip().isdigit() else 0
        return {"success": True, "data": {"total": total, "enabled": enabled, "disabled": total - enabled}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def export_rules_to_file(output_path: str) -> Dict[str, Any]:
    try:
        _run_ps('netsh advfirewall export "' + output_path + '"')
        import os
        exists = os.path.isfile(output_path)
        return {"success": exists, "data": {"path": output_path, "exported": exists}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def reset_firewall_defaults() -> Dict[str, Any]:
    try:
        _run_ps("netsh advfirewall reset")
        return {"success": True, "data": "Firewall reset to defaults", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
