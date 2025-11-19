# agent.py
import os, sys, datetime as dt, re, time, random
from typing import Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

def _find_module_file(basename: str) -> str | None:
    """Find a file like 'basename.py' even if it has stray spaces or '.py.txt'."""
    want = (basename + ".py").lower()
    for name in os.listdir(HERE):
        n = name.replace("\u00A0", " ").strip().lower()  # normalize NBSP/space
        if n == want or n.startswith(basename.lower()) and (n.endswith(".py") or n.endswith(".py.txt")):
            return os.path.join(HERE, name)
    return None

def _load_local_module(name: str, path: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    sys.modules[name] = mod
    return mod


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except Exception:
        return default


_PROMPT_SPEED = max(0.2, min(1.0, _env_float("IRAA_PROMPT_SPEED", 0.35)))
_PROMPT_MIN_GAP = max(0.03, _env_float("IRAA_PROMPT_MIN_GAP", 0.05))


def _prompt_pause(seconds: float) -> None:
    """Shorten waits between Iraa's prompts so turnarounds feel snappier."""
    scaled = seconds * _PROMPT_SPEED
    time.sleep(scaled if scaled >= _PROMPT_MIN_GAP else _PROMPT_MIN_GAP)

_FILLER_WORDS = (
    "uh",
    "hmm",
    "well",
    "you know",
    "so",
    "alright",
    "okay, so",
    "let me think",
)

def _maybe_prefix_filler(text: str, probability: float) -> str:
    if probability <= 0 or not text:
        return text
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    if random.random() >= probability:
        return cleaned
    filler = random.choice(_FILLER_WORDS).strip()
    if not filler:
        return cleaned
    if cleaned[0].isupper():
        filler = filler[:1].upper() + filler[1:]
    prefix = f"{filler}," if filler[-1] not in ".!?," else filler
    return f"{prefix} {cleaned}"

def _speak_line(speak_fn, text: str, filler_probability: float = 0.0):
    if not text:
        return
    utterance = text.strip()
    if not utterance:
        return
    utterance = _maybe_prefix_filler(utterance, filler_probability)
    speak_fn(utterance)

def _speak_llm_response(speak_fn, text: str, first_sentence_prob: float = 0.55, followup_prob: float = 0.25):
    if not text:
        return
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        sentences = [text.strip()]
    for idx, sentence in enumerate(sentences):
        if sentence[-1] not in ".!?":
            sentence = f"{sentence}."
        prob = first_sentence_prob if idx == 0 else followup_prob
        _speak_line(speak_fn, sentence, filler_probability=prob)
        if idx < len(sentences) - 1:
            _prompt_pause(0.3)

def is_sleep_requested() -> bool:
    """Query app.is_sleep_requested() if available; otherwise assume not sleeping."""
    try:
        import app  # type: ignore
        fn = getattr(app, "is_sleep_requested", None)
        if callable(fn):
            return bool(fn())
    except Exception:
        pass
    return False

def _check_sleep() -> None:
    """Raise InterruptedError when sleep has been requested to abort current action."""
    if is_sleep_requested():
        raise InterruptedError("Sleep requested")

# --------- Email services (robust import) ----------
try:
    from services_email import draft_email, save_draft, send_email_mock
except Exception as e:
    print("[agent] services_email import failed ->", repr(e))
    try:
        path = _find_module_file("services_email")
        if not path: raise FileNotFoundError("services_email*.py not found in working folder")
        _load_local_module("services_email", path)
        from services_email import draft_email, save_draft, send_email_mock
        print(f"[agent] services_email loaded via path: {os.path.basename(path)}")
    except Exception as e2:
        print("[agent] services_email path-load failed ->", repr(e2))
        # Final fallbacks so app still works
        def _tmpl(to_email: str, purpose: str) -> Tuple[str, str]:
            subj = (purpose or "Follow-up").strip().capitalize()
            if len(subj) > 70: subj = subj[:67] + "..."
            today = dt.date.today().strftime("%d %b %Y")
            body = (f"Dear {to_email},\n\nI’m writing regarding {purpose}.\n\nBest regards,\n[Your Name]\n{today}")
            return subj, body
        def draft_email(to_email: str, purpose: str) -> Tuple[str, str]:
            return _tmpl(to_email or "", purpose or "a follow-up")
        def save_draft(user_id: str, to_email: str, subject: str, body: str) -> None:
            try:
                from db import conn
                with conn() as c:
                    cur = c.cursor()
                    cur.execute(
                        "INSERT INTO emails (user_id, recipient, subject, body, status) VALUES (%s,%s,%s,%s,'draft')",
                        (user_id, to_email, subject, body)
                    ); c.commit()
            except Exception as ex:
                print("[agent fallback] draft not saved:", ex)
        def send_email_mock(user_id: str, to_email: str, subject: str, body: str) -> dict:
            try:
                from google_gmail import send_email
                resp = send_email(user_id, to_email, subject, body)
                return {"status":"sent","id":resp.get("id")} if isinstance(resp, dict) else {"status":"failed"}
            except Exception as ex:
                return {"status":"failed","reason":str(ex)}

# --------- Other services ----------
from google_meet import create_instant_meet
from google_calendar import create_event, iso_in_tz
from google_gmail import list_recent
from services_telegram import send_message, read_messages
from services_pdf import create_llm_pdf_and_send_via_telegram
from services_spotify import (
    SpotifyApiError,
    SpotifyAuthError,
    SpotifyPlaybackError,
    describe_track,
    is_playing as spotify_is_playing,
    open_track,
    pause_playback,
    resume_playback,
    search_tracks,
)
from jokes import tell_joke

try:
    from llm_groq import complete
except Exception:
    complete = None

_SPOTIFY_PLAYBACK_ACTIVE = False


def set_spotify_playback_active(active: bool) -> None:
    """Toggle whether Spotify music is currently playing so the app can stay quiet."""
    global _SPOTIFY_PLAYBACK_ACTIVE
    _SPOTIFY_PLAYBACK_ACTIVE = bool(active)


def is_spotify_playback_active() -> bool:
    """Return True when Spotify playback is active and Iraa should remain silent."""
    return _SPOTIFY_PLAYBACK_ACTIVE

# ---------- Intent Detection ----------
def detect_intent(text: str) -> str:
    t = (text or "").lower()
    tokens = {token.strip(".,!?") for token in t.split()}
    
    # Email reading
    if any(k in t for k in ("read email","read my email","check email","show email","list email")): 
        return "email_read"
    
    # Email writing - more specific patterns
    if any(k in t for k in ("write email", "write an email", "write me an email", "draft email", 
                            "draft an email", "compose email", "send email", "email to", "mail to")):
        return "email"
    
    # Meeting
    if "meet" in t and "schedule" in t:                      return "meet_schedule"
    if "start" in t and "meet" in t:                         return "meet_instant"
    
    # Calendar
    if any(k in t for k in ("calendar","event","reminder")): return "calendar"
    
    # Telegram
    if "telegram" in t and "send" in t:                      return "telegram_send"
    if "telegram" in t and "read" in t:                      return "telegram_read"

    # Calls
    if any(k in t for k in ("call me", "make a call", "place a call", "dial me", "phone me")):
        return "call_me"
    
    # Travel & Info
    if any(k in t for k in ("flight", "flights", "fly", "flying")): return "flights"
    
    # Weather - detect city names in the query
    if any(k in t for k in ("weather", "temperature", "climate", "forecast", "how hot", "how cold")):
        return "weather"
    
    # News
    if "news" in t:                                          return "news"
    
    # Stocks
    if any(k in t for k in ("stock", "stocks", "share price", "market")): return "stocks"
    
    # Entertainment
    if "joke" in t:                                          return "joke"
    if any(k in t for k in (
        "pause music",
        "pause the music",
        "stop music",
        "stop the music",
        "pause song",
        "pause spotify",
        "pause play",
    )):
        return "spotify_pause"
    if any(k in t for k in (
        "resume music",
        "resume the music",
        "continue music",
        "continue the music",
        "play again",
        "unpause music",
        "unpause the music",
        "keep playing",
        "play music again",
    )):
        return "spotify_resume"
    if any(k in t for k in (
        "pause play",
        "play pause",
        "toggle music",
        "toggle the music",
        "toggle playback",
    )):
        return "spotify_toggle"
    if any(k in t for k in (
        "change music",
        "change the music",
        "next song",
        "next track",
        "skip song",
        "skip the song",
        "skip track",
        "skip the track",
        "play something else",
    )):
        return "spotify_next"
    if any(k in t for k in (
        "spotify",
        "play music",
        "play some music",
        "play a song",
        "play song",
        "play track",
        "play something",
    )):
        return "spotify_play"
    if "time" in t:                                          return "ask_time"

    # Schedule queries
    if any(k in t for k in ("what's my schedule", "whats my schedule", "my schedule today", "today's schedule", "todays schedule", "agenda today", "plan for today")):
        return "schedule_today"
    if any(k in t for k in ("next meeting", "next event", "what's next", "whats next")):
        return "schedule_next"

    # Calendar reminder controls
    if any(k in t for k in ("enable calendar reminders", "turn on calendar reminders")):
        return "calrem_enable"
    if any(k in t for k in ("disable calendar reminders", "turn off calendar reminders")):
        return "calrem_disable"
    if any(k in t for k in ("refresh calendar reminders", "refresh my reminders")):
        return "calrem_refresh"
    if any(k in t for k in ("morning briefing", "give me a morning brief", "daily briefing")):
        return "calrem_brief_now"
    if "set reminder leads" in t or "set reminder lead" in t:
        return "calrem_set_leads"

    # Location lookup
    if any(k in t for k in (
        "where am i",
        "what is my location",
        "what's my location",
        "my current location",
        "current location"
    )):
        return "location_query"
    
    # PDF generation
    if "pdf" in t and any(k in t for k in ("create a pdf file ", "make me a pdf file", "generate a pdf", "draft a pdf", "prepare a pdf", "send")):
        return "pdf_create"

    # Chat history controls
    if any(k in t for k in ("chat history", "conversation history", "chat log", "chat logs", "conversation log")):
        if any(k in t for k in ("delete", "clear", "erase", "remove", "wipe", "forget")):
            return "chat_history_delete"
        return "chat_history_read"
    if any(k in t for k in ("clear chats", "clear chat", "delete chats", "delete conversation", "erase conversation", "wipe conversation")):
        return "chat_history_delete"
    if any(k in t for k in ("read chats", "read chat", "show chats", "show conversation", "review conversation", "recall conversation", "list chats")):
        return "chat_history_read"

    # Casual conversation
    if "conversation" in t and ("history" in t or "log" in t):
        pass  # handled in chat history block above
    else:
        conversation_triggers = (
            "have a conversation",
            "have conversation",
            "let's have a conversation",
            "lets have a conversation",
            "let's chat",
            "lets chat",
            "casual chat",
            "do a casual chat",
            "talk to me",
            "talk with me",
            "chat with me",
            "keep me company",
            "chat casually",
            "let's talk",
            "lets talk",
            "talk for a bit",
        )
        if any(phrase in t for phrase in conversation_triggers):
            return "casual_chat"

    personal_check = (
        "how are you",
        "how're you",
        "how are u",
        "how are ya",
        "how r you",
        "how r u",
        "how's it going",
        "hows it going",
        "how have you been",
        "how've you been",
        "what's up",
        "whats up",
        "what is up",
        "how's life",
        "hows life",
        "how is life",
        "how's everything",
        "hows everything",
        "how are things",
        "how's your day",
        "hows your day",
        "who are you",
        "what are you",
        "what is your name",
        "what's your name",
        "whats your name",
        "introduce yourself",
        "tell me about yourself",
        "are you there",
        "you there",
        "are you awake",
        "are you listening",
        "are you online",
    )
    if any(phrase in t for phrase in personal_check):
        return "personal_status"

    # Smalltalk
    if any(k in t for k in ("hello","hi","hey","good morning","good evening","good night","thank","bye")):
        return "smalltalk"
    
    # If it's a question or information request, use LLM
    if tokens & {"information", "info", "details", "detail", "what", "how"}:
        return "question"
    if any(k in t for k in (
        "what",
        "who",
        "when",
        "where",
        "why",
        "how",
        "tell me",
        "explain",
        "describe",
        "what is",
        "what are",
        "what does",
        "can you",
        "could you",
    )):
        return "question"
    
    return "unknown"

def _infer_chat_history_role(user_text: str) -> Optional[str]:
    u = (user_text or "").lower()
    if not u:
        return None
    if any(term in u for term in ("assistant", "assistant field", "your replies", "your responses", "iraa's messages", "bot messages")):
        return "assistant"
    if any(term in u for term in ("user", "my messages", "my chats", "from me", "i said", "my history", "user field", "my entries", "mine")):
        return "user"
    return None

def _infer_chat_history_limit(user_text: str, default: int = 5, max_limit: int = 25) -> int:
    u = (user_text or "").lower()
    if not u:
        return default
    match = re.search(r"(?:last|recent|past)\s+(\d+)", u)
    if not match:
        match = re.search(r"(\d+)\s+(?:entries|lines|messages|chats)", u)
    if match:
        try:
            val = int(match.group(1))
            return max(1, min(val, max_limit))
        except Exception:
            return default
    return default

def _infer_chat_history_keyword(user_text: str) -> Optional[str]:
    if not user_text:
        return None
    quoted = re.findall(r"[\"']([^\"']+)[\"']", user_text)
    if quoted:
        return quoted[-1].strip()[:100]
    lowered = user_text.lower()
    for marker in ("about", "regarding", "containing", "with keyword", "with phrase"):
        idx = lowered.find(marker)
        if idx != -1:
            snippet = user_text[idx + len(marker):].strip(" :,-")
            if snippet:
                words = snippet.split()
                candidate = " ".join(words[:4]).strip(" .,!?:;")
                if candidate:
                    return candidate[:100]
    return None

def _chat_history_filters(user_text: str, default_limit: int = 5) -> Tuple[Optional[str], Optional[str], int]:
    role = _infer_chat_history_role(user_text)
    keyword = _infer_chat_history_keyword(user_text)
    limit = _infer_chat_history_limit(user_text, default=default_limit)
    return role, keyword, limit

def _describe_chat_history_scope(role: Optional[str], keyword: Optional[str]) -> str:
    base = "chat entries"
    if role == "assistant":
        base = "assistant responses"
    elif role == "user":
        base = "your messages"
    if keyword:
        return f'{base} containing "{keyword}"'
    return base

# ---------- Handlers ----------
def handle_smalltalk(speak, utter: str):
    u = (utter or "").lower()
    resp = None
    if   "good morning" in u: resp = "Good morning, sir! How's your day kicking off?"
    elif "good evening" in u: resp = "Good evening, sir! How did your day go?"
    elif "good night"  in u:  resp = "Good night, sir. Sleep well and I'll be here when you wake."
    elif "thank" in u:        resp = "Anytime, sir! Always happy to help."
    elif "bye" in u:          resp = "Bye for now, sir. Call me back whenever you need me."
    elif any(w in u for w in ("hello","hi","hey")): resp = "Hi there, sir! What can I do for you?"
    else: resp = "I'm right here if you need anything else, sir."
    _speak_line(speak, resp, filler_probability=0.45)

def handle_personal_status(speak, utter: str):
    u = (utter or "").lower()
    how_are = (
        "how are you",
        "how're you",
        "how are u",
        "how are ya",
        "how r you",
        "how r u",
        "how's it going",
        "hows it going",
        "how have you been",
        "how've you been",
        "what's up",
        "whats up",
        "what is up",
        "how's life",
        "hows life",
        "how is life",
        "how's everything",
        "hows everything",
        "how are things",
        "how's your day",
        "hows your day",
    )
    identity = (
        "who are you",
        "what are you",
        "what is your name",
        "what's your name",
        "whats your name",
        "introduce yourself",
        "tell me about yourself",
    )
    presence = (
        "are you there",
        "you there",
        "are you awake",
        "are you listening",
        "are you online",
    )
    if any(phrase in u for phrase in how_are):
        responses = [
            "I'm running smoothly and keeping everything on track for you, sir. How are you feeling?",
            "Doing great, sir—systems are green and I'm ready for whatever you need.",
            "Feeling sharp and attentive, sir. Just say the word and I'll jump in.",
        ]
    elif any(phrase in u for phrase in identity):
        responses = [
            "I'm Iraa, your Intelligent Responsive Agentic Assistant, dedicated to keeping your day organized.",
            "I'm Iraa—your AI partner for calendars, meetings, and whatever technical help you need.",
        ]
    elif any(phrase in u for phrase in presence):
        responses = [
            "Always here and listening, sir.",
            "Yes sir, I'm right here—ready when you are.",
        ]
    else:
        responses = [
            "Still by your side whenever you need me, sir.",
            "Here for you anytime, sir.",
        ]
    _speak_line(speak, random.choice(responses), filler_probability=0.55)

def handle_casual_chat(speak, utter: str):
    """Keep things conversational when the user just wants to chat."""
    prompt = None
    if complete:
        prompt = (
            "You are Iraa, a friendly executive AI assistant who keeps conversations light."
            " Reply to the user's message in 2 short sentences and end with an inviting follow-up question."
            " Avoid repeating the same follow-up line every time."
        )
    try:
        if prompt and complete:
            response = complete(f"{prompt}\nUser: {utter}\nIraa:")
            text = (response or "").strip()
            if text:
                _speak_llm_response(speak, text, first_sentence_prob=0.6, followup_prob=0.35)
                return
    except Exception as exc:
        print(f"[agent] Casual chat LLM error: {exc}")
    # Fallback if LLM fails or unavailable
    fallback_lines = [
        "I'd love to chat, sir. What's catching your interest today?",
        "I'm all ears—tell me what's on your mind lately.",
        "Sure, let's just talk. How's your day feeling so far?",
        "Happy to keep you company. Anything fun or stressful happening?",
    ]
    # Rotate using utter hash so it doesn't sound repetitive
    idx = abs(hash(utter)) % len(fallback_lines)
    _speak_line(speak, fallback_lines[idx], filler_probability=0.4)

def handle_time(speak):
    now = dt.datetime.now().strftime("%I:%M %p"); speak(f"It's {now} right now, sir.")

def handle_joke(speak):
    try:
        joke = tell_joke()
        speak(f"Here's something to make you smile, sir: {joke}")
    except Exception:
        speak("Here's one for you, sir: Why do programmers prefer dark mode? Because light attracts bugs.")


def handle_schedule_today(speak, user_id: str):
    try:
        # Import scheduler plan cache via functions
        from scheduler_jobs import _ensure_day_plan  # type: ignore
        plan = _ensure_day_plan(user_id)
        if not plan:
            speak("Looks like you have a free day today, sir. No meetings on the calendar.")
            return
        # Read top N items
        top = plan[:5]
        parts = []
        for it in top:
            when = it.get("when") or "soon"
            title = it.get("summary") or "(no title)"
            parts.append(f"{when}: {title}")
        speak("Here's what you have coming up today, sir: " + "; ".join(parts) + ("." if parts else ""))
    except Exception as e:
        print(f"[schedule_today] Error: {e}")
        speak("I couldn't retrieve today's schedule.")


def handle_schedule_next(speak, user_id: str):
    try:
        from scheduler_jobs import _ensure_day_plan  # type: ignore
        from datetime import datetime
        plan = _ensure_day_plan(user_id)
        if not plan:
            speak("You don't have any more items scheduled today, sir.")
            return
        # Find first item in the future
        now = datetime.now()
        upcoming = None
        for it in plan:
            dt = it.get("start_dt")
            if hasattr(dt, "timestamp") and dt > now:
                upcoming = it
                break
        if not upcoming:
            # If nothing in future, say last item
            last = plan[-1]
            speak(f"The last thing on your calendar today was {last.get('summary')} at {last.get('when')}, sir.")
            return
        speak(f"Up next, sir: {upcoming.get('summary')} at {upcoming.get('when')}.")
    except Exception as e:
        print(f"[schedule_next] Error: {e}")
        speak("I couldn't determine your next item.")


def handle_calrem_enable(speak):
    try:
        import os
        os.environ["CALREM_ENABLED"] = "1"
        speak("Calendar reminders are enabled.")
    except Exception as e:
        print(f"[calrem_enable] Error: {e}")
        speak("I couldn't enable calendar reminders.")


def handle_calrem_disable(speak):
    try:
        import os
        os.environ["CALREM_ENABLED"] = "0"
        speak("Calendar reminders are disabled.")
    except Exception as e:
        print(f"[calrem_disable] Error: {e}")
        speak("I couldn't disable calendar reminders.")


def handle_calrem_refresh(speak, user_id: str):
    try:
        from scheduler_jobs import _rebuild_day_plan, _schedule_event_reminders  # type: ignore
        import os
        leads_raw = os.getenv("CALENDAR_REMINDER_LEADS", "30,5")
        leads = []
        for p in leads_raw.split(','):
            p = p.strip()
            if p.isdigit():
                leads.append(int(p))
        if not leads:
            leads = [30, 5]
        speak("Refreshing calendar reminders.")
        _rebuild_day_plan(user_id)
        # Scheduler instance isn't directly accessible; poller job will pick up.
        # This call is a hint; actual scheduling occurs in scheduler_jobs via polling.
    except Exception as e:
        print(f"[calrem_refresh] Error: {e}")
        speak("I couldn't refresh calendar reminders.")


def handle_calrem_brief_now(speak, user_id: str):
    try:
        from scheduler_jobs import _morning_brief  # type: ignore
        _morning_brief(user_id)
    except Exception as e:
        print(f"[calrem_brief_now] Error: {e}")
        speak("I couldn't give the morning briefing right now.")


def handle_calrem_set_leads(speak, user_text: str):
    try:
        import re, os
        nums = [int(n) for n in re.findall(r"(\d+)", user_text or "")]
        if not nums:
            speak("Please specify the minutes, like set reminder leads to fifteen and five minutes.")
            return
        os.environ["CALENDAR_REMINDER_LEADS"] = ",".join(str(n) for n in nums)
        speak("Updated reminder lead times. I'll use them from the next reminder cycle.")
    except Exception as e:
        print(f"[calrem_set_leads] Error: {e}")
        speak("I couldn't update the reminder lead times.")


def _extract_pdf_instruction(user_text: str) -> str:
    words = (user_text or "").strip()
    if not words:
        return ""
    lowered = words.lower()
    if "pdf" not in lowered:
        return words
    junk = {"create", "generate", "make", "draft", "prepare", "a", "an", "the", "pdf", "document", "file", "please"}
    cleaned = []
    for token in words.replace(".", " ").replace(",", " ").split():
        if token.lower() in junk:
            continue
        cleaned.append(token)
    return " ".join(cleaned).strip()


def action_pdf_create(speak, listen, user_id, user_text: str = ""):
    import os
    import time

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token:
        speak("Telegram bot token is not configured. Please set TELEGRAM_BOT_TOKEN in your environment variables.")
        return
    if not chat_id or chat_id == "your_telegram_chat_id":
        speak("Telegram chat ID is not configured. Please set TELEGRAM_CHAT_ID in your environment variables.")
        return

    instruction = _extract_pdf_instruction(user_text)
    if not instruction:
        speak("What should the PDF cover, sir?")
        _prompt_pause(0.2)
        instruction = (listen() or "").strip()
    if not instruction:
        speak("I didn't catch the content. Let's try again later.")
        return

    speak("What filename should I use? Say skip to use the default document name.")
    _prompt_pause(0.2)
    filename_input = (listen() or "").strip()
    filename = "document.pdf"
    if filename_input and filename_input.lower() not in {"skip", "default"}:
        filename = filename_input if filename_input.lower().endswith(".pdf") else f"{filename_input}.pdf"

    speak("Would you like to add a caption for Telegram? Say skip to continue without one.")
    _prompt_pause(0.2)
    caption_input = (listen() or "").strip()
    caption = None if not caption_input or caption_input.lower() in {"skip", "no"} else caption_input

    try:
        speak("Drafting the PDF content now, sir.")
        result = create_llm_pdf_and_send_via_telegram(
            instruction=instruction,
            filename=filename,
            caption=caption,
            chat_id=chat_id,
        )
    except Exception as e:
        print(f"[pdf_create] Error: {e}")
        speak("I couldn't create or send the PDF. Please check the logs for details.")
        return

    status = result.get("status")
    pdf_path = result.get("file_path")
    llm_text = result.get("llm_text", "")

    if status == "sent":
        speak("The PDF has been created and sent to Telegram successfully.")
    else:
        speak("I created the PDF but sending to Telegram seems to have failed. Please check your bot settings.")

    # Give the user a brief preview of the generated text.
    if llm_text:
        preview = llm_text.splitlines()
        if preview:
            speak("Here's a quick preview of the content.")
            for line in preview[:2]:
                if line.strip():
                    speak(line.strip())
                    _prompt_pause(0.1)

    if pdf_path:
        print(f"[pdf_create] PDF saved at: {pdf_path}")

def action_location_query(speak, user_id):
    """Answer user's current location using saved data or IP-based detection."""
    try:
        from location_utils import get_user_location, get_current_location
        details = get_user_location(user_id) or {}
        city = get_current_location(user_id)
        if city and city != "Unknown":
            region = details.get("region") or ""
            country = details.get("country") or ""
            parts = [p for p in [city, region, country] if p]
            speak("You are in " + ", ".join(parts) + ".")
        else:
            speak("I couldn't determine your location.")
    except Exception as e:
        print(f"[location_query] Error: {e}")
        speak("I couldn't retrieve your location right now.")

def action_flights(speak, listen, user_id):
    """Handle flight information requests."""
    import time
    try:
        _check_sleep()
        from serp_api import get_flight_info
        
        speak("Where are you flying from?")
        _prompt_pause(0.3)
        _check_sleep()
        origin = (listen() or "").strip()
        if not origin:
            speak("I didn't catch the origin. Let's try again later.")
            return
        if is_sleep_requested():
            return
        
        speak("Where are you flying to?")
        _prompt_pause(0.3)
        _check_sleep()
        destination = (listen() or "").strip()
        if not destination:
            speak("I didn't catch the destination. Let's try again later.")
            return
        if is_sleep_requested():
            return
        
        speak("What date are you traveling? You can say the date or 'tomorrow' or skip for today.")
        _prompt_pause(0.3)
        _check_sleep()
        date_input = (listen() or "").strip().lower()
        date = None
        if date_input and date_input != "skip" and date_input != "today":
            # Try to parse date - simple parsing for common formats
            from google_calendar import iso_in_tz
            try:
                # Extract just the date part
                parsed = iso_in_tz(date_input)
                date = parsed.split('T')[0]  # Get YYYY-MM-DD format
            except:
                pass  # Use None if parsing fails
        
        speak(f"Flights from {origin} to {destination}.")
        
        try:
            result = get_flight_info(origin, destination, date)
        except Exception as e:
            error_msg = str(e)
            print(f"[flights] API error: {error_msg}")
            if "400" in error_msg or "Bad Request" in error_msg:
                speak(f"I couldn't find flights for those locations. The SerpAPI service may not support these airport codes, or there might be an issue with the API configuration. Please try checking flights on Google Flights directly.")
                speak(f"For reference, I converted {origin} and {destination} to airport codes. You can also try saying the airport codes directly, like 'JAI' or 'DEL'.")
            elif "SERP_API_KEY" in error_msg:
                speak("SerpAPI key is not configured. Please set SERP_API_KEY in your environment variables.")
            else:
                speak(f"I encountered an error while searching for flights: {error_msg}")
            return
        
        if "error" in result:
            speak(f"I couldn't find flight information. {result.get('error', 'Please check your SerpAPI key and try again.')}")
            return
        
        # Try to extract flight data from different response structures
        flights = result.get("flights", [])
        best_flights = result.get("best_flights", [])
        
        # If no flights in standard format, check for alternative formats
        if not flights and best_flights:
            # Extract flights from best_flights structure
            for best in best_flights:
                if isinstance(best, dict) and "flights" in best:
                    flights.extend(best.get("flights", []))
        
        if not flights:
            # Try another approach - check if there's search metadata
            if "search_parameters" in result:
                speak(f"Flight options found, but couldn't parse the detailed information.")
                speak(f"Please check Google Flights directly.")
            else:
                speak(f"No flights from {origin} to {destination}. Please try using airport codes like JAI for Jaipur or DEL for Delhi.")
            return
        
        speak(f"Here are the top {min(3, len(flights))} flight options:")
        _prompt_pause(0.1)
        
        # Save flight searches to database
        try:
            from db import save_flight
            from serp_api import _normalize_location
            origin_code = _normalize_location(origin)
            dest_code = _normalize_location(destination)
            for flight in flights[:3]:
                airline = flight.get("airline", "Unknown airline")
                price = flight.get("price", flight.get("total_price", "price not available"))
                duration = flight.get("duration", "duration not available")
                stops = flight.get("stops", flight.get("number_of_stops", 0))
                save_flight(user_id, origin_code, dest_code, date, airline, str(price), str(duration), stops)
        except Exception as db_err:
            print(f"[flights] Could not save to DB: {db_err}")
        
        for i, flight in enumerate(flights[:3], 1):
            airline = flight.get("airline", "Unknown airline")
            # Clean airline name to remove any URLs
            import re
            airline_clean = re.sub(r'https?://\S+|www\.\S+', '', airline).strip()
            
            price = flight.get("price", flight.get("total_price", "price not available"))
            # Clean price to remove URLs
            price_clean = re.sub(r'https?://\S+|www\.\S+', '', str(price)).strip()
            
            duration = flight.get("duration", "duration not available")
            stops = flight.get("stops", flight.get("number_of_stops", 0))
            stops_text = "direct flight" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}"
            
            speak(f"Option {i}: {airline_clean}, {price_clean}, {duration}, {stops_text}.")
            _prompt_pause(0.2)
        
    except RuntimeError as e:
        error_msg = str(e)
        print(f"[flights] Error: {error_msg}")
        if "SERP_API_KEY" in error_msg:
            speak("SerpAPI key is not configured. Please set SERP_API_KEY in your environment variables.")
        else:
            speak(f"I couldn't get flight information. {error_msg}")
    except Exception as e:
        error_msg = str(e)
        print(f"[flights] Error: {error_msg}")
        import traceback
        traceback.print_exc()
        speak(f"I encountered an error while searching for flights. Please try again.")

