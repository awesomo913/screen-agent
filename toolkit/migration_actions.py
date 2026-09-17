import sqlite3
import json
import pathlib
import os
import shutil
import hashlib
import csv
import yaml
import xml.etree.ElementTree as ET
import re
import datetime
from typing import Dict, List, Any, Optional, Union, Sequence
from io import StringIO
from pathlib import Path


def _build_response(success: bool, message: str, data: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
    """Standardized response builder to ensure consistent Dict returns."""
    return {
        "success": success,
        "message": message,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "data": data,
        "error": error
    }


def _hash_data(data: Any) -> str:
    """Generate a SHA-256 hash of stringified data for verification."""
    content = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def migrate_database_schema(db_path: Union[str, Path], migrations: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        db_path = Path(db_path)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _migration_history (
                version INTEGER PRIMARY KEY,
                name TEXT,
                applied_at TEXT,
                up_sql TEXT,
                down_sql TEXT
            )
        """)
        conn.commit()

        applied = []
        for mig in migrations:
            version = mig.get("version")
            up_sql = mig.get("up_sql", "")
            down_sql = mig.get("down_sql", "")
            name = mig.get("name", f"migration_{version}")

            cursor.execute("SELECT COUNT(*) FROM _migration_history WHERE version = ?", (version,))
            if cursor.fetchone()[0] > 0:
                continue

            cursor.executescript(up_sql)
            cursor.execute(
                "INSERT INTO _migration_history (version, name, applied_at, up_sql, down_sql) VALUES (?, ?, ?, ?, ?)",
                (version, name, datetime.datetime.now(datetime.timezone.utc).isoformat(), up_sql, down_sql)
            )
            applied.append(version)
        
        conn.commit()
        conn.close()
        return _build_response(True, f"Successfully applied {len(applied)} migrations.", {"applied_versions": applied})
    except Exception as e:
        return _build_response(False, "Database migration failed.", error=str(e))


def rollback_migration(db_path: Union[str, Path], version: int) -> Dict[str, Any]:
    try:
        db_path = Path(db_path)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT down_sql, name FROM _migration_history WHERE version = ?", (version,))
        row = cursor.fetchone()
        if not row:
            return _build_response(False, f"Migration version {version} not found in history.")
        
        down_sql, name = row
        cursor.executescript(down_sql)
        cursor.execute("DELETE FROM _migration_history WHERE version = ?", (version,))
        conn.commit()
        conn.close()
        return _build_response(True, f"Successfully rolled back migration '{name}' (v{version}).")
    except Exception as e:
        return _build_response(False, f"Rollback failed for version {version}.", error=str(e))


def get_migration_status(db_path: Union[str, Path]) -> Dict[str, Any]:
    try:
        db_path = Path(db_path)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT version, name, applied_at FROM _migration_history ORDER BY version ASC")
        history = [{"version": r[0], "name": r[1], "applied_at": r[2]} for r in cursor.fetchall()]
        conn.close()
        return _build_response(True, "Migration status retrieved.", {"history": history, "current_version": history[-1]["version"] if history else 0})
    except sqlite3.OperationalError:
        return _build_response(True, "No migration history table found.", {"history": [], "current_version": 0})
    except Exception as e:
        return _build_response(False, "Failed to retrieve migration status.", error=str(e))


def create_migration(name: str, up_sql: str, down_sql: str, output: Union[str, Path]) -> Dict[str, Any]:
    try:
        output = Path(output)
        migration_data = {
            "name": name,
            "version": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
            "up_sql": up_sql,
            "down_sql": down_sql,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "checksum": hashlib.md5((up_sql + down_sql).encode()).hexdigest()
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(migration_data, f, indent=2)
        return _build_response(True, f"Migration file created at {output}", {"path": str(output), "version": migration_data["version"]})
    except Exception as e:
        return _build_response(False, "Failed to create migration file.", error=str(e))


def apply_pending_migrations(db_path: Union[str, Path], migrations_dir: Union[str, Path]) -> Dict[str, Any]:
    try:
        db_path = Path(db_path)
        migrations_dir = Path(migrations_dir)
        if not migrations_dir.exists():
            return _build_response(False, "Migrations directory does not exist.")

        # Get applied versions
        status = get_migration_status(db_path)
        applied_versions = {m["version"] for m in status.get("data", {}).get("history", [])}

        files = sorted(migrations_dir.glob("*.json"))
        pending = []
        for f in files:
            with open(f, "r", encoding="utf-8") as fh:
                mig = json.load(fh)
            if mig["version"] not in applied_versions:
                pending.append(mig)

        return migrate_database_schema(db_path, pending)
    except Exception as e:
        return _build_response(False, "Failed to apply pending migrations.", error=str(e))


def export_data_csv(db_path: Union[str, Path], table: str, output: Union[str, Path]) -> Dict[str, Any]:
    try:
        db_path = Path(db_path)
        output = Path(output)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        headers = [description[0] for description in cursor.description]
        
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(zip(headers, row)))
        conn.close()
        return _build_response(True, f"Exported {len(rows)} rows to CSV.", {"path": str(output), "row_count": len(rows)})
    except Exception as e:
        return _build_response(False, f"CSV export failed for table '{table}'.", error=str(e))


def import_data_csv(db_path: Union[str, Path], table: str, csv_path: Union[str, Path]) -> Dict[str, Any]:
    try:
        db_path = Path(db_path)
        csv_path = Path(csv_path)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            placeholders = ", ".join(["?"] * len(headers))
            cols = ", ".join(headers)
            insert_query = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"
            
            batch = []
            count = 0
            for row in reader:
                batch.append([row[h] for h in headers])
                count += 1
        
        if batch:
            cursor.executemany(insert_query, batch)
        conn.commit()
        conn.close()
        return _build_response(True, f"Imported {count} rows to '{table}'.", {"row_count": count})
    except Exception as e:
        return _build_response(False, f"CSV import failed for table '{table}'.", error=str(e))


def export_data_json(db_path: Union[str, Path], table: str, output: Union[str, Path]) -> Dict[str, Any]:
    try:
        db_path = Path(db_path)
        output = Path(output)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        headers = [description[0] for description in cursor.description]
        
        data = [dict(zip(headers, row)) for row in rows]
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        conn.close()
        return _build_response(True, f"Exported {len(data)} rows to JSON.", {"path": str(output), "row_count": len(data)})
    except Exception as e:
        return _build_response(False, f"JSON export failed for table '{table}'.", error=str(e))


def import_data_json(db_path: Union[str, Path], table: str, json_path: Union[str, Path]) -> Dict[str, Any]:
    try:
        db_path = Path(db_path)
        json_path = Path(json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list) or not data:
            return _build_response(False, "JSON file must contain a list of objects.")
            
        headers = list(data[0].keys())
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        placeholders = ", ".join(["?"] * len(headers))
        cols = ", ".join(headers)
        insert_query = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"
        
        batch = [[row.get(h) for h in headers] for row in data]
        cursor.executemany(insert_query, batch)
        conn.commit()
        conn.close()
        return _build_response(True, f"Imported {len(batch)} rows to '{table}'.", {"row_count": len(batch)})
    except Exception as e:
        return _build_response(False, f"JSON import failed for table '{table}'.", error=str(e))


def convert_csv_to_json(csv_path: Union[str, Path], output: Union[str, Path]) -> Dict[str, Any]:
    try:
        csv_path = Path(csv_path)
        output = Path(output)
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            data = list(reader)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return _build_response(True, f"Converted CSV to JSON ({len(data)} records).", {"path": str(output), "count": len(data)})
    except Exception as e:
        return _build_response(False, "CSV to JSON conversion failed.", error=str(e))


def convert_json_to_csv(json_path: Union[str, Path], output: Union[str, Path]) -> Dict[str, Any]:
    try:
        json_path = Path(json_path)
        output = Path(output)
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data:
            return _build_response(False, "JSON data is empty.")
            
        # Flatten nested dicts if needed, otherwise use first record keys
        headers = []
        for item in data:
            for k in item.keys():
                if k not in headers:
                    headers.append(k)
                    
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            for row in data:
                writer.writerow(row)
        return _build_response(True, f"Converted JSON to CSV ({len(data)} records).", {"path": str(output), "count": len(data)})
    except Exception as e:
        return _build_response(False, "JSON to CSV conversion failed.", error=str(e))


def _xml_element_to_dict(element: ET.Element) -> Dict[str, Any]:
    """Recursively convert XML element to dictionary."""
    node = {element.tag: {} if element.attrib else element.text}
    children = list(element)
    if children:
        child_dict = {}
        for child in children:
            child_tag = child.tag
            child_val = _xml_element_to_dict(child)
            if child_tag in child_dict:
                if not isinstance(child_dict[child_tag], list):
                    child_dict[child_tag] = [child_dict[child_tag]]
                child_dict[child_tag].append(child_val)
            else:
                child_dict[child_tag] = child_val
        node = {element.tag: child_dict}
    if element.attrib:
        node[element.tag].update({"@" + k: v for k, v in element.attrib.items()})
    return node


def convert_xml_to_json(xml_path: Union[str, Path], output: Union[str, Path]) -> Dict[str, Any]:
    try:
        xml_path = Path(xml_path)
        output = Path(output)
        tree = ET.parse(xml_path)
        root = tree.getroot()
        data = _xml_element_to_dict(root)
        
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return _build_response(True, "XML to JSON conversion successful.", {"path": str(output)})
    except Exception as e:
        return _build_response(False, "XML to JSON conversion failed.", error=str(e))


def _dict_to_xml_element(data: Dict, parent: Optional[ET.Element] = None, root_tag: str = "root") -> ET.Element:
    """Recursively convert dictionary to XML element."""
    if parent is None:
        root = ET.Element(root_tag)
    else:
        root = parent
        
    if isinstance(data, dict):
        for key, value in data.items():
            if key.startswith("@"):
                root.set(key[1:], str(value))
            elif isinstance(value, dict):
                _dict_to_xml_element(value, ET.SubElement(root, key))
            elif isinstance(value, list):
                for item in value:
                    _dict_to_xml_element(item, ET.SubElement(root, key))
            else:
                child = ET.SubElement(root, key)
                child.text = str(value) if value is not None else ""
    return root


def convert_json_to_xml(json_path: Union[str, Path], root_tag: str, output: Union[str, Path]) -> Dict[str, Any]:
    try:
        json_path = Path(json_path)
        output = Path(output)
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        root = ET.Element(root_tag) if isinstance(data, list) else _dict_to_xml_element(data, None, root_tag)
        if isinstance(data, list):
            for item in data:
                _dict_to_xml_element(item, root)
                
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        output.parent.mkdir(parents=True, exist_ok=True)
        tree.write(output, encoding="utf-8", xml_declaration=True)
        return _build_response(True, f"JSON to XML conversion successful.", {"path": str(output), "root_tag": root_tag})
    except Exception as e:
        return _build_response(False, "JSON to XML conversion failed.", error=str(e))


def convert_yaml_to_json(yaml_path: Union[str, Path], output: Union[str, Path]) -> Dict[str, Any]:
    try:
        yaml_path = Path(yaml_path)
        output = Path(output)
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return _build_response(True, "YAML to JSON conversion successful.", {"path": str(output)})
    except Exception as e:
        return _build_response(False, "YAML to JSON conversion failed.", error=str(e))


def convert_json_to_yaml(json_path: Union[str, Path], output: Union[str, Path]) -> Dict[str, Any]:
    try:
        json_path = Path(json_path)
        output = Path(output)
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        return _build_response(True, "JSON to YAML conversion successful.", {"path": str(output)})
    except Exception as e:
        return _build_response(False, "JSON to YAML conversion failed.", error=str(e))


def migrate_file_structure(source: Union[str, Path], rules: Dict[str, str], dest: Union[str, Path]) -> Dict[str, Any]:
    try:
        source = Path(source)
        dest = Path(dest)
        if not source.exists():
            return _build_response(False, "Source directory does not exist.")
            
        dest.mkdir(parents=True, exist_ok=True)
        moved = 0
        skipped = 0
        
        for item in source.rglob("*"):
            if not item.is_file():
                continue
            relative = item.relative_to(source)
            moved_flag = False
            for pattern, target_dir in rules.items():
                if re.search(pattern, item.name):
                    target_path = dest / target_dir / item.name
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(item), str(target_path))
                    moved_flag = True
                    moved += 1
                    break
            if not moved_flag:
                skipped += 1
                
        return _build_response(True, f"Structure migration complete.", {"moved": moved, "skipped": skipped})
    except Exception as e:
        return _build_response(False, "File structure migration failed.", error=str(e))


def batch_rename_files(directory: Union[str, Path], pattern: str, replacement: str) -> Dict[str, Any]:
    try:
        directory = Path(directory)
        if not directory.is_dir():
            return _build_response(False, "Invalid directory path.")
            
        renamed = 0
        for filepath in directory.iterdir():
            if filepath.is_file():
                new_name = re.sub(pattern, replacement, filepath.name)
                if new_name != filepath.name:
                    new_path = directory / new_name
                    if not new_path.exists():
                        shutil.move(str(filepath), str(new_path))
                        renamed += 1
        return _build_response(True, f"Batch rename complete.", {"renamed_count": renamed})
    except Exception as e:
        return _build_response(False, "Batch rename failed.", error=str(e))


def transform_data(data: List[Dict[str, Any]], transformations: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        results = [row.copy() for row in data]
        for rule in transformations:
            op = rule.get("op", "").lower()
            fields = rule.get("fields", []) or [rule.get("field")]
            value = rule.get("value")
            
            for row in results:
                for field in fields:
                    if field not in row or row[field] is None:
                        continue
                    if op == "lowercase": row[field] = str(row[field]).lower()
                    elif op == "uppercase": row[field] = str(row[field]).upper()
                    elif op == "strip": row[field] = str(row[field]).strip()
                    elif op == "replace": row[field] = str(row[field]).replace(value[0], value[1])
                    elif op == "type_cast": row[field] = eval(f"{value}({row[field]})")
                    elif op == "default" and not row[field]: row[field] = value
                    
        return _build_response(True, f"Applied {len(transformations)} transformations.", {"transformed_count": len(results)})
    except Exception as e:
        return _build_response(False, "Data transformation failed.", error=str(e))


def validate_data_schema(data: List[Dict[str, Any]], schema: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    try:
        errors = []
        for i, row in enumerate(data):
            for field, rules in schema.get("fields", {}).items():
                if rules.get("required", False) and field not in row:
                    errors.append({"row": i, "error": f"Missing required field: {field}"})
                elif field in row:
                    expected_type = rules.get("type", "str")
                    actual_type = type(row[field]).__name__
                    type_map = {"str": str, "int": int, "float": float, "bool": bool}
                    if expected_type in type_map and not isinstance(row[field], type_map[expected_type]):
                        errors.append({"row": i, "error": f"Invalid type for {field}. Expected {expected_type}, got {actual_type}"})
        valid = len(errors) == 0
        return _build_response(valid, "Schema validation passed." if valid else "Schema validation failed.", {"errors": errors, "valid": valid})
    except Exception as e:
        return _build_response(False, "Schema validation failed.", error=str(e))


def merge_data_files(files: List[Union[str, Path]], output: Union[str, Path], format: str = "json") -> Dict[str, Any]:
    try:
        output = Path(output)
        merged = []
        for f_path in files:
            f_path = Path(f_path)
            if format == "json":
                with open(f_path, "r") as f: merged.extend(json.load(f))
            elif format == "csv":
                with open(f_path, "r", newline="", encoding="utf-8") as f:
                    merged.extend(list(csv.DictReader(f)))
        
        output.parent.mkdir(parents=True, exist_ok=True)
        if format == "json":
            with open(output, "w") as f: json.dump(merged, f, indent=2)
        elif format == "csv" and merged:
            headers = merged[0].keys()
            with open(output, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=headers); writer.writeheader(); writer.writerows(merged)
        return _build_response(True, f"Merged {len(files)} files.", {"total_records": len(merged), "output": str(output)})
    except Exception as e:
        return _build_response(False, "File merge failed.", error=str(e))


def split_data_file(filepath: Union[str, Path], chunks: int, output_dir: Union[str, Path]) -> Dict[str, Any]:
    try:
        filepath = Path(filepath)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        ext = filepath.suffix.lower()
        if ext == ".json":
            with open(filepath, "r") as f: data = json.load(f)
        elif ext == ".csv":
            with open(filepath, "r", newline="", encoding="utf-8") as f: data = list(csv.DictReader(f))
        else:
            return _build_response(False, "Unsupported file format for splitting.")
            
        chunk_size = max(1, len(data) // chunks)
        filenames = []
        for i in range(chunks):
            start = i * chunk_size
            end = start + chunk_size if i < chunks - 1 else len(data)
            chunk_data = data[start:end]
            out_file = output_dir / f"{filepath.stem}_chunk_{i+1}{ext}"
            filenames.append(str(out_file))
            with open(out_file, "w" if ext == ".json" else open(out_file, "w", newline="")) as f:
                if ext == ".json": json.dump(chunk_data, f)
                else: csv.DictWriter(f, fieldnames=data[0].keys()).writeheader(); csv.DictWriter(f, fieldnames=data[0].keys()).writerows(chunk_data)
        return _build_response(True, f"Split file into {chunks} chunks.", {"files": filenames, "chunks": len(filenames)})
    except Exception as e:
        return _build_response(False, "File split failed.", error=str(e))


def deduplicate_data(data: List[Dict[str, Any]], key_fields: List[str]) -> Dict[str, Any]:
    try:
        seen = set()
        unique = []
        for row in data:
            key = tuple(str(row.get(k, "")) for k in key_fields)
            if key not in seen:
                seen.add(key)
                unique.append(row)
        return _build_response(True, f"Deduplication complete.", {"original": len(data), "unique": len(unique), "removed": len(data) - len(unique)})
    except Exception as e:
        return _build_response(False, "Deduplication failed.", error=str(e))


def map_fields(data: List[Dict[str, Any]], field_mapping: Dict[str, str]) -> Dict[str, Any]:
    try:
        result = []
        for row in data:
            mapped = {field_mapping.get(k, k): v for k, v in row.items()}
            result.append(mapped)
        return _build_response(True, "Field mapping applied.", {"mapped_count": len(result)})
    except Exception as e:
        return _build_response(False, "Field mapping failed.", error=str(e))


def create_migration_plan(source_schema: Dict[str, Any], target_schema: Dict[str, Any]) -> Dict[str, Any]:
    try:
        src_fields = set(source_schema.get("fields", {}).keys())
        tgt_fields = set(target_schema.get("fields", {}).keys())
        plan = {
            "add_fields": list(tgt_fields - src_fields),
            "remove_fields": list(src_fields - tgt_fields),
            "common_fields": list(src_fields & tgt_fields),
            "actions": []
        }
        for f in plan["add_fields"]: plan["actions"].append({"type": "ALTER_TABLE_ADD", "field": f})
        for f in plan["remove_fields"]: plan["actions"].append({"type": "ALTER_TABLE_DROP", "field": f})
        return _build_response(True, "Migration plan generated.", {"plan": plan})
    except Exception as e:
        return _build_response(False, "Plan generation failed.", error=str(e))


def verify_migration(before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        before_hash = _hash_data(before)
        after_hash = _hash_data(after)
        checks = {
            "record_count_match": len(before) == len(after),
            "data_integrity": before_hash == after_hash,
            "counts": {"before": len(before), "after": len(after)}
        }
        success = checks["record_count_match"] and checks["data_integrity"]
        return _build_response(success, "Migration verification complete.", {"checks": checks})
    except Exception as e:
        return _build_response(False, "Verification failed.", error=str(e))