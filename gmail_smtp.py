import smtplib, ssl
from email.mime.text import MIMEText
from db import conn
from secure_store import decrypt_json

def _load_smtp(user_id: str):
    with conn() as c:
        cur = c.cursor()
        cur.execute("SELECT enc_blob FROM user_credentials WHERE user_id=%s AND provider='smtp'", (user_id,))
        row = cur.fetchone()
        if not row: raise RuntimeError("SMTP credentials not found")
        cfg = decrypt_json(row[0])
    return cfg

def send_email_smtp(user_id: str, to_email: str, subject: str, body: str):
    cfg = _load_smtp(user_id)
    host = cfg["host"]; port = int(cfg["port"]); user = cfg["user_email"]; app_password = cfg["app_password"]
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject; msg["From"] = user; msg["To"] = to_email
    ctx = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.ehlo()
        if cfg.get("tls", True):
            server.starttls(context=ctx)
        server.login(user, app_password)
        server.send_message(msg)