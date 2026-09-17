"""
toolkit_43_sqlite_manager.py
Create, query, and manage SQLite databases: tables, indexes, CRUD,
schema inspection, backup, and full-text search.
"""
from __future__ import annotations
import sqlite3
import json
import os
from pathlib import Path
from typing import Any, Dict, List

def create_database(db_path: str) -> Dict[str, Any]:
    try:
        conn = sqlite3.connect(db_path)
        conn.close()
        return {"success": True, "data": {"created": db_path, "exists": True}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_table(db_path: str, table_name: str, columns: dict) -> Dict[str, Any]:
    """columns: {col_name: col_type} e.g. {'id': 'INTEGER PRIMARY KEY', 'name': 'TEXT'}"""
    try:
        conn = sqlite3.connect(db_path)
        col_defs = ", ".join(k + " " + v for k, v in columns.items())
        conn.execute('CREATE TABLE IF NOT EXISTS "' + table_name + '" (' + col_defs + ')')
        conn.commit()
        conn.close()
        return {"success": True, "data": "Table created: " + table_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def drop_table(db_path: str, table_name: str) -> Dict[str, Any]:
    try:
        conn = sqlite3.connect(db_path)
        conn.execute('DROP TABLE IF EXISTS "' + table_name + '"')
        conn.commit()
        conn.close()
        return {"success": True, "data": "Table dropped: " + table_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_tables(db_path: str) -> Dict[str, Any]:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return {"success": True, "data": tables, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_table_schema(db_path: str, table_name: str) -> Dict[str, Any]:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute('PRAGMA table_info("' + table_name + '")')
        cols = [{"cid": r[0], "name": r[1], "type": r[2], "notnull": r[3], "default": r[4], "pk": r[5]} for r in cursor.fetchall()]
        conn.close()
        return {"success": True, "data": cols, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def insert_row(db_path: str, table_name: str, row: dict) -> Dict[str, Any]:
    try:
        conn = sqlite3.connect(db_path)
        keys = list(row.keys())
        placeholders = ", ".join(["?"] * len(keys))
        sql = 'INSERT INTO "' + table_name + '" ("' + '", "'.join(keys) + '") VALUES (' + placeholders + ')'
        cursor = conn.execute(sql, list(row.values()))
        conn.commit()
        rowid = cursor.lastrowid
        conn.close()
        return {"success": True, "data": {"rowid": rowid}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def insert_many(db_path: str, table_name: str, rows: list) -> Dict[str, Any]:
    try:
        if not rows:
            return {"success": False, "data": None, "error": "Empty rows"}
        keys = list(rows[0].keys())
        placeholders = ", ".join(["?"] * len(keys))
        sql = 'INSERT INTO "' + table_name + '" ("' + '", "'.join(keys) + '") VALUES (' + placeholders + ')'
        conn = sqlite3.connect(db_path)
        conn.executemany(sql, [list(r.values()) for r in rows])
        conn.commit()
        conn.close()
        return {"success": True, "data": {"inserted": len(rows)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def query(db_path: str, sql: str, params: list = []) -> Dict[str, Any]:
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql, params)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return {"success": True, "data": {"rows": rows, "count": len(rows)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_all(db_path: str, table_name: str, limit: int = 100) -> Dict[str, Any]:
    return query(db_path, 'SELECT * FROM "' + table_name + '" LIMIT ?', [limit])

def update_rows(db_path: str, table_name: str, updates: dict, where: str, where_params: list = []) -> Dict[str, Any]:
    try:
        set_clause = ", ".join('"' + k + '"=?' for k in updates.keys())
        sql = 'UPDATE "' + table_name + '" SET ' + set_clause + ' WHERE ' + where
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(sql, list(updates.values()) + where_params)
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return {"success": True, "data": {"rows_affected": affected}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def delete_rows(db_path: str, table_name: str, where: str, where_params: list = []) -> Dict[str, Any]:
    try:
        sql = 'DELETE FROM "' + table_name + '" WHERE ' + where
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(sql, where_params)
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return {"success": True, "data": {"rows_deleted": affected}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def count_rows(db_path: str, table_name: str) -> Dict[str, Any]:
    try:
        result = query(db_path, 'SELECT COUNT(*) as cnt FROM "' + table_name + '"')
        count = result["data"]["rows"][0]["cnt"] if result["success"] else 0
        return {"success": True, "data": count, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_index(db_path: str, table_name: str, column_name: str, unique: bool = False) -> Dict[str, Any]:
    try:
        idx_name = "idx_" + table_name + "_" + column_name
        unique_str = "UNIQUE " if unique else ""
        conn = sqlite3.connect(db_path)
        conn.execute('CREATE ' + unique_str + 'INDEX IF NOT EXISTS "' + idx_name + '" ON "' + table_name + '" ("' + column_name + '")')
        conn.commit()
        conn.close()
        return {"success": True, "data": "Index created: " + idx_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def backup_database(db_path: str, backup_path: str) -> Dict[str, Any]:
    try:
        source = sqlite3.connect(db_path)
        dest = sqlite3.connect(backup_path)
        source.backup(dest)
        source.close()
        dest.close()
        return {"success": True, "data": {"backed_up_to": backup_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_database_info(db_path: str) -> Dict[str, Any]:
    try:
        conn = sqlite3.connect(db_path)
        tables_cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in tables_cursor.fetchall()]
        table_info = {}
        for t in tables:
            c = conn.execute('SELECT COUNT(*) FROM "' + t + '"').fetchone()[0]
            table_info[t] = {"rows": c}
        size_kb = round(os.path.getsize(db_path) / 1024, 1) if os.path.isfile(db_path) else 0
        conn.close()
        return {"success": True, "data": {"path": db_path, "tables": table_info, "size_kb": size_kb}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def vacuum_database(db_path: str) -> Dict[str, Any]:
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("VACUUM")
        conn.close()
        return {"success": True, "data": "Database vacuumed", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
