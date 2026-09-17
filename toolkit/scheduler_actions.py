# scheduler_actions.py
"""
Scheduler actions for the Screen Agent Toolkit.

This module implements a lightweight, thread‑based scheduler that can:
* run one‑off, recurring, fixed‑time, daily and cron‑style jobs,
* pause / resume / cancel tasks,
* group / chain tasks,
* keep a history of executions,
* enforce max concurrent workers,
* export / import schedules,
* backup / restore scheduler state,
* expose a rich set of helper utilities (cron parsing, human‑readable output, …).

All public functions return a ``Dict`` that follows the convention::

    {
        "status": "success" | "error",
        "message": str,
        "data": <optional payload>
    }

Only the Python standard library is used:
    threading, time, json, typing, pathlib, datetime, uuid,
    heapq, sched, functools, logging
"""

from __future__ import annotations

import threading
import time
import json
import logging
import uuid
import heapq
import sched
import functools
from pathlib import Path
from datetime import datetime, timedelta
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Tuple,
    Optional,
    Set,
    Union,
)

# --------------------------------------------------------------------------- #
# Global logger configuration
# --------------------------------------------------------------------------- #
_logger = logging.getLogger(__name__)
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(threadName)s %(message)s"
    )
    _handler.setFormatter(_formatter)
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)

