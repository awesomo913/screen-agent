import psutil
import os
import json
import time
import gc
import sys
import threading
import weakref
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Callable, Set

# --- Internal State ---
_MONITOR_THREAD: Optional[threading.Thread] = None
_STOP_EVENT = threading.Event()
_MEMORY_HISTORY: List[Dict[str, Any]] = []
_TRACKED_OBJECTS: Dict[str, weakref.ReferenceType] = {}
_SNAPSHOTS: Dict[str, List[Dict[str, Any]]] = {}
_THRESHOLD_MB: float = 1024.0
_MAX_MEMORY_LIMIT_MB: float = 0.0
_ALERT_CALLBACK: Optional[Callable[[Dict[str, Any]], None]] = None
_LAST_CHECK: Dict[str, float] = {"time": time.time(), "memory": 0.0}

@dataclass
class ObjectSnapshot:
    type: str
    size: int
    count: int

# --- Helper Functions ---
def _bytes_to_mb(b: int) -> float:
    return round(b / (1024 * 1024), 2)

def _deep_getsizeof(obj: Any, seen: Set[int]) -> int:
    """Recursively calculates the true size of an object."""
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)
    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        size += sum(_deep_getsizeof(v, seen) for v in obj.values())
        size += sum(_deep_getsizeof(k, seen) for k in obj.keys())
    elif hasattr(obj, '__dict__'):
        size += _deep_getsizeof(obj.__dict__, seen)
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
        size += sum(_deep_getsizeof(i, seen) for i in obj)
    return size

# --- Core Memory API (25+ Functions) ---

def get_memory_usage() -> Dict[str, Any]:
    return {
        "system": get_system_memory(),
        "process": get_process_memory()
    }

def get_system_memory() -> Dict[str, Any]:
    mem = psutil.virtual_memory()
    return {
        "total_mb": _bytes_to_mb(mem.total),
        "available_mb": _bytes_to_mb(mem.available),
        "used_mb": _bytes_to_mb(mem.used),
        "free_mb": _bytes_to_mb(mem.free),
        "percent": mem.percent
    }

def get_process_memory() -> Dict[str, Any]:
    process = psutil.Process(os.getpid())
    mem = process.memory_info()
    data = {
        "rss_mb": _bytes_to_mb(mem.rss),
        "vms_mb": _bytes_to_mb(mem.vms)
    }
    if hasattr(mem, 'shared'):
        data["shared_mb"] = _bytes_to_mb(mem.shared)
    return data

def set_alert_callback(callback: Callable[[Dict[str, Any]], None]) -> Dict[str, str]:
    global _ALERT_CALLBACK
    _ALERT_CALLBACK = callback
    return {"status": "success", "message": "Callback updated"}

def set_memory_threshold(threshold_mb: float) -> Dict[str, float]:
    global _THRESHOLD_MB
    _THRESHOLD_MB = float(threshold_mb)
    return {"status": "success", "new_threshold_mb": _THRESHOLD_MB}

def limit_memory_usage(max_mb: float) -> Dict[str, float]:
    global _MAX_MEMORY_LIMIT_MB
    _MAX_MEMORY_LIMIT_MB = float(max_mb)
    return {"status": "success", "limit_set_mb": _MAX_MEMORY_LIMIT_MB, "note": "Soft limit enforced via monitor thread"}

def _monitor_loop(interval: float):
    global _LAST_CHECK
    process = psutil.Process(os.getpid())
    while not _STOP_EVENT.is_set():
        rss_mb = _bytes_to_mb(process.memory_info().rss)
        current_time = time.time()
        
        # Update history
        record = {"time": current_time, "rss_mb": rss_mb}
        _MEMORY_HISTORY.append(record)
        if len(_MEMORY_HISTORY) > 1000:
            _MEMORY_HISTORY.pop(0)

        # Rate calculations
        time_diff = current_time - _LAST_CHECK["time"]
        if time_diff > 0:
            rate = (rss_mb - _LAST_CHECK["memory"]) / time_diff
            _LAST_CHECK = {"time": current_time, "memory": rss_mb, "rate": rate}

        # Check thresholds and limits
        if rss_mb >= _THRESHOLD_MB and _ALERT_CALLBACK:
            _ALERT_CALLBACK({"alert": "threshold_exceeded", "current_mb": rss_mb, "threshold": _THRESHOLD_MB})
        
        if _MAX_MEMORY_LIMIT_MB > 0 and rss_mb >= _MAX_MEMORY_LIMIT_MB:
            optimize_memory() # Auto-trigger GC if hitting soft limits
            
        time.sleep(interval)

def monitor_memory(interval: float = 1.0) -> Dict[str, str]:
    global _MONITOR_THREAD
    if _MONITOR_THREAD and _MONITOR_THREAD.is_alive():
        return {"status": "running", "message": "Monitor already active"}
    _STOP_EVENT.clear()
    _MONITOR_THREAD = threading.Thread(target=_monitor_loop, args=(interval,), daemon=True)
    _MONITOR_THREAD.start()
    return {"status": "started", "interval": str(interval)}

def get_memory_history() -> Dict[str, List[Dict[str, Any]]]:
    return {"history": _MEMORY_HISTORY.copy()}

def force_garbage_collect() -> Dict[str, int]:
    collected = gc.collect()
    return {"status": "success", "objects_collected": collected}

def get_gc_stats() -> Dict[str, List[Dict[str, int]]]:
    return {"stats": gc.get_stats()}

def track_object(obj_id: str, obj: Any) -> Dict[str, str]:
    _TRACKED_OBJECTS[obj_id] = weakref.ref(obj)
    return {"status": "success", "tracking": obj_id}

