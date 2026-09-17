from __future__ import annotations

import json
import os
import pathlib
import socket
import stat
import subprocess
import threading
import time
import uuid
from typing import Any, Dict, Optional, List, Tuple

import paramiko
from scp import SCPClient


_SESSIONS: Dict[str, paramiko.SSHClient] = {}
_SFTPS: Dict[str, paramiko.SFTPClient] = {}
_TUNNELS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.RLock()


def _result(success: bool, **kwargs: Any) -> Dict[str, Any]:
    return {"success": success, **kwargs}


def _get_client(session_id: str) -> paramiko.SSHClient:
    with _LOCK:
        client = _SESSIONS.get(session_id)
    if not client:
        raise ValueError(f"Invalid session_id: {session_id}")
    return client


def _get_sftp(session_id: str) -> paramiko.SFTPClient:
    with _LOCK:
        sftp = _SFTPS.get(session_id)
    if not sftp:
        client = _get_client(session_id)
        sftp = client.open_sftp()
        with _LOCK:
            _SFTPS[session_id] = sftp
    return sftp


def ssh_connect(host: str, port: int = 22, username: Optional[str] = None,
                password: Optional[str] = None, key_file: Optional[str] = None) -> Dict[str, Any]:
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs: Dict[str, Any] = {
            "hostname": host,
            "port": port,
            "username": username,
            "password": password,
            "timeout": 15,
            "look_for_keys": False,
            "allow_agent": False,
        }
        if key_file:
            kwargs["key_filename"] = key_file
        client.connect(**kwargs)
        session_id = str(uuid.uuid4())
        with _LOCK:
            _SESSIONS[session_id] = client
        return _result(True, session_id=session_id, host=host, port=port)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_disconnect(session_id: str) -> Dict[str, Any]:
    try:
        with _LOCK:
            sftp = _SFTPS.pop(session_id, None)
            client = _SESSIONS.pop(session_id, None)
        if sftp:
            sftp.close()
        if client:
            client.close()
        return _result(True, session_id=session_id)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_execute(session_id: str, command: str, timeout: int = 60) -> Dict[str, Any]:
    try:
        client = _get_client(session_id)
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        return _result(
            True,
            stdout=stdout.read().decode(errors="replace"),
            stderr=stderr.read().decode(errors="replace"),
            exit_code=exit_code,
        )
    except Exception as e:
        return _result(False, error=str(e))


