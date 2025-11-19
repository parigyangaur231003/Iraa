import os
from typing import Optional
from services_telegram import send_document
from db import conn

try:
    from pdf_utils import generate_pdf  # type: ignore
    _PDF_IMPORT_ERROR: Exception | None = None
except Exception as import_error:
    generate_pdf = None  # type: ignore[assignment]
    _PDF_IMPORT_ERROR = import_error

_MYSQL_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS pdf_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    caption VARCHAR(255) NULL,
    chat_id VARCHAR(64) NULL,
    content LONGBLOB NOT NULL,
    source ENUM('manual','llm') NOT NULL DEFAULT 'manual',
    telegram_ok TINYINT(1) NOT NULL DEFAULT 0,
    telegram_message_id BIGINT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

_SQLITE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS pdf_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    caption TEXT NULL,
    chat_id TEXT NULL,
    content BLOB NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    telegram_ok INTEGER NOT NULL DEFAULT 0,
    telegram_message_id INTEGER NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def _ensure_pdf_table():
    """Create pdf_documents table if it doesn't exist."""
    with conn() as c:
        cur = c.cursor()
        ddl = _SQLITE_TABLE_DDL if getattr(c, "dialect", "") == "sqlite" else _MYSQL_TABLE_DDL
        cur.execute(ddl)
        c.commit()


def _store_pdf_bytes(filename: str, caption: Optional[str], chat_id: Optional[str], content: bytes, source: str = "manual") -> int:
    _ensure_pdf_table()
    with conn() as c:
        cur = c.cursor()
        cur.execute(
            "INSERT INTO pdf_documents (filename, caption, chat_id, content, source) VALUES (%s,%s,%s,%s,%s)",
            (filename, caption, chat_id, content, source)
        )
        c.commit()
        return cur.lastrowid


def _update_telegram_status(pdf_id: int, telegram_ok: bool, telegram_message_id: Optional[int]):
    with conn() as c:
        cur = c.cursor()
        cur.execute(
            "UPDATE pdf_documents SET telegram_ok=%s, telegram_message_id=%s WHERE id=%s",
            (1 if telegram_ok else 0, telegram_message_id, pdf_id)
        )
        c.commit()


def _assert_pdf_utils_ready():
    if generate_pdf is None:
        raise RuntimeError(
            "PDF generation is unavailable because optional dependency 'reportlab' could not be imported."
        ) from _PDF_IMPORT_ERROR


def create_and_send_pdf_via_telegram(text: str, filename: str = "document.pdf", caption: Optional[str] = None, chat_id: Optional[str] = None) -> dict:
    """Create a PDF from the provided text and send it to Telegram.

    Returns a dict with status, file_path, and telegram_response.
    """
    _assert_pdf_utils_ready()
    # Ensure filename has .pdf extension
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    out_dir = os.path.join("tmp", "pdfs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, filename)

    abs_path = generate_pdf(text, out_path)  # type: ignore[operator]

    # Read bytes and store in DB
    with open(abs_path, "rb") as f:
        pdf_bytes = f.read()
    pdf_id = _store_pdf_bytes(os.path.basename(abs_path), caption, chat_id, pdf_bytes, source="manual")

    # Send via Telegram
    tg_resp = send_document(abs_path, caption=caption, chat_id=chat_id)
    ok = bool(tg_resp.get("ok")) if isinstance(tg_resp, dict) else False

    # Extract message_id if present
    message_id = None
    try:
        message_id = tg_resp.get("result", {}).get("message_id") if isinstance(tg_resp, dict) else None
    except Exception:
        message_id = None

    _update_telegram_status(pdf_id, ok, message_id)

    return {
        "status": "sent" if ok else "failed",
        "file_path": abs_path,
        "telegram_response": tg_resp,
        "pdf_id": pdf_id,
    }


def create_llm_pdf_and_send_via_telegram(instruction: str, filename: str = "document.pdf", caption: Optional[str] = None, chat_id: Optional[str] = None, temperature: float = 0.4) -> dict:
    """Use LLM to generate content based on instruction, create a PDF, and send it via Telegram.

    Returns dict with: status, file_path, telegram_response, llm_text.
    """
    _assert_pdf_utils_ready()
    from llm_groq import complete
    
    # Get plain text content from LLM
    llm_text = complete([
        {"role": "system", "content": (
            "You generate clean plain text suitable for a PDF document. "
            "Avoid markdown, code fences, and excessive whitespace. "
            "Use clear headings and short paragraphs."
        )},
        {"role": "user", "content": instruction},
    ], temperature=temperature).strip()

    # Fallback if empty
    if not llm_text:
        llm_text = "Auto-generated content is empty. Please try again with clearer instructions."

    # Generate PDF first to path
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    out_dir = os.path.join("tmp", "pdfs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, filename)
    abs_path = generate_pdf(llm_text, out_path)  # type: ignore[operator]

    # Store in DB with source='llm'
    with open(abs_path, "rb") as f:
        pdf_bytes = f.read()
    pdf_id = _store_pdf_bytes(os.path.basename(abs_path), caption, chat_id, pdf_bytes, source="llm")

    # Send via Telegram
    tg_resp = send_document(abs_path, caption=caption, chat_id=chat_id)
    ok = bool(tg_resp.get("ok")) if isinstance(tg_resp, dict) else False
    message_id = None
    try:
        message_id = tg_resp.get("result", {}).get("message_id") if isinstance(tg_resp, dict) else None
    except Exception:
        message_id = None

    _update_telegram_status(pdf_id, ok, message_id)

    return {
        "status": "sent" if ok else "failed",
        "file_path": abs_path,
        "telegram_response": tg_resp,
        "llm_text": llm_text,
        "pdf_id": pdf_id,
    }
