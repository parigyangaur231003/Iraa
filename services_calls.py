# services_calls.py
"""
Twilio-based calling service for Iraa.
Requires environment variables:
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_FROM_NUMBER (E.164, e.g., +14155551212)
- MY_PHONE_NUMBER (destination for 'call me')
"""
import os
from typing import Optional, Dict


def _get_env(name: str, required: bool = True) -> Optional[str]:
    val = os.getenv(name)
    if required and not val:
        raise RuntimeError(f"Missing environment variable: {name}")
    return val


def call_me() -> Dict[str, str]:
    """Place a call to MY_PHONE_NUMBER using Twilio and play a short greeting.

    Returns a dict with status and call_sid (when available).
    """
    try:
        from twilio.rest import Client  # type: ignore
    except Exception as e:
        raise RuntimeError("Twilio SDK not installed. Add 'twilio' to requirements and install.") from e

    account_sid = _get_env("TWILIO_ACCOUNT_SID")
    auth_token = _get_env("TWILIO_AUTH_TOKEN")
    from_number = _get_env("TWILIO_FROM_NUMBER")
    to_number = _get_env("MY_PHONE_NUMBER")

    client = Client(account_sid, auth_token)

    # Simple TwiML: say a greeting and hang up.
    twiml = (
        "<Response>"
        "<Say voice=\"Polly.Matthew\" language=\"en-US\">"
        "Hello. This is Iraa calling to confirm your call setup is working. Goodbye."
        "</Say>"
        "</Response>"
    )

    try:
        call = client.calls.create(
            to=to_number,
            from_=from_number,
            twiml=twiml,
        )
        return {"status": "queued", "call_sid": getattr(call, "sid", "")}
    except Exception as e:
        # Normalize common Twilio errors
        msg = str(e)
        if "Authenticate" in msg or "401" in msg:
            msg = "Authentication failed. Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
        elif "From" in msg and "not a valid" in msg:
            msg = "Invalid TWILIO_FROM_NUMBER. Ensure it is a purchased/verified Twilio number in E.164 format."
        elif "To" in msg and "is not a valid" in msg:
            msg = "Invalid MY_PHONE_NUMBER. Ensure E.164 format like +14155551212 and verify number if in trial."
        return {"status": "error", "reason": msg}
