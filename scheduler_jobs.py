import os
import threading
import time
from datetime import datetime, timedelta

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:
    BackgroundScheduler = None  # type: ignore
    print("[scheduler_jobs] APScheduler not installed; recurring jobs disabled.")

try:
    import pyttsx3
except Exception:
    pyttsx3 = None  # type: ignore
    print("[scheduler_jobs] pyttsx3 not installed; reminders will be printed.")


_day_plan: list[dict] = []
_day_plan_date: str | None = None
_scheduled_lock = threading.Lock()
_scheduled_keys: dict[str, float] = {}


def _prune_scheduled_keys(now_ts: float, max_age_hours: int = 48) -> None:
    cutoff = now_ts - max_age_hours * 3600
    stale = [key for key, ts in list(_scheduled_keys.items()) if ts < cutoff]
    for key in stale:
        _scheduled_keys.pop(key, None)

def _speak(text: str):
    import sys
    import platform
    
    # On macOS, use 'say' command with Samantha voice
    if platform.system() == "Darwin":
        import subprocess
        try:
            subprocess.run(["say", "-v", "Samantha", text], check=True, timeout=60)
            return
        except Exception:
            pass
    
    # Fallback to pyttsx3
    if pyttsx3 is None:
        print(text); return
    try:
        engine = pyttsx3.init()
        # Try to use Samantha voice
        try:
            voices = engine.getProperty("voices") or []
            for v in voices:
                name = getattr(v, "name", "").lower()
                if "samantha" in name:
                    engine.setProperty("voice", v.id)
                    break
        except Exception:
            pass
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception:
        print(text)

def drink_water():   _speak("Sir, please drink some water to stay hydrated.")
def lunch_reminder():_speak("It's 1 PM. Time for lunch!")
def rest_reminder(): _speak("Sir, please take a rest.")
def tea_break():     _speak("It's 5 PM. Time for a tea break!")

def announce():
    hour = datetime.now().hour
    if   5 <= hour < 12: greet="Good morning"
    elif 12 <= hour < 17:greet="Good afternoon"
    elif 17 <= hour < 21:greet="Good evening"
    else:                greet="Good evening"  # Use "Good evening" instead of "Good night"
    _speak(f"{greet}! I am Iraa, ready to help you today.")

def _speak_reminder_for_event(ev: dict):
    title = ev.get("summary") or ev.get("title") or "your event"
    when  = ev.get("when") or ev.get("start") or "soon"
    _speak(f"Reminder: {title} at {when}.")


def _format_when(local_dt: datetime) -> str:
    try:
        return local_dt.strftime("%I:%M %p on %d %b")
    except Exception:
        return local_dt.isoformat()


def _list_today_events(user_id: str):
    """Fetch today's Google Calendar events (local timezone)."""
    try:
        from google_calendar import list_today
        items = list_today(user_id)
        tzname = os.getenv("TIMEZONE", "Asia/Kolkata")
        import pytz, datetime as dt
        tz = pytz.timezone(tzname)
        today = dt.datetime.now(tz)
        upcoming = []
        for it in items:
            ev_id = it.get("id")
            start = (it.get("start") or {}).get("dateTime") or (it.get("start") or {}).get("date")
            if not start:
                continue
            try:
                from dateutil import parser as dtparser
                sdt = dtparser.isoparse(start)
                local_dt = sdt.astimezone(tz)
            except Exception:
                local_dt = today
            upcoming.append({
                "source": "calendar",
                "id": ev_id,
                "summary": it.get("summary", "(No title)"),
                "start_dt": local_dt,
                "when": _format_when(local_dt),
            })
        return upcoming
    except Exception as e:
        print(f"[day_plan] list_today events error: {e}")
        return []


def _list_local_schedules(user_id: str):
    """Fetch today's local schedules from DB.schedules if table exists."""
    try:
        from db import conn
        import datetime as dt
        tzname = os.getenv("TIMEZONE", "Asia/Kolkata")
        import pytz
        tz = pytz.timezone(tzname)
        today = dt.datetime.now(tz).date()
        with conn() as c:
            cur = c.cursor(dictionary=True)
            cur.execute("""
                SELECT id, item as summary, due_dt
                FROM schedules
                WHERE DATE(due_dt) = CURDATE()
                ORDER BY due_dt ASC
            """)
            rows = cur.fetchall() or []
        out = []
        for r in rows:
            due = r.get("due_dt")
            if not due:
                continue
            if hasattr(due, "tzinfo") and due.tzinfo is None:
                # assume server local -> convert to configured tz
                import datetime as dtt
                due = tz.localize(due) if isinstance(due, dtt.datetime) else tz.localize(dtt.datetime.combine(today, dtt.time.min))
            else:
                try:
                    due = due.astimezone(tz)
                except Exception:
                    pass
            out.append({
                "source": "local",
                "id": f"sch_{r.get('id')}",
                "summary": r.get("summary") or "(No title)",
                "start_dt": due,
                "when": _format_when(due),
            })
        return out
    except Exception as e:
        print(f"[day_plan] list_local_schedules error: {e}")
        return []


