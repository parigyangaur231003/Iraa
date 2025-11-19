# google_oauth.py
import os
import time
import json
import threading
import urllib.parse as _u
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from db import conn 

# ======== Config from .env ========
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8765/").strip()
DEBUG = os.getenv("GOOGLE_OAUTH_DEBUG", "false").lower() == "true"

SCOPES = [
    "openid", "email", "profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/meetings.space.created",
]

AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO  = "https://www.googleapis.com/oauth2/v3/userinfo"


# ======== Helpers ========

def _parse_redirect(uri: str):
    """Return (host, port, path) from REDIRECT_URI; defaults sensible if missing."""
    p = _u.urlparse(uri)
    if p.scheme not in ("http", "https"):
        raise RuntimeError(f"GOOGLE_REDIRECT_URI must be http/https, got: {uri}")
    host = p.hostname or "127.0.0.1"
    port = p.port or (443 if p.scheme == "https" else 80)
    path = p.path or "/"
    return host, port, path


def _debug(msg: str):
    if DEBUG:
        print(f"[google_oauth] {msg}")


# ======== Public API ========

def build_auth_url(state: str = "iraa") -> str:
    """
    Build the Google OAuth URL. If you get 400 in browser, compare the printed URL's
    redirect_uri with your Google Console 'Authorized redirect URIs' (for Web clients).
    Desktop clients ignore this list and use loopback URIs.
    """
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "access_type": "offline",  
        "prompt": "consent",        
        "scope": " ".join(SCOPES),
        "state": state,
    }
    url = AUTH_URL + "?" + _u.urlencode(params)
    _debug(f"Auth URL: {url}")
    return url


def _fetch_userinfo(access_token: str) -> dict:
    r = requests.get(
        USERINFO,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20
    )
    r.raise_for_status()
    return r.json()  # { email, name, picture, ... }


def exchange_code_for_tokens(code: str) -> dict:
    """
    Exchange authorization code for tokens. Returns normalized token dict with:
    access_token, refresh_token, expires_at, user_email, user_name, scope, id_token
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET in .env")

    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    r = requests.post(TOKEN_URL, data=data, timeout=30)
    if not r.ok:
        _debug(f"Token exchange error payload: {r.text}")
    r.raise_for_status()

    tok = r.json()
    tok["expires_at"] = int(time.time()) + int(tok.get("expires_in", 3600))
    try:
        ui = _fetch_userinfo(tok["access_token"])
        tok["user_email"] = ui.get("email", "") or ""
        tok["user_name"]  = ui.get("name", "") or ""
    except Exception as e:
        _debug(f"Failed to fetch userinfo: {e}")
        tok["user_email"] = ""
        tok["user_name"]  = ""

    return tok


def refresh_tokens(refresh_token: str) -> dict:
    """
    Refresh access using a stored refresh_token.
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET in .env")

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    r = requests.post(TOKEN_URL, data=data, timeout=30)
    if not r.ok:
        _debug(f"Token refresh error payload: {r.text}")
    r.raise_for_status()

    tok = r.json()
    tok["refresh_token"] = refresh_token  # Google may omit it on refresh
    tok["expires_at"] = int(time.time()) + int(tok.get("expires_in", 3600))
    try:
        ui = _fetch_userinfo(tok["access_token"])
        tok["user_email"] = ui.get("email", "") or ""
        tok["user_name"]  = ui.get("name", "") or ""
    except Exception as e:
        _debug(f"Failed to fetch userinfo during refresh: {e}")
        tok["user_email"] = ""
        tok["user_name"]  = ""

    return tok


def save_tokens(user_id: str, tok: dict):
    """
    Persist tokens to DB (oauth_tokens table).
    """
    with conn() as c:
        cur = c.cursor()
        cur.execute("""
            INSERT INTO oauth_tokens
                (user_id, provider, user_email, access_token, refresh_token, expires_at, scope, id_token)
            VALUES
                (%s, 'google', %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                user_email=VALUES(user_email),
                access_token=VALUES(access_token),
                refresh_token=VALUES(refresh_token),
                expires_at=VALUES(expires_at),
                scope=VALUES(scope),
                id_token=VALUES(id_token)
        """, (
            user_id,
            tok.get("user_email", ""),
            tok.get("access_token", ""),
            tok.get("refresh_token", ""),
            int(tok.get("expires_at", 0)),
            tok.get("scope", ""),
            tok.get("id_token", ""),
        ))
        c.commit()


def load_tokens(user_id: str):
    """
    Load tokens from DB or return None.
    """
    with conn() as c:
        cur = c.cursor()
        cur.execute("""
            SELECT user_email, access_token, refresh_token, expires_at
            FROM oauth_tokens
            WHERE user_id=%s AND provider='google'
        """, (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "user_email": row[0] or "",
            "access_token": row[1],
            "refresh_token": row[2],
            "expires_at": int(row[3]),
        }


def ensure_access_token(user_id: str) -> str:
    """
    Return a valid access token; refresh if expiring.
    """
    rec = load_tokens(user_id)
    if not rec:
        raise RuntimeError("No Google tokens found. Run authorization first.")
    # refresh if < 2 minutes left
    if rec["expires_at"] - int(time.time()) < 120:
        tok = refresh_tokens(rec["refresh_token"])
        save_tokens(user_id, tok)
        return tok["access_token"]
    return rec["access_token"]


def connected_email(user_id: str) -> str:
    """Return the connected Google email from DB (empty if not linked)."""
    rec = load_tokens(user_id)
    return (rec or {}).get("user_email", "") if rec else ""


# ======== Local callback HTTP server ========

class _Handler(BaseHTTPRequestHandler):
    """
    Minimal handler that accepts ANY path on the configured host/port
    and captures 'code' from the query string (works for Web & Desktop).
    """
    code = None
    error = None

    def do_GET(self):
        try:
            parts = _u.urlparse(self.path)
            qs = _u.parse_qs(parts.query)
            if "error" in qs:
                _Handler.error = qs.get("error", [""])[0]
            if "code" in qs:
                _Handler.code = qs["code"][0]

            self.send_response(200 if _Handler.code else 400)
            self.end_headers()
            if _Handler.code:
                self.wfile.write(b"Iraa: Authorization received. You can close this tab.")
            else:
                self.wfile.write(b"Iraa: No code in request. Check redirect URI & scopes.")
        except Exception as e:
            try:
                self.send_response(500); self.end_headers()
                self.wfile.write(b"Iraa: Internal error handling callback.")
            except Exception:
                pass

    def log_message(self, *args):  # silence default logging
        return


def run_local_callback_server(timeout: int = 180):
    """
    Start a one-shot HTTP server bound to host:port from GOOGLE_REDIRECT_URI.
    Accepts ANY path (so both '/' and '/oauth/google/callback' work).
    Returns the 'code' or None after timeout. Also logs 'error' if present.
    """
    host, port, _ = _parse_redirect(REDIRECT_URI)
    _debug(f"Binding local redirect server on {host}:{port}")
    server = HTTPServer((host, port), _Handler)

    th = threading.Thread(target=server.handle_request, daemon=True)
    th.start()

    t0 = time.time()
    while _Handler.code is None and time.time() - t0 < timeout:
        time.sleep(0.1)

    try:
        server.server_close()
    except Exception:
        pass

    if _Handler.error:
        _debug(f"OAuth error from Google: { _Handler.error }")
    if _Handler.code is None:
        _debug("No 'code' received. Possible causes: wrong redirect URI, app not in Test users, or you closed the tab.")
    return _Handler.code