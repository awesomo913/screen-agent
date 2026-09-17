"""
ftp_actions.py - Production-grade FTP/SFTP Action Toolkit for Screen Agents.
Provides comprehensive file transfer, directory management, synchronization,
and metadata retrieval with robust error handling and standardized Dict returns.
"""

import ftplib
import paramiko
import pathlib
import os
import io
import json
import time
import threading
import hashlib
import fnmatch
from typing import Dict, Any, Optional, Union, List, Tuple

# Standardized response structure for agent compatibility
def _response(success: bool, message: str, data: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
    """Helper to ensure consistent Dict return format across all functions."""
    return {
        "success": success,
        "message": message,
        "data": data,
        "error": error,
        "timestamp": time.time()
    }


# =============================================================================
# FTP Operations
# =============================================================================

def ftp_connect(host: str, port: int = 21, user: str = "anonymous", password: str = "") -> Dict[str, Any]:
    """Establish an FTP connection."""
    try:
        ftp = ftplib.FTP()
        ftp.connect(host, port, timeout=30)
        ftp.login(user, password)
        ftp.encoding = "utf-8"
        return _response(True, "FTP connected successfully", data={"host": host, "port": port, "type": "ftp"})
    except Exception as e:
        return _response(False, "FTP connection failed", error=str(e))


def ftp_disconnect(connection: Union[ftplib.FTP, paramiko.SFTPClient, Dict[str, Any]]) -> Dict[str, Any]:
    """Gracefully disconnect from FTP or SFTP session."""
    try:
        if isinstance(connection, ftplib.FTP):
            connection.quit()
        elif isinstance(connection, paramiko.SFTPClient):
            connection.close()
            if hasattr(connection, "_ssh_client"):
                connection._ssh_client.close()
        elif isinstance(connection, dict) and "connection" in connection:
            return ftp_disconnect(connection["connection"])
        else:
            return _response(False, "Invalid connection object", error="Unsupported connection type")
        return _response(True, "Disconnected successfully")
    except Exception as e:
        return _response(False, "Disconnection error", error=str(e))


def ftp_upload(connection: ftplib.FTP, local_path: str, remote_path: str) -> Dict[str, Any]:
    """Upload a file to the FTP server."""
    local = pathlib.Path(local_path)
    if not local.is_file():
        return _response(False, f"Local file not found: {local_path}")
    try:
        with open(local, "rb") as f:
            connection.storbinary(f"STOR {remote_path}", f)
        return _response(True, "Upload successful", data={"remote_path": remote_path, "size": local.stat().st_size})
    except Exception as e:
        return _response(False, "Upload failed", error=str(e))


def ftp_download(connection: ftplib.FTP, remote_path: str, local_path: str) -> Dict[str, Any]:
    """Download a file from the FTP server."""
    try:
        local = pathlib.Path(local_path)
        local.parent.mkdir(parents=True, exist_ok=True)
        with open(local, "wb") as f:
            connection.retrbinary(f"RETR {remote_path}", f.write)
        return _response(True, "Download successful", data={"local_path": str(local), "size": local.stat().st_size})
    except Exception as e:
        return _response(False, "Download failed", error=str(e))


def ftp_list_dir(connection: ftplib.FTP, path: str = ".") -> Dict[str, Any]:
    """List contents of a remote directory."""
    try:
        connection.cwd(path)
        items = []
        try:
            for name, facts in connection.mlsd():
                items.append({
                    "name": name,
                    "type": facts.get("type", "unknown"),
                    "size": int(facts.get("size", 0)),
                    "modified": facts.get("modify", "")
                })
        except ftplib.error_perm:
            # Fallback for servers without MLSD support
            names = connection.nlst()
            items = [{"name": n, "type": "unknown"} for n in names]
        return _response(True, f"Listed directory: {path}", data=items)
    except Exception as e:
        return _response(False, f"Failed to list directory: {path}", error=str(e))


def ftp_mkdir(connection: ftplib.FTP, path: str) -> Dict[str, Any]:
    """Create a directory on the FTP server."""
    try:
        connection.mkd(path)
        return _response(True, f"Created directory: {path}")
    except Exception as e:
        return _response(False, f"Failed to create directory: {path}", error=str(e))


def ftp_rmdir(connection: ftplib.FTP, path: str) -> Dict[str, Any]:
    """Remove an empty directory on the FTP server."""
    try:
        connection.rmd(path)
        return _response(True, f"Removed directory: {path}")
    except Exception as e:
        return _response(False, f"Failed to remove directory: {path}", error=str(e))


def ftp_delete(connection: ftplib.FTP, filepath: str) -> Dict[str, Any]:
    """Delete a file on the FTP server."""
    try:
        connection.delete(filepath)
        return _response(True, f"Deleted file: {filepath}")
    except Exception as e:
        return _response(False, f"Failed to delete file: {filepath}", error=str(e))


def ftp_rename(connection: ftplib.FTP, old_name: str, new_name: str) -> Dict[str, Any]:
    """Rename a file or directory on the FTP server."""
    try:
        connection.rename(old_name, new_name)
        return _response(True, f"Renamed {old_name} to {new_name}")
    except Exception as e:
        return _response(False, f"Failed to rename {old_name} to {new_name}", error=str(e))


def ftp_get_size(connection: ftplib.FTP, filepath: str) -> Dict[str, Any]:
    """Get the size of a remote file."""
    try:
        size = connection.size(filepath)
        return _response(True, "Size retrieved", data={"filepath": filepath, "size": size})
    except Exception as e:
        return _response(False, f"Failed to get size for {filepath}", error=str(e))


def ftp_exists(connection: ftplib.FTP, path: str) -> Dict[str, Any]:
    """Check if a file or directory exists on the FTP server."""
    original_cwd = connection.pwd()
    try:
        # Try as file
        connection.size(path)
        return _response(True, "Path exists (file)", data={"path": path, "type": "file"})
    except ftplib.error_perm:
        try:
            # Try as directory
            connection.cwd(path)
            connection.cwd(original_cwd)
            return _response(True, "Path exists (directory)", data={"path": path, "type": "directory"})
        except Exception:
            return _response(False, "Path does not exist", data={"path": path, "exists": False})
    except Exception as e:
        return _response(False, "Existence check failed", error=str(e))


# =============================================================================
# SFTP Operations (Paramiko)
# =============================================================================

def sftp_connect(host: str, port: int = 22, user: str = "", password: str = "", key_file: str = "") -> Dict[str, Any]:
    """Establish an SFTP connection via SSH."""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        connect_kwargs: Dict[str, Any] = {"hostname": host, "port": port, "username": user, "timeout": 30, "allow_agent": True}
        if key_file and os.path.isfile(key_file):
            connect_kwargs["key_filename"] = key_file
        elif password:
            connect_kwargs["password"] = password
        else:
            client.close()
            return _response(False, "No valid authentication method provided", error="Provide password or key_file")

        client.connect(**connect_kwargs)
        sftp = client.open_sftp()
        sftp._ssh_client = client  # Attach for graceful disconnect
        return _response(True, "SFTP connected successfully", data={"connection": sftp, "host": host, "port": port, "type": "sftp"})
    except Exception as e:
        return _response(False, "SFTP connection failed", error=str(e))


def sftp_upload(connection: paramiko.SFTPClient, local_path: str, remote_path: str) -> Dict[str, Any]:
    """Upload a file via SFTP."""
    try:
        connection.put(local_path, remote_path)
        return _response(True, "SFTP Upload successful", data={"remote_path": remote_path, "size": os.path.getsize(local_path)})
    except Exception as e:
        return _response(False, "SFTP Upload failed", error=str(e))


def sftp_download(connection: paramiko.SFTPClient, remote_path: str, local_path: str) -> Dict[str, Any]:
    """Download a file via SFTP."""
    try:
        pathlib.Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        connection.get(remote_path, local_path)
        return _response(True, "SFTP Download successful", data={"local_path": local_path, "size": os.path.getsize(local_path)})
    except Exception as e:
        return _response(False, "SFTP Download failed", error=str(e))


def sftp_list_dir(connection: paramiko.SFTPClient, path: str = ".") -> Dict[str, Any]:
    """List contents of a remote SFTP directory."""
    try:
        items = connection.listdir_attr(path)
        result = [
            {
                "name": attr.filename,
                "size": attr.st_size,
                "type": 16384 if (attr.st_mode & 0o40000) else 32768,
                "modified": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(attr.st_mtime))
            }
            for attr in items
        ]
        return _response(True, f"SFTP Listed directory: {path}", data=result)
    except Exception as e:
        return _response(False, f"SFTP Failed to list directory: {path}", error=str(e))


