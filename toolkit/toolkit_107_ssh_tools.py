"""toolkit_107_ssh_tools.py
SSH remote execution and SFTP file transfer via paramiko or subprocess ssh/scp.
"""
import subprocess, os, re, json
try:
    import paramiko; HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False

def _ssh_cmd(host, username, port, key_path):
    cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-p", str(port)]
    if key_path: cmd += ["-i", key_path]
    target = (username + "@" if username else "") + host
    return cmd + [target]

def run_remote_command(host: str, command: str, username: str = "", password: str = "", key_path: str = "", port: int = 22, timeout: int = 30) -> dict:
    """Run a command on a remote host via SSH."""
    try:
        if HAS_PARAMIKO:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            kw = {"hostname": host, "port": port, "username": username, "timeout": timeout}
            if key_path: kw["key_filename"] = key_path
            elif password: kw["password"] = password
            client.connect(**kw)
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            code = stdout.channel.recv_exit_status()
            client.close()
            return {"success": True, "data": {"stdout": out, "stderr": err, "exit_code": code}, "error": None}
        cmd = _ssh_cmd(host, username, port, key_path) + [command]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"success": r.returncode == 0, "data": {"stdout": r.stdout, "stderr": r.stderr, "exit_code": r.returncode}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def upload_file(host: str, local_path: str, remote_path: str, username: str = "", password: str = "", key_path: str = "", port: int = 22) -> dict:
    """Upload a file to remote host via SFTP/SCP."""
    try:
        if HAS_PARAMIKO:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            kw = {"hostname": host, "port": port, "username": username}
            if key_path: kw["key_filename"] = key_path
            elif password: kw["password"] = password
            client.connect(**kw); sftp = client.open_sftp()
            sftp.put(local_path, remote_path); sftp.close(); client.close()
            return {"success": True, "data": {"local": local_path, "remote": remote_path}, "error": None}
        cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-P", str(port)]
        if key_path: cmd += ["-i", key_path]
        dest = (username + "@" if username else "") + host + ":" + remote_path
        r = subprocess.run(cmd + [local_path, dest], capture_output=True, text=True, timeout=60)
        return {"success": r.returncode == 0, "data": {"local": local_path, "remote": dest}, "error": r.stderr if r.returncode != 0 else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def download_file(host: str, remote_path: str, local_path: str, username: str = "", password: str = "", key_path: str = "", port: int = 22) -> dict:
    """Download a file from remote host via SCP."""
    try:
        cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-P", str(port)]
        if key_path: cmd += ["-i", key_path]
        src = (username + "@" if username else "") + host + ":" + remote_path
        r = subprocess.run(cmd + [src, local_path], capture_output=True, text=True, timeout=60)
        return {"success": r.returncode == 0, "data": {"remote": remote_path, "local": local_path}, "error": r.stderr if r.returncode != 0 else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def test_connection(host: str, username: str = "", key_path: str = "", port: int = 22) -> dict:
    """Test SSH connectivity."""
    r = run_remote_command(host, "echo ok", username=username, key_path=key_path, port=port, timeout=8)
    return {"success": r["success"], "data": {"connected": r["success"], "host": host}, "error": r.get("error")}

def list_remote_files(host: str, remote_path: str = ".", username: str = "", key_path: str = "", port: int = 22) -> dict:
    """List files in a remote directory."""
    r = run_remote_command(host, "ls -la " + remote_path, username=username, key_path=key_path, port=port)
    if r["success"]:
        files = r["data"]["stdout"].splitlines()
        return {"success": True, "data": {"files": files, "count": len(files)}, "error": None}
    return r

def get_remote_info(host: str, username: str = "", key_path: str = "", port: int = 22) -> dict:
    """Get system info from remote host."""
    try:
        info = {}
        for k, cmd in {"hostname": "hostname", "os": "uname -a", "uptime": "uptime", "disk": "df -h /"}.items():
            r = run_remote_command(host, cmd, username=username, key_path=key_path, port=port)
            info[k] = r["data"]["stdout"].strip() if r["success"] else "N/A"
        return {"success": True, "data": info, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_paramiko() -> dict:
    """Check if paramiko is installed."""
    return {"success": True, "data": {"paramiko_available": HAS_PARAMIKO}, "error": None}

def generate_ssh_config(host: str, hostname: str, username: str, port: int = 22, key_path: str = "") -> dict:
    """Generate SSH config block."""
    try:
        lines2 = ["Host " + host, "    HostName " + hostname, "    User " + username, "    Port " + str(port)]
        if key_path: lines2.append("    IdentityFile " + key_path)
        return {"success": True, "data": chr(10).join(lines2), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_tunnel_cmd(local_port: int, remote_host: str, remote_port: int, jump_host: str, username: str = "") -> dict:
    """Build SSH tunnel command string."""
    try:
        target = (username + "@" if username else "") + jump_host
        cmd = "ssh -L " + str(local_port) + ":" + remote_host + ":" + str(remote_port) + " -N " + target
        return {"success": True, "data": cmd, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def run_script_remote(host: str, script: str, username: str = "", key_path: str = "", port: int = 22) -> dict:
    """Run a shell script string on remote host."""
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(suffix=".sh", mode="w", delete=False) as f:
            f.write(script); fname = f.name
        r_up = upload_file(host, fname, "/tmp/_screen_agent_script.sh", username=username, key_path=key_path, port=port)
        os.unlink(fname)
        if not r_up["success"]: return r_up
        return run_remote_command(host, "bash /tmp/_screen_agent_script.sh", username=username, key_path=key_path, port=port)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}