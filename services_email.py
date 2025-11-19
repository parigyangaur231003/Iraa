from typing import Tuple
import datetime as dt
from user_profile import signature_text

def _template_draft(to_email: str, purpose: str) -> Tuple[str, str]:
    subj = (purpose or "Follow-up").strip().capitalize()
    if len(subj) > 70:
        subj = subj[:67] + "..."
    today = dt.date.today().strftime("%d %b %Y")
    body = (
        f"Dear {to_email},\n\n"
        f"I hope you are doing well. I’m writing regarding {purpose}.\n\n"
        f"Please let me know if you need any additional details or the preferred next step.\n\n"
        f"Best regards,\n"
        f"[Your Name]\n[Your Role] • [Company]\n{today}"
    )
    return subj, body

def draft_email(to_email: str, purpose: str) -> Tuple[str, str]:
    try:
        from llm_groq import complete
        body = complete(
            [
                {"role":"system","content":"Write a short, formal professional email (120–180 words). Indian workplace tone. No markdown. End with a signature block using this exact signature (no extra blank lines):\n" + signature_text(include_date=True)},
                {"role":"user","content":f"Recipient: {to_email}\nPurpose: {purpose}\nReturn ONLY the email body."}
            ],
            temperature=0.4,
        ).strip()
        subj = complete(
            [
                {"role":"system","content":"Write a crisp email subject (<=10 words) for this purpose."},
                {"role":"user","content":purpose}
            ],
            temperature=0.2,
        ).strip().rstrip(".")
        if not subj or not body:
            raise ValueError("Empty LLM response")
        return subj, body
    except Exception:
        return _template_draft(to_email, purpose)


def save_draft(user_id: str, to_email: str, subject: str, body: str) -> None:
    try:
        from db import conn
        with conn() as c:
            cur = c.cursor()
            cur.execute(
                "INSERT INTO emails (user_id, recipient, subject, body, status) VALUES (%s,%s,%s,%s,'draft')",
                (user_id, to_email, subject, body)
            )
            c.commit()
    except Exception as e:
        print("[services_email] draft not saved:", e)


def send_email_mock(user_id: str, to_email: str, subject: str, body: str) -> dict:
    import requests
    try:
        from google_gmail import send_email
        # Ensure signature is appended if caller didn't include it
        if signature_text(include_date=True).splitlines()[-1] not in body:
            body = body.rstrip() + "\n\n" + signature_text(include_date=True)
        resp = send_email(user_id, to_email, subject, body)
        if isinstance(resp, dict) and resp.get("id"):
            return {"status": "sent", "id": resp["id"]}
        return {"status": "failed", "reason": str(resp)}
    except requests.HTTPError as http_err:
        # Extract detailed error from response
        error_msg = str(http_err)
        if hasattr(http_err, 'response') and http_err.response is not None:
            try:
                error_detail = http_err.response.text
                error_msg = f"{error_msg} - {error_detail}"
            except:
                pass
        print(f"[email] HTTP error: {error_msg}")
        return {"status": "failed", "reason": error_msg}
    except Exception as e:
        error_msg = str(e)
        print(f"[email] Exception: {error_msg}")
        import traceback
        traceback.print_exc()
        return {"status": "failed", "reason": error_msg}