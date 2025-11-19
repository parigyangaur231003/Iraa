import json
from db import conn
from secure_store import encrypt_json

try:
    from email_validator import validate_email, EmailNotValidError
except Exception as import_error:
    class EmailNotValidError(ValueError):
        """Fallback validation error raised when email_validator is unavailable."""

    def validate_email(value: str):
        if not isinstance(value, str) or "@" not in value or "." not in value.split("@")[-1]:
            raise EmailNotValidError(
                "Invalid email address (basic validation only; install 'email_validator' for full checks)"
            ) from import_error
        return {"email": value}

def _assert(cond, msg):
    if not cond: raise ValueError(msg)

def store_credentials(user_id: str, payload_json: str):
    try:
        payload = json.loads(payload_json)
    except Exception:
        raise ValueError("Invalid JSON")

    provider = (payload.get("provider") or "").lower()
    kind = (payload.get("kind") or payload.get("type") or "").lower()

    _assert(provider in {"google","smtp","imap","telegram"}, "Unsupported provider")
    _assert(kind in {"oauth2","app_password"}, "Unsupported kind")

    if provider == "google":
        _assert(kind == "oauth2", "Google must use OAuth2 tokens, not password")
        for k in ["user_email","access_token","refresh_token","expires_at"]:
            _assert(payload.get(k), f"Missing {k}")

    if provider in {"smtp","imap"}:
        _assert(kind == "app_password", "SMTP/IMAP must use app_password")
        for k in ["host","port","user_email","app_password"]:
            _assert(payload.get(k), f"Missing {k}")

    if provider == "telegram":
        _assert(payload.get("bot_token"), "Missing bot_token")
        if not payload.get("user_email"):
            payload["user_email"] = "telegram@local"

    if payload.get("user_email"):
        try: validate_email(payload["user_email"])
        except EmailNotValidError as e: raise ValueError(str(e))

    blob = encrypt_json(payload)

    with conn() as c:
        cur = c.cursor()
        cur.execute("""
            INSERT INTO user_credentials (user_id, provider, kind, user_email, enc_blob)
            VALUES (%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE kind=VALUES(kind), user_email=VALUES(user_email), enc_blob=VALUES(enc_blob)
        """, (user_id, provider, kind, payload.get("user_email"), blob))
        c.commit()

    return {"status":"ok", "provider":provider, "kind":kind}
