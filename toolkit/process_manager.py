# process_manager.py
"""
A lightweight, production‑ready toolkit for managing and inspecting OS processes.
All public functions return a ``Dict`` with the keys:

* ``success`` – ``bool`` – whether the operation succeeded
* ``data``    – ``Any``  – the useful payload (e.g. output, pid, stats …)
* ``error``   – ``str``  – error message when ``success`` is ``False``

The module relies on the standard library and the third‑party
``psutil`` package (install via ``pip install psutil``).
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
import shutil

# ----------------------------------------------------------------------
# Helper utilities
# ----------------------------------------------------------------------


def _make_result(
    success: bool,
    data: Any = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Standardised result dictionary."""
    return {"success": success, "data": data, "error": error}


def _resolve_path(path: str) -> str:
    """Resolve a user supplied path (tilde expansion, relative → absolute)."""
    try:
        return str(Path(path).expanduser().resolve())
    except Exception as exc:
        raise ValueError(f"Unable to resolve path '{path}': {exc}") from exc


# ----------------------------------------------------------------------
# Process execution helpers
# ----------------------------------------------------------------------


def run_command(
    command: str | List[str],
    timeout: Optional[float] = None,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    shell: bool = False,
) -> Dict[str, Any]:
    """
    Execute a command synchronously.

    Returns:
        ``{'success': True, 'data': {'stdout': ..., 'stderr': ..., 'returncode': ...}}``
        or ``{'success': False, 'error': ...}``.
    """
    try:
        if isinstance(command, list):
            cmd = command
        else:
            cmd = command if shell else shlex.split(command)

        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return _make_result(
            True,
            {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            },
        )
    except subprocess.TimeoutExpired as exc:
        return _make_result(False, None, f"Timeout after {timeout}s: {exc}")
    except Exception as exc:
        return _make_result(False, None, f"run_command error: {exc}")