def action_news(speak, listen, user_id):
    """Handle news information requests."""
    import time
    try:
        _check_sleep()
        from serp_api import get_news
        
        speak("What topic would you like to know about?")
        _prompt_pause(0.1)
        _check_sleep()
        query = (listen() or "").strip()
        
        if not query:
            query = "technology"  # Default to technology news
            speak("News about technology.")
        else:
            speak(f"News about {query}.")
        
        result = get_news(query, num_results=5)
        
        if "error" in result:
            speak(f"I couldn't fetch news. {result.get('error', 'Please check your SerpAPI key and try again.')}")
            return
        
        articles = result.get("articles", [])
        if not articles:
            speak(f"No news articles about {query}. Please try a different topic.")
            return
        
        speak(f"Here are the top {len(articles)} news articles:")
        _prompt_pause(0.1)
        
        # Save news articles to database
        try:
            from db import save_news
            for article in articles[:5]:
                title = article.get("title", "No title")
                source = article.get("source", "Unknown source")
                
                # Extract clean source name from dict/list/string
                source_name = ""
                if isinstance(source, dict):
                    source_name = str(source.get("name") or source.get("title") or "Unknown source").strip()
                elif isinstance(source, (list, tuple)):
                    parts = []
                    for s in source:
                        if isinstance(s, dict):
                            n = s.get("name") or s.get("title")
                            if n:
                                parts.append(str(n))
                        elif isinstance(s, str):
                            parts.append(s)
                    source_name = ", ".join([p for p in parts if p]) or "Unknown source"
                elif isinstance(source, str):
                    source_name = source.strip()
                else:
                    source_name = "Unknown source"
                
                snippet = article.get("snippet", "")
                link = article.get("link", "")
                save_news(user_id, query, title, source_name, snippet, link)
        except Exception as db_err:
            print(f"[news] Could not save to DB: {db_err}")
        
        for i, article in enumerate(articles[:5], 1):
            title = article.get("title", "No title")
            source = article.get("source", "")
            snippet = article.get("snippet", "")
            
            # Remove any URLs from title or snippet before speaking
            import re
            title_clean = re.sub(r'https?://\S+|www\.\S+', '', title).strip()
            snippet_clean = re.sub(r'https?://\S+|www\.\S+', '', snippet).strip() if snippet else ""

            # Normalize source to a clean string (handle dict/list from API)
            source_name = ""
            if isinstance(source, dict):
                source_name = str(source.get("name") or source.get("title") or "").strip()
            elif isinstance(source, (list, tuple)):
                parts = []
                for s in source:
                    if isinstance(s, dict):
                        n = s.get("name") or s.get("title")
                        if n:
                            parts.append(str(n))
                    elif isinstance(s, str):
                        parts.append(s)
                source_name = ", ".join([p for p in parts if p])
            elif isinstance(source, str):
                source_name = source.strip()
            # Clean any URLs from source and avoid speaking raw objects
            if source_name:
                source_name = re.sub(r'https?://\S+|www\.\S+', '', source_name).strip()
            
            speak(f"Article {i}: {title_clean}." + (f" From {source_name}." if source_name else ""))
            if snippet_clean and len(snippet_clean) < 100:
                _prompt_pause(0.1)
                speak(snippet_clean)
            _prompt_pause(0.2)
        
    except InterruptedError:
        # Sleep mode requested - exit silently
        return
    except RuntimeError as e:
        error_msg = str(e)
        print(f"[news] Error: {error_msg}")
        import traceback
        traceback.print_exc()
        if "SERP_API_KEY" in error_msg:
            speak("SerpAPI key is not configured. Please set SERP_API_KEY in your environment variables.")
        elif "400" in error_msg or "Bad Request" in error_msg:
            speak(f"I'm having trouble accessing news through the SerpAPI service right now.")
            speak(f"This might be a temporary issue with the news API. Please try again later or check Google News directly for '{query}'.")
        else:
            speak(f"I couldn't fetch news. {error_msg}")
    except Exception as e:
        error_msg = str(e)
        print(f"[news] Error: {error_msg}")
        import traceback
        traceback.print_exc()
        speak(f"I encountered an error while fetching news. Please try again.")

