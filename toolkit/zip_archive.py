import zipfile
import tarfile
import gzip
import bz2
import lzma
import os
import json
import pathlib
import shutil
import io
import base64
from typing import Dict, Any, List, Optional, Union

def _success(data: Any = None) -> Dict[str, Any]:
    """Helper to return a successful standard dictionary."""
    return {"success": True, "data": data, "error": None}

def _error(msg: str) -> Dict[str, Any]:
    """Helper to return an error standard dictionary."""
    return {"success": False, "data": None, "error": msg}

def set_compression_level(level: int) -> Dict[str, Any]:
    """Sets/Returns the compression type based on a 0-9 scale."""
    try:
        if level <= 0:
            ctype = zipfile.ZIP_STORED
        elif level <= 3:
            ctype = zipfile.ZIP_BZIP2
        elif level <= 6:
            ctype = zipfile.ZIP_DEFLATED
        else:
            ctype = zipfile.ZIP_LZMA
        return _success({"zip_compression_type": ctype})
    except Exception as e:
        return _error(str(e))

def create_zip(source_path: str, dest_path: str, level: int = 6) -> Dict[str, Any]:
    """Creates a zip archive from a file or directory."""
    try:
        src = pathlib.Path(source_path)
        dest = pathlib.Path(dest_path)
        comp_type = set_compression_level(level).get("data", {}).get("zip_compression_type", zipfile.ZIP_DEFLATED)
        
        with zipfile.ZipFile(dest, 'w', comp_type) as zf:
            if src.is_file():
                zf.write(src, arcname=src.name)
            elif src.is_dir():
                for root, _, files in os.walk(src):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, src.parent)
                        zf.write(file_path, arcname)
            else:
                return _error("Source path does not exist.")
        return _success({"archive": str(dest), "size_bytes": dest.stat().st_size})
    except Exception as e:
        return _error(f"Failed to create zip: {e}")

def extract_zip(source_path: str, dest_dir: str) -> Dict[str, Any]:
    """Extracts a zip archive to a directory."""
    try:
        with zipfile.ZipFile(source_path, 'r') as zf:
            zf.extractall(dest_dir)
            files = zf.namelist()
        return _success({"extracted_files": files, "dest": dest_dir})
    except Exception as e:
        return _error(f"Failed to extract zip: {e}")

def list_zip_contents(source_path: str) -> Dict[str, Any]:
    """Lists contents of a zip archive."""
    try:
        contents = []
        with zipfile.ZipFile(source_path, 'r') as zf:
            for info in zf.infolist():
                contents.append({
                    "filename": info.filename,
                    "size": info.file_size,
                    "compressed_size": info.compress_size
                })
        return _success({"contents": contents})
    except Exception as e:
        return _error(f"Failed to list contents: {e}")

def add_to_zip(zip_path: str, source_path: str, arcname: Optional[str] = None) -> Dict[str, Any]:
    """Adds a file to an existing zip archive."""
    try:
        src = pathlib.Path(source_path)
        if not src.exists():
            return _error("Source file does not exist.")
        name_in_zip = arcname if arcname else src.name
        with zipfile.ZipFile(zip_path, 'a', zipfile.ZIP_DEFLATED) as zf:
            zf.write(src, name_in_zip)
        return _success({"added": name_in_zip})
    except Exception as e:
        return _error(f"Failed to add to zip: {e}")

def remove_from_zip(zip_path: str, filename_to_remove: str) -> Dict[str, Any]:
    """Removes a specific file from a zip archive by copying to a temp file."""
    try:
        temp_path = f"{zip_path}.temp"
        removed = False
        with zipfile.ZipFile(zip_path, 'r') as z_in, zipfile.ZipFile(temp_path, 'w') as z_out:
            for item in z_in.infolist():
                if item.filename != filename_to_remove:
                    z_out.writestr(item, z_in.read(item.filename))
                else:
                    removed = True
        if removed:
            shutil.move(temp_path, zip_path)
            return _success({"removed": filename_to_remove})
        else:
            os.remove(temp_path)
            return _error("File not found in archive.")
    except Exception as e:
        if os.path.exists(f"{zip_path}.temp"):
            os.remove(f"{zip_path}.temp")
        return _error(f"Failed to remove from zip: {e}")

