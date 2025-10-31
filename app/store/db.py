# app/store/db.py
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from typing import Optional, List, Dict, Any 

# Prefer app.config.DB_PATH if present, else default to local file
try:
    from app.config import DB_PATH  # type: ignore
except Exception:
    DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "triage.db")

# -------------------- internal connection helpers -----------------------------

def _connect() -> sqlite3.Connection:
    # check_same_thread=False so FastAPI worker thread(s) can use the same file DB
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _exec(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> None:
    cur = conn.cursor()
    cur.execute(sql, args)

def _fetchall(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> List[sqlite3.Row]:
    cur = conn.cursor()
    cur.execute(sql, args)
    return cur.fetchall()

def _table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())

# ------------------------------- schema ---------------------------------------

DDL = [
    # Sessions hold chat flow state
    """CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        step INTEGER NOT NULL DEFAULT 0,
        closed INTEGER NOT NULL DEFAULT 0,
        initiator TEXT
    );""",
    # Answers store Q/A per session
    """CREATE TABLE IF NOT EXISTS answers (
        session_id TEXT NOT NULL,
        step INTEGER NOT NULL,
        question TEXT NOT NULL,
        answer TEXT,
        PRIMARY KEY (session_id, step)
    );""",
    # Logs store ingested events
    """CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT,
        ts TEXT,
        level TEXT,
        message TEXT,
        correlation_id TEXT,
        endpoint TEXT,
        account TEXT
        -- label column added via migration in init()
    );"""
]

def init() -> None:
    """
    Initialize DB file and apply light migrations:
      - ensure tables exist
      - add logs.label if missing
      - add sessions.initiator if missing
    """
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = _connect()
    try:
        cur = conn.cursor()
        for stmt in DDL:
            cur.execute(stmt)

        # Migrations
        if not _table_has_column(conn, "logs", "label"):
            cur.execute("ALTER TABLE logs ADD COLUMN label TEXT")
        if not _table_has_column(conn, "sessions", "initiator"):
            cur.execute("ALTER TABLE sessions ADD COLUMN initiator TEXT")

        conn.commit()
    finally:
        conn.close()

# ----------------------------- session helpers --------------------------------

def new_session(initiator: Optional[str] = None) -> str:
    """Create a session with generated id and return it."""
    sid = str(uuid.uuid4())
    create_session(sid, initiator=initiator or "")
    return sid

def create_session(session_id: str, initiator: str = "") -> None:
    conn = _connect()
    try:
        # defensive: ensure column exists (in case init() not called yet)
        if not _table_has_column(conn, "sessions", "initiator"):
            _exec(conn, "ALTER TABLE sessions ADD COLUMN initiator TEXT")

        _exec(
            conn,
            "INSERT INTO sessions (id, created_at, step, closed, initiator) VALUES (?, ?, ?, ?, ?)",
            (session_id, datetime.utcnow().isoformat(), 0, 0, initiator),
        )
        conn.commit()
    finally:
        conn.close()

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        rows = _fetchall(conn, "SELECT * FROM sessions WHERE id=?", (session_id,))
        return dict(rows[0]) if rows else None
    finally:
        conn.close()

def update_step(session_id: str, step: int) -> None:
    conn = _connect()
    try:
        _exec(conn, "UPDATE sessions SET step=? WHERE id=?", (step, session_id))
        conn.commit()
    finally:
        conn.close()

def close_session(session_id: str) -> None:
    conn = _connect()
    try:
        _exec(conn, "UPDATE sessions SET closed=1 WHERE id=?", (session_id,))
        conn.commit()
    finally:
        conn.close()

# ------------------------------ answers helpers -------------------------------

def add_answer(session_id: str, step: int, question: str, answer: Optional[str]) -> None:
    """Alias used by dynamic flow."""
    put_answer(session_id, step, question, answer)

def put_answer(session_id: str, step: int, question: str, answer: Optional[str]) -> None:
    """Back-compat name used in scripted flow."""
    conn = _connect()
    try:
        _exec(
            conn,
            "INSERT OR REPLACE INTO answers (session_id, step, question, answer) VALUES (?, ?, ?, ?)",
            (session_id, step, question, answer),
        )
        conn.commit()
    finally:
        conn.close()

def get_answers(session_id: str) -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        rows = _fetchall(
            conn,
            "SELECT step, question, answer FROM answers WHERE session_id=? ORDER BY step",
            (session_id,),
        )
        return [dict(r) for r in rows]
    finally:
        conn.close()

# --------------------------- logs: ingest & queries ----------------------------

def insert_logs(rows: List[Dict[str, Any]]) -> int:
    """Bulk insert logs; returns number of inserted rows."""
    if not rows:
        return 0
    conn = _connect()
    try:
        payload = [
            (
                r.get("source"),
                r.get("ts"),
                r.get("level"),
                r.get("message"),
                r.get("correlation_id"),
                r.get("endpoint"),
                r.get("account"),
            )
            for r in rows
        ]
        conn.executemany(
            "INSERT INTO logs (source, ts, level, message, correlation_id, endpoint, account) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            payload,
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()

def upsert_log_label(log_id: int, label: str) -> None:
    conn = _connect()
    try:
        _exec(conn, "UPDATE logs SET label=? WHERE id=?", (label, log_id))
        conn.commit()
    finally:
        conn.close()
def fetch_logs_window(start_ts: Optional[str], end_ts: Optional[str], limit: int = 200) -> List[Dict[str, Any]]:
    """
    Return logs between start_ts and end_ts (inclusive).
    - If start_ts is None: open-ended from earliest.
    - If end_ts is None: open-ended to latest.
    Timestamps are compared as strings (ISO-8601 expected, which your logs use).
    """
    conn = _connect()
    try:
        rows = _fetchall(
            conn,
            """
            SELECT id, ts, level, message, correlation_id, endpoint
            FROM logs
            WHERE (? IS NULL OR ts >= ?)
              AND (? IS NULL OR ts <= ?)
            ORDER BY ts ASC
            LIMIT ?
            """,
            (start_ts, start_ts, end_ts, end_ts, limit),
        )
        return [dict(r) for r in rows]
    finally:
        conn.close()
        
def fetch_recent_logs(limit: int = 500) -> List[Dict[str, Any]]:
    """Return recent logs including label (needed by dynamic questioner)."""
    conn = _connect()
    try:
        rows = _fetchall(
            conn,
            "SELECT id, ts, level, message, correlation_id, endpoint, label "
            "FROM logs ORDER BY ts DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]
    finally:
        conn.close()

def count_labels() -> Dict[str, int]:
    conn = _connect()
    try:
        rows = _fetchall(
            conn,
            "SELECT COALESCE(label,'other') AS label, COUNT(1) AS cnt FROM logs "
            "GROUP BY COALESCE(label,'other')"
        )
        return {r["label"]: r["cnt"] for r in rows}
    finally:
        conn.close()

def find_recent_errors(limit: int = 20) -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        rows = _fetchall(
            conn,
            "SELECT * FROM logs WHERE level IN ('ERROR','FATAL','EXCEPTION','CRITICAL') "
            "ORDER BY ts DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]
    finally:
        conn.close()

def find_pof_window(start_ts: Optional[str] = None, end_ts: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = _connect()
    try:
        q = "SELECT * FROM logs WHERE level IN ('ERROR','FATAL','EXCEPTION','CRITICAL')"
        params: list[Any] = []
        if start_ts:
            q += " AND ts >= ?"
            params.append(start_ts)
        if end_ts:
            q += " AND ts <= ?"
            params.append(end_ts)
        q += " ORDER BY ts ASC LIMIT 1"
        rows = _fetchall(conn, q, tuple(params))
        return dict(rows[0]) if rows else None
    finally:
        conn.close()

def search_correlation(correlation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    conn = _connect()
    try:
        rows = _fetchall(
            conn,
            "SELECT * FROM logs WHERE correlation_id=? ORDER BY ts LIMIT ?",
            (correlation_id, limit),
        )
        return [dict(r) for r in rows]
    finally:
        conn.close()
