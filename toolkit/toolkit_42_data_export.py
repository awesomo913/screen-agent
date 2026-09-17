"""
toolkit_42_data_export.py
Export data to various formats: CSV, JSON, HTML table, Markdown table,
XML, YAML, TSV, SQLite. Stdlib only (YAML uses PyYAML soft-import).
"""
from __future__ import annotations
import csv
import json
import os
import sqlite3
import xml.etree.ElementTree as ET
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

def list_to_csv(data: list, output_path: str, headers: list = []) -> Dict[str, Any]:
    """Write list of lists to CSV file."""
    try:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if headers:
                writer.writerow(headers)
            writer.writerows(data)
        return {"success": True, "data": {"saved": output_path, "rows": len(data)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def dicts_to_csv(records: list, output_path: str) -> Dict[str, Any]:
    """Write list of dicts to CSV file."""
    try:
        if not records:
            return {"success": False, "data": None, "error": "Empty records list"}
        keys = list(records[0].keys())
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(records)
        return {"success": True, "data": {"saved": output_path, "rows": len(records), "columns": keys}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def to_json_file(data: dict, output_path: str, indent: int = 2) -> Dict[str, Any]:
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
        return {"success": True, "data": {"saved": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def to_jsonl_file(records: list, output_path: str) -> Dict[str, Any]:
    """Write list of records to JSONL (JSON Lines) format."""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        return {"success": True, "data": {"saved": output_path, "rows": len(records)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def dicts_to_html_table(records: list, output_path: str, title: str = "Data Table") -> Dict[str, Any]:
    try:
        if not records:
            return {"success": False, "data": None, "error": "Empty records"}
        keys = list(records[0].keys())
        rows_html = ""
        for r in records:
            cells = "".join("<td>" + str(r.get(k, "")) + "</td>" for k in keys)
            rows_html += "<tr>" + cells + "</tr>\n"
        header_html = "".join("<th>" + k + "</th>" for k in keys)
        html = """<!DOCTYPE html>
<html><head><title>""" + title + """</title>
<style>table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:8px;text-align:left}th{background:#4472C4;color:white}tr:nth-child(even){background:#f2f2f2}</style>
</head><body>
<h1>""" + title + """</h1>
<table><thead><tr>""" + header_html + """</tr></thead>
<tbody>""" + rows_html + """</tbody></table>
</body></html>"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        return {"success": True, "data": {"saved": output_path, "rows": len(records)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def dicts_to_markdown_table(records: list) -> Dict[str, Any]:
    """Convert list of dicts to a Markdown table string."""
    try:
        if not records:
            return {"success": False, "data": None, "error": "Empty records"}
        keys = list(records[0].keys())
        header = "| " + " | ".join(keys) + " |"
        separator = "| " + " | ".join(["---"] * len(keys)) + " |"
        rows = ["| " + " | ".join(str(r.get(k, "")) for k in keys) + " |" for r in records]
        table = "\n".join([header, separator] + rows)
        return {"success": True, "data": table, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def dicts_to_xml(records: list, output_path: str, root_tag: str = "records", item_tag: str = "record") -> Dict[str, Any]:
    try:
        root = ET.Element(root_tag)
        for r in records:
            item = ET.SubElement(root, item_tag)
            for k, v in r.items():
                child = ET.SubElement(item, str(k))
                child.text = str(v)
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(output_path, encoding="unicode", xml_declaration=True)
        return {"success": True, "data": {"saved": output_path, "rows": len(records)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def to_yaml_file(data: dict, output_path: str) -> Dict[str, Any]:
    try:
        if not HAS_YAML:
            return {"success": False, "data": None, "error": "PyYAML not installed (pip install pyyaml)"}
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        return {"success": True, "data": {"saved": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def dicts_to_tsv(records: list, output_path: str) -> Dict[str, Any]:
    try:
        if not records:
            return {"success": False, "data": None, "error": "Empty records"}
        keys = list(records[0].keys())
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            f.write("\t".join(keys) + "\n")
            for r in records:
                f.write("\t".join(str(r.get(k, "")) for k in keys) + "\n")
        return {"success": True, "data": {"saved": output_path, "rows": len(records)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def dicts_to_sqlite(records: list, db_path: str, table_name: str = "data") -> Dict[str, Any]:
    try:
        if not records:
            return {"success": False, "data": None, "error": "Empty records"}
        keys = list(records[0].keys())
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cols = ", ".join('"' + k + '" TEXT' for k in keys)
        cursor.execute('CREATE TABLE IF NOT EXISTS "' + table_name + '" (' + cols + ')')
        for r in records:
            vals = [str(r.get(k, "")) for k in keys]
            placeholders = ", ".join(["?"] * len(keys))
            cursor.execute('INSERT INTO "' + table_name + '" VALUES (' + placeholders + ')', vals)
        conn.commit()
        conn.close()
        return {"success": True, "data": {"db": db_path, "table": table_name, "rows": len(records)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def csv_to_json(csv_path: str, json_path: str) -> Dict[str, Any]:
    try:
        records = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            records = list(reader)
        return to_json_file(records, json_path)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def json_to_csv(json_path: str, csv_path: str) -> Dict[str, Any]:
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            data = [data]
        return dicts_to_csv(data, csv_path)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def flatten_dict(d: dict, separator: str = ".", prefix: str = "") -> Dict[str, Any]:
    """Flatten a nested dict to a single-level dict."""
    try:
        items: dict = {}
        for k, v in d.items():
            new_key = prefix + separator + k if prefix else k
            if isinstance(v, dict):
                sub = flatten_dict(v, separator, new_key)
                items.update(sub["data"])
            else:
                items[new_key] = v
        return {"success": True, "data": items, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_libraries() -> Dict[str, Any]:
    return {"success": True, "data": {"yaml": HAS_YAML}, "error": None}
