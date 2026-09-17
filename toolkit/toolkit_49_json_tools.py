"""
toolkit_49_json_tools.py
Advanced JSON utilities: deep merge, diff, flatten, schema inference,
path queries, pretty-print, repair, and validation. Stdlib only.
"""
from __future__ import annotations
import json
import re
import copy
from typing import Any, Dict, List

def pretty_print_json(data: dict, indent: int = 2) -> Dict[str, Any]:
    try:
        return {"success": True, "data": json.dumps(data, indent=indent, ensure_ascii=False, default=str), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def parse_json_string(json_str: str) -> Dict[str, Any]:
    try:
        data = json.loads(json_str)
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def load_json_file(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def save_json_file(data: dict, path: str, indent: int = 2) -> Dict[str, Any]:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
        return {"success": True, "data": {"saved": path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def deep_merge(base: dict, override: dict) -> Dict[str, Any]:
    """Recursively merge override into base."""
    try:
        result = copy.deepcopy(base)
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = deep_merge(result[k], v)["data"]
            else:
                result[k] = copy.deepcopy(v)
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def json_diff(a: dict, b: dict, path: str = "") -> Dict[str, Any]:
    """Find differences between two JSON objects."""
    try:
        diffs = []
        all_keys = set(a.keys()) | set(b.keys())
        for k in all_keys:
            full_path = path + "." + k if path else k
            if k not in a:
                diffs.append({"path": full_path, "type": "added", "value": b[k]})
            elif k not in b:
                diffs.append({"path": full_path, "type": "removed", "value": a[k]})
            elif isinstance(a[k], dict) and isinstance(b[k], dict):
                sub = json_diff(a[k], b[k], full_path)
                diffs.extend(sub["data"])
            elif a[k] != b[k]:
                diffs.append({"path": full_path, "type": "changed", "from": a[k], "to": b[k]})
        return {"success": True, "data": diffs, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def flatten_json(data: dict, separator: str = ".", prefix: str = "") -> Dict[str, Any]:
    try:
        flat: dict = {}
        for k, v in data.items():
            new_key = prefix + separator + str(k) if prefix else str(k)
            if isinstance(v, dict):
                sub = flatten_json(v, separator, new_key)
                flat.update(sub["data"])
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    if isinstance(item, dict):
                        sub = flatten_json(item, separator, new_key + "[" + str(i) + "]")
                        flat.update(sub["data"])
                    else:
                        flat[new_key + "[" + str(i) + "]"] = item
            else:
                flat[new_key] = v
        return {"success": True, "data": flat, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_json_path(data: dict, path: str) -> Dict[str, Any]:
    """Access nested value with dot notation like 'a.b.c'."""
    try:
        keys = path.split(".")
        current = data
        for k in keys:
            if isinstance(current, list):
                current = current[int(k)]
            elif isinstance(current, dict):
                current = current[k]
            else:
                return {"success": False, "data": None, "error": "Path not found: " + path}
        return {"success": True, "data": current, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_json_path(data: dict, path: str, value: Any) -> Dict[str, Any]:
    """Set a nested value with dot notation."""
    try:
        result = copy.deepcopy(data)
        keys = path.split(".")
        current = result
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def infer_schema(data: dict, path: str = "") -> Dict[str, Any]:
    """Infer a simple schema from a JSON object."""
    try:
        def _infer(val, p=""):
            t = type(val).__name__
            if isinstance(val, dict):
                return {"type": "object", "properties": {k: _infer(v, p + "." + k) for k, v in val.items()}}
            elif isinstance(val, list):
                items = _infer(val[0]) if val else {"type": "unknown"}
                return {"type": "array", "items": items, "length": len(val)}
            else:
                return {"type": t}
        schema = _infer(data)
        return {"success": True, "data": schema, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def filter_json_list(records: list, key: str, value: Any) -> Dict[str, Any]:
    try:
        filtered = [r for r in records if isinstance(r, dict) and r.get(key) == value]
        return {"success": True, "data": filtered, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def sort_json_list(records: list, key: str, reverse: bool = False) -> Dict[str, Any]:
    try:
        sorted_list = sorted(records, key=lambda x: x.get(key, ""), reverse=reverse)
        return {"success": True, "data": sorted_list, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def count_keys(data: dict, recursive: bool = True) -> Dict[str, Any]:
    try:
        def _count(d):
            total = len(d)
            if recursive:
                for v in d.values():
                    if isinstance(v, dict):
                        total += _count(v)
            return total
        return {"success": True, "data": _count(data), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_values_by_key(data: dict, target_key: str) -> Dict[str, Any]:
    """Recursively find all values for a given key."""
    try:
        results = []
        def _search(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == target_key:
                        results.append(v)
                    _search(v)
            elif isinstance(obj, list):
                for item in obj:
                    _search(item)
        _search(data)
        return {"success": True, "data": results, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def remove_nulls(data: dict) -> Dict[str, Any]:
    """Remove all null/None values from a dict."""
    try:
        def _clean(obj):
            if isinstance(obj, dict):
                return {k: _clean(v) for k, v in obj.items() if v is not None}
            elif isinstance(obj, list):
                return [_clean(i) for i in obj if i is not None]
            return obj
        return {"success": True, "data": _clean(data), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def json_to_query_string(params: dict) -> Dict[str, Any]:
    try:
        import urllib.parse
        qs = urllib.parse.urlencode(params)
        return {"success": True, "data": qs, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
