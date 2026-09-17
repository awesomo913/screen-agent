"""
notification_actions.py
-----------------------

Utility functions for sending notifications through many channels (desktop, email,
webhooks, SMS, etc.) and for managing notification history, rate‑limiting and queues.

All public functions return a ``Dict`` with the following structure::

    {
        "success": bool,
        "message": str,
        "data": Optional[Any]   # may contain extra information (e.g. response JSON)
    }

The module is deliberately self‑contained; external dependencies are limited to
the standard library plus the packages you listed:

* plyer
* smtplib / email
* requests
* json
* subprocess
* platform
* threading
* time
"""

from __future__ import annotations

import json
import platform
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import requests
from email import encoders
from email.message import EmailMessage
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from plyer import notification as plyer_notification

# --------------------------------------------------------------------------- #
# Helper Types
# --------------------------------------------------------------------------- #

SMTPConfig = Dict[str, Union[str, int, bool]]
RateLimiterRecord = Dict[str, List[float]]  # key -> list of timestamps (epoch seconds)

# Global in‑memory structures (thread‑safe where needed)
_rate_limiter_lock = threading.Lock()
_rate_limiter_store: RateLimiterRecord = {}

# --------------------------------------------------------------------------- #
# Core notification utilities
# --------------------------------------------------------------------------- #

def _make_result(success: bool, message: str, data: Any = None) -> Dict[str, Any]:
    """Standardised result builder."""
    return {"success": success, "message": message, "data": data}


# --------------------------------------------------------------------------- #
# Desktop notifications
# --------------------------------------------------------------------------- #

def send_desktop_notification(
    title: str,
    message: str,
    icon: Optional[str] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    """
    Show a native desktop notification using *plyer*.

    Returns a result dict. ``timeout`` is ignored on macOS (plyer uses the system default).
    """
    try:
        plyer_notification.notify(
            title=title,
            message=message,
            app_icon=icon,
            timeout=timeout,
        )
        return _make_result(True, "Desktop notification sent.")
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"Desktop notification failed: {exc}")


def send_toast_windows(title: str, message: str) -> Dict[str, Any]:
    """
    Windows 10+ toast notification via PowerShell.
    Relies on the built‑in ``New-BurntToastNotification`` cmdlet (comes with
    Windows 10 1903+). If unavailable we fall back to a simple message box.
    """
    try:
        safe_title = title.replace("'", "\\'")
        safe_msg = message.replace("'", "\\'")
        ps_script = (
            f"$title = '{safe_title}'; "
            f"$msg = '{safe_msg}'; "
            f"New-BurntToastNotification -Text $title, $msg"
        )
        subprocess.run(
            ["powershell", "-Command", ps_script],
            check=True,
            capture_output=True,
        )
        return _make_result(True, "Windows toast sent.")
    except subprocess.CalledProcessError as exc:
        # Fallback to a simple messagebox
        try:
            fallback = (
                f"[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');"
                f"[System.Windows.Forms.MessageBox]::Show('{message}', '{title}')"
            )
            subprocess.run(
                ["powershell", "-Command", fallback],
                check=True,
                capture_output=True,
            )
            return _make_result(True, "Windows fallback toast sent.")
        except Exception as e2:  # pragma: no cover
            return _make_result(False, f"Windows toast failed: {exc}; fallback error: {e2}")


def send_notify_linux(title: str, message: str, urgency: str = "normal") -> Dict[str, Any]:
    """
    Linux desktop notification via ``notify-send``.
    ``urgency`` can be ``low``, ``normal`` or ``critical``.
    """
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, title, message],
            check=True,
            capture_output=True,
        )
        return _make_result(True, "Linux notify-send notification sent.")
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"Linux notify-send failed: {exc}")


def send_macos_notification(title: str, message: str) -> Dict[str, Any]:
    """
    macOS notification using AppleScript (``osascript``).
    """
    try:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
        )
        return _make_result(True, "macOS notification sent.")
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"macOS notification failed: {exc}")


def play_notification_sound(sound_path: str) -> Dict[str, Any]:
    """
    Play a sound file. Uses platform‑appropriate command:
        * macOS – ``afplay``
        * Linux – ``aplay`` (or ``paplay`` if available)
        * Windows – PowerShell ``[Media.SoundPlayer]``.
    """
    try:
        system = platform.system()
        if system == "Darwin":
            cmd = ["afplay", sound_path]
        elif system == "Linux":
            # Prefer paplay (PulseAudio) else fallback to aplay
            cmd = ["paplay", sound_path] if subprocess.run(["which", "paplay"], capture_output=True).returncode == 0 else ["aplay", sound_path]
        elif system == "Windows":
            ps = (
                f"$player = New-Object System.Media.SoundPlayer '{sound_path}'; "
                "$player.PlaySync()"
            )
            cmd = ["powershell", "-Command", ps]
        else:
            return _make_result(False, f"Unsupported platform: {system}")

        subprocess.run(cmd, check=True, capture_output=True)
        return _make_result(True, "Sound played successfully.")
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"Failed to play sound: {exc}")