def create_tar(source_path: str, dest_path: str, mode: str = 'w:gz') -> Dict[str, Any]:
    """Creates a tar archive."""
    try:
        with tarfile.open(dest_path, mode) as tar:
            tar.add(source_path, arcname=os.path.basename(source_path))
        return _success({"archive": dest_path})
    except Exception as e:
        return _error(f"Failed to create tar: {e}")

def extract_tar(source_path: str, dest_dir: str) -> Dict[str, Any]:
    """Extracts a tar archive."""
    try:
        with tarfile.open(source_path, 'r:*') as tar:
            tar.extractall(path=dest_dir)
            files = tar.getnames()
        return _success({"extracted_files": files})
    except Exception as e:
        return _error(f"Failed to extract tar: {e}")

def compress_gzip(source_path: str, dest_path: str) -> Dict[str, Any]:
    """Compresses a single file using gzip."""
    try:
        with open(source_path, 'rb') as f_in, gzip.open(dest_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
        return _success({"archive": dest_path})
    except Exception as e:
        return _error(f"Failed to gzip: {e}")

def decompress_gzip(source_path: str, dest_path: str) -> Dict[str, Any]:
    """Decompresses a gzip file."""
    try:
        with gzip.open(source_path, 'rb') as f_in, open(dest_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
        return _success({"extracted_to": dest_path})
    except Exception as e:
        return _error(f"Failed to decompress gzip: {e}")

def compress_bz2(source_path: str, dest_path: str) -> Dict[str, Any]:
    """Compresses a single file using bz2."""
    try:
        with open(source_path, 'rb') as f_in, bz2.open(dest_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
        return _success({"archive": dest_path})
    except Exception as e:
        return _error(f"Failed to bz2: {e}")

def decompress_bz2(source_path: str, dest_path: str) -> Dict[str, Any]:
    """Decompresses a bz2 file."""
    try:
        with bz2.open(source_path, 'rb') as f_in, open(dest_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
        return _success({"extracted_to": dest_path})
    except Exception as e:
        return _error(f"Failed to decompress bz2: {e}")

def compress_lzma(source_path: str, dest_path: str) -> Dict[str, Any]:
    """Compresses a single file using lzma."""
    try:
        with open(source_path, 'rb') as f_in, lzma.open(dest_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
        return _success({"archive": dest_path})
    except Exception as e:
        return _error(f"Failed to lzma: {e}")

def decompress_lzma(source_path: str, dest_path: str) -> Dict[str, Any]:
    """Decompresses an lzma file."""
    try:
        with lzma.open(source_path, 'rb') as f_in, open(dest_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
        return _success({"extracted_to": dest_path})
    except Exception as e:
        return _error(f"Failed to decompress lzma: {e}")

def get_archive_info(archive_path: str) -> Dict[str, Any]:
    """Returns metadata about the archive."""
    try:
        stat = os.stat(archive_path)
        info = {"path": archive_path, "size_bytes": stat.st_size, "type": "unknown"}
        if zipfile.is_zipfile(archive_path):
            info["type"] = "zip"
        elif tarfile.is_tarfile(archive_path):
            info["type"] = "tar"
        return _success(info)
    except Exception as e:
        return _error(f"Failed to get info: {e}")

def validate_archive(archive_path: str) -> Dict[str, Any]:
    """Validates archive integrity."""
    try:
        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path, 'r') as zf:
                bad_file = zf.testzip()
                if bad_file:
                    return _error(f"Corrupted file found: {bad_file}")
            return _success({"valid": True})
        elif tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path, 'r:*') as tf:
                tf.getmembers() 
            return _success({"valid": True})
        return _error("Unsupported archive type for validation.")
    except Exception as e:
        return _error(f"Validation failed: {e}")

def create_encrypted_zip(source_path: str, dest_path: str, password: str) -> Dict[str, Any]:
    """Python's standard zipfile does not support writing encrypted zips natively. 
    Returns explicit tool limitation error for the agent to adjust."""
    return _error("Operation not supported: Standard Python `zipfile` module cannot create encrypted archives.")

def extract_encrypted_zip(zip_path: str, dest_dir: str, password: str) -> Dict[str, Any]:
    """Extracts a password-protected zip file."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(path=dest_dir, pwd=password.encode('utf-8'))
        return _success({"extracted_to": dest_dir})
    except Exception as e:
        return _error(f"Failed to extract encrypted zip: {e}")

def split_archive(file_path: str, chunk_size_bytes: int) -> Dict[str, Any]:
    """Splits an archive into chunks."""
    try:
        chunks = []
        with open(file_path, 'rb') as f:
            chunk_num = 1
            while True:
                chunk = f.read(chunk_size_bytes)
                if not chunk:
                    break
                chunk_name = f"{file_path}.{chunk_num:03d}"
                with open(chunk_name, 'wb') as cf:
                    cf.write(chunk)
                chunks.append(chunk_name)
                chunk_num += 1
        return _success({"chunks": chunks})
    except Exception as e:
        return _error(f"Failed to split archive: {e}")

def merge_archives(base_name: str, dest_path: str, num_chunks: int) -> Dict[str, Any]:
    """Merges split archive chunks back into a single file."""
    try:
        with open(dest_path, 'wb') as dest:
            for i in range(1, num_chunks + 1):
                chunk_name = f"{base_name}.{i:03d}"
                with open(chunk_name, 'rb') as src:
                    shutil.copyfileobj(src, dest)
        return _success({"merged_file": dest_path})
    except Exception as e:
        return _error(f"Failed to merge archives: {e}")

def create_self_extracting(source_zip: str, dest_py: str) -> Dict[str, Any]:
    """Wraps a zip file into a self-extracting Python script."""
    try:
        with open(source_zip, 'rb') as f:
            encoded_zip = base64.b64encode(f.read()).decode('utf-8')
        
        script_content = f"""#!/usr/bin/env python3
import base64
import zipfile
import io
import os

payload = "{encoded_zip}"
print("Extracting payload...")
zip_data = base64.b64decode(payload)
with zipfile.ZipFile(io.BytesIO(zip_data), 'r') as zf:
    zf.extractall()
print("Extraction complete.")
"""
        with open(dest_py, 'w') as f:
            f.write(script_content)
        os.chmod(dest_py, 0o755)
        return _success({"executable": dest_py})
    except Exception as e:
        return _error(f"Failed to create self-extractor: {e}")

def batch_compress(file_list: List[str], dest_dir: str) -> Dict[str, Any]:
    """Compresses a list of files into individual zip files in a destination directory."""
    try:
        os.makedirs(dest_dir, exist_ok=True)
        results = []
        for file in file_list:
            if os.path.exists(file):
                dest = os.path.join(dest_dir, f"{os.path.basename(file)}.zip")
                res = create_zip(file, dest)
                results.append({"file": file, "success": res["success"], "archive": dest})
        return _success({"batch_results": results})
    except Exception as e:
        return _error(f"Batch compression failed: {e}")

def batch_extract(zip_list: List[str], dest_dir: str) -> Dict[str, Any]:
    """Extracts a list of zip files into a single destination directory."""
    try:
        os.makedirs(dest_dir, exist_ok=True)
        results = []
        for zf in zip_list:
            if os.path.exists(zf):
                res = extract_zip(zf, dest_dir)
                results.append({"archive": zf, "success": res["success"]})
        return _success({"batch_results": results})
    except Exception as e:
        return _error(f"Batch extraction failed: {e}")

def filter_archive_contents(zip_path: str, extension: str, dest_dir: str) -> Dict[str, Any]:
    """Extracts only files matching a specific extension from a zip."""
    try:
        extracted = []
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for info in zf.infolist():
                if info.filename.endswith(extension):
                    zf.extract(info, dest_dir)
                    extracted.append(info.filename)
        return _success({"extracted_files": extracted})
    except Exception as e:
        return _error(f"Failed to filter contents: {e}")

def export_archive_manifest(zip_path: str, manifest_json_path: str) -> Dict[str, Any]:
    """Exports the contents list of a zip archive to a JSON manifest file."""
    try:
        contents_res = list_zip_contents(zip_path)
        if not contents_res["success"]:
            return contents_res
        with open(manifest_json_path, 'w') as f:
            json.dump(contents_res["data"], f, indent=4)
        return _success({"manifest": manifest_json_path})
    except Exception as e:
        return _error(f"Failed to export manifest: {e}")
