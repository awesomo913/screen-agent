"""
notification_service.py
Screen Agent Toolkit - Production Notification Service
Uses: plyer, win10toast, smtplib, requests, json, threading, queue, time
"""

import os
import time
import json
import queue
import threading
import logging
import requests
import smtplib
from email.mime.text import MIMEText
from typing import Dict, Any, Callable, List, Optional
from datetime import datetime
from collections import deque

# -----------------------------------------------------------------------------
# Import Dependencies (Graceful Fallbacks for Environments)
# -----------------------------------------------------------------------------
try:
    from plyer import notification as plyer_notification
except ImportError:
    plyer_notification = None

try:
    import win10toast
except ImportError:
    win10toast = None

# -----------------------------------------------------------------------------
# Module-Level Thread-Safe State
# -----------------------------------------------------------------------------
_notification_queue = queue.Queue()
_notification_history: List[Dict[str, Any]] = []
_history_lock = threading.Lock()

_callbacks: Dict[str, Callable] = {}
_alert_rules: List[Dict[str, Any]] = []
_rules_lock = threading.Lock()

_rate_limit_lock = threading.Lock()
_rate_limit_timestamps = deque()
_rate_limit_max = 10

_templates: Dict[str, Dict[str, str]] = {}

_stats_lock = threading.Lock()
_stats = {
    "total_sent": 0,
    "total_failed": 0,
    "channels": {},
    "last_updated": None
}

_DEFAULT_LOG_PATH = "notification_service.log"
_logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Internal Helpers
# -----------------------------------------------------------------------------

def _check_rate_limit_internal() -> Dict[str, Any]:
    """Internal thread-safe rate limit checker."""
    with _rate_limit_lock:
        now = time.time()
        while _rate_limit_timestamps and _rate_limit_timestamps[0] < now - 60:
            _rate_limit_timestamps.popleft()
        if len(_rate_limit_timestamps) >= _rate_limit_max:
            wait_time = round(60 - (now - _rate_limit_timestamps[0]), 2)
            return {"success": False, "data": {"wait_seconds": wait_time}}
        _rate_limit_timestamps.append(now)
        return {"success": True}

def _record_history(record: Dict[str, Any]) -> None:
    """Append to in-memory history safely."""
    with _history_lock:
        _notification_history.append(record)
        if len(_notification_history) > 1000:
            _notification_history = _notification_history[-500:]

def _update_stats(channel: str, success: bool) -> None:
    """Update thread-safe counters."""
    with _stats_lock:
        key = "total_sent" if success else "total_failed"
        _stats[key] = _stats.get(key, 0) + 1
        if channel not in _stats["channels"]:
            _stats["channels"][channel] = {"sent": 0, "failed": 0}
        sub_key = "sent" if success else "failed"
        _stats["channels"][channel][sub_key] += 1
        _stats["last_updated"] = datetime.now().isoformat()

def _invoke_callbacks(channel: str, payload: Dict[str, Any]) -> None:
    """Trigger registered callbacks for an event/channel."""
    for event, func in _callbacks.items():
        if event in (channel, "notify", "all"):
            try:
                func(channel, payload)
            except Exception as e:
                _logger.error(f"Callback execution failed for {event}: {e}")

# -----------------------------------------------------------------------------
# Public API Functions
# -----------------------------------------------------------------------------

def show_desktop_notification(title: str, message: str, timeout: int = 10) -> Dict[str, Any]:
    """Show a native desktop notification via plyer."""
    record = {"channel": "desktop", "timestamp": datetime.now().isoformat(), "title": title, "message": message}
    try:
        if plyer_notification is None:
            raise RuntimeError("plyer is not installed or not supported on this platform.")
        plyer_notification.notify(title=title, message=message, app_name="ScreenAgent", timeout=timeout)
        record["success"] = True
        _update_stats("desktop", True)
        return {"success": True, "message": "Desktop notification displayed", "data": record}
    except Exception as e:
        record["success"] = False
        record["error"] = str(e)
        _update_stats("desktop", False)
        return {"success": False, "message": "Failed to display desktop notification", "error": str(e)}