# --------------------------------------------------------------------------- #
# Email utilities
# --------------------------------------------------------------------------- #

def validate_email_config(smtp_config: SMTPConfig) -> Dict[str, Any]:
    """Ensure required keys are present in a SMTP configuration dict."""
    required = {"host", "port", "username", "password"}
    missing = required - smtp_config.keys()
    if missing:
        return _make_result(False, f"Missing SMTP config keys: {missing}")
    return _make_result(True, "SMTP config valid.")


def _connect_smtp(smtp_config: SMTPConfig) -> Tuple[Optional[smtplib.SMTP], Optional[str]]:
    """Create and return an SMTP connection (or an error message)."""
    try:
        host = smtp_config["host"]
        port = smtp_config["port"]
        username = smtp_config["username"]
        password = smtp_config["password"]
        use_tls = smtp_config.get("use_tls", True)

        server = smtplib.SMTP(host, port, timeout=10)
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        server.login(username, password)
        return server, None
    except Exception as exc:  # pragma: no cover
        return None, str(exc)


def send_email_notification(
    to: str,
    subject: str,
    body: str,
    smtp_config: SMTPConfig,
) -> Dict[str, Any]:
    """
    Send a plain‑text email.
    """
    conn, err = _connect_smtp(smtp_config)
    if err:
        return _make_result(False, f"SMTP connection failed: {err}")

    try:
        msg = EmailMessage()
        msg["From"] = smtp_config["username"]
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        conn.send_message(msg)
        return _make_result(True, "Email sent.")
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"Email send failed: {exc}")
    finally:
        conn.quit()


def send_email_with_attachment(
    to: str,
    subject: str,
    body: str,
    attachments: List[str],
    smtp_config: SMTPConfig,
) -> Dict[str, Any]:
    """
    Send an email with one or more file attachments.
    """
    conn, err = _connect_smtp(smtp_config)
    if err:
        return _make_result(False, f"SMTP connection failed: {err}")

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_config["username"]
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        for path_str in attachments:
            path = Path(path_str)
            if not path.is_file():
                return _make_result(False, f"Attachment not found: {path_str}")

            with path.open("rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{path.name}"',
                )
                msg.attach(part)

        conn.send_message(msg)
        return _make_result(True, "Email with attachment sent.")
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"Failed to send email with attachment: {exc}")
    finally:
        conn.quit()


def create_email_template(template: str, variables: Dict[str, str]) -> Dict[str, Any]:
    """
    Very small templating helper – replaces ``{{key}}`` placeholders
    with values from ``variables``.
    """
    try:
        for k, v in variables.items():
            placeholder = f"{{{{{k}}}}}"
            template = template.replace(placeholder, v)
        return _make_result(True, "Template rendered.", template)
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"Template rendering error: {exc}")


def send_html_email(
    to: str,
    subject: str,
    html_body: str,
    smtp_config: SMTPConfig,
) -> Dict[str, Any]:
    """Send an HTML formatted email."""
    conn, err = _connect_smtp(smtp_config)
    if err:
        return _make_result(False, f"SMTP connection failed: {err}")

    try:
        msg = EmailMessage()
        msg["From"] = smtp_config["username"]
        msg["To"] = to
        msg["Subject"] = subject
        msg.add_alternative(html_body, subtype="html")
        conn.send_message(msg)
        return _make_result(True, "HTML email sent.")
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"HTML email send failed: {exc}")
    finally:
        conn.quit()


def send_batch_emails(
    recipients: List[str],
    subject: str,
    body: str,
    smtp_config: SMTPConfig,
) -> Dict[str, Any]:
    """
    Send the same plain‑text email to many recipients.
    Returns a summary with success / failure counts.
    """
    conn, err = _connect_smtp(smtp_config)
    if err:
        return _make_result(False, f"SMTP connection failed: {err}")

    success = 0
    failures = []

    try:
        for rcpt in recipients:
            msg = EmailMessage()
            msg["From"] = smtp_config["username"]
            msg["To"] = rcpt
            msg["Subject"] = subject
            msg.set_content(body)

            try:
                conn.send_message(msg)
                success += 1
            except Exception as e:  # pragma: no cover
                failures.append((rcpt, str(e)))

        summary = {
            "sent": success,
            "failed": len(failures),
            "failures": failures,
        }
        return _make_result(True, "Batch email completed.", summary)
    finally:
        conn.quit()


