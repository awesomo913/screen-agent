"""
toolkit_54_archive_inspector.py
Inspect contents of ZIP, 7z, RAR, TAR archives without fully extracting.
List files, get metadata, extract specific files, test integrity. Stdlib + soft-imports.
"""
from __future__ import annotations
import zipfile
import tarfile
import os
from pathlib import Path
from typing import Any, Dict, List

try:
    import py7zr
    HAS_7Z = True
except ImportError:
    HAS_7Z = False

try:
    import rarfile
    HAS_RAR = True
except ImportError:
    HAS_RAR = False

def list_zip_contents(path: str) -> Dict[str, Any]:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            infos = []
            for info in zf.infolist():
                infos.append({
                    "filename": info.filename,
                    "size": info.file_size,
                    "compressed_size": info.compress_size,
                    "ratio": round((1 - info.compress_size / max(info.file_size, 1)) * 100, 1) if info.file_size else 0,
                    "date": str(info.date_time),
                    "is_dir": info.filename.endswith("/")
                })
            total_size = sum(i["size"] for i in infos)
            return {"success": True, "data": {"file_count": len(infos), "total_size": total_size, "files": infos}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_zip(path: str, output_folder: str, password: str = "") -> Dict[str, Any]:
    try:
        os.makedirs(output_folder, exist_ok=True)
        with zipfile.ZipFile(path, "r") as zf:
            if password:
                zf.extractall(output_folder, pwd=password.encode())
            else:
                zf.extractall(output_folder)
        return {"success": True, "data": {"extracted_to": output_folder}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_zip_file(zip_path: str, filename: str, output_folder: str) -> Dict[str, Any]:
    try:
        os.makedirs(output_folder, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extract(filename, output_folder)
        return {"success": True, "data": {"extracted": filename, "to": output_folder}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def test_zip_integrity(path: str) -> Dict[str, Any]:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            bad = zf.testzip()
        return {"success": True, "data": {"valid": bad is None, "first_bad": bad}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_zip(output_path: str, source_files: list) -> Dict[str, Any]:
    """Create a ZIP from a list of file paths."""
    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fp in source_files:
                zf.write(fp, os.path.basename(fp))
        return {"success": True, "data": {"created": output_path, "files": len(source_files)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_zip_from_folder(folder: str, output_path: str) -> Dict[str, Any]:
    try:
        count = 0
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    fp = os.path.join(root, f)
                    arcname = os.path.relpath(fp, folder)
                    zf.write(fp, arcname)
                    count += 1
        return {"success": True, "data": {"created": output_path, "files": count}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_zip_info(path: str) -> Dict[str, Any]:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            count = len(zf.infolist())
            total = sum(i.file_size for i in zf.infolist())
            compressed = sum(i.compress_size for i in zf.infolist())
        archive_size = os.path.getsize(path)
        return {"success": True, "data": {
            "path": path,
            "files": count,
            "uncompressed_mb": round(total / 1048576, 2),
            "compressed_mb": round(compressed / 1048576, 2),
            "archive_size_mb": round(archive_size / 1048576, 2),
            "ratio": round((1 - compressed / max(total, 1)) * 100, 1)
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def is_zip_encrypted(path: str) -> Dict[str, Any]:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            for info in zf.infolist():
                if info.flag_bits & 0x1:
                    return {"success": True, "data": True, "error": None}
        return {"success": True, "data": False, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_tar_contents(path: str) -> Dict[str, Any]:
    try:
        with tarfile.open(path, "r:*") as tf:
            members = []
            for m in tf.getmembers():
                members.append({
                    "name": m.name,
                    "size": m.size,
                    "is_dir": m.isdir(),
                    "is_file": m.isfile(),
                    "mode": oct(m.mode)
                })
            return {"success": True, "data": {"count": len(members), "files": members}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_tar(path: str, output_folder: str) -> Dict[str, Any]:
    try:
        os.makedirs(output_folder, exist_ok=True)
        with tarfile.open(path, "r:*") as tf:
            tf.extractall(output_folder)
        return {"success": True, "data": {"extracted_to": output_folder}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_tar_gz(output_path: str, source_folder: str) -> Dict[str, Any]:
    try:
        with tarfile.open(output_path, "w:gz") as tf:
            tf.add(source_folder, arcname=os.path.basename(source_folder))
        return {"success": True, "data": {"created": output_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_7z_contents(path: str) -> Dict[str, Any]:
    try:
        if not HAS_7Z:
            return {"success": False, "data": None, "error": "py7zr not installed (pip install py7zr)"}
        with py7zr.SevenZipFile(path, mode="r") as zf:
            files = []
            for info in zf.list():
                files.append({"filename": info.filename, "size": info.uncompressed, "is_dir": info.is_directory})
            return {"success": True, "data": {"count": len(files), "files": files}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_7z(path: str, output_folder: str) -> Dict[str, Any]:
    try:
        if not HAS_7Z:
            return {"success": False, "data": None, "error": "py7zr not installed"}
        os.makedirs(output_folder, exist_ok=True)
        with py7zr.SevenZipFile(path, mode="r") as zf:
            zf.extractall(output_folder)
        return {"success": True, "data": {"extracted_to": output_folder}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def detect_archive_type(path: str) -> Dict[str, Any]:
    try:
        ext = Path(path).suffix.lower()
        types = {".zip": "ZIP", ".tar": "TAR", ".gz": "GZIP", ".bz2": "BZIP2",
                 ".7z": "7-Zip", ".rar": "RAR", ".tgz": "TAR+GZIP"}
        detected = types.get(ext, "unknown")
        return {"success": True, "data": {"type": detected, "extension": ext}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_libraries() -> Dict[str, Any]:
    return {"success": True, "data": {"py7zr": HAS_7Z, "rarfile": HAS_RAR, "zipfile": True, "tarfile": True}, "error": None}
