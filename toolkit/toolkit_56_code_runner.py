"""
toolkit_56_code_runner.py
Execute code snippets in various languages, capture output, measure execution
time, and run scripts from files. Supports Python, PowerShell, JS (node), cmd.
"""
from __future__ import annotations
import subprocess
import tempfile
import os
import time
from typing import Any, Dict, List

def run_python_snippet(code: str, timeout: float = 10.0) -> Dict[str, Any]:
    try:
        import sys
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp = f.name
        start = time.perf_counter()
        result = subprocess.run([sys.executable, tmp], capture_output=True, text=True, timeout=timeout)
        elapsed = time.perf_counter() - start
        os.unlink(tmp)
        return {"success": result.returncode == 0, "data": {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "elapsed_ms": round(elapsed * 1000, 1)
        }, "error": result.stderr if result.returncode != 0 else None}
    except subprocess.TimeoutExpired:
        return {"success": False, "data": None, "error": "Execution timed out after " + str(timeout) + "s"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def run_powershell_snippet(code: str, timeout: float = 15.0) -> Dict[str, Any]:
    try:
        with tempfile.NamedTemporaryFile(suffix=".ps1", mode="w", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp = f.name
        start = time.perf_counter()
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", tmp],
            capture_output=True, text=True, timeout=timeout
        )
        elapsed = time.perf_counter() - start
        os.unlink(tmp)
        return {"success": result.returncode == 0, "data": {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "elapsed_ms": round(elapsed * 1000, 1)
        }, "error": result.stderr if result.returncode != 0 else None}
    except subprocess.TimeoutExpired:
        return {"success": False, "data": None, "error": "Timeout"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def run_cmd_snippet(code: str, timeout: float = 10.0) -> Dict[str, Any]:
    try:
        with tempfile.NamedTemporaryFile(suffix=".bat", mode="w", delete=False, encoding="cp1252") as f:
            f.write("@echo off\n" + code)
            tmp = f.name
        start = time.perf_counter()
        result = subprocess.run([tmp], capture_output=True, text=True, timeout=timeout, shell=True)
        elapsed = time.perf_counter() - start
        os.unlink(tmp)
        return {"success": result.returncode == 0, "data": {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "elapsed_ms": round(elapsed * 1000, 1)
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def run_node_snippet(code: str, timeout: float = 10.0) -> Dict[str, Any]:
    try:
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp = f.name
        start = time.perf_counter()
        result = subprocess.run(["node", tmp], capture_output=True, text=True, timeout=timeout)
        elapsed = time.perf_counter() - start
        os.unlink(tmp)
        return {"success": result.returncode == 0, "data": {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "elapsed_ms": round(elapsed * 1000, 1)
        }, "error": result.stderr if result.returncode != 0 else None}
    except FileNotFoundError:
        return {"success": False, "data": None, "error": "node.js not found"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def run_python_file(file_path: str, args: list = [], timeout: float = 30.0) -> Dict[str, Any]:
    try:
        import sys
        cmd = [sys.executable, file_path] + [str(a) for a in args]
        start = time.perf_counter()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        elapsed = time.perf_counter() - start
        return {"success": result.returncode == 0, "data": {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "elapsed_ms": round(elapsed * 1000, 1)
        }, "error": result.stderr if result.returncode != 0 else None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def measure_python_execution(code: str, runs: int = 3) -> Dict[str, Any]:
    """Measure average execution time of a Python code snippet."""
    try:
        import sys
        times = []
        for _ in range(runs):
            with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
                f.write(code)
                tmp = f.name
            start = time.perf_counter()
            subprocess.run([sys.executable, tmp], capture_output=True, timeout=15)
            times.append(time.perf_counter() - start)
            os.unlink(tmp)
        return {"success": True, "data": {
            "runs": runs,
            "avg_ms": round(sum(times) / len(times) * 1000, 2),
            "min_ms": round(min(times) * 1000, 2),
            "max_ms": round(max(times) * 1000, 2)
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def eval_python_expression(expression: str) -> Dict[str, Any]:
    """Safely evaluate a Python expression and return the result."""
    try:
        import ast
        tree = ast.parse(expression, mode="eval")
        allowed_nodes = {ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp,
                         ast.Compare, ast.Call, ast.Num, ast.Str, ast.Constant,
                         ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
                         ast.FloorDiv, ast.And, ast.Or, ast.Not, ast.Eq, ast.NotEq,
                         ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.List, ast.Tuple,
                         ast.Dict, ast.Set, ast.IfExp, ast.USub, ast.UAdd}
        for node in ast.walk(tree):
            if type(node) not in allowed_nodes:
                if isinstance(node, ast.Name):
                    if node.id not in {"True", "False", "None", "abs", "round", "len",
                                       "min", "max", "sum", "sorted", "range", "int", "float", "str"}:
                        return {"success": False, "data": None, "error": "Unsafe expression: " + node.id}
        result = eval(compile(tree, "<string>", "eval"), {"__builtins__": {}},
                      {"abs": abs, "round": round, "len": len, "min": min, "max": max,
                       "sum": sum, "sorted": sorted, "range": range, "int": int, "float": float, "str": str})
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_runtime_available(runtime: str) -> Dict[str, Any]:
    """Check if a runtime is available: python, node, powershell, java, etc."""
    try:
        version_flags = {"python": "--version", "node": "--version", "java": "-version",
                         "ruby": "--version", "go": "version", "dotnet": "--version"}
        flag = version_flags.get(runtime.lower(), "--version")
        result = subprocess.run([runtime, flag], capture_output=True, text=True, timeout=5)
        available = result.returncode == 0
        version = (result.stdout or result.stderr).strip().split("\n")[0]
        return {"success": True, "data": {"runtime": runtime, "available": available, "version": version}, "error": None}
    except FileNotFoundError:
        return {"success": True, "data": {"runtime": runtime, "available": False, "version": None}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def run_shell_command(command: str, timeout: float = 15.0) -> Dict[str, Any]:
    """Run a shell command and capture output."""
    try:
        start = time.perf_counter()
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        elapsed = time.perf_counter() - start
        return {"success": result.returncode == 0, "data": {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "elapsed_ms": round(elapsed * 1000, 1)
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_python_version() -> Dict[str, Any]:
    try:
        import sys
        return {"success": True, "data": {"version": sys.version, "major": sys.version_info.major, "minor": sys.version_info.minor}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