def action_stocks(speak, listen, user_id):
    """Handle stock information requests."""
    import time
    try:
        _check_sleep()
        from serp_api import get_stock_info
        
        speak("Which stock symbol would you like to check?")
        _prompt_pause(0.3)
        symbol_input = (listen() or "").strip().upper()
        
        if not symbol_input:
            speak("I didn't catch the stock symbol. Please try again.")
            return
        
        # Extract stock symbol (handle phrases like "check Apple stock" or just "AAPL")
        symbol = symbol_input
        if " " in symbol_input:
            # Try to extract ticker symbol from the input
            words = symbol_input.split()
            # Common stock names to symbols mapping
            stock_map = {
                "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL", "amazon": "AMZN",
                "tesla": "TSLA", "meta": "META", "netflix": "NFLX", "nvidia": "NVDA"
            }
            for word in words:
                if word.upper() in stock_map.values():
                    symbol = word.upper()
                    break
                elif word.lower() in stock_map:
                    symbol = stock_map[word.lower()]
                    break
        
        speak(f"Stock information for {symbol}.")
        
        result = get_stock_info(symbol)
        
        if "error" in result:
            speak(f"I couldn't get stock information. {result.get('error', 'Please check your SerpAPI key and try again.')}")
            return
        
        name = result.get("name", symbol)
        # Clean name to remove any URLs
        import re
        name_clean = re.sub(r'https?://\S+|www\.\S+', '', name).strip()
        
        price = result.get("price", "N/A")
        change = result.get("change", "N/A")
        change_percent = result.get("change_percent", "N/A")
        market_cap = result.get("market_cap", "N/A")
        volume = result.get("volume", "N/A")
        
        # Save stock lookup to database
        try:
            from db import save_stock
            save_stock(user_id, symbol, name_clean, str(price), str(change), str(change_percent), str(market_cap), str(volume))
        except Exception as db_err:
            print(f"[stocks] Could not save to DB: {db_err}")
        
        speak(f"Stock information for {name_clean}:")
        _prompt_pause(0.3)
        speak(f"Current price: {price}.")
        if change != "N/A" or change_percent != "N/A":
            change_text = f"{change} ({change_percent})" if change_percent != "N/A" else str(change)
            speak(f"Change: {change_text}.")
        
        if market_cap != "N/A":
            _prompt_pause(0.3)
            speak(f"Market cap: {market_cap}.")
        
    except InterruptedError:
        # Sleep mode requested - exit silently
        return
    except RuntimeError as e:
        error_msg = str(e)
        print(f"[stocks] Error: {error_msg}")
        import traceback
        traceback.print_exc()
        if "SERP_API_KEY" in error_msg:
            speak("SerpAPI key is not configured. Please set SERP_API_KEY in your environment variables.")
        elif "400" in error_msg or "Bad Request" in error_msg:
            speak(f"I'm having trouble accessing stock information through the SerpAPI service right now.")
            speak(f"This might be a temporary issue with the stock API. Please try again later or check Google Finance directly for '{symbol}'.")
        else:
            speak(f"I couldn't get stock information. {error_msg}")
    except Exception as e:
        error_msg = str(e)
        print(f"[stocks] Error: {error_msg}")
        import traceback
        traceback.print_exc()
        speak(f"I encountered an error while fetching stock information. Please try again.")

