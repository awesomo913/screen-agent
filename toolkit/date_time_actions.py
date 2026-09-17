"""
date_time_actions.py
Screen Agent Toolkit: Robust, fully-implemented date/time operations.
Uses: datetime, time, calendar, pytz, dateutil, zoneinfo
All functions return Dict[str, Any] with standardized success/error structure.
"""

from datetime import datetime, timedelta, timezone, date, time
import time as time_lib
import calendar
import pytz
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dateutil import parser as dateutil_parser
from typing import Dict, Any, List, Optional

# Standardized return helpers
def _success(data: Any) -> Dict[str, Any]:
    return {"success": True, "data": data, "error": None}

def _error(msg: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "error": str(msg)}

# Internal timezone resolver
def _resolve_tz(tz_name: str) -> timezone:
    tz_upper = tz_name.upper().strip()
    if tz_upper in ("UTC", "GMT", "+00:00"):
        return timezone.utc
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        try:
            return pytz.timezone(tz_name)
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f"Unknown timezone: {tz_name}")

# Internal datetime parser with safe fallbacks
def _parse_dt(dt_string: str) -> datetime:
    if not dt_string or not isinstance(dt_string, str):
        return datetime.now(timezone.utc)
    try:
        dt = dateutil_parser.parse(dt_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as e:
        raise ValueError(f"Failed to parse datetime string '{dt_string}': {e}")


def get_current_time(timezone: str = "UTC") -> Dict[str, Any]:
    """Returns current time components in the specified timezone."""
    try:
        tz = _resolve_tz(timezone)
        now = datetime.now(tz)
        return _success({
            "time": now.strftime("%H:%M:%S"),
            "iso8601": now.isoformat(),
            "utc_offset": now.strftime("%z"),
            "tz_name": now.tzname()
        })
    except Exception as e:
        return _error(str(e))


def get_current_date(timezone: str = "UTC") -> Dict[str, Any]:
    """Returns current date components in the specified timezone."""
    try:
        tz = _resolve_tz(timezone)
        now = datetime.now(tz)
        return _success({
            "date": now.strftime("%Y-%m-%d"),
            "iso8601": now.isoformat(),
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "tz_name": now.tzname()
        })
    except Exception as e:
        return _error(str(e))


def format_datetime(dt_string: str, format: str = "%Y-%m-%d %H:%M:%S") -> Dict[str, Any]:
    """Parses a datetime string and formats it according to the given format."""
    try:
        dt = _parse_dt(dt_string)
        return _success({
            "formatted": dt.strftime(format),
            "iso8601": dt.isoformat()
        })
    except Exception as e:
        return _error(str(e))


def parse_datetime(dt_string: str, format: str = "") -> Dict[str, Any]:
    """Parses a datetime string. If format is provided, uses strptime; else dateutil."""
    try:
        if format:
            dt = datetime.strptime(dt_string, format)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = _parse_dt(dt_string)
        return _success({
            "iso8601": dt.isoformat(),
            "year": dt.year, "month": dt.month, "day": dt.day,
            "hour": dt.hour, "minute": dt.minute, "second": dt.second,
            "tzinfo": str(dt.tzinfo)
        })
    except Exception as e:
        return _error(str(e))


def add_days(dt_string: str, days: int) -> Dict[str, Any]:
    """Adds/subtracts days to/from a datetime string."""
    try:
        dt = _parse_dt(dt_string)
        new_dt = dt + timedelta(days=days)
        return _success({"datetime": new_dt.isoformat(), "added_days": days})
    except Exception as e:
        return _error(str(e))


def add_hours(dt_string: str, hours: int) -> Dict[str, Any]:
    """Adds/subtracts hours to/from a datetime string."""
    try:
        dt = _parse_dt(dt_string)
        new_dt = dt + timedelta(hours=hours)
        return _success({"datetime": new_dt.isoformat(), "added_hours": hours})
    except Exception as e:
        return _error(str(e))


def add_minutes(dt_string: str, minutes: int) -> Dict[str, Any]:
    """Adds/subtracts minutes to/from a datetime string."""
    try:
        dt = _parse_dt(dt_string)
        new_dt = dt + timedelta(minutes=minutes)
        return _success({"datetime": new_dt.isoformat(), "added_minutes": minutes})
    except Exception as e:
        return _error(str(e))


def subtract_dates(dt1: str, dt2: str) -> Dict[str, Any]:
    """Subtracts dt2 from dt1 and returns the delta."""
    try:
        d1 = _parse_dt(dt1)
        d2 = _parse_dt(dt2)
        delta = d1 - d2
        return _success({
            "days": delta.days,
            "seconds": delta.seconds,
            "total_seconds": delta.total_seconds(),
            "iso8601_duration": str(delta)
        })
    except Exception as e:
        return _error(str(e))


def get_weekday(dt_string: str) -> Dict[str, Any]:
    """Returns weekday name and index (0=Monday, 6=Sunday)."""
    try:
        dt = _parse_dt(dt_string)
        return _success({
            "weekday_name": dt.strftime("%A"),
            "weekday_index": dt.weekday(),
            "iso_weekday": dt.isoweekday()
        })
    except Exception as e:
        return _error(str(e))


def is_weekend(dt_string: str) -> Dict[str, Any]:
    """Checks if the given date falls on a weekend."""
    try:
        dt = _parse_dt(dt_string)
        is_wknd = dt.weekday() >= 5
        return _success({"is_weekend": is_wknd, "weekday": dt.strftime("%A")})
    except Exception as e:
        return _error(str(e))


def is_leap_year(year: int) -> Dict[str, Any]:
    """Checks if a given year is a leap year."""
    try:
        return _success({"is_leap_year": calendar.isleap(year), "year": year})
    except Exception as e:
        return _error(str(e))


def get_month_calendar(year: int, month: int) -> Dict[str, Any]:
    """Returns the calendar grid for a specific month and year."""
    try:
        cal = calendar.monthcalendar(year, month)
        return _success({
            "year": year,
            "month": month,
            "calendar_grid": cal,
            "month_name": calendar.month_name[month]
        })
    except Exception as e:
        return _error(str(e))


def convert_timezone(dt_string: str, from_tz: str, to_tz: str) -> Dict[str, Any]:
    """Converts a datetime string from one timezone to another."""
    try:
        dt = dateutil_parser.parse(dt_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_resolve_tz(from_tz))
        else:
            dt = dt.astimezone(_resolve_tz(from_tz))
        
        converted = dt.astimezone(_resolve_tz(to_tz))
        return _success({
            "original": dt.isoformat(),
            "converted": converted.isoformat(),
            "from_tz": str(dt.tzinfo),
            "to_tz": str(converted.tzinfo)
        })
    except Exception as e:
        return _error(str(e))


def list_timezones(filter: str = "") -> Dict[str, Any]:
    """Lists available timezones, optionally filtered."""
    try:
        all_tz = set(ZoneInfo().key_names) if hasattr(ZoneInfo, 'key_names') else set()
        if not all_tz:
            all_tz = set(pytz.all_timezones)
        filtered = sorted([tz for tz in all_tz if filter.lower() in tz.lower()])
        return _success({"timezones": filtered, "count": len(filtered), "filter": filter})
    except Exception as e:
        return _error(str(e))


def get_unix_timestamp(dt_string: str = "") -> Dict[str, Any]:
    """Returns the Unix timestamp for a datetime string or current time."""
    try:
        if not dt_string:
            ts = time_lib.time()
        else:
            ts = _parse_dt(dt_string).timestamp()
        return _success({"unix_timestamp": ts})
    except Exception as e:
        return _error(str(e))


def from_unix_timestamp(timestamp: float) -> Dict[str, Any]:
    """Converts a Unix timestamp to an ISO8601 UTC datetime string."""
    try:
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return _success({"datetime": dt.isoformat(), "utc": True})
    except Exception as e:
        return _error(str(e))


def get_iso_format(dt_string: str) -> Dict[str, Any]:
    """Returns the ISO8601 representation of a datetime string."""
    try:
        dt = _parse_dt(dt_string)
        return _success({"iso8601": dt.isoformat()})
    except Exception as e:
        return _error(str(e))


def get_relative_time(dt_string: str) -> Dict[str, Any]:
    """Returns human-readable relative time (e.g., '2 days ago')."""
    try:
        target = _parse_dt(dt_string)
        now = datetime.now(timezone.utc)
        if target.tzinfo:
            target = target.astimezone(timezone.utc)
            
        delta = target - now
        total_seconds = int(delta.total_seconds())
        is_past = total_seconds < 0
        abs_secs = abs(total_seconds)
        
        if abs_secs < 60:
            desc = f"{abs_secs} seconds {'ago' if is_past else 'from now'}"
        elif abs_secs < 3600:
            desc = f"{abs_secs // 60} minutes {'ago' if is_past else 'from now'}"
        elif abs_secs < 86400:
            desc = f"{abs_secs // 3600} hours {'ago' if is_past else 'from now'}"
        else:
            desc = f"{abs_secs // 86400} days {'ago' if is_past else 'from now'}"
            
        return _success({"relative": desc, "is_past": is_past, "total_seconds": total_seconds})
    except Exception as e:
        return _error(str(e))


def date_range(start: str, end: str, step_days: int = 1) -> Dict[str, Any]:
    """Generates a list of dates between start and end."""
    try:
        start_dt = _parse_dt(start)
        end_dt = _parse_dt(end)
        if step_days <= 0:
            raise ValueError("step_days must be positive")
            
        dates = []
        current = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end_d = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        while current <= end_d:
            dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=step_days)
            
        return _success({"dates": dates, "count": len(dates)})
    except Exception as e:
        return _error(str(e))


