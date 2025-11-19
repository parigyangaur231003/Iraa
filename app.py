# app.py
import os, sys, time, tempfile, webbrowser, threading
from collections.abc import Iterable
from contextlib import contextmanager

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except Exception:
        return default

def _find_module_file(basename: str) -> str | None:
    want = (basename + ".py").lower()
    for name in os.listdir(HERE):
        n = name.replace("\u00A0", " ").strip().lower()
        if n == want or (n.startswith(basename.lower()) and (n.endswith(".py") or n.endswith(".py.txt"))):
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

from speech_io import record_to_wav, transcribe_wav, speak
from time_utils import greeting
from db import log_chat

try:
    from services_spotify import pause_for_listening
except Exception:
    @contextmanager
    def pause_for_listening():
        yield False

# Global sleep flag that can be checked anywhere - MUST be defined before imports that use it
_SLEEP_REQUESTED = False

def set_sleep_requested(value: bool):
    """Set the global sleep flag."""
    global _SLEEP_REQUESTED
    _SLEEP_REQUESTED = value

def is_sleep_requested() -> bool:
    """Check if sleep mode has been requested."""
    return _SLEEP_REQUESTED

from agent import (
    detect_intent, handle_smalltalk, handle_personal_status, handle_time, handle_joke, handle_question, handle_intent,
    action_email, action_email_read, action_meet_instant, action_meet_schedule, action_calendar,
    action_telegram_send, action_telegram_read, action_flights, action_news, action_stocks, action_weather,
    action_spotify_play, action_spotify_pause, action_spotify_resume, action_spotify_next, action_spotify_toggle,
    action_chat_history_read, action_chat_history_delete, is_spotify_playback_active,
    handle_casual_chat,
)
from credentials import store_credentials
from google_oauth import (
    build_auth_url, run_local_callback_server, exchange_code_for_tokens,
    save_tokens, connected_email
)

# Scheduler import with tolerant path search
try:
    from scheduler_jobs import start_recurring, announce
except Exception as e:
    print("[app] scheduler import failed ->", repr(e))
    try:
        path = _find_module_file("scheduler_jobs")
        if not path: raise FileNotFoundError("scheduler_jobs*.py not found")
        _load_local_module("scheduler_jobs", path)
        from scheduler_jobs import start_recurring, announce
        print(f"[app] scheduler loaded via path: {os.path.basename(path)}")
    except Exception as e2:
        print("[app] scheduler path-load failed ->", repr(e2))
        def announce():        print("[scheduler] unavailable — skipping announcement.")
        def start_recurring(): print("[scheduler] unavailable — periodic reminders disabled."); return None

from uptime_monitor import Watchdog, start_scheduler_guard

USER_ID = "me"
WAKE_WORDS: tuple[str, ...] = (
    "hello assistant",
    "hey assistant",
    "assistant",
    "ira",
    "iraa",
    "hey ira",
    "hey iraa",
    "hey buddy",
    "hello ira",
    "hello iraa",
    "hello buddy",
)

_scheduler_lock = threading.Lock()
_scheduler_instance = None
_scheduler_guard_lock = threading.Lock()
_scheduler_guard_thread = None
_main_watchdog: Watchdog | None = None

_STT_EXTENSION_SECONDS = _env_float("IRAA_STT_EXTENSION_SECONDS", 6.0)
_STT_MAX_CAPTURE_SECONDS = _env_float("IRAA_STT_MAX_CAPTURE_SECONDS", 16.0)


def _set_scheduler(sched):
    global _scheduler_instance
    with _scheduler_lock:
        _scheduler_instance = sched
    return sched


def _get_scheduler():
    with _scheduler_lock:
        return _scheduler_instance


def _start_scheduler():
    try:
        sched = start_recurring()
    except Exception as exc:
        print(f"[app] start_recurring() failed: {exc}")
        sched = None
    return _set_scheduler(sched)


def _restart_scheduler():
    with _scheduler_lock:
        current = _scheduler_instance
        _scheduler_instance = None
    if current is not None:
        try:
            current.shutdown(wait=False)  # type: ignore[attr-defined]
        except Exception as exc:
            print(f"[app] Error shutting down scheduler: {exc}")
    return _start_scheduler()


def _ensure_scheduler_guard():
    global _scheduler_guard_thread
    with _scheduler_guard_lock:
        if _scheduler_guard_thread is None:
            _scheduler_guard_thread = start_scheduler_guard(_get_scheduler, _restart_scheduler)


def compute_listen_window(seconds: float, allow_extension: bool = True) -> float:
    """Return the upper bound for a single listen cycle."""
    if not allow_extension:
        return seconds
    return min(_STT_MAX_CAPTURE_SECONDS, seconds + _STT_EXTENSION_SECONDS)


