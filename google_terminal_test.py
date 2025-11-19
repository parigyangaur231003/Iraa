# google_terminal_test.py
import webbrowser
import os

from google_oauth import (
    build_auth_url,
    run_local_callback_server,
    exchange_code_for_tokens,
    save_tokens,
    connected_email,
)
from google_gmail import send_email
from google_calendar import create_event, list_today, iso_in_tz
from google_meet import create_instant_meet

USER_ID = "me"


def _ask_yes_no(prompt: str) -> bool:
    s = input(f"{prompt} [y/N]: ").strip().lower()
    return s in ("y", "yes")


def _ask_dt(label: str) -> str:
    """
    Keep asking until user provides a valid datetime.
    Accepts:
      - '2025-11-01 15:00' (recommended)
      - '2025-11-01T15:00'
      - 'today 14:30', 'tomorrow 09:00'
      - 'now', 'in 15 minutes', 'in 2 hours'
      - '2025-11-01' (defaults to 09:00)
    """
    while True:
        s = input(label).strip()
        try:
            return iso_in_tz(s)
        except Exception as e:
            print("  ↳", e)


def main():
    print("\n=== Iraa • Google Live Setup & Quick Test ===")

    # 1) OAuth: open consent URL and capture code
    url = build_auth_url()
    print("\nAuth URL (for debugging/copy-paste if the browser doesn't open):")
    print(url, "\n")

    print("Opening browser for Google consent...")
    webbrowser.open(url, new=1, autoraise=True)
    print("Waiting for redirect to local callback... (if you see 'unverified', click Advanced → Continue)")
    code = run_local_callback_server()

    if not code:
        print("\nNo 'code' received automatically.")
        code = input("Paste the 'code' query parameter from the redirect URL here (or press Enter to abort): ").strip()
        if not code:
            print("Aborted. Re-run this script to try again.")
            return

    # 2) Exchange code for tokens and persist
    try:
        tok = exchange_code_for_tokens(code)
        save_tokens(USER_ID, tok)
        email = connected_email(USER_ID) or tok.get("user_email") or "(unknown email)"
        print(f"\n Tokens saved for: {email}")
    except Exception as e:
        print("\n Token exchange failed:")
        print("   ", e)
        return

    # 3) Optional quick Gmail send test
    if _ask_yes_no("\nRun Gmail send test now?"):
        to = input("  To email: ").strip()
        try:
            resp = send_email(USER_ID, to, "Iraa test email", "This is a live test email sent by Iraa.")
            ok = bool(resp and resp.get("id"))
            print("  Gmail send:", "OK" if ok else f"Unexpected response: {resp}")
        except Exception as e:
            print("  Gmail send error:", e)

    # 4) Optional Calendar create test
    if _ask_yes_no("\nCreate a Calendar test event now?"):
        title = input("  Event title [Iraa Test Event]: ").strip() or "Iraa Test Event"
        start = _ask_dt("  Start (e.g., 2025-11-01 15:00 OR 'today 16:30' OR 'in 10 minutes'): ")
        end   = _ask_dt("  End   (e.g., 2025-11-01 16:00 OR 'in 40 minutes'): ")
        try:
            ev = create_event(USER_ID, title, start, end, [])
            print("  Calendar created:", ev.get("htmlLink", "(no link)"))
        except Exception as e:
            print("   Calendar error:", e)

    # 5) Optional Meet instant space test
    if _ask_yes_no("\nCreate an instant Google Meet now?"):
        topic = input("  Meeting topic [Iraa Test Meeting]: ").strip() or "Iraa Test Meeting"
        try:
            link = create_instant_meet(USER_ID, topic)
            print("  Meet link:", link)
        except Exception as e:
            print("   Meet error:", e)

    # 6) Show today's events summary (optional)
    if _ask_yes_no("\nList today's events?"):
        try:
            items = list_today(USER_ID)
            if not items:
                print("  No events found for today.")
            else:
                print("  Today's events:")
                for it in items[:10]:
                    print("   -", it.get("summary", "(no title)"), "|", it.get("start", {}).get("dateTime", ""))
        except Exception as e:
            print("   Fetch events error:", e)

    print("\nAll done. You can now run Iraa with:  pipenv run python app.py\n")


if __name__ == "__main__":
    main()