def sftp_mkdir(connection: paramiko.SFTPClient, path: str) -> Dict[str, Any]:
    """Create a directory on the SFTP server."""
    try:
        connection.mkdir(path)
        return _response(True, f"SFTP Created directory: {path}")
    except Exception as e:
        return _response(False, f"SFTP Failed to create directory: {path}", error=str(e))


def sftp_delete(connection: paramiko.SFTPClient, filepath: str) -> Dict[str, Any]:
    """Delete a file on the SFTP server."""
    try:
        connection.remove(filepath)
        return _response(True, f"SFTP Deleted file: {filepath}")
    except Exception as e:
        return _response(False, f"SFTP Failed to delete file: {filepath}", error=str(e))


# =============================================================================
# Advanced Operations
# =============================================================================

def batch_upload(connection: Union[ftplib.FTP, paramiko.SFTPClient], local_dir: str, remote_dir: str, pattern: str = "*") -> Dict[str, Any]:
    """Upload multiple files matching a pattern using thread-safe result aggregation."""
    results = {"uploaded": [], "failed": [], "errors": []}
    lock = threading.Lock()
    local_path = pathlib.Path(local_dir)
    
    if not local_path.is_dir():
        return _response(False, "Local directory not found")

    def _upload_task(file_path: pathlib.Path):
        remote_file = f"{remote_dir}/{file_path.name}" if remote_dir not in (".", "") else file_path.name
        try:
            if isinstance(connection, ftplib.FTP):
                res = ftp_upload(connection, str(file_path), remote_file)
            elif isinstance(connection, paramiko.SFTPClient):
                res = sftp_upload(connection, str(file_path), remote_file)
            else:
                res = {"success": False, "error": "Invalid connection type"}

            with lock:
                if res["success"]:
                    results["uploaded"].append(remote_file)
                else:
                    results["failed"].append(remote_file)
                    results["errors"].append(res.get("error", "Unknown"))
        except Exception as e:
            with lock:
                results["failed"].append(str(file_path))
                results["errors"].append(str(e))

    try:
        threads = []
        for f in local_path.iterdir():
            if f.is_file() and fnmatch.fnmatch(f.name, pattern):
                t = threading.Thread(target=_upload_task, args=(f,))
                threads.append(t)
                t.start()
        
        for t in threads:
            t.join()
            
        return _response(True, "Batch upload completed", data=json.loads(json.dumps(results, default=str)))
    except Exception as e:
        return _response(False, "Batch upload failed", error=str(e))


