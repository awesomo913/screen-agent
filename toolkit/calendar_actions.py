from __future__ import annotations

import calendar as pycalendar
import json
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytz
import recurring_ical_events
from icalendar import Alarm, Calendar, Event, Todo, vCalAddress, vText


DEFAULT_TZ = "UTC"


def _ok(**kwargs: Any) -> Dict[str, Any]:
    return {"success": True, **kwargs}


def _err(message: str, **kwargs: Any) -> Dict[str, Any]:
    return {"success": False, "error": message, **kwargs}


def _ensure_dt(value: Any, tz_name: str = DEFAULT_TZ) -> datetime:
    tz = pytz.timezone(tz_name)
    if isinstance(value, datetime):
        return value if value.tzinfo else tz.localize(value)
    if isinstance(value, date):
        return tz.localize(datetime.combine(value, time.min))
    if isinstance(value, str):
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else tz.localize(dt)
    raise ValueError(f"Unsupported datetime value: {value!r}")


def _to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return datetime.combine(value, time.min).isoformat()
    return str(value)


def _load_calendar_obj(calendar_path: str | Path) -> Calendar:
    path = Path(calendar_path)
    if not path.exists():
        raise FileNotFoundError(f"Calendar file not found: {path}")
    return Calendar.from_ical(path.read_bytes())