def get_business_days(start: str, end: str, holidays: Optional[List[str]] = None) -> Dict[str, Any]:
    """Returns list of business days (Mon-Fri) excluding holidays."""
    try:
        start_dt = _parse_dt(start).date()
        end_dt = _parse_dt(end).date()
        holiday_dates = set()
        if holidays:
            for h in holidays:
                try: holiday_dates.add(_parse_dt(h).date())
                except: pass
                
        b_days = []
        delta_day = 1 if end_dt >= start_dt else -1
        current = start_dt
        while (current <= end_dt if delta_day > 0 else current >= end_dt):
            if current.weekday() < 5 and current not in holiday_dates:
                b_days.append(current.isoformat())
            current += timedelta(days=delta_day)
            
        return _success({"business_days": b_days, "count": len(b_days)})
    except Exception as e:
        return _error(str(e))


def add_business_days(dt_string: str, days: int, holidays: Optional[List[str]] = None) -> Dict[str, Any]:
    """Adds/subtracts business days, skipping weekends and holidays."""
    try:
        dt = _parse_dt(dt_string)
        orig_time = dt.timetz() if dt.tzinfo else dt.time()
        current_dt = dt.date()
        
        holiday_dates = set()
        if holidays:
            for h in holidays:
                try: holiday_dates.add(_parse_dt(h).date())
                except: pass
                
        sign = 1 if days >= 0 else -1
        remaining = abs(days)
        while remaining > 0:
            current_dt += timedelta(days=sign)
            if current_dt.weekday() < 5 and current_dt not in holiday_dates:
                remaining -= 1
                
        result_dt = datetime.combine(current_dt, orig_time)
        return _success({"datetime": result_dt.isoformat(), "added_business_days": days})
    except Exception as e:
        return _error(str(e))


