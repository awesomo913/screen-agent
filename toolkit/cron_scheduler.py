import schedule
import apscheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
import json
from pathlib import Path
import os
import time
import logging
import subprocess
import functools
import threading
from typing import Any, Callable, Dict, List, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global State & Synchronization
_scheduler: Optional[BackgroundScheduler] = None
_schedule_runner_thread: Optional[threading.Thread] = None
_schedule_runner_event = threading.Event()
_lock = threading.RLock()

_job_metadata: Dict[str, Dict[str, Any]] = {}
_job_history: Dict[str, List[Dict[str, Any]]] = {}
_job_groups: Dict[str, List[str]] = {}
_job_retries: Dict[str, int] = {}
_original_funcs: Dict[str, Dict[str, Any]] = {}


def _parse_time_str(time_str: str) -> Dict[str, int]:
    """Parse HH:MM:SS or HH:MM into dict components."""
    parts = time_str.strip().split(":")
    return {
        "hour": int(parts[0]),
        "minute": int(parts[1]),
        "second": int(parts[2]) if len(parts) > 2 else 0
    }


def _execute_wrapper(func: Callable, job_id: str, args: tuple) -> Any:
    """Internal wrapper for execution tracking, retries, and history logging."""
    start_time = datetime.now()
    try:
        result = func(*args) if args else func()
        duration = (datetime.now() - start_time).total_seconds()
        entry = {
            "job_id": job_id,
            "start_time": start_time.isoformat(),
            "status": "success",
            "duration": duration,
            "result": str(result)
        }
        with _lock:
            _job_history.setdefault(job_id, []).append(entry)
        logger.info(f"Job '{job_id}' completed successfully in {duration:.3f}s")
        return result
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        entry = {
            "job_id": job_id,
            "start_time": start_time.isoformat(),
            "status": "failed",
            "duration": duration,
            "error": str(e)
        }
        with _lock:
            _job_history.setdefault(job_id, []).append(entry)
        logger.error(f"Job '{job_id}' failed: {e}")

        # Automatic retry logic
        retries_left = _job_retries.get(job_id, 0)
        if retries_left > 0:
            _job_retries[job_id] = retries_left - 1
            logger.info(f"Retrying job '{job_id}'. Remaining retries: {_job_retries[job_id]}")
            if _scheduler and _scheduler.running:
                try:
                    _scheduler.add_job(
                        functools.partial(_execute_wrapper, func, job_id, args or ()),
                        trigger=DateTrigger(run_date=datetime.now() + timedelta(seconds=2)),
                        id=f"{job_id}_retry",
                        replace_existing=True
                    )
                except Exception as retry_err:
                    logger.error(f"Retry scheduling failed for '{job_id}': {retry_err}")
    return None


def _schedule_runner():
    """Background thread to run `schedule` library pending tasks."""
    while not _schedule_runner_event.is_set():
        schedule.run_pending()
        _schedule_runner_event.wait(1.0)


# ------------------- Scheduler Management -------------------

def start_scheduler() -> Dict[str, Any]:
    """Initialize and start the background scheduler."""
    global _scheduler, _schedule_runner_thread
    try:
        with _lock:
            if _scheduler and _scheduler.running:
                return {"success": True, "message": "Scheduler is already running."}
            
            if not _scheduler:
                _scheduler = BackgroundScheduler(jobstores={'default': apscheduler.jobstores.memory.MemoryJobStore()})
            
            if not _scheduler.running:
                _scheduler.start()
                if not (_schedule_runner_thread and _schedule_runner_thread.is_alive()):
                    _schedule_runner_event.clear()
                    _schedule_runner_thread = threading.Thread(target=_schedule_runner, daemon=True)
                    _schedule_runner_thread.start()
                logger.info("Scheduler started successfully.")
                return {"success": True, "message": "Scheduler started."}
        return {"success": False, "message": "Scheduler state is inconsistent."}
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        return {"success": False, "message": str(e)}


def stop_scheduler() -> Dict[str, Any]:
    """Stop the scheduler and clear pending schedule library tasks."""
    global _scheduler
    try:
        with _lock:
            if _scheduler and _scheduler.running:
                _scheduler.shutdown(wait=True)
                logger.info("Scheduler stopped.")
            schedule.clear()
            _schedule_runner_event.set()
            return {"success": True, "message": "Scheduler stopped and cleaned up."}
        return {"success": True, "message": "Scheduler was already stopped."}
    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}")
        return {"success": False, "message": str(e)}


def restart_scheduler() -> Dict[str, Any]:
    """Stop and then start the scheduler."""
    try:
        stop_scheduler()
        return start_scheduler()
    except Exception as e:
        logger.error(f"Failed to restart scheduler: {e}")
        return {"success": False, "message": str(e)}


