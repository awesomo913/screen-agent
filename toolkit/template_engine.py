import jinja2
from jinja2 import Environment, BaseLoader, FileSystemLoader, DictLoader, select_autoescape, TemplateSyntaxError, UndefinedError, TemplateNotFound, meta
import string
import re
import json
from pathlib import Path
import os
import html
import copy
from datetime import datetime
from collections import defaultdict, OrderedDict
from typing import Dict, Any, List, Callable, Optional
import difflib

# Module-Level State
_global_env: Optional[Environment] = None
_template_cache: Dict[str, str] = {}
_execution_metrics: Dict[str, int] = defaultdict(int)


def _get_env() -> Environment:
    """Retrieve or initialize the default Jinja2 environment."""
    global _global_env
    if _global_env is None:
        _global_env = Environment(
            loader=BaseLoader(),
            undefined=jinja2.StrictUndefined,
            autoescape=False
        )
        _global_env.globals['datetime'] = datetime
        _global_env.globals['version'] = 1.0
    return _global_env


def _prepare_response(result: Any, success: bool = True, message: str = "Operation completed successfully") -> Dict[str, Any]:
    """Standardized response dictionary constructor."""
    _execution_metrics["successes" if success else "failures"] += 1
    return OrderedDict([
        ("success", success),
        ("result", result),
        ("error", None if success else message),
        ("timestamp", datetime.now().isoformat())
    ])


def _error_response(exc: Exception, context: str = "Unknown error") -> Dict[str, Any]:
    """Standardized error response constructor."""
    return _prepare_response(
        result=None,
        success=False,
        message=f"{context}: {str(exc)}"
    )