def heard_wake_word(transcript: str, wake_words: Iterable[str] = WAKE_WORDS) -> bool:
    """Return True when the transcript includes any configured wake-word phrase."""
    if not transcript:
        return False
    normalized = transcript.lower()
    return any(word in normalized for word in wake_words)

def listen_once(seconds: int = 4, allow_extension: bool = True) -> str:
    tmp_file = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_file = f.name
        with pause_for_listening():
            max_seconds = compute_listen_window(float(seconds), allow_extension)
            record_to_wav(tmp_file, seconds=seconds, max_seconds=max_seconds)
        res = transcribe_wav(tmp_file) or {}
        return (res.get("text") or "").strip()
    except Exception as e:
        print("[listen_once] error:", e); return ""
    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.unlink(tmp_file)
            except Exception:
                pass

def auth_google_flow_cli():
    speak("I'll pop open the Google authorization page in your browser now, sir.")
    url = build_auth_url(); print("\nAuth URL (copy if browser fails to open):\n", url, "\n")
    webbrowser.open(url, new=1, autoraise=True)
    speak("Take your time authorizing. If you see 'unverified', just pick Advanced and Continue.")
    code = run_local_callback_server()
    if not code:
        speak("Hmm, I didn't receive the authorization code, sir. Let's try again in a moment.")
        return
    tok = exchange_code_for_tokens(code); save_tokens(USER_ID, tok)
    speak("All connected! Your Google account is ready to go, sir.")