def show_toast_windows(title: str, message: str, duration: int = 5) -> Dict[str, Any]:
    """Show a Windows 10/11 toast notification via win10toast."""
    record = {"channel": "windows_toast", "timestamp": datetime.now().isoformat(), "title": title, "duration": duration}
    try:
        if win10toast is None:
            raise RuntimeError("win10toast is not installed or this is not a Windows environment.")
        toaster = win10toast.ToastNotifier()
        toaster.show_toast(title=title, msg=message, duration=duration, threaded=True)
        record["success"] = True
        _update_stats("windows_toast", True)
        return {"success": True, "message": "Windows toast queued", "data": record}
    except Exception as e:
        record["success"] = False
        record["error"] = str(e)
        _update_stats("windows_toast", False)
        return {"success": False, "message": "Failed to show Windows toast", "error": str(e)}

def send_email_notification(to: str, subject: str, body: str, smtp_host: str = "") -> Dict[str, Any]:
    """Send an email notification via SMTP."""
    record = {"channel": "email", "timestamp": datetime.now().isoformat(), "to": to, "subject": subject}
    try:
        host = smtp_host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USER")
        password = os.getenv("SMTP_PASS")
        if not user or not password:
            raise ValueError("SMTP_USER and SMTP_PASS environment variables must be set.")

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = user
        msg["To"] = to

        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, [to], msg.as_string())
        record["success"] = True
        _update_stats("email", True)
        return {"success": True, "message": "Email sent successfully", "data": record}
    except Exception as e:
        record["success"] = False
        record["error"] = str(e)
        _update_stats("email", False)
        return {"success": False, "message": "Failed to send email", "error": str(e)}

def send_slack_webhook(webhook_url: str, message: str, channel: str = "") -> Dict[str, Any]:
    """Send a message to Slack via Incoming Webhook."""
    record = {"channel": "slack", "timestamp": datetime.now().isoformat(), "url": webhook_url}
    try:
        payload = {"text": message}
        if channel:
            payload["channel"] = channel
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        record["success"] = True
        record["status"] = response.status_code
        _update_stats("slack", True)
        return {"success": True, "message": "Slack webhook sent", "data": record}
    except Exception as e:
        record["success"] = False
        record["error"] = str(e)
        _update_stats("slack", False)
        return {"success": False, "message": "Failed to send Slack webhook", "error": str(e)}

def send_discord_webhook(webhook_url: str, message: str, username: str = "") -> Dict[str, Any]:
    """Send a message to Discord via Webhook."""
    record = {"channel": "discord", "timestamp": datetime.now().isoformat(), "url": webhook_url}
    try:
        payload = {"content": message}
        if username:
            payload["username"] = username
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        record["success"] = True
        record["status"] = response.status_code
        _update_stats("discord", True)
        return {"success": True, "message": "Discord webhook sent", "data": record}
    except Exception as e:
        record["success"] = False
        record["error"] = str(e)
        _update_stats("discord", False)
        return {"success": False, "message": "Failed to send Discord webhook", "error": str(e)}

def send_telegram_message(bot_token: str, chat_id: str, message: str) -> Dict[str, Any]:
    """Send a message via Telegram Bot API."""
    record = {"channel": "telegram", "timestamp": datetime.now().isoformat(), "chat_id": chat_id}
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        record["success"] = True
        _update_stats("telegram", True)
        return {"success": True, "message": "Telegram message sent", "data": record}
    except Exception as e:
        record["success"] = False
        record["error"] = str(e)
        _update_stats("telegram", False)
        return {"success": False, "message": "Failed to send Telegram message", "error": str(e)}

def send_pushover(user_key: str, api_token: str, message: str) -> Dict[str, Any]:
    """Send a notification via Pushover API."""
    record = {"channel": "pushover", "timestamp": datetime.now().isoformat()}
    try:
        url = "https://api.pushover.net/1/messages.json"
        payload = {"user": user_key, "token": api_token, "message": message}
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        record["success"] = True
        _update_stats("pushover", True)
        return {"success": True, "message": "Pushover notification sent", "data": record}
    except Exception as e:
        record["success"] = False
        record["error"] = str(e)
        _update_stats("pushover", False)
        return {"success": False, "message": "Failed to send Pushover notification", "error": str(e)}

def schedule_notification(title: str, message: str, delay_seconds: int) -> Dict[str, Any]:
    """Schedule a desktop notification using a background thread."""
    record = {"channel": "desktop", "scheduled_at": datetime.now().isoformat(), "delay": delay_seconds}
    try:
        if delay_seconds < 0:
            raise ValueError("Delay must be non-negative.")
        def _delayed_task():
            show_desktop_notification(title, message)
        timer = threading.Timer(delay_seconds, _delayed_task)
        timer.daemon = True
        timer.start()
        record["execute_at"] = datetime.now().isoformat() if delay_seconds == 0 else (datetime.now() + datetime.timedelta(seconds=delay_seconds)).isoformat()
        return {"success": True, "message": "Notification scheduled", "data": record}
    except Exception as e:
        record["success"] = False
        record["error"] = str(e)
        return {"success": False, "message": "Failed to schedule notification", "error": str(e)}