def render_template(template_str: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    try:
        safe_vars = copy.deepcopy(variables)
        env = _get_env()
        template = env.from_string(template_str)
        rendered = template.render(**safe_vars)
        return _prepare_response(rendered)
    except Exception as e:
        return _error_response(e, "Template render failed")


def render_template_file(filepath: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    try:
        path = Path(filepath).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Template file not found: {filepath}")
        template_str = path.read_text(encoding="utf-8")
        return render_template(template_str, variables)
    except Exception as e:
        return _error_response(e, "File template render failed")


def create_template(name: str, content: str, output: str) -> Dict[str, Any]:
    try:
        # Validate name using string module
        valid_chars = set(string.ascii_letters + string.digits + "_-.")
        if not all(c in valid_chars for c in name):
            raise ValueError("Template name contains invalid characters. Only alphanumeric, _, -, and . are allowed.")
        
        out_dir = Path(output)
        out_dir.mkdir(parents=True, exist_ok=True)
        target_path = out_dir / f"{name}.j2"
        target_path.write_text(content, encoding="utf-8")
        return _prepare_response({"filepath": str(target_path), "status": "created"})
    except Exception as e:
        return _error_response(e, "Template creation failed")


def load_template(filepath: str) -> Dict[str, Any]:
    try:
        content = Path(filepath).read_text(encoding="utf-8")
        return _prepare_response({"content": content, "filepath": str(filepath)})
    except Exception as e:
        return _error_response(e, "Template load failed")


def validate_template(template_str: str) -> Dict[str, Any]:
    try:
        env = _get_env()
        env.parse(template_str)
        return _prepare_response({"valid": True, "message": "Template syntax is valid"})
    except TemplateSyntaxError as e:
        return _prepare_response({
            "valid": False,
            "error": str(e),
            "line": e.lineno,
            "message": "Template contains syntax errors"
        })
    except Exception as e:
        return _error_response(e, "Template validation failed")


def list_template_variables(template_str: str) -> Dict[str, Any]:
    try:
        env = _get_env()
        ast = env.parse(template_str)
        undeclared = meta.find_undeclared_variables(ast)
        return _prepare_response({"variables": sorted(list(undeclared)), "count": len(undeclared)})
    except Exception as e:
        return _error_response(e, "Variable extraction failed")


def render_html_template(template_str: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    try:
        safe_vars = copy.deepcopy(variables)
        # Escape raw string variables to prevent XSS if they aren't marked safe
        for k, v in safe_vars.items():
            if isinstance(v, str) and not hasattr(v, '__html__'):
                safe_vars[k] = html.escape(v, quote=True)
        
        env = Environment(loader=BaseLoader(), autoescape=select_autoescape(['html', 'xml']))
        rendered = env.from_string(template_str).render(**safe_vars)
        return _prepare_response(rendered)
    except Exception as e:
        return _error_response(e, "HTML template render failed")


def render_email_template(template_str: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    try:
        safe_vars = copy.deepcopy(variables)
        env = Environment(loader=BaseLoader(), autoescape=True)
        env.globals['now'] = datetime.now
        rendered = env.from_string(template_str).render(**safe_vars)
        # Basic sanitization for email safety (strip scripts)
        rendered = re.sub(r'<script.*?>.*?</script>', '', rendered, flags=re.IGNORECASE | re.DOTALL)
        return _prepare_response(rendered)
    except Exception as e:
        return _error_response(e, "Email template render failed")


def render_code_template(template_str: str, variables: Dict[str, Any], language: str) -> Dict[str, Any]:
    try:
        safe_vars = copy.deepcopy(variables)
        # Code templates should disable autoescape to preserve indentation/syntax
        env = Environment(loader=BaseLoader(), autoescape=False, undefined=jinja2.StrictUndefined)
        rendered = env.from_string(template_str).render(**safe_vars)
        lines = len(rendered.splitlines())
        return _prepare_response({
            "code": rendered,
            "language": language,
            "line_count": lines,
            "byte_size": len(rendered.encode('utf-8'))
        })
    except Exception as e:
        return _error_response(e, "Code template render failed")


def batch_render(template_str: str, data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        env = _get_env()
        template = env.from_string(template_str)
        results = []
        for idx, data in enumerate(data_list):
            safe_data = copy.deepcopy(data)
            rendered = template.render(**safe_data)
            results.append({"index": idx, "output": rendered})
        return _prepare_response({"results": results, "rendered_count": len(results)})
    except Exception as e:
        return _error_response(e, "Batch render failed")


def register_filter(name: str, func: Callable[..., Any]) -> Dict[str, Any]:
    try:
        env = _get_env()
        env.filters[name] = func
        return _prepare_response({"registered": True, "filter": name})
    except Exception as e:
        return _error_response(e, "Filter registration failed")


def register_global(name: str, value: Any) -> Dict[str, Any]:
    try:
        env = _get_env()
        env.globals[name] = value
        return _prepare_response({"registered": True, "global": name})
    except Exception as e:
        return _error_response(e, "Global registration failed")


def create_template_env(template_dir: str, extensions: Optional[List[str]] = None) -> Dict[str, Any]:
    global _global_env
    try:
        path = Path(template_dir).resolve()
        if not path.is_dir():
            raise ValueError(f"Template directory does not exist: {template_dir}")
        ext = extensions or []
        _global_env = Environment(
            loader=FileSystemLoader(str(path)),
            extensions=ext,
            autoescape=False
        )
        return _prepare_response({
            "created": True,
            "loader_path": str(path),
            "extensions": ext
        })
    except Exception as e:
        return _error_response(e, "Environment creation failed")


def render_with_includes(template_str: str, variables: Dict[str, Any], include_dir: str) -> Dict[str, Any]:
    try:
        include_path = Path(include_dir).resolve()
        if not include_path.is_dir():
            raise FileNotFoundError(f"Include directory not found: {include_dir}")
        
        # Chain loaders: current dir then include dir
        loader = FileSystemLoader([os.curdir, str(include_path)])
        env = Environment(loader=loader, autoescape=False)
        template = env.from_string(template_str)
        rendered = template.render(**copy.deepcopy(variables))
        return _prepare_response(rendered)
    except Exception as e:
        return _error_response(e, "Include render failed")


def render_with_inheritance(child_template: str, variables: Dict[str, Any], parent_dir: str) -> Dict[str, Any]:
    try:
        parent_path = Path(parent_dir).resolve()
        if not parent_path.is_dir():
            raise FileNotFoundError(f"Parent template directory not found: {parent_dir}")
        
        # Use DictLoader for the child string, FileSystemLoader for parents
        composite_loader = jinja2.ChoiceLoader([
            DictLoader({"_child_": child_template}),
            FileSystemLoader(str(parent_path))
        ])
        env = Environment(loader=composite_loader, autoescape=False)
        template = env.get_template("_child_")
        rendered = template.render(**copy.deepcopy(variables))
        return _prepare_response(rendered)
    except Exception as e:
        return _error_response(e, "Inheritance render failed")


def conditional_render(template_str: str, variables: Dict[str, Any], conditions: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # Merge conditions into context for {% if %} evaluations
        runtime_ctx = {**copy.deepcopy(variables), **copy.deepcopy(conditions)}
        env = _get_env()
        rendered = env.from_string(template_str).render(**runtime_ctx)
        applied_conditions = {k: v for k, v in conditions.items() if v is True}
        return _prepare_response(rendered, message=f"Conditional render completed. Applied: {list(applied_conditions.keys())}")
    except Exception as e:
        return _error_response(e, "Conditional render failed")


def loop_render(template_str: str, items: List[Any], item_var: str) -> Dict[str, Any]:
    try:
        if not isinstance(items, (list, tuple)):
            raise TypeError("items must be a list or tuple")
        # Wrap template in a for-loop structure
        loop_wrapper = f"{{% for {item_var} in __loop_items__ %}}{template_str}{{% endfor %}}"
        env = _get_env()
        rendered = env.from_string(loop_wrapper).render(__loop_items__=items)
        return _prepare_response({"output": rendered, "iterations": len(items)})
    except Exception as e:
        return _error_response(e, "Loop render failed")


def safe_render(template_str: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    try:
        # Custom undefined that returns empty strings safely
        class SafeUndefined(jinja2.Undefined):
            def __str__(self) -> str: return ""
            def __call__(self, *args: Any, **kwargs: Any) -> str: return ""
            def __getattr__(self, name: str) -> "SafeUndefined": return self

        safe_vars = copy.deepcopy(variables)
        env = Environment(loader=BaseLoader(), undefined=SafeUndefined, autoescape=False)
        rendered = env.from_string(template_str).render(**safe_vars)
        return _prepare_response(rendered)
    except Exception as e:
        return _error_response(e, "Safe render failed")


def minify_rendered(template_str: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    try:
        env = _get_env()
        rendered = env.from_string(template_str).render(**copy.deepcopy(variables))
        # Remove HTML/XML comments
        minified = re.sub(r'<!--.*?-->', '', rendered, flags=re.DOTALL)
        # Collapse whitespace (newlines, tabs, spaces)
        minified = re.sub(r'\s+', ' ', minified)
        # Strip trailing/leading
        minified = minified.strip()
        return _prepare_response({"minified": minified, "original_size": len(rendered), "compressed_size": len(minified)})
    except Exception as e:
        return _error_response(e, "Minification failed")


def cache_template(template_str: str, key: str) -> Dict[str, Any]:
    try:
        _template_cache[key] = template_str
        _execution_metrics["cache_writes"] += 1
        return _prepare_response({"cached": True, "key": key})
    except Exception as e:
        return _error_response(e, "Cache storage failed")


def get_cached_template(key: str) -> Dict[str, Any]:
    try:
        _execution_metrics["cache_reads"] += 1
        if key in _template_cache:
            return _prepare_response({"template": _template_cache[key], "status": "hit"})
        return _prepare_response({"template": None, "status": "miss"})
    except Exception as e:
        return _error_response(e, "Cache retrieval failed")


def clear_template_cache() -> Dict[str, Any]:
    try:
        count = len(_template_cache)
        _template_cache.clear()
        return _prepare_response({"cleared": True, "items_removed": count})
    except Exception as e:
        return _error_response(e, "Cache clear failed")


def export_rendered(template_str: str, variables: Dict[str, Any], output: str) -> Dict[str, Any]:
    try:
        render_res = render_template(template_str, variables)
        if not render_res["success"]:
            return render_res
        content = str(render_res["result"])
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        return _prepare_response({"exported": True, "path": str(out_path), "bytes_written": os.path.getsize(out_path)})
    except Exception as e:
        return _error_response(e, "Export failed")


def diff_rendered(template_str: str, vars1: Dict[str, Any], vars2: Dict[str, Any]) -> Dict[str, Any]:
    try:
        env = _get_env()
        res1 = env.from_string(template_str).render(**copy.deepcopy(vars1))
        res2 = env.from_string(template_str).render(**copy.deepcopy(vars2))
        
        diff_lines = list(difflib.unified_diff(
            res1.splitlines(keepends=True),
            res2.splitlines(keepends=True),
            fromfile='version_1',
            tofile='version_2',
            lineterm=''
        ))
        return _prepare_response({
            "result_1": res1,
            "result_2": res2,
            "diff_output": "".join(diff_lines),
            "identical": res1 == res2
        })
    except Exception as e:
        return _error_response(e, "Diff render failed")


def create_template_library(templates: Dict[str, str], output: str) -> Dict[str, Any]:
    try:
        out_dir = Path(output)
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest = []
        
        for name, content in templates.items():
            # Sanitize filenames for cross-platform safety
            safe_name = re.sub(r'[^\w\-.]', '_', name)
            target = out_dir / f"{safe_name}.jinja2"
            target.write_text(content, encoding="utf-8")
            manifest.append({"name": name, "path": str(target), "size": target.stat().st_size})
            
        return _prepare_response({
            "library_created": True,
            "path": str(out_dir),
            "count": len(manifest),
            "files": manifest
        })
    except Exception as e:
        return _error_response(e, "Library creation failed")