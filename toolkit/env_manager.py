import os
import json
import subprocess
import venv
import sys
import shutil
import platform
import re
from pathlib import Path
from typing import Dict, Any, Union, Optional, List
from dotenv import dotenv_values, set_key, unset_key, load_dotenv as dotenv_loader


def get_env_var(name: str, default: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve an environment variable."""
    try:
        value = os.environ.get(name, default)
        return {"success": True, "message": f"Retrieved '{name}'", "data": value}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def set_env_var(name: str, value: str, persistent: bool = False) -> Dict[str, Any]:
    """Set an environment variable. Optionally persists to .env file."""
    try:
        os.environ[name] = value
        if persistent:
            env_file = Path(".env")
            if env_file.exists() and name in dotenv_values(env_file):
                set_key(str(env_file), name, value, quote_mode="never")
            else:
                with open(env_file, "a") as f:
                    escaped = value.replace('"', '\\"')
                    f.write(f'\n{name}="{escaped}"\n')
        return {"success": True, "message": f"Set '{name}'", "data": None}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def delete_env_var(name: str) -> Dict[str, Any]:
    """Delete an environment variable from memory and .env file."""
    try:
        os.environ.pop(name, None)
        env_file = Path(".env")
        if env_file.exists() and name in dotenv_values(env_file):
            unset_key(str(env_file), name)
        return {"success": True, "message": f"Deleted '{name}'", "data": None}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def list_env_vars(pattern: Optional[str] = None) -> Dict[str, Any]:
    """List environment variables, optionally filtered by regex pattern."""
    try:
        envs = dict(os.environ)
        if pattern:
            compiled = re.compile(pattern)
            envs = {k: v for k, v in envs.items() if compiled.search(k)}
        return {"success": True, "message": f"Listed {len(envs)} variable(s)", "data": envs}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def load_dotenv(filepath: Union[str, Path]) -> Dict[str, Any]:
    """Load variables from a .env file into os.environ."""
    try:
        path = Path(filepath)
        if not path.exists():
            return {"success": False, "message": "File not found", "data": None}
        values = dotenv_loader(str(path), override=True)
        loaded = dotenv_values(str(path))
        return {"success": True, "message": f"Loaded {len(loaded)} variables", "data": loaded}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def save_dotenv(variables: Dict[str, str], filepath: Union[str, Path]) -> Dict[str, Any]:
    """Save a dictionary of variables to a .env file."""
    try:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for k, v in variables.items():
                safe_v = str(v).replace('"', '\\"')
                f.write(f'{k}="{safe_v}"\n')
        return {"success": True, "message": f"Saved to {path}", "data": str(path)}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def create_virtualenv(path: Union[str, Path], python_version: Optional[str] = None) -> Dict[str, Any]:
    """Create a new virtual environment. Uses current interpreter (std venv limitation)."""
    try:
        path = Path(path).resolve()
        if python_version:
            # Note: venv module binds to the caller's python version.
            # We accept the parameter for API consistency but use sys.executable.
            pass
        builder = venv.EnvBuilder(with_pip=True, clear=True)
        builder.create(str(path))
        return {"success": True, "message": f"Created venv at {path}", "data": str(path)}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def activate_virtualenv(path: Union[str, Path]) -> Dict[str, Any]:
    """Simulate virtualenv activation by modifying process environment."""
    try:
        path = Path(path).resolve()
        suffix = "bin" if sys.platform != "win32" else "Scripts"
        bin_dir = path / suffix
        if not bin_dir.exists():
            return {"success": False, "message": "Invalid virtual environment path", "data": None}
        
        if "__ORIG_PATH__" not in os.environ and "VIRTUAL_ENV" not in os.environ:
            os.environ["__ORIG_PATH__"] = os.environ.get("PATH", "")
            
        os.environ["VIRTUAL_ENV"] = str(path)
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
        os.environ.pop("PYTHONHOME", None)
        
        return {"success": True, "message": "Activated virtual environment", "data": {"VIRTUAL_ENV": str(path)}}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def deactivate_virtualenv() -> Dict[str, Any]:
    """Restore environment to pre-activation state."""
    try:
        if not os.environ.get("VIRTUAL_ENV"):
            return {"success": False, "message": "No virtual environment active", "data": None}
        
        original_path = os.environ.pop("__ORIG_PATH__", os.environ.get("PATH", ""))
        os.environ["PATH"] = original_path
        os.environ.pop("VIRTUAL_ENV", None)
        
        return {"success": True, "message": "Deactivated virtual environment", "data": None}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def _get_pip_path(venv_path: Path) -> Path:
    """Internal helper to resolve pip executable path."""
    suffix = "bin/pip3" if sys.platform != "win32" else "Scripts/pip.exe"
    return venv_path / suffix


def install_package(package: str, venv_path: Union[str, Path]) -> Dict[str, Any]:
    """Install a Python package into a virtual environment."""
    try:
        pip = _get_pip_path(Path(venv_path))
        result = subprocess.run([str(pip), "install", package], capture_output=True, text=True, check=True)
        return {"success": True, "message": f"Installed {package}", "data": result.stdout.strip()}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.stderr.strip(), "data": None}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def uninstall_package(package: str, venv_path: Union[str, Path]) -> Dict[str, Any]:
    """Uninstall a Python package from a virtual environment."""
    try:
        pip = _get_pip_path(Path(venv_path))
        result = subprocess.run([str(pip), "uninstall", "-y", package], capture_output=True, text=True, check=True)
        return {"success": True, "message": f"Uninstalled {package}", "data": result.stdout.strip()}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.stderr.strip(), "data": None}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def list_installed_packages(venv_path: Union[str, Path]) -> Dict[str, Any]:
    """List installed packages in a virtual environment."""
    try:
        pip = _get_pip_path(Path(venv_path))
        result = subprocess.run([str(pip), "list", "--format=json"], capture_output=True, text=True, check=True)
        packages = json.loads(result.stdout)
        return {"success": True, "message": "Listed packages", "data": packages}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.stderr.strip(), "data": None}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def freeze_requirements(venv_path: Union[str, Path], output: Union[str, Path]) -> Dict[str, Any]:
    """Export installed packages to a requirements.txt file."""
    try:
        pip = _get_pip_path(Path(venv_path))
        result = subprocess.run([str(pip), "freeze"], capture_output=True, text=True, check=True)
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result.stdout)
        return {"success": True, "message": "Frozen requirements", "data": str(out_path)}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.stderr.strip(), "data": None}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def install_requirements(requirements_file: Union[str, Path], venv_path: Union[str, Path]) -> Dict[str, Any]:
    """Install packages from a requirements file into a virtual environment."""
    try:
        req_file = Path(requirements_file)
        pip = _get_pip_path(Path(venv_path))
        result = subprocess.run([str(pip), "install", "-r", str(req_file)], capture_output=True, text=True, check=True)
        return {"success": True, "message": "Installed requirements", "data": result.stdout.strip()}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.stderr.strip(), "data": None}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def get_python_version(venv_path: Union[str, Path]) -> Dict[str, Any]:
    """Get Python version of a virtual environment."""
    try:
        venv_dir = Path(venv_path)
        suffix = "bin/python" if sys.platform != "win32" else "Scripts/python.exe"
        python_exe = venv_dir / suffix
        result = subprocess.run([str(python_exe), "--version"], capture_output=True, text=True, check=True)
        version = result.stdout.strip().split()[-1]
        return {"success": True, "message": "Retrieved Python version", "data": version}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.stderr.strip(), "data": None}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def create_conda_env(name: str, python_version: Optional[str] = None) -> Dict[str, Any]:
    """Create a new Conda environment."""
    try:
        cmd = ["conda", "create", "-n", name, "-y"]
        if python_version:
            cmd.append(f"python={python_version}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return {"success": True, "message": f"Created conda env '{name}'", "data": result.stdout.strip()}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.stderr.strip(), "data": None}
    except FileNotFoundError:
        return {"success": False, "message": "Conda executable not found in PATH", "data": None}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def get_system_path() -> Dict[str, Any]:
    """Get the current system PATH as a list of directories."""
    try:
        paths = os.environ.get("PATH", "").split(os.pathsep)
        return {"success": True, "message": "Retrieved system PATH", "data": paths}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def add_to_path(directory: Union[str, Path], persistent: bool = False) -> Dict[str, Any]:
    """Add a directory to PATH. Optionally persists to shell profile or .env."""
    try:
        directory = str(Path(directory).resolve())
        current_paths = os.environ.get("PATH", "").split(os.pathsep)
        if directory in current_paths:
            return {"success": True, "message": "Directory already in PATH", "data": current_paths}
        
        current_paths.insert(0, directory)
        os.environ["PATH"] = os.pathsep.join(current_paths)
        
        if persistent:
            if sys.platform == "win32":
                subprocess.run(["setx", "PATH", f"{os.environ['PATH']}"], check=True, capture_output=True)
            else:
                shell_profile = Path.home() / ".bashrc"
                if not shell_profile.exists():
                    shell_profile = Path.home() / ".bash_profile"
                with open(shell_profile, "a") as f:
                    f.write(f'\nexport PATH="{directory}:$PATH"\n')
                    
        return {"success": True, "message": "Added directory to PATH", "data": current_paths}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def remove_from_path(directory: Union[str, Path]) -> Dict[str, Any]:
    """Remove a directory from the current process PATH."""
    try:
        directory = str(Path(directory).resolve())
        current_paths = os.environ.get("PATH", "").split(os.pathsep)
        if directory not in current_paths:
            return {"success": False, "message": "Directory not found in PATH", "data": None}
        
        filtered = [p for p in current_paths if p != directory]
        os.environ["PATH"] = os.pathsep.join(filtered)
        return {"success": True, "message": "Removed directory from PATH", "data": filtered}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def get_platform_info() -> Dict[str, Any]:
    """Retrieve detailed system platform information."""
    try:
        info = {
            "system": platform.system(),
            "node": platform.node(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        }
        return {"success": True, "message": "Retrieved platform info", "data": info}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def check_command_exists(command: str) -> Dict[str, Any]:
    """Check if a command exists in the system PATH."""
    try:
        exists = shutil.which(command) is not None
        return {"success": True, "message": f"Checked '{command}'", "data": exists}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def get_disk_space(path: Union[str, Path]) -> Dict[str, Any]:
    """Get disk usage statistics for a given path."""
    try:
        path = Path(path)
        usage = shutil.disk_usage(path)
        info = {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "total_gb": round(usage.total / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "used_percent": round((usage.used / usage.total) * 100, 2)
        }
        return {"success": True, "message": "Retrieved disk space info", "data": info}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def get_memory_info() -> Dict[str, Any]:
    """Get system memory information."""
    try:
        if os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo") as f:
                info = {}
                for line in f:
                    parts = line.split()
                    if parts[0].startswith(("MemTotal:", "MemAvailable:")):
                        info[parts[0].rstrip(":")] = int(parts[1]) * 1024
            total = info.get("MemTotal:", 0)
            available = info.get("MemAvailable:", 0)
        else:
            # Windows fallback
            cmd = 'wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /Value'
            out = subprocess.check_output(cmd, shell=True, text=True).strip()
            total = int(out.split("TotalVisibleMemorySize=")[1].split("\n")[0]) * 1024
            available = int(out.split("FreePhysicalMemory=")[1]) * 1024
            
        return {"success": True, "message": "Retrieved memory info", "data": {"total_bytes": total, "available_bytes": available}}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def get_cpu_info() -> Dict[str, Any]:
    """Get CPU information and load averages."""
    try:
        info: Dict[str, Any] = {
            "cpu_count": os.cpu_count() or 0,
            "processor_name": None,
            "load_average": None
        }
        if sys.platform != "win32":
            try:
                info["load_average"] = list(os.getloadavg())
            except OSError:
                pass
        try:
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if line.startswith("model name"):
                            info["processor_name"] = line.split(": ", 1)[1].strip()
                            break
        except Exception:
            pass
            
        return {"success": True, "message": "Retrieved CPU info", "data": info}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}


def export_env_config(output: Union[str, Path]) -> Dict[str, Any]:
    """Export current environment configuration to a JSON file."""
    try:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        config = {
            "env_vars": dict(os.environ),
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "path_directories": os.environ.get("PATH", "").split(os.pathsep)
        }
        out_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))
        return {"success": True, "message": "Exported environment config", "data": str(out_path)}
    except Exception as e:
        return {"success": False, "message": str(e), "data": None}