def create_notification_queue() -> Dict[str, Any]:
    """Initialize or reset the internal notification queue."""
    global _notification_queue
    try:
        _notification_queue = queue.Queue()
        return {"success": True, "message": "Notification queue initialized", "data": {"type": "FIFO", "maxsize": 0}}
    except Exception as e:
        return {"success": False, "message": "Failed to initialize queue", "error": str(e)}

def add_to_queue(notification: dict) -> Dict[str, Any]:
    """Add a notification dict to the processing queue."""
    try:
        if not isinstance(notification, dict):
            raise TypeError("Notification must be a dictionary.")
        notification["queued_at"] = datetime.now().isoformat()
        _notification_queue.put(notification, block=False)
        return {"success": True, "message": "Notification queued", "data": {"queue_size": _notification_queue.qsize()}}
    except queue.Full:
        return {"success": False, "message": "Queue is full", "error": "QueueFull"}
    except Exception as e:
        return {"success": False, "message": "Failed to queue notification", "error": str(e)}

def process_queue(batch_size: int = 10) -> Dict[str, Any]:
    """Process up to `batch_size` queued notifications."""
    results = []
    processed = 0
    try:
        for _ in range(batch_size):
            if _notification_queue.empty():
                break
            notif = _notification_queue.get_nowait()
            ch = notif.get("channel", notif.get("type", "desktop"))
            
            rate_check = _check_rate_limit_internal()
            if not rate_check["success"]:
                results.append({"success": False, "message": "Rate limited", "data": rate_check.get("data")})
                processed += 1
                continue

            if ch == "desktop":
                res = show_desktop_notification(notif.get("title", "Alert"), notif.get("message", ""))
            elif ch == "email":
                res = send_email_notification(notif.get("to", ""), notif.get("subject", "Alert"), notif.get("body", notif.get("message", "")), notif.get("smtp_host", ""))
            elif ch == "slack":
                res = send_slack_webhook(notif.get("webhook_url", ""), notif.get("message", ""))
            elif ch == "discord":
                res = send_discord_webhook(notif.get("webhook_url", ""), notif.get("message", ""))
            elif ch == "telegram":
                res = send_telegram_message(notif.get("bot_token", ""), notif.get("chat_id", ""), notif.get("message", ""))
            elif ch == "pushover":
                res = send_pushover(notif.get("user_key", ""), notif.get("api_token", ""), notif.get("message", ""))
            elif ch == "webhook":
                res = send_webhook(notif.get("url", ""), notif)
            else:
                res = {"success": False, "message": f"Unsupported channel: {ch}"}
            
            results.append(res)
            processed += 1
            _record_history({"action": "queue_process", "notification": notif, "result": res})
            _notification_queue.task_done()
            
        return {"success": True, "message": f"Processed {processed} notifications", "data": {"results": results}}
    except Exception as e:
        return {"success": False, "message": "Queue processing failed", "error": str(e)}

def set_notification_callback(event: str, callback: callable) -> Dict[str, Any]:
    """Register a callback for notification events."""
    try:
        if not callable(callback):
            raise TypeError("Callback must be a callable function.")
        _callbacks[event] = callback
        return {"success": True, "message": f"Callback registered for event: {event}"}
    except Exception as e:
        return {"success": False, "message": "Failed to register callback", "error": str(e)}

def create_alert_rule(name: str, condition: callable, notification: dict) -> Dict[str, Any]:
    """Create an alert rule with a conditional trigger."""
    try:
        if not callable(condition):
            raise TypeError("Condition must be a callable function.")
        rule = {"name": name, "condition": condition, "notification": notification, "active": True, "created_at": datetime.now().isoformat()}
        with _rules_lock:
            _alert_rules.append(rule)
        return {"success": True, "message": f"Alert rule '{name}' created"}
    except Exception as e:
        return {"success": False, "message": "Failed to create alert rule", "error": str(e)}

