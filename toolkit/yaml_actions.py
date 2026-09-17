import yaml
import json
import os
import re
import copy
import io
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

def _error(msg: str) -> Dict[str, Any]:
    return {"status": "error", "error": msg}

def _success(data: Any = None) -> Dict[str, Any]:
    return {"status": "success", "data": data}

def read_yaml(file_path: Union[str, Path]) -> Dict[str, Any]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return _success(data if data is not None else {})
    except Exception as e:
        return _error(f"Failed to read YAML: {str(e)}")

def write_yaml(data: Dict[str, Any], file_path: Union[str, Path]) -> Dict[str, Any]:
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        return _success({"file": str(file_path), "action": "written"})
    except Exception as e:
        return _error(f"Failed to write YAML: {str(e)}")

def validate_yaml(yaml_string_or_path: str) -> Dict[str, Any]:
    try:
        if os.path.exists(yaml_string_or_path):
            with open(yaml_string_or_path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)
        else:
            yaml.safe_load(yaml_string_or_path)
        return _success({"valid": True})
    except Exception as e:
        return _error(f"Invalid YAML: {str(e)}")

def merge_yaml_files(file1: str, file2: str, output_path: str) -> Dict[str, Any]:
    try:
        d1 = read_yaml(file1).get("data", {})
        d2 = read_yaml(file2).get("data", {})
        merged = copy.deepcopy(d1)
        merged.update(d2)
        write_yaml(merged, output_path)
        return _success(merged)
    except Exception as e:
        return _error(str(e))

def yaml_to_json(yaml_path: str, json_path: str = "") -> Dict[str, Any]:
    try:
        data = read_yaml(yaml_path).get("data", {})
        if json_path:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        return _success({"json_string": json.dumps(data), "saved_to": json_path})
    except Exception as e:
        return _error(str(e))

def json_to_yaml(json_path: str, yaml_path: str = "") -> Dict[str, Any]:
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if yaml_path:
            write_yaml(data, yaml_path)
        return _success({"yaml_string": yaml.safe_dump(data), "saved_to": yaml_path})
    except Exception as e:
        return _error(str(e))

def get_nested_value(data: Dict[str, Any], path: str) -> Dict[str, Any]:
    keys = path.split('.')
    current = data
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return _error(f"Key path '{path}' not found.")
    return _success(current)

def set_nested_value(data: Dict[str, Any], path: str, value: Any) -> Dict[str, Any]:
    try:
        keys = path.split('.')
        current = data
        for k in keys[:-1]:
            current = current.setdefault(k, {})
        current[keys[-1]] = value
        return _success(data)
    except Exception as e:
        return _error(str(e))

def delete_key(data: Dict[str, Any], path: str) -> Dict[str, Any]:
    try:
        keys = path.split('.')
        current = data
        for k in keys[:-1]:
            if k not in current:
                return _error(f"Key path '{path}' not found.")
            current = current[k]
        if keys[-1] in current:
            del current[keys[-1]]
            return _success(data)
        return _error(f"Key '{keys[-1]}' not found.")
    except Exception as e:
        return _error(str(e))

def list_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    def _extract_keys(d, prefix=''):
        keys = []
        for k, v in d.items():
            full_key = f"{prefix}.{k}" if prefix else k
            keys.append(full_key)
            if isinstance(v, dict):
                keys.extend(_extract_keys(v, full_key))
        return keys
    return _success(_extract_keys(data))

def flatten_yaml(data: Dict[str, Any]) -> Dict[str, Any]:
    flat = {}
    def _flatten(d, parent_key=''):
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                _flatten(v, new_key)
            else:
                flat[new_key] = v
    _flatten(data)
    return _success(flat)

def unflatten_yaml(data: Dict[str, Any]) -> Dict[str, Any]:
    unflattened = {}
    for k, v in data.items():
        set_nested_value(unflattened, k, v)
    return _success(unflattened)

def diff_yaml_files(file1: str, file2: str) -> Dict[str, Any]:
    d1 = flatten_yaml(read_yaml(file1).get("data", {})).get("data", {})
    d2 = flatten_yaml(read_yaml(file2).get("data", {})).get("data", {})
    added = {k: d2[k] for k in set(d2) - set(d1)}
    removed = {k: d1[k] for k in set(d1) - set(d2)}
    changed = {k: {"old": d1[k], "new": d2[k]} for k in set(d1) & set(d2) if d1[k] != d2[k]}
    return _success({"added": added, "removed": removed, "changed": changed})

def patch_yaml(original: str, patch_data: Dict[str, Any], output_path: str) -> Dict[str, Any]:
    try:
        orig_data = read_yaml(original).get("data", {})
        flat_patch = flatten_yaml(patch_data).get("data", {})
        for k, v in flat_patch.items():
            set_nested_value(orig_data, k, v)
        write_yaml(orig_data, output_path)
        return _success(orig_data)
    except Exception as e:
        return _error(str(e))

