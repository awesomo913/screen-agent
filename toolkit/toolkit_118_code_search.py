"""toolkit_118_code_search.py
Search code bases — grep patterns, find symbols, search by content across files.
"""
import subprocess, os, sys, json, re
from pathlib import Path

def check_available() -> dict:
    """Check if dependencies for code_search are available."""
    import importlib
    libs = {"docker": "docker", "openapi": "openapi_spec_validator", "graphql": "gql", "websocket": "websocket", "database": "sqlite3", "file_watcher_api": "watchdog", "celery": "celery", "redis": "redis", "aws": "boto3", "performance": "py_spy", "code_search": None}
    lib = libs.get("code_search")
    if lib is None:
        return {"success": True, "data": {"available": True, "note": "stdlib only"}, "error": None}
    try:
        importlib.import_module(lib)
        return {"success": True, "data": {"available": True, "library": lib}, "error": None}
    except ImportError:
        return {"success": True, "data": {"available": False, "install": "pip install " + lib}, "error": None}

def search_in_files(directory: str, pattern: str, file_pattern: str = "*.py", ignore_case: bool = False) -> dict:
    """Search for a regex/text pattern across files."""
    try:
        flags = re.IGNORECASE if ignore_case else 0
        results = []
        for path in Path(directory).rglob(file_pattern):
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        if re.search(pattern, line, flags):
                            results.append({"file": str(path.relative_to(directory)), "line": i, "text": line.rstrip()})
            except: pass
        return {"success": True, "data": {"matches": results[:100], "count": len(results)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_function_definition(directory: str, func_name: str) -> dict:
    """Find where a function is defined in a codebase."""
    return search_in_files(directory, r"def " + re.escape(func_name) + r"\s*\(", "*.py")

def find_class_definition(directory: str, class_name: str) -> dict:
    """Find where a class is defined."""
    return search_in_files(directory, r"class " + re.escape(class_name) + r"[:(]", "*.py")

def find_imports_of(directory: str, module_name: str) -> dict:
    """Find all files that import a module."""
    pattern = r"^(?:import |from )" + re.escape(module_name)
    return search_in_files(directory, pattern, "*.py")

def count_occurrences(directory: str, text: str, file_pattern: str = "*.py") -> dict:
    """Count occurrences of text across files."""
    try:
        total = 0
        file_counts = {}
        for path in Path(directory).rglob(file_pattern):
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                count = content.count(text)
                if count > 0:
                    file_counts[str(path.relative_to(directory))] = count
                    total += count
            except: pass
        return {"success": True, "data": {"total": total, "by_file": file_counts}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_large_functions(directory: str, threshold: int = 50) -> dict:
    """Find functions longer than threshold lines."""
    try:
        import ast
        results = []
        for path in Path(directory).rglob("*.py"):
            try:
                code = path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        end = getattr(node, "end_lineno", node.lineno + 10)
                        length = end - node.lineno
                        if length > threshold:
                            results.append({"file": str(path.relative_to(directory)), "function": node.name, "line": node.lineno, "length": length})
            except: pass
        return {"success": True, "data": {"large_functions": results, "count": len(results)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def grep_files(directory: str, pattern: str, file_extensions: list = [".py",".js",".ts",".go",".rs",".c",".cpp"]) -> dict:
    """Grep text pattern across multiple file types."""
    try:
        results = []
        for path in Path(directory).rglob("*"):
            if path.suffix in file_extensions and path.is_file():
                try:
                    with open(path, encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if re.search(pattern, line, re.IGNORECASE):
                                results.append({"file": str(path.relative_to(directory)), "line": i, "text": line.rstrip()[:200]})
                except: pass
        return {"success": True, "data": {"matches": results[:200], "count": len(results)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def find_dead_imports(file_path: str) -> dict:
    """Find imported names that are never used in a Python file."""
    try:
        import ast
        with open(file_path, encoding="utf-8") as f:
            code = f.read()
        tree = ast.parse(code)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.append(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported.append(alias.asname or alias.name)
        unused = [name for name in imported if name != "*" and len(re.findall(r"\b" + re.escape(name) + r"\b", code)) <= 1]
        return {"success": True, "data": {"unused_imports": unused, "count": len(unused)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}