def _rebuild_day_plan(user_id: str):
    """Rebuild in-memory plan for today by aggregating calendar and local schedules."""
    global _day_plan, _day_plan_date
    tzname = os.getenv("TIMEZONE", "Asia/Kolkata")
    import pytz, datetime as dt
    tz = pytz.timezone(tzname)
    today_str = dt.datetime.now(tz).strftime("%Y-%m-%d")
    items = _list_today_events(user_id) + _list_local_schedules(user_id)

    # Mirror calendar events into schedules table (idempotent upsert)
    try:
        from db import upsert_schedule_from_calendar
        for it in items:
            if it.get("source") == "calendar":
                ev_id = it.get("id") or ""
                title = it.get("summary") or "(No title)"
                due = it.get("start_dt")
                if ev_id and due:
                    try:
                        upsert_schedule_from_calendar(user_id, title, due, ev_id)
                    except Exception as e:
                        print(f"[day_plan] upsert schedule error: {e}")
    except Exception as e:
        print(f"[day_plan] could not upsert schedules: {e}")

    # sort by time
    items.sort(key=lambda x: x.get("start_dt"))
    _day_plan = items
    _day_plan_date = today_str
    print(f"[day_plan] Rebuilt plan for {today_str} with {len(items)} items")
    return items


def _ensure_day_plan(user_id: str):
    tzname = os.getenv("TIMEZONE", "Asia/Kolkata")
    import pytz, datetime as dt
    tz = pytz.timezone(tzname)
    today_str = dt.datetime.now(tz).strftime("%Y-%m-%d")
    if _day_plan_date != today_str:
        _rebuild_day_plan(user_id)
    return _day_plan


def _morning_brief(user_id: str):
    plan = _ensure_day_plan(user_id)
    if not plan:
        _speak("Good morning. You have no scheduled items today.")
        return
    # Build concise summary
    parts = []
    for it in plan[:5]:  # limit to first 5 items for brevity
        parts.append(f"{it.get('when')}: {it.get('summary')}")
    more = "" if len(plan) <= 5 else f" and {len(plan)-5} more."
    _speak("Good morning. Here is your schedule: " + "; ".join(parts) + more)


def _list_upcoming_events(user_id: str, window_hours: int = 12):
    """Fetch upcoming calendar events within the next window_hours."""
    try:
        from google_calendar import ensure_access_token
        import requests, datetime as dt, pytz, os
        tzname = os.getenv("TIMEZONE", "Asia/Kolkata")
        tz = pytz.timezone(tzname)
        now = dt.datetime.now(tz)
        end = now + dt.timedelta(hours=window_hours)
        access = ensure_access_token(user_id)
        r = requests.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {access}"},
            params={
                "timeMin": now.isoformat(),
                "timeMax": end.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
            },
            timeout=30,
        )
        if not r.ok:
            print(f"[calendar_reminders] API error {r.status_code}: {r.text}")
            return []
        items = r.json().get("items", [])
        # Normalize to have local start datetime and human 'when'
        upcoming = []
        for it in items:
            ev_id = it.get("id")
            start = (it.get("start") or {}).get("dateTime") or (it.get("start") or {}).get("date")
            if not start:
                continue
            try:
                # Parse RFC3339 into aware dt
                from dateutil import parser as dtparser  # optional but robust
                sdt = dtparser.isoparse(start)
                local_dt = sdt.astimezone(tz)
            except Exception:
                # Fallback: naive parse
                local_dt = now
            upcoming.append({
                "id": ev_id,
                "summary": it.get("summary", "(No title)"),
                "start_dt": local_dt,
                "when": _format_when(local_dt),
            })
        return upcoming
    except Exception as e:
        print(f"[calendar_reminders] list_upcoming error: {e}")
        return []


def _list_upcoming_schedules(user_id: str, window_hours: int = 12):
    """Fetch upcoming entries from DB.schedules within the next window_hours."""
    try:
        from db import conn
    except Exception as e:
        print(f"[schedule_reminders] DB import error: {e}")
        return []

    tzname = os.getenv("TIMEZONE", "Asia/Kolkata")
    try:
        import pytz
        tz = pytz.timezone(tzname)
    except Exception:
        tz = None

    now = datetime.now(tz) if tz else datetime.now()
    end = now + timedelta(hours=window_hours)
    now_db = now.replace(tzinfo=None) if getattr(now, "tzinfo", None) else now
    end_db = end.replace(tzinfo=None) if getattr(end, "tzinfo", None) else end

    try:
        with conn() as c:
            cur = c.cursor(dictionary=True)
            cur.execute(
                """
                SELECT id, item, due_dt, note
                FROM schedules
                WHERE user_id=%s AND due_dt BETWEEN %s AND %s
                ORDER BY due_dt ASC
                """,
                (user_id, now_db, end_db),
            )
            rows = cur.fetchall() or []
    except Exception as e:
        print(f"[schedule_reminders] query error: {e}")
        return []

    upcoming = []
    for row in rows:
        note = (row.get("note") or "").strip().lower()
        if note.startswith("calendar:"):
            continue  # calendar entries handled separately

        due = row.get("due_dt")
        due_dt = None
        if isinstance(due, str):
            try:
                from dateutil import parser as dtparser

                due_dt = dtparser.parse(due)
            except Exception:
                due_dt = None
        elif hasattr(due, "isoformat"):
            due_dt = due
        if due_dt is None:
            continue

        if tz:
            if getattr(due_dt, "tzinfo", None):
                try:
                    due_dt = due_dt.astimezone(tz)
                except Exception:
                    pass
            else:
                try:
                    due_dt = tz.localize(due_dt)
                except Exception:
                    pass

        upcoming.append(
            {
                "id": f"sch_{row.get('id')}",
                "summary": row.get("item") or "(No title)",
                "start_dt": due_dt,
                "when": _format_when(due_dt),
            }
        )
    return upcoming