# --------------------------------------------------------------------------- #
# Webhook / API notifications
# --------------------------------------------------------------------------- #

def send_webhook(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    method: str = "POST",
) -> Dict[str, Any]:
    """
    Generic webhook helper. Supports ``GET`` and ``POST`` (default).
    Returns the JSON response (if any) in ``data``.
    """
    try:
        headers = headers or {"Content-Type": "application/json"}
        if method.upper() == "POST":
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
        else:
            resp = requests.get(url, params=payload, headers=headers, timeout=10)

        resp.raise_for_status()
        try:
            data = resp.json()
        except Exception:
            data = resp.text
        return _make_result(True, "Webhook sent.", data)
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"Webhook call failed: {exc}")


def send_slack_webhook(
    webhook_url: str,
    message: str,
    channel: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sends a message to Slack via an incoming webhook.
    If ``channel`` is supplied the payload includes it (requires the webhook to be
    configured for channel overrides).
    """
    payload = {"text": message}
    if channel:
        payload["channel"] = channel
    return send_webhook(webhook_url, payload)


def send_discord_webhook(
    webhook_url: str,
    message: Optional[str] = None,
    embed: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Sends a Discord webhook. Either a simple message, an embed, or both can be provided.
    """
    payload: Dict[str, Any] = {}
    if message:
        payload["content"] = message
    if embed:
        payload["embeds"] = [embed]
    return send_webhook(webhook_url, payload)


def send_telegram_message(
    bot_token: str,
    chat_id: Union[int, str],
    message: str,
) -> Dict[str, Any]:
    """
    Sends a Telegram text message using the Bot API.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    return send_webhook(url, payload, method="POST")


def send_sms_twilio(
    account_sid: str,
    auth_token: str,
    to: str,
    from_num: str,
    body: str,
) -> Dict[str, Any]:
    """
    Sends an SMS via Twilio's REST API using ``requests`` (no external Twilio library).
    """
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    payload = {"To": to, "From": from_num, "Body": body}
    try:
        resp = requests.post(
            url,
            data=payload,
            auth=(account_sid, auth_token),
            timeout=10,
        )
        resp.raise_for_status()
        return _make_result(True, "SMS sent via Twilio.", resp.json())
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"Twilio SMS failed: {exc}")


def send_pushover_notification(
    token: str,
    user: str,
    message: str,
) -> Dict[str, Any]:
    """
    Sends a notification via Pushover.
    """
    url = "https://api.pushover.net/1/messages.json"
    payload = {
        "token": token,
        "user": user,
        "message": message,
    }
    return send_webhook(url, payload, method="POST")


def send_system_alert(level: str, message: str) -> Dict[str, Any]:
    """
    Simple system‑level alert – writes to ``stderr`` and optionally triggers a desktop
    notification. ``level`` can be ``info``, ``warning`` or ``error``.
    """
    level = level.lower()
    prefix = {"info": "[INFO]", "warning": "[WARN]", "error": "[ERROR]"}.get(
        level, "[INFO]"
    )
    full_msg = f"{prefix} {message}"
    try:
        print(full_msg, file=sys.stderr)
        # For noticeable alerts we also pop a desktop notification
        if level in {"warning", "error"}:
            send_desktop_notification(title=level.title(), message=message, timeout=5)
        return _make_result(True, "System alert emitted.")
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"System alert failed: {exc}")


# --------------------------------------------------------------------------- #
# Scheduling / rate limiting
# --------------------------------------------------------------------------- #

def schedule_notification(
    title: str,
    message: str,
    delay_seconds: int,
) -> Dict[str, Any]:
    """
    Schedules a plain desktop notification after ``delay_seconds``.
    Returns a handle dictionary that can be used to cancel the timer if needed.
    """
    def _callback():
        send_desktop_notification(title=title, message=message)

    try:
        timer = threading.Timer(delay_seconds, _callback)
        timer.start()
        return _make_result(True, "Notification scheduled.", {"timer": timer})
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"Scheduling failed: {exc}")


def notification_rate_limiter(
    key: str,
    max_per_hour: int,
) -> Dict[str, Any]:
    """
    Very lightweight in‑memory rate limiter.
    ``key`` identifies the notification source (e.g. user‑id, email address).
    Returns a dict with ``allowed`` boolean and ``remaining`` count.
    """
    now = time.time()
    cutoff = now - 3600  # one hour ago

    with _rate_limiter_lock:
        timestamps = _rate_limiter_store.setdefault(key, [])
        # Remove old entries
        timestamps = [t for t in timestamps if t > cutoff]
        allowed = len(timestamps) < max_per_hour
        if allowed:
            timestamps.append(now)
        _rate_limiter_store[key] = timestamps

    remaining = max(0, max_per_hour - len(timestamps))
    return _make_result(True, "Rate limiter checked.", {"allowed": allowed, "remaining": remaining})


# --------------------------------------------------------------------------- #
# Queue handling
# --------------------------------------------------------------------------- #

def create_notification_queue(notifications: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Wrap a list of notification descriptors into a simple queue structure.
    The caller is expected to provide dictionaries with at least a ``type`` field
    and the corresponding arguments.
    """
    if not isinstance(notifications, list):
        return _make_result(False, "notifications must be a list.")
    queue = {"queue": notifications, "size": len(notifications)}
    return _make_result(True, "Queue created.", queue)


def process_notification_queue(queue: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process items in a notification queue sequentially.
    Each queue item must contain:
        - ``type``: one of the function names defined in this module.
        - ``args``: a dict of keyword arguments for that function.
    Returns a summary of successes/failures.
    """
    if "queue" not in queue:
        return _make_result(False, "Invalid queue structure.")
    items = queue["queue"]
    successes = 0
    failures = []

    for idx, item in enumerate(items):
        n_type = item.get("type")
        args = item.get("args", {})
        func: Optional[Callable] = globals().get(n_type)
        if not callable(func):
            failures.append((idx, f"Unknown notification type: {n_type}"))
            continue
        try:
            result = func(**args)  # type: ignore
            if result.get("success"):
                successes += 1
            else:
                failures.append((idx, result.get("message")))
        except Exception as exc:  # pragma: no cover
            failures.append((idx, str(exc)))

    summary = {
        "processed": len(items),
        "successful": successes,
        "failed": len(failures),
        "failures": failures,
    }
    return _make_result(True, "Queue processed.", summary)


# --------------------------------------------------------------------------- #
# Logging / history
# --------------------------------------------------------------------------- #

def log_notification(notification_data: Dict[str, Any], log_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Append a JSON line to ``log_path``. The file is created if it does not exist.
    """
    try:
        log_file = Path(log_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as f:
            json_line = json.dumps({"timestamp": datetime.utcnow().isoformat(), **notification_data})
            f.write(json_line + "\n")
        return _make_result(True, "Notification logged.")
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"Logging failed: {exc}")


def get_notification_history(
    log_path: Union[str, Path],
    since: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Retrieve logged notifications. If ``since`` is provided, only entries newer
    than that datetime are returned.
    """
    try:
        log_file = Path(log_path)
        if not log_file.is_file():
            return _make_result(True, "No history file; returning empty list.", [])

        entries = []
        with log_file.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    entry_time = datetime.fromisoformat(entry["timestamp"])
                    if since is None or entry_time >= since:
                        entries.append(entry)
                except Exception:
                    continue  # skip malformed lines

        return _make_result(True, f"Returned {len(entries)} entries.", entries)
    except Exception as exc:  # pragma: no cover
        return _make_result(False, f"Failed to read history: {exc}")


# --------------------------------------------------------------------------- #
# Retry helper
# --------------------------------------------------------------------------- #

def retry_notification(
    func: Callable,
    args: Tuple[Any, ...],
    max_retries: int = 3,
    backoff: float = 1.0,
) -> Dict[str, Any]:
    """
    Calls ``func`` with ``args``. On failure, retries up to ``max_retries`` times
    with exponential back‑off (``backoff`` seconds multiplied each retry).
    """
    attempt = 0
    while attempt <= max_retries:
        try:
            result = func(*args)  # type: ignore
            if result.get("success"):
                return _make_result(True, f"Successful after {attempt} retries.", result)
            else:
                raise RuntimeError(result.get("message", "unknown error"))
        except Exception as exc:
            if attempt == max_retries:
                return _make_result(False, f"All retries exhausted: {exc}")
            time.sleep(backoff * (2 ** attempt))
            attempt += 1
    # Should never reach here
    return _make_result(False, "Retry logic error.")


# --------------------------------------------------------------------------- #
# End of file
# --------------------------------------------------------------------------- #