def check_alert_rules(data: dict) -> Dict[str, Any]:
    """Evaluate data against active alert rules and trigger notifications."""
    triggered = []
    try:
        with _rules_lock:
            for rule in _alert_rules:
                if not rule.get("active"):
                    continue
                try:
                    if rule["condition"](data):
                        notif = rule["notification"]
                        ch = notif.get("channel", notif.get("type", "desktop"))
                        if ch == "desktop":
                            res = show_desktop_notification(notif.get("title", "Alert"), notif.get("message", f"Rule {rule['name']} triggered"))
                        else:
                            res = {"success": True, "message": f"Rule {rule['name']} triggered (mock)", "channel": ch}
                        triggered.append({"rule": rule["name"], "result": res})
                        _record_history({"action": "alert_trigger", "rule": rule["name"], "data": data, "result": res})
                except Exception as e:
                    _logger.error(f"Alert rule '{rule['name']}' condition check failed: {e}")
        return {"success": True, "message": f"Evaluated rules. Triggered: {len(triggered)}", "data": {"triggered": triggered}}
    except Exception as e:
        return {"success": False, "message": "Failed to check alert rules", "error": str(e)}

def send_webhook(url: str, payload: dict) -> Dict[str, Any]:
    """Send a generic JSON webhook request."""
    record = {"channel": "webhook", "timestamp": datetime.now().isoformat(), "url": url}
    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        record["success"] = True
        record["status"] = response.status_code
        _update_stats("webhook", True)
        return {"success": True, "message": "Webhook delivered", "data": record}
    except Exception as e:
        record["success"] = False
        record["error"] = str(e)
        _update_stats("webhook", False)
        return {"success": False, "message": "Failed to send webhook", "error": str(e)}

def log_notification(notification: dict, log_file: str = "") -> Dict[str, Any]:
    """Persist notification record to a JSONL log file and memory."""
    try:
        path = log_file if log_file else _DEFAULT_LOG_PATH
        record = {"timestamp": datetime.now().isoformat(), "notification": notification}
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        _record_history(record)
        return {"success": True, "message": "Notification logged", "data": {"file": path}}
    except Exception as e:
        return {"success": False, "message": "Failed to log notification", "error": str(e)}

def get_notification_history(limit: int = 50) -> Dict[str, Any]:
    """Retrieve the most recent notification history."""
    try:
        with _history_lock:
            history = list(_notification_history[-limit:])
        return {"success": True, "data": {"history": history, "count": len(history)}}
    except Exception as e:
        return {"success": False, "message": "Failed to retrieve history", "error": str(e)}

def clear_notification_history() -> Dict[str, Any]:
    """Clear in-memory notification history."""
    try:
        with _history_lock:
            _notification_history.clear()
        return {"success": True, "message": "History cleared"}
    except Exception as e:
        return {"success": False, "message": "Failed to clear history", "error": str(e)}

def set_rate_limit(max_per_minute: int = 10) -> Dict[str, Any]:
    """Configure global rate limiting."""
    global _rate_limit_max
    try:
        if max_per_minute < 1:
            raise ValueError("Rate limit must be >= 1.")
        _rate_limit_max = max_per_minute
        return {"success": True, "message": f"Rate limit set to {max_per_minute}/min"}
    except Exception as e:
        return {"success": False, "message": "Failed to set rate limit", "error": str(e)}

def send_batch_notifications(notifications: list) -> Dict[str, Any]:
    """Process a list of notification dictionaries sequentially with rate limiting."""
    results = []
    success_count = 0
    try:
        for i, notif in enumerate(notifications):
            rl = _check_rate_limit_internal()
            if not rl["success"]:
                results.append({"index": i, "success": False, "message": "Rate limited", "data": rl.get("data")})
                continue
            
            ch = notif.get("type", notif.get("channel", "desktop"))
            res = {"success": False, "message": f"Unsupported type: {ch}"}
            
            if ch == "desktop":
                res = show_desktop_notification(notif.get("title", "Batch"), notif.get("message", ""))
            elif ch == "email":
                res = send_email_notification(notif.get("to", ""), notif.get("subject", "Batch"), notif.get("body", ""), notif.get("smtp_host"))
            elif ch == "slack":
                res = send_slack_webhook(notif.get("webhook_url", ""), notif.get("message", ""))
            elif ch == "discord":
                res = send_discord_webhook(notif.get("webhook_url", ""), notif.get("message", ""))
            elif ch == "telegram":
                res = send_telegram_message(notif.get("bot_token", ""), notif.get("chat_id", ""), notif.get("message", ""))
            elif ch == "webhook":
                res = send_webhook(notif.get("url", ""), notif.get("payload", notif))
                
            res["index"] = i
            results.append(res)
            if res.get("success"):
                success_count += 1
                
        return {"success": True, "message": f"Batch complete: {success_count}/{len(notifications)}", "data": {"results": results}}
    except Exception as e:
        return {"success": False, "message": "Batch processing failed", "error": str(e)}