def action_weather(speak, listen, user_id, initial_query=None):
    """Handle weather information requests with smart city extraction."""
    import time
    import re
    
    try:
        _check_sleep()
        from serp_api import get_weather
        from location_utils import get_current_location
        
        location = None
        
        # Try to extract city from initial query if provided
        if initial_query:
            query_lower = initial_query.lower()
            
            # Common patterns: "weather in Delhi", "weather of Jaipur", "Delhi weather", etc.
            patterns = [
                r'weather\s+(?:in|of|for|at)\s+([\w\s]+?)(?:\s+is|\s+like|\?|\.|$)',  # weather in Delhi
                r'(?:in|of|at)\s+([\w\s]+?)\s+weather',  # in Delhi weather
                r'weather\s+([\w\s]+?)(?:\s+is|\s+like|\?|\.|$)',  # weather Delhi
                r'(?:tell me|what is|what\'s)\s+(?:the\s+)?weather\s+(?:in|of|for|at)\s+([\w\s]+)',  # tell me weather in Delhi
            ]
            
            for pattern in patterns:
                match = re.search(pattern, query_lower)
                if match:
                    location = match.group(1).strip()
                    # Remove common words
                    location = re.sub(r'\b(the|is|like|today|tomorrow|now)\b', '', location).strip()
                    if location:
                        break
        
        # If no city found in query, automatically use user's location
        if not location:
            try:
                location = get_current_location(user_id)
                if location == "Unknown":
                    speak("I couldn't detect your location automatically. Please tell me the city name.")
                    _prompt_pause(0.1)
                    _check_sleep()
                    location = (listen() or "").strip()
                    if not location:
                        speak("I didn't catch the city name. Let's try again later.")
                        return
            except Exception as e:
                print(f"[weather] Location detection error: {e}")
                speak("I couldn't detect your location. Please tell me the city name.")
                _prompt_pause(0.1)
                _check_sleep()
                location = (listen() or "").strip()
                if not location:
                    speak("I didn't catch the city name. Let's try again later.")
                    return
        
        # Confirm and fetch weather
        speak(f"Sure sir, the weather in {location}.")
        
        try:
            result = get_weather(location)
        except Exception as e:
            error_msg = str(e)
            print(f"[weather] API error: {error_msg}")
            if "SERP_API_KEY" in error_msg:
                speak("SerpAPI key is not configured. Please set SERP_API_KEY in your environment variables.")
            else:
                speak(f"I couldn't fetch weather information. {error_msg}")
            return
        
        if "error" in result:
            speak(f"I couldn't get weather information. {result.get('error', 'Please try again.')}")
            return
        
        # Extract weather data
        location_name = result.get("location", location)
        temperature = result.get("temperature", "N/A")
        condition = result.get("condition", "N/A")
        precipitation = result.get("precipitation", "N/A")
        humidity = result.get("humidity", "N/A")
        wind = result.get("wind", "N/A")
        forecast = result.get("forecast", [])
        
        # Speak current weather - combine for faster delivery
        weather_parts = [f"Weather in {location_name}:"]
        
        if temperature != "N/A":
            weather_parts.append(f"Temperature: {temperature}.")
        
        if condition != "N/A":
            weather_parts.append(f"Condition: {condition}.")
        
        if precipitation != "N/A":
            weather_parts.append(f"Precipitation: {precipitation}.")
        
        if humidity != "N/A":
            weather_parts.append(f"Humidity: {humidity}.")
        
        if wind != "N/A":
            weather_parts.append(f"Wind: {wind}.")
        
        # Speak all weather info together for faster delivery
        speak(" ".join(weather_parts))
        
        # Speak forecast if available
        if forecast:
            _prompt_pause(0.2)
            forecast_parts = ["Forecast:"]
            for day_forecast in forecast:
                day = day_forecast.get("day", "")
                temp = day_forecast.get("temperature", "")
                weather = day_forecast.get("weather", "")
                if day and temp:
                    forecast_parts.append(f"{day}: {temp}, {weather}.")
            speak(" ".join(forecast_parts))
        
    except InterruptedError:
        # Sleep mode requested - exit silently
        return
    except RuntimeError as e:
        error_msg = str(e)
        print(f"[weather] Error: {error_msg}")
        import traceback
        traceback.print_exc()
        if "SERP_API_KEY" in error_msg:
            speak("SerpAPI key is not configured. Please set SERP_API_KEY in your environment variables.")
        else:
            speak(f"I couldn't fetch weather information. {error_msg}")
    except Exception as e:
        error_msg = str(e)
        print(f"[weather] Error: {error_msg}")
        import traceback
        traceback.print_exc()
        speak(f"I encountered an error while fetching weather information. Please try again.")

