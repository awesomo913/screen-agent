"""toolkit_108_docker_tools.py
Docker container management — run, stop, list, pull, inspect containers via CLI.
"""
import subprocess, os, sys, json, re
from pathlib import Path

def check_available() -> dict:
    """Check if dependencies for docker are available."""
    import importlib
    libs = {"docker": "docker", "openapi": "openapi_spec_validator", "graphql": "gql", "websocket": "websocket", "database": "sqlite3", "file_watcher_api": "watchdog", "celery": "celery", "redis": "redis", "aws": "boto3", "performance": "py_spy", "code_search": None}
    lib = libs.get("docker")
    if lib is None:
        return {"success": True, "data": {"available": True, "note": "stdlib only"}, "error": None}
    try:
        importlib.import_module(lib)
        return {"success": True, "data": {"available": True, "library": lib}, "error": None}
    except ImportError:
        return {"success": True, "data": {"available": False, "install": "pip install " + lib}, "error": None}

def run_container(image: str, command: str = "", ports: str = "", env_vars: list = [], detach: bool = True, name: str = "") -> dict:
    """Run a Docker container."""
    try:
        cmd = ["docker", "run"]
        if detach: cmd.append("-d")
        if name: cmd += ["--name", name]
        if ports: cmd += ["-p", ports]
        for e in env_vars: cmd += ["-e", e]
        cmd.append(image)
        if command: cmd.extend(command.split())
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return {"success": r.returncode == 0, "data": {"container_id": r.stdout.strip()[:12], "cmd": " ".join(cmd)}, "error": r.stderr if r.returncode != 0 else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_containers(all_containers: bool = False) -> dict:
    """List Docker containers."""
    try:
        cmd = ["docker", "ps", "--format", "json"]
        if all_containers: cmd.append("-a")
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            containers = [json.loads(l) for l in r.stdout.splitlines() if l.strip()]
            return {"success": True, "data": containers, "error": None}
        return {"success": False, "data": None, "error": r.stderr}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def stop_container(container_id: str) -> dict:
    """Stop a Docker container."""
    try:
        r = subprocess.run(["docker", "stop", container_id], capture_output=True, text=True, timeout=30)
        return {"success": r.returncode == 0, "data": r.stdout.strip(), "error": r.stderr if r.returncode != 0 else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def remove_container(container_id: str, force: bool = False) -> dict:
    """Remove a Docker container."""
    try:
        cmd = ["docker", "rm"]
        if force: cmd.append("-f")
        cmd.append(container_id)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return {"success": r.returncode == 0, "data": r.stdout.strip(), "error": r.stderr if r.returncode != 0 else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def pull_image(image: str) -> dict:
    """Pull a Docker image."""
    try:
        r = subprocess.run(["docker", "pull", image], capture_output=True, text=True, timeout=120)
        return {"success": r.returncode == 0, "data": r.stdout[-500:], "error": r.stderr if r.returncode != 0 else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_container_logs(container_id: str, tail: int = 50) -> dict:
    """Get logs from a Docker container."""
    try:
        r = subprocess.run(["docker", "logs", "--tail", str(tail), container_id], capture_output=True, text=True, timeout=15)
        return {"success": r.returncode == 0, "data": r.stdout + r.stderr, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def execute_in_container(container_id: str, command: str) -> dict:
    """Execute a command inside a running container."""
    try:
        cmd = ["docker", "exec", container_id] + command.split()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {"success": r.returncode == 0, "data": r.stdout, "error": r.stderr if r.returncode != 0 else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_images() -> dict:
    """List Docker images."""
    try:
        r = subprocess.run(["docker", "images", "--format", "json"], capture_output=True, text=True, timeout=15)
        images = [json.loads(l) for l in r.stdout.splitlines() if l.strip()]
        return {"success": r.returncode == 0, "data": images, "error": r.stderr if r.returncode != 0 else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def docker_compose_up(compose_file: str = "docker-compose.yml", detach: bool = True) -> dict:
    """Start services with docker-compose."""
    try:
        cmd = ["docker", "compose", "-f", compose_file, "up"]
        if detach: cmd.append("-d")
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return {"success": r.returncode == 0, "data": r.stdout[-500:], "error": r.stderr if r.returncode != 0 else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def docker_compose_down(compose_file: str = "docker-compose.yml") -> dict:
    """Stop services with docker-compose."""
    try:
        r = subprocess.run(["docker", "compose", "-f", compose_file, "down"], capture_output=True, text=True, timeout=60)
        return {"success": r.returncode == 0, "data": r.stdout, "error": r.stderr if r.returncode != 0 else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def run_code_in_docker(image: str, code: str, language: str = "python", timeout: int = 15) -> dict:
    """Run code in an isolated Docker container."""
    try:
        import tempfile
        ext_map = {"python": "py", "node": "js", "ruby": "rb"}
        ext = ext_map.get(language, "py")
        with tempfile.NamedTemporaryFile(suffix="." + ext, mode="w", delete=False) as f:
            f.write(code); fname = f.name
        cmd = ["docker", "run", "--rm", "-v", fname + ":/code." + ext, image, language, "/code." + ext]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        os.unlink(fname)
        return {"success": r.returncode == 0, "data": {"stdout": r.stdout, "stderr": r.stderr, "exit_code": r.returncode}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_docker_stats() -> dict:
    """Get resource stats for running containers."""
    try:
        r = subprocess.run(["docker", "stats", "--no-stream", "--format", "json"], capture_output=True, text=True, timeout=15)
        stats = [json.loads(l) for l in r.stdout.splitlines() if l.strip()]
        return {"success": r.returncode == 0, "data": stats, "error": r.stderr if r.returncode != 0 else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}