def _save_calendar_obj(cal: Calendar, calendar_path: str | Path) -> None:
    path = Path(calendar_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(cal.to_ical())


def _iter_components(cal: Calendar, name: str):
    for component in cal.walk():
        if component.name == name:
            yield component


def _find_by_uid(cal: Calendar, uid: str, component_name: str = "VEVENT"):
    for component in _iter_components(cal, component_name):
        if str(component.get("UID", "")) == uid:
            return component
    return None


def create_calendar(name: str, timezone: str) -> Dict[str, Any]:
    try:
        pytz.timezone(timezone)
        cal = Calendar()
        cal.add("prodid", "-//Screen Agent Toolkit//Calendar//EN")
        cal.add("version", "2.0")
        cal.add("x-wr-calname", name)
        cal.add("x-wr-timezone", timezone)
        return _ok(calendar=cal)
    except Exception as e:
        return _err(str(e))


def create_event(title: str, start: Any, end: Any, description: str = "", location: str = "", recurrence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        sdt = _ensure_dt(start)
        edt = _ensure_dt(end)
        event = Event()
        uid = f"evt-{int(datetime.now().timestamp() * 1_000_000)}"
        event.add("uid", uid)
        event.add("summary", title)
        event.add("dtstart", sdt)
        event.add("dtend", edt)
        event.add("description", description)
        event.add("location", location)
        event.add("dtstamp", datetime.utcnow())
        if recurrence:
            event.add("rrule", recurrence)
        return _ok(event=event, event_id=uid)
    except Exception as e:
        return _err(str(e))


def create_recurring_event(title: str, start: Any, end: Any, freq: str, interval: int, until: Any) -> Dict[str, Any]:
    recurrence = {"FREQ": freq, "INTERVAL": interval, "UNTIL": _ensure_dt(until)}
    return create_event(title, start, end, recurrence=recurrence)


def save_calendar(calendar_obj: Calendar, file_path: str | Path) -> Dict[str, Any]:
    try:
        _save_calendar_obj(calendar_obj, file_path)
        return _ok(path=str(file_path))
    except Exception as e:
        return _err(str(e))


def load_calendar(file_path: str | Path) -> Dict[str, Any]:
    try:
        return _ok(calendar=_load_calendar_obj(file_path))
    except Exception as e:
        return _err(str(e))


def delete_event(calendar_path: str | Path, event_id: str) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        target = _find_by_uid(cal, event_id)
        if not target:
            return _err("Event not found")
        cal.subcomponents.remove(target)
        _save_calendar_obj(cal, calendar_path)
        return _ok(deleted=event_id)
    except Exception as e:
        return _err(str(e))


def update_event(calendar_path: str | Path, event_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        event = _find_by_uid(cal, event_id)
        if not event:
            return _err("Event not found")
        mapping = {"title": "summary", "description": "description", "location": "location"}
        for key, value in updates.items():
            if key in ("start", "dtstart"):
                event["DTSTART"] = _ensure_dt(value)
            elif key in ("end", "dtend"):
                event["DTEND"] = _ensure_dt(value)
            else:
                event[mapping.get(key, key)] = value
        _save_calendar_obj(cal, calendar_path)
        return _ok(updated=event_id)
    except Exception as e:
        return _err(str(e))


def get_event(calendar_path: str | Path, event_id: str) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        event = _find_by_uid(cal, event_id)
        if not event:
            return _err("Event not found")
        return _ok(event={k: _to_iso(v.dt if hasattr(v, 'dt') else v) for k, v in event.items()})
    except Exception as e:
        return _err(str(e))


def list_events(calendar_path: str | Path, start_date: Any, end_date: Any) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        events = recurring_ical_events.of(cal).between(_ensure_dt(start_date), _ensure_dt(end_date))
        result = []
        for e in events:
            result.append({
                "uid": str(e.get("UID", "")),
                "summary": str(e.get("SUMMARY", "")),
                "start": _to_iso(e.decoded("DTSTART")),
                "end": _to_iso(e.decoded("DTEND")),
            })
        return _ok(events=result)
    except Exception as e:
        return _err(str(e))


def search_events(calendar_path: str | Path, query: str) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        q = query.lower()
        matches = []
        for e in _iter_components(cal, "VEVENT"):
            hay = " ".join(str(e.get(k, "")) for k in ("SUMMARY", "DESCRIPTION", "LOCATION")).lower()
            if q in hay:
                matches.append(str(e.get("UID")))
        return _ok(matches=matches)
    except Exception as e:
        return _err(str(e))


def merge_calendars(cal_paths: List[str | Path]) -> Dict[str, Any]:
    try:
        merged = Calendar()
        merged.add("prodid", "-//Merged Calendar//EN")
        merged.add("version", "2.0")
        for path in cal_paths:
            cal = _load_calendar_obj(path)
            for comp in cal.subcomponents:
                merged.add_component(comp)
        return _ok(calendar=merged)
    except Exception as e:
        return _err(str(e))


def export_calendar_json(calendar_path: str | Path, output_path: str | Path) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        data = []
        for e in _iter_components(cal, "VEVENT"):
            data.append({k: _to_iso(v.dt if hasattr(v, 'dt') else v) for k, v in e.items()})
        Path(output_path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        return _ok(path=str(output_path))
    except Exception as e:
        return _err(str(e))


def import_calendar_json(json_path: str | Path) -> Dict[str, Any]:
    try:
        data = json.loads(Path(json_path).read_text(encoding="utf-8"))
        cal = Calendar()
        cal.add("prodid", "-//Imported JSON Calendar//EN")
        cal.add("version", "2.0")
        for item in data:
            evt = Event()
            for k, v in item.items():
                evt.add(k.lower(), v)
            cal.add_component(evt)
        return _ok(calendar=cal)
    except Exception as e:
        return _err(str(e))


def check_conflict(calendar_path: str | Path, start: Any, end: Any) -> Dict[str, Any]:
    try:
        sdt, edt = _ensure_dt(start), _ensure_dt(end)
        events = list_events(calendar_path, sdt, edt)
        return _ok(conflict=bool(events.get("events")), events=events.get("events", []))
    except Exception as e:
        return _err(str(e))


def get_free_slots(calendar_path: str | Path, date: Any, work_start: int, work_end: int, duration_min: int) -> Dict[str, Any]:
    try:
        day = _ensure_dt(date)
        ws = day.replace(hour=work_start, minute=0, second=0)
        we = day.replace(hour=work_end, minute=0, second=0)
        busy = list_events(calendar_path, ws, we).get("events", [])
        cursor = ws
        free = []
        delta = timedelta(minutes=duration_min)
        for event in sorted(busy, key=lambda x: x["start"]):
            estart = _ensure_dt(event["start"])
            if estart - cursor >= delta:
                free.append((cursor.isoformat(), estart.isoformat()))
            cursor = max(cursor, _ensure_dt(event["end"]))
        if we - cursor >= delta:
            free.append((cursor.isoformat(), we.isoformat()))
        return _ok(slots=free)
    except Exception as e:
        return _err(str(e))


def add_reminder(calendar_path: str | Path, event_id: str, minutes_before: int) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        event = _find_by_uid(cal, event_id)
        if not event:
            return _err("Event not found")
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", f"Reminder for {event.get('SUMMARY', '')}")
        alarm.add("trigger", timedelta(minutes=-minutes_before))
        event.add_component(alarm)
        _save_calendar_obj(cal, calendar_path)
        return _ok(reminder_added=True)
    except Exception as e:
        return _err(str(e))


def remove_reminder(calendar_path: str | Path, event_id: str) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        event = _find_by_uid(cal, event_id)
        if not event:
            return _err("Event not found")
        event.subcomponents = [c for c in event.subcomponents if c.name != "VALARM"]
        _save_calendar_obj(cal, calendar_path)
        return _ok(reminder_removed=True)
    except Exception as e:
        return _err(str(e))


def get_upcoming_events(calendar_path: str | Path, hours_ahead: int) -> Dict[str, Any]:
    now = datetime.now(pytz.UTC)
    return list_events(calendar_path, now, now + timedelta(hours=hours_ahead))


def get_today_events(calendar_path: str | Path) -> Dict[str, Any]:
    today = datetime.now(pytz.UTC)
    start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    return list_events(calendar_path, start, start + timedelta(days=1))


def get_week_events(calendar_path: str | Path) -> Dict[str, Any]:
    now = datetime.now(pytz.UTC)
    return list_events(calendar_path, now, now + timedelta(days=7))


def get_month_events(calendar_path: str | Path, year: int, month: int) -> Dict[str, Any]:
    start = pytz.UTC.localize(datetime(year, month, 1))
    _, days = pycalendar.monthrange(year, month)
    end = start + timedelta(days=days)
    return list_events(calendar_path, start, end)


def get_recurring_instances(calendar_path: str | Path, event_id: str, start: Any, end: Any) -> Dict[str, Any]:
    try:
        events = list_events(calendar_path, start, end).get("events", [])
        filtered = [e for e in events if e["uid"] == event_id]
        return _ok(instances=filtered)
    except Exception as e:
        return _err(str(e))


def calculate_duration(start: Any, end: Any) -> Dict[str, Any]:
    try:
        delta = _ensure_dt(end) - _ensure_dt(start)
        return _ok(minutes=int(delta.total_seconds() // 60), seconds=int(delta.total_seconds()))
    except Exception as e:
        return _err(str(e))


def shift_event(calendar_path: str | Path, event_id: str, days: int, hours: int) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        event = _find_by_uid(cal, event_id)
        if not event:
            return _err("Event not found")
        delta = timedelta(days=days, hours=hours)
        event["DTSTART"] = event.decoded("DTSTART") + delta
        event["DTEND"] = event.decoded("DTEND") + delta
        _save_calendar_obj(cal, calendar_path)
        return _ok(shifted=True)
    except Exception as e:
        return _err(str(e))


def clone_event(calendar_path: str | Path, event_id: str, new_date: Any) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        event = _find_by_uid(cal, event_id)
        if not event:
            return _err("Event not found")
        start = event.decoded("DTSTART")
        end = event.decoded("DTEND")
        target = _ensure_dt(new_date)
        duration = end - start
        result = create_event(str(event.get("SUMMARY")), target, target + duration)
        if result["success"]:
            cal.add_component(result["event"])
            _save_calendar_obj(cal, calendar_path)
        return result
    except Exception as e:
        return _err(str(e))


def add_attendee(calendar_path: str | Path, event_id: str, name: str, email: str) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        event = _find_by_uid(cal, event_id)
        if not event:
            return _err("Event not found")
        attendee = vCalAddress(f"MAILTO:{email}")
        attendee.params["CN"] = vText(name)
        event.add("attendee", attendee)
        _save_calendar_obj(cal, calendar_path)
        return _ok(attendee_added=email)
    except Exception as e:
        return _err(str(e))


def remove_attendee(calendar_path: str | Path, event_id: str, email: str) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        event = _find_by_uid(cal, event_id)
        if not event:
            return _err("Event not found")
        attendees = event.get("ATTENDEE")
        if not attendees:
            return _ok(removed=False)
        if not isinstance(attendees, list):
            attendees = [attendees]
        filtered = [a for a in attendees if email.lower() not in str(a).lower()]
        if "ATTENDEE" in event:
            del event["ATTENDEE"]
        for a in filtered:
            event.add("attendee", a)
        _save_calendar_obj(cal, calendar_path)
        return _ok(removed=True)
    except Exception as e:
        return _err(str(e))


def get_attendees(calendar_path: str | Path, event_id: str) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        event = _find_by_uid(cal, event_id)
        if not event:
            return _err("Event not found")
        attendees = event.get("ATTENDEE", [])
        if not isinstance(attendees, list):
            attendees = [attendees]
        return _ok(attendees=[str(a) for a in attendees])
    except Exception as e:
        return _err(str(e))


def set_event_color(calendar_path: str | Path, event_id: str, color: str) -> Dict[str, Any]:
    return update_event(calendar_path, event_id, {"COLOR": color})


def get_events_by_category(calendar_path: str | Path, category: str) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        matches = []
        for e in _iter_components(cal, "VEVENT"):
            cats = str(e.get("CATEGORIES", ""))
            if category.lower() in cats.lower():
                matches.append(str(e.get("UID")))
        return _ok(matches=matches)
    except Exception as e:
        return _err(str(e))


def create_todo(summary: str, due_date: Any, priority: int) -> Dict[str, Any]:
    try:
        todo = Todo()
        uid = f"todo-{int(datetime.now().timestamp() * 1_000_000)}"
        todo.add("uid", uid)
        todo.add("summary", summary)
        todo.add("due", _ensure_dt(due_date))
        todo.add("priority", priority)
        return _ok(todo=todo, todo_id=uid)
    except Exception as e:
        return _err(str(e))


def complete_todo(calendar_path: str | Path, todo_id: str) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        todo = _find_by_uid(cal, todo_id, "VTODO")
        if not todo:
            return _err("Todo not found")
        todo["STATUS"] = "COMPLETED"
        todo["COMPLETED"] = datetime.utcnow()
        _save_calendar_obj(cal, calendar_path)
        return _ok(completed=True)
    except Exception as e:
        return _err(str(e))


def list_todos(calendar_path: str | Path) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        todos = [str(t.get("SUMMARY", "")) for t in _iter_components(cal, "VTODO")]
        return _ok(todos=todos)
    except Exception as e:
        return _err(str(e))


def get_overdue_todos(calendar_path: str | Path) -> Dict[str, Any]:
    try:
        cal = _load_calendar_obj(calendar_path)
        now = datetime.now(pytz.UTC)
        overdue = []
        for t in _iter_components(cal, "VTODO"):
            due = t.decoded("DUE") if "DUE" in t else None
            if due and due < now and str(t.get("STATUS", "")) != "COMPLETED":
                overdue.append(str(t.get("UID")))
        return _ok(overdue=overdue)
    except Exception as e:
        return _err(str(e))


def generate_daily_summary(calendar_path: str | Path, date: Any) -> Dict[str, Any]:
    events = list_events(calendar_path, _ensure_dt(date), _ensure_dt(date) + timedelta(days=1))
    return _ok(count=len(events.get("events", [])), events=events.get("events", []))


def generate_week_summary(calendar_path: str | Path, start_date: Any) -> Dict[str, Any]:
    events = list_events(calendar_path, _ensure_dt(start_date), _ensure_dt(start_date) + timedelta(days=7))
    return _ok(count=len(events.get("events", [])), events=events.get("events", []))


def count_events_by_day(calendar_path: str | Path, start: Any, end: Any) -> Dict[str, Any]:
    try:
        events = list_events(calendar_path, start, end).get("events", [])
        counts: Dict[str, int] = {}
        for e in events:
            key = _ensure_dt(e["start"]).date().isoformat()
            counts[key] = counts.get(key, 0) + 1
        return _ok(counts=counts)
    except Exception as e:
        return _err(str(e))


def get_busiest_day(calendar_path: str | Path, start: Any, end: Any) -> Dict[str, Any]:
    counts = count_events_by_day(calendar_path, start, end)
    if not counts["success"]:
        return counts
    data = counts["counts"]
    if not data:
        return _ok(day=None, count=0)
    day = max(data, key=data.get)
    return _ok(day=day, count=data[day])


def timezone_convert(dt: Any, from_tz: str, to_tz: str) -> Dict[str, Any]:
    try:
        source = pytz.timezone(from_tz)
        target = pytz.timezone(to_tz)
        value = _ensure_dt(dt, from_tz)
        if value.tzinfo is None:
            value = source.localize(value)
        return _ok(converted=value.astimezone(target).isoformat())
    except Exception as e:
        return _err(str(e))


def parse_natural_date(text: str) -> Dict[str, Any]:
    try:
        t = text.strip().lower()
        now = datetime.now()
        if t == "today":
            dt = now
        elif t == "tomorrow":
            dt = now + timedelta(days=1)
        elif t == "next week":
            dt = now + timedelta(days=7)
        else:
            dt = datetime.fromisoformat(text)
        return _ok(datetime=dt.isoformat())
    except Exception as e:
        return _err(f"Unable to parse date: {e}")
