"""
toolkit_31_file_hash.py
Compute and verify file hashes (MD5, SHA1, SHA256, SHA512, CRC32).
Supports single files, directories, and hash comparison. Stdlib only.
"""
from __future__ import annotations
import hashlib
import os
import zlib
from pathlib import Path
from typing import Any, Dict, List

def hash_file(path: str, algorithm: str = "sha256") -> Dict[str, Any]:
    try:
        h = hashlib.new(algorithm)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return {"success": True, "data": {"path": path, "algorithm": algorithm, "hash": h.hexdigest()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def hash_file_md5(path: str) -> Dict[str, Any]:
    return hash_file(path, "md5")

def hash_file_sha1(path: str) -> Dict[str, Any]:
    return hash_file(path, "sha1")

def hash_file_sha256(path: str) -> Dict[str, Any]:
    return hash_file(path, "sha256")

def hash_file_sha512(path: str) -> Dict[str, Any]:
    return hash_file(path, "sha512")

def hash_file_crc32(path: str) -> Dict[str, Any]:
    try:
        crc = 0
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                crc = zlib.crc32(chunk, crc)
        return {"success": True, "data": {"path": path, "algorithm": "crc32", "hash": format(crc & 0xFFFFFFFF, "08x")}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def hash_string(text: str, algorithm: str = "sha256") -> Dict[str, Any]:
    try:
        h = hashlib.new(algorithm)
        h.update(text.encode("utf-8"))
        return {"success": True, "data": {"algorithm": algorithm, "hash": h.hexdigest()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def hash_bytes(data: list, algorithm: str = "sha256") -> Dict[str, Any]:
    """Hash raw bytes provided as a list of ints."""
    try:
        h = hashlib.new(algorithm)
        h.update(bytes(data))
        return {"success": True, "data": {"algorithm": algorithm, "hash": h.hexdigest()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def verify_file_hash(path: str, expected_hash: str, algorithm: str = "sha256") -> Dict[str, Any]:
    try:
        result = hash_file(path, algorithm)
        if not result["success"]:
            return result
        actual = result["data"]["hash"]
        match = actual.lower() == expected_hash.lower()
        return {"success": True, "data": {"match": match, "expected": expected_hash.lower(), "actual": actual}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def compare_files_by_hash(path1: str, path2: str, algorithm: str = "sha256") -> Dict[str, Any]:
    try:
        h1 = hash_file(path1, algorithm)
        h2 = hash_file(path2, algorithm)
        if not h1["success"] or not h2["success"]:
            return {"success": False, "data": None, "error": "Could not hash one or both files"}
        identical = h1["data"]["hash"] == h2["data"]["hash"]
        return {"success": True, "data": {
            "identical": identical,
            path1: h1["data"]["hash"],
            path2: h2["data"]["hash"]
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def hash_directory(folder: str, algorithm: str = "sha256", recursive: bool = True) -> Dict[str, Any]:
    """Hash all files in a directory, return a dict of path->hash."""
    try:
        results = {}
        if recursive:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    fp = os.path.join(root, f)
                    r = hash_file(fp, algorithm)
                    rel = os.path.relpath(fp, folder)
                    results[rel] = r["data"]["hash"] if r["success"] else "ERROR: " + str(r["error"])
        else:
            for f in os.listdir(folder):
                fp = os.path.join(folder, f)
                if os.path.isfile(fp):
                    r = hash_file(fp, algorithm)
                    results[f] = r["data"]["hash"] if r["success"] else "ERROR: " + str(r["error"])
        return {"success": True, "data": {"count": len(results), "hashes": results}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_duplicate_files(folder: str, algorithm: str = "md5") -> Dict[str, Any]:
    """Find files with identical content by hash."""
    try:
        hash_map: dict = {}
        for root, dirs, files in os.walk(folder):
            for f in files:
                fp = os.path.join(root, f)
                r = hash_file(fp, algorithm)
                if r["success"]:
                    h = r["data"]["hash"]
                    if h not in hash_map:
                        hash_map[h] = []
                    hash_map[h].append(fp)
        dupes = {h: paths for h, paths in hash_map.items() if len(paths) > 1}
        total_dupes = sum(len(v) - 1 for v in dupes.values())
        return {"success": True, "data": {"duplicate_groups": len(dupes), "total_duplicate_files": total_dupes, "groups": dupes}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def save_hash_manifest(folder: str, output_file: str, algorithm: str = "sha256") -> Dict[str, Any]:
    """Save a file listing all hashes in a folder (like a checksum file)."""
    try:
        lines = []
        for root, dirs, files in os.walk(folder):
            for f in sorted(files):
                fp = os.path.join(root, f)
                r = hash_file(fp, algorithm)
                rel = os.path.relpath(fp, folder)
                if r["success"]:
                    lines.append(r["data"]["hash"] + "  " + rel)
        with open(output_file, "w") as out_f:
            out_f.write("\n".join(lines) + "\n")
        return {"success": True, "data": {"saved": output_file, "entries": len(lines)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def verify_hash_manifest(manifest_file: str, base_folder: str, algorithm: str = "sha256") -> Dict[str, Any]:
    """Verify files against a hash manifest."""
    try:
        ok = []
        failed = []
        missing = []
        with open(manifest_file, "r") as mf:
            for line in mf:
                line = line.strip()
                if not line or "  " not in line:
                    continue
                expected_hash, rel_path = line.split("  ", 1)
                fp = os.path.join(base_folder, rel_path)
                if not os.path.isfile(fp):
                    missing.append(rel_path)
                    continue
                r = verify_file_hash(fp, expected_hash, algorithm)
                if r["success"] and r["data"]["match"]:
                    ok.append(rel_path)
                else:
                    failed.append(rel_path)
        return {"success": True, "data": {"ok": len(ok), "failed": failed, "missing": missing}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_supported_algorithms() -> Dict[str, Any]:
    try:
        return {"success": True, "data": sorted(hashlib.algorithms_available), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_file_hash_all(path: str) -> Dict[str, Any]:
    """Compute MD5, SHA1, SHA256, and CRC32 of a file in one pass."""
    try:
        md5 = hashlib.md5()
        sha1 = hashlib.sha1()
        sha256 = hashlib.sha256()
        crc = 0
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                md5.update(chunk)
                sha1.update(chunk)
                sha256.update(chunk)
                crc = zlib.crc32(chunk, crc)
        return {"success": True, "data": {
            "md5": md5.hexdigest(),
            "sha1": sha1.hexdigest(),
            "sha256": sha256.hexdigest(),
            "crc32": format(crc & 0xFFFFFFFF, "08x")
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
