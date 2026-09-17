import csv
import json
import os
import io
import re
import random
import statistics
import traceback
from pathlib import Path
from collections import defaultdict, Counter
from functools import wraps
from typing import List, Dict, Any, Optional, Union, Tuple

# =====================================================================
# AGENT TOOLKIT DECORATOR
# Ensures all functions return a standardized Dict payload.
# =====================================================================
def agent_tool(func):
    @wraps(func)
    def wrapper(*args, **kwargs) -> Dict[str, Any]:
        try:
            result = func(*args, **kwargs)
            # Prevent double-wrapping if a function calls another
            if isinstance(result, dict) and "success" in result and "data" in result:
                return result
            return {
                "success": True,
                "message": f"'{func.__name__}' executed successfully.",
                "data": result,
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Execution failed in '{func.__name__}'.",
                "data": None,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    return wrapper

# =====================================================================
# CORE I/O OPERATIONS
# =====================================================================

@agent_tool
def read_csv(filepath: Union[str, Path], delimiter: str = ',') -> List[Dict[str, str]]:
    filepath = Path(filepath)
    with filepath.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        return list(reader)

@agent_tool
def write_csv(filepath: Union[str, Path], data: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None, delimiter: str = ',') -> str:
    if not data:
        raise ValueError("Data list is empty. Cannot write CSV.")
    filepath = Path(filepath)
    fieldnames = fieldnames or list(data[0].keys())
    with filepath.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(data)
    return str(filepath.absolute())

@agent_tool
def append_rows(filepath: Union[str, Path], rows: List[Dict[str, Any]], delimiter: str = ',') -> str:
    if not rows:
        return str(Path(filepath).absolute())
    filepath = Path(filepath)
    file_exists = filepath.exists()
    fieldnames = list(rows[0].keys())
    
    with filepath.open('a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)
    return str(filepath.absolute())

@agent_tool
def csv_to_dict_list(filepath: Union[str, Path]) -> List[Dict[str, str]]:
    # Alias for read_csv logically, but kept explicit for agent routing
    return read_csv(filepath).get("data", [])

# =====================================================================
# DATA MANIPULATION & FILTERING
# =====================================================================

@agent_tool
def filter_rows(filepath: Union[str, Path], column: str, condition: str, value: Any, output_path: Optional[Union[str, Path]] = None) -> List[Dict[str, str]]:
    data = read_csv(filepath).get("data", [])
    filtered = []
    value_str = str(value).lower()
    
    for row in data:
        cell_val = str(row.get(column, "")).lower()
        match = False
        if condition == '==': match = cell_val == value_str
        elif condition == '!=': match = cell_val != value_str
        elif condition == 'contains': match = value_str in cell_val
        elif condition == '>': match = float(cell_val) > float(value_str)
        elif condition == '<': match = float(cell_val) < float(value_str)
        else: raise ValueError(f"Unsupported condition: {condition}")
        
        if match:
            filtered.append(row)
            
    if output_path:
        write_csv(output_path, filtered)
    return filtered

@agent_tool
def sort_csv(filepath: Union[str, Path], column: str, reverse: bool = False, output_path: Optional[Union[str, Path]] = None) -> List[Dict[str, str]]:
    data = read_csv(filepath).get("data", [])
    
    def sort_key(row):
        val = row.get(column, "")
        try: return float(val)
        except ValueError: return val

    sorted_data = sorted(data, key=sort_key, reverse=reverse)
    if output_path:
        write_csv(output_path, sorted_data)
    return sorted_data

@agent_tool
def deduplicate(filepath: Union[str, Path], subset: Optional[List[str]] = None, output_path: Optional[Union[str, Path]] = None) -> List[Dict[str, str]]:
    data = read_csv(filepath).get("data", [])
    seen = set()
    deduped = []
    
    for row in data:
        check_keys = subset if subset else row.keys()
        sig = tuple(row.get(k, "") for k in check_keys)
        if sig not in seen:
            seen.add(sig)
            deduped.append(row)
            
    if output_path:
        write_csv(output_path, deduped)
    return deduped

@agent_tool
def search_csv(filepath: Union[str, Path], query: str, regex: bool = False) -> List[Dict[str, str]]:
    data = read_csv(filepath).get("data", [])
    results = []
    pattern = re.compile(query, re.IGNORECASE) if regex else None
    
    for row in data:
        for val in row.values():
            if regex and pattern.search(str(val)):
                results.append(row)
                break
            elif not regex and query.lower() in str(val).lower():
                results.append(row)
                break
    return results

# =====================================================================
# COLUMN OPERATIONS
# =====================================================================

@agent_tool
def get_column(filepath: Union[str, Path], column: str) -> List[str]:
    data = read_csv(filepath).get("data", [])
    if not data or column not in data[0]:
        raise ValueError(f"Column '{column}' not found.")
    return [row[column] for row in data]

@agent_tool
def add_column(filepath: Union[str, Path], column: str, default_value: Any = "", output_path: Optional[Union[str, Path]] = None) -> List[Dict[str, str]]:
    data = read_csv(filepath).get("data", [])
    for row in data:
        row[column] = str(default_value)
    
    out = output_path or filepath
    write_csv(out, data)
    return data

@agent_tool
def remove_column(filepath: Union[str, Path], column: str, output_path: Optional[Union[str, Path]] = None) -> List[Dict[str, str]]:
    data = read_csv(filepath).get("data", [])
    for row in data:
        row.pop(column, None)
        
    out = output_path or filepath
    write_csv(out, data)
    return data

@agent_tool
def rename_columns(filepath: Union[str, Path], mapping: Dict[str, str], output_path: Optional[Union[str, Path]] = None) -> List[Dict[str, str]]:
    data = read_csv(filepath).get("data", [])
    new_data = []
    for row in data:
        new_row = {mapping.get(k, k): v for k, v in row.items()}
        new_data.append(new_row)
        
    out = output_path or filepath
    write_csv(out, new_data)
    return new_data

# =====================================================================
# FORMAT CONVERSIONS
# =====================================================================

@agent_tool
def csv_to_json(csv_path: Union[str, Path], json_path: Union[str, Path]) -> str:
    data = read_csv(csv_path).get("data", [])
    with Path(json_path).open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    return str(Path(json_path).absolute())

@agent_tool
def json_to_csv(json_path: Union[str, Path], csv_path: Union[str, Path]) -> str:
    with Path(json_path).open('r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list) or not isinstance(data[0], dict):
        raise ValueError("JSON must contain a list of dictionaries to convert to CSV.")
    write_csv(csv_path, data)
    return str(Path(csv_path).absolute())

@agent_tool
def export_formatted(filepath: Union[str, Path], format_type: str = 'markdown') -> str:
    data = read_csv(filepath).get("data", [])
    if not data: return ""
    
    if format_type.lower() == 'markdown':
        headers = list(data[0].keys())
        md = []
        md.append("| " + " | ".join(headers) + " |")
        md.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in data:
            md.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
        return "\n".join(md)
    else:
        raise ValueError(f"Format type '{format_type}' not supported.")

# =====================================================================
# AGGREGATION & STATISTICS
# =====================================================================

@agent_tool
def get_statistics(filepath: Union[str, Path], column: str) -> Dict[str, float]:
    col_data = get_column(filepath, column).get("data", [])
    numeric_data = []
    for val in col_data:
        try:
            numeric_data.append(float(val))
        except ValueError:
            pass
            
    if not numeric_data:
        raise ValueError("No numeric data found in column to calculate statistics.")
        
    return {
        "count": len(numeric_data),
        "min": min(numeric_data),
        "max": max(numeric_data),
        "mean": statistics.mean(numeric_data),
        "median": statistics.median(numeric_data),
        "stdev": statistics.stdev(numeric_data) if len(numeric_data) > 1 else 0.0
    }

@agent_tool
def pivot_table(filepath: Union[str, Path], index_col: str, value_col: str, agg_func: str = 'sum') -> List[Dict[str, Any]]:
    data = read_csv(filepath).get("data", [])
    pivot = defaultdict(list)
    
    for row in data:
        idx_val = row.get(index_col)
        val = row.get(value_col)
        try: pivot[idx_val].append(float(val))
        except (ValueError, TypeError): continue
        
    result = []
    for idx, vals in pivot.items():
        agg_val = 0
        if agg_func == 'sum': agg_val = sum(vals)
        elif agg_func == 'mean': agg_val = statistics.mean(vals)
        elif agg_func == 'count': agg_val = len(vals)
        elif agg_func == 'max': agg_val = max(vals)
        elif agg_func == 'min': agg_val = min(vals)
        
        result.append({index_col: idx, f"{value_col}_{agg_func}": agg_val})
    return result

@agent_tool
def group_by(filepath: Union[str, Path], column: str) -> Dict[str, List[Dict[str, str]]]:
    data = read_csv(filepath).get("data", [])
    grouped = defaultdict(list)
    for row in data:
        grouped[row.get(column, "UNKNOWN")].append(row)
    return dict(grouped)

# =====================================================================
# FILE & INFRASTRUCTURE UTILS
# =====================================================================

@agent_tool
def merge_csv_files(filepaths: List[Union[str, Path]], output_path: Union[str, Path]) -> str:
    if not filepaths: raise ValueError("No files provided to merge.")
    
    all_data = []
    for fp in filepaths:
        file_data = read_csv(fp).get("data", [])
        all_data.extend(file_data)
        
    write_csv(output_path, all_data)
    return str(Path(output_path).absolute())

@agent_tool
def split_csv(filepath: Union[str, Path], rows_per_file: int, output_dir: Union[str, Path]) -> List[str]:
    data = read_csv(filepath).get("data", [])
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = Path(filepath).stem
    
    out_files = []
    for i in range(0, len(data), rows_per_file):
        chunk = data[i:i + rows_per_file]
        chunk_path = out_dir / f"{base_name}_part_{i//rows_per_file + 1}.csv"
        write_csv(chunk_path, chunk)
        out_files.append(str(chunk_path.absolute()))
    return out_files

@agent_tool
def chunk_csv(filepath: Union[str, Path], chunk_size: int) -> List[List[Dict[str, str]]]:
    data = read_csv(filepath).get("data", [])
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

@agent_tool
def validate_csv(filepath: Union[str, Path], required_columns: List[str]) -> bool:
    data = read_csv(filepath).get("data", [])
    if not data: return False
    headers = data[0].keys()
    missing = [col for col in required_columns if col not in headers]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return True

@agent_tool
def detect_delimiter(filepath: Union[str, Path]) -> str:
    with Path(filepath).open('r', encoding='utf-8') as f:
        sample = f.read(2048)
        try:
            dialect = csv.Sniffer().sniff(sample)
            return dialect.delimiter
        except csv.Error:
            return ',' # Default fallback

@agent_tool
def fix_encoding(input_path: Union[str, Path], output_path: Union[str, Path], from_enc: str = 'latin1', to_enc: str = 'utf-8') -> str:
    with Path(input_path).open('r', encoding=from_enc, errors='replace') as infile:
        content = infile.read()
    with Path(output_path).open('w', encoding=to_enc) as outfile:
        outfile.write(content)
    return str(Path(output_path).absolute())

@agent_tool
def sample_rows(filepath: Union[str, Path], n: int) -> List[Dict[str, str]]:
    data = read_csv(filepath).get("data", [])
    if n > len(data): n = len(data)
    return random.sample(data, n)

