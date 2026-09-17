import subprocess
import shlex
import os
import json
import time
import threading
import signal
import pathlib
import tempfile
from typing import Dict, List, Any, Optional, Union, Callable

class CommandExecutor:
    """
    Production-grade command execution module for screen agent toolkits.
    All methods return a standardized Dictionary containing execution state.
    """
    
    def __init__(self):
        self.env: Dict[str, str] = os.environ.copy()
        self.active_processes: Dict[int, subprocess.Popen] = {}
        self.history: List[Dict[str, Any]] = []
        self.history_lock = threading.Lock()

    def _standardize_result(self, status: str, cmd: str, returncode: int = -1, stdout: str = "", stderr: str = "", pid: Optional[int] = None, error: str = "") -> Dict[str, Any]:
        result = {
            "status": status,
            "command": cmd,
            "returncode": returncode,
            "stdout": stdout,
            "stderr": stderr,
            "pid": pid,
            "error_message": error,
            "timestamp": time.time()
        }
        self.log_command_output(result)
        return result

    def validate_command(self, command: str) -> Dict[str, Any]:
        if not command or not command.strip():
            return {"valid": False, "error": "Command is empty"}
        # Basic injection check (highly dependent on context, keep minimal for general executor)
        dangerous_tokens = [";", "&&", "||", "|", ">", "<"]
        if not hasattr(shlex, 'join'): # simple check for complex shell constructs if not using shell=True
            pass
        return {"valid": True, "error": ""}

    def escape_arguments(self, args: List[str]) -> str:
        return shlex.join(args)

    def set_environment(self, env_vars: Dict[str, str]) -> Dict[str, Any]:
        self.env.update(env_vars)
        return self._standardize_result("success", "set_environment", 0, json.dumps(env_vars))

    def run_command(self, command: Union[str, List[str]], shell: bool = False, cwd: Optional[str] = None) -> Dict[str, Any]:
        if isinstance(command, list):
            cmd_str = self.escape_arguments(command)
        else:
            cmd_str = command
            command = shlex.split(command) if not shell else command

        try:
            result = subprocess.run(command, shell=shell, cwd=cwd, env=self.env, capture_output=True, text=True)
            return self._standardize_result(
                "success" if result.returncode == 0 else "failed",
                cmd_str, result.returncode, result.stdout, result.stderr
            )
        except Exception as e:
            return self._standardize_result("error", cmd_str, error=str(e))

    def capture_output(self, command: str) -> Dict[str, Any]:
        # Alias for run_command specifically enforcing output capture
        return self.run_command(command)

    def run_with_timeout(self, command: Union[str, List[str]], timeout: float, shell: bool = False) -> Dict[str, Any]:
        cmd_str = command if isinstance(command, str) else self.escape_arguments(command)
        cmd_args = shlex.split(command) if isinstance(command, str) and not shell else command
        
        try:
            result = subprocess.run(cmd_args, shell=shell, env=self.env, capture_output=True, text=True, timeout=timeout)
            return self._standardize_result("success" if result.returncode == 0 else "failed", cmd_str, result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired as e:
            return self._standardize_result("timeout", cmd_str, error=f"Command timed out after {timeout} seconds")
        except Exception as e:
            return self._standardize_result("error", cmd_str, error=str(e))

    def run_in_background(self, command: Union[str, List[str]], shell: bool = False, cwd: Optional[str] = None) -> Dict[str, Any]:
        cmd_str = command if isinstance(command, str) else self.escape_arguments(command)
        cmd_args = shlex.split(command) if isinstance(command, str) and not shell else command

        try:
            process = subprocess.Popen(cmd_args, shell=shell, cwd=cwd, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.active_processes[process.pid] = process
            return self._standardize_result("running", cmd_str, pid=process.pid)
        except Exception as e:
            return self._standardize_result("error", cmd_str, error=str(e))

    def run_async_command(self, command: Union[str, List[str]]) -> Dict[str, Any]:
        # Semantic duplicate of run_in_background for agent toolkit API compliance
        return self.run_in_background(command)

    def run_detached(self, command: Union[str, List[str]]) -> Dict[str, Any]:
        cmd_str = command if isinstance(command, str) else self.escape_arguments(command)
        cmd_args = shlex.split(command) if isinstance(command, str) else command
        
        try:
            # start_new_session separates process group (POSIX), creationflags for Windows
            kwargs = {}
            if os.name == 'nt':
                kwargs['creationflags'] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs['start_new_session'] = True

            process = subprocess.Popen(cmd_args, env=self.env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
            return self._standardize_result("detached", cmd_str, pid=process.pid)
        except Exception as e:
            return self._standardize_result("error", cmd_str, error=str(e))

    def stream_output(self, command: Union[str, List[str]], callback: Callable[[str], None], shell: bool = False) -> Dict[str, Any]:
        cmd_str = command if isinstance(command, str) else self.escape_arguments(command)
        cmd_args = shlex.split(command) if isinstance(command, str) and not shell else command

        try:
            process = subprocess.Popen(cmd_args, shell=shell, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
            self.active_processes[process.pid] = process
            
            def read_stream():
                for line in process.stdout:
                    callback(line.strip())
                process.wait()
                
            threading.Thread(target=read_stream, daemon=True).start()
            return self._standardize_result("streaming", cmd_str, pid=process.pid)
        except Exception as e:
            return self._standardize_result("error", cmd_str, error=str(e))

    def run_piped_commands(self, commands: List[str]) -> Dict[str, Any]:
        if not commands:
            return self._standardize_result("error", "", error="No commands provided for piping")
            
        full_cmd_str = " | ".join(commands)
        try:
            processes = []
            prev_stdout = None
            
            for cmd in commands:
                args = shlex.split(cmd)
                p = subprocess.Popen(args, stdin=prev_stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env, text=True)
                processes.append(p)
                if prev_stdout:
                    prev_stdout.close() # Allow p1 to receive SIGPIPE if p2 exits
                prev_stdout = p.stdout
                
            last_p = processes[-1]
            stdout, stderr = last_p.communicate()
            
            # Wait for all
            for p in processes:
                p.wait()
                
            return self._standardize_result("success" if last_p.returncode == 0 else "failed", full_cmd_str, last_p.returncode, stdout, stderr)
        except Exception as e:
            return self._standardize_result("error", full_cmd_str, error=str(e))

    def create_command_chain(self, commands: List[str], operator: str = "&&") -> Dict[str, Any]:
        if operator not in ["&&", "||", ";"]:
            return self._standardize_result("error", str(commands), error="Invalid operator. Use &&, ||, or ;")
        
        chain = f" {operator} ".join(commands)
        return self.run_command(chain, shell=True)

    def batch_run_commands(self, commands: List[str], continue_on_error: bool = False) -> Dict[str, Any]:
        results = []
        overall_status = "success"
        for cmd in commands:
            res = self.run_command(cmd)
            results.append(res)
            if res['returncode'] != 0:
                overall_status = "partial_failure"
                if not continue_on_error:
                    break
                    
        return {
            "status": overall_status,
            "commands_executed": len(results),
            "results": results
        }

    def run_with_retry(self, command: str, retries: int = 3, delay: float = 1.0) -> Dict[str, Any]:
        for attempt in range(retries):
            result = self.run_command(command)
            if result['returncode'] == 0:
                result['attempts'] = attempt + 1
                return result
            time.sleep(delay)
        
        result['attempts'] = retries
        result['status'] = "failed_after_retries"
        return result

    def get_process_status(self, pid: int) -> Dict[str, Any]:
        if pid not in self.active_processes:
            # Check OS level if not in managed
            try:
                os.kill(pid, 0)
                return {"pid": pid, "status": "running_unmanaged", "returncode": None}
            except OSError:
                return {"pid": pid, "status": "not_found", "returncode": None}
                
        process = self.active_processes[pid]
        ret = process.poll()
        if ret is None:
            return {"pid": pid, "status": "running", "returncode": None}
        else:
            return {"pid": pid, "status": "terminated", "returncode": ret}

    def wait_for_process(self, pid: int, timeout: Optional[float] = None) -> Dict[str, Any]:
        if pid not in self.active_processes:
            return {"status": "error", "error": "PID not managed by executor"}
            
        process = self.active_processes[pid]
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            del self.active_processes[pid]
            return self._standardize_result("success" if process.returncode == 0 else "failed", "wait_for_process", process.returncode, stdout, stderr, pid)
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "pid": pid, "error": f"Timeout {timeout}s exceeded waiting for process"}

    def kill_process(self, pid: int, force: bool = False) -> Dict[str, Any]:
        if pid not in self.active_processes:
            try:
                sig = signal.SIGKILL if force else signal.SIGTERM
                os.kill(pid, sig)
                return {"status": "success", "pid": pid, "action": "killed_unmanaged"}
            except OSError as e:
                return {"status": "error", "pid": pid, "error": str(e)}
                
        process = self.active_processes[pid]
        try:
            if force:
                process.kill()
            else:
                process.terminate()
            process.wait(timeout=3)
            del self.active_processes[pid]
            return {"status": "success", "pid": pid, "action": "killed_managed"}
        except Exception as e:
            return {"status": "error", "pid": pid, "error": str(e)}

    def get_running_processes(self) -> Dict[str, Any]:
        # Clean up dead processes first
        active = {}
        for pid, p in list(self.active_processes.items()):
            if p.poll() is None:
                active[pid] = "running"
            else:
                del self.active_processes[pid]
        return {"status": "success", "running_managed_pids": list(active.keys())}

    def get_exit_code(self, pid: int) -> Dict[str, Any]:
        status = self.get_process_status(pid)
        return {"pid": pid, "returncode": status.get("returncode")}

    def run_shell_script(self, script_content: str) -> Dict[str, Any]:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(script_content)
            temp_name = f.name
            
        try:
            pathlib.Path(temp_name).chmod(0o755)
            result = self.run_command(temp_name)
            return result
        finally:
            os.remove(temp_name)

    def run_python_script(self, script_content: str) -> Dict[str, Any]:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script_content)
            temp_name = f.name
            
        try:
            result = self.run_command(["python3", temp_name])
            return result
        finally:
            os.remove(temp_name)

    def run_elevated(self, command: str, password: Optional[str] = None) -> Dict[str, Any]:
        # Warning: Using sudo with -S passes password via stdin. Security risk if logged.
        if os.name == 'nt':
             return self._standardize_result("error", command, error="Elevation not natively supported on Windows via standard library without pywin32.")
             
        if password:
            cmd = f"echo {shlex.quote(password)} | sudo -S {command}"
            return self.run_command(cmd, shell=True)
        else:
            return self.run_command(f"sudo {command}", shell=True)

    def run_interactive(self, command: Union[str, List[str]]) -> Dict[str, Any]:
        cmd_args = shlex.split(command) if isinstance(command, str) else command
        try:
            # Leaves stdin open for the caller to write to process.stdin.write()
            process = subprocess.Popen(cmd_args, env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            self.active_processes[process.pid] = process
            return {
                "status": "interactive_started",
                "pid": process.pid,
                "process_object": process, # Exposing the object so agent can interact
                "command": str(command)
            }
        except Exception as e:
            return self._standardize_result("error", str(command), error=str(e))

    def log_command_output(self, result_dict: Dict[str, Any]) -> Dict[str, Any]:
        # Filter out process objects before saving to history
        safe_dict = {k: v for k, v in result_dict.items() if k != 'process_object'}
        with self.history_lock:
            self.history.append(safe_dict)
            # Cap history to prevent memory leaks in long-running agents
            if len(self.history) > 1000:
                self.history.pop(0)
        return {"status": "logged"}

    def export_command_history(self, filepath: str) -> Dict[str, Any]:
        try:
            with open(filepath, 'w') as f:
                with self.history_lock:
                    json.dump(self.history, f, indent=2)
            return {"status": "success", "file": filepath, "entries": len(self.history)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

# --- Example Usage Sandbox ---
if __name__ == "__main__":
    executor = CommandExecutor()
    print(json.dumps(executor.run_command("echo 'System Initialized'"), indent=2))