def main():
    global _main_watchdog
    try:
        em = connected_email(USER_ID)
        if not em:
            print("[app] Google is not connected. Say 'authorize google' to connect.")
    except Exception:
        print("[app] Could not verify Google connection.")

    if not _get_scheduler():
        _start_scheduler()
    _ensure_scheduler_guard()

    conversation_active = False
    first_wakeup = True  # Track if this is the first wakeup
    silent_turns = 0  # Count consecutive empty transcripts during active chat
    
    music_control_intents = {"spotify_pause", "spotify_next", "spotify_toggle"}

    def _heartbeat_conf(name: str, default: str) -> float:
        try:
            return float(os.getenv(name, default))
        except Exception:
            return float(default)

    def _loop_stalled(age: float) -> None:
        nonlocal conversation_active
        print(f"[app] Main loop heartbeat stalled for {age:.1f}s; resetting conversation state.")
        conversation_active = False
        set_sleep_requested(False)

    try:
        main_watchdog = Watchdog(
            "iraa_main_loop",
            timeout=_heartbeat_conf("IRAA_MAIN_LOOP_TIMEOUT", "240"),
            heartbeat_interval=_heartbeat_conf("IRAA_HEARTBEAT_INTERVAL", "30"),
            on_stall=_loop_stalled,
        )
        _main_watchdog = main_watchdog
    except Exception as exc:
        print(f"[app] Watchdog unavailable: {exc}")

        class _NullWatchdog:
            def beat(self) -> None:
                return

        main_watchdog = _NullWatchdog()
        _main_watchdog = None

    def prompt_if_music_idle(message: str) -> None:
        """Speak follow-up prompts only when Spotify isn't actively playing."""
        if not is_spotify_playback_active():
            speak(message)

    def enter_music_sleep_if_needed():
        """Drop back to idle listening whenever Spotify starts playing."""
        nonlocal conversation_active
        if is_spotify_playback_active():
            conversation_active = False
    
    def check_sleep_mode(text: str) -> bool:
        """Check if text contains sleep mode words and handle accordingly."""
        nonlocal conversation_active
        if not text:
            return False
        
        u_lower = text.lower().strip()
        normalized = " ".join(u_lower.split())
        
        # Check for exit command (stops program entirely)
        if "exit" in u_lower:
            speak("I'll power down now, sir. Just wake me when you need me again.")
            time.sleep(0.1)
            sys.exit(0)
        
        sleep_triggers = [
            {"phrases": ("thank you", "thanks"), "response": "Always a pleasure, sir. I'll be right here when you call."},
            {"phrases": ("bye", "goodbye"), "response": "Goodbye for now, sir. I'll be right here when you call."},
            {"phrases": ("stop",), "response": "Understood, sir. I'll slip into sleep mode until you wake me."},
            {"phrases": ("dhanyvad",), "response": "Shukriya, sir. I'll rest for now—call me anytime."},
            {"phrases": ("sleep mode",), "response": "Sliding into sleep mode now, sir."},
            {"phrases": ("go to sleep",), "response": "Heading into sleep mode now, sir."},
            {"phrases": ("sleep now",), "response": "I'll rest for now, sir. Wake me anytime."},
            {"phrases": ("rest now", "take rest"), "response": "Taking a quick rest now, sir."},
            {"phrases": ("good night",), "response": "Good night, sir. I'll be here when you wake me."},
            {"phrases": ("sleep please",), "response": "Of course, sir. Going to sleep now.", "match_exact": True},
            {"phrases": ("sleep",), "response": "Of course, sir. Going to sleep now.", "match_exact": True},
        ]
        for entry in sleep_triggers:
            phrases = entry["phrases"]
            response = entry["response"]
            match_exact = entry.get("match_exact", False)
            for phrase in phrases:
                if match_exact:
                    if normalized == phrase:
                        set_sleep_requested(True)
                        conversation_active = False
                        speak(response)
                        time.sleep(0.1)
                        return True
                else:
                    if phrase in normalized:
                        set_sleep_requested(True)
                        conversation_active = False
                        speak(response)
                        time.sleep(0.1)
                        return True
        
        return False
    
    while True:
        main_watchdog.beat()
        time.sleep(0.05)
        
        # Reset sleep flag when conversation starts
        if not conversation_active:
            silent_turns = 0
            set_sleep_requested(False)
        
        # If sleep is requested, skip all processing
        if is_sleep_requested() and conversation_active:
            conversation_active = False
            continue
        
        # Listen for wake word or continue conversation
        if not conversation_active:
            wake = (listen_once(seconds=4, allow_extension=False) or "").lower()
            main_watchdog.beat()
            print("[DEBUG] Listening for wake word, heard:", repr(wake))
            
            # Check for sleep words even during wake word listening
            if check_sleep_mode(wake):
                continue

            if is_spotify_playback_active():
                control_intent = detect_intent(wake)
                if control_intent in music_control_intents:
                    conversation_active = True
                    set_sleep_requested(False)
                    if control_intent == "spotify_pause":
                        action_spotify_pause(speak, lambda: "", USER_ID)
                        prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                    elif control_intent == "spotify_next":
                        action_spotify_next(speak, lambda: listen_once(5), USER_ID)
                        prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                        enter_music_sleep_if_needed()
                    elif control_intent == "spotify_toggle":
                        action_spotify_toggle(speak, lambda: "", USER_ID)
                        prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                        enter_music_sleep_if_needed()
                    continue

            if not heard_wake_word(wake):
                continue
            
            conversation_active = True
            set_sleep_requested(False)  # Reset on wake
            
            # First time greeting vs subsequent
            if first_wakeup:
                from time_utils import greeting
                greet = greeting()
                if not is_sleep_requested():
                    speak(f"{greet} sir! What can I take care of for you today?")
                first_wakeup = False
            else:
                if not is_sleep_requested():
                    speak("Hey sir, welcome back! What can I do for you this time?")
            time.sleep(0.1)  # Brief pause after greeting
        else:
            # Continue conversation - listen for user input
            utter = listen_once(seconds=6)
            main_watchdog.beat()
            if not utter:
                silent_turns += 1
                print(f"[DEBUG] No speech detected during active chat (#{silent_turns}).")
                if silent_turns >= 3:
                    silent_turns = 0
                    conversation_active = False
                    prompt_if_music_idle("I'm not hearing anything, so I'll wait quietly. Just call me back when you're ready.")
                continue
            silent_turns = 0
            
            print("[DEBUG] Heard in conversation:", repr(utter))
            u_lower = utter.lower().strip()
            
            # Check for exit/sleep mode commands FIRST - before anything else
            if check_sleep_mode(utter):
                continue
            
            # Log user input
            try:
                log_chat(USER_ID, "user", utter)
            except Exception as db_err:
                print(f"[app] Could not log chat to DB: {db_err}")

            intent = detect_intent(utter)
            print(f"[DEBUG] User said: '{utter}'")
            print(f"[DEBUG] Detected intent: {intent}")

            if is_spotify_playback_active() and intent not in music_control_intents:
                print("[spotify] Music playing — waiting for pause/change command.")
                continue

            # Handle special commands
            if "authorize google" in u_lower or "connect google" in u_lower:
                auth_google_flow_cli()
                prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                continue
            if any(kw in u_lower for kw in ("which account","what account","who am i connected")):
                em = connected_email(USER_ID)
                speak(f"You are connected as {em}." if em else "You are not connected. Say 'authorize google' to connect.")
                prompt_if_music_idle("What else can I do for you?")
                continue
            if "set credentials" in u_lower or "save credentials" in u_lower:
                speak("Paste the credentials JSON into the terminal now. I will not read it aloud.")
                print("\nPaste credentials JSON and press Enter:\n> ", end="")
                try:
                    creds = input()
                    store_credentials(USER_ID, creds)
                    speak("Credentials saved securely. What else can I help you with?")
                except Exception as e:
                    speak("Sorry, I could not save those credentials.")
                    print("Error:", e)
                continue
            
            # Location management commands
            if "set location" in u_lower or "set my location" in u_lower:
                speak("What city should I set as your location?")
                city = (listen_once(4) or "").strip()
                if city:
                    try:
                        from location_utils import set_default_location
                        if set_default_location(USER_ID, city):
                            speak(f"Location set to {city}. What else can I help you with?")
                        else:
                            speak("I couldn't save your location. Please try again.")
                    except Exception as e:
                        speak("Sorry, I encountered an error saving your location.")
                        print(f"Error: {e}")
                else:
                    speak("I didn't catch the city name.")
                continue
            try:
                # Simple single-response handlers - ask what else after
                if   intent == "smalltalk":      
                    handle_smalltalk(speak, utter)
                    prompt_if_music_idle("What else can I help you with?")
                elif intent == "personal_status":
                    handle_personal_status(speak, utter)
                    prompt_if_music_idle("What else can I help you with?")
                elif intent == "ask_time":       
                    handle_time(speak)
                    prompt_if_music_idle("What else can I help you with?")
                elif intent == "joke":           
                    handle_joke(speak)
                    prompt_if_music_idle("What else can I help you with?")
                elif intent == "question":       
                    handle_question(speak, utter)
                    prompt_if_music_idle("What else can I help you with?")
                elif intent == "casual_chat":
                    handle_casual_chat(speak, utter)
                    prompt_if_music_idle("Want to keep chatting, or should I jump into a task?")
                elif intent == "chat_history_read":
                    action_chat_history_read(speak, USER_ID, utter)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                elif intent == "chat_history_delete":
                    action_chat_history_delete(speak, USER_ID, utter)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                # Multi-step action handlers - they handle their own flow
                elif intent == "email":          
                    action_email(speak, lambda: listen_once(6), USER_ID)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                elif intent == "email_read":     
                    action_email_read(speak, lambda: listen_once(3), USER_ID)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                elif intent == "meet_instant":   
                    action_meet_instant(speak, lambda: listen_once(4), USER_ID)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                elif intent == "meet_schedule":  
                    action_meet_schedule(speak, lambda: listen_once(6), USER_ID)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                elif intent == "calendar":       
                    action_calendar(speak, lambda: listen_once(6), USER_ID)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                elif intent == "telegram_send":  
                    action_telegram_send(speak, lambda: listen_once(6), USER_ID)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                elif intent == "telegram_read":  
                    action_telegram_read(speak, lambda: listen_once(3), USER_ID)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                elif intent in {
                    "call_me",
                    "schedule_today",
                    "schedule_next",
                    "calrem_enable",
                    "calrem_disable",
                    "calrem_refresh",
                    "calrem_brief_now",
                    "calrem_set_leads",
                    "location_query",
                    "pdf_create",
                }:
                    handle_intent(speak, lambda: listen_once(6), USER_ID, intent, utter)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                # Future features
                elif intent == "flights":       
                    action_flights(speak, lambda: listen_once(6), USER_ID)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                elif intent == "weather":        
                    action_weather(speak, lambda: listen_once(6), USER_ID, initial_query=utter)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                elif intent == "news":
                    action_news(speak, lambda: listen_once(6), USER_ID)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                elif intent == "stocks":         
                    action_stocks(speak, lambda: listen_once(6), USER_ID)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                elif intent == "spotify_pause":
                    action_spotify_pause(speak, lambda: "", USER_ID)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                elif intent == "spotify_resume":
                    action_spotify_resume(speak, lambda: "", USER_ID)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                    enter_music_sleep_if_needed()
                    continue
                elif intent == "spotify_next":
                    action_spotify_next(speak, lambda: listen_once(5), USER_ID)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                    enter_music_sleep_if_needed()
                    continue
                elif intent == "spotify_toggle":
                    action_spotify_toggle(speak, lambda: "", USER_ID)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                    enter_music_sleep_if_needed()
                    continue
                elif intent == "spotify_play":
                    action_spotify_play(speak, lambda: listen_once(5), USER_ID)
                    prompt_if_music_idle("Anything else you'd like me to handle, sir?")
                    enter_music_sleep_if_needed()
                    continue
                else:
                    # Use LLM for unknown intents as fallback
                    handle_question(speak, utter)
                    prompt_if_music_idle("What else can I help you with?")
                    
            except Exception as handler_err:
                print(f"[app] Handler error for intent '{intent}': {handler_err}")
                import traceback
                traceback.print_exc()
                speak("I encountered an error. Please try again. What else can I do?")
            
            try:
                log_chat(USER_ID, "assistant", f"intent:{intent}")
            except Exception as db_err:
                print(f"[app] Could not log chat to DB: {db_err}")

def _stop(*_):
    speak("I'll shut down now, sir. Just wake me when you're ready again.")
    if _main_watchdog is not None:
        _main_watchdog.stop()
    sys.exit(0)

if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGINT, _stop); signal.signal(signal.SIGTERM, _stop)
    main()
