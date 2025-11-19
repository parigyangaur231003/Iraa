from datetime import datetime
import pytz, os

TZ = os.getenv("TIMEZONE", "Asia/Kolkata")

def local_now():
    return datetime.now(pytz.timezone(TZ))

def greeting():
    h = local_now().hour
    if 5 <= h < 12: return "Good morning"
    if 12 <= h < 17: return "Good afternoon"
    if 17 <= h < 22: return "Good evening"
    return "Good evening"  # Use "Good evening" instead of "Good night"

def current_time_str():
    return local_now().strftime("%I:%M %p")