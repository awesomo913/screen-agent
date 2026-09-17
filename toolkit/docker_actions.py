from __future__ import annotations

import json
import os
import pathlib
import re
import shlex
import subprocess
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

JsonDict = Dict[str, Any]
PathLike = Union[str, os.PathLike[str]]


def _result(success: bool, action: str, **kwargs: Any) -> JsonDict:
    payload: JsonDict = {"success": success, "action": action}
    payload.update(kwargs)
    return payload


def _run_command(
    cmd: Sequence[str],
    action: str,
    timeout: int = 300,
    check: bool = True,
    cwd: Optional[PathLike] = None,
) -> JsonDict:
    try:
        completed = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=str(cwd) if cwd else None,
        )
        result = {
            "command": shlex.join(cmd),
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
        if check and completed.returncode != 0:
            return _result(False, action, error=result["stderr"] or "Command failed", **result)
        return _result(True, action, **result)
    except subprocess.TimeoutExpired:
        return _result(False, action, error=f"Command timed out after {timeout}s", command=shlex.join(cmd))
    except FileNotFoundError:
        return _result(False, action, error="Docker executable not found", command=shlex.join(cmd))
    except Exception as exc:
        return _result(False, action, error=str(exc), command=shlex.join(cmd))


def _run_docker(args: Sequence[str], action: str, **kwargs: Any) -> JsonDict:
    return _run_command(["docker", *args], action, **kwargs)


def docker_version() -> JsonDict:
    return _run_docker(["version", "--format", "{{json .}}"], "docker_version")


def list_containers(all: bool = False) -> JsonDict:
    args = ["ps", "--format", "{{json .}}"]
    if all:
        args.insert(1, "-a")
    return _run_docker(args, "list_containers")


def run_container(
    image: str,
    name: Optional[str] = None,
    ports: Optional[Mapping[str, str]] = None,
    volumes: Optional[Mapping[str, str]] = None,
    env: Optional[Mapping[str, str]] = None,
    detach: bool = True,
    command: Optional[Union[str, Sequence[str]]] = None,
) -> JsonDict:
    args: List[str] = ["run"]
    if detach:
        args.append("-d")
    if name:
        args += ["--name", name]
    for host, container in (ports or {}).items():
        args += ["-p", f"{host}:{container}"]
    for src, dest in (volumes or {}).items():
        args += ["-v", f"{src}:{dest}"]
    for key, value in (env or {}).items():
        args += ["-e", f"{key}={value}"]
    args.append(image)
    if command:
        args += shlex.split(command) if isinstance(command, str) else list(command)
    return _run_docker(args, "run_container", timeout=600)


def stop_container(container_id: str) -> JsonDict:
    return _run_docker(["stop", container_id], "stop_container")


def start_container(container_id: str) -> JsonDict:
    return _run_docker(["start", container_id], "start_container")


def restart_container(container_id: str) -> JsonDict:
    return _run_docker(["restart", container_id], "restart_container")


def remove_container(container_id: str, force: bool = False) -> JsonDict:
    args = ["rm"]
    if force:
        args.append("-f")
    args.append(container_id)
    return _run_docker(args, "remove_container")


def container_logs(container_id: str, tail: int = 100, follow: bool = False) -> JsonDict:
    args = ["logs", "--tail", str(tail)]
    if follow:
        args.append("-f")
    args.append(container_id)
    return _run_docker(args, "container_logs", timeout=3600, check=False)


def container_inspect(container_id: str) -> JsonDict:
    return _run_docker(["inspect", container_id], "container_inspect")


def container_stats(container_id: str) -> JsonDict:
    return _run_docker(["stats", "--no-stream", container_id, "--format", "{{json .}}"], "container_stats")


def container_top(container_id: str) -> JsonDict:
    return _run_docker(["top", container_id], "container_top")


def exec_in_container(container_id: str, command: Union[str, Sequence[str]]) -> JsonDict:
    args = ["exec", container_id]
    args += shlex.split(command) if isinstance(command, str) else list(command)
    return _run_docker(args, "exec_in_container")


def copy_to_container(container_id: str, src: PathLike, dest: str) -> JsonDict:
    return _run_docker(["cp", str(src), f"{container_id}:{dest}"], "copy_to_container")


def copy_from_container(container_id: str, src: str, dest: PathLike) -> JsonDict:
    pathlib.Path(dest).parent.mkdir(parents=True, exist_ok=True)
    return _run_docker(["cp", f"{container_id}:{src}", str(dest)], "copy_from_container")


def list_images() -> JsonDict:
    return _run_docker(["images", "--format", "{{json .}}"], "list_images")


def pull_image(image: str, tag: str = "latest") -> JsonDict:
    return _run_docker(["pull", f"{image}:{tag}"], "pull_image", timeout=1800)


def build_image(path: PathLike, tag: str, dockerfile: Optional[PathLike] = None) -> JsonDict:
    args = ["build", "-t", tag]
    if dockerfile:
        args += ["-f", str(dockerfile)]
    args.append(str(path))
    return _run_docker(args, "build_image", timeout=3600)


def remove_image(image_id: str, force: bool = False) -> JsonDict:
    args = ["rmi"]
    if force:
        args.append("-f")
    args.append(image_id)
    return _run_docker(args, "remove_image")


def tag_image(source: str, target: str) -> JsonDict:
    return _run_docker(["tag", source, target], "tag_image")


def push_image(image: str, tag: str = "latest") -> JsonDict:
    return _run_docker(["push", f"{image}:{tag}"], "push_image", timeout=1800)


def image_inspect(image_id: str) -> JsonDict:
    return _run_docker(["inspect", image_id], "image_inspect")


def image_history(image_id: str) -> JsonDict:
    return _run_docker(["history", image_id, "--no-trunc"], "image_history")


def list_networks() -> JsonDict:
    return _run_docker(["network", "ls", "--format", "{{json .}}"], "list_networks")


def create_network(name: str, driver: str = "bridge") -> JsonDict:
    return _run_docker(["network", "create", "--driver", driver, name], "create_network")


def remove_network(network_id: str) -> JsonDict:
    return _run_docker(["network", "rm", network_id], "remove_network")


def connect_network(network_id: str, container_id: str) -> JsonDict:
    return _run_docker(["network", "connect", network_id, container_id], "connect_network")


def disconnect_network(network_id: str, container_id: str) -> JsonDict:
    return _run_docker(["network", "disconnect", network_id, container_id], "disconnect_network")


def list_volumes() -> JsonDict:
    return _run_docker(["volume", "ls", "--format", "{{json .}}"], "list_volumes")


def create_volume(name: str, driver: str = "local") -> JsonDict:
    return _run_docker(["volume", "create", "--driver", driver, name], "create_volume")


def remove_volume(volume_name: str) -> JsonDict:
    return _run_docker(["volume", "rm", volume_name], "remove_volume")


def volume_inspect(volume_name: str) -> JsonDict:
    return _run_docker(["volume", "inspect", volume_name], "volume_inspect")


def _compose_cmd(compose_file: PathLike, subcommand: Sequence[str]) -> List[str]:
    return ["compose", "-f", str(compose_file), *subcommand]


def docker_compose_up(compose_file: PathLike, detach: bool = True) -> JsonDict:
    cmd = ["up"]
    if detach:
        cmd.append("-d")
    return _run_docker(_compose_cmd(compose_file, cmd), "docker_compose_up", timeout=1800)


def docker_compose_down(compose_file: PathLike) -> JsonDict:
    return _run_docker(_compose_cmd(compose_file, ["down"]), "docker_compose_down", timeout=1800)


def docker_compose_ps(compose_file: PathLike) -> JsonDict:
    return _run_docker(_compose_cmd(compose_file, ["ps"]), "docker_compose_ps")


def docker_compose_logs(compose_file: PathLike, service: Optional[str] = None) -> JsonDict:
    cmd = ["logs"]
    if service:
        cmd.append(service)
    return _run_docker(_compose_cmd(compose_file, cmd), "docker_compose_logs", timeout=1800)


def docker_compose_build(compose_file: PathLike) -> JsonDict:
    return _run_docker(_compose_cmd(compose_file, ["build"]), "docker_compose_build", timeout=3600)


def system_prune(all: bool = False, volumes: bool = False) -> JsonDict:
    args = ["system", "prune", "-f"]
    if all:
        args.append("-a")
    if volumes:
        args.append("--volumes")
    return _run_docker(args, "system_prune", timeout=1800)


def system_df() -> JsonDict:
    return _run_docker(["system", "df"], "system_df")


def system_info() -> JsonDict:
    return _run_docker(["system", "info"], "system_info")


def export_container(container_id: str, output_path: PathLike) -> JsonDict:
    output = pathlib.Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    res = _run_command(["docker", "export", "-o", str(output), container_id], "export_container", timeout=1800)
    if res["success"]:
        res["output_path"] = str(output)
    return res


def import_container(file_path: PathLike, image_name: str) -> JsonDict:
    return _run_docker(["import", str(file_path), image_name], "import_container", timeout=1800)


def save_image(image_id: str, output_path: PathLike) -> JsonDict:
    output = pathlib.Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    return _run_command(["docker", "save", "-o", str(output), image_id], "save_image", timeout=1800)


def load_image(file_path: PathLike) -> JsonDict:
    return _run_docker(["load", "-i", str(file_path)], "load_image", timeout=1800)


def container_health(container_id: str) -> JsonDict:
    res = _run_docker(["inspect", "--format", "{{json .State.Health}}", container_id], "container_health")
    if res["success"] and res.get("stdout"):
        try:
            res["health"] = json.loads(res["stdout"])
        except json.JSONDecodeError:
            res["health"] = res["stdout"]
    return res


def wait_container_ready(container_id: str, timeout: int = 60) -> JsonDict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        health = container_health(container_id)
        if health["success"]:
            data = health.get("health")
            if isinstance(data, dict) and data.get("Status") == "healthy":
                return _result(True, "wait_container_ready", container_id=container_id, status="healthy")
            inspect = container_inspect(container_id)
            if inspect["success"] and '"Running": true' in inspect.get("stdout", ""):
                return _result(True, "wait_container_ready", container_id=container_id, status="running")
        time.sleep(2)
    return _result(False, "wait_container_ready", error="Timeout waiting for container readiness")


def get_container_ip(container_id: str) -> JsonDict:
    return _run_docker(
        ["inspect", "--format", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", container_id],
        "get_container_ip",
    )


def port_mapping(container_id: str) -> JsonDict:
    res = _run_docker(["port", container_id], "port_mapping")
    if res["success"]:
        mappings: List[Dict[str, str]] = []
        for line in res.get("stdout", "").splitlines():
            match = re.match(r"(.+?) -> (.+)", line)
            if match:
                mappings.append({"container_port": match.group(1), "host_binding": match.group(2)})
        res["mappings"] = mappings
    return res
