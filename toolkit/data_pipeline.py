import pandas as pd
import csv
import json
import sqlite3
import threading
import queue
import hashlib
import io
from typing import List, Dict, Any, Callable, Optional


def _hash_data(data: Any, max_len: int = 1000) -> str:
    """Compute a deterministic hash for data tracking."""
    try:
        payload = json.dumps(data, default=str, sort_keys=True)
        return hashlib.sha256(payload[:max_len].encode("utf-8")).hexdigest()
    except Exception:
        return hashlib.md5(str(type(data)).encode()).hexdigest()


def _safe_df_to_list(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert DataFrame to list of dictionaries, replacing NaT/NaN with None."""
    return df.replace({pd.NaT: None, pd.NaT: None}).where(pd.notnull(df), None).to_dict(orient="records")


def _response(success: bool, data: Any = None, metadata: Dict[str, Any] = None, error: Optional[str] = None) -> Dict[str, Any]:
    """Standard response wrapper."""
    meta = metadata or {}
    if data is not None:
        meta.setdefault("hash", _hash_data(data))
    return {
        "success": success,
        "data": data,
        "metadata": meta,
        "error": error
    }


def _infer_type(value: str, col_series: pd.Series) -> Any:
    """Safely cast filter value to match DataFrame column dtype."""
    if col_series.dtype == "object":
        return value
    try:
        if pd.api.types.is_numeric_dtype(col_series):
            return pd.to_numeric(value)
        if pd.api.types.is_bool_dtype(col_series):
            return str(value).lower() in ("true", "1", "yes")
        return value
    except (ValueError, TypeError):
        return value


# -------------------------
# File I/O Functions
# -------------------------

def read_csv(file_path: str, delimiter: str = ",") -> Dict[str, Any]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            csv_reader = csv.DictReader(f, delimiter=delimiter)
            data = list(csv_reader)
        df = pd.DataFrame(data)
        result = _safe_df_to_list(df)
        return _response(True, result, {"rows_read": len(result)})
    except Exception as e:
        return _response(False, error=f"Failed to read CSV: {str(e)}")


def write_csv(data: List[Dict[str, Any]], file_path: str, headers: List[str] = None) -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        if headers:
            missing = set(headers) - set(df.columns)
            if missing:
                df[list(missing)] = None
            df = df[headers]
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(output.getvalue())
        return _response(True, data, {"rows_written": len(data), "path": file_path})
    except Exception as e:
        return _response(False, error=f"Failed to write CSV: {str(e)}")


def read_json_file(file_path: str) -> Dict[str, Any]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        parsed = json.loads(content)
        return _response(True, parsed, {"bytes_read": len(content)})
    except Exception as e:
        return _response(False, error=f"Failed to read JSON: {str(e)}")


def write_json_file(data: Dict[str, Any], file_path: str, indent: int = 2) -> Dict[str, Any]:
    try:
        content = json.dumps(data, indent=indent, default=str)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return _response(True, data, {"bytes_written": len(content.encode("utf-8")), "path": file_path})
    except Exception as e:
        return _response(False, error=f"Failed to write JSON: {str(e)}")


def csv_to_json(csv_path: str, json_path: str = "") -> Dict[str, Any]:
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            csv_reader = csv.DictReader(f)
            data = list(csv_reader)
        if data:
            df = pd.DataFrame(data)
            result = _safe_df_to_list(df)
        else:
            result = []
        if json_path:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, default=str)
        return _response(True, result, {"source": csv_path, "target": json_path or "in-memory"})
    except Exception as e:
        return _response(False, error=f"CSV to JSON conversion failed: {str(e)}")


def json_to_csv(json_path: str, csv_path: str = "") -> Dict[str, Any]:
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        if isinstance(parsed, dict):
            parsed = [parsed]
        df = pd.DataFrame(parsed)
        if csv_path:
            df.to_csv(csv_path, index=False)
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        result = list(csv.DictReader(output))
        return _response(True, result, {"source": json_path, "target": csv_path or "in-memory"})
    except Exception as e:
        return _response(False, error=f"JSON to CSV conversion failed: {str(e)}")


# -------------------------
# Data Manipulation Functions
# -------------------------

def filter_data(data: List[Dict[str, Any]], column: str, value: str, operator: str = "eq") -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        if column not in df.columns:
            raise KeyError(f"Column '{column}' not found")
        target_val = _infer_type(value, df[column])
        ops = {
            "eq": lambda c, v: c == v,
            "ne": lambda c, v: c != v,
            "gt": lambda c, v: c > v,
            "lt": lambda c, v: c < v,
            "ge": lambda c, v: c >= v,
            "le": lambda c, v: c <= v,
            "contains": lambda c, v: c.astype(str).str.contains(str(v), na=False, regex=False)
        }
        if operator not in ops:
            raise ValueError(f"Unsupported operator: {operator}")
        filtered = df[ops[operator](df[column], target_val)]
        result = _safe_df_to_list(filtered)
        return _response(True, result, {"rows_filtered": len(result)})
    except Exception as e:
        return _response(False, error=f"Filtering failed: {str(e)}")


def sort_data(data: List[Dict[str, Any]], column: str, reverse: bool = False) -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        if column not in df.columns:
            raise KeyError(f"Column '{column}' not found")
        if pd.api.types.is_numeric_dtype(df[column]):
            df = df.sort_values(column, ascending=not reverse)
        else:
            df = df.sort_values(column, ascending=not reverse, key=lambda x: x.astype(str))
        return _response(True, _safe_df_to_list(df), {"sorted": True})
    except Exception as e:
        return _response(False, error=f"Sorting failed: {str(e)}")


def merge_datasets(data1: List[Dict[str, Any]], data2: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    try:
        df1, df2 = pd.DataFrame(data1), pd.DataFrame(data2)
        merged = pd.merge(df1, df2, on=key, how="inner")
        return _response(True, _safe_df_to_list(merged), {"merged_rows": len(merged), "join_key": key})
    except Exception as e:
        return _response(False, error=f"Merging failed: {str(e)}")


def aggregate_data(data: List[Dict[str, Any]], column: str, operation: str = "sum") -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        if column not in df.columns:
            raise KeyError(f"Column '{column}' not found")
        series = pd.to_numeric(df[column], errors="coerce")
        agg_map = {
            "sum": series.sum(), "mean": series.mean(), "count": series.count(),
            "min": series.min(), "max": series.max(), "median": series.median(),
            "std": series.std()
        }
        if operation not in agg_map:
            raise ValueError(f"Unsupported operation: {operation}")
        result_val = agg_map[operation]
        res_val = float(result_val) if pd.notna(result_val) else 0.0
        return _response(True, [{column: column, f"{operation}_result": res_val}])
    except Exception as e:
        return _response(False, error=f"Aggregation failed: {str(e)}")


def deduplicate(data: List[Dict[str, Any]], columns: List[str] = None) -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        subset = [c for c in columns if c in df.columns] if columns else None
        deduped = df.drop_duplicates(subset=subset)
        removed = len(data) - len(deduped)
        return _response(True, _safe_df_to_list(deduped), {"duplicates_removed": removed})
    except Exception as e:
        return _response(False, error=f"Deduplication failed: {str(e)}")


def validate_data(data: List[Dict[str, Any]], schema: Dict[str, str]) -> Dict[str, Any]:
    try:
        valid, invalid_count = [], 0
        type_checks = {
            "int": lambda x: isinstance(x, int),
            "float": lambda x: isinstance(x, (float, int)),
            "str": lambda x: isinstance(x, str),
            "bool": lambda x: isinstance(x, bool) or str(x).lower() in ("true", "false", "1", "0"),
            "email": lambda x: isinstance(x, str) and "@" in x
        }
        for row in data:
            is_valid = True
            for col, expected_type in schema.items():
                val = row.get(col)
                if val is None:
                    is_valid = False
                    break
                checker = type_checks.get(expected_type.lower(), lambda x: True)
                if not checker(val):
                    try:
                        cast_map = {"int": int, "float": float, "str": str, "bool": bool}
                        cast_map.get(expected_type, lambda x: x)(val)
                    except (ValueError, TypeError):
                        is_valid = False
                        break
            if is_valid:
                valid.append(row)
            else:
                invalid_count += 1
        return _response(True, valid, {"valid_rows": len(valid), "invalid_rows": invalid_count, "schema": schema})
    except Exception as e:
        return _response(False, error=f"Validation failed: {str(e)}")


def transform_column(data: List[Dict[str, Any]], column: str, func: Callable) -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        if column not in df.columns:
            raise KeyError(f"Column '{column}' not found")
        df[column] = df[column].apply(func)
        return _response(True, _safe_df_to_list(df), {"column_transformed": column})
    except Exception as e:
        return _response(False, error=f"Transformation failed: {str(e)}")


def pivot_data(data: List[Dict[str, Any]], index: str, columns: str, values: str) -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        pivoted = df.pivot(index=index, columns=columns, values=values).reset_index()
        pivoted.columns.name = None
        return _response(True, _safe_df_to_list(pivoted))
    except Exception as e:
        return _response(False, error=f"Pivoting failed: {str(e)}")


def unpivot_data(data: List[Dict[str, Any]], id_vars: List[str], value_vars: List[str]) -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        melted = pd.melt(df, id_vars=id_vars, value_vars=value_vars)
        return _response(True, _safe_df_to_list(melted))
    except Exception as e:
        return _response(False, error=f"Unpivoting failed: {str(e)}")


def sample_data(data: List[Dict[str, Any]], n: int = 10, random_state: int = 42) -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        n = min(n, len(df))
        sampled = df.sample(n=n, random_state=random_state)
        return _response(True, _safe_df_to_list(sampled), {"sampled_rows": n, "random_state": random_state})
    except Exception as e:
        return _response(False, error=f"Sampling failed: {str(e)}")


def split_data(data: List[Dict[str, Any]], ratio: float = 0.8) -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        split_idx = int(len(df) * ratio)
        train, test = df.iloc[:split_idx], df.iloc[split_idx:]
        return _response(True, {"train": _safe_df_to_list(train), "test": _safe_df_to_list(test)}, {"train_size": len(train), "test_size": len(test)})
    except Exception as e:
        return _response(False, error=f"Splitting failed: {str(e)}")


def normalize_column(data: List[Dict[str, Any]], column: str) -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        s = pd.to_numeric(df[column], errors="coerce")
        min_v, max_v = s.min(), s.max()
        if max_v == min_v:
            df[column] = 0.0
        else:
            df[column] = (s - min_v) / (max_v - min_v)
        return _response(True, _safe_df_to_list(df), {"min_original": min_v, "max_original": max_v})
    except Exception as e:
        return _response(False, error=f"Normalization failed: {str(e)}")


def fill_missing(data: List[Dict[str, Any]], column: str, strategy: str = "mean") -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        s = pd.to_numeric(df[column], errors="coerce")
        if strategy == "mean":
            fill_val = s.mean()
        elif strategy == "median":
            fill_val = s.median()
        elif strategy == "mode":
            fill_val = s.mode().iloc[0] if not s.mode().empty else 0.0
        else:
            fill_val = 0.0
        df[column] = s.fillna(fill_val)
        return _response(True, _safe_df_to_list(df), {"fillna_value": fill_val, "strategy": strategy})
    except Exception as e:
        return _response(False, error=f"Missing value filling failed: {str(e)}")


def encode_categorical(data: List[Dict[str, Any]], column: str) -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        df[column] = df[column].astype("category").cat.codes.replace(-1, 0)
        return _response(True, _safe_df_to_list(df), {"encoded_column": column, "categories": len(df[column].unique())})
    except Exception as e:
        return _response(False, error=f"Categorical encoding failed: {str(e)}")


# -------------------------
# Pipeline & Database Functions
# -------------------------

def create_pipeline(steps: list) -> Dict[str, Any]:
    """Creates a pipeline configuration object from a list of functions or step dictionaries."""
    processed_steps = []
    for step in steps:
        if callable(step):
            processed_steps.append({"func": step, "kwargs": {}})
        elif isinstance(step, dict):
            processed_steps.append(step)
        else:
            raise ValueError("Steps must be callable or configuration dict")
    return _response(True, {"steps": processed_steps}, {"step_count": len(steps)})


def run_pipeline(pipeline: dict, data: list) -> Dict[str, Any]:
    """Executes the pipeline steps using threading and queue for controlled flow."""
    try:
        q = queue.Queue()
        q.put(data)
        result_queue = queue.Queue()
        steps = pipeline.get("data", {}).get("steps", pipeline.get("steps", []))

        def execute_step(step_data):
            current_data, step_list = step_data
            for cfg in step_list:
                func = cfg["func"]
                kwargs = cfg.get("kwargs", {})
                if isinstance(current_data, dict) and "data" in current_data:
                    current_data = current_data.get("data", current_data)
                try:
                    res = func(current_data, **kwargs)
                    current_data = res.get("data", res) if isinstance(res, dict) else res
                except Exception as ex:
                    raise RuntimeError(f"Pipeline step failed at {func.__name__}: {str(ex)}")
            result_queue.put(current_data)

        worker = threading.Thread(target=execute_step, args=(data, steps), daemon=True)
        worker.start()
        worker.join(timeout=120)

        if result_queue.empty():
            final_data = q.get()
        else:
            final_data = result_queue.get()

        return _response(True, final_data, {"steps_executed": len(steps), "pipeline_status": "completed"})
    except Exception as e:
        return _response(False, error=f"Pipeline execution failed: {str(e)}")


def export_to_sqlite(data: list, db_path: str, table: str) -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        con = sqlite3.connect(db_path)
        try:
            df.to_sql(table, con, if_exists="replace", index=False)
        finally:
            con.close()
        return _response(True, data, {"table": table, "db_path": db_path, "rows_inserted": len(data)})
    except Exception as e:
        return _response(False, error=f"SQLite export failed: {str(e)}")


def import_from_sqlite(db_path: str, query: str) -> Dict[str, Any]:
    try:
        con = sqlite3.connect(db_path)
        try:
            df = pd.read_sql_query(query, con)
        finally:
            con.close()
        return _response(True, _safe_df_to_list(df), {"rows_imported": len(df), "query": query})
    except Exception as e:
        return _response(False, error=f"SQLite import failed: {str(e)}")


def generate_summary(data: list) -> Dict[str, Any]:
    try:
        df = pd.DataFrame(data)
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        summary = {
            "shape": df.shape,
            "columns": list(df.columns),
            "total_values": df.size,
            "missing_values": df.isnull().sum().to_dict(),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "head": _safe_df_to_list(df.head()),
            "numeric_stats": df[numeric_cols].describe().to_dict() if numeric_cols else {}
        }
        return _response(True, summary, {"summary_generated": True})
    except Exception as e:
        return _response(False, error=f"Summary generation failed: {str(e)}")