def batch_download(connection: Union[ftplib.FTP, paramiko.SFTPClient], remote_dir: str, local_dir: str, pattern: str = "*") -> Dict[str, Any]:
    """Download multiple files matching a pattern from remote server."""
    results = {"downloaded": [], "failed": [], "errors": []}
    lock = threading.Lock()
    local_path = pathlib.Path(local_dir)
    local_path.mkdir(parents=True, exist_ok=True)

    try:
        list_res = sftp_list_dir(connection, remote_dir) if isinstance(connection, paramiko.SFTPClient) else ftp_list_dir(connection, remote_dir)
        if not list_res["success"]:
            return _response(False, "Failed to list remote directory", error=list_res.get("error"))

        def _download_task(item: Dict[str, Any]):
            item_name = item["name"]
            if "type" in item and item["type"] == "file" or not isinstance(item["type"], str):
                if fnmatch.fnmatch(item_name, pattern):
                    remote_file = f"{remote_dir}/{item_name}" if remote_dir not in (".", "") else item_name
                    local_file = str(local_path / item_name)
                    try:
                        res = ftp_download(connection, remote_file, local_file) if isinstance(connection, ftplib.FTP) else sftp_download(connection, remote_file, local_file)
                        with lock:
                            if res["success"]:
                                results["downloaded"].append(local_file)
                            else:
                                results["failed"].append(remote_file)
                                results["errors"].append(res.get("error", "Unknown"))
                    except Exception as e:
                        with lock:
                            results["failed"].append(remote_file)
                            results["errors"].append(str(e))

        threads = [threading.Thread(target=_download_task, args=(item,)) for item in list_res["data"]]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        return _response(True, "Batch download completed", data=json.loads(json.dumps(results, default=str)))
    except Exception as e:
        return _response(False, "Batch download failed", error=str(e))


