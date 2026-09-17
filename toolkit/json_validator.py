import json
import jsonschema
from pathlib import Path
import os
import re
import copy
import difflib
from collections import OrderedDict
import io
from typing import Any, Dict, List, Union, Optional
import csv
import xml.etree.ElementTree as ET


def _resolve_json_pointer(data: Any, pointer: str) -> Any:
    """Resolve a JSON Pointer string (e.g., '/root/list/0/key') against data."""
    if not pointer:
        return data
    if pointer[0] != '/':
        pointer = '/' + pointer
    parts = pointer.split('/')[1:]
    current = data
    for part in parts:
        part = part.replace('~1', '/').replace('~0', '~')  # Unescape JSON Pointer
        if isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                raise KeyError(f"Key '{part}' not found in path")
        elif isinstance(current, list):
            try:
                idx = int(part)
                current = current[idx]
            except (ValueError, IndexError) as e:
                raise IndexError(f"Invalid list index '{part}': {e}")
        else:
            raise TypeError(f"Cannot traverse into non-container type {type(current).__name__} at '{part}'")
    return current


def _set_by_pointer(data: Any, pointer: str, value: Any) -> None:
    """Set a value in a nested structure using a JSON Pointer."""
    if pointer == '' or pointer == '/':
        raise ValueError("Cannot replace root object with patch")
    if pointer[0] != '/':
        pointer = '/' + pointer
    parts = pointer.split('/')[1:]
    parent = _resolve_json_pointer(data, '/' + '/'.join(parts[:-1]))
    key = parts[-1].replace('~1', '/').replace('~0', '~')
    if isinstance(parent, dict):
        parent[key] = value
    elif isinstance(parent, list):
        if key == '-':
            parent.append(value)
        else:
            parent[int(key)] = value
    else:
        raise TypeError("Cannot set value on non-container type")


