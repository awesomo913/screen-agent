"""toolkit_84_code_converter.py
Convert code between languages using pattern mapping and online transpilers.
"""
import re
import json
import urllib.request

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

def _post(url, payload, headers=None):
    try:
        body = json.dumps(payload).encode()
        h = {'Content-Type': 'application/json'}
        if headers:
            h.update(headers)
        if HAS_REQUESTS:
            r = requests.post(url, json=payload, headers=h, timeout=20)
            return r.status_code, r.text
        req = urllib.request.Request(url, data=body, headers=h)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return 0, str(e)

def python_to_pseudocode(code: str) -> dict:
    """Convert Python code to English pseudocode."""
    try:
        lines = code.splitlines()
        pseudo = []
        for line in lines:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())
            pad = '  ' * (indent // 4)
            if not stripped or stripped.startswith('#'):
                pseudo.append(pad + stripped.replace('#','NOTE:'))
            elif stripped.startswith('def '):
                m = re.match(r'def (\w+)\(([^)]*)\):', stripped)
                if m:
                    args = m.group(2) or 'no arguments'
                    pseudo.append(pad + 'FUNCTION ' + m.group(1) + ' with ' + args)
            elif stripped.startswith('class '):
                m = re.match(r'class (\w+)', stripped)
                if m:
                    pseudo.append(pad + 'CLASS ' + m.group(1))
            elif stripped.startswith('if '):
                cond = stripped[3:].rstrip(':')
                pseudo.append(pad + 'IF ' + cond + ' THEN')
            elif stripped.startswith('elif '):
                cond = stripped[5:].rstrip(':')
                pseudo.append(pad + 'ELSE IF ' + cond + ' THEN')
            elif stripped == 'else:':
                pseudo.append(pad + 'ELSE')
            elif stripped.startswith('for '):
                m = re.match(r'for (.+) in (.+):', stripped)
                if m:
                    pseudo.append(pad + 'FOR EACH ' + m.group(1) + ' IN ' + m.group(2))
            elif stripped.startswith('while '):
                cond = stripped[6:].rstrip(':')
                pseudo.append(pad + 'WHILE ' + cond)
            elif stripped.startswith('return '):
                pseudo.append(pad + 'RETURN ' + stripped[7:])
            elif stripped.startswith('print('):
                pseudo.append(pad + 'PRINT ' + stripped[6:-1])
            elif '=' in stripped and not stripped.startswith('=='):
                parts = stripped.split('=', 1)
                pseudo.append(pad + 'SET ' + parts[0].strip() + ' TO ' + parts[1].strip())
            elif stripped.startswith('import '):
                pseudo.append(pad + 'USE library ' + stripped[7:])
            else:
                pseudo.append(pad + stripped)
        return {'success': True, 'data': '\n'.join(pseudo), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def javascript_to_python_basics(code: str) -> dict:
    """Basic transpile JS patterns to Python equivalents."""
    try:
        result = code
        result = re.sub(r'\bconst\b', '', result)
        result = re.sub(r'\blet\b', '', result)
        result = re.sub(r'\bvar\b', '', result)
        result = re.sub(r';\s*$', '', result, flags=re.MULTILINE)
        result = re.sub(r'console\.log\(', 'print(', result)
        result = re.sub(r'===', '==', result)
        result = re.sub(r'!==', '!=', result)
        result = re.sub(r'\s*\{\s*$', ':', result, flags=re.MULTILINE)
        result = re.sub(r'^\s*\}\s*$', '', result, flags=re.MULTILINE)
        result = re.sub(r'function (\w+)\(([^)]*)\):', r'def \1(\2):', result)
        result = re.sub(r'\|\ \|', 'or', result)
        result = re.sub(r'&&', 'and', result)
        result = re.sub(r'!(?!=)', 'not ', result)
        result = re.sub(r'//.*$', '# \g<0>', result, flags=re.MULTILINE)
        result = re.sub(r'true\b', 'True', result)
        result = re.sub(r'false\b', 'False', result)
        result = re.sub(r'null\b', 'None', result)
        result = re.sub(r'undefined\b', 'None', result)
        return {'success': True, 'data': result, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def python_to_javascript_basics(code: str) -> dict:
    """Basic transpile Python patterns to JS."""
    try:
        result = code
        result = re.sub(r'\bTrue\b', 'true', result)
        result = re.sub(r'\bFalse\b', 'false', result)
        result = re.sub(r'\bNone\b', 'null', result)
        result = re.sub(r'\bprint\(', 'console.log(', result)
        result = re.sub(r'\band\b', '&&', result)
        result = re.sub(r'\bor\b', '||', result)
        result = re.sub(r'\bnot\b', '!', result)
        result = re.sub(r'^(\s*)def (\w+)\(([^)]*)\):\s*$', r'\1function \2(\3) {', result, flags=re.MULTILINE)
        result = re.sub(r'^(\s*)class (\w+).*:\s*$', r'\1class \2 {', result, flags=re.MULTILINE)
        result = re.sub(r'^(\s*)if (.+):\s*$', r'\1if (\2) {', result, flags=re.MULTILINE)
        result = re.sub(r'^(\s*)elif (.+):\s*$', r'\1} else if (\2) {', result, flags=re.MULTILINE)
        result = re.sub(r'^(\s*)else:\s*$', r'\1} else {', result, flags=re.MULTILINE)
        result = re.sub(r'^(\s*)for (\w+) in range\((\d+)\):\s*$', r'\1for (let \2 = 0; \2 < \3; \2++) {', result, flags=re.MULTILINE)
        result = re.sub(r'^(\s*)while (.+):\s*$', r'\1while (\2) {', result, flags=re.MULTILINE)
        result = re.sub(r'#(.*)$', r'//\1', result, flags=re.MULTILINE)
        return {'success': True, 'data': result, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def python_to_lua(code: str) -> dict:
    """Basic Python to Lua conversion."""
    try:
        result = code
        result = re.sub(r'\bTrue\b', 'true', result)
        result = re.sub(r'\bFalse\b', 'false', result)
        result = re.sub(r'\bNone\b', 'nil', result)
        result = re.sub(r'\bprint\((.+)\)', r'print(\1)', result)
        result = re.sub(r'\band\b', 'and', result)
        result = re.sub(r'\bor\b', 'or', result)
        result = re.sub(r'\bnot\b', 'not', result)
        result = re.sub(r'^(\s*)def (\w+)\(([^)]*)\):\s*$', r'\1function \2(\3)', result, flags=re.MULTILINE)
        result = re.sub(r'^(\s*)if (.+):\s*$', r'\1if \2 then', result, flags=re.MULTILINE)
        result = re.sub(r'^(\s*)elif (.+):\s*$', r'\1elseif \2 then', result, flags=re.MULTILINE)
        result = re.sub(r'^(\s*)else:\s*$', r'\1else', result, flags=re.MULTILINE)
        result = re.sub(r'^(\s*)for (\w+) in range\((\d+)\):\s*$', r'\1for \2 = 0, \3-1 do', result, flags=re.MULTILINE)
        result = re.sub(r'^(\s*)while (.+):\s*$', r'\1while \2 do', result, flags=re.MULTILINE)
        result = re.sub(r'^(\s*)return ', r'\1return ', result, flags=re.MULTILINE)
        result = re.sub(r'#(.*)$', r'--\1', result, flags=re.MULTILINE)
        return {'success': True, 'data': result, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def json_to_python_dataclass(json_str: str, class_name: str = 'MyModel') -> dict:
    """Convert a JSON object to a Python dataclass."""
    try:
        data = json.loads(json_str)
        if not isinstance(data, dict):
            return {'success': False, 'data': None, 'error': 'JSON must be an object'}
        type_map = {int: 'int', float: 'float', str: 'str', bool: 'bool', list: 'list', dict: 'dict', type(None): 'Optional[Any]'}
        lines = ['from dataclasses import dataclass', 'from typing import Optional, Any', '', '@dataclass', 'class ' + class_name + ':']
        for key, val in data.items():
            t = type_map.get(type(val), 'Any')
            default = repr(val) if not isinstance(val, (dict, list)) else 'None'
            lines.append('    ' + key + ': ' + t + ' = ' + default)
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def json_to_typescript_interface(json_str: str, interface_name: str = 'MyInterface') -> dict:
    """Convert a JSON object to a TypeScript interface."""
    try:
        data = json.loads(json_str)
        if not isinstance(data, dict):
            return {'success': False, 'data': None, 'error': 'JSON must be an object'}
        type_map = {int: 'number', float: 'number', str: 'string', bool: 'boolean', list: 'any[]', dict: 'Record<string, any>', type(None): 'null | undefined'}
        lines = ['interface ' + interface_name + ' {']
        for key, val in data.items():
            t = type_map.get(type(val), 'any')
            lines.append('  ' + key + ': ' + t + ';')
        lines.append('}')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def json_to_go_struct(json_str: str, struct_name: str = 'MyStruct') -> dict:
    """Convert JSON object to Go struct with json tags."""
    try:
        data = json.loads(json_str)
        if not isinstance(data, dict):
            return {'success': False, 'data': None, 'error': 'JSON must be an object'}
        type_map = {int: 'int', float: 'float64', str: 'string', bool: 'bool', list: '[]interface{}', dict: 'map[string]interface{}', type(None): 'interface{}'}
        lines = ['type ' + struct_name + ' struct {']
        for key, val in data.items():
            t = type_map.get(type(val), 'interface{}')
            field_name = key.capitalize()
            lines.append('\t' + field_name + ' ' + t + ' `json:"' + key + '"`')
        lines.append('}')
        return {'success': True, 'data': '\n'.join(lines), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def csv_to_json(csv_text: str, delimiter: str = ',') -> dict:
    """Convert CSV text to JSON array."""
    try:
        import csv, io
        reader = csv.DictReader(io.StringIO(csv_text), delimiter=delimiter)
        rows = list(reader)
        return {'success': True, 'data': rows, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def json_to_csv(json_str: str) -> dict:
    """Convert JSON array to CSV text."""
    try:
        import csv, io
        data = json.loads(json_str)
        if not isinstance(data, list) or not data:
            return {'success': False, 'data': None, 'error': 'JSON must be a non-empty array'}
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        return {'success': True, 'data': output.getvalue(), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def xml_to_json(xml_text: str) -> dict:
    """Convert XML to JSON dict."""
    try:
        import xml.etree.ElementTree as ET
        def _elem_to_dict(elem):
            d = {}
            for child in elem:
                val = _elem_to_dict(child) if len(child) else child.text
                if child.tag in d:
                    if not isinstance(d[child.tag], list):
                        d[child.tag] = [d[child.tag]]
                    d[child.tag].append(val)
                else:
                    d[child.tag] = val
            if elem.attrib:
                d['@attributes'] = elem.attrib
            if not d and elem.text:
                return elem.text
            return d
        root = ET.fromstring(xml_text)
        return {'success': True, 'data': {root.tag: _elem_to_dict(root)}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
