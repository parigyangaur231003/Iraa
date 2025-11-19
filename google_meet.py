# google_meet.py
import datetime as dt
import uuid
import os
import pytz
import requests
from google_oauth import ensure_access_token

TZ = os.getenv("TIMEZONE", "Asia/Kolkata")
def _tz(): return pytz.timezone(TZ)

def _now_iso():
    now = dt.datetime.now(_tz()).replace(second=0, microsecond=0)
    return now.isoformat()

def _plus_minutes_iso(minutes=30):
    t = dt.datetime.now(_tz()).replace(second=0, microsecond=0) + dt.timedelta(minutes=minutes)
    return t.isoformat()

def create_instant_meet(user_id: str, title: str = "Instant Meeting") -> str:
    """
    Creates a short calendar event (now -> +30min) with conferenceData.createRequest,
    which returns a Google Meet link immediately. This avoids flaky Meet v2 payloads.
    Returns the Meet URL string.
    """
    access = ensure_access_token(user_id)

    start = _now_iso()
    end   = _plus_minutes_iso(30)
    body = {
        "summary": title,
        "start": {"dateTime": start},
        "end":   {"dateTime": end},
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4())  # must be unique per request
            }
        }
    }

    r = requests.post(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
        params={"conferenceDataVersion": 1},
        json=body,
        timeout=30,
    )
    r.raise_for_status()
    ev = r.json()

    # Prefer explicit conferenceData entryPoints; fall back to hangoutLink
    link = None
    conf = ev.get("conferenceData", {})
    for ep in conf.get("entryPoints", []) or []:
        if ep.get("entryPointType") == "video" and ep.get("uri"):
            link = ep["uri"]; break
    link = link or ev.get("hangoutLink")
    if not link:
        raise RuntimeError("Meet link not returned by Calendar API response.")
    return link