def action_spotify_play(speak, listen, user_id):
    """Search Spotify for a track and open it for playback."""
    import time

    def _parse_choice(text: str, max_index: int) -> Optional[int]:
        if not text:
            return None
        lowered = text.lower().strip()
        mapping = {
            "1": 1,
            "one": 1,
            "first": 1,
            "1st": 1,
            "first one": 1,
            "option one": 1,
            "2": 2,
            "two": 2,
            "second": 2,
            "2nd": 2,
            "second one": 2,
            "option two": 2,
            "3": 3,
            "three": 3,
            "third": 3,
            "3rd": 3,
            "third one": 3,
            "option three": 3,
        }
        for key, val in mapping.items():
            if key in lowered and val <= max_index:
                return val
        return None

    set_spotify_playback_active(False)
    try:
        print("[spotify] Starting playback flow")
        _check_sleep()
        speak("What would you like to listen to on Spotify, sir?")
        _prompt_pause(0.2)
        _check_sleep()
        query = (listen() or "").strip()
        if not query:
            speak("I didn't catch the song name. Let's try again later.")
            return

        print(f"[spotify] Searching for: {query}")
        speak(f"Looking up {query} on Spotify.")
        try:
            tracks = search_tracks(query, limit=5)
        except SpotifyAuthError as e:
            print(f"[spotify] Auth error: {e}")
            speak("Spotify isn't configured yet. Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your environment.")
            return
        except SpotifyApiError as e:
            print(f"[spotify] API error: {e}")
            speak("I couldn't reach Spotify right now. Please check your connection and try again.")
            return

        if not tracks:
            speak(f"I couldn't find any tracks for {query}.")
            return

        top_choices = tracks[:3]
        if len(top_choices) == 1:
            chosen = top_choices[0]
            description = describe_track(chosen)
        else:
            speak("Here are the top options I found.")
            _prompt_pause(0.1)
            for idx, track in enumerate(top_choices, start=1):
                speak(f"Option {idx}: {describe_track(track)}.")
                _prompt_pause(0.1)
            speak("Say the number you prefer, or say first to choose the first option.")
            _prompt_pause(0.2)
            _check_sleep()
            choice_raw = (listen() or "").strip()
            choice = _parse_choice(choice_raw, len(top_choices))
            if not choice:
                choice = 1
            chosen = top_choices[choice - 1]

        url = chosen.get("url")
        print(f"[spotify] Opening track: {url}")
        opened = open_track(chosen)
        if not opened:
            set_spotify_playback_active(False)
            speak("I found the track but couldn't open it automatically. Please follow the link on your screen.")
            if url:
                print(f"[spotify] Track URL: {url}")
            return
        set_spotify_playback_active(True)
    except InterruptedError:
        set_spotify_playback_active(False)
        return
    except Exception as exc:
        print(f"[spotify] Unexpected error: {exc}")
        set_spotify_playback_active(False)
        speak("I ran into a problem while trying to play music.")


