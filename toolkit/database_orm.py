from __future__ import annotations

import csv
import json
import os
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

_CONNECTIONS: Dict[str, sqlite3.Connection] = {}
_DB_PATHS: Dict[str, Path] = {}


def _ok(**kwargs: Any) -> Dict[str, Any]:
    return {"success": True, **kwargs}


def _err(message: str, **kwargs: Any) -> Dict[str, Any]:
    return {"success": False, "error": message, **kwargs}


def _get_conn(connection_id: str) -> sqlite3.Connection:
    if connection_id not in _CONNECTIONS:
        raise KeyError(f"Invalid connection_id: {connection_id}")
    return _CONNECTIONS[connection_id]


def _quote_ident(name: str) -> str:
    if not name or any(c in name for c in ';\x00'):
        raise ValueError("Invalid identifier")
    return f'"{name}"'


def create_database(db_path: str, tables_schema: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    try:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{path}")
        with engine.begin() as conn:
            for table, schema in tables_schema.items():
                cols = ", ".join(f'{_quote_ident(k)} {v}' for k, v in schema.items())
                conn.execute(text(f"CREATE TABLE IF NOT EXISTS {_quote_ident(table)} ({cols})"))
        engine.dispose()
        return _ok(db_path=str(path))
    except Exception as e:
        return _err(str(e))


def connect_database(db_path: str) -> Dict[str, Any]:
    try:
        path = Path(db_path)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        cid = str(uuid.uuid4())
        _CONNECTIONS[cid] = conn
        _DB_PATHS[cid] = path
        return _ok(connection_id=cid)
    except Exception as e:
        return _err(str(e))


def disconnect_database(connection_id: str) -> Dict[str, Any]:
    try:
        conn = _get_conn(connection_id)
        conn.close()
        _CONNECTIONS.pop(connection_id, None)
        _DB_PATHS.pop(connection_id, None)
        return _ok(connection_id=connection_id)
    except Exception as e:
        return _err(str(e))


def execute_query(connection_id: str, query: str, params: Optional[Sequence[Any]] = None) -> Dict[str, Any]:
    try:
        conn = _get_conn(connection_id)
        cur = conn.execute(query, params or [])
        rows = [dict(r) for r in cur.fetchall()] if cur.description else []
        conn.commit()
        return _ok(rows=rows, rowcount=cur.rowcount)
    except Exception as e:
        return _err(str(e))


def execute_many(connection_id: str, query: str, params_list: Iterable[Sequence[Any]]) -> Dict[str, Any]:
    try:
        conn = _get_conn(connection_id)
        cur = conn.executemany(query, list(params_list))
        conn.commit()
        return _ok(rowcount=cur.rowcount)
    except Exception as e:
        return _err(str(e))


def create_table(connection_id: str, table_name: str, columns: Dict[str, str]) -> Dict[str, Any]:
    q = f"CREATE TABLE IF NOT EXISTS {_quote_ident(table_name)} (" + ", ".join(f'{_quote_ident(k)} {v}' for k, v in columns.items()) + ")"
    return execute_query(connection_id, q)


def drop_table(connection_id: str, table_name: str) -> Dict[str, Any]:
    return execute_query(connection_id, f"DROP TABLE IF EXISTS {_quote_ident(table_name)}")


def insert_record(connection_id: str, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
    cols = ", ".join(_quote_ident(k) for k in data)
    placeholders = ", ".join("?" for _ in data)
    return execute_query(connection_id, f"INSERT INTO {_quote_ident(table)} ({cols}) VALUES ({placeholders})", list(data.values()))


def insert_many_records(connection_id: str, table: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not records:
        return _ok(rowcount=0)
    cols = list(records[0].keys())
    q = f"INSERT INTO {_quote_ident(table)} (" + ", ".join(_quote_ident(c) for c in cols) + ") VALUES (" + ", ".join("?" for _ in cols) + ")"
    params = [[r.get(c) for c in cols] for r in records]
    return execute_many(connection_id, q, params)


def update_records(connection_id: str, table: str, data: Dict[str, Any], where: Dict[str, Any]) -> Dict[str, Any]:
    set_clause = ", ".join(f"{_quote_ident(k)}=?" for k in data)
    where_clause = " AND ".join(f"{_quote_ident(k)}=?" for k in where)
    params = list(data.values()) + list(where.values())
    return execute_query(connection_id, f"UPDATE {_quote_ident(table)} SET {set_clause} WHERE {where_clause}", params)


def delete_records(connection_id: str, table: str, where: Dict[str, Any]) -> Dict[str, Any]:
    where_clause = " AND ".join(f"{_quote_ident(k)}=?" for k in where)
    return execute_query(connection_id, f"DELETE FROM {_quote_ident(table)} WHERE {where_clause}", list(where.values()))


def select_records(connection_id: str, table: str, columns: List[str], where: Optional[Dict[str, Any]] = None, order_by: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, Any]:
    q = f"SELECT {', '.join(_quote_ident(c) for c in columns)} FROM {_quote_ident(table)}"
    params: List[Any] = []
    if where:
        q += " WHERE " + " AND ".join(f"{_quote_ident(k)}=?" for k in where)
        params.extend(where.values())
    if order_by:
        q += f" ORDER BY {_quote_ident(order_by)}"
    if limit is not None:
        q += " LIMIT ?"
        params.append(limit)
    return execute_query(connection_id, q, params)


def count_records(connection_id: str, table: str, where: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    res = select_records(connection_id, table, ["COUNT(*) as count"], where)
    return _ok(count=res.get("rows", [{}])[0].get("count", 0)) if res["success"] else res


def table_exists(connection_id: str, table_name: str) -> Dict[str, Any]:
    return execute_query(connection_id, "SELECT name FROM sqlite_master WHERE type='table' AND name=?", [table_name])


def list_tables(connection_id: str) -> Dict[str, Any]:
    return execute_query(connection_id, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")


def get_table_schema(connection_id: str, table_name: str) -> Dict[str, Any]:
    return execute_query(connection_id, f"PRAGMA table_info({_quote_ident(table_name)})")


def add_column(connection_id: str, table_name: str, column_name: str, column_type: str) -> Dict[str, Any]:
    return execute_query(connection_id, f"ALTER TABLE {_quote_ident(table_name)} ADD COLUMN {_quote_ident(column_name)} {column_type}")


def create_index(connection_id: str, table_name: str, columns: List[str], unique: bool = False) -> Dict[str, Any]:
    idx = f"idx_{table_name}_{'_'.join(columns)}"
    uq = "UNIQUE " if unique else ""
    q = f"CREATE {uq}INDEX IF NOT EXISTS {_quote_ident(idx)} ON {_quote_ident(table_name)} (" + ", ".join(_quote_ident(c) for c in columns) + ")"
    return execute_query(connection_id, q)


def drop_index(connection_id: str, index_name: str) -> Dict[str, Any]:
    return execute_query(connection_id, f"DROP INDEX IF EXISTS {_quote_ident(index_name)}")


def backup_database(connection_id: str, backup_path: str) -> Dict[str, Any]:
    try:
        src = _DB_PATHS[connection_id]
        shutil.copy2(src, backup_path)
        return _ok(backup_path=backup_path)
    except Exception as e:
        return _err(str(e))


def restore_database(backup_path: str, target_path: str) -> Dict[str, Any]:
    try:
        shutil.copy2(backup_path, target_path)
        return _ok(target_path=target_path)
    except Exception as e:
        return _err(str(e))


def export_to_json(connection_id: str, table: str, output_path: str) -> Dict[str, Any]:
    res = select_records(connection_id, table, ["*"])
    if not res["success"]:
        return res
    Path(output_path).write_text(json.dumps(res["rows"], default=str, indent=2))
    return _ok(output_path=output_path)


def import_from_json(connection_id: str, table: str, json_path: str) -> Dict[str, Any]:
    records = json.loads(Path(json_path).read_text())
    return insert_many_records(connection_id, table, records)


def export_to_csv(connection_id: str, table: str, output_path: str) -> Dict[str, Any]:
    res = select_records(connection_id, table, ["*"])
    if not res["success"]:
        return res
    rows = res["rows"]
    if not rows:
        Path(output_path).write_text("")
        return _ok(output_path=output_path)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return _ok(output_path=output_path)


def import_from_csv(connection_id: str, table: str, csv_path: str) -> Dict[str, Any]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return insert_many_records(connection_id, table, rows)


def get_database_size(db_path: str) -> Dict[str, Any]:
    try:
        return _ok(size_bytes=os.path.getsize(db_path))
    except Exception as e:
        return _err(str(e))


def vacuum_database(connection_id: str) -> Dict[str, Any]:
    return execute_query(connection_id, "VACUUM")


def begin_transaction(connection_id: str) -> Dict[str, Any]:
    return execute_query(connection_id, "BEGIN TRANSACTION")


def commit_transaction(connection_id: str) -> Dict[str, Any]:
    try:
        _get_conn(connection_id).commit()
        return _ok()
    except Exception as e:
        return _err(str(e))


def rollback_transaction(connection_id: str) -> Dict[str, Any]:
    try:
        _get_conn(connection_id).rollback()
        return _ok()
    except Exception as e:
        return _err(str(e))


def store_agent_state(connection_id: str, agent_id: str, state_data: Dict[str, Any]) -> Dict[str, Any]:
    create_table(connection_id, "agent_states", {"agent_id": "TEXT PRIMARY KEY", "state_data": "TEXT", "updated_at": "TEXT"})
    return upsert_record(connection_id, "agent_states", {"agent_id": agent_id, "state_data": json.dumps(state_data), "updated_at": datetime.utcnow().isoformat()}, "agent_id")


def load_agent_state(connection_id: str, agent_id: str) -> Dict[str, Any]:
    res = select_records(connection_id, "agent_states", ["state_data"], {"agent_id": agent_id})
    if not res["success"] or not res["rows"]:
        return res
    return _ok(state_data=json.loads(res["rows"][0]["state_data"]))


def log_action(connection_id: str, agent_id: str, action: str, details: Dict[str, Any]) -> Dict[str, Any]:
    create_table(connection_id, "action_logs", {"id": "INTEGER PRIMARY KEY AUTOINCREMENT", "agent_id": "TEXT", "action": "TEXT", "details": "TEXT", "created_at": "TEXT"})
    return insert_record(connection_id, "action_logs", {"agent_id": agent_id, "action": action, "details": json.dumps(details), "created_at": datetime.utcnow().isoformat()})


def get_action_logs(connection_id: str, agent_id: str, limit: int = 100) -> Dict[str, Any]:
    return select_records(connection_id, "action_logs", ["id", "action", "details", "created_at"], {"agent_id": agent_id}, "id", limit)


def store_task_result(connection_id: str, task_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    create_table(connection_id, "task_results", {"task_id": "TEXT PRIMARY KEY", "result": "TEXT", "updated_at": "TEXT"})
    return upsert_record(connection_id, "task_results", {"task_id": task_id, "result": json.dumps(result), "updated_at": datetime.utcnow().isoformat()}, "task_id")


def get_task_result(connection_id: str, task_id: str) -> Dict[str, Any]:
    res = select_records(connection_id, "task_results", ["result"], {"task_id": task_id})
    if not res["success"] or not res["rows"]:
        return res
    return _ok(result=json.loads(res["rows"][0]["result"]))


def search_records(connection_id: str, table: str, column: str, pattern: str) -> Dict[str, Any]:
    return execute_query(connection_id, f"SELECT * FROM {_quote_ident(table)} WHERE {_quote_ident(column)} LIKE ?", [pattern])


def aggregate_query(connection_id: str, table: str, column: str, function: str, where: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    fn = function.upper()
    q = f"SELECT {fn}({_quote_ident(column)}) as value FROM {_quote_ident(table)}"
    params: List[Any] = []
    if where:
        q += " WHERE " + " AND ".join(f"{_quote_ident(k)}=?" for k in where)
        params.extend(where.values())
    return execute_query(connection_id, q, params)


def join_tables(connection_id: str, table1: str, table2: str, on_column: str, columns: List[str]) -> Dict[str, Any]:
    cols = ", ".join(columns)
    q = f"SELECT {cols} FROM {_quote_ident(table1)} JOIN {_quote_ident(table2)} ON {_quote_ident(table1)}.{_quote_ident(on_column)} = {_quote_ident(table2)}.{_quote_ident(on_column)}"
    return execute_query(connection_id, q)


def upsert_record(connection_id: str, table: str, data: Dict[str, Any], conflict_column: str) -> Dict[str, Any]:
    cols = list(data.keys())
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{_quote_ident(c)}=excluded.{_quote_ident(c)}" for c in cols if c != conflict_column)
    q = (
        f"INSERT INTO {_quote_ident(table)} (" + ", ".join(_quote_ident(c) for c in cols) + ") "
        f"VALUES ({placeholders}) ON CONFLICT({_quote_ident(conflict_column)}) DO UPDATE SET {updates}"
    )
    return execute_query(connection_id, q, [data[c] for c in cols])
