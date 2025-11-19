import os
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any

try:
    import mysql.connector
    _MYSQL_CONNECTOR_AVAILABLE = True
    _MYSQL_IMPORT_ERROR: Exception | None = None
except Exception as import_error:
    mysql = None  # type: ignore[assignment]
    _MYSQL_CONNECTOR_AVAILABLE = False
    _MYSQL_IMPORT_ERROR = import_error


_SQLITE_PATH = os.getenv("IRAA_SQLITE_PATH") or os.path.join(
    os.path.dirname(__file__),
    "tmp",
    "iraa_local.db",
)
_SQLITE_DIR = os.path.dirname(_SQLITE_PATH)
if _SQLITE_DIR and not os.path.exists(_SQLITE_DIR):
    os.makedirs(_SQLITE_DIR, exist_ok=True)


class _SQLiteCompatCursor:
    """Lightweight cursor wrapper that accepts MySQL-style placeholders."""

    def __init__(self, inner: sqlite3.Cursor, dictionary: bool = False):
        self._inner = inner
        self._dictionary = dictionary
        self.dialect = "sqlite"

    def execute(self, query: str, params: tuple | list | None = None):
        q = query.replace("%s", "?")
        self._inner.execute(q, params or [])
        return self

    def fetchone(self):
        row = self._inner.fetchone()
        if row is None or not self._dictionary:
            return row
        cols = [col[0] for col in self._inner.description or []]
        return {col: row[idx] for idx, col in enumerate(cols)}

    def fetchall(self):
        rows = self._inner.fetchall()
        if not self._dictionary:
            return rows
        cols = [col[0] for col in self._inner.description or []]
        return [{col: row[idx] for idx, col in enumerate(cols)} for row in rows]

    @property
    def rowcount(self) -> int:
        return self._inner.rowcount

    def close(self):
        self._inner.close()


class _SQLiteCompatConnection:
    """Connection wrapper that mirrors mysql.connector behavior used in the app."""

    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self.dialect = "sqlite"

    def cursor(self, dictionary: bool = False):
        return _SQLiteCompatCursor(self._conn.cursor(), dictionary=dictionary)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()

_cfg = dict(
    host=os.getenv("MYSQL_HOST","127.0.0.1"),
    port=int(os.getenv("MYSQL_PORT","3306")),
    user=os.getenv("MYSQL_USER","root"),
    password=os.getenv("MYSQL_PASSWORD",""),
    database=os.getenv("MYSQL_DB","iraa_db"),
)

_SQLITE_WARNED = False

def conn():
    global _SQLITE_WARNED
    if _MYSQL_CONNECTOR_AVAILABLE:
        return mysql.connector.connect(**_cfg)
    if not _SQLITE_WARNED:
        print(
            f"[db] mysql-connector-python unavailable; using SQLite fallback at {_SQLITE_PATH} "
            f"(error: {_MYSQL_IMPORT_ERROR})"
        )
        _SQLITE_WARNED = True
    return _SQLiteCompatConnection(_SQLITE_PATH)

def log_chat(user_id: str, role: str, text: str):
    with conn() as c:
        cur = c.cursor()
        cur.execute("INSERT INTO chat_history (user_id, role, text) VALUES (%s,%s,%s)", (user_id, role, text))
        c.commit()

def get_chat_history(
    user_id: str,
    limit: int = 20,
    role: Optional[str] = None,
    contains: Optional[str] = None,
    newest_first: bool = False,
) -> List[Dict[str, Any]]:
    """Fetch chat history rows with simple filtering."""
    if limit <= 0:
        limit = 20
    sql = ["SELECT id, user_id, role, text, created_at FROM chat_history WHERE user_id=%s"]
    params: List[Any] = [user_id]
    if role in {"user", "assistant"}:
        sql.append("AND role=%s")
        params.append(role)
    if contains:
        sql.append("AND text LIKE %s")
        params.append(f"%{contains}%")
    order = "ORDER BY created_at DESC"
    sql.append(order)
    sql.append("LIMIT %s")
    params.append(limit)
    with conn() as c:
        cur = c.cursor(dictionary=True)
        cur.execute(" ".join(sql), params)
        rows = cur.fetchall() or []
        if newest_first:
            return rows
        return list(reversed(rows))

def delete_chat_history(
    user_id: str,
    role: Optional[str] = None,
    contains: Optional[str] = None,
    before: Optional[datetime] = None,
) -> int:
    """Delete chat history entries, returning number of rows deleted."""
    sql = ["DELETE FROM chat_history WHERE user_id=%s"]
    params: List[Any] = [user_id]
    if role in {"user", "assistant"}:
        sql.append("AND role=%s")
        params.append(role)
    if contains:
        sql.append("AND text LIKE %s")
        params.append(f"%{contains}%")
    if before:
        sql.append("AND created_at <= %s")
        params.append(before)
    with conn() as c:
        cur = c.cursor()
        cur.execute(" ".join(sql), params)
        c.commit()
        return cur.rowcount