def run_command_async(
    command: str | List[str],
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Start a command asynchronously (non‑blocking).

    Returns the ``subprocess.Popen`` object in ``data['process']``.
    """
    try:
        if isinstance(command, list):
            cmd = command
        else:
            cmd = shlex.split(command)

        popen = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return _make_result(True, {"pid": popen.pid, "process": popen})
    except Exception as exc:
        return _make_result(False, None, f"run_command_async error: {exc}")


def get_process_output(process_id: int) -> Dict[str, Any]:
    """
    Return the captured ``stdout``/``stderr`` of a previously started async
    process (if still alive, it will be waited for).
    """
    try:
        proc = psutil.Process(process_id)
        # psutil does not provide stdout/stderr directly; we rely on a
        # stored subprocess.Popen reference in ``run_command_async``.
        # If the caller passes a pid that originated from ``run_command_async``,
        # we cannot retrieve output without that reference.  Instead we fallback
        # to reading from the process’s file descriptors if possible.
        # Here we simply indicate that the operation is unsupported.
        return _make_result(
            False,
            None,
            "Retrieving live output from a PID alone is not supported; store the Popen object.",
        )
    except psutil.NoSuchProcess:
        return _make_result(False, None, f"No process with pid {process_id}")
    except Exception as exc:
        return _make_result(False, None, f"get_process_output error: {exc}")


def kill_process(pid: int, force: bool = False) -> Dict[str, Any]:
    """
    Kill a process. If ``force`` is true, ``SIGKILL`` is used, otherwise ``SIGTERM``.
    """
    try:
        proc = psutil.Process(pid)
        sig = signal.SIGKILL if force else signal.SIGTERM
        proc.kill() if force else proc.terminate()
        proc.wait(timeout=5)
        return _make_result(True, {"pid": pid, "signal": sig})
    except psutil.NoSuchProcess:
        return _make_result(False, None, f"Process {pid} does not exist")
    except psutil.TimeoutExpired:
        return _make_result(False, None, f"Process {pid} did not exit in time")
    except Exception as exc:
        return _make_result(False, None, f"kill_process error: {exc}")


def terminate_process(pid: int) -> Dict[str, Any]:
    """Gracefully terminate a process (SIGTERM)."""
    return kill_process(pid, force=False)


def is_process_running(pid: int) -> Dict[str, Any]:
    """Check if a PID is alive."""
    try:
        alive = psutil.pid_exists(pid)
        return _make_result(True, {"pid": pid, "running": alive})
    except Exception as exc:
        return _make_result(False, None, f"is_process_running error: {exc}")


def get_process_info(pid: int) -> Dict[str, Any]:
    """Retrieve a dictionary with detailed process information."""
    try:
        p = psutil.Process(pid)
        info = {
            "pid": p.pid,
            "name": p.name(),
            "exe": p.exe(),
            "cwd": p.cwd(),
            "cmdline": p.cmdline(),
            "status": p.status(),
            "create_time": p.create_time(),
            "username": p.username(),
            "cpu_times": p.cpu_times()._asdict(),
            "memory_info": p.memory_info()._asdict(),
        }
        return _make_result(True, info)
    except psutil.NoSuchProcess:
        return _make_result(False, None, f"Process {pid} not found")
    except Exception as exc:
        return _make_result(False, None, f"get_process_info error: {exc}")


def list_processes(filter_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Return a list of processes; if ``filter_name`` is given,
    only processes whose name contains the string (case‑insensitive) are returned.
    """
    try:
        result = []
        for p in psutil.process_iter(attrs=["pid", "name", "username"]):
            if filter_name and filter_name.lower() not in p.info["name"].lower():
                continue
            result.append(p.info)
        return _make_result(True, result)
    except Exception as exc:
        return _make_result(False, None, f"list_processes error: {exc}")


def find_process_by_name(name: str) -> Dict[str, Any]:
    """Return all processes whose executable name matches ``name`` (case‑insensitive)."""
    try:
        matched = [
            p.info
            for p in psutil.process_iter(attrs=["pid", "name", "username"])
            if p.info["name"].lower() == name.lower()
        ]
        return _make_result(True, matched)
    except Exception as exc:
        return _make_result(False, None, f"find_process_by_name error: {exc}")


def find_process_by_port(port: int) -> Dict[str, Any]:
    """Find processes listening on a specific TCP/UDP port."""
    try:
        connections = psutil.net_connections()
        matches = []
        for c in connections:
            if c.laddr and c.laddr.port == port:
                try:
                    p = psutil.Process(c.pid)
                    matches.append(
                        {
                            "pid": c.pid,
                            "process_name": p.name(),
                            "fd": c.fd,
                            "family": c.family,
                            "type": c.type,
                            "local_address": c.laddr,
                            "remote_address": c.raddr,
                            "status": c.status,
                        }
                    )
                except (psutil.NoSuchProcess, TypeError):
                    continue
        return _make_result(True, matches)
    except Exception as exc:
        return _make_result(False, None, f"find_process_by_port error: {exc}")


def get_process_tree(pid: int) -> Dict[str, Any]:
    """Return a nested dictionary representing the process hierarchy rooted at ``pid``."""
    try:
        root = psutil.Process(pid)

        def _build(proc: psutil.Process) -> Dict[str, Any]:
            children = proc.children(recursive=False)
            return {
                "pid": proc.pid,
                "name": proc.name(),
                "children": [_build(child) for child in children],
            }

        tree = _build(root)
        return _make_result(True, tree)
    except psutil.NoSuchProcess:
        return _make_result(False, None, f"Process {pid} not found")
    except Exception as exc:
        return _make_result(False, None, f"get_process_tree error: {exc}")


def get_cpu_usage(pid: int) -> Dict[str, Any]:
    """Return the CPU usage percent of a process."""
    try:
        p = psutil.Process(pid)
        usage = p.cpu_percent(interval=0.1)
        return _make_result(True, {"pid": pid, "cpu_percent": usage})
    except psutil.NoSuchProcess:
        return _make_result(False, None, f"Process {pid} does not exist")
    except Exception as exc:
        return _make_result(False, None, f"get_cpu_usage error: {exc}")


def get_memory_usage(pid: int) -> Dict[str, Any]:
    """Return memory usage statistics for a process."""
    try:
        p = psutil.Process(pid)
        mem = p.memory_info()._asdict()
        mem_percent = p.memory_percent()
        return _make_result(True, {"pid": pid, "memory": mem, "percent": mem_percent})
    except psutil.NoSuchProcess:
        return _make_result(False, None, f"Process {pid} does not exist")
    except Exception as exc:
        return _make_result(False, None, f"get_memory_usage error: {exc}")


def get_system_cpu() -> Dict[str, Any]:
    """System‑wide CPU statistics."""
    try:
        cpu = {
            "percent_per_cpu": psutil.cpu_percent(percpu=True),
            "overall_percent": psutil.cpu_percent(),
            "times": psutil.cpu_times()._asdict(),
            "count_logical": psutil.cpu_count(),
            "count_physical": psutil.cpu_count(logical=False),
        }
        return _make_result(True, cpu)
    except Exception as exc:
        return _make_result(False, None, f"get_system_cpu error: {exc}")


def get_system_memory() -> Dict[str, Any]:
    """System‑wide memory statistics."""
    try:
        vmem = psutil.virtual_memory()._asdict()
        swap = psutil.swap_memory()._asdict()
        return _make_result(True, {"virtual": vmem, "swap": swap})
    except Exception as exc:
        return _make_result(False, None, f"get_system_memory error: {exc}")


def get_system_disk() -> Dict[str, Any]:
    """Disk usage for each mounted partition."""
    try:
        partitions = []
        for part in psutil.disk_partitions(all=False):
            usage = psutil.disk_usage(part.mountpoint)._asdict()
            partitions.append(
                {
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "opts": part.opts,
                    "usage": usage,
                }
            )
        return _make_result(True, partitions)
    except Exception as exc:
        return _make_result(False, None, f"get_system_disk error: {exc}")


def get_system_uptime() -> Dict[str, Any]:
    """Return system uptime in seconds."""
    try:
        boot = psutil.boot_time()
        now = time.time()
        uptime = now - boot
        return _make_result(True, {"boot_time": boot, "uptime_seconds": uptime})
    except Exception as exc:
        return _make_result(False, None, f"get_system_uptime error: {exc}")


def get_system_load() -> Dict[str, Any]:
    """Return the 1, 5 and 15‑minute load averages (Unix only)."""
    try:
        if hasattr(os, "getloadavg"):
            load1, load5, load15 = os.getloadavg()
            return _make_result(True, {"1min": load1, "5min": load5, "15min": load15})
        else:
            return _make_result(False, None, "Load average not available on this platform")
    except Exception as exc:
        return _make_result(False, None, f"get_system_load error: {exc}")


# ----------------------------------------------------------------------
# Daemon helpers
# ----------------------------------------------------------------------


def start_daemon(
    command: str | List[str],
    pid_file: str,
    log_file: str,
) -> Dict[str, Any]:
    """
    Start a long‑running daemon, writing its PID to ``pid_file`` and output to ``log_file``.
    If a PID file already exists and the PID is alive, the daemon is not started again.
    """
    try:
        pid_path = Path(pid_file)
        if pid_path.is_file():
            try:
                existing_pid = int(pid_path.read_text().strip())
                if psutil.pid_exists(existing_pid):
                    return _make_result(
                        False,
                        None,
                        f"Daemon already running with PID {existing_pid}",
                    )
            except ValueError:
                pass  # Corrupted pid file → ignore

        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(command, list):
            cmd = command
        else:
            cmd = shlex.split(command)

        with log_path.open("ab") as f:
            proc = subprocess.Popen(
                cmd,
                stdout=f,
                stderr=f,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        pid_path.write_text(str(proc.pid))
        return _make_result(True, {"pid": proc.pid})
    except Exception as exc:
        return _make_result(False, None, f"start_daemon error: {exc}")


def stop_daemon(pid_file: str) -> Dict[str, Any]:
    """Terminate a daemon whose PID is stored in ``pid_file``."""
    try:
        pid_path = Path(pid_file)
        if not pid_path.is_file():
            return _make_result(False, None, "PID file does not exist")

        pid = int(pid_path.read_text().strip())
        res = kill_process(pid, force=True)
        if res["success"]:
            pid_path.unlink(missing_ok=True)
        return res
    except Exception as exc:
        return _make_result(False, None, f"stop_daemon error: {exc}")


def restart_daemon(
    command: str | List[str],
    pid_file: str,
    log_file: str,
) -> Dict[str, Any]:
    """Convenience: stop then start a daemon."""
    stop_res = stop_daemon(pid_file)
    if not stop_res["success"]:
        # Not a fatal error – continue to start
        pass
    start_res = start_daemon(command, pid_file, log_file)
    return start_res


# ----------------------------------------------------------------------
# Waiting / monitoring utilities
# ----------------------------------------------------------------------


def wait_for_process(pid: int, timeout: float) -> Dict[str, Any]:
    """Block until the given PID exits or ``timeout`` seconds elapse."""
    try:
        proc = psutil.Process(pid)
        start = time.time()
        while True:
            if not proc.is_running():
                return _make_result(True, {"pid": pid, "exited": True})
            if time.time() - start >= timeout:
                return _make_result(False, None, "Timeout waiting for process")
            time.sleep(0.2)
    except psutil.NoSuchProcess:
        return _make_result(True, {"pid": pid, "exited": True})
    except Exception as exc:
        return _make_result(False, None, f"wait_for_process error: {exc}")


def wait_for_port(host: str, port: int, timeout: float) -> Dict[str, Any]:
    """Wait until a TCP port becomes connectable."""
    import socket

    start = time.time()
    while True:
        try:
            with socket.create_connection((host, port), timeout=1):
                return _make_result(True, {"host": host, "port": port})
        except OSError:
            if time.time() - start >= timeout:
                return _make_result(False, None, "Timeout waiting for port")
            time.sleep(0.2)


def set_process_priority(pid: int, priority: int) -> Dict[str, Any]:
    """
    Set the niceness (Unix) or priority (Windows) of a process.
    ``priority`` corresponds to ``nice`` values on Unix (-20 … 19).
    """
    try:
        p = psutil.Process(pid)
        p.nice(priority)
        return _make_result(True, {"pid": pid, "nice": priority})
    except psutil.NoSuchProcess:
        return _make_result(False, None, f"Process {pid} not found")
    except Exception as exc:
        return _make_result(False, None, f"set_process_priority error: {exc}")


def get_process_connections(pid: int) -> Dict[str, Any]:
    """Return a list of network connections opened by the process."""
    try:
        p = psutil.Process(pid)
        conns = [
            {
                "fd": c.fd,
                "family": c.family,
                "type": c.type,
                "local_address": c.laddr,
                "remote_address": c.raddr,
                "status": c.status,
            }
            for c in p.connections()
        ]
        return _make_result(True, conns)
    except psutil.NoSuchProcess:
        return _make_result(False, None, f"Process {pid} not found")
    except Exception as exc:
        return _make_result(False, None, f"get_process_connections error: {exc}")


def get_open_files(pid: int) -> Dict[str, Any]:
    """List files opened by the process."""
    try:
        p = psutil.Process(pid)
        files = [f.path for f in p.open_files()]
        return _make_result(True, files)
    except psutil.NoSuchProcess:
        return _make_result(False, None, f"Process {pid} not found")
    except Exception as exc:
        return _make_result(False, None, f"get_open_files error: {exc}")


def monitor_process(
    pid: int,
    interval: float = 1.0,
    duration: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Sample CPU and memory usage of a process over time.

    Returns ``{'samples': [{'timestamp': ..., 'cpu': ..., 'memory': ...}, ...]}``.
    """
    try:
        p = psutil.Process(pid)
        samples = []
        start = time.time()
        while True:
            if duration and time.time() - start > duration:
                break
            if not p.is_running():
                break
            cpu = p.cpu_percent(interval=None)
            mem = p.memory_percent()
            samples.append(
                {"timestamp": time.time(), "cpu_percent": cpu, "memory_percent": mem}
            )
            time.sleep(interval)
        return _make_result(True, {"samples": samples})
    except psutil.NoSuchProcess:
        return _make_result(False, None, f"Process {pid} does not exist")
    except Exception as exc:
        return _make_result(False, None, f"monitor_process error: {exc}")


# ----------------------------------------------------------------------
# Parallel / pipe utilities
# ----------------------------------------------------------------------


def create_process_pool(
    commands: List[str | List[str]],
    max_workers: int = 4,
) -> Dict[str, Any]:
    """
    Execute a list of commands in parallel using a thread pool.
    Returns a list of each command’s result dict.
    """
    def _run(cmd: str | List[str]) -> Dict[str, Any]:
        return run_command(cmd)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_run, c) for c in commands]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        return _make_result(True, results)
    except Exception as exc:
        return _make_result(False, None, f"create_process_pool error: {exc}")


def pipe_commands(commands: List[List[str]]) -> Dict[str, Any]:
    """
    Execute a pipeline of commands (like ``cmd1 | cmd2 | cmd3``).
    ``commands`` is a list where each element is a list of arguments for that stage.
    Returns the final stage output.
    """
    try:
        if not commands:
            return _make_result(False, None, "No commands provided")

        # Build the pipeline
        prev = None
        processes = []
        for cmd in commands:
            proc = subprocess.Popen(
                cmd,
                stdin=prev.stdout if prev else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if prev:
                prev.stdout.close()  # allow prev to receive SIGPIPE if proc exits.
            prev = proc
            processes.append(proc)

        # Capture final output
        stdout, stderr = processes[-1].communicate()
        # Ensure earlier processes clean up
        for p in processes[:-1]:
            p.wait()

        return _make_result(
            True,
            {"stdout": stdout, "stderr": stderr, "returncode": processes[-1].returncode},
        )
    except Exception as exc:
        return _make_result(False, None, f"pipe_commands error: {exc}")


def run_in_background(command: str | List[str], log_file: str) -> Dict[str, Any]:
    """
    Execute a command detached from the parent, redirecting output to ``log_file``.
    Returns the child PID.
    """
    try:
        if isinstance(command, str):
            cmd = shlex.split(command)
        else:
            cmd = command

        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with log_path.open("ab") as f:
            proc = subprocess.Popen(
                cmd,
                stdout=f,
                stderr=f,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        return _make_result(True, {"pid": proc.pid})
    except Exception as exc:
        return _make_result(False, None, f"run_in_background error: {exc}")


# ----------------------------------------------------------------------
# Environment helpers
# ----------------------------------------------------------------------


def get_environment_variables() -> Dict[str, Any]:
    """Return a copy of ``os.environ`` as a dict."""
    try:
        return _make_result(True, dict(os.environ))
    except Exception as exc:
        return _make_result(False, None, f"get_environment_variables error: {exc}")


def set_environment_variable(key: str, value: str) -> Dict[str, Any]:
    """Set an environment variable in the current process."""
    try:
        os.environ[key] = value
        return _make_result(True, {key: value})
    except Exception as exc:
        return _make_result(False, None, f"set_environment_variable error: {exc}")


def expand_path(path: str) -> Dict[str, Any]:
    """Expand ``~`` and return the absolute path."""
    try:
        resolved = _resolve_path(path)
        return _make_result(True, resolved)
    except Exception as exc:
        return _make_result(False, None, f"expand_path error: {exc}")


def which_command(command: str) -> Dict[str, Any]:
    """Return the absolute path to an executable found in ``PATH``."""
    try:
        result = shutil.which(command)
        if result:
            return _make_result(True, result)
        return _make_result(False, None, f"Command '{command}' not found in PATH")
    except Exception as exc:
        return _make_result(False, None, f"which_command error: {exc}")


def get_shell() -> Dict[str, Any]:
    """Return the user's default shell (Unix) or the value of COMSPEC on Windows."""
    try:
        shell = os.getenv("SHELL") if os.name != "nt" else os.getenv("COMSPEC")
        if shell:
            return _make_result(True, shell)
        return _make_result(False, None, "Shell not defined in environment")
    except Exception as exc:
        return _make_result(False, None, f"get_shell error: {exc}")


# ----------------------------------------------------------------------
# Script runners / schedulers
# ----------------------------------------------------------------------


def run_python_script(script_path: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
    """Execute a Python script using the current interpreter."""
    try:
        script = _resolve_path(script_path)
        cmd = [sys.executable, script]
        if args:
            cmd.extend(args)
        return run_command(cmd)
    except Exception as exc:
        return _make_result(False, None, f"run_python_script error: {exc}")


def run_with_retry(
    command: str | List[str],
    max_retries: int = 3,
    delay: float = 1.0,
) -> Dict[str, Any]:
    """Run a command, retrying on failure up to ``max_retries`` times."""
    try:
        for attempt in range(1, max_retries + 1):
            res = run_command(command)
            if res["success"]:
                return res
            time.sleep(delay)
        return _make_result(False, None, f"All {max_retries} attempts failed")
    except Exception as exc:
        return _make_result(False, None, f"run_with_retry error: {exc}")


def schedule_command(command: str | List[str], delay_seconds: float) -> Dict[str, Any]:
    """Run ``command`` after ``delay_seconds`` using a background thread."""
    try:
        timer = threading.Timer(delay_seconds, lambda: run_command(command))
        timer.start()
        return _make_result(True, {"scheduled_in": delay_seconds, "timer": timer})
    except Exception as exc:
        return _make_result(False, None, f"schedule_command error: {exc}")


# ----------------------------------------------------------------------
# System networking & battery info
# ----------------------------------------------------------------------


def get_network_connections() -> Dict[str, Any]:
    """Return all current network connections on the host."""
    try:
        conns = [
            {
                "pid": c.pid,
                "fd": c.fd,
                "family": c.family,
                "type": c.type,
                "local_address": c.laddr,
                "remote_address": c.raddr,
                "status": c.status,
            }
            for c in psutil.net_connections()
        ]
        return _make_result(True, conns)
    except Exception as exc:
        return _make_result(False, None, f"get_network_connections error: {exc}")


def get_battery_info() -> Dict[str, Any]:
    """Return battery status if available (laptops, mobiles)."""
    try:
        if hasattr(psutil, "sensors_battery"):
            bat = psutil.sensors_battery()
            if bat is None:
                return _make_result(False, None, "No battery detected")
            info = {
                "percent": bat.percent,
                "secsleft": bat.secsleft,
                "power_plugged": bat.power_plugged,
            }
            return _make_result(True, info)
        else:
            return _make_result(False, None, "Battery information not supported on this platform")
    except Exception as exc:
        return _make_result(False, None, f"get_battery_info error: {exc}")


# ----------------------------------------------------------------------
# End of module
# ----------------------------------------------------------------------