def ssh_execute_sudo(session_id: str, command: str, sudo_password: str) -> Dict[str, Any]:
    try:
        client = _get_client(session_id)
        full_cmd = f"sudo -S -p '' {command}"
        stdin, stdout, stderr = client.exec_command(full_cmd)
        stdin.write(sudo_password + "\n")
        stdin.flush()
        exit_code = stdout.channel.recv_exit_status()
        return _result(True, stdout=stdout.read().decode(), stderr=stderr.read().decode(), exit_code=exit_code)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_upload_file(session_id: str, local_path: str, remote_path: str) -> Dict[str, Any]:
    try:
        client = _get_client(session_id)
        with SCPClient(client.get_transport()) as scp:
            scp.put(local_path, remote_path)
        return _result(True, local_path=local_path, remote_path=remote_path)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_download_file(session_id: str, remote_path: str, local_path: str) -> Dict[str, Any]:
    try:
        pathlib.Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        client = _get_client(session_id)
        with SCPClient(client.get_transport()) as scp:
            scp.get(remote_path, local_path)
        return _result(True, remote_path=remote_path, local_path=local_path)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_upload_directory(session_id: str, local_dir: str, remote_dir: str) -> Dict[str, Any]:
    try:
        client = _get_client(session_id)
        with SCPClient(client.get_transport()) as scp:
            scp.put(local_dir, remote_dir, recursive=True)
        return _result(True)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_download_directory(session_id: str, remote_dir: str, local_dir: str) -> Dict[str, Any]:
    try:
        pathlib.Path(local_dir).mkdir(parents=True, exist_ok=True)
        client = _get_client(session_id)
        with SCPClient(client.get_transport()) as scp:
            scp.get(remote_dir, local_dir, recursive=True)
        return _result(True)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_list_directory(session_id: str, remote_path: str) -> Dict[str, Any]:
    try:
        sftp = _get_sftp(session_id)
        entries = []
        for attr in sftp.listdir_attr(remote_path):
            entries.append({
                "name": attr.filename,
                "size": attr.st_size,
                "mode": stat.filemode(attr.st_mode),
                "mtime": attr.st_mtime,
                "is_dir": stat.S_ISDIR(attr.st_mode),
            })
        return _result(True, entries=entries)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_file_exists(session_id: str, remote_path: str) -> Dict[str, Any]:
    try:
        sftp = _get_sftp(session_id)
        try:
            sftp.stat(remote_path)
            exists = True
        except FileNotFoundError:
            exists = False
        return _result(True, exists=exists)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_mkdir(session_id: str, remote_path: str) -> Dict[str, Any]:
    try:
        _get_sftp(session_id).mkdir(remote_path)
        return _result(True)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_rmdir(session_id: str, remote_path: str) -> Dict[str, Any]:
    try:
        _get_sftp(session_id).rmdir(remote_path)
        return _result(True)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_remove_file(session_id: str, remote_path: str) -> Dict[str, Any]:
    try:
        _get_sftp(session_id).remove(remote_path)
        return _result(True)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_chmod(session_id: str, remote_path: str, mode: int) -> Dict[str, Any]:
    try:
        _get_sftp(session_id).chmod(remote_path, mode)
        return _result(True)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_chown(session_id: str, remote_path: str, owner: int, group: int) -> Dict[str, Any]:
    try:
        _get_sftp(session_id).chown(remote_path, owner, group)
        return _result(True)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_read_file(session_id: str, remote_path: str) -> Dict[str, Any]:
    try:
        with _get_sftp(session_id).open(remote_path, "r") as f:
            return _result(True, content=f.read())
    except Exception as e:
        return _result(False, error=str(e))


def ssh_write_file(session_id: str, remote_path: str, content: str) -> Dict[str, Any]:
    try:
        with _get_sftp(session_id).open(remote_path, "w") as f:
            f.write(content)
        return _result(True)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_append_file(session_id: str, remote_path: str, content: str) -> Dict[str, Any]:
    try:
        with _get_sftp(session_id).open(remote_path, "a") as f:
            f.write(content)
        return _result(True)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_tail_file(session_id: str, remote_path: str, lines: int = 10) -> Dict[str, Any]:
    return ssh_execute(session_id, f"tail -n {int(lines)} {remote_path}")


def ssh_get_file_info(session_id: str, remote_path: str) -> Dict[str, Any]:
    try:
        attr = _get_sftp(session_id).stat(remote_path)
        return _result(True, size=attr.st_size, mode=attr.st_mode, mtime=attr.st_mtime)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_find_files(session_id: str, remote_path: str, pattern: str) -> Dict[str, Any]:
    return ssh_execute(session_id, f"find {remote_path} -name '{pattern}'")


def ssh_disk_usage(session_id: str) -> Dict[str, Any]:
    return ssh_execute(session_id, "df -h")


def ssh_memory_info(session_id: str) -> Dict[str, Any]:
    return ssh_execute(session_id, "free -h")


def ssh_cpu_info(session_id: str) -> Dict[str, Any]:
    return ssh_execute(session_id, "lscpu || cat /proc/cpuinfo")


def ssh_process_list(session_id: str) -> Dict[str, Any]:
    return ssh_execute(session_id, "ps aux")


def ssh_kill_process(session_id: str, pid: int) -> Dict[str, Any]:
    return ssh_execute(session_id, f"kill -9 {int(pid)}")


def ssh_service_status(session_id: str, service_name: str) -> Dict[str, Any]:
    return ssh_execute(session_id, f"systemctl status {service_name}")


