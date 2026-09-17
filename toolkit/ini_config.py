import configparser
import json
import os
import re
import io
import shutil
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Type

# ==============================================================================
# Helper Functions
# ==============================================================================

def _get_parser() -> configparser.ConfigParser:
    """Returns a configured ConfigParser that preserves case sensitivity."""
    parser = configparser.ConfigParser()
    parser.optionxform = str  # type: ignore
    return parser

def _ensure_dir(file_path: Union[str, Path]) -> None:
    """Ensures the directory for the given file path exists."""
    path = Path(file_path)
    if path.parent:
        path.parent.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# Core INI Operations
# ==============================================================================

def read_ini(file_path: Union[str, Path]) -> Dict[str, Dict[str, str]]:
    """Reads an INI file and returns it as a dictionary."""
    path = Path(file_path)
    if not path.exists():
        return {}
    
    parser = _get_parser()
    try:
        parser.read(path, encoding='utf-8')
        return {section: dict(parser.items(section)) for section in parser.sections()}
    except configparser.Error as e:
        raise RuntimeError(f"Failed to parse INI file {path}: {e}")

def write_ini(file_path: Union[str, Path], data: Dict[str, Dict[str, str]]) -> None:
    """Writes a dictionary back to an INI file."""
    _ensure_dir(file_path)
    parser = _get_parser()
    
    try:
        for section, keys in data.items():
            parser.add_section(section)
            for key, value in keys.items():
                parser.set(section, key, str(value))
                
        with open(file_path, 'w', encoding='utf-8') as f:
            parser.write(f)
    except Exception as e:
        raise RuntimeError(f"Failed to write INI file {file_path}: {e}")

def get_value(file_path: Union[str, Path], section: str, key: str, fallback: Any = None) -> Optional[str]:
    """Retrieves a specific string value from the INI file."""
    data = read_ini(file_path)
    return data.get(section, {}).get(key, fallback)

def set_value(file_path: Union[str, Path], section: str, key: str, value: str) -> None:
    """Sets a specific value in the INI file, preserving other contents."""
    data = read_ini(file_path)
    if section not in data:
        data[section] = {}
    data[section][key] = str(value)
    write_ini(file_path, data)

def delete_key(file_path: Union[str, Path], section: str, key: str) -> bool:
    """Deletes a key from a section. Returns True if deleted, False if not found."""
    data = read_ini(file_path)
    if section in data and key in data[section]:
        del data[section][key]
        write_ini(file_path, data)
        return True
    return False

def delete_section(file_path: Union[str, Path], section: str) -> bool:
    """Deletes an entire section. Returns True if deleted, False if not found."""
    data = read_ini(file_path)
    if section in data:
        del data[section]
        write_ini(file_path, data)
        return True
    return False

def list_sections(file_path: Union[str, Path]) -> List[str]:
    """Returns a list of all sections in the INI file."""
    return list(read_ini(file_path).keys())

def list_keys(file_path: Union[str, Path], section: str) -> List[str]:
    """Returns a list of all keys within a specific section."""
    data = read_ini(file_path)
    return list(data.get(section, {}).keys())

def has_section(file_path: Union[str, Path], section: str) -> bool:
    """Checks if a section exists."""
    return section in read_ini(file_path)

def has_key(file_path: Union[str, Path], section: str, key: str) -> bool:
    """Checks if a key exists within a specific section."""
    data = read_ini(file_path)
    return key in data.get(section, {})

def clear_section(file_path: Union[str, Path], section: str) -> bool:
    """Removes all keys from a section but leaves the section header."""
    data = read_ini(file_path)
    if section in data:
        data[section] = {}
        write_ini(file_path, data)
        return True
    return False

# ==============================================================================
# Conversion & Translation Operations
# ==============================================================================

def ini_to_dict(file_path: Union[str, Path]) -> Dict[str, Dict[str, str]]:
    """Alias for read_ini to explicitly show data type transformation."""
    return read_ini(file_path)

def dict_to_ini(data: Dict[str, Dict[str, Any]], file_path: Union[str, Path]) -> None:
    """Alias for write_ini to handle generic dictionary structures."""
    stringified_data = {
        sec: {k: str(v) for k, v in keys.items()} 
        for sec, keys in data.items()
    }
    write_ini(file_path, stringified_data)

def ini_to_json(file_path: Union[str, Path], json_path: Union[str, Path]) -> None:
    """Converts an INI file to a JSON file."""
    data = read_ini(file_path)
    _ensure_dir(json_path)
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        raise RuntimeError(f"Failed to write JSON {json_path}: {e}")