def save_email(user_id, recipient, subject, body, status="draft"):
    with conn() as c:
        cur = c.cursor()
        cur.execute("INSERT INTO emails (user_id, recipient, subject, body, status) VALUES (%s,%s,%s,%s,%s)",
                    (user_id, recipient, subject, body, status))
        c.commit()

def save_meet(user_id, title, link, scheduled_at=None):
    with conn() as c:
        cur = c.cursor()
        cur.execute("INSERT INTO meets (user_id, title, link, scheduled_at) VALUES (%s,%s,%s,%s)",
                    (user_id, title, link, scheduled_at))
        c.commit()

def save_event(user_id, title, start_dt, end_dt, note=None):
    with conn() as c:
        cur = c.cursor()
        cur.execute("INSERT INTO events (user_id, title, start_dt, end_dt, note) VALUES (%s,%s,%s,%s,%s)",
                    (user_id, title, start_dt, end_dt, note))
        c.commit()

def save_schedule(user_id, item, due_dt, note=None):
    with conn() as c:
        cur = c.cursor()
        cur.execute("INSERT INTO schedules (user_id, item, due_dt, note) VALUES (%s,%s,%s,%s)",
                    (user_id, item, due_dt, note))
        c.commit()


def upsert_schedule_from_calendar(user_id: str, item: str, due_dt, source_id: str, note: str | None = None):
    """Mirror a Google Calendar event into schedules with idempotency.
    Uses (user_id, source_id, due_dt) as a dedupe key.
    """
    with conn() as c:
        cur = c.cursor()
        # Check existing
        cur.execute("SELECT id FROM schedules WHERE user_id=%s AND note=%s AND due_dt=%s LIMIT 1",
                    (user_id, f"calendar:{source_id}", due_dt))
        row = cur.fetchone()
        if row:
            # Update item/note if needed
            cur.execute("UPDATE schedules SET item=%s, note=%s WHERE id=%s",
                        (item, note or f"calendar:{source_id}", row[0]))
        else:
            cur.execute("INSERT INTO schedules (user_id, item, due_dt, note) VALUES (%s,%s,%s,%s)",
                        (user_id, item, due_dt, note or f"calendar:{source_id}"))
        c.commit()

def save_telegram(user_id, direction, chat_id, text):
    with conn() as c:
        cur = c.cursor()
        cur.execute("INSERT INTO telegram_msgs (user_id, direction, chat_id, text) VALUES (%s,%s,%s,%s)",
                    (user_id, direction, chat_id, text))
        c.commit()

def save_flight(user_id, origin, destination, date=None, airline=None, price=None, duration=None, stops=0):
    """Save flight search result to database."""
    with conn() as c:
        cur = c.cursor()
        cur.execute("""INSERT INTO flights (user_id, origin, destination, date, airline, price, duration, stops) 
                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (user_id, origin, destination, date, airline, price, duration, stops))
        c.commit()

def save_news(user_id, query, title, source=None, snippet=None, link=None):
    """Save news article to database."""
    with conn() as c:
        cur = c.cursor()
        cur.execute("""INSERT INTO news (user_id, query, title, source, snippet, link) 
                      VALUES (%s,%s,%s,%s,%s,%s)""",
                    (user_id, query, title, source, snippet, link))
        c.commit()

def save_stock(user_id, symbol, name=None, price=None, change=None, change_percent=None, market_cap=None, volume=None):
    """Save stock lookup result to database."""
    with conn() as c:
        cur = c.cursor()
        cur.execute("""INSERT INTO stocks (user_id, symbol, name, price, `change`, change_percent, market_cap, volume) 
                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (user_id, symbol, name, price, change, change_percent, market_cap, volume))
        c.commit()

def save_user_location(user_id, city, region=None, country=None, latitude=None, longitude=None, timezone=None, zip_code=None):
    """Save or update user location in database."""
    with conn() as c:
        cur = c.cursor()
        cur.execute("""INSERT INTO user_location (user_id, city, region, country, latitude, longitude, timezone, zip) 
                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                      ON DUPLICATE KEY UPDATE 
                      city=%s, region=%s, country=%s, latitude=%s, longitude=%s, timezone=%s, zip=%s, updated_at=CURRENT_TIMESTAMP""",
                    (user_id, city, region, country, latitude, longitude, timezone, zip_code,
                     city, region, country, latitude, longitude, timezone, zip_code))
        c.commit()

def get_user_location(user_id):
    """Get user location from database."""
    with conn() as c:
        cur = c.cursor(dictionary=True)
        cur.execute("SELECT * FROM user_location WHERE user_id=%s", (user_id,))
        return cur.fetchone()
