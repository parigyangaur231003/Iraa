# google_calendar.py
import os
import re
import datetime as dt
import pytz
import requests
from google_oauth import ensure_access_token

TZ = os.getenv("TIMEZONE", "Asia/Kolkata")

# ---------- TZ helpers ----------
def _tz():
    return pytz.timezone(TZ)

def _localize(d: dt.datetime) -> str:
    if d.tzinfo is None:
        d = _tz().localize(d)
    return d.astimezone(_tz()).isoformat()

def _parse_iso_datetime(value: str) -> dt.datetime | None:
    """Return aware datetime from RFC3339/ISO string or None if parsing fails."""
    if not value:
        return None
    try:
        cleaned = value.strip().replace("Z", "+00:00")
        return dt.datetime.fromisoformat(cleaned)
    except Exception:
        return None

# ---------- Parsing helpers ----------
def _parse_relative(s: str) -> dt.datetime | None:
    """Handle 'now', 'in 15 minutes', 'in 2 hours', etc."""
    s = (s or "").strip().lower()
    now = dt.datetime.now(_tz()).replace(second=0, microsecond=0)
    
    if s in ("now", "right now", "immediately"):
        return now
    
    # "in X minutes/hours"
    m = re.match(r"in\s+(\d+)\s*(minute|min|minutes|mins)$", s)
    if m:
        return now + dt.timedelta(minutes=int(m.group(1)))
    
    m = re.match(r"in\s+(\d+)\s*(hour|hours|hr|hrs)$", s)
    if m:
        return now + dt.timedelta(hours=int(m.group(1)))
    
    # "X minutes/hours from now"
    m = re.match(r"(\d+)\s*(minute|min|minutes|mins)\s+from\s+now$", s)
    if m:
        return now + dt.timedelta(minutes=int(m.group(1)))
    
    m = re.match(r"(\d+)\s*(hour|hours|hr|hrs)\s+from\s+now$", s)
    if m:
        return now + dt.timedelta(hours=int(m.group(1)))
    
    return None

def _parse_today_tomorrow(s: str) -> dt.datetime | None:
    """Handle various natural language time formats."""
    s = (s or "").strip().lower()
    base = dt.datetime.now(_tz())
    
    # Patterns for "today" or "tomorrow"
    day_patterns = [
        (r"today\s+at\s+(\d{1,2}):(\d{2})$", 0),  # "today at 14:30"
        (r"today\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", 0),  # "today at 2 pm"
        (r"today\s+(\d{1,2}):(\d{2})$", 0),  # "today 14:30"
        (r"today\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", 0),  # "today 2 pm"
        (r"tomorrow\s+at\s+(\d{1,2}):(\d{2})$", 1),  # "tomorrow at 10:00"
        (r"tomorrow\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", 1),  # "tomorrow at 10 pm"
        (r"tomorrow\s+(\d{1,2}):(\d{2})$", 1),  # "tomorrow 10:00"
        (r"tomorrow\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", 1),  # "tomorrow 10 pm"
    ]
    
    for pattern, days_offset in day_patterns:
        m = re.match(pattern, s)
        if m:
            day = base.date() if days_offset == 0 else (base + dt.timedelta(days=days_offset)).date()
            
            if len(m.groups()) == 2:  # 24-hour format with colon
                hour, minute = int(m.group(1)), int(m.group(2))
            elif len(m.groups()) == 3 and m.group(3) in ('am', 'pm'):  # 12-hour format
                hour = int(m.group(1))
                minute = int(m.group(2)) if m.group(2) else 0
                is_pm = m.group(3) == "pm"
                if hour == 12:
                    hour = 0 if not is_pm else 12
                elif is_pm:
                    hour += 12
            else:  # 12-hour format without colon
                hour = int(m.group(1))
                minute = 0
                is_pm = m.group(2) == "pm" if len(m.groups()) > 1 else False
                if hour == 12:
                    hour = 0 if not is_pm else 12
                elif is_pm:
                    hour += 12
            
            return dt.datetime.combine(day, dt.time(hour=hour, minute=minute))
    
    return None

def _try_formats(s: str) -> dt.datetime | None:
    """Try common formats; return naive local datetime (will be localized later)."""
    s = (s or "").strip()
    fmts = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d",  # date only → default 09:00
    ]
    for f in fmts:
        try:
            x = dt.datetime.strptime(s, f)
            if f == "%Y-%m-%d":
                x = x.replace(hour=9, minute=0, second=0, microsecond=0)
            return x
        except ValueError:
            continue
    return None