def _spotify_control_action(
    speak,
    action_name: str,
    control_fn,
    success_message: str,
) -> None:
    """Shared helper for simple Spotify playback commands."""
    try:
        _check_sleep()
        result = control_fn()
        if result:
            speak(success_message)
        else:
            speak(f"I couldn't {action_name} the music.")
    except SpotifyPlaybackError as exc:
        message = (str(exc) or "").strip()
        if message:
            speak(message)
        else:
            speak(f"I couldn't {action_name} the music.")
    except InterruptedError:
        return
    except Exception as exc:
        print(f"[spotify] Control error ({action_name}): {exc}")
        speak(f"I ran into a problem while trying to {action_name} the music.")


def action_spotify_pause(speak, *_):
    """Pause the current Spotify playback."""
    def _pause_and_flag():
        result = pause_playback()
        if result:
            set_spotify_playback_active(False)
        return result

    _spotify_control_action(speak, "pause", _pause_and_flag, "Paused the music for you, sir.")


def action_spotify_resume(speak, *_):
    """Resume Spotify playback."""
    def _resume_and_flag():
        result = resume_playback()
        if result:
            set_spotify_playback_active(True)
        return result

    _spotify_control_action(speak, "resume", _resume_and_flag, "Resuming your music now, sir.")


def action_spotify_toggle(speak, *_):
    """Toggle Spotify playback between pause and resume."""
    try:
        _check_sleep()
        playing = spotify_is_playing()
    except SpotifyPlaybackError as exc:
        message = (str(exc) or "").strip()
        if message:
            speak(message)
        else:
            speak("I couldn't connect to Spotify to check the current playback state.")
        return
    except InterruptedError:
        return
    except Exception as exc:
        print(f"[spotify] Toggle state error: {exc}")
        speak("I couldn't tell whether music is playing.")
        return

    if playing:
        action_spotify_pause(speak, *_)
    else:
        action_spotify_resume(speak, *_)


def action_spotify_next(speak, listen, user_id):
    """Ask the user for a new track and queue it on Spotify."""
    try:
        _check_sleep()
        paused = False
        try:
            if spotify_is_playing():
                paused = pause_playback()
            else:
                paused = True
        except SpotifyPlaybackError as exc:
            print(f"[spotify] Could not pause before changing track: {exc}")
        if paused:
            set_spotify_playback_active(False)
        speak("Which music should I play?")
        _check_sleep()
        query = (listen() or "").strip()
        if not query:
            speak("I didn't catch the new song name. Let's keep the current music for now.")
            return
        speak(f"Got it. Looking up {query} on Spotify.")
        tracks = search_tracks(query, limit=5)
        if not tracks:
            speak(f"I couldn't find any matches for {query}.")
            return
        chosen = tracks[0]
        if not open_track(chosen):
            set_spotify_playback_active(False)
            url = chosen.get("url")
            speak("I found it but couldn't open Spotify automatically. Please tap the link I displayed.")
            if url:
                print(f"[spotify] Track URL: {url}")
            return
        set_spotify_playback_active(True)
    except SpotifyAuthError as exc:
        print(f"[spotify] Auth error during change: {exc}")
        set_spotify_playback_active(False)
        speak("Spotify isn't configured yet. Please update your credentials.")
    except SpotifyApiError as exc:
        print(f"[spotify] API error during change: {exc}")
        set_spotify_playback_active(False)
        speak("Spotify isn't reachable right now. Please try again shortly.")
    except InterruptedError:
        set_spotify_playback_active(False)
        return
    except Exception as exc:
        print(f"[spotify] Unexpected error during change: {exc}")
        set_spotify_playback_active(False)
        speak("I couldn't switch the music due to an error.")

def handle_question(speak, question: str):
    """Handle general questions using LLM, with specialization in CS/AI/ML/Cybersecurity/Crypto."""
    import time
    if not complete:
        speak("I'm sorry, sir. The AI assistant is not available right now. Please check your configuration.")
        return
    
    try:
        from prompts import SYSTEM_PROMPT
        print(f"[question] User asked: {question}")
        
        # Detect if it's a technical/CS question and adjust response style
        question_lower = question.lower()
        is_technical = any(keyword in question_lower for keyword in [
            "algorithm", "programming", "code", "python", "java", "javascript", "data structure",
            "machine learning", "deep learning", "neural network", "ai", "artificial intelligence",
            "cybersecurity", "security", "hacking", "encryption", "cryptography", "vulnerability",
            "crypto", "bitcoin", "ethereum", "blockchain", "smart contract", "defi", "nft",
            "software", "engineering", "architecture", "design pattern", "database", "sql",
            "network", "protocol", "api", "framework", "library", "function", "class", "object"
        ])
        
        # Detect user's explanation depth preference
        wants_brief = any(phrase in question_lower for phrase in [
            "brief", "short", "quick", "in short", "in brief", "summarize", "summary", "quickly"
        ])
        wants_deep = any(phrase in question_lower for phrase in [
            "deep explanation", "detailed explanation", "explain in detail", "explain deeply",
            "elaborate", "tell me more", "more details", "comprehensive", "thorough",
            "how does it work", "how do they work", "why does it", "why do they"
        ])
        
        # Enhance prompt based on user intent
        enhanced_prompt = SYSTEM_PROMPT
        if is_technical:
            if wants_brief:
                enhanced_prompt += "\n\nProvide a VERY BRIEF, concise answer (1-2 sentences maximum). Be direct and to the point."
            elif wants_deep:
                enhanced_prompt += "\n\nProvide a comprehensive, detailed technical explanation with examples and thorough explanations. Be precise and detailed."
            else:
                enhanced_prompt += "\n\nProvide a CONCISE, to-the-point answer (2-4 sentences maximum). Be precise and direct without unnecessary elaboration."
        
        messages = [
            {"role": "system", "content": enhanced_prompt},
            {"role": "user", "content": question}
        ]
        
        # Use slightly lower temperature for technical questions for more accurate answers
        temperature = 0.5 if is_technical else 0.7
        response = complete(messages, temperature=temperature)
        print(f"[question] LLM response: {response[:200]}...")
        
        _speak_llm_response(speak, response)
                
    except Exception as e:
        error_msg = str(e)
        print(f"[question] Error: {error_msg}")
        import traceback
        traceback.print_exc()
        speak("I'm sorry, sir. I encountered an error while processing your question. Please try again.")

