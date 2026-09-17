"""Job dispatcher for screen_agent toolkit — SQLite-backed durable job queue.

Allows OpenClaw (or any client) to:
  1. Submit a toolkit tool call as a background job → returns job_id
  2. Poll job status / result by job_id
  3. List jobs (filter by status)
  4. Cancel a pending job
  5. Clean up old completed jobs

Jobs are executed sequentially by a worker thread. Each job wraps
``registry.call_tool(tool_name, kwargs)`` and stores the result.

Usage (CLI):
    python job_dispatcher.py submit --tool system_monitor.get_cpu_usage --params '{}'
    python job_dispatcher.py status --job-id <uuid>
    python job_dispatcher.py list --status pending
    python job_dispatcher.py cancel --job-id <uuid>
    python job_dispatcher.py worker-start   # starts background worker thread
    python job_dispatcher.py health

OpenClaw integration:
    Use ``JobDispatcher`` directly:
        from job_dispatcher import JobDispatcher
        d = JobDispatcher()
        job_id = d.submit("system_monitor.get_cpu_usage", {})
        result = d.wait_for_result(job_id, timeout_sec=30)
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "job_queue.db"
WORKER_POLL_SEC = 2
DEFAULT_TIMEOUT_SEC = 300  # 5 minutes max per job


# ---------------------------------------------------------------------------
# SQLite-backed job store
# ---------------------------------------------------------------------------

class JobStore:
    """Thread-safe SQLite store for jobs."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                tool_name TEXT NOT NULL,
                params_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                submitted_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                result_json TEXT,
                error TEXT,
                notify_topic TEXT
            )""")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_submitted ON jobs(submitted_at DESC)"
            )

    def add_job(self, job_id: str, tool_name: str, params: dict, notify_topic: str | None = None) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                """INSERT INTO jobs (id, tool_name, params_json, status, submitted_at, notify_topic)
                   VALUES (?, ?, ?, 'pending', ?, ?)""",
                (job_id, tool_name, json.dumps(params), datetime.now().isoformat(), notify_topic),
            )

    def get_job(self, job_id: str) -> dict | None:
        with self._lock, self._conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            return dict(row) if row else None

    def update_job_running(self, job_id: str) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET status='running', started_at=? WHERE id=?",
                (datetime.now().isoformat(), job_id),
            )

    def update_job_completed(self, job_id: str, result: dict) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                """UPDATE jobs SET status='completed', completed_at=?, result_json=? WHERE id=?""",
                (datetime.now().isoformat(), json.dumps(result), job_id),
            )

    def update_job_failed(self, job_id: str, error: str) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                """UPDATE jobs SET status='failed', completed_at=?, error=? WHERE id=?""",
                (datetime.now().isoformat(), error, job_id),
            )

    def cancel_job(self, job_id: str) -> bool:
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                "UPDATE jobs SET status='cancelled' WHERE id=? AND status='pending'",
                (job_id,),
            )
            return cur.rowcount > 0

    def list_jobs(self, status: str | None = None, limit: int = 50) -> list[dict]:
        with self._lock, self._conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE status=? ORDER BY submitted_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY submitted_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    def purge_old(self, older_than_hours: int = 24) -> int:
        cutoff = (datetime.now() - timedelta(hours=older_than_hours)).isoformat()
        with self._lock, self._conn() as conn:
            cur = conn.execute(
                """DELETE FROM jobs
                   WHERE status IN ('completed', 'failed', 'cancelled')
                   AND submitted_at < ?""",
                (cutoff,),
            )
            return cur.rowcount

    def get_pending_count(self) -> int:
        with self._lock, self._conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status='pending'"
            ).fetchone()[0]

    def get_next_pending(self) -> dict | None:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE status='pending' ORDER BY submitted_at ASC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None


# ---------------------------------------------------------------------------
# JobDispatcher — public API
# ---------------------------------------------------------------------------

class JobDispatcher:
    """Submit, track, and retrieve results from screen_agent toolkit jobs."""

    def __init__(self, db_path: Path = DB_PATH, max_workers: int = 1):
        self.store = JobStore(db_path)
        self.max_workers = max_workers
        self._worker_thread: threading.Thread | None = None
        self._worker_running = False
        self._current_job: str | None = None

    def submit(self, tool_name: str, params: dict | None = None, notify_topic: str | None = None) -> str:
        """Submit a job. Returns job_id."""
        job_id = str(uuid.uuid4())
        self.store.add_job(job_id, tool_name, params or {}, notify_topic)
        logger.info("Submitted job %s: %s", job_id[:8], tool_name)
        return job_id

    def status(self, job_id: str) -> dict:
        """Get job status + result if completed."""
        job = self.store.get_job(job_id)
        if not job:
            return {"success": False, "error": f"Job {job_id} not found", "job_id": job_id}
        result = {
            "success": True,
            "job_id": job["id"],
            "tool_name": job["tool_name"],
            "status": job["status"],
            "submitted_at": job["submitted_at"],
            "started_at": job["started_at"],
            "completed_at": job["completed_at"],
        }
        if job["result_json"]:
            try:
                result["result"] = json.loads(job["result_json"])
            except Exception:
                result["result_raw"] = job["result_json"]
        if job["error"]:
            result["error"] = job["error"]
        return result

    def wait_for_result(self, job_id: str, timeout_sec: int = DEFAULT_TIMEOUT_SEC) -> dict:
        """Block until job completes or times out. Returns status dict."""
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            s = self.status(job_id)
            if not s.get("success"):
                return s
            st = s.get("status")
            if st in ("completed", "failed", "cancelled"):
                return s
            time.sleep(1)
        return {"success": False, "job_id": job_id, "error": "timeout", "status": "running"}

    def list_jobs(self, status: str | None = None, limit: int = 50) -> list[dict]:
        return self.store.list_jobs(status, limit)

    def cancel(self, job_id: str) -> dict:
        ok = self.store.cancel_job(job_id)
        return {
            "success": ok,
            "job_id": job_id,
            "cancelled": ok,
            "error": None if ok else "Job not pending or not found",
        }

    def purge(self, older_than_hours: int = 24) -> dict:
        n = self.store.purge_old(older_than_hours)
        return {"success": True, "purged": n}

    def health(self) -> dict:
        pending = self.store.get_pending_count()
        recent = self.store.list_jobs(limit=5)
        return {
            "ok": True,
            "pending_jobs": pending,
            "worker_running": self._worker_running,
            "current_job": self._current_job,
            "recent_jobs": [
                {"job_id": j["id"][:8], "tool": j["tool_name"], "status": j["status"]}
                for j in recent
            ],
        }

    # -- Worker

    def start_worker(self) -> None:
        """Start the background worker thread (idempotent)."""
        if self._worker_running:
            return
        self._worker_running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("Worker started")

    def stop_worker(self) -> None:
        self._worker_running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        logger.info("Worker stopped")

    def _worker_loop(self) -> None:
        while self._worker_running:
            try:
                job = self.store.get_next_pending()
                if not job:
                    time.sleep(WORKER_POLL_SEC)
                    continue
                self._process_job(job)
            except Exception as e:
                logger.exception("Worker loop error: %s", e)
                time.sleep(WORKER_POLL_SEC)

    def _process_job(self, job: dict) -> None:
        job_id = job["id"]
        tool_name = job["tool_name"]
        self._current_job = job_id[:8]
        try:
            params = json.loads(job["params_json"]) if job["params_json"] else {}
        except Exception:
            params = {}
        self.store.update_job_running(job_id)
        logger.info("Processing job %s: %s", job_id[:8], tool_name)
        try:
            from toolkit.registry import get_registry
            reg = get_registry()
            result = reg.call_tool(tool_name, params)
            self.store.update_job_completed(job_id, result)
            logger.info("Completed job %s", job_id[:8])
        except Exception as e:
            self.store.update_job_failed(job_id, str(e))
            logger.error("Failed job %s: %s", job_id[:8], e)
        finally:
            self._current_job = None


# ---------------------------------------------------------------------------
# OpenClaw dispatch interface (same envelope as other bridges)
# ---------------------------------------------------------------------------

OPENCLAW_COMMANDS: dict[str, str] = {
    "health": "Dispatcher + queue health check",
    "submit": "Submit a toolkit job (params: tool_name, params_json, notify_topic)",
    "status": "Get job status + result (params: job_id)",
    "wait": "Block until job done (params: job_id, timeout_sec=300)",
    "list": "List jobs (params: status=NULL, limit=50)",
    "cancel": "Cancel pending job (params: job_id)",
    "purge": "Delete old finished jobs (params: older_than_hours=24)",
    "worker_start": "Start background worker thread",
    "worker_stop": "Stop background worker thread",
    "toolkit_stats": "Delegates to screen_agent registry stats",
    "toolkit_list": "List toolkit tools (params: category=NULL, limit=50)",
    "toolkit_search": "Search tools (params: query)",
}

_HANDLERS: dict[str, Any] = {}


def _err(command: str, message: str) -> dict[str, Any]:
    return {"success": False, "command": command, "data": None, "error": message}


def _get_dispatcher() -> JobDispatcher:
    return JobDispatcher()


def _cmd_health(_params: dict) -> dict:
    d = _get_dispatcher()
    return d.health()


def _cmd_submit(params: dict) -> dict:
    tool_name = str(params.get("tool_name", "")).strip()
    if not tool_name:
        raise ValueError("tool_name is required")
    params_json = params.get("params_json", {})
    if isinstance(params_json, str):
        params_json = json.loads(params_json)
    notify_topic = params.get("notify_topic")
    d = _get_dispatcher()
    job_id = d.submit(tool_name, params_json, notify_topic)
    return {"job_id": job_id, "tool_name": tool_name, "status": "pending"}


def _cmd_status(params: dict) -> dict:
    job_id = str(params.get("job_id", "")).strip()
    if not job_id:
        raise ValueError("job_id is required")
    d = _get_dispatcher()
    return d.status(job_id)


def _cmd_wait(params: dict) -> dict:
    job_id = str(params.get("job_id", "")).strip()
    if not job_id:
        raise ValueError("job_id is required")
    timeout = int(params.get("timeout_sec", DEFAULT_TIMEOUT_SEC))
    d = _get_dispatcher()
    return d.wait_for_result(job_id, timeout_sec=timeout)


def _cmd_list(params: dict) -> dict:
    d = _get_dispatcher()
    status = params.get("status") or None
    limit = int(params.get("limit", 50))
    return {"jobs": d.list_jobs(status=status, limit=limit)}


def _cmd_cancel(params: dict) -> dict:
    job_id = str(params.get("job_id", "")).strip()
    if not job_id:
        raise ValueError("job_id is required")
    d = _get_dispatcher()
    return d.cancel(job_id)


def _cmd_purge(params: dict) -> dict:
    hours = int(params.get("older_than_hours", 24))
    d = _get_dispatcher()
    return d.purge(hours)


def _cmd_worker_start(_params: dict) -> dict:
    d = _get_dispatcher()
    d.start_worker()
    return {"status": "worker started", "running": True}


def _cmd_worker_stop(_params: dict) -> dict:
    d = _get_dispatcher()
    d.stop_worker()
    return {"status": "worker stopped", "running": False}


def _cmd_toolkit_list(params: dict) -> dict:
    from toolkit.registry import get_registry
    reg = get_registry()
    category = params.get("category") or None
    limit = int(params.get("limit", 50))
    tools = reg.list_tools(category=category)
    return {"total": len(tools), "returned": min(limit, len(tools)), "tools": tools[:limit]}


def _cmd_toolkit_search(params: dict) -> dict:
    from toolkit.registry import get_registry
    reg = get_registry()
    query = str(params.get("query", "")).strip()
    if not query:
        raise ValueError("query is required")
    results = reg.search_tools(query)
    return {"query": query, "results": results[:20]}


def _cmd_toolkit_stats(_params: dict) -> dict:
    from toolkit.registry import get_registry
    reg = get_registry()
    return reg.get_stats()


# Build handler map
_HANDLERS = {
    "health": _cmd_health,
    "submit": _cmd_submit,
    "status": _cmd_status,
    "wait": _cmd_wait,
    "list": _cmd_list,
    "cancel": _cmd_cancel,
    "purge": _cmd_purge,
    "worker_start": _cmd_worker_start,
    "worker_stop": _cmd_worker_stop,
    "toolkit_stats": _cmd_toolkit_stats,
    "toolkit_list": _cmd_toolkit_list,
    "toolkit_search": _cmd_toolkit_search,
}


def dispatch(command: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    p = params or {}
    try:
        handler = _HANDLERS.get(command)
        if not handler:
            return _err(
                command,
                f"Unknown command: {command}. Available: {', '.join(OPENCLAW_COMMANDS)}",
            )
        data = handler(p)
        return {"success": True, "command": command, "data": data}
    except Exception as e:
        logger.exception("JobDispatcher dispatch error for %s", command)
        return _err(command, str(e))


def generate_openclaw_shell_snippet() -> dict[str, Any]:
    root = str(Path(__file__).resolve().parent)
    py = "python"  # toolkit modules require being in the screen_agent dir
    invoke = f'cd /d "{root}" && {py} job_dispatcher.py dispatch --cmd <command> --params \'<json>\''
    return {
        "project_dir": root,
        "python": py,
        "example_invoke_windows": invoke,
        "job_commands": {
            "submit": "submit",
            "check_status": "status",
            "wait_for_result": "wait",
            "list_all": "list",
            "cancel_job": "cancel",
        },
        "worker_commands": {
            "start_worker": "worker_start",
            "stop_worker": "worker_stop",
        },
        "toolkit_commands": {
            "stats": "toolkit_stats",
            "list_tools": "toolkit_list",
            "search_tools": "toolkit_search",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="screen-agent-dispatcher — job queue for toolkit calls")
    sub = parser.add_subparsers(dest="verb", required=True)

    p_h = sub.add_parser("health", help="Dispatcher health")
    p_c = sub.add_parser("config", help="OpenClaw wiring JSON")
    p_w = sub.add_parser("worker-start", help="Start background worker")
    p_wo = sub.add_parser("worker-stop", help="Stop background worker")

    p_d = sub.add_parser("dispatch", help="Run one command")
    p_d.add_argument("--cmd", required=True)
    p_d.add_argument("--params", default="{}")

    p_s = sub.add_parser("submit", help="Submit a toolkit job")
    p_s.add_argument("--tool", required=True)
    p_s.add_argument("--params", default="{}")

    p_st = sub.add_parser("status", help="Check job status")
    p_st.add_argument("--job-id", required=True)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.verb == "health":
        d = JobDispatcher()
        print(json.dumps(d.health(), indent=2))
        return 0
    if args.verb == "config":
        print(json.dumps(generate_openclaw_shell_snippet(), indent=2))
        return 0
    if args.verb == "worker-start":
        d = JobDispatcher()
        d.start_worker()
        print("Worker started. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            d.stop_worker()
        return 0
    if args.verb == "worker-stop":
        # Worker runs in-process; stopping means nothing to do here
        print("Note: worker runs in-process. Stop the process to stop the worker.")
        return 0
    if args.verb == "submit":
        params = json.loads(args.params)
        d = JobDispatcher()
        jid = d.submit(args.tool, params)
        print(json.dumps({"job_id": jid}, indent=2))
        return 0
    if args.verb == "status":
        d = JobDispatcher()
        print(json.dumps(d.status(args.job_id), indent=2, default=str))
        return 0
    if args.verb == "dispatch":
        params = json.loads(args.params)
        result = dispatch(args.cmd, params)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("success") else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