def json_to_ini(json_path: Union[str, Path], ini_path: Union[str, Path]) -> None:
    """Converts a JSON file to an INI file."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        dict_to_ini(data, ini_path)
    except (IOError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Failed to process JSON {json_path}: {e}")

def merge_ini_files(base_file: Union[str, Path], override_file: Union[str, Path], output_file: Union[str, Path]) -> Dict[str, Dict[str, str]]:
    """Merges override_file into base_file and saves to output_file. Overrides take precedence."""
    base_data = read_ini(base_file)
    override_data = read_ini(override_file)
    
    for section, keys in override_data.items():
        if section not in base_data:
            base_data[section] = {}
        base_data[section].update(keys)
        
    write_ini(output_file, base_data)
    return base_data

def diff_ini_files(file1: Union[str, Path], file2: Union[str, Path]) -> Dict[str, Any]:
    """Compares two INI files. Returns a dictionary of differences."""
    data1 = read_ini(file1)
    data2 = read_ini(file2)
    
    diff = {"added": {}, "removed": {}, "changed": {}}
    
    all_sections = set(data1.keys()).union(set(data2.keys()))
    for sec in all_sections:
        keys1 = data1.get(sec, {})
        keys2 = data2.get(sec, {})
        
        all_keys = set(keys1.keys()).union(set(keys2.keys()))
        for k in all_keys:
            v1 = keys1.get(k)
            v2 = keys2.get(k)
            
            if v1 is None:
                diff["added"].setdefault(sec, {})[k] = v2
            elif v2 is None:
                diff["removed"].setdefault(sec, {})[k] = v1
            elif v1 != v2:
                diff["changed"].setdefault(sec, {})[k] = {"from": v1, "to": v2}
                
    return {k: v for k, v in diff.items() if v}

# ==============================================================================
# Advanced Types & Environment integration
# ==============================================================================

def get_typed_value(file_path: Union[str, Path], section: str, key: str, value_type: Type, fallback: Any = None) -> Any:
    """Retrieves a value and casts it to the specified type (int, float, bool, list, dict)."""
    raw_val = get_value(file_path, section, key)
    if raw_val is None:
        return fallback
        
    try:
        if value_type == bool:
            return raw_val.lower() in ('true', '1', 'yes', 'on')
        elif value_type in (int, float):
            return value_type(raw_val)
        elif value_type == list:
            try:
                return json.loads(raw_val)
            except json.JSONDecodeError:
                return [x.strip() for x in raw_val.split(',') if x.strip()]
        elif value_type == dict:
            return json.loads(raw_val)
        return value_type(raw_val)
    except (ValueError, TypeError, json.JSONDecodeError):
        return fallback

def set_typed_value(file_path: Union[str, Path], section: str, key: str, value: Any) -> None:
    """Sets a value, serializing complex types like lists or dicts to JSON strings."""
    if isinstance(value, bool):
        str_val = 'true' if value else 'false'
    elif isinstance(value, (list, dict)):
        str_val = json.dumps(value)
    else:
        str_val = str(value)
        
    set_value(file_path, section, key, str_val)

def export_to_env(file_path: Union[str, Path], prefix: str = "INI_") -> None:
    """Exports all INI keys to os.environ. Format: PREFIX_SECTION_KEY=value."""
    data = read_ini(file_path)
    for section, keys in data.items():
        for key, val in keys.items():
            env_key = f"{prefix}{section.upper()}_{key.upper()}".replace("-", "_").replace(" ", "_")
            os.environ[env_key] = val

def import_from_env(file_path: Union[str, Path], prefix: str = "INI_") -> Dict[str, Dict[str, str]]:
    """Imports environment variables matching the prefix into the INI file."""
    data = read_ini(file_path)
    prefix_len = len(prefix)
    
    for env_key, val in os.environ.items():
        if env_key.startswith(prefix):
            # Assume first underscore after prefix separates SECTION and KEY
            stripped = env_key[prefix_len:]
            if '_' in stripped:
                section, key = stripped.split('_', 1)
                # Fallback to lowercasing for standard INI aesthetics
                section, key = section.lower(), key.lower()
                
                if section not in data:
                    data[section] = {}
                data[section][key] = val
                
    write_ini(file_path, data)
    return data

# ==============================================================================
# Utility & Safety Operations
# ==============================================================================

def validate_ini(file_path: Union[str, Path], schema: Dict[str, List[str]]) -> bool:
    """
    Validates that the INI file contains the required sections and keys.
    schema format: {"Section1": ["key1", "key2"]}
    """
    data = read_ini(file_path)
    for req_section, req_keys in schema.items():
        if req_section not in data:
            return False
        for k in req_keys:
            if k not in data[req_section]:
                return False
    return True

def create_template(file_path: Union[str, Path], template_data: Dict[str, Dict[str, str]]) -> None:
    """Creates a default INI file if one does not already exist."""
    if not Path(file_path).exists():
        write_ini(file_path, template_data)

def backup_ini(file_path: Union[str, Path], backup_dir: Union[str, Path, None] = None) -> str:
    """Creates a timestamped backup of the INI file. Returns the backup path."""
    src = Path(file_path)
    if not src.exists():
        raise FileNotFoundError(f"Cannot backup. File does not exist: {file_path}")
        
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    b_dir = Path(backup_dir) if backup_dir else src.parent
    _ensure_dir(b_dir / "dummy")
    
    backup_path = b_dir / f"{src.stem}_{timestamp}{src.suffix}.bak"
    shutil.copy2(src, backup_path)
    return str(backup_path)

def restore_ini(backup_path: Union[str, Path], file_path: Union[str, Path]) -> None:
    """Restores an INI file from a backup."""
    b_path = Path(backup_path)
    if not b_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")
    
    _ensure_dir(file_path)
    shutil.copy2(b_path, file_path)

def watch_ini_changes(file_path: Union[str, Path], timeout: int = 60, interval: float = 1.0) -> bool:
    """
    Blocks and watches the INI file for changes up to `timeout` seconds.
    Returns True if changed, False if timeout reached.
    """
    path = Path(file_path)
    if not path.exists():
        return False
        
    initial_mtime = os.path.getmtime(path)
    start_time = time.time()
    
    while (time.time() - start_time) < timeout:
        try:
            current_mtime = os.path.getmtime(path)
            if current_mtime != initial_mtime:
                return True
        except OSError:
            pass  # File might be temporarily locked or deleted during write
        time.sleep(interval)
        
    return False