def action_email(speak, listen, user_id):
    import time
    from google_oauth import connected_email
    from email_utils import parse_and_validate_email
    
    print("[action_email] Starting email action")
    # Check if Google is connected
    email = connected_email(user_id)
    print(f"[action_email] Google connected: {bool(email)}, email: {email}")
    if not email:
        speak("Google is not connected. Please say 'authorize google' first to connect your account.")
        return
    
    # Friendly greeting
    speak("Sure sir, I'll help you write an email.")
    _prompt_pause(0.1)
    
    # Get and validate email address
    max_attempts = 3
    to_email = None
    for attempt in range(max_attempts):
        try:
            _check_sleep()
        except InterruptedError:
            return
        
        print(f"[action_email] Asking for recipient (attempt {attempt + 1}/{max_attempts})")
        speak("Whom should I write the email to?")
        _prompt_pause(0.1)
        try:
            _check_sleep()
        except InterruptedError:
            return
        raw_input = (listen() or "").strip()
        print(f"[action_email] Received recipient (raw): '{raw_input}'")
        
        if not raw_input:
            speak("I didn't catch the email address. Please try again.")
            continue
        
        # Parse and validate email
        parsed_email, error_msg = parse_and_validate_email(raw_input)
        if parsed_email:
            to_email = parsed_email
            print(f"[action_email] Validated email: '{to_email}'")
            # Confirm the email address
            speak(f"I'll send it to {to_email}. Is that correct?")
            _prompt_pause(0.3)
            try:
                _check_sleep()
            except InterruptedError:
                return
            confirm = (listen() or "").lower()
            if "yes" in confirm or "correct" in confirm or "right" in confirm or confirm == "":
                break
            elif "no" in confirm or "wrong" in confirm:
                speak("Okay, let me ask again.")
                continue
            else:
                # If unclear, assume yes and proceed
                break
        else:
            print(f"[action_email] Email validation failed: {error_msg}")
            speak(error_msg)
            if attempt < max_attempts - 1:
                speak("Please try again.")
    
    if not to_email:
        speak("I couldn't get a valid email address. Let's try again later.")
        return
    
    try:
        _check_sleep()
    except InterruptedError:
        return
    
    print("[action_email] Asking for purpose")
    speak("What should the email be about?")
    _prompt_pause(0.3)
    try:
        _check_sleep()
    except InterruptedError:
        return
    purpose = (listen() or "").strip()
    print(f"[action_email] Received purpose: '{purpose}'")
    if not purpose:
        speak("I didn't catch the purpose. Let's try again later.")
        return
    
    try:
        print("[action_email] Drafting email...")
        subj, body = draft_email(to_email, purpose)
        print(f"[action_email] Drafted - Subject: {subj}")
        print(f"[action_email] Drafted - Body: {body[:200]}...")
        
        speak("Here's the email I've drafted.")
        _prompt_pause(0.3)
        speak(f"Subject: {subj}")
        _prompt_pause(0.5)
        speak("Email body:")
        _prompt_pause(0.3)
        
        paragraphs = body.split('\n\n')
        body_paragraphs = []
        for para in paragraphs:
            para = para.strip()
            if para:
                # If paragraph has single newlines, split them but keep related lines together
                lines = [line.strip() for line in para.split('\n') if line.strip()]
                if lines:
                    body_paragraphs.append(' '.join(lines))
        
        # Read each paragraph
        for para in body_paragraphs:
            speak(para)
            _prompt_pause(0.4)  # Pause between paragraphs
        
        _prompt_pause(0.5)
        speak("Should I send this email?")
        _prompt_pause(0.3)
        confirm = (listen() or "").lower()
        print(f"[action_email] Confirmation: '{confirm}'")
        if "yes" in confirm or "send" in confirm:
            print("[action_email] Sending email...")
            res = send_email_mock(user_id, to_email, subj, body)
            print(f"[action_email] Send result: {res}")
            if res.get("status") == "sent":
                speak("Email sent successfully!")
            else:
                error_msg = res.get("reason", "Unknown error")
                print(f"[email] Error: {error_msg}")
                
                # Provide user-friendly error messages
                if "Invalid To header" in error_msg or "invalidArgument" in error_msg:
                    speak(f"I couldn't send the email because the email address '{to_email}' is invalid. Please try saying the email address again, like 'john at gmail dot com'.")
                elif "401" in error_msg or "unauthorized" in error_msg.lower():
                    speak("Google authorization expired. Please say 'authorize google' to reconnect.")
                elif "403" in error_msg or "forbidden" in error_msg.lower():
                    speak("I don't have permission to send emails. Please check your Google account settings.")
                else:
                    speak(f"I couldn't send the email. Please check the console for details or try again.")
        else:
            print("[action_email] Saving as draft...")
            save_draft(user_id, to_email, subj, body)
            speak("I saved this email as a draft.")
    except Exception as e:
        print(f"[email] Exception: {e}")
        import traceback
        traceback.print_exc()
        speak(f"I encountered an error while processing the email: {str(e)}")

def action_meet_instant(speak, listen, user_id):
    import time
    import os
    from google_oauth import connected_email
    
    print("[action_meet_instant] Starting meet creation")
    # Check if Google is connected
    email = connected_email(user_id)
    print(f"[action_meet_instant] Google connected: {bool(email)}")
    if not email:
        speak("Google is not connected. Please say 'authorize google' first to connect your account.")
        return
    
    speak("Creating an instant Google Meet now.")
    try:
        print("[action_meet_instant] Calling create_instant_meet...")
        link = create_instant_meet(user_id, "Instant Meeting")
        print(f"[action_meet_instant] Created meet: {link}")
        _prompt_pause(0.3)
        speak(f"Here's your meeting link: {link}")
        
        # Automatically send the link to Telegram if configured
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if bot_token and chat_id and chat_id != "your_telegram_chat_id":
            try:
                from services_telegram import send_message
                _prompt_pause(0.3)
                speak("Sending the meeting link to Telegram.")
                result = send_message(f"Instant Meeting Link:\n{link}")
                if result.get("ok"):
                    _prompt_pause(0.3)
                    speak("Meeting link sent to Telegram successfully!")
                else:
                    print(f"[action_meet_instant] Telegram send failed: {result.get('description', 'Unknown error')}")
                    # Don't speak error - meeting was created successfully
            except Exception as telegram_err:
                print(f"[action_meet_instant] Telegram send error: {telegram_err}")
                # Don't speak error - meeting was created successfully
        else:
            print("[action_meet_instant] Telegram not configured, skipping send")
            
    except RuntimeError as e:
        error_msg = str(e)
        print(f"[agent] Meet error: {error_msg}")
        import traceback
        traceback.print_exc()
        if "No Google tokens" in error_msg or "not connected" in error_msg.lower():
            speak("Google is not connected. Please say 'authorize google' first.")
        else:
            speak(f"I couldn't start the meeting. Error: {error_msg}")
    except Exception as e:
        error_msg = str(e)
        print(f"[agent] Meet error: {error_msg}")
        import traceback
        traceback.print_exc()
        speak(f"I couldn't start the meeting. Error: {error_msg}")

def action_meet_schedule(speak, listen, user_id):
    import time
    from google_oauth import connected_email
    
    # Check if Google is connected
    if not connected_email(user_id):
        speak("Google is not connected. Please say 'authorize google' first to connect your account.")
        return
    
    speak("What should be the meeting title?")
    _prompt_pause(0.3)
    title = (listen() or "").strip() or "Scheduled Meeting"
    speak("When should it start?")
    _prompt_pause(0.3)
    try:
        start_input = listen()
        print(f"[action_meet_schedule] Start time input: '{start_input}'")
        start = iso_in_tz(start_input)
        print(f"[action_meet_schedule] Parsed start: {start}")
    except Exception as e:
        error_msg = str(e)
        print(f"[action_meet_schedule] Start time parse error: {error_msg}")
        speak(f"I couldn't understand the start time. Please say it again in any way you like, for example 'tomorrow at 10 pm' or 'next Monday morning'.")
        return
    speak("When should it end?")
    _prompt_pause(0.3)
    try:
        end_input = listen()
        print(f"[action_meet_schedule] End time input: '{end_input}'")
        end = iso_in_tz(end_input)
        print(f"[action_meet_schedule] Parsed end: {end}")
    except Exception as e:
        error_msg = str(e)
        print(f"[action_meet_schedule] End time parse error: {error_msg}")
        speak(f"I couldn't understand the end time. Please say it again in any way you like, for example 'tomorrow at 11 pm' or 'next Monday afternoon'.")
        return
    try:
        ev = create_event(user_id, title, start, end)
        link = ev.get("hangoutLink") or ev.get("htmlLink") or "No link available"
        speak(f"I've scheduled it. Meeting link: {link}")
    except RuntimeError as e:
        error_msg = str(e)
        print(f"[agent] Calendar error: {error_msg}")
        if "No Google tokens" in error_msg or "not connected" in error_msg.lower():
            speak("Google is not connected. Please say 'authorize google' first.")
        else:
            speak(f"I couldn't schedule that meeting. Error: {error_msg}")
    except Exception as e:
        error_msg = str(e)
        print(f"[agent] Calendar error: {error_msg}")
        speak(f"I couldn't schedule that meeting. Error: {error_msg}")

