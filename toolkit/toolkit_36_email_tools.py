"""
toolkit_36_email_tools.py
Send emails (SMTP), check IMAP mailboxes, compose messages,
and manage drafts. Uses stdlib smtplib/imaplib with soft credentials handling.
"""
from __future__ import annotations
import smtplib
import imaplib
import email
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Any, Dict, List

def send_email(smtp_host: str, smtp_port: int, username: str, password: str,
               to: str, subject: str, body: str, use_tls: bool = True) -> Dict[str, Any]:
    try:
        msg = MIMEMultipart()
        msg["From"] = username
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        if use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        server.login(username, password)
        server.sendmail(username, to, msg.as_string())
        server.quit()
        return {"success": True, "data": {"sent_to": to, "subject": subject}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def send_email_with_attachment(smtp_host: str, smtp_port: int, username: str, password: str,
                               to: str, subject: str, body: str, attachment_path: str, use_tls: bool = True) -> Dict[str, Any]:
    try:
        msg = MIMEMultipart()
        msg["From"] = username
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        with open(attachment_path, "rb") as att:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(att.read())
        encoders.encode_base64(part)
        filename = os.path.basename(attachment_path)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)
        if use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        server.login(username, password)
        server.sendmail(username, to, msg.as_string())
        server.quit()
        return {"success": True, "data": {"sent_to": to, "attachment": filename}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def send_html_email(smtp_host: str, smtp_port: int, username: str, password: str,
                    to: str, subject: str, html_body: str, use_tls: bool = True) -> Dict[str, Any]:
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = username
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))
        if use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        server.login(username, password)
        server.sendmail(username, to, msg.as_string())
        server.quit()
        return {"success": True, "data": {"sent_to": to, "subject": subject}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_imap_inbox(imap_host: str, username: str, password: str, max_messages: int = 10) -> Dict[str, Any]:
    try:
        mail = imaplib.IMAP4_SSL(imap_host, timeout=15)
        mail.login(username, password)
        mail.select("INBOX")
        _, msg_ids = mail.search(None, "ALL")
        ids = msg_ids[0].split()
        recent = ids[-max_messages:] if len(ids) > max_messages else ids
        messages = []
        for mid in reversed(recent):
            _, msg_data = mail.fetch(mid, "(RFC822.HEADER)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            messages.append({
                "id": mid.decode(),
                "from": msg.get("From", ""),
                "subject": msg.get("Subject", ""),
                "date": msg.get("Date", "")
            })
        mail.logout()
        return {"success": True, "data": {"total": len(ids), "messages": messages}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_unread_count(imap_host: str, username: str, password: str) -> Dict[str, Any]:
    try:
        mail = imaplib.IMAP4_SSL(imap_host, timeout=15)
        mail.login(username, password)
        mail.select("INBOX")
        _, data = mail.search(None, "UNSEEN")
        count = len(data[0].split()) if data[0] else 0
        mail.logout()
        return {"success": True, "data": {"unread": count}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_email_by_id(imap_host: str, username: str, password: str, message_id: str) -> Dict[str, Any]:
    try:
        mail = imaplib.IMAP4_SSL(imap_host, timeout=15)
        mail.login(username, password)
        mail.select("INBOX")
        _, msg_data = mail.fetch(message_id.encode(), "(RFC822)")
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(errors="replace")
                    break
        else:
            body = msg.get_payload(decode=True).decode(errors="replace")
        mail.logout()
        return {"success": True, "data": {
            "from": msg.get("From", ""),
            "to": msg.get("To", ""),
            "subject": msg.get("Subject", ""),
            "date": msg.get("Date", ""),
            "body": body[:5000]
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_imap_folders(imap_host: str, username: str, password: str) -> Dict[str, Any]:
    try:
        mail = imaplib.IMAP4_SSL(imap_host, timeout=15)
        mail.login(username, password)
        _, folders = mail.list()
        folder_names = [f.decode().split('"/"')[-1].strip().strip('"') for f in folders]
        mail.logout()
        return {"success": True, "data": folder_names, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def test_smtp_connection(smtp_host: str, smtp_port: int, use_tls: bool = True) -> Dict[str, Any]:
    try:
        if use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        banner = server.ehlo()
        server.quit()
        return {"success": True, "data": {"host": smtp_host, "port": smtp_port, "connected": True}, "error": None}
    except Exception as e:
        return {"success": False, "data": {"connected": False}, "error": str(e)}

def compose_email_text(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> Dict[str, Any]:
    """Build an email as a text string (without sending)."""
    try:
        msg = MIMEMultipart()
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc
        msg.attach(MIMEText(body, "plain"))
        return {"success": True, "data": {"composed": msg.as_string()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def parse_email_file(eml_path: str) -> Dict[str, Any]:
    """Parse a .eml file."""
    try:
        with open(eml_path, "rb") as f:
            msg = email.message_from_bytes(f.read())
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(errors="replace")
                    break
        else:
            body = msg.get_payload(decode=True).decode(errors="replace")
        return {"success": True, "data": {
            "from": msg.get("From", ""),
            "to": msg.get("To", ""),
            "subject": msg.get("Subject", ""),
            "date": msg.get("Date", ""),
            "body": body[:5000]
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