def untrack_object(obj_id: str) -> Dict[str, str]:
    if obj_id in _TRACKED_OBJECTS:
        del _TRACKED_OBJECTS[obj_id]
        return {"status": "success", "removed": obj_id}
    return {"status": "error", "message": "Object ID not found"}

def get_tracked_objects() -> Dict[str, Dict[str, bool]]:
    status = {}
    for obj_id, ref in _TRACKED_OBJECTS.items():
        status[obj_id] = ref() is not None
    return {"tracked_objects": status}

def get_memory_leaks() -> Dict[str, Any]:
    dead_refs = [k for k, v in _TRACKED_OBJECTS.items() if v() is None]
    alive_refs = [k for k, v in _TRACKED_OBJECTS.items() if v() is not None]
    uncollectable = len(gc.garbage)
    return {
        "potential_leaks": alive_refs,
        "freed_objects": dead_refs,
        "uncollectable_garbage_count": uncollectable
    }

def create_memory_snapshot(name: str) -> Dict[str, str]:
    objects = gc.get_objects()
    type_counts = {}
    for obj in objects:
        t_name = type(obj).__name__
        type_counts[t_name] = type_counts.get(t_name, 0) + 1
    
    snapshot = [{"type": k, "count": v} for k, v in type_counts.items()]
    _SNAPSHOTS[name] = snapshot
    return {"status": "success", "snapshot": name, "total_types": str(len(snapshot))}

def compare_snapshots(name1: str, name2: str) -> Dict[str, Any]:
    if name1 not in _SNAPSHOTS or name2 not in _SNAPSHOTS:
        return {"status": "error", "message": "Snapshot name not found"}
    
    dict1 = {x["type"]: x["count"] for x in _SNAPSHOTS[name1]}
    dict2 = {x["type"]: x["count"] for x in _SNAPSHOTS[name2]}
    
    diff = {}
    all_keys = set(dict1.keys()).union(dict2.keys())
    for k in all_keys:
        v1 = dict1.get(k, 0)
        v2 = dict2.get(k, 0)
        if v1 != v2:
            diff[k] = {"before": v1, "after": v2, "delta": v2 - v1}
            
    return {"status": "success", "differences": diff}

def get_top_memory_consumers(limit: int = 10) -> Dict[str, List[Dict[str, Any]]]:
    objects = gc.get_objects()
    # Sampling objects to avoid extreme blocking, limiting size calculation depth
    sizes = []
    for obj in objects[:50000]: # Limit scan to prevent hanging large applications
        try:
            sizes.append({"type": type(obj).__name__, "size": sys.getsizeof(obj), "id": id(obj)})
        except Exception:
            continue
    sizes.sort(key=lambda x: x["size"], reverse=True)
    return {"top_consumers": sizes[:limit]}

def get_swap_usage() -> Dict[str, Any]:
    swap = psutil.swap_memory()
    return {
        "total_mb": _bytes_to_mb(swap.total),
        "used_mb": _bytes_to_mb(swap.used),
        "free_mb": _bytes_to_mb(swap.free),
        "percent": swap.percent
    }

def get_memory_map() -> Dict[str, List[Dict[str, Any]]]:
    process = psutil.Process(os.getpid())
    maps = []
    try:
        for m in process.memory_maps():
            maps.append({"path": m.path, "rss_mb": _bytes_to_mb(m.rss)})
    except Exception as e:
        return {"status": "error", "message": str(e)}
    return {"memory_maps": maps}

def clear_caches() -> Dict[str, int]:
    global _MEMORY_HISTORY, _SNAPSHOTS
    cleared = len(_MEMORY_HISTORY) + len(_SNAPSHOTS)
    _MEMORY_HISTORY.clear()
    _SNAPSHOTS.clear()
    return {"status": "success", "items_cleared": cleared}

def optimize_memory() -> Dict[str, float]:
    before = get_process_memory().get("rss_mb", 0.0)
    clear_caches()
    force_garbage_collect()
    after = get_process_memory().get("rss_mb", 0.0)
    return {"status": "success", "freed_mb": round(before - after, 2)}

def get_object_size(obj: Any) -> Dict[str, float]:
    seen: Set[int] = set()
    size_bytes = _deep_getsizeof(obj, seen)
    return {"status": "success", "size_bytes": size_bytes, "size_mb": _bytes_to_mb(size_bytes)}

def get_memory_allocation_rate() -> Dict[str, float]:
    return {"status": "success", "rate_mb_per_sec": round(_LAST_CHECK.get("rate", 0.0), 4)}

def get_memory_trend() -> Dict[str, str]:
    if len(_MEMORY_HISTORY) < 5:
        return {"trend": "insufficient_data"}
    recent = [x["rss_mb"] for x in _MEMORY_HISTORY[-5:]]
    if recent[-1] > recent[0] * 1.05:
        trend = "increasing"
    elif recent[-1] < recent[0] * 0.95:
        trend = "decreasing"
    else:
        trend = "stable"
    return {"trend": trend}

def export_memory_report(filepath: str) -> Dict[str, str]:
    report = {
        "usage": get_memory_usage(),
        "swap": get_swap_usage(),
        "trend": get_memory_trend(),
        "allocation_rate": get_memory_allocation_rate(),
        "gc_stats": get_gc_stats()
    }
    try:
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=4)
        return {"status": "success", "file": filepath}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    # Test suite to ensure compilation and basic behavior
    print(monitor_memory(0.5))
    print(set_memory_threshold(512.0))
    time.sleep(1)
    print(get_memory_usage())
    print(optimize_memory())