def action_calendar(speak, listen, user_id):
    import time
    from google_oauth import connected_email
    
    print("[action_calendar] Starting calendar event creation")
    # Check if Google is connected
    email = connected_email(user_id)
    print(f"[action_calendar] Google connected: {bool(email)}")
    if not email:
        speak("Google is not connected. Please say 'authorize google' first to connect your account.")
        return
    
    speak("What's the event title?")
    _prompt_pause(0.3)
    title = (listen() or "").strip() or "Untitled Event"
    print(f"[action_calendar] Event title: '{title}'")
    speak("When should it start?")
    _prompt_pause(0.3)
    try:
        start_input = listen()
        print(f"[action_calendar] Start time input: '{start_input}'")
        start = iso_in_tz(start_input)
        print(f"[action_calendar] Parsed start: {start}")
    except Exception as e:
        error_msg = str(e)
        print(f"[action_calendar] Start time parse error: {error_msg}")
        speak(f"I couldn't understand the start time. Please say it again in any way you like, for example 'tomorrow at 10 pm' or 'today afternoon'.")
        return
    speak("When should it end?")
    _prompt_pause(0.3)
    try:
        end_input = listen()
        print(f"[action_calendar] End time input: '{end_input}'")
        end = iso_in_tz(end_input)
        print(f"[action_calendar] Parsed end: {end}")
    except Exception as e:
        error_msg = str(e)
        print(f"[action_calendar] End time parse error: {error_msg}")
        speak(f"I couldn't understand the end time. Please say it again in any way you like, for example 'tomorrow at 11 pm' or 'today evening'.")
        return
    try:
        print("[action_calendar] Creating calendar event...")
        result = create_event(user_id, title, start, end)
        print(f"[action_calendar] Event created: {result.get('id', 'unknown')}")
        speak(f"Event '{title}' added successfully!")
    except RuntimeError as e:
        error_msg = str(e)
        print(f"[agent] Calendar error: {error_msg}")
        import traceback
        traceback.print_exc()
        if "No Google tokens" in error_msg or "not connected" in error_msg.lower():
            speak("Google is not connected. Please say 'authorize google' first.")
        else:
            speak(f"I couldn't add the event to your calendar. Error: {error_msg}")
    except Exception as e:
        error_msg = str(e)
        print(f"[agent] Calendar error: {error_msg}")
        import traceback
        traceback.print_exc()
        speak(f"I couldn't add the event to your calendar. Error: {error_msg}")

def action_telegram_send(speak, listen, user_id):
    import time
    import os

    print("[action_telegram_send] Starting Telegram send")
    # Check if Telegram is configured
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    print(f"[action_telegram_send] Bot token: {bool(bot_token)}, Chat ID: {chat_id}")
    
    if not bot_token:
        speak("Telegram bot token is not configured. Please set TELEGRAM_BOT_TOKEN in your environment variables.")
        return
    if not chat_id or chat_id == "your_telegram_chat_id":
        speak("Telegram chat ID is not configured. Please set TELEGRAM_CHAT_ID in your environment variables. Get your chat ID from the Telegram bot API.")
        return
    
    speak("What message should I send?")
    _prompt_pause(0.3)
    msg = (listen() or "").strip()
    print(f"[action_telegram_send] Received message: '{msg}'")
    if not msg:
        speak("I didn't catch the message. Let's try again later.")
        return
    try:
        print("[action_telegram_send] Sending message...")
        result = send_message(msg)
        print(f"[action_telegram_send] Result: {result}")
        if result.get("ok"):
            speak("Message sent on Telegram successfully!")
        else:
            error_desc = result.get("description", "Unknown error")
            error_code = result.get("error_code", 0)
            print(f"[agent] Telegram send error: {error_code} - {error_desc}")
            if "chat not found" in error_desc.lower():
                speak("Telegram chat ID is incorrect. Please check your TELEGRAM_CHAT_ID in the environment file. Make sure you've sent at least one message to your bot first.")
            else:
                speak(f"I couldn't send that message. Error: {error_desc}")
    except Exception as e:
        error_msg = str(e)
        print(f"[agent] Telegram send error: {error_msg}")
        import traceback
        traceback.print_exc()
        speak(f"I couldn't send that message. Error: {error_msg}")

def action_email_read(speak, listen, user_id):
    import time
    from google_oauth import connected_email
    
    # Check if Google is connected
    if not connected_email(user_id):
        speak("Google is not connected. Please say 'authorize google' first to connect your account.")
        return
    
    speak("Fetching your recent emails.")
    try:
        messages = list_recent(user_id, "newer_than:7d")
        if not messages: 
            speak("You have no recent emails in the last 7 days.")
            return
        speak(f"I found {len(messages)} recent emails. Here are the first few:")
        for msg in messages[:5]:
            # Note: list_recent returns message IDs, we'd need to fetch full details
            # For now, just indicate we found messages
            speak(f"Email {messages.index(msg) + 1}")
            _prompt_pause(0.2)
        speak("I can show you email summaries. For full details, please check your Gmail inbox.")
    except RuntimeError as e:
        error_msg = str(e)
        print(f"[agent] Email read error: {error_msg}")
        if "No Google tokens" in error_msg:
            speak("Google is not connected. Please say 'authorize google' first.")
        else:
            speak(f"I couldn't read your emails. Error: {error_msg}")
    except Exception as e: 
        error_msg = str(e)
        print(f"[agent] Email read error: {error_msg}")
        speak(f"I couldn't read your emails right now. Error: {error_msg}")

def action_telegram_read(speak, listen, user_id):
    import time
    import os
    
    # Check if Telegram is configured
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        speak("Telegram is not configured. Please set TELEGRAM_BOT_TOKEN in your environment variables.")
        return
    
    speak("Fetching your latest messages.")
    try:
        msgs = read_messages()
        if not msgs: 
            speak("There are no new messages.")
            return
        speak(f"I found {len(msgs)} messages.")
        for m in msgs[:5]: 
            sender = m.get('chat_id', 'Someone')
            text = m.get('text', '')
            speak(f"From {sender}: {text}")
            _prompt_pause(0.3)
    except Exception as e: 
        error_msg = str(e)
        print(f"[agent] Telegram read error: {error_msg}")
        speak(f"I couldn't read your messages right now. Error: {error_msg}")

def _truncate_for_voice(text: str, limit: int = 200) -> str:
    snippet = (text or "").strip()
    if len(snippet) <= limit:
        return snippet
    return snippet[: max(0, limit - 3)].rstrip() + "..."

def action_chat_history_read(speak, user_id: str, user_text: str = ""):
    try:
        from db import get_chat_history
    except Exception as exc:
        print(f"[agent] Chat history read unavailable: {exc}")
        speak("Chat history isn't available right now.")
        return
    role, keyword, limit = _chat_history_filters(user_text, default_limit=5)
    scope = _describe_chat_history_scope(role, keyword)
    try:
        rows = get_chat_history(user_id, limit=limit, role=role, contains=keyword)
    except Exception as exc:
        print(f"[agent] Chat history read error: {exc}")
        speak("I couldn't read the chat history right now.")
        return
    if not rows:
        speak(f"I couldn't find any {scope}.")
        return
    speak(f"Here are the last {len(rows)} {scope}.")
    for row in rows:
        who = "You" if (row.get("role") == "user") else "I"
        snippet = _truncate_for_voice(row.get("text", ""))
        created_at = row.get("created_at")
        when = ""
        if created_at and hasattr(created_at, "strftime"):
            when = created_at.strftime("%b %d at %I:%M %p").lstrip("0")
        prefix = f"{who}"
        if when:
            prefix += f" on {when}"
        speak(f"{prefix} said: {snippet}")

def action_chat_history_delete(speak, user_id: str, user_text: str = ""):
    try:
        from db import delete_chat_history
    except Exception as exc:
        print(f"[agent] Chat history delete unavailable: {exc}")
        speak("Chat history controls aren't available right now.")
        return
    role, keyword, _ = _chat_history_filters(user_text, default_limit=5)
    scope_with_keyword = _describe_chat_history_scope(role, keyword)
    scope_base = _describe_chat_history_scope(role, None)
    try:
        deleted = delete_chat_history(user_id, role=role, contains=keyword)
    except Exception as exc:
        print(f"[agent] Chat history delete error: {exc}")
        speak("I couldn't delete the chat history right now.")
        return
    if deleted == 0:
        speak(f"I didn't find any {scope_with_keyword} to delete.")
        return
    if keyword:
        speak(f"Deleted {deleted} {scope_base} containing \"{keyword}\".")
    else:
        speak(f"Deleted {deleted} {scope_base}.")

# Map new intent to handler (utility function for app integrations may import)

def handle_intent(speak, listen, user_id, intent: str, user_text: str = ""):
    if intent == "location_query":
        return action_location_query(speak, user_id)
    if intent == "pdf_create":
        return action_pdf_create(speak, listen, user_id, user_text)
    if intent == "personal_status":
        return handle_personal_status(speak, user_text)
    if intent == "call_me":
        try:
            from services_calls import call_me as _call
            res = _call()
            if isinstance(res, dict) and res.get("status") == "queued":
                speak("Placing a call to your phone now.")
            else:
                speak(f"I couldn't place the call. {res.get('reason','Unknown error')}")
        except Exception as e:
            print(f"[agent] Call error: {e}")
            speak("Calling service is unavailable or misconfigured.")
        return None
    if intent == "schedule_today":
        return handle_schedule_today(speak, user_id)
    if intent == "schedule_next":
        return handle_schedule_next(speak, user_id)
    if intent == "calrem_enable":
        return handle_calrem_enable(speak)
    if intent == "calrem_disable":
        return handle_calrem_disable(speak)
    if intent == "calrem_refresh":
        return handle_calrem_refresh(speak, user_id)
    if intent == "calrem_brief_now":
        return handle_calrem_brief_now(speak, user_id)
    if intent == "calrem_set_leads":
        return handle_calrem_set_leads(speak, user_text)
   
    return None