def create_template(name: str, title_template: str, body_template: str) -> Dict[str, Any]:
    """Store a notification template for later use."""
    try:
        if not name:
            raise ValueError("Template name cannot be empty.")
        _templates[name] = {"title": title_template, "body": body_template, "created_at": datetime.now().isoformat()}
        return {"success": True, "message": f"Template '{name}' created"}
    except Exception as e:
        return {"success": False, "message": "Failed to create template", "error": str(e)}

def send_from_template(template_name: str, variables: dict) -> Dict[str, Any]:
    """Render and send a notification using a stored template."""
    try:
        if template_name not in _templates:
            raise KeyError(f"Template '{template_name}' not found.")
        tmpl = _templates[template_name]
        title = tmpl["title"].format(**variables)
        body = tmpl["body"].format(**variables)
        res = show_desktop_notification(title, body)
        return {"success": True, "message": "Notification sent from template", "data": {"template": template_name, "result": res}}
    except Exception as e:
        return {"success": False, "message": "Failed to send from template", "error": str(e)}

def test_notification_channel(channel: str, config: dict) -> Dict[str, Any]:
    """Run a diagnostic test on a specified notification channel."""
    try:
        if channel == "desktop":
            return show_desktop_notification("Test Notification", "Screen agent desktop test.")
        elif channel == "email":
            if not config.get("to"): raise ValueError("Missing 'to' in config")
            return send_email_notification(config["to"], "Test Email", "Screen agent email test.", config.get("smtp_host"))
        elif channel == "slack":
            if not config.get("webhook_url"): raise ValueError("Missing 'webhook_url' in config")
            return send_slack_webhook(config["webhook_url"], "Test: Screen agent Slack integration.")
        elif channel == "discord":
            if not config.get("webhook_url"): raise ValueError("Missing 'webhook_url' in config")
            return send_discord_webhook(config["webhook_url"], "Test: Screen agent Discord integration.")
        elif channel == "telegram":
            return send_telegram_message(config.get("bot_token", ""), config.get("chat_id", ""), "Test: Screen agent Telegram.")
        elif channel == "pushover":
            return send_pushover(config.get("user_key", ""), config.get("api_token", ""), "Test: Screen agent Pushover.")
        elif channel == "webhook":
            if not config.get("url"): raise ValueError("Missing 'url' in config")
            return send_webhook(config["url"], {"test": True, "source": "screen_agent"})
        else:
            return {"success": False, "error": f"Unsupported channel for testing: {channel}"}
    except Exception as e:
        return {"success": False, "message": f"Channel test failed: {channel}", "error": str(e)}

def get_notification_stats() -> Dict[str, Any]:
    """Return current service statistics and counters."""
    try:
        with _stats_lock:
            snapshot = dict(_stats)
        snapshot["last_updated"] = datetime.now().isoformat()
        return {"success": True, "data": snapshot}
    except Exception as e:
        return {"success": False, "message": "Failed to retrieve stats", "error": str(e)}

def retry_failed_notifications(max_retries: int = 3) -> Dict[str, Any]:
    """Identify failed notifications in history and attempt retries."""
    retried = []
    try:
        with _history_lock:
            for record in _notification_history:
                notif = record.get("notification")
                result = record.get("result", {})
                # Determine if it failed and hasn't exceeded retries
                failed = (result.get("success") is False) or (record.get("action") == "queue_process" and not result.get("success"))
                retry_count = record.get("retry_count", 0)
                
                if failed and retry_count < max_retries:
                    ch = notif.get("channel", notif.get("type", "desktop"))
                    res = {"success": False}
                    
                    if ch == "desktop":
                        res = show_desktop_notification(notif.get("title", "Retry"), notif.get("message", ""))
                    elif ch == "webhook":
                        res = send_webhook(notif.get("url", ""), notif.get("payload", notif))
                    elif ch in ("slack", "discord"):
                        res = send_webhook(notif.get("webhook_url", ""), {"text": notif.get("message", ""), "retry": True})
                        
                    record["retry_count"] = retry_count + 1
                    record["last_retry_at"] = datetime.now().isoformat()
                    retried.append({"record_id": id(record), "channel": ch, "result": res})
                    if res.get("success"):
                        record["success"] = True
        return {"success": True, "message": f"Retry complete for {len(retried)} entries", "data": {"retried": retried}}
    except Exception as e:
        return {"success": False, "message": "Retry process failed", "error": str(e)}