def _parse_natural_language(dt_str: str) -> dt.datetime | None:
    """Use LLM to parse natural language time expressions as fallback."""
    try:
        from llm_groq import complete
        from prompts import SYSTEM_PROMPT
        
        if not complete:
            return None
        
        prompt = f"""Parse this time expression into a specific date and time in ISO format (YYYY-MM-DD HH:MM).
Current date/time: {dt.datetime.now(_tz()).strftime('%Y-%m-%d %H:%M')}
Time expression: "{dt_str}"

Respond ONLY with the ISO format datetime (YYYY-MM-DD HH:MM), nothing else.
Examples:
- "tomorrow at 10 pm" -> 2025-11-02 22:00
- "next Monday at 3" -> 2025-11-04 15:00
- "Friday evening" -> 2025-11-01 18:00

Time expression: {dt_str}"""
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        response = complete(messages, temperature=0.1)
        response = response.strip()
        
        # Try to extract ISO format from response
        iso_match = re.search(r'(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})', response)
        if iso_match:
            date_str = iso_match.group(1)
            hour = int(iso_match.group(2))
            minute = int(iso_match.group(3))
            parsed = dt.datetime.strptime(f"{date_str} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M")
            return parsed
    except Exception as e:
        print(f"[time_parse] LLM fallback error: {e}")
    
    return None

# ---------- Public: parse to RFC3339 local ----------
def iso_in_tz(dt_str: str) -> str:
    """
    Ultra-flexible parser that accepts time in any natural language format.
    Examples:
      - '2025-11-01 15:00'
      - 'today 14:30', 'tomorrow 10 pm', 'today at 2 pm'
      - 'now', 'in 15 minutes', 'in 2 hours'
      - 'next Monday at 3', 'Friday evening', 'tomorrow morning'
      - Any natural language time expression
    """
    if not dt_str or not dt_str.strip():
        raise ValueError("Please provide a date and time.")

    # Try relative time first
    rel = _parse_relative(dt_str)
    if rel:
        return _localize(rel)

    # Try today/tomorrow patterns
    tt = _parse_today_tomorrow(dt_str)
    if tt:
        return _localize(tt)

    # Try standard formats
    base = _try_formats(dt_str)
    if base:
        return _localize(base)

    # Last resort: Use LLM to parse natural language
    nl_parsed = _parse_natural_language(dt_str)
    if nl_parsed:
        return _localize(nl_parsed)

    raise ValueError(f"I couldn't understand the time format: '{dt_str}'. Please try saying it differently, like 'tomorrow at 10 pm' or 'today 2 PM'.")

# ---------- Create event (strict & explicit) ----------
def _mirror_event_to_schedule(user_id: str, title: str, start_iso: str, event_id: str | None):
    """Store a Google Calendar event inside schedules for local reminders."""
    if not event_id:
        return
    due_dt = _parse_iso_datetime(start_iso)
    if not due_dt:
        return
    try:
        from db import upsert_schedule_from_calendar
        upsert_schedule_from_calendar(user_id, title or "Untitled", due_dt, event_id)
    except Exception as e:
        print(f"[calendar] Failed to mirror event into schedules: {e}")


def create_event(user_id: str, title: str, start_iso: str, end_iso: str, attendees=None):
    """
    Creates a Calendar event with explicit timeZone fields and strict validation.
    start_iso/end_iso must be RFC3339 datetimes (with offset), e.g. 2025-11-01T15:00:00+05:30
    """
    # Validate times and ordering
    try:
        s = dt.datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        e = dt.datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        if e <= s:
            raise ValueError("End time must be after start time.")
    except Exception as ex:
        raise ValueError(
            f"Bad start/end datetime: {ex}\nGot start='{start_iso}', end='{end_iso}'"
        )

    access = ensure_access_token(user_id)
    tzname = _tz().zone
    body = {
        "summary": title or "Untitled",
        "start": {"dateTime": start_iso, "timeZone": tzname},
        "end":   {"dateTime": end_iso,   "timeZone": tzname},
    }
    if attendees:
        body["attendees"] = [{"email": a} for a in attendees if a]

    try:
        r = requests.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
            json=body,
            timeout=30,
        )
        if not r.ok:
            # Bubble up Google's JSON so you can see the exact cause
            raise RuntimeError(f"Calendar API error {r.status_code}: {r.text}")
        event = r.json()
        _mirror_event_to_schedule(user_id, body["summary"], start_iso, event.get("id"))
        return event
    except requests.RequestException as req_err:
        raise RuntimeError(f"Network/HTTP error calling Calendar API: {req_err}")

# ---------- List today's events ----------
def list_today(user_id: str):
    access = ensure_access_token(user_id)
    tz = _tz()
    start = tz.localize(dt.datetime.combine(dt.date.today(), dt.time.min)).isoformat()
    end   = tz.localize(dt.datetime.combine(dt.date.today(), dt.time.max)).isoformat()
    r = requests.get(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers={"Authorization": f"Bearer {access}"},
        params={"timeMin": start, "timeMax": end, "singleEvents": "true", "orderBy": "startTime"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("items", [])