# ------------------- Core Job Operations -------------------

def create_job(func: Callable, trigger: Any, args: Optional[tuple] = None, job_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a job with a given trigger, function, and arguments."""
    global _scheduler
    try:
        if not _scheduler or not _scheduler.running:
            return {"success": False, "message": "Scheduler not running. Call start_scheduler() first."}
        
        with _lock:
            if job_id is None:
                job_id = f"job_{int(time.time() * 1000)}"
            _job_metadata.setdefault(job_id, {})
            _job_metadata[job_id].update({
                "func_name": func.__name__,
                "args": args,
                "status": "scheduled",
                "created_at": datetime.now().isoformat()
            })
            _original_funcs[job_id] = {"func": func, "args": args}
            _job_retries.setdefault(job_id, 0)

        wrapper = functools.partial(_execute_wrapper, func, job_id, args or ())
        _scheduler.add_job(wrapper, trigger=trigger, id=job_id, replace_existing=True)
        return {"success": True, "job_id": job_id, "message": "Job created successfully.", "data": _job_metadata[job_id]}
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        return {"success": False, "message": str(e)}


def remove_job(job_id: str) -> Dict[str, Any]:
    """Remove a job by ID."""
    try:
        if not _scheduler:
            return {"success": False, "message": "Scheduler not initialized."}
        with _lock:
            if job_id not in _job_metadata:
                return {"success": False, "message": "Job ID not found."}
            try:
                _scheduler.remove_job(job_id)
            except apscheduler.JobLookupError:
                pass # Already removed or not found in scheduler
            _job_metadata.pop(job_id, None)
            _original_funcs.pop(job_id, None)
            _job_retries.pop(job_id, None)
        return {"success": True, "message": f"Job '{job_id}' removed."}
    except Exception as e:
        logger.error(f"Failed to remove job '{job_id}': {e}")
        return {"success": False, "message": str(e)}


def pause_job(job_id: str) -> Dict[str, Any]:
    """Pause a specific job."""
    try:
        if not _scheduler or not _scheduler.running:
            return {"success": False, "message": "Scheduler not running."}
        with _lock:
            if job_id not in _job_metadata:
                return {"success": False, "message": "Job ID not found."}
            _scheduler.pause_job(job_id)
            _job_metadata[job_id]["status"] = "paused"
        return {"success": True, "message": f"Job '{job_id}' paused."}
    except Exception as e:
        logger.error(f"Failed to pause job '{job_id}': {e}")
        return {"success": False, "message": str(e)}


def resume_job(job_id: str) -> Dict[str, Any]:
    """Resume a paused job."""
    try:
        if not _scheduler or not _scheduler.running:
            return {"success": False, "message": "Scheduler not running."}
        with _lock:
            if job_id not in _job_metadata:
                return {"success": False, "message": "Job ID not found."}
            _scheduler.resume_job(job_id)
            _job_metadata[job_id]["status"] = "resumed"
        return {"success": True, "message": f"Job '{job_id}' resumed."}
    except Exception as e:
        logger.error(f"Failed to resume job '{job_id}': {e}")
        return {"success": False, "message": str(e)}


def list_jobs() -> Dict[str, Any]:
    """List all registered jobs with their metadata."""
    try:
        with _lock:
            jobs_snapshot = {jid: dict(meta) for jid, meta in _job_metadata.items()}
            for jid in jobs_snapshot:
                try:
                    job_obj = _scheduler.get_job(jid) if _scheduler else None
                    jobs_snapshot[jid]["scheduler_next_run"] = job_obj.next_run_time.isoformat() if job_obj and job_obj.next_run_time else None
                    jobs_snapshot[jid]["scheduler_status"] = "scheduled"
                except apscheduler.JobLookupError:
                    jobs_snapshot[jid]["scheduler_status"] = "removed_or_invalid"
        return {"success": True, "count": len(jobs_snapshot), "jobs": jobs_snapshot}
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        return {"success": False, "message": str(e)}


def get_job_status(job_id: str) -> Dict[str, Any]:
    """Get detailed status of a specific job."""
    try:
        with _lock:
            if job_id not in _job_metadata:
                return {"success": False, "message": "Job ID not found."}
            meta = dict(_job_metadata[job_id])
            meta["retries_remaining"] = _job_retries.get(job_id, 0)
            meta["history_count"] = len(_job_history.get(job_id, []))
            try:
                if _scheduler:
                    job_obj = _scheduler.get_job(job_id)
                    if job_obj:
                        meta["is_paused"] = job_obj.next_run_time is None
                        meta["next_run"] = job_obj.next_run_time.isoformat() if job_obj.next_run_time else None
            except apscheduler.JobLookupError:
                meta["scheduler_status"] = "not_running"
        return {"success": True, "job_id": job_id, "data": meta}
    except Exception as e:
        logger.error(f"Failed to get status for '{job_id}': {e}")
        return {"success": False, "message": str(e)}


def get_next_run(job_id: str) -> Dict[str, Any]:
    """Get the next scheduled run time for a job."""
    try:
        if not _scheduler:
            return {"success": False, "message": "Scheduler not initialized."}
        job_obj = _scheduler.get_job(job_id)
        if not job_obj:
            return {"success": False, "message": "Job not found in scheduler."}
        next_run = job_obj.next_run_time.isoformat() if job_obj.next_run_time else None
        return {"success": True, "job_id": job_id, "next_run": next_run}
    except Exception as e:
        logger.error(f"Failed to get next run for '{job_id}': {e}")
        return {"success": False, "message": str(e)}


def get_job_history(job_id: str, limit: int = 10) -> Dict[str, Any]:
    """Retrieve execution history for a job."""
    try:
        with _lock:
            history = _job_history.get(job_id, [])
            return {"success": True, "job_id": job_id, "history": history[-limit:] if limit else history, "total_records": len(history)}
    except Exception as e:
        logger.error(f"Failed to retrieve history for '{job_id}': {e}")
        return {"success": False, "message": str(e)}


# ------------------- Convenience Runners -------------------

def run_at_time(func: Callable, time_str: str, args: Optional[tuple] = None) -> Dict[str, Any]:
    """Schedule job to run daily at a specific time string (HH:MM[:SS])."""
    try:
        t = _parse_time_str(time_str)
        trigger = CronTrigger(hour=t["hour"], minute=t["minute"], second=t["second"])
        job_id = f"at_time_{func.__name__}_{time_str.replace(':','')}"
        return create_job(func, trigger, args, job_id.replace("/", "_"))
    except Exception as e:
        return {"success": False, "message": f"Invalid time string or function: {str(e)}"}


def run_interval(func: Callable, seconds: Union[int, float], args: Optional[tuple] = None) -> Dict[str, Any]:
    """Schedule job to run repeatedly every N seconds."""
    try:
        trigger = IntervalTrigger(seconds=seconds)
        job_id = f"interval_{func.__name__}_{seconds}s"
        return create_job(func, trigger, args, job_id.replace("/", "_"))
    except Exception as e:
        return {"success": False, "message": str(e)}


def run_daily(func: Callable, time_str: str, args: Optional[tuple] = None) -> Dict[str, Any]:
    """Schedule job to run daily at specified time."""
    return run_at_time(func, time_str, args)


def run_weekly(func: Callable, day: Union[str, int], time_str: str, args: Optional[tuple] = None) -> Dict[str, Any]:
    """Schedule job weekly on a specific day at a specific time."""
    try:
        t = _parse_time_str(time_str)
        day_str = str(day)
        if isinstance(day, int):
            days_map = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
            day_str = days_map.get(day % 7, "mon")
        trigger = CronTrigger(day_of_week=day_str, hour=t["hour"], minute=t["minute"])
        job_id = f"weekly_{day_str}_{time_str.replace(':','')}"
        return create_job(func, trigger, args, job_id.replace("/", "_"))
    except Exception as e:
        return {"success": False, "message": str(e)}


def run_monthly(func: Callable, day: int, time_str: str, args: Optional[tuple] = None) -> Dict[str, Any]:
    """Schedule job monthly on a specific day at a specific time."""
    try:
        t = _parse_time_str(time_str)
        trigger = CronTrigger(day=day, hour=t["hour"], minute=t["minute"])
        job_id = f"monthly_{day}_{time_str.replace(':','')}"
        return create_job(func, trigger, args, job_id.replace("/", "_"))
    except Exception as e:
        return {"success": False, "message": str(e)}


def run_cron(func: Callable, cron_expression: str, args: Optional[tuple] = None) -> Dict[str, Any]:
    """Schedule job using standard cron syntax (minute hour day month day_of_week)."""
    try:
        trigger = CronTrigger.from_crontab(cron_expression)
        job_id = f"cron_{func.__name__}_{hash(cron_expression)}"
        return create_job(func, trigger, args, str(job_id))
    except Exception as e:
        return {"success": False, "message": f"Invalid cron expression: {str(e)}"}


def run_once(func: Callable, delay: Union[int, float], args: Optional[tuple] = None) -> Dict[str, Any]:
    """Execute job once after a delay in seconds."""
    try:
        trigger = DateTrigger(run_date=datetime.now() + timedelta(seconds=delay))
        job_id = f"once_{func.__name__}_{delay}s"
        return create_job(func, trigger, args, job_id.replace("/", "_"))
    except Exception as e:
        return {"success": False, "message": str(e)}


def run_at_datetime(func: Callable, dt: datetime, args: Optional[tuple] = None) -> Dict[str, Any]:
    """Execute job once at an exact datetime."""
    try:
        if not isinstance(dt, datetime):
            dt = datetime.fromisoformat(str(dt))
        trigger = DateTrigger(run_date=dt)
        job_id = f"at_dt_{dt.strftime('%Y%m%d%H%M%S')}"
        return create_job(func, trigger, args, job_id)
    except Exception as e:
        return {"success": False, "message": str(e)}


# ------------------- Advanced Scheduling -------------------

def set_job_max_retries(job_id: str, retries: int) -> Dict[str, Any]:
    """Set maximum retry attempts for a failed job."""
    try:
        with _lock:
            if job_id not in _job_metadata:
                return {"success": False, "message": "Job ID not found."}
            _job_retries[job_id] = max(0, int(retries))
        return {"success": True, "message": f"Max retries for '{job_id}' set to {_job_retries[job_id]}."}
    except Exception as e:
        return {"success": False, "message": str(e)}


def run_shell_scheduled(command: str, trigger: Any) -> Dict[str, Any]:
    """Schedule a shell command execution."""
    def _shell_runner(cmd: str) -> Dict[str, Any]:
        try:
            start = datetime.now()
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=3600)
            return {
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "duration": (datetime.now() - start).total_seconds()
            }
        except subprocess.TimeoutExpired:
            return {"returncode": -1, "error": "Command timed out"}
        except Exception as e:
            return {"returncode": -1, "error": str(e)}

    job_id = f"shell_{hash(command)}"
    return create_job(_shell_runner, trigger, args=(command,), job_id=job_id)


def chain_jobs(job_ids: List[str], sequential: bool = True) -> Dict[str, Any]:
    """Create a meta-job that executes multiple jobs in sequence or parallel."""
    def _chain_runner(jobs: List[str], seq: bool):
        results = []
        for jid in jobs:
            if jid in _original_funcs:
                try:
                    info = _original_funcs[jid]
                    res = _execute_wrapper(info["func"], jid, info["args"] or ())
                    results.append({"job_id": jid, "status": "executed", "result": res})
                except Exception as e:
                    results.append({"job_id": jid, "status": "error", "error": str(e)})
                if seq and jid != jobs[-1]:
                    time.sleep(0.1) # Small yield to prevent CPU thrashing
        return results

    chain_id = f"chain_{'_'.join(job_ids)}"
    trigger = DateTrigger(run_date=datetime.now() + timedelta(seconds=1)) # Execute immediately after creation
    return create_job(_chain_runner, trigger, args=(job_ids, sequential), job_id=chain_id)


def create_job_group(name: str, jobs: List[str]) -> Dict[str, Any]:
    """Group job IDs under a single label for management."""
    try:
        with _lock:
            validated = [j for j in jobs if j in _job_metadata]
            if not validated:
                return {"success": False, "message": "No valid job IDs provided."}
            _job_groups[name] = validated
        return {"success": True, "group_name": name, "job_count": len(validated), "jobs": validated}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ------------------- Export / Import -------------------

def export_schedule(filepath: str) -> Dict[str, Any]:
    """Export job metadata, groups, and history to a JSON file."""
    try:
        path = Path(filepath)
        with _lock:
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "metadata": _job_metadata,
                "retries": _job_retries,
                "groups": _job_groups,
                "history": _job_history
            }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, default=str)
        return {"success": True, "message": f"Schedule exported to {path.resolve()}", "file_path": str(path.resolve())}
    except Exception as e:
        logger.error(f"Failed to export schedule: {e}")
        return {"success": False, "message": str(e)}


def import_schedule(filepath: str) -> Dict[str, Any]:
    """Import job configuration from a JSON file and reschedule jobs."""
    try:
        path = Path(filepath)
        if not path.exists():
            return {"success": False, "message": f"File not found: {filepath}"}
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        with _lock:
            _job_metadata.clear()
            _job_retries.clear()
            _job_groups.clear()
            _job_history.clear()
            _original_funcs.clear()
            
            _job_metadata.update(data.get("metadata", {}))
            _job_retries.update(data.get("retries", {}))
            _job_groups.update(data.get("groups", {}))
            _job_history.update(data.get("history", {}))
        
        # Note: Actual functions cannot be serialized. Jobs must be recreated manually by the calling agent.
        # This import restores state/config/history.
        return {"success": True, "message": "Schedule configuration and state imported successfully. Note: Functions must be re-registered programmatically."}
    except Exception as e:
        logger.error(f"Failed to import schedule: {e}")
        return {"success": False, "message": str(e)}


# Ensure schedule library is actively maintained if used alongside APScheduler
schedule.every(10).minutes.do(lambda: logger.debug("Schedule library heartbeat active"))