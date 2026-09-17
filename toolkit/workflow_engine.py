import json
from pathlib import Path
import threading
import time
import logging
import functools
import inspect
import traceback
import uuid
import copy
import queue
from typing import Any, Dict, Callable, List, Optional, Union

# Configure module logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ====================================================================================
# Global State & Thread Safety
# ====================================================================================
_registry_lock = threading.Lock()
_workflows: Dict[str, Dict[str, Any]] = {}
_history: Dict[str, List[Dict[str, Any]]] = {}
_pause_events: Dict[str, threading.Event] = {}
_cancel_events: Dict[str, threading.Event] = {}
_step_results: Dict[str, Dict[str, Any]] = {}
_event_queue: queue.Queue = queue.Queue()

def _drain_event_queue():
    """Internal helper to process queued log events synchronously."""
    try:
        while not _event_queue.empty():
            _event_queue.get_nowait()
    except queue.Empty:
        pass

def _safe_call(func: Callable, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Safely invoke a callable with error context capturing."""
    try:
        if inspect.iscoroutinefunction(func):
            raise ValueError("Async functions not supported in synchronous engine. Use wrapper.")
        sig = inspect.signature(func)
        bound = sig.bind_partial(**kwargs)
        bound.apply_defaults()
        result = func(*bound.args, **bound.kwargs)
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Function call failed: {e}\n{tb}")
        return {"success": False, "data": None, "error": f"{type(e).__name__}: {str(e)}"}

def _resolve_value(val: Any, context: Dict[str, Any]) -> Any:
    """Evaluate callables or return static values using context."""
    if callable(val):
        return _safe_call(val, context).get("data")
    if isinstance(val, str) and val in context:
        return context[val]
    return val

# ====================================================================================
# Core Workflow Functions
# ====================================================================================
def create_workflow(name: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Initialize and register a new workflow."""
    try:
        wf_id = str(uuid.uuid4())
        wf = {
            "id": wf_id,
            "name": name,
            "steps": copy.deepcopy(steps),
            "status": "created",
            "metadata": {"created_at": time.time()}
        }
        with _registry_lock:
            _workflows[wf_id] = wf
            _pause_events[wf_id] = threading.Event()
            _pause_events[wf_id].set()  # Unpaused initially
            _cancel_events[wf_id] = threading.Event()
            _history[wf_id] = []
            _step_results[wf_id] = {}
        log_workflow_event(wf_id, "Workflow created")
        return {"success": True, "data": wf, "error": None}
    except Exception as e:
        logger.error(f"create_workflow failed: {traceback.format_exc()}")
        return {"success": False, "data": None, "error": str(e)}

def execute_workflow(workflow: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute workflow steps sequentially with pause/cancel checks."""
    wf_id = workflow.get("id")
    if not wf_id or wf_id not in _workflows:
        return {"success": False, "data": None, "error": "Workflow not registered"}
    
    try:
        with _registry_lock:
            _workflows[wf_id]["status"] = "running"
        
        log_workflow_event(wf_id, "Execution started")
        
        for i, step in enumerate(workflow["steps"]):
            # Cancel check
            if _cancel_events[wf_id].is_set():
                with _registry_lock:
                    _workflows[wf_id]["status"] = "cancelled"
                log_workflow_event(wf_id, "Execution cancelled by user")
                return {"success": False, "data": {"status": "cancelled", "last_step": step.get("name")}, "error": "Workflow cancelled"}
            
            # Pause check (blocks until resumed)
            if not _pause_events[wf_id].is_set():
                with _registry_lock:
                    _workflows[wf_id]["status"] = "paused"
            _pause_events[wf_id].wait()
            with _registry_lock:
                if _workflows[wf_id]["status"] == "paused":
                    _workflows[wf_id]["status"] = "running"

            # Skip check
            if step.get("_skipped", False):
                log_workflow_event(wf_id, f"Skipped step: {step.get('name')}")
                continue

            step_res = execute_step(step, context)
            _step_results[wf_id][step.get("name", f"step_{i}")] = step_res
            
            if not step_res["success"]:
                with _registry_lock:
                    _workflows[wf_id]["status"] = "failed"
                log_workflow_event(wf_id, f"Failed at step: {step.get('name')}")
                return {"success": False, "data": _step_results[wf_id], "error": step_res.get("error")}
            
            # Update context with step output for chaining
            if step_res["data"] is not None:
                context = {**context, f"{step.get('name')}_output": step_res["data"]}
                
        with _registry_lock:
            _workflows[wf_id]["status"] = "completed"
        log_workflow_event(wf_id, "Execution completed")
        return {"success": True, "data": _step_results[wf_id].copy(), "error": None}
    except Exception as e:
        logger.error(f"execute_workflow failed: {traceback.format_exc()}")
        with _registry_lock:
            _workflows[wf_id]["status"] = "error"
        return {"success": False, "data": None, "error": str(e)}

def add_step(workflow: Dict[str, Any], step_name: str, func: Callable[..., Any], args: Optional[Dict] = None) -> Dict[str, Any]:
    """Append a step to the workflow definition."""
    try:
        if "steps" not in workflow:
            return {"success": False, "data": None, "error": "Invalid workflow structure"}
        new_step = {"name": step_name, "type": "standard", "func": func, "args": args or {}, "_skipped": False}
        with _registry_lock:
            workflow["steps"].append(new_step)
            # Sync with registry if registered
            if wf_id := workflow.get("id"):
                if wf_id in _workflows:
                    _workflows[wf_id]["steps"] = copy.deepcopy(workflow["steps"])
        log_workflow_event(workflow.get("id", "unnamed"), f"Added step: {step_name}")
        return {"success": True, "data": workflow, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def remove_step(workflow: Dict[str, Any], step_name: str) -> Dict[str, Any]:
    """Remove a step by name from the workflow."""
    try:
        steps = workflow.get("steps", [])
        filtered = [s for s in steps if s.get("name") != step_name]
        if len(filtered) == len(steps):
            return {"success": False, "data": workflow, "error": f"Step '{step_name}' not found"}
        workflow["steps"] = filtered
        if wf_id := workflow.get("id"):
            with _registry_lock:
                if wf_id in _workflows:
                    _workflows[wf_id]["steps"] = copy.deepcopy(filtered)
        return {"success": True, "data": workflow, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def reorder_steps(workflow: Dict[str, Any], new_order: List[str]) -> Dict[str, Any]:
    """Reorder workflow steps according to a list of step names."""
    try:
        steps = {s["name"]: s for s in workflow.get("steps", [])}
        reordered = []
        for name in new_order:
            if name not in steps:
                return {"success": False, "data": None, "error": f"Step '{name}' missing in workflow"}
            reordered.append(steps[name])
        workflow["steps"] = reordered
        if wf_id := workflow.get("id"):
            with _registry_lock:
                if wf_id in _workflows:
                    _workflows[wf_id]["steps"] = copy.deepcopy(reordered)
        return {"success": True, "data": workflow, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def skip_step(workflow: Dict[str, Any], step_name: str) -> Dict[str, Any]:
    """Mark a step as skipped for execution."""
    try:
        found = False
        for step in workflow.get("steps", []):
            if step.get("name") == step_name:
                step["_skipped"] = True
                found = True
        if not found:
            return {"success": False, "data": None, "error": "Step not found"}
        return {"success": True, "data": workflow, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

# ====================================================================================
# Step Construction Factories
# ====================================================================================
def create_conditional_step(condition: Callable[[Dict], bool], true_step: Dict[str, Any], false_step: Dict[str, Any]) -> Dict[str, Any]:
    """Factory for conditional branching steps."""
    return {"name": "conditional", "type": "conditional", "condition": condition, "true_step": true_step, "false_step": false_step}

def create_loop_step(iterable: Union[List, Callable], body_step: Dict[str, Any]) -> Dict[str, Any]:
    """Factory for iterative looping steps."""
    return {"name": "loop", "type": "loop", "iterable": iterable, "body_step": body_step}

def create_parallel_steps(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Factory for concurrent execution block."""
    return {"name": "parallel", "type": "parallel", "steps": copy.deepcopy(steps)}

def create_error_handler(step: Dict[str, Any], handler: Callable[[Dict, Exception], Any]) -> Dict[str, Any]:
    """Wrap a step with error recovery logic."""
    return {"name": f"{step.get('name', 'step')}_handler", "type": "error_handler", "target": step, "handler": handler}

# ====================================================================================
# Execution Primitives
# ====================================================================================
def execute_step(step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch and execute a single step based on its type."""
    try:
        step_type = step.get("type", "standard")
        
        if step_type == "conditional":
            cond = step["condition"]
            cond_res = _safe_call(cond, context)
            target = step["true_step"] if cond_res.get("success") and cond_res["data"] else step["false_step"]
            return execute_step(target, context)
            
        elif step_type == "loop":
            iter_val = _resolve_value(step.get("iterable"), context)
            if not isinstance(iter_val, (list, tuple)):
                raise ValueError("Loop iterable must resolve to a list/tuple")
            results = []
            for item in iter_val:
                loop_ctx = {**context, "_loop_item": item, "_loop_index": len(results)}
                res = execute_step(step["body_step"], loop_ctx)
                if not res["success"]: return res
                results.append(res["data"])
            return {"success": True, "data": results, "error": None}
            
        elif step_type == "parallel":
            threads = []
            q_res = queue.Queue()
            steps = step.get("steps", [])
            def _worker(idx, s):
                try: q_res.put((idx, execute_step(s, context)))
                except Exception as e: q_res.put((idx, {"success": False, "error": str(e)}))
            for i, s in enumerate(steps): threading.Thread(target=_worker, args=(i, s)).start()
            collected = []
            while len(collected) < len(steps):
                collected.append(q_res.get(timeout=300))
            collected.sort(key=lambda x: x[0])
            final_data = [r["data"] for _, r in collected]
            failures = [r["error"] for _, r in collected if not r["success"]]
            if failures: return {"success": False, "data": None, "error": f"Parallel failures: {'; '.join(failures)}"}
            return {"success": True, "data": final_data, "error": None}
            
        elif step_type == "error_handler":
            target_res = execute_step(step["target"], context)
            if target_res["success"]: return target_res
            handler_res = _safe_call(step["handler"], {**context, "_error": target_res.get("error")})
            return handler_res
            
        else: # standard
            func = step.get("func")
            args = step.get("args", {}) or {}
            # Inject context into missing signature parameters
            if callable(func):
                try:
                    sig = set(inspect.signature(func).parameters.keys())
                    for k, v in context.items():
                        if k in sig and k not in args: args[k] = v
                except Exception: pass
            return _safe_call(func, args)
            
    except Exception as e:
        return {"success": False, "data": None, "error": f"Step execution error: {str(e)}"}

def retry_step(step: Dict[str, Any], context: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
    """Wrap step execution with retry logic."""
    last_error = None
    for attempt in range(max_retries + 1):
        res = execute_step(step, context)
        if res["success"]: return res
        last_error = res.get("error", "Unknown retriable error")
        log_workflow_event("retry", f"Attempt {attempt+1}/{max_retries+1} failed: {last_error}")
        time.sleep(min(2 ** attempt, 5))  # Exponential backoff
    return {"success": False, "data": None, "error": f"Failed after {max_retries+1} attempts: {last_error}"}

# ====================================================================================
# Control & State Management
# ====================================================================================
def pause_workflow(workflow_id: str) -> Dict[str, Any]:
    """Signal a running workflow to pause at the next safe point."""
    if workflow_id not in _pause_events:
        return {"success": False, "data": None, "error": "Workflow not active"}
    _pause_events[workflow_id].clear()
    log_workflow_event(workflow_id, "Pause requested")
    return {"success": True, "data": {"status": "pausing"}, "error": None}

def resume_workflow(workflow_id: str) -> Dict[str, Any]:
    """Resume a paused workflow."""
    if workflow_id not in _pause_events:
        return {"success": False, "data": None, "error": "Workflow not active"}
    _pause_events[workflow_id].set()
    log_workflow_event(workflow_id, "Resumed")
    return {"success": True, "data": {"status": "running"}, "error": None}

def cancel_workflow(workflow_id: str) -> Dict[str, Any]:
    """Terminate a running workflow immediately."""
    if workflow_id not in _cancel_events:
        return {"success": False, "data": None, "error": "Workflow not active"}
    _cancel_events[workflow_id].set()
    _pause_events[workflow_id].set()  # Unblock if paused
    log_workflow_event(workflow_id, "Cancelled")
    return {"success": True, "data": {"status": "cancelling"}, "error": None}

def get_workflow_status(workflow_id: str) -> Dict[str, Any]:
    """Retrieve current execution status."""
    with _registry_lock:
        wf = _workflows.get(workflow_id)
    if not wf:
        return {"success": False, "data": None, "error": "Workflow not found"}
    return {"success": True, "data": {"id": workflow_id, "status": wf.get("status")}, "error": None}

def get_step_result(workflow_id: str, step_name: str) -> Dict[str, Any]:
    """Fetch stored result of a completed step."""
    return {"success": True, "data": _step_results.get(workflow_id, {}).get(step_name), "error": None}

def validate_workflow(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """Check workflow structure and integrity."""
    errors = []
    if not isinstance(workflow, dict):
        return {"success": False, "data": None, "error": "Workflow must be a dict"}
    if "steps" not in workflow or not isinstance(workflow["steps"], list):
        errors.append("Missing or invalid 'steps' list")
    seen = set()
    for s in workflow.get("steps", []):
        if not isinstance(s, dict):
            errors.append("Step must be a dict")
            continue
        if "name" in s and s["name"] in seen:
            errors.append(f"Duplicate step name: {s['name']}")
        seen.add(s.get("name"))
    if errors:
        return {"success": False, "data": {"errors": errors}, "error": "Validation failed"}
    return {"success": True, "data": {"valid": True}, "error": None}

# ====================================================================================
# Persistence & Templates
# ====================================================================================
def _workflow_serializer(obj: Any) -> Any:
    """Custom JSON serializer handling non-serializable objects."""
    if callable(obj):
        return f"<callable:{obj.__module__}.{obj.__qualname__}>"
    if isinstance(obj, set): return list(obj)
    if isinstance(obj, (Path,)): return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def save_workflow(workflow: Dict[str, Any], filepath: Union[str, Path]) -> Dict[str, Any]:
    """Serialize workflow definition to disk."""
    try:
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(workflow, f, indent=2, default=_workflow_serializer)
        return {"success": True, "data": str(p), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def load_workflow(filepath: Union[str, Path]) -> Dict[str, Any]:
    """Deserialize workflow definition from disk."""
    try:
        p = Path(filepath)
        if not p.exists():
            return {"success": False, "data": None, "error": "File not found"}
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Restore IDs and reset execution state
        data["status"] = "loaded"
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def create_workflow_template(name: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a reusable workflow template with placeholders."""
    return {"template_id": str(uuid.uuid4()), "name": name, "type": "template", "steps": copy.deepcopy(steps)}

def instantiate_template(template: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a concrete workflow from a template by resolving placeholders."""
    if template.get("type") != "template":
        return {"success": False, "data": None, "error": "Not a template"}
    try:
        wf_id = str(uuid.uuid4())
        # Deep copy and resolve params in step args/names
        inst_steps = copy.deepcopy(template["steps"])
        for step in inst_steps:
            if "args" in step and step["args"]:
                step["args"] = {k: v if v not in params else params[v] for k, v in step["args"].items()}
        wf = {"id": wf_id, "name": template["name"], "steps": inst_steps, "status": "instantiated"}
        with _registry_lock:
            _workflows[wf_id] = wf
        return {"success": True, "data": wf, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def chain_workflows(workflows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Sequentially concatenate multiple workflows into one."""
    try:
        if not workflows:
            return {"success": False, "data": None, "error": "Empty workflow list"}
        chain_id = str(uuid.uuid4())
        all_steps = []
        for w in workflows:
            all_steps.extend(copy.deepcopy(w.get("steps", [])))
        wf = {"id": chain_id, "name": f"Chained_{int(time.time())}", "steps": all_steps, "status": "chained"}
        with _registry_lock:
            _workflows[chain_id] = wf
        return {"success": True, "data": wf, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

# ====================================================================================
# Logging & History
# ====================================================================================
def log_workflow_event(workflow_id: str, event: str) -> Dict[str, Any]:
    """Record a timestamped event to history and async queue."""
    entry = {"timestamp": time.time(), "workflow_id": workflow_id, "event": event}
    with _registry_lock:
        if workflow_id in _history:
            _history[workflow_id].append(entry)
        else:
            _history[workflow_id] = [entry]
    try: _event_queue.put_nowait(entry)
    except queue.Full: pass
    return {"success": True, "data": entry, "error": None}

def get_workflow_history(workflow_id: str) -> Dict[str, Any]:
    """Retrieve execution timeline."""
    _drain_event_queue()
    with _registry_lock:
        hist = copy.deepcopy(_history.get(workflow_id, []))
    return {"success": True, "data": hist, "error": None}