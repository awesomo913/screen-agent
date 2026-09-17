import os
import stat
import json
import pathlib
import hashlib
import mimetypes
import time
import datetime
import struct
from typing import Dict, Any, List, Optional, Union

def _safe_execute(func, *args, **kwargs) -> Dict[str, Any]:
    """Helper to catch OS errors and return structured Dict outputs."""
    try:
        return {"status": "success", "data": func(*args, **kwargs)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_file_size(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    return _safe_execute(lambda p: os.path.getsize(p), path)

def get_creation_time(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _ctime(p):
        stat_res = os.stat(p)
        ts = getattr(stat_res, 'st_birthtime', stat_res.st_ctime)
        return datetime.datetime.fromtimestamp(ts).isoformat()
    return _safe_execute(_ctime, path)

def get_modification_time(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _mtime(p):
        return datetime.datetime.fromtimestamp(os.path.getmtime(p)).isoformat()
    return _safe_execute(_mtime, path)

def get_access_time(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _atime(p):
        return datetime.datetime.fromtimestamp(os.path.getatime(p)).isoformat()
    return _safe_execute(_atime, path)

def get_file_type(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _type(p):
        mode = os.stat(p).st_mode
        if stat.S_ISDIR(mode): return "directory"
        elif stat.S_ISREG(mode): return "file"
        elif stat.S_ISLNK(mode): return "symlink"
        return "unknown"
    return _safe_execute(_type, path)

def get_mime_type(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _mime(p):
        mime, encoding = mimetypes.guess_type(str(p))
        return {"mime_type": mime or "application/octet-stream", "encoding": encoding}
    return _safe_execute(_mime, path)

def get_file_hash_md5(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _md5(p):
        hash_md5 = hashlib.md5()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    return _safe_execute(_md5, path)

def get_file_hash_sha256(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _sha256(p):
        hash_sha = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha.update(chunk)
        return hash_sha.hexdigest()
    return _safe_execute(_sha256, path)

def get_file_permissions(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    return _safe_execute(lambda p: oct(os.stat(p).st_mode)[-3:], path)

def set_file_permissions(path: Union[str, pathlib.Path], mode: int) -> Dict[str, Any]:
    def _chmod(p, m):
        os.chmod(p, m)
        return oct(m)
    return _safe_execute(_chmod, path, mode)

def get_file_owner(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _owner(p):
        uid = os.stat(p).st_uid
        gid = os.stat(p).st_gid
        try:
            import pwd, grp
            return {"uid": uid, "user": pwd.getpwuid(uid).pw_name, "gid": gid, "group": grp.getgrgid(gid).gr_name}
        except ImportError:
            return {"uid": uid, "gid": gid}
    return _safe_execute(_owner, path)

def get_extended_attributes(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _xattr(p):
        if hasattr(os, 'listxattr'):
            return {k: os.getxattr(p, k).decode('utf-8', 'ignore') for k in os.listxattr(p)}
        return {}
    return _safe_execute(_xattr, path)

def set_extended_attribute(path: Union[str, pathlib.Path], key: str, value: bytes) -> Dict[str, Any]:
    def _set_xattr(p, k, v):
        if hasattr(os, 'setxattr'):
            os.setxattr(p, k, v)
            return True
        raise OSError("Extended attributes not supported on this OS")
    return _safe_execute(_set_xattr, path, key, value)

def get_image_dimensions(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _dims(p):
        with open(p, 'rb') as f:
            head = f.read(24)
            if head.startswith(b'\x89PNG\r\n\x1a\n'):
                w, h = struct.unpack('>LL', head[16:24])
                return {"width": w, "height": h, "type": "PNG"}
            elif head.startswith(b'GIF87a') or head.startswith(b'GIF89a'):
                w, h = struct.unpack('<HH', head[6:10])
                return {"width": w, "height": h, "type": "GIF"}
            elif head.startswith(b'\xff\xd8'):
                f.seek(0)
                size = 2
                ftype = 0
                while not 0xc0 <= ftype <= 0xcf or ftype in (0xc4, 0xc8, 0xcc):
                    f.seek(size, 1)
                    byte = f.read(1)
                    while ord(byte) == 0xff: byte = f.read(1)
                    ftype = ord(byte)
                    size = struct.unpack('>H', f.read(2))[0] - 2
                f.seek(1, 1)
                h, w = struct.unpack('>HH', f.read(4))
                return {"width": w, "height": h, "type": "JPEG"}
        return {"error": "Unsupported image format for native parsing"}
    return _safe_execute(_dims, path)

def get_exif_data(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _exif(p):
        with open(p, 'rb') as f:
            if not f.read(2) == b'\xff\xd8': return {"error": "Not a JPEG"}
            marker = f.read(2)
            if marker == b'\xff\xe1':
                length = struct.unpack('>H', f.read(2))[0]
                if f.read(4) == b'Exif':
                    return {"exif_present": True, "raw_length": length}
        return {"exif_present": False}
    return _safe_execute(_exif, path)

def strip_exif_data(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _strip(p):
        with open(p, 'rb') as f:
            data = f.read()
        if not data.startswith(b'\xff\xd8'): return {"error": "Not a JPEG"}
        start = data.find(b'\xff\xe1')
        if start == -1: return {"status": "No EXIF found"}
        length = struct.unpack('>H', data[start+2:start+4])[0]
        clean_data = data[:start] + data[start+2+length:]
        with open(p, 'wb') as f:
            f.write(clean_data)
        return {"status": "EXIF stripped"}
    return _safe_execute(_strip, path)

def get_pdf_metadata(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _pdf(p):
        with open(p, 'rb') as f:
            header = f.read(10)
            if not header.startswith(b'%PDF'):
                return {"error": "Not a PDF"}
            f.seek(-1024, 2)
            tail = f.read().decode('latin-1', 'ignore')
            return {"is_pdf": True, "eof_present": "%%EOF" in tail}
    return _safe_execute(_pdf, path)

def get_audio_metadata(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _audio(p):
        with open(p, 'rb') as f:
            head = f.read(12)
            if head.startswith(b'RIFF') and head[8:12] == b'WAVE':
                return {"type": "WAV", "valid": True}
            elif head[:3] == b'ID3':
                return {"type": "MP3", "id3_present": True}
        return {"type": "unknown"}
    return _safe_execute(_audio, path)

def get_video_metadata(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _video(p):
        with open(p, 'rb') as f:
            f.seek(4)
            ftyp = f.read(4)
            if ftyp == b'ftyp':
                return {"type": "MP4/MOV", "valid": True}
        return {"type": "unknown"}
    return _safe_execute(_video, path)

def get_file_info(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"status": "error", "message": "File does not exist"}
    return {
        "status": "success",
        "path": str(path),
        "size": get_file_size(path).get("data"),
        "type": get_file_type(path).get("data"),
        "mime": get_mime_type(path).get("data", {}).get("mime_type"),
        "created": get_creation_time(path).get("data"),
        "modified": get_modification_time(path).get("data"),
        "permissions": get_file_permissions(path).get("data"),
        "owner": get_file_owner(path).get("data")
    }

def batch_get_metadata(paths: List[Union[str, pathlib.Path]]) -> Dict[str, Any]:
    return {"status": "success", "data": {str(p): get_file_info(p) for p in paths}}

def compare_file_metadata(path1: Union[str, pathlib.Path], path2: Union[str, pathlib.Path]) -> Dict[str, Any]:
    m1 = get_file_info(path1).get("data", {}) if get_file_info(path1)["status"] == "success" else {}
    m2 = get_file_info(path2).get("data", {}) if get_file_info(path2)["status"] == "success" else {}
    differences = {k: {"file1": m1.get(k), "file2": m2.get(k)} for k in set(m1) | set(m2) if m1.get(k) != m2.get(k)}
    return {"status": "success", "data": differences, "match": len(differences) == 0}

def export_metadata_report(paths: List[Union[str, pathlib.Path]], out_path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _export(ps, out):
        data = batch_get_metadata(ps)
        with open(out, 'w') as f:
            json.dump(data, f, indent=4)
        return str(out)
    return _safe_execute(_export, paths, out_path)

def search_by_metadata(dir_path: Union[str, pathlib.Path], criteria: Dict[str, Any]) -> Dict[str, Any]:
    def _search(dp, crit):
        matches = []
        for root, _, files in os.walk(dp):
            for file in files:
                full_path = os.path.join(root, file)
                info = get_file_info(full_path)
                if info["status"] == "success":
                    match = all(info.get(k) == v for k, v in crit.items())
                    if match: matches.append(full_path)
        return matches
    return _safe_execute(_search, dir_path, criteria)

def create_metadata_index(dir_path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    def _index(dp):
        idx = {}
        for root, _, files in os.walk(dp):
            for file in files:
                p = os.path.join(root, file)
                idx[p] = get_file_info(p)
        return idx
    return _safe_execute(_index, dir_path)

if __name__ == "__main__":
    # Test suite hooks can be initialized here
    pass