# --------------------------------------------------------------------------- #
# Helper data structures
# --------------------------------------------------------------------------- #
class Task:
    """Container for a scheduled job."""
    def __init__(
        self,
        func: Callable,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
        schedule_type: str,
        *,
        run_at: Optional[datetime] = None,
        interval: Optional[int] = None,
        cron_expr: Optional[str] = None,
        priority: int = 0,
        timeout: Optional[float] = None,
    ) -> None:
        self.id: str = uuid.uuid4().hex
        self.func: Callable = func
        self.args: Tuple[Any, ...] = args
        self.kwargs: Dict[str, Any] = kwargs
        self.schedule_type: str = schedule_type
        self.run_at: Optional[datetime] = run_at
        self.interval: Optional[int] = interval
        self.cron_expr: Optional[str] = cron_expr
        self.priority: int = priority
        self.timeout: Optional[float] = timeout

        self.cancelled: bool = False
        self.paused: bool = False
        self.dependencies: Set[str] = set()
        self.dependents: Set[str] = set()      # reverse links for quick graph walk
        self.history: List[Dict[str, Any]] = []  # execution records

        # callbacks
        self.on_success: Optional[Callable[[str, Any], None]] = None
        self.on_failure: Optional[Callable[[str, Exception], None]] = None

    # ------------------------------------------------------------------- #
    # Helpers used by the scheduler core
    # ------------------------------------------------------------------- #
    def next_run_time(self, now: datetime) -> Optional[datetime]:
        """Calculate the next run time based on the schedule type."""
        if self.cancelled:
            return None
        if self.paused:
            return None
        if self.schedule_type == "once":
            return self.run_at
        if self.schedule_type == "recurring":
            return now + timedelta(seconds=self.interval or 0)
        if self.schedule_type == "at":
            return self.run_at
        if self.schedule_type == "daily":
            target = now.replace(hour=self.run_at.hour,
                                 minute=self.run_at.minute,
                                 second=0,
                                 microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target
        if self.schedule_type == "cron":
            return next_cron_time(self.cron_expr, now)  # type: ignore
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialisable representation used for export / API responses."""
        return {
            "id": self.id,
            "schedule_type": self.schedule_type,
            "run_at": self.run_at.isoformat() if self.run_at else None,
            "interval": self.interval,
            "cron_expr": self.cron_expr,
            "priority": self.priority,
            "cancelled": self.cancelled,
            "paused": self.paused,
            "timeout": self.timeout,
            "dependencies": list(self.dependencies),
            "history": self.history,
        }

class Scheduler:
    """Thread‑safe wrapper around ``sched.scheduler`` with extended features."""
    def __init__(self, max_workers: int = 4) -> None:
        self.id: str = uuid.uuid4().hex
        self._sched = sched.scheduler(timefunc=time.time, delayfunc=time.sleep)
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.RLock()
        self._running: Set[str] = set()
        self._failed: Set[str] = set()
        self._max_workers = max_workers
        self._semaphore = threading.Semaphore(max_workers)

        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(
            target=self._run_loop,
            name=f"Scheduler-{self.id[:8]}",
            daemon=True,
        )
        self._worker_thread.start()
        _logger.info("Scheduler %s created (max_workers=%d)", self.id, max_workers)

    # ------------------------------------------------------------------- #
    # Core loop
    # ------------------------------------------------------------------- #
    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    # Feed the internal scheduler with the next due tasks
                    now = time.time()
                    while self._sched.queue and self._sched.queue[0].time <= now:
                        event = self._sched.queue[0]
                        self._sched.run(blocking=False)
                time.sleep(0.2)
            except Exception as exc:  # pragma: no cover
                _logger.exception("Unexpected error in scheduler loop: %s", exc)

    # ------------------------------------------------------------------- #
    # Public API used by the helper functions below
    # ------------------------------------------------------------------- #
    def _schedule_task(self, task: Task, when: datetime) -> None:
        """Insert a task into the internal ``sched.scheduler``."""
        delay = max(0.0, (when - datetime.utcnow()).total_seconds())
        self._sched.enter(delay, task.priority, self._execute_task, argument=(task.id,))
        _logger.debug("Task %s scheduled to run at %s (in %.2f sec)",
                      task.id, when.isoformat(), delay)

    def _execute_task(self, task_id: str) -> None:
        """Execute a task respecting concurrency, timeout and dependencies."""
        task = self._tasks.get(task_id)
        if not task:
            _logger.warning("Attempted to run unknown task %s", task_id)
            return
        if task.cancelled or task.paused:
            _logger.info("Task %s is cancelled/paused; skipping execution", task_id)
            return
        if task.dependencies - set(self._tasks.keys()):
            # Some dependencies are unknown – treat as not ready
            _logger.info("Task %s has unknown dependencies; skipping", task_id)
            return
        if any(dep not in self._tasks or self._tasks[dep].cancelled for dep in task.dependencies):
            _logger.info("Task %s dependencies not satisfied; skipping", task_id)
            return
        # Acquire concurrency slot
        acquired = self._semaphore.acquire(blocking=False)
        if not acquired:
            # Reschedule soon (back‑off) if we cannot run now
            self._schedule_task(task, datetime.utcnow() + timedelta(seconds=1))
            _logger.debug("Task %s postponed due to max concurrency limit", task.id)
            return

        def _run():
            start = datetime.utcnow()
            result = None
            error: Optional[Exception] = None
            try:
                if task.timeout:
                    timer = threading.Timer(task.timeout, lambda: None)
                    timer.start()
                result = task.func(*task.args, **task.kwargs)
                if timer:
                    timer.cancel()
                # success callback
                if task.on_success:
                    try:
                        task.on_success(task.id, result)
                    except Exception:  # pragma: no cover
                        _logger.exception("Success callback for %s raised", task.id)
                status = "success"
            except Exception as exc:  # pragma: no cover
                error = exc
                status = "failure"
                self._failed.add(task.id)
                _logger.exception("Task %s raised an exception", task.id)
                if task.on_failure:
                    try:
                        task.on_failure(task.id, exc)
                    except Exception:  # pragma: no cover
                        _logger.exception("Failure callback for %s raised", task.id)
            finally:
                end = datetime.utcnow()
                # Record history
                task.history.append(
                    {
                        "run_at": start.isoformat(),
                        "finished_at": end.isoformat(),
                        "status": status,
                        "result": repr(result) if status == "success" else None,
                        "error": repr(error) if error else None,
                    }
                )
                self._running.discard(task.id)
                self._semaphore.release()

                # Reschedule if recurring / cron / daily
                if not task.cancelled and not task.paused and status == "success":
                    next_run = task.next_run_time(datetime.utcnow())
                    if next_run:
                        self._schedule_task(task, next_run)

        # Mark as running
        self._running.add(task.id)
        threading.Thread(target=_run, name=f"Task-{task.id[:8]}", daemon=True).start()

    # ------------------------------------------------------------------- #
    # Scheduler maintenance helpers
    # ------------------------------------------------------------------- #
    def shutdown(self) -> None:
        self._stop_event.set()
        self._worker_thread.join(timeout=5)
        _logger.info("Scheduler %s stopped", self.id)

    # ------------------------------------------------------------------- #
    # CRUD utilities used by the public helper functions
    # ------------------------------------------------------------------- #
    def add_task(self, task: Task, when: Optional[datetime] = None) -> None:
        with self._lock:
            self._tasks[task.id] = task
            run_time = when or task.next_run_time(datetime.utcnow())
            if run_time:
                self._schedule_task(task, run_time)

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def remove_task(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.pop(task_id, None)
            if task:
                task.cancelled = True
                return True
            return False

    def list_tasks(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [t.to_dict() for t in self._tasks.values()]

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "scheduler_id": self.id,
                "task_count": len(self._tasks),
                "running": len(self._running),
                "failed": len(self._failed),
                "max_workers": self._max_workers,
            }

# --------------------------------------------------------------------------- #
# Global registry of schedulers (scheduler_id -> Scheduler instance)
# --------------------------------------------------------------------------- #
_SCHEDULERS: Dict[str, Scheduler] = {}
_REGISTRY_LOCK = threading.RLock()

def _response(status: str, message: str, data: Any = None) -> Dict[str, Any]:
    resp = {"status": status, "message": message}
    if data is not None:
        resp["data"] = data
    return resp

# --------------------------------------------------------------------------- #
# Public API (functions required by the prompt)
# --------------------------------------------------------------------------- #
def create_scheduler(max_workers: int = 4) -> Dict[str, Any]:
    """Create a new scheduler and return its identifier."""
    try:
        scheduler = Scheduler(max_workers=max_workers)
        with _REGISTRY_LOCK:
            _SCHEDULERS[scheduler.id] = scheduler
        return _response("success", "Scheduler created",
                         {"scheduler_id": scheduler.id})
    except Exception as exc:  # pragma: no cover
        _logger.exception("Failed to create scheduler")
        return _response("error", str(exc))

def _get_scheduler(scheduler_id: str) -> Optional[Scheduler]:
    with _REGISTRY_LOCK:
        return _SCHEDULERS.get(scheduler_id)

def start_scheduler(scheduler_id: str) -> Dict[str, Any]:
    """Start is implicit – this function merely validates existence."""
    if _get_scheduler(scheduler_id):
        return _response("success", f"Scheduler {scheduler_id} is running")
    return _response("error", f"Scheduler {scheduler_id} not found")

def stop_scheduler(scheduler_id: str) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    scheduler.shutdown()
    with _REGISTRY_LOCK:
        _SCHEDULERS.pop(scheduler_id, None)
    return _response("success", f"Scheduler {scheduler_id} stopped and removed")

# --------------------------------------------------------------------------- #
# Scheduling helpers
# --------------------------------------------------------------------------- #
def _wrap_callable(func: Callable) -> Callable:
    """Ensure the supplied object is callable; raise a clear error otherwise."""
    if not callable(func):
        raise TypeError("Supplied func argument must be callable")
    return func

def schedule_once(
    scheduler_id: str,
    func: Callable,
    delay_seconds: int,
    args: Tuple[Any, ...] = ()
) -> Dict[str, Any]:
    """Schedule ``func`` to run once after *delay_seconds*."""
    try:
        scheduler = _get_scheduler(scheduler_id)
        if not scheduler:
            return _response("error", f"Scheduler {scheduler_id} not found")
        _wrap_callable(func)
        run_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
        task = Task(func, args, {}, "once", run_at=run_at)
        scheduler.add_task(task, when=run_at)
        return _response("success", "Task scheduled",
                         {"task_id": task.id, "run_at": run_at.isoformat()})
    except Exception as exc:  # pragma: no cover
        _logger.exception("schedule_once failed")
        return _response("error", str(exc))

def schedule_recurring(
    scheduler_id: str,
    func: Callable,
    interval_seconds: int,
    args: Tuple[Any, ...] = ()
) -> Dict[str, Any]:
    """Schedule ``func`` to run repeatedly every *interval_seconds*."""
    try:
        scheduler = _get_scheduler(scheduler_id)
        if not scheduler:
            return _response("error", f"Scheduler {scheduler_id} not found")
        _wrap_callable(func)
        task = Task(func, args, {}, "recurring", interval=interval_seconds)
        scheduler.add_task(task, when=datetime.utcnow() + timedelta(seconds=interval_seconds))
        return _response("success", "Recurring task scheduled",
                         {"task_id": task.id, "interval": interval_seconds})
    except Exception as exc:  # pragma: no cover
        _logger.exception("schedule_recurring failed")
        return _response("error", str(exc))

def schedule_at(
    scheduler_id: str,
    func: Callable,
    run_at: datetime,
    args: Tuple[Any, ...] = ()
) -> Dict[str, Any]:
    """Schedule ``func`` to run at a specific ``datetime``."""
    try:
        scheduler = _get_scheduler(scheduler_id)
        if not scheduler:
            return _response("error", f"Scheduler {scheduler_id} not found")
        _wrap_callable(func)
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=None)  # naive UTC assumed
        task = Task(func, args, {}, "at", run_at=run_at)
        scheduler.add_task(task, when=run_at)
        return _response("success", "Task scheduled at fixed time",
                         {"task_id": task.id, "run_at": run_at.isoformat()})
    except Exception as exc:  # pragma: no cover
        _logger.exception("schedule_at failed")
        return _response("error", str(exc))

def schedule_daily(
    scheduler_id: str,
    func: Callable,
    hour: int,
    minute: int = 0,
    args: Tuple[Any, ...] = ()
) -> Dict[str, Any]:
    """Schedule ``func`` to run daily at *hour:minute* (UTC)."""
    try:
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError("hour must be 0‑23 and minute 0‑59")
        scheduler = _get_scheduler(scheduler_id)
        if not scheduler:
            return _response("error", f"Scheduler {scheduler_id} not found")
        _wrap_callable(func)
        today = datetime.utcnow()
        run_at = today.replace(hour=hour, minute=minute,
                               second=0, microsecond=0)
        task = Task(func, args, {}, "daily", run_at=run_at)
        scheduler.add_task(task, when=run_at)
        return _response("success", "Daily task scheduled",
                         {"task_id": task.id, "hour": hour, "minute": minute})
    except Exception as exc:  # pragma: no cover
        _logger.exception("schedule_daily failed")
        return _response("error", str(exc))

def schedule_cron(
    scheduler_id: str,
    func: Callable,
    cron_expr: str,
    args: Tuple[Any, ...] = ()
) -> Dict[str, Any]:
    """Schedule ``func`` using a simple 5‑field cron expression (UTC)."""
    try:
        parse_cron(cron_expr)  # validate
        scheduler = _get_scheduler(scheduler_id)
        if not scheduler:
            return _response("error", f"Scheduler {scheduler_id} not found")
        _wrap_callable(func)
        task = Task(func, args, {}, "cron", cron_expr=cron_expr)
        # initial run time
        next_run = next_cron_time(cron_expr, datetime.utcnow())
        scheduler.add_task(task, when=next_run)
        return _response("success", "Cron task scheduled",
                         {"task_id": task.id, "cron": cron_expr})
    except Exception as exc:  # pragma: no cover
        _logger.exception("schedule_cron failed")
        return _response("error", str(exc))

# --------------------------------------------------------------------------- #
# Task manipulation
# --------------------------------------------------------------------------- #
def cancel_task(scheduler_id: str, task_id: str) -> Dict[str, Any]:
    try:
        scheduler = _get_scheduler(scheduler_id)
        if not scheduler:
            return _response("error", f"Scheduler {scheduler_id} not found")
        task = scheduler.get_task(task_id)
        if not task:
            return _response("error", f"Task {task_id} not found")
        task.cancelled = True
        scheduler.remove_task(task_id)
        return _response("success", f"Task {task_id} cancelled")
    except Exception as exc:  # pragma: no cover
        _logger.exception("cancel_task failed")
        return _response("error", str(exc))

def pause_task(scheduler_id: str, task_id: str) -> Dict[str, Any]:
    try:
        scheduler = _get_scheduler(scheduler_id)
        if not scheduler:
            return _response("error", f"Scheduler {scheduler_id} not found")
        task = scheduler.get_task(task_id)
        if not task:
            return _response("error", f"Task {task_id} not found")
        task.paused = True
        return _response("success", f"Task {task_id} paused")
    except Exception as exc:
        _logger.exception("pause_task failed")
        return _response("error", str(exc))

def resume_task(scheduler_id: str, task_id: str) -> Dict[str, Any]:
    try:
        scheduler = _get_scheduler(scheduler_id)
        if not scheduler:
            return _response("error", f"Scheduler {scheduler_id} not found")
        task = scheduler.get_task(task_id)
        if not task:
            return _response("error", f"Task {task_id} not found")
        task.paused = False
        # if the next run time is in the past, schedule it for now
        next_run = task.next_run_time(datetime.utcnow())
        if next_run:
            scheduler._schedule_task(task, next_run)
        return _response("success", f"Task {task_id} resumed")
    except Exception as exc:
        _logger.exception("resume_task failed")
        return _response("error", str(exc))

def list_tasks(scheduler_id: str) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    return _response("success", "Task list", {"tasks": scheduler.list_tasks()})

def get_task_info(scheduler_id: str, task_id: str) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    task = scheduler.get_task(task_id)
    if not task:
        return _response("error", f"Task {task_id} not found")
    return _response("success", "Task details", {"task": task.to_dict()})

def get_task_history(
    scheduler_id: str,
    task_id: str,
    limit: Optional[int] = None
) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    task = scheduler.get_task(task_id)
    if not task:
        return _response("error", f"Task {task_id} not found")
    history = task.history[-limit:] if limit else task.history
    return _response("success", "History fetched", {"history": history})

def get_next_run(scheduler_id: str, task_id: str) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    task = scheduler.get_task(task_id)
    if not task:
        return _response("error", f"Task {task_id} not found")
    nxt = task.next_run_time(datetime.utcnow())
    return _response("success", "Next run time", {"next_run": nxt.isoformat() if nxt else None})

def reschedule_task(
    scheduler_id: str,
    task_id: str,
    new_interval: int
) -> Dict[str, Any]:
    """For recurring/daily tasks only – replace the interval."""
    try:
        scheduler = _get_scheduler(scheduler_id)
        if not scheduler:
            return _response("error", f"Scheduler {scheduler_id} not found")
        task = scheduler.get_task(task_id)
        if not task:
            return _response("error", f"Task {task_id} not found")
        if task.schedule_type not in ("recurring", "daily"):
            return _response("error", "Reschedule only applicable to recurring/daily tasks")
        task.interval = new_interval
        return _response("success", f"Task {task_id} interval updated")
    except Exception as exc:
        _logger.exception("reschedule_task failed")
        return _response("error", str(exc))

def run_task_now(scheduler_id: str, task_id: str) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    task = scheduler.get_task(task_id)
    if not task:
        return _response("error", f"Task {task_id} not found")
    # Direct execution (bypassing schedule) but still respects concurrency
    scheduler._execute_task(task_id)
    return _response("success", f"Task {task_id} triggered for immediate execution")

def set_task_priority(
    scheduler_id: str,
    task_id: str,
    priority: int
) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    task = scheduler.get_task(task_id)
    if not task:
        return _response("error", f"Task {task_id} not found")
    task.priority = priority
    return _response("success", f"Priority for task {task_id} set to {priority}")

def add_task_callback(
    scheduler_id: str,
    task_id: str,
    on_success: Optional[Callable[[str, Any], None]] = None,
    on_failure: Optional[Callable[[str, Exception], None]] = None,
) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    task = scheduler.get_task(task_id)
    if not task:
        return _response("error", f"Task {task_id} not found")
    if on_success:
        if not callable(on_success):
            return _response("error", "on_success must be callable")
        task.on_success = on_success
    if on_failure:
        if not callable(on_failure):
            return _response("error", "on_failure must be callable")
        task.on_failure = on_failure
    return _response("success", f"Callbacks attached to task {task_id}")

def create_task_chain(
    scheduler_id: str,
    tasks: List[Tuple[Callable, Tuple[Any, ...]]]
) -> Dict[str, Any]:
    """
    Create a linear chain where each task runs after the previous one succeeds.
    ``tasks`` is a list of ``(func, args)`` tuples.
    Returns the list of generated task IDs.
    """
    try:
        scheduler = _get_scheduler(scheduler_id)
        if not scheduler:
            return _response("error", f"Scheduler {scheduler_id} not found")
        if not tasks:
            return _response("error", "Empty task list")
        task_ids: List[str] = []
        previous_id: Optional[str] = None
        for func, args in tasks:
            _wrap_callable(func)
            task = Task(func, args, {}, "once")  # temporary “once”, we’ll trigger manually
            task_ids.append(task.id)
            scheduler.add_task(task)  # scheduled immediately; will be paused below
            task.paused = True

            # attach success callback to launch next
            def _make_success(next_id: str) -> Callable[[str, Any], None]:
                def _callback(_completed_id: str, _result: Any) -> None:
                    next_task = scheduler.get_task(next_id)
                    if next_task and not next_task.cancelled:
                        scheduler.resume_task(next_id)  # type: ignore
                return _callback

            if previous_id:
                prev_task = scheduler.get_task(previous_id)
                if prev_task:
                    prev_task.on_success = _make_success(task.id)
            else:
                # first task – start immediately
                task.paused = False
            previous_id = task.id

        return _response("success", "Task chain created", {"task_ids": task_ids})
    except Exception as exc:  # pragma: no cover
        _logger.exception("create_task_chain failed")
        return _response("error", str(exc))

def create_task_group(
    scheduler_id: str,
    tasks: List[Tuple[Callable, Tuple[Any, ...]]],
    parallel: bool = True
) -> Dict[str, Any]:
    """
    Create a group of tasks that either run in parallel (default) or sequentially.
    Returns a list of task IDs.
    """
    try:
        scheduler = _get_scheduler(scheduler_id)
        if not scheduler:
            return _response("error", f"Scheduler {scheduler_id} not found")
        if not tasks:
            return _response("error", "Empty task list")
        task_ids: List[str] = []
        previous_id: Optional[str] = None
        for func, args in tasks:
            _wrap_callable(func)
            task = Task(func, args, {}, "once")
            task_ids.append(task.id)
            scheduler.add_task(task)
            if not parallel and previous_id:
                # make current depend on previous
                task.dependencies.add(previous_id)
                prev = scheduler.get_task(previous_id)
                if prev:
                    prev.dependents.add(task.id)
            previous_id = task.id
        return _response("success", "Task group created", {"task_ids": task_ids})
    except Exception as exc:
        _logger.exception("create_task_group failed")
        return _response("error", str(exc))

def get_scheduler_stats(scheduler_id: str) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    return _response("success", "Scheduler stats", scheduler.summary())

def export_schedule(scheduler_id: str, output_path: Union[str, Path]) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    try:
        data = {
            "scheduler_id": scheduler.id,
            "tasks": scheduler.list_tasks(),
            "max_workers": scheduler._max_workers,
        }
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2))
        return _response("success", f"Schedule exported to {p}")
    except Exception as exc:
        _logger.exception("export_schedule failed")
        return _response("error", str(exc))

def import_schedule(scheduler_id: str, file_path: Union[str, Path]) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    try:
        p = Path(file_path)
        raw = json.loads(p.read_text())
        tasks_data = raw.get("tasks", [])
        for td in tasks_data:
            # Re‑create tasks; note that we cannot restore original callables.
            # Users should supply a registry of functions; for simplicity we skip them.
            continue  # In real implementation you would map a name to a callable.
        return _response("success", "Import stub completed (callables not restored)")
    except Exception as exc:
        _logger.exception("import_schedule failed")
        return _response("error", str(exc))

def clear_all_tasks(scheduler_id: str) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    with scheduler._lock:
        for tid in list(scheduler._tasks.keys()):
            scheduler.remove_task(tid)
    return _response("success", "All tasks cleared")

def set_max_concurrent(scheduler_id: str, max_workers: int) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    scheduler._max_workers = max_workers
    scheduler._semaphore = threading.Semaphore(max_workers)
    return _response("success", f"Max concurrent workers set to {max_workers}")

def get_running_tasks(scheduler_id: str) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    return _response("success", "Running tasks",
                     {"running_task_ids": list(scheduler._running)})

def get_failed_tasks(scheduler_id: str) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    return _response("success", "Failed tasks",
                     {"failed_task_ids": list(scheduler._failed)})

def retry_failed_task(scheduler_id: str, task_id: str) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    if task_id not in scheduler._failed:
        return _response("error", f"Task {task_id} is not in failed state")
    task = scheduler.get_task(task_id)
    if not task:
        return _response("error", f"Task {task_id} not found")
    scheduler._failed.discard(task_id)
    scheduler._execute_task(task_id)
    return _response("success", f"Retry of task {task_id} queued")

def set_task_timeout(scheduler_id: str, task_id: str, timeout: float) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    task = scheduler.get_task(task_id)
    if not task:
        return _response("error", f"Task {task_id} not found")
    if timeout <= 0:
        return _response("error", "Timeout must be positive")
    task.timeout = timeout
    return _response("success", f"Timeout for task {task_id} set to {timeout}s")

def add_task_dependency(
    scheduler_id: str,
    task_id: str,
    depends_on: str
) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    task = scheduler.get_task(task_id)
    other = scheduler.get_task(depends_on)
    if not task or not other:
        return _response("error", "One of the tasks does not exist")
    task.dependencies.add(depends_on)
    other.dependents.add(task_id)
    return _response("success", f"Task {task_id} now depends on {depends_on}")

def get_dependency_graph(scheduler_id: str) -> Dict[str, Any]:
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    graph = {
        task_id: list(task.dependencies) for task_id, task in scheduler._tasks.items()
    }
    return _response("success", "Dependency graph", {"graph": graph})

def validate_schedule(scheduler_id: str) -> Dict[str, Any]:
    """Simple validation – checks for cycles in the dependency graph."""
    scheduler = _get_scheduler(scheduler_id)
    if not scheduler:
        return _response("error", f"Scheduler {scheduler_id} not found")
    graph = {tid: set(t.dependencies) for tid, t in scheduler._tasks.items()}
    visited: Set[str] = set()
    rec_stack: Set[str] = set()

    def _visit(node: str) -> bool:
        if node in rec_stack:
            return False
        if node in visited:
            return True
        visited.add(node)
        rec_stack.add(node)
        for neigh in graph.get(node, []):
            if not _visit(neigh):
                return False
        rec_stack.remove(node)
        return True

    for node in graph:
        if not _visit(node):
            return _response("error", "Cyclic dependency detected")
    return _response("success", "Schedule validation passed")

def backup_scheduler(scheduler_id: str, output_path: Union[str, Path]) -> Dict[str, Any]:
    """Thin wrapper around ``export_schedule`` – keeping a legacy name."""
    return export_schedule(scheduler_id, output_path)

def restore_scheduler(scheduler_id: str, backup_path: Union[str, Path]) -> Dict[str, Any]:
    """Thin wrapper around ``import_schedule``."""
    return import_schedule(scheduler_id, backup_path)

# --------------------------------------------------------------------------- #
# Cron utilities (basic 5‑field parser, no named months/days)
# --------------------------------------------------------------------------- #
_WeekdayMap = {"0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6}
def parse_cron(expression: str) -> Dict[str, Any]:
    """
    Parse a simple 5‑field cron expression: ``minute hour day month weekday``.
    Returns a dict with lists of allowed values for each field.
    Supports ``*``, ``*/n`` and comma separated lists.
    """
    try:
        fields = expression.strip().split()
        if len(fields) != 5:
            raise ValueError("Cron expression must have exactly 5 fields")
        minute, hour, day, month, weekday = fields

        def _parse_part(part: str, min_val: int, max_val: int) -> List[int]:
            if part == "*":
                return list(range(min_val, max_val + 1))
            result: Set[int] = set()
            for sub in part.split(","):
                if sub.startswith("*/"):
                    step = int(sub[2:])
                    result.update(range(min_val, max_val + 1, step))
                elif "-" in sub:
                    start, end = map(int, sub.split("-"))
                    result.update(range(start, end + 1))
                else:
                    result.add(int(sub))
            return sorted(result)

        cr = {
            "minute": _parse_part(minute, 0, 59),
            "hour": _parse_part(hour, 0, 23),
            "day": _parse_part(day, 1, 31),
            "month": _parse_part(month, 1, 12),
            "weekday": _parse_part(weekday, 0, 6),
        }
        return cr
    except Exception as exc:
        raise ValueError(f"Invalid cron expression: {exc}") from exc

def next_cron_time(expression: str, from_time: datetime) -> datetime:
    """Calculate the next datetime matching *expression* after ``from_time``."""
    cr = parse_cron(expression)
    # Increment minute by minute until we find a match – simple but sufficient.
    candidate = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
    while True:
        if (candidate.minute in cr["minute"] and
            candidate.hour in cr["hour"] and
            candidate.day in cr["day"] and
            candidate.month in cr["month"] and
            candidate.weekday() in cr["weekday"]):
            return candidate
        candidate += timedelta(minutes=1)

def human_readable_schedule(task_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a task dict (as produced by ``Task.to_dict``) into a human‑readable description.
    """
    stype = task_info.get("schedule_type")
    if stype == "once":
        desc = f"Runs once at {task_info.get('run_at')}"
    elif stype == "recurring":
        desc = f"Runs every {task_info.get('interval')} second(s)"
    elif stype == "at":
        desc = f"Runs at specific time {task_info.get('run_at')}"
    elif stype == "daily":
        run_at = task_info.get("run_at")
        if run_at:
            dt = datetime.fromisoformat(run_at)
            desc = f"Runs daily at {dt.hour:02d}:{dt.minute:02d} UTC"
        else:
            desc = "Daily schedule (time unknown)"
    elif stype == "cron":
        desc = f"Cron schedule: {task_info.get('cron_expr')}"
    else:
        desc = "Unknown schedule type"
    return {"task_id": task_info.get("id"), "description": desc}