def get_quarter(dt_string: str) -> Dict[str, Any]:
    """Returns the fiscal/calendar quarter (1-4) for a date."""
    try:
        dt = _parse_dt(dt_string)
        q = (dt.month - 1) // 3 + 1
        return _success({"quarter": q, "quarter_label": f"Q{q}", "month": dt.month, "year": dt.year})
    except Exception as e:
        return _error(str(e))


def get_week_number(dt_string: str) -> Dict[str, Any]:
    """Returns ISO week number and year."""
    try:
        dt = _parse_dt(dt_string)
        iso = dt.isocalendar()
        return _success({"iso_week_number": iso[1], "iso_year": iso[0], "date": dt.strftime("%Y-%m-%d")})
    except Exception as e:
        return _error(str(e))


def time_until(target_dt: str) -> Dict[str, Any]:
    """Calculates structured time remaining until a target datetime."""
    try:
        target = _parse_dt(target_dt)
        now = datetime.now(timezone.utc)
        if target.tzinfo:
            target = target.astimezone(timezone.utc)
            
        delta = target - now
        total_secs = delta.total_seconds()
        
        if total_secs < 0:
            return _success({"time_until": "target is in the past", "seconds": total_secs})
            
        days = int(total_secs // 86400)
        hours = int((total_secs % 86400) // 3600)
        minutes = int((total_secs % 3600) // 60)
        seconds = int(total_secs % 60)
        
        return _success({
            "days": days, "hours": hours, "minutes": minutes, "seconds": seconds,
            "total_seconds": total_secs,
            "iso8601_duration": f"P{days}DT{hours}H{minutes}M{seconds}S"
        })
    except Exception as e:
        return _error(str(e))


def schedule_cron_next(cron_expr: str, count: int = 5) -> Dict[str, Any]:
    """Calculates the next N occurrences of a standard 5-field cron expression."""
    try:
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            raise ValueError("Cron expression must have exactly 5 fields: min hour dom month dow")
            
        def parse_field(field_str: str, min_val: int, max_val: int) -> List[int]:
            if field_str == '*':
                return list(range(min_val, max_val + 1))
            values = set()
            for part in field_str.split(','):
                if '/' in part:
                    base, step = part.split('/')
                    step = int(step)
                    start = int(base) if base != '*' else min_val
                    values.update(range(start, max_val + 1, step))
                elif '-' in part:
                    s, e = part.split('-')
                    values.update(range(int(s), int(e) + 1))
                else:
                    values.add(int(part))
            return sorted([v for v in values if min_val <= v <= max_val])
            
        minutes, hours, days, months, cron_wdays = [
            parse_field(parts[0], 0, 59),
            parse_field(parts[1], 0, 23),
            parse_field(parts[2], 1, 31),
            parse_field(parts[3], 1, 12),
            parse_field(parts[4], 0, 7) # 0 & 7 = Sunday in cron
        ]
        
        # Map cron weekdays (0=Sun, 1=Mon...6=Sat, 7=Sun) to Python (0=Mon...6=Sun)
        cron_to_py = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6}
        py_wdays = sorted({cron_to_py[w] for w in cron_wdays})
        
        now = datetime.now(timezone.utc)
        results = []
        search_limit = now + timedelta(days=365)
        curr = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        
        while len(results) < count and curr < search_limit:
            if (curr.minute in minutes and
                curr.hour in hours and
                curr.day in days and
                curr.month in months and
                curr.weekday() in py_wdays):
                results.append(curr.isoformat())
            curr += timedelta(minutes=1)
            
        return _success({"next_occurrences": results, "cron_expression": cron_expr, "count": len(results)})
    except Exception as e:
        return _error(str(e))