def create_yaml_template(keys: list, output_path: str) -> Dict[str, Any]:
    try:
        template = {}
        for k in keys:
            set_nested_value(template, k, None)
        write_yaml(template, output_path)
        return _success(template)
    except Exception as e:
        return _error(str(e))

def validate_against_schema(yaml_path: str, schema_path: str) -> Dict[str, Any]:
    try:
        data = flatten_yaml(read_yaml(yaml_path).get("data", {})).get("data", {})
        schema = flatten_yaml(read_yaml(schema_path).get("data", {})).get("data", {})
        missing = [k for k in schema if k not in data]
        return _success({"valid": len(missing) == 0, "missing_keys": missing})
    except Exception as e:
        return _error(str(e))

def sort_yaml_keys(yaml_path: str, output_path: str) -> Dict[str, Any]:
    try:
        data = read_yaml(yaml_path).get("data", {})
        sorted_data = dict(sorted(data.items()))
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(sorted_data, f, default_flow_style=False, sort_keys=True)
        return _success({"sorted": True, "file": output_path})
    except Exception as e:
        return _error(str(e))

def remove_comments(yaml_string: str) -> Dict[str, Any]:
    try:
        clean = re.sub(r'(?m)^ *#.*\n?', '', yaml_string)
        clean = re.sub(r' +#.*$', '', clean, flags=re.MULTILINE)
        return _success(clean.strip())
    except Exception as e:
        return _error(str(e))

def add_comment(yaml_string: str, key: str, comment: str) -> Dict[str, Any]:
    try:
        pattern = re.compile(rf'^({key}:.*)', re.MULTILINE)
        if pattern.search(yaml_string):
            modified = pattern.sub(rf'\1 # {comment}', yaml_string)
            return _success(modified)
        return _error("Key not found at root level.")
    except Exception as e:
        return _error(str(e))

def find_value(data: Dict[str, Any], target_value: Any) -> Dict[str, Any]:
    matches = []
    flat = flatten_yaml(data).get("data", {})
    for k, v in flat.items():
        if v == target_value:
            matches.append(k)
    return _success(matches)

def replace_value(data: Dict[str, Any], old_value: Any, new_value: Any) -> Dict[str, Any]:
    try:
        d = copy.deepcopy(data)
        flat = flatten_yaml(d).get("data", {})
        for k, v in flat.items():
            if v == old_value:
                set_nested_value(d, k, new_value)
        return _success(d)
    except Exception as e:
        return _error(str(e))

def split_yaml_document(yaml_path: str, output_dir: str) -> Dict[str, Any]:
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(yaml_path, 'r', encoding='utf-8') as f:
            docs = list(yaml.safe_load_all(f))
        saved = []
        for i, doc in enumerate(docs):
            if doc:
                p = os.path.join(output_dir, f"doc_{i}.yaml")
                write_yaml(doc, p)
                saved.append(p)
        return _success({"documents": len(saved), "files": saved})
    except Exception as e:
        return _error(str(e))

def merge_yaml_documents(yaml_paths: list, output_path: str) -> Dict[str, Any]:
    try:
        docs = [read_yaml(p).get("data", {}) for p in yaml_paths]
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump_all(docs, f)
        return _success({"merged": len(docs), "output": output_path})
    except Exception as e:
        return _error(str(e))

def convert_yaml_to_env(yaml_path: str, env_path: str) -> Dict[str, Any]:
    try:
        flat = flatten_yaml(read_yaml(yaml_path).get("data", {})).get("data", {})
        env_lines = []
        for k, v in flat.items():
            env_key = k.replace('.', '_').upper()
            env_lines.append(f"{env_key}={v}")
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(env_lines))
        return _success({"file": env_path, "vars": len(env_lines)})
    except Exception as e:
        return _error(str(e))

def export_yaml_to_toml(yaml_path: str, toml_path: str) -> Dict[str, Any]:
    try:
        data = read_yaml(yaml_path).get("data", {})
        lines = []
        for k, v in data.items():
            if isinstance(v, dict):
                lines.append(f"\n[{k}]")
                for sub_k, sub_v in v.items():
                    val = f'"{sub_v}"' if isinstance(sub_v, str) else str(sub_v).lower() if isinstance(sub_v, bool) else sub_v
                    lines.append(f"{sub_k} = {val}")
            else:
                val = f'"{v}"' if isinstance(v, str) else str(v).lower() if isinstance(v, bool) else v
                lines.append(f"{k} = {val}")
        
        with open(toml_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        return _success({"file": toml_path})
    except Exception as e:
        return _error(str(e))
