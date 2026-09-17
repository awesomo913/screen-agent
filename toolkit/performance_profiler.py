import time
import cProfile
import pstats
import tracemalloc
import psutil
import functools
import threading
import json
import io
import os
import sys
import asyncio
import inspect
from typing import Dict, Any, Callable, List, Optional

# ---------------------------------------------------------------------------
# Module State & Helpers
# ---------------------------------------------------------------------------
_timers: Dict[str, float] = {}
_timers_lock = threading.Lock()

_performance_thresholds: Dict[str, float] = {}
_thresholds_lock = threading.Lock()


def _make_result(data: Dict[str, Any], error: Optional[str] = None) -> Dict[str, Any]:
    """Standardized result envelope for all profiler functions."""
    return {
        "status": "error" if error else "success",
        "data": data or {},
        "error": error
    }


def _safe_call(func: Callable[..., Any], *args: Any, **kwargs: Any):
    """Execute wrapped call to isolate exceptions."""
    return func(*args, **kwargs)


# ---------------------------------------------------------------------------
# Core Profiling Functions
# ---------------------------------------------------------------------------

def time_function(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Dict[str, Any]:
    try:
        start = time.perf_counter()
        result = _safe_call(func, *args, **kwargs)
        end = time.perf_counter()
        return _make_result({
            "duration_sec": end - start,
            "wall_time": end - start,
            "result_type": type(result).__name__
        })
    except Exception as e:
        return _make_result({}, str(e))


def profile_function(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Dict[str, Any]:
    try:
        profiler = cProfile.Profile()
        profiler.enable()
        result = _safe_call(func, *args, **kwargs)
        profiler.disable()

        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats("cumulative")
        stats.print_stats(20)

        # Extract structured stats
        func_list = []
        for func_key, calls_data in stats.get_stats_profile().func_profiles.items():
            module, line_no, func_name = func_key
            func_list.append({
                "module": module if module else "<module>",
                "lineno": line_no,
                "function": func_name if func_name else "<method>",
                "ncalls": calls_data.ncalls,
                "tottime": round(calls_data.tottime, 4),
                "cumtime": round(calls_data.cumtime, 4)
            })

        return _make_result({
            "total_calls": sum(c["ncalls"] for c in func_list),
            "total_time": round(run_time, 4) if (run_time := stats.total_tt) is not None else 0.0,
            "top_functions": func_list[:20],
            "raw_stats": stream.getvalue()
        })
    except Exception as e:
        return _make_result({}, str(e))


def memory_profile(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Dict[str, Any]:
    try:
        tracemalloc.start()
        start = tracemalloc.take_snapshot()
        result = _safe_call(func, *args, **kwargs)
        tracemalloc.stop()
        end = tracemalloc.take_snapshot()

        diff = end.compare_to(start, "lineno")
        top_diff = [{"file": str(d.traceback), "line": d.traceback[-1].lineno, "size_diff": d.size_diff, "count_diff": d.count_diff} for d in diff[:10]]

        current, peak = tracemalloc.get_tracked_memory()
        return _make_result({
            "current_usage_bytes": current,
            "peak_usage_bytes": peak,
            "top_growth": top_diff,
            "result_type": type(result).__name__
        })
    except Exception as e:
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        return _make_result({}, str(e))


def get_memory_usage() -> Dict[str, Any]:
    try:
        proc = psutil.Process(os.getpid())
        mem_info = proc.memory_info()
        return _make_result({
            "rss_bytes": mem_info.rss,
            "vms_bytes": mem_info.vms,
            "percent": proc.memory_percent(),
            "pid": os.getpid()
        })
    except Exception as e:
        return _make_result({}, str(e))


def get_peak_memory() -> Dict[str, Any]:
    try:
        current, peak = (0, 0)
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_tracked_memory()
        # Fallback to OS-level RSS
        proc = psutil.Process(os.getpid())
        rss = proc.memory_info().rss
        return _make_result({
            "tracemalloc_peak_bytes": peak,
            "process_rss_bytes": rss,
            "note": "Peak tracked via tracemalloc if active, otherwise current RSS"
        })
    except Exception as e:
        return _make_result({}, str(e))


# ---------------------------------------------------------------------------
# Timer Utilities
# ---------------------------------------------------------------------------

def start_timer(label: str = "") -> Dict[str, Any]:
    try:
        with _timers_lock:
            _timers[label] = time.perf_counter()
        return _make_result({"label": label, "started": True})
    except Exception as e:
        return _make_result({}, str(e))


def stop_timer(label: str = "") -> Dict[str, Any]:
    try:
        with _timers_lock:
            if label not in _timers:
                raise ValueError(f"Timer '{label}' not started.")
            elapsed = time.perf_counter() - _timers[label]
            del _timers[label]
        return _make_result({"label": label, "elapsed_sec": elapsed, "stopped": True})
    except Exception as e:
        return _make_result({}, str(e))


def get_elapsed(label: str = "") -> Dict[str, Any]:
    try:
        with _timers_lock:
            if label not in _timers:
                raise ValueError(f"Timer '{label}' not found or already stopped.")
            elapsed = time.perf_counter() - _timers[label]
        return _make_result({"label": label, "elapsed_sec": elapsed, "running": True})
    except Exception as e:
        return _make_result({}, str(e))


# ---------------------------------------------------------------------------
# Benchmark & Comparison
# ---------------------------------------------------------------------------

def benchmark(func: Callable[..., Any], iterations: int = 1000) -> Dict[str, Any]:
    try:
        if iterations <= 0:
            raise ValueError("Iterations must be > 0")
        
        durations = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            _safe_call(func)
            t1 = time.perf_counter()
            durations.append(t1 - t0)

        return _make_result({
            "iterations": iterations,
            "total_sec": sum(durations),
            "avg_sec": sum(durations) / len(durations),
            "min_sec": min(durations),
            "max_sec": max(durations),
            "ops_per_sec": len(durations) / sum(durations) if sum(durations) > 0 else float('inf')
        })
    except Exception as e:
        return _make_result({}, str(e))


def compare_functions(funcs: List[Callable[..., Any]], iterations: int = 1000) -> Dict[str, Any]:
    try:
        results = {}
        for f in funcs:
            fname = getattr(f, "__name__", repr(f))
            bench = benchmark(f, iterations)
            results[fname] = bench["data"]
        return _make_result(results)
    except Exception as e:
        return _make_result({}, str(e))


def profile_code_block(code: str, globals_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        global_ns = globals_dict or {}
        profiler = cProfile.Profile()
        profiler.enable()
        exec(code, global_ns)
        profiler.disable()
        
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats("cumulative").print_stats(20)
        return _make_result({"stats": stream.getvalue()})
    except Exception as e:
        return _make_result({}, str(e))


def get_call_stack() -> Dict[str, Any]:
    try:
        stack = []
        for frame in inspect.stack():
            stack.append({
                "file": frame.filename,
                "line": frame.lineno,
                "function": frame.function,
                "code_context": [c.strip() for c in frame.code_context] if frame.code_context else []
            })
        return _make_result({"stack": stack[2:-1]})
    except Exception as e:
        return _make_result({}, str(e))


def trace_function_calls(func: Callable[..., Any], *args: Any) -> Dict[str, Any]:
    try:
        call_counts = {}
        def tracer(frame, event, arg):
            if event == "call":
                code = frame.f_code
                key = f"{code.co_filename}:{code.co_name}:{code.co_firstlineno}"
                call_counts[key] = call_counts.get(key, 0) + 1
            return tracer

        sys.settrace(tracer)
        try:
            _safe_call(func, *args)
        finally:
            sys.settrace(None)
        return _make_result({"call_counts": call_counts})
    except Exception as e:
        sys.settrace(None)
        return _make_result({}, str(e))


def measure_throughput(func: Callable[..., Any], duration: float = 5.0) -> Dict[str, Any]:
    try:
        t0 = time.monotonic()
        count = 0
        while time.monotonic() - t0 < duration:
            _safe_call(func)
            count += 1
        elapsed = time.monotonic() - t0
        return _make_result({
            "duration_sec": elapsed,
            "total_calls": count,
            "throughput_ops_per_sec": count / elapsed if elapsed > 0 else 0
        })
    except Exception as e:
        return _make_result({}, str(e))


def detect_memory_leaks(func: Callable[..., Any], iterations: int = 100) -> Dict[str, Any]:
    try:
        tracemalloc.start()
        snapshots = []
        for i in range(iterations + 1):
            if i == 0:
                snapshots.append(tracemalloc.take_snapshot())
            _safe_call(func)
            if i == iterations:
                snapshots.append(tracemalloc.take_snapshot())
        tracemalloc.stop()

        before, after = snapshots
        stats = after.compare_to(before, "filename")
        total_diff = sum(abs(s.size_diff) for s in stats if s.size_diff > 0)
        
        leaks = [{"filename": str(s.traceback), "size_diff_bytes": s.size_diff, "count_diff": s.count_diff} for s in sorted(stats, key=lambda x: x.size_diff, reverse=True)[:10]]
        
        return _make_result({
            "total_growth_bytes": total_diff,
            "iterations_tested": iterations,
            "potential_leaks": leaks,
            "is_leak_suspected": total_diff > (1024 * 1024)
        })
    except Exception as e:
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        return _make_result({}, str(e))


def get_cpu_time() -> Dict[str, Any]:
    try:
        user = time.process_time()
        sys_cpu = time.process_time_ns() // 1_000_000_000
        return _make_result({
            "user_cpu_sec": user,
            "system_cpu_sec": sys_cpu,
            "pid": os.getpid()
        })
    except Exception as e:
        return _make_result({}, str(e))


def profile_io(func: Callable[..., Any], *args: Any) -> Dict[str, Any]:
    try:
        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        _safe_call(func, *args)
        cpu_end = time.process_time()
        wall_end = time.perf_counter()
        
        wall_time = wall_end - wall_start
        cpu_time = cpu_end - cpu_start
        io_wait = max(0, wall_time - cpu_time)
        
        return _make_result({
            "wall_time_sec": round(wall_time, 4),
            "cpu_time_sec": round(cpu_time, 4),
            "io_wait_estimate_sec": round(io_wait, 4),
            "io_bound_percent": round((io_wait / wall_time) * 100, 2) if wall_time > 0 else 0
        })
    except Exception as e:
        return _make_result({}, str(e))


def create_flame_graph(func: Callable[..., Any], output_path: str, *args: Any) -> Dict[str, Any]:
    """Generates folded stack format compatible with flamegraph.pl"""
    try:
        profiler = cProfile.Profile()
        
        call_stacks: Dict[str, int] = {}
        current_stack = []
        def tracer(frame, event, arg):
            nonlocal current_stack
            code = frame.f_code
            if event == "call":
                current_stack.append(f"{code.co_filename}:{code.co_name}:{code.co_firstlineno}")
            elif event == "return":
                if current_stack:
                    stack_str = ";".join(current_stack)
                    call_stacks[stack_str] = call_stacks.get(stack_str, 0) + 1
                    current_stack.pop()
            return tracing

        profiler.runcall(func, *args)
        
        with open(output_path, "w") as f:
            for stack, count in call_stacks.items():
                f.write(f"{stack} {count}\n")
                
        return _make_result({"path": output_path, "stacks_recorded": len(call_stacks)})
    except Exception as e:
        return _make_result({}, str(e))


def get_hot_spots(func: Callable[..., Any], top_n: int = 10, *args: Any) -> Dict[str, Any]:
    try:
        profiler = cProfile.Profile()
        profiler.runcall(func, *args)
        
        s = pstats.Stats(profiler)
        hot_spots = []
        for func_key, (cc, nc, tt, ct, callers) in s.stats.items():
            module, line, name = func_key
            hot_spots.append({
                "module": module or "<module>",
                "line": line,
                "name": name or "<method>",
                "cumulative_time": round(ct, 4),
                "total_time": round(tt, 4),
                "call_count": nc
            })
            
        hot_spots.sort(key=lambda x: x["cumulative_time"], reverse=True)
        return _make_result({"hot_spots": hot_spots[:top_n]})
    except Exception as e:
        return _make_result({}, str(e))


def monitor_resources(duration: float = 10.0, interval: float = 0.5) -> Dict[str, Any]:
    try:
        proc = psutil.Process(os.getpid())
        data_points = []
        steps = max(1, int(duration / interval))
        
        for _ in range(steps):
            t = time.time()
            mem = proc.memory_info().rss
            cpu = proc.cpu_percent(interval=0.1)
            data_points.append({"timestamp": t, "memory_mb": round(mem / 1024 / 1024, 2), "cpu_percent": cpu})
            time.sleep(interval)
            
        return _make_result({
            "samples": len(data_points),
            "timeline": data_points,
            "avg_cpu": sum(d["cpu_percent"] for d in data_points) / len(data_points),
            "peak_memory_mb": max(d["memory_mb"] for d in data_points)
        })
    except Exception as e:
        return _make_result({}, str(e))


def line_profile(func: Callable[..., Any], *args: Any) -> Dict[str, Any]:
    try:
        line_counts = {}
        def trace_lines(frame, event, arg):
            if event == "line":
                key = (frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name)
                line_counts[key] = line_counts.get(key, 0) + 1
            return trace_lines

        sys.settrace(trace_lines)
        try:
            _safe_call(func, *args)
        finally:
            sys.settrace(None)
            
        profile_list = [{"file": k[0], "line": k[1], "func": k[2], "hits": v} for k, v in line_counts.items()]
        profile_list.sort(key=lambda x: x["hits"], reverse=True)
        return _make_result({"line_hits": profile_list[:50]})
    except Exception as e:
        sys.settrace(None)
        return _make_result({}, str(e))


def async_profile(coro: Callable[..., Any], *args: Any) -> Dict[str, Any]:
    try:
        async def run_coro():
            t0 = time.perf_counter()
            result = await coro(*args)
            t1 = time.perf_counter()
            return result, t1 - t0

        result, elapsed = asyncio.run(run_coro())
        return _make_result({"async_duration_sec": elapsed, "result_type": type(result).__name__})
    except Exception as e:
        return _make_result({}, str(e))


def generate_report(profiles: List[Dict[str, Any]], output_path: str = "") -> Dict[str, Any]:
    try:
        report = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "profiles_count": len(profiles), "data": profiles}
        json_str = json.dumps(report, indent=2, default=str)
        
        if output_path:
            with open(output_path, "w") as f:
                f.write(json_str)
            return _make_result({"path": output_path, "size_bytes": os.path.getsize(output_path)})
            
        return _make_result({"json": report})
    except Exception as e:
        return _make_result({}, str(e))


def set_performance_threshold(metric: str, threshold: float) -> Dict[str, Any]:
    try:
        with _thresholds_lock:
            _performance_thresholds[metric] = threshold
        return _make_result({"metric": metric, "threshold": threshold})
    except Exception as e:
        return _make_result({}, str(e))


def continuous_monitor(pid: int = 0, interval: float = 1.0, duration: float = 60.0) -> Dict[str, Any]:
    try:
        target_pid = pid or os.getpid()
        proc = psutil.Process(target_pid)
        start_time = time.time()
        history = []
        
        while time.time() - start_time < duration:
            try:
                with proc.oneshot():
                    mem = proc.memory_info().rss
                    cpu = proc.cpu_percent()
                    threads = proc.num_threads()
                    fds = proc.num_fds() if sys.platform != "win32" else 0
                    
                history.append({
                    "timestamp": time.time() - start_time,
                    "cpu_percent": cpu,
                    "memory_mb": round(mem / 1024 / 1024, 2),
                    "threads": threads,
                    "open_files_filedes": fds
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                history.append({"timestamp": time.time() - start_time, "error": "Process gone or inaccessible"})
                break
            time.sleep(interval)
            
        return _make_result({
            "pid": target_pid,
            "samples": len(history),
            "data": history
        })
    except Exception as e:
        return _make_result({}, str(e))