def ssh_start_service(session_id: str, service_name: str) -> Dict[str, Any]:
    return ssh_execute(session_id, f"systemctl start {service_name}")


def ssh_stop_service(session_id: str, service_name: str) -> Dict[str, Any]:
    return ssh_execute(session_id, f"systemctl stop {service_name}")


def ssh_restart_service(session_id: str, service_name: str) -> Dict[str, Any]:
    return ssh_execute(session_id, f"systemctl restart {service_name}")


def ssh_port_forward(session_id: str, local_port: int, remote_host: str, remote_port: int) -> Dict[str, Any]:
    try:
        client = _get_client(session_id)
        transport = client.get_transport()
        if transport is None:
            raise RuntimeError("No transport available")

        stop_event = threading.Event()
        tunnel_id = str(uuid.uuid4())

        def _server() -> None:
            sock = socket.socket()
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", local_port))
            sock.listen(5)
            sock.settimeout(1)
            _TUNNELS[tunnel_id]["socket"] = sock
            while not stop_event.is_set():
                try:
                    client_sock, _ = sock.accept()
                except socket.timeout:
                    continue
                chan = transport.open_channel("direct-tcpip", (remote_host, remote_port), client_sock.getsockname())
                data = client_sock.recv(65535)
                if data:
                    chan.send(data)
                    client_sock.send(chan.recv(65535))
                chan.close()
                client_sock.close()
            sock.close()

        _TUNNELS[tunnel_id] = {"stop": stop_event}
        thread = threading.Thread(target=_server, daemon=True)
        _TUNNELS[tunnel_id]["thread"] = thread
        thread.start()
        return _result(True, tunnel_id=tunnel_id)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_tunnel_close(tunnel_id: str) -> Dict[str, Any]:
    try:
        tunnel = _TUNNELS.pop(tunnel_id)
        tunnel["stop"].set()
        return _result(True)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_check_connectivity(host: str, port: int = 22, timeout: int = 5) -> Dict[str, Any]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return _result(True, reachable=True)
    except Exception as e:
        return _result(False, reachable=False, error=str(e))


def ssh_get_system_info(session_id: str) -> Dict[str, Any]:
    return ssh_execute(session_id, "uname -a && hostname && whoami")


def ssh_get_uptime(session_id: str) -> Dict[str, Any]:
    return ssh_execute(session_id, "uptime")


def ssh_run_script(session_id: str, script_content: str, interpreter: str = "bash") -> Dict[str, Any]:
    try:
        remote_path = f"/tmp/script_{uuid.uuid4().hex}.sh"
        ssh_write_file(session_id, remote_path, script_content)
        ssh_chmod(session_id, remote_path, 0o755)
        result = ssh_execute(session_id, f"{interpreter} {remote_path}")
        ssh_remove_file(session_id, remote_path)
        return result
    except Exception as e:
        return _result(False, error=str(e))


def ssh_interactive_shell(session_id: str) -> Dict[str, Any]:
    try:
        client = _get_client(session_id)
        channel = client.invoke_shell()
        time.sleep(1)
        output = channel.recv(65535).decode(errors="replace") if channel.recv_ready() else ""
        channel.close()
        return _result(True, banner=output)
    except Exception as e:
        return _result(False, error=str(e))


def list_ssh_sessions() -> Dict[str, Any]:
    with _LOCK:
        sessions = list(_SESSIONS.keys())
    return _result(True, sessions=sessions)


def ssh_keep_alive(session_id: str) -> Dict[str, Any]:
    try:
        transport = _get_client(session_id).get_transport()
        if transport:
            transport.set_keepalive(30)
        return _result(True)
    except Exception as e:
        return _result(False, error=str(e))


def ssh_get_env(session_id: str, var_name: str) -> Dict[str, Any]:
    return ssh_execute(session_id, f"printenv {var_name}")


def ssh_set_env(session_id: str, var_name: str, value: str) -> Dict[str, Any]:
    return ssh_execute(session_id, f"export {var_name}={json.dumps(value)} && echo ${var_name}")
