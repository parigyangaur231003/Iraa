# services_telegram.py
import os, requests
from db import save_telegram

TELEGRAM_API_BASE = "https://api.telegram.org"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def _ensure_bot_and_chat(chat_id: str | None = None):
    chat_id = chat_id or DEFAULT_CHAT_ID
    if not BOT_TOKEN:
        print(" TELEGRAM_BOT_TOKEN not set in .env")
        return None, {"ok": False, "error_code": 401, "description": "Bot token not configured"}
    if not chat_id or str(chat_id) == "your_telegram_chat_id":
        print(" TELEGRAM_CHAT_ID not set or still has placeholder value in .env")
        return None, {"ok": False, "error_code": 400, "description": "Chat ID not configured. Update TELEGRAM_CHAT_ID in .env"}
    return str(chat_id), None


def send_message(text: str, chat_id: str | None = None):
    """Send message to Telegram chat (using Bot API)."""
    chat_id, err = _ensure_bot_and_chat(chat_id)
    if err:
        return err

    url = f"{TELEGRAM_API_BASE}/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text})
    data = resp.json()
    save_telegram("me", "outgoing", chat_id, text)
    return data


def send_document(file_path: str, caption: str | None = None, chat_id: str | None = None):
    """Send a document (PDF or other) to Telegram chat using sendDocument API."""
    chat_id, err = _ensure_bot_and_chat(chat_id)
    if err:
        return err

    url = f"{TELEGRAM_API_BASE}/bot{BOT_TOKEN}/sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": (os.path.basename(file_path), f)}
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        resp = requests.post(url, data=data, files=files)
    return resp.json()


def read_messages(limit=10):
    """Fetch recent updates from Telegram."""
    if not BOT_TOKEN:
        print(" Telegram bot not configured in .env")
        return []

    url = f"{TELEGRAM_API_BASE}/bot{BOT_TOKEN}/getUpdates"
    resp = requests.get(url)
    data = resp.json()

    messages = []
    for u in data.get("result", [])[-limit:]:
        msg = u.get("message")
        if not msg: continue
        text = msg.get("text")
        chat_id = msg.get("chat", {}).get("id")
        if text:
            messages.append({"chat_id": chat_id, "text": text})
            save_telegram("me", "incoming", chat_id, text)
    return messages