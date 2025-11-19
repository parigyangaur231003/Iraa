import base64, requests
from google_oauth import ensure_access_token

def _b64(msg: str) -> str:
  return base64.urlsafe_b64encode(msg.encode("utf-8")).decode("utf-8")

def send_email(user_id: str, to: str, subject: str, body: str):
  access = ensure_access_token(user_id)
  
  # Get the authenticated user's email for the From field
  from google_oauth import connected_email
  from_email = connected_email(user_id) or "me"
  
  # Build proper email message with all required headers
  email_message = (
    f"From: {from_email}\r\n"
    f"To: {to}\r\n"
    f"Subject: {subject}\r\n"
    f"Content-Type: text/plain; charset=UTF-8\r\n"
    f"\r\n"
    f"{body}"
  )
  
  raw = _b64(email_message)
  
  r = requests.post(
    "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
    headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
    json={"raw": raw}, timeout=30
  )
  
  if not r.ok:
    error_detail = r.text
    print(f"[gmail] API error {r.status_code}: {error_detail}")
    r.raise_for_status()
  
  return r.json()

def list_recent(user_id: str, q: str = "newer_than:7d"):
  access = ensure_access_token(user_id)
  r = requests.get(
    "https://gmail.googleapis.com/gmail/v1/users/me/messages",
    headers={"Authorization": f"Bearer {access}"},
    params={"q": q, "maxResults": 10}, timeout=30
  )
  r.raise_for_status()
  return r.json().get("messages", [])