def sync_directories(connection: Union[ftplib.FTP, paramiko.SFTPClient], local_dir: str, remote_dir: str) -> Dict[str, Any]:
    """Sync local directory to remote server based on size/hash comparison."""
    results = {"synced": [], "skipped": [], "errors": []}
    lock = threading.Lock()
    local_path = pathlib.Path(local_dir)

    def _compute_hash(file_path: pathlib.Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _sync_file(file: pathlib.Path):
        rel_path = file.relative_to(local_path)
        remote_file = str(pathlib.PurePosixPath(remote_dir) / rel_path).replace("\\", "/")
        
        try:
            local_hash = _compute_hash(file)
            local_size = file.stat().st_size
            needs_upload = True

            if isinstance(connection, paramiko.SFTPClient):
                try:
                    remote_stat = connection.stat(remote_file)
                    if remote_stat.st_size == local_size:
                        # Quick hash check for SFTP
                        remote_buf = io.BytesIO()
                        connection.getfo(remote_file, remote_buf)
                        remote_buf.seek(0)
                        if hashlib.sha256(remote_buf.read()).hexdigest() == local_hash:
                            needs_upload = False
                except IOError:
                    pass
            else:
                try:
                    size_res = ftp_get_size(connection, remote_file)
                    if size_res["success"] and size_res["data"]["size"] == local_size:
                        # FTP fallback: skip if size matches (hash over FTP is slow)
                        needs_upload = False
                except Exception:
                    pass

            if needs_upload:
                if isinstance(connection, ftplib.FTP):
                    res = ftp_upload(connection, str(file), remote_file)
                else:
                    # Ensure remote dirs exist for SFTP
                    remote_parent = str(pathlib.PurePosixPath(remote_file).parent)
                    _ensure_sftp_dirs(connection, remote_parent)
                    res = sftp_upload(connection, str(file), remote_file)
                
                with lock:
                    if res["success"]:
                        results["synced"].append(str(rel_path))
                    else:
                        results["errors"].append({"file": str(rel_path), "error": res.get("error", "Unknown")})
            else:
                with lock:
                    results["skipped"].append(str(rel_path))
        except Exception as e:
            with lock:
                results["errors"].append({"file": str(rel_path), "error": str(e)})

    def _ensure_sftp_dirs(sftp_conn: paramiko.SFTPClient, path: str):
        parts = path.lstrip("/").split("/")
        current = ""
        for p in parts:
            if not p: continue
            current += f"/{p}"
            try:
                sftp_conn.stat(current)
            except IOError:
                try:
                    sftp_conn.mkdir(current)
                except Exception:
                    pass

    try:
        threads = []
        for f in local_path.rglob("*"):
            if f.is_file():
                threads.append(threading.Thread(target=_sync_file, args=(f,)))
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        return _response(True, "Sync completed", data=results)
    except Exception as e:
        return _response(False, "Sync failed", error=str(e))


def ftp_walk(connection: ftplib.FTP, path: str = ".") -> Dict[str, Any]:
    """Recursively walk FTP directory structure."""
    result = []
    lock = threading.Lock()
    
    def _recursive_walk(current: str, depth: int = 0):
        if depth > 50:
            return
        try:
            original = connection.pwd()
            connection.cwd(current)
            names = [f for f in connection.nlst() if f not in (".", "..")]
            dirs, files = [], []
            for n in names:
                try:
                    connection.cwd(n)
                    connection.pwd()
                    dirs.append(n)
                    connection.cwd("..")
                except Exception:
                    files.append(n)
            
            with lock:
                result.append((current, dirs, files))
                
            for d in dirs:
                next_path = f"{current}/{d}" if current not in (".", "") else d
                _recursive_walk(next_path, depth + 1)
            connection.cwd(original)
        except Exception:
            with lock:
                result.append((current, [], ["Error: Permission or network failure"]))

    try:
        _recursive_walk(path)
        return _response(True, "Walk completed", data=result)
    except Exception as e:
        return _response(False, "Walk failed", error=str(e))


def ftp_get_modified_time(connection: ftplib.FTP, filepath: str) -> Dict[str, Any]:
    """Retrieve remote file modification timestamp using MDTM command."""
    try:
        resp = connection.sendcmd(f'MDTM {filepath}')
        time_str = resp.split()[-1]
        mtime = time.mktime(time.strptime(time_str, "%Y%m%d%H%M%S"))
        return _response(True, "Modified time retrieved", data={
            "filepath": filepath,
            "timestamp": mtime,
            "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime))
        })
    except Exception as e:
        return _response(False, "Failed to get modified time", error=str(e))


def ftp_chmod(connection: Union[ftplib.FTP, paramiko.SFTPClient], filepath: str, mode: int) -> Dict[str, Any]:
    """Change file permissions. Supports FTP SITE CHMOD and SFTP native chmod."""
    try:
        if isinstance(connection, paramiko.SFTPClient):
            connection.chmod(filepath, mode)
            return _response(True, f"SFTP chmod successful: {filepath}")
        else:
            octal_mode = oct(mode).replace("0o", "")
            resp = connection.sendcmd(f'SITE CHMOD {octal_mode} {filepath}')
            return _response(True, f"FTP SITE CHMOD successful: {filepath}", data={"response": resp})
    except Exception as e:
        return _response(False, f"Failed to chmod {filepath}", error=str(e))


def resume_upload(connection: Union[ftplib.FTP, paramiko.SFTPClient], local_path: str, remote_path: str) -> Dict[str, Any]:
    """Resume upload of a partially transferred file."""
    try:
        local = pathlib.Path(local_path)
        local_size = local.stat().st_size
        offset = 0
        
        if isinstance(connection, paramiko.SFTPClient):
            try:
                offset = connection.stat(remote_path).st_size
            except IOError:
                offset = 0
                
            if offset >= local_size:
                return _response(True, "Remote file is up-to-date or larger", data={"offset": offset})
                
            with open(local, 'rb') as f, connection.open(remote_path, 'ab') as rf:
                f.seek(offset)
                rf.seek(offset)
                for chunk in iter(lambda: f.read(65536), b""):
                    rf.write(chunk)
        else:
            try:
                offset = connection.size(remote_path) or 0
            except Exception:
                offset = 0
                
            if offset >= local_size:
                return _response(True, "Remote file is up-to-date or larger", data={"offset": offset})
                
            connection.voidcmd("TYPE I")
            with open(local, 'rb') as f:
                f.seek(offset)
                connection.storbinary(f"STOR {remote_path}", f, rest=offset)
                
        return _response(True, "Resume upload successful", data={"bytes_uploaded": local_size - offset})
    except Exception as e:
        return _response(False, "Resume upload failed", error=str(e))


def resume_download(connection: Union[ftplib.FTP, paramiko.SFTPClient], remote_path: str, local_path: str) -> Dict[str, Any]:
    """Resume download of a partially transferred file."""
    try:
        local = pathlib.Path(local_path)
        offset = local.stat().st_size if local.exists() else 0
        
        if isinstance(connection, paramiko.SFTPClient):
            remote_stat = connection.stat(remote_path)
            remote_size = remote_stat.st_size
            if offset >= remote_size:
                return _response(True, "Local file is up-to-date", data={"offset": offset})
                
            with connection.open(remote_path, 'rb') as rf, open(local, 'ab') as lf:
                rf.seek(offset)
                for chunk in iter(lambda: rf.read(65536), b""):
                    lf.write(chunk)
        else:
            remote_size = connection.size(remote_path) or 0
            if offset >= remote_size:
                return _response(True, "Local file is up-to-date", data={"offset": offset})
                
            connection.voidcmd("TYPE I")
            with open(local, 'ab') as f:
                connection.retrbinary(f"RETR {remote_path}", f.write, rest=offset)
                
        return _response(True, "Resume download successful", data={"offset": os.path.getsize(local_path), "local_path": str(local)})
    except Exception as e:
        return _response(False, "Resume download failed", error=str(e))