def _schedule_event_reminders(sched, user_id: str, leads_min: list[int]):
    """Schedule reminders for upcoming events, deduping already scheduled ones."""
    window_hours = _env_int("CALENDAR_REMINDER_WINDOW_HOURS", 12)
    events = _list_upcoming_events(user_id, window_hours)
    schedules = _list_upcoming_schedules(user_id, window_hours)
    items = events + schedules
    tzname = os.getenv("TIMEZONE", "Asia/Kolkata")
    try:
        import pytz
        tz = pytz.timezone(tzname)
    except Exception:
        tz = None
    now = datetime.now(tz) if tz else datetime.now()
    now_ts = time.time()
    for ev in items:
        ev_id = ev.get("id") or ""
        start_dt = ev.get("start_dt")
        if not ev_id or not isinstance(start_dt, datetime):
            continue
        for lead in leads_min:
            run_at = start_dt - timedelta(minutes=lead)
            if run_at <= now:
                continue  # past
            key = f"{ev_id}|{lead}"
            with _scheduled_lock:
                _prune_scheduled_keys(now_ts)
                if key in _scheduled_keys:
                    continue
                try:
                    run_at_ts = run_at.timestamp()
                except Exception:
                    run_at_ts = now_ts
                _scheduled_keys[key] = run_at_ts
            # Attach event info to the job
            def _job(ev=ev):
                _speak_reminder_for_event(ev)
            try:
                sched.add_job(_job, "date", run_date=run_at, id=f"ev_{ev_id}_{lead}")
                print(f"[calendar_reminders] Scheduled '{ev.get('summary')}' at {run_at} ({lead} min before)")
            except Exception as e:
                print(f"[calendar_reminders] schedule error: {e}")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_leads() -> list[int]:
    raw = os.getenv("CALENDAR_REMINDER_LEADS", "30,5").strip()
    out: list[int] = []
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            pass
    return out or [30, 5]


def start_recurring():
    if BackgroundScheduler is None:
        print("[scheduler_jobs] Recurring jobs disabled (APScheduler missing).")
        return None
    tzname = os.getenv("TIMEZONE", "Asia/Kolkata")
    sched = BackgroundScheduler(timezone=tzname)
    # Wellness reminders
    sched.add_job(drink_water,   "interval", minutes=30, id="water")
    sched.add_job(rest_reminder, "interval", minutes=90, id="rest")
    sched.add_job(lunch_reminder,"cron",     hour=13, minute=0, id="lunch")
    sched.add_job(tea_break,     "cron",     hour=17, minute=0, id="tea")

    # Calendar reminders: poll every 5 minutes to (re)schedule upcoming event reminders
    leads = _env_leads()
    def poll_and_schedule():
        user_id = os.getenv("DEFAULT_USER_ID", "me")
        _ensure_day_plan(user_id)
        _schedule_event_reminders(sched, user_id, leads)
    sched.add_job(poll_and_schedule, "interval", minutes=_env_int("CALENDAR_POLL_MINUTES", 5), id="calendar_poll")

    # Morning briefing at DAILY_BRIEF_HOUR (default 8)
    brief_hour = _env_int("DAILY_BRIEF_HOUR", 8)
    def daily_brief_job():
        user_id = os.getenv("DEFAULT_USER_ID", "me")
        _rebuild_day_plan(user_id)
        _morning_brief(user_id)
        _schedule_event_reminders(sched, user_id, leads)
    sched.add_job(daily_brief_job, "cron", hour=brief_hour, minute=0, id="daily_brief")

    # Initial build on startup
    try:
        user_id = os.getenv("DEFAULT_USER_ID", "me")
        _rebuild_day_plan(user_id)
        _schedule_event_reminders(sched, user_id, leads)
    except Exception as e:
        print(f"[day_plan] initial build error: {e}")

    sched.start()
    print("[scheduler_jobs] Recurring jobs started with calendar reminders and daily plan.")
    return sched
