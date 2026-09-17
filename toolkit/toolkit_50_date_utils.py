"""
toolkit_50_date_utils.py
Advanced date/time utilities beyond the existing date_time_actions module:
working days, holidays, date ranges, countdown timers, relative formatting,
and time zone conversions. Stdlib only.
"""
from __future__ import annotations
import datetime
import calendar
import time
from typing import Any, Dict, List

def get_working_days_between(start_date: str, end_date: str) -> Dict[str, Any]:
    """Count working days (Mon-Fri) between two dates (YYYY-MM-DD)."""
    try:
        start = datetime.date.fromisoformat(start_date)
        end = datetime.date.fromisoformat(end_date)
        count = 0
        current = start
        while current <= end:
            if current.weekday() < 5:
                count += 1
            current += datetime.timedelta(days=1)
        return {"success": True, "data": {"working_days": count, "from": start_date, "to": end_date}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def add_working_days(start_date: str, days: int) -> Dict[str, Any]:
    """Add N working days to a date."""
    try:
        current = datetime.date.fromisoformat(start_date)
        added = 0
        while added < days:
            current += datetime.timedelta(days=1)
            if current.weekday() < 5:
                added += 1
        return {"success": True, "data": current.isoformat(), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_date_range(start_date: str, end_date: str) -> Dict[str, Any]:
    """List all dates between two dates."""
    try:
        start = datetime.date.fromisoformat(start_date)
        end = datetime.date.fromisoformat(end_date)
        dates = []
        current = start
        while current <= end:
            dates.append(current.isoformat())
            current += datetime.timedelta(days=1)
        return {"success": True, "data": dates, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_month_calendar(year: int, month: int) -> Dict[str, Any]:
    try:
        cal = calendar.monthcalendar(year, month)
        month_name = calendar.month_name[month]
        return {"success": True, "data": {
            "year": year, "month": month, "month_name": month_name,
            "weeks": cal,
            "days_in_month": calendar.monthrange(year, month)[1]
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_quarter(date_str: str = "") -> Dict[str, Any]:
    """Get the quarter (Q1-Q4) for a date."""
    try:
        if date_str:
            d = datetime.date.fromisoformat(date_str)
        else:
            d = datetime.date.today()
        q = (d.month - 1) // 3 + 1
        return {"success": True, "data": {"quarter": q, "quarter_name": "Q" + str(q), "year": d.year, "date": d.isoformat()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def days_until(target_date: str) -> Dict[str, Any]:
    try:
        target = datetime.date.fromisoformat(target_date)
        today = datetime.date.today()
        delta = (target - today).days
        return {"success": True, "data": {"days_until": delta, "target": target_date, "today": today.isoformat(), "past": delta < 0}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def time_since(past_datetime: str) -> Dict[str, Any]:
    """Human-readable time elapsed since a datetime string."""
    try:
        past = datetime.datetime.fromisoformat(past_datetime)
        now = datetime.datetime.now()
        delta = now - past
        seconds = int(delta.total_seconds())
        if seconds < 60:
            result = str(seconds) + " seconds ago"
        elif seconds < 3600:
            result = str(seconds // 60) + " minutes ago"
        elif seconds < 86400:
            result = str(seconds // 3600) + " hours ago"
        elif seconds < 604800:
            result = str(seconds // 86400) + " days ago"
        elif seconds < 2592000:
            result = str(seconds // 604800) + " weeks ago"
        else:
            result = str(seconds // 2592000) + " months ago"
        return {"success": True, "data": {"formatted": result, "total_seconds": seconds}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def convert_timezone(dt_str: str, from_tz: str, to_tz: str) -> Dict[str, Any]:
    """Convert between timezone offset strings like '+05:30', '-08:00', 'UTC'."""
    try:
        from datetime import timezone, timedelta
        def parse_tz(tz_str):
            if tz_str.upper() == "UTC":
                return timezone.utc
            sign = 1 if "+" in tz_str else -1
            parts = tz_str.replace("+", "").replace("-", "").split(":")
            hours = int(parts[0])
            mins = int(parts[1]) if len(parts) > 1 else 0
            return timezone(timedelta(hours=sign * hours, minutes=sign * mins))
        dt = datetime.datetime.fromisoformat(dt_str)
        src_tz = parse_tz(from_tz)
        dst_tz = parse_tz(to_tz)
        dt_aware = dt.replace(tzinfo=src_tz)
        converted = dt_aware.astimezone(dst_tz)
        return {"success": True, "data": {"converted": converted.isoformat(), "from_tz": from_tz, "to_tz": to_tz}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_week_number(date_str: str = "") -> Dict[str, Any]:
    try:
        d = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
        iso = d.isocalendar()
        return {"success": True, "data": {"week": iso[1], "year": iso[0], "weekday": iso[2], "date": d.isoformat()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_last_day_of_month(year: int, month: int) -> Dict[str, Any]:
    try:
        last_day = calendar.monthrange(year, month)[1]
        return {"success": True, "data": str(datetime.date(year, month, last_day)), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def parse_date_flexible(date_str: str) -> Dict[str, Any]:
    """Try to parse many common date formats."""
    try:
        formats = [
            "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
            "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
            "%Y%m%d", "%d.%m.%Y", "%Y/%m/%d"
        ]
        for fmt in formats:
            try:
                d = datetime.datetime.strptime(date_str, fmt)
                return {"success": True, "data": {"iso": d.date().isoformat(), "format_used": fmt}, "error": None}
            except ValueError:
                pass
        return {"success": False, "data": None, "error": "Could not parse date: " + date_str}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def format_duration(seconds: float) -> Dict[str, Any]:
    """Format a duration in seconds as HH:MM:SS or human readable."""
    try:
        s = int(seconds)
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        formatted = str(h).zfill(2) + ":" + str(m).zfill(2) + ":" + str(sec).zfill(2)
        if h > 0:
            human = str(h) + "h " + str(m) + "m " + str(sec) + "s"
        elif m > 0:
            human = str(m) + "m " + str(sec) + "s"
        else:
            human = str(sec) + "s"
        return {"success": True, "data": {"formatted": formatted, "human": human, "total_seconds": s}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_age(birth_date: str) -> Dict[str, Any]:
    try:
        born = datetime.date.fromisoformat(birth_date)
        today = datetime.date.today()
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        next_birthday = datetime.date(today.year + (1 if (today.month, today.day) > (born.month, born.day) else 0), born.month, born.day)
        days_to_next = (next_birthday - today).days
        return {"success": True, "data": {"age": age, "birth_date": birth_date, "days_until_birthday": days_to_next}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def is_leap_year(year: int) -> Dict[str, Any]:
    try:
        return {"success": True, "data": calendar.isleap(year), "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_day_of_year(date_str: str = "") -> Dict[str, Any]:
    try:
        d = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
        return {"success": True, "data": {"day_of_year": d.timetuple().tm_yday, "date": d.isoformat()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