def validate_json(data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    try:
        jsonschema.validate(instance=data, schema=schema)
        return {"status": "success", "valid": True, "message": "Data matches schema."}
    except jsonschema.ValidationError as e:
        return {"status": "error", "valid": False, "message": f"Validation failed: {e.message}", "path": list(e.path)}
    except Exception as e:
        return {"status": "error", "valid": False, "message": f"Unexpected error during validation: {str(e)}"}


def load_json(filepath: Union[str, Path]) -> Dict[str, Any]:
    try:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        content = path.read_text(encoding="utf-8")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Root JSON element is not an object/dict.")
        return {"status": "success", "data": parsed, "file": str(path)}
    except Exception as e:
        return {"status": "error", "data": None, "message": str(e)}


def save_json(data: Dict[str, Any], filepath: Union[str, Path], indent: int = 4) -> Dict[str, Any]:
    try:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(data, indent=indent, ensure_ascii=False)
        path.write_text(content, encoding="utf-8")
        return {"status": "success", "message": f"Saved to {path}", "bytes_written": len(content.encode("utf-8")), "path": str(path)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def parse_json_string(text: str) -> Dict[str, Any]:
    try:
        obj = json.loads(text.strip())
        if isinstance(obj, dict):
            return {"status": "success", "data": obj}
        return {"status": "success", "data": {"root": obj}, "note": "Wrapped non-dict root in 'root' key to satisfy Dict return type."}
    except json.JSONDecodeError as e:
        return {"status": "error", "data": None, "message": f"Invalid JSON string: {str(e)}"}
    except Exception as e:
        return {"status": "error", "data": None, "message": str(e)}


def merge_json(base: Dict[str, Any], overlay: Dict[str, Any], deep: bool = True) -> Dict[str, Any]:
    try:
        result = copy.deepcopy(base)
        if not deep:
            result.update(overlay)
        else:
            def deep_merge(d1: dict, d2: dict) -> None:
                for k, v in d2.items():
                    if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
                        deep_merge(d1[k], v)
                    else:
                        d1[k] = copy.deepcopy(v)
            deep_merge(result, overlay)
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "data": None, "message": str(e)}


def diff_json(json1: Dict[str, Any], json2: Dict[str, Any]) -> Dict[str, Any]:
    try:
        s1 = json.dumps(json1, sort_keys=True, indent=2).splitlines()
        s2 = json.dumps(json2, sort_keys=True, indent=2).splitlines()
        diff = list(difflib.unified_diff(s1, s2, fromfile="json1", tofile="json2", lineterm=""))
        has_changes = len(diff) > 0
        return {"status": "success", "identical": not has_changes, "diff_lines": diff}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def flatten_json(data: Dict[str, Any], separator: str = ".") -> Dict[str, Any]:
    try:
        def _flatten(d: Any, parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
            items = {}
            if isinstance(d, dict):
                for k, v in d.items():
                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                    if isinstance(v, dict):
                        items.update(_flatten(v, new_key, sep))
                    else:
                        items[new_key] = v
            else:
                items[parent_key] = d if parent_key else d
            return items

        flat = _flatten(data, "", separator)
        return {"status": "success", "data": flat}
    except Exception as e:
        return {"status": "error", "data": None, "message": str(e)}


def unflatten_json(data: Dict[str, Any], separator: str = ".") -> Dict[str, Any]:
    try:
        unflat = {}
        for key, value in data.items():
            parts = key.split(separator)
            target = unflat
            for p in parts[:-1]:
                if p not in target or not isinstance(target[p], dict):
                    target[p] = {}
                target = target[p]
            target[parts[-1]] = value
        return {"status": "success", "data": unflat}
    except Exception as e:
        return {"status": "error", "data": None, "message": str(e)}


def query_json(data: Dict[str, Any], jsonpath: str) -> Dict[str, Any]:
    try:
        path = jsonpath.strip()
        if path.startswith("$"):
            path = path[1:]
        if not path:
            return {"status": "success", "matches": [data]}
        
        tokens = re.split(r"(?:\[|\])", path.replace(".", ".["))
        tokens = [t.strip() for t in tokens if t]
        
        current = [data]
        for token in tokens:
            new_current = []
            if token == "*":
                for item in current:
                    if isinstance(item, (list, dict)):
                        new_current.extend(item.values() if isinstance(item, dict) else item)
                current = new_current
                continue
            
            is_list_idx = token.isdigit() or token.lstrip("-").isdigit()
            
            for item in current:
                if isinstance(item, dict):
                    if token in item:
                        new_current.append(item[token])
                elif isinstance(item, list) and is_list_idx:
                    idx = int(token)
                    if -len(item) <= idx < len(item):
                        new_current.append(item[idx])
            current = new_current
        
        return {"status": "success", "matches": current}
    except Exception as e:
        return {"status": "error", "matches": [], "message": str(e)}


def transform_json(data: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    try:
        result = {}
        for new_key, path_expr in mapping.items():
            matches = query_json(data, path_expr).get("matches", [])
            result[new_key] = matches[0] if len(matches) == 1 else matches
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "data": None, "message": str(e)}


def filter_json_keys(data: Dict[str, Any], keys: List[str], include: bool = True) -> Dict[str, Any]:
    try:
        def _filter(d: Any) -> Any:
            if isinstance(d, dict):
                res = {}
                for k, v in d.items():
                    if include and k in keys:
                        res[k] = _filter(v)
                    elif not include and k not in keys:
                        res[k] = _filter(v)
                return res
            return d
        return {"status": "success", "data": _filter(data)}
    except Exception as e:
        return {"status": "error", "data": None, "message": str(e)}


def sort_json_keys(data: Dict[str, Any], recursive: bool = True) -> Dict[str, Any]:
    try:
        sorted_d = collections.OrderedDict()
        if recursive:
            def _sort(d: Any) -> Any:
                if isinstance(d, dict):
                    return collections.OrderedDict((k, _sort(v)) for k, v in sorted(d.items()))
                elif isinstance(d, list):
                    return [_sort(x) for x in d]
                return d
            sorted_d = _sort(data)
        else:
            sorted_d = collections.OrderedDict((k, v) for k, v in sorted(data.items()))
        return {"status": "success", "data": sorted_d}
    except Exception as e:
        return {"status": "error", "data": None, "message": str(e)}


def json_to_xml(data: Dict[str, Any], root_tag: str = "root") -> Dict[str, Any]:
    try:
        def _build_xml(d: Any, tag: str, parent: ET.Element) -> None:
            if isinstance(d, dict):
                el = ET.SubElement(parent, tag)
                for k, v in d.items():
                    if isinstance(v, list):
                        for item in v:
                            child = ET.SubElement(el, k)
                            if isinstance(item, dict):
                                _build_xml(item, k, child)
                            else:
                                child.text = str(item) if item is not None else ""
                    else:
                        child = ET.SubElement(el, k)
                        if isinstance(v, dict):
                            _build_xml(v, k, child)
                        else:
                            child.text = str(v) if v is not None else ""
            else:
                el = ET.SubElement(parent, tag)
                el.text = str(d) if d is not None else ""

        root = ET.Element(root_tag)
        _build_xml(data, root_tag, root)
        xml_str = ET.tostring(root, encoding="unicode", method="xml")
        return {"status": "success", "xml": xml_str}
    except Exception as e:
        return {"status": "error", "xml": None, "message": str(e)}


def xml_to_json(xml_string: str) -> Dict[str, Any]:
    try:
        root = ET.fromstring(xml_string.strip())
        def _xml_to_dict(el: ET.Element) -> Any:
            children = list(el)
            if not children:
                text = el.text
                if text and re.match(r"^-?\d+$", text):
                    return int(text)
                if text and re.match(r"^-?\d+\.\d+$", text):
                    return float(text)
                return text or None
            is_list = len(set(c.tag for c in children)) == 1
            result = {} if not is_list else []
            for child in children:
                val = _xml_to_dict(child)
                if is_list:
                    result.append(val)
                else:
                    result.setdefault(child.tag, []).append(val)
            if not is_list:
                for k in result:
                    if len(result[k]) == 1:
                        result[k] = result[k][0]
            return result
        
        json_obj = _xml_to_dict(root)
        return {"status": "success", "data": json_obj}
    except ET.ParseError as e:
        return {"status": "error", "data": None, "message": f"XML parse error: {str(e)}"}
    except Exception as e:
        return {"status": "error", "data": None, "message": str(e)}


def json_to_csv(data: Union[Dict[str, Any], List[Dict[str, Any]]], output: Optional[str] = None) -> Dict[str, Any]:
    try:
        records = data if isinstance(data, list) else [data]
        if not records:
            return {"status": "error", "message": "Empty data provided."}
        
        headers = []
        seen = set()
        for r in records:
            if isinstance(r, dict):
                for k in r.keys():
                    if k not in seen:
                        headers.append(k)
                        seen.add(k)
        
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            if isinstance(r, dict):
                writer.writerow({k: str(v) if not isinstance(v, str) else v for k, v in r.items()})
        csv_str = buf.getvalue()
        
        saved_path = None
        if output:
            Path(output).write_text(csv_str, encoding="utf-8")
            saved_path = output
        
        return {"status": "success", "csv": csv_str, "rows": len(records), "columns": len(headers), "saved_to": saved_path}
    except Exception as e:
        return {"status": "error", "csv": None, "message": str(e)}


def csv_to_json(filepath: Union[str, Path]) -> Dict[str, Any]:
    try:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            records = list(reader)
        
        for row in records:
            for k, v in row.items():
                if v is None:
                    continue
                if v.isdigit():
                    row[k] = int(v)
                elif re.match(r"^-?\d+\.\d+$", v):
                    row[k] = float(v)
                elif v.lower() in ("true", "false"):
                    row[k] = v.lower() == "true"
        
        return {"status": "success", "data": records, "total_records": len(records)}
    except Exception as e:
        return {"status": "error", "data": [], "message": str(e)}


def validate_json_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    try:
        jsonschema.Draft7Validator.check_schema(schema)
        return {"status": "success", "valid": True, "message": "Schema structure is valid."}
    except jsonschema.exceptions.SchemaError as e:
        return {"status": "error", "valid": False, "message": f"Invalid schema: {str(e)}", "path": list(e.path)}
    except Exception as e:
        return {"status": "error", "valid": False, "message": f"Schema validation error: {str(e)}"}


def create_json_schema(sample_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        def _infer_type(val: Any) -> str:
            if isinstance(val, bool): return "boolean"
            if isinstance(val, int): return "integer"
            if isinstance(val, float): return "number"
            if isinstance(val, str): return "string"
            if isinstance(val, list): return "array"
            if isinstance(val, dict): return "object"
            return "null"

        def _build_schema(obj: Any) -> Dict[str, Any]:
            schema_type = _infer_type(obj)
            schema: Dict[str, Any] = {"type": schema_type}
            if isinstance(obj, dict):
                schema["properties"] = {k: _build_schema(v) for k, v in obj.items()}
                schema["required"] = list(obj.keys())
            elif isinstance(obj, list) and obj:
                schema["items"] = _build_schema(obj[0])
            return schema

        return {"status": "success", "schema": _build_schema(sample_data)}
    except Exception as e:
        return {"status": "error", "schema": None, "message": str(e)}


def minify_json(data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        compact = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        return {"status": "success", "minified": compact, "original_size": len(json.dumps(data)), "compressed_size": len(compact)}
    except Exception as e:
        return {"status": "error", "minified": None, "message": str(e)}


def prettify_json(data: Dict[str, Any], indent: int = 4) -> Dict[str, Any]:
    try:
        pretty = json.dumps(data, indent=indent, ensure_ascii=False)
        return {"status": "success", "prettified": pretty}
    except Exception as e:
        return {"status": "error", "prettified": None, "message": str(e)}


def json_patch(data: Dict[str, Any], operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        working = copy.deepcopy(data)
        for op_idx, op in enumerate(operations):
            op_type = op.get("op")
            path = op.get("path", "")
            if not path.startswith("/"):
                path = "/" + path
            
            if op_type == "add":
                _set_by_pointer(working, path, op.get("value"))
            elif op_type == "remove":
                _set_by_pointer(working, path, json.JSONDecoder().decode("null"))
                parent_ptr = "/".join(path.split("/")[:-1]) or "/"
                key = path.split("/")[-1]
                parent = _resolve_json_pointer(working, parent_ptr)
                if isinstance(parent, dict):
                    del parent[key]
                elif isinstance(parent, list):
                    del parent[int(key)]
            elif op_type == "replace":
                _resolve_json_pointer(working, path)  # verify exists
                _set_by_pointer(working, path, op.get("value"))
            elif op_type == "move":
                val = copy.deepcopy(_resolve_json_pointer(working, path))
                _set_by_pointer(working, path, None)
                parent_ptrs = path.split("/")
                parent = _resolve_json_pointer(working, "/".join(parent_ptrs[:-1]) or "/")
                if isinstance(parent, dict):
                    del parent[parent_ptrs[-1]]
                else:
                    del parent[int(parent_ptrs[-1])]
                _set_by_pointer(working, op.get("to"), val)
            elif op_type == "copy":
                val = copy.deepcopy(_resolve_json_pointer(working, path))
                _set_by_pointer(working, op.get("to"), val)
            elif op_type == "test":
                current = _resolve_json_pointer(working, path)
                if current != op.get("value"):
                    raise ValueError(f"Test failed at {path}: expected {op.get('value')}, got {current}")
            else:
                raise ValueError(f"Unsupported operation: {op_type}")
        
        return {"status": "success", "data": working, "operations_applied": len(operations)}
    except Exception as e:
        return {"status": "error", "data": copy.deepcopy(data), "message": f"Patch failed at operation: {str(e)}"}


def compare_json_structures(json1: Dict[str, Any], json2: Dict[str, Any]) -> Dict[str, Any]:
    try:
        diffs: List[Dict[str, str]] = []
        def _compare(d1: Any, d2: Any, path: str) -> None:
            t1, t2 = type(d1).__name__, type(d2).__name__
            if t1 != t2:
                diffs.append({"path": path or "/", "type1": t1, "type2": t2})
                return
            if isinstance(d1, dict):
                keys1, keys2 = set(d1.keys()), set(d2.keys())
                for k in keys1 - keys2:
                    diffs.append({"path": f"{path}/{k}" if path else k, "issue": "missing_in_second"})
                for k in keys2 - keys1:
                    diffs.append({"path": f"{path}/{k}" if path else k, "issue": "missing_in_first"})
                for k in keys1 & keys2:
                    _compare(d1[k], d2[k], f"{path}/{k}" if path else k)
            elif isinstance(d1, list):
                if len(d1) != len(d2):
                    diffs.append({"path": path or "/", "issue": f"list_length_difference ({len(d1)} vs {len(d2)})"})
                min_len = min(len(d1), len(d2))
                for i in range(min_len):
                    _compare(d1[i], d2[i], f"{path}/[{i}]")
        
        _compare(json1, json2, "")
        return {"status": "success", "structural_match": len(diffs) == 0, "differences": diffs}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def batch_validate(data_list: List[Dict[str, Any]], schema: Dict[str, Any]) -> Dict[str, Any]:
    try:
        results = []
        valid_count = invalid_count = 0
        for idx, item in enumerate(data_list):
            v = validate_json(item, schema)
            if v.get("valid"):
                valid_count += 1
            else:
                invalid_count += 1
            results.append({"index": idx, "valid": v.get("valid", False), "message": v.get("message", "")})
        
        return {"status": "success", "total": len(data_list), "valid": valid_count, "invalid": invalid_count, "details": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def deep_get(data: Dict[str, Any], path: str, default: Any = None) -> Dict[str, Any]:
    try:
        keys = path.replace("/", ".").split(".")
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return {"status": "success", "value": default, "found": False, "path": path}
        return {"status": "success", "value": current, "found": True, "path": path}
    except Exception as e:
        return {"status": "error", "value": default, "message": str(e)}


def deep_set(data: Dict[str, Any], path: str, value: Any) -> Dict[str, Any]:
    try:
        target = copy.deepcopy(data)
        keys = path.replace("/", ".").split(".")
        current = target
        for i, key in enumerate(keys[:-1]):
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
        return {"status": "success", "data": target, "updated_path": path}
    except Exception as e:
        return {"status": "error", "data": data, "message": str(e)}