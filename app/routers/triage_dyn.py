# app/routers/triage_dyn.py
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from uuid import uuid4
from typing import Optional, Tuple
from datetime import datetime, timedelta, timezone
import re

from app.store import db
from app.services import analysis
from app.services.questioner import propose_next_question
from app.services.formatter import format_snow

router = APIRouter(prefix="/triage-dyn", tags=["triage-dyn"])


# ---------- Models ----------
class StartBody(BaseModel):
    initiator: str = "react-ui"


class AnswerBody(BaseModel):
    answer: str


# ---------- Time parsing helpers ----------
HHMM = re.compile(r"\b(\d{1,2}):(\d{2})\b")
ISO_TS = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:\d{2})?)\b"
)
BETWEEN = re.compile(
    r"\bbetween\s+([^\s]+)\s+(?:and|-|to)\s+([^\s]+)", re.IGNORECASE
)
AROUND = re.compile(r"\b(?:around|about|~)\s+([^\s]+)", re.IGNORECASE)


def _today_at_utc(hour: int, minute: int) -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _parse_hhmm(token: str) -> Optional[datetime]:
    """
    Parse a HH:MM token into a 'today @ HH:MM' UTC datetime.
    """
    m = HHMM.fullmatch(token)
    if not m:
        return None
    h, mnt = int(m.group(1)), int(m.group(2))
    # clamp to sane ranges
    h = max(0, min(23, h))
    mnt = max(0, min(59, mnt))
    return _today_at_utc(h, mnt)


def _parse_iso(token: str) -> Optional[datetime]:
    """
    Parse ISO 8601 timestamp with timezone (Z or ±hh:mm).
    """
    if not ISO_TS.fullmatch(token):
        return None
    try:
        # fromisoformat supports '+HH:MM'; handle trailing 'Z' as UTC
        if token.endswith("Z"):
            token = token[:-1] + "+00:00"
        return datetime.fromisoformat(token)
    except Exception:
        return None


def _parse_one_token_dt(token: str) -> Optional[datetime]:
    """
    Try ISO first, then HH:MM.
    """
    dt = _parse_iso(token)
    if dt:
        return dt
    return _parse_hhmm(token)


def parse_time_window(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Accepts:
      - 'between 09:10 and 09:25'
      - 'between 2025-10-29T09:10:00Z and 2025-10-29T09:25:00Z'
      - 'around 09:30' / '~09:30' (±5 min window)
      - raw '2025-10-29T09:30:03+00:00' (±5 min window)
      - a single '09:30' (±5 min window)
    Returns (start_iso, end_iso) in ISO 8601 (timezone-aware).
    """
    txt = text.strip()

    # 1) between A and B
    m = BETWEEN.search(txt)
    if m:
        a, b = m.group(1), m.group(2)
        dt_a = _parse_one_token_dt(a)
        dt_b = _parse_one_token_dt(b)
        if dt_a and dt_b:
            if dt_a > dt_b:
                dt_a, dt_b = dt_b, dt_a
            return dt_a.isoformat(), dt_b.isoformat()

    # 2) around X / ~X
    m = AROUND.search(txt)
    if m:
        tok = m.group(1)
        dt = _parse_one_token_dt(tok)
        if dt:
            start = dt - timedelta(minutes=5)
            end = dt + timedelta(minutes=5)
            return start.isoformat(), end.isoformat()

    # 3) raw ISO in text?
    m = ISO_TS.search(txt)
    if m:
        dt = _parse_iso(m.group(1))
        if dt:
            start = dt - timedelta(minutes=5)
            end = dt + timedelta(minutes=5)
            return start.isoformat(), end.isoformat()

    # 4) any HH:MM present?
    m = HHMM.search(txt)
    if m:
        dt = _parse_hhmm(m.group(0))
        if dt:
            start = dt - timedelta(minutes=5)
            end = dt + timedelta(minutes=5)
            return start.isoformat(), end.isoformat()

    return None, None


# ---------- Routes ----------
@router.post("/start")
def start_dyn(body: StartBody):
    sid = str(uuid4())
    db.create_session(sid, initiator=body.initiator)

    # First (dynamic) question from the model
    q = propose_next_question(sid)

    # Store the question at step=0 (answer empty for now)
    db.put_answer(sid, 0, q["question"], None)

    return {
        "session_id": sid,
        "question": q["question"],
        "step": 0,
        "context": {},
    }


@router.post("/{session_id}/answer")
def answer_dyn(session_id: str, body: AnswerBody):
    sess = db.get_session(session_id)
    if not sess or sess.get("closed"):
        return {"detail": "session not found or closed"}

    # Determine current step (we already inserted step=0 as question)
    answers = db.get_answers(session_id)
    cur_step = max(0, len(answers) - 1)

    # Fill the last question's answer
    last_q = answers[-1]["question"] if answers else "(no question)"
    db.put_answer(session_id, cur_step, last_q, body.answer)

    # --- NEW: time-window trigger ---
    start_ts, end_ts = parse_time_window(body.answer or "")
    if start_ts and end_ts:
        # Look for a POF (first critical error) in that window
        found = db.find_pof_window(start_ts, end_ts) or {}
        if found:
            ctx = {}
            # surface common hints for UI
            if found.get("ts"):
                ctx["pof_timestamp"] = found["ts"]
            if found.get("message"):
                ctx["pof_message"] = found["message"]
            if found.get("correlation_id"):
                ctx["correlation_id"] = found["correlation_id"]
            if found.get("endpoint"):
                ctx["endpoint"] = found["endpoint"]

            # Ask a context-aware follow-up based on the windowed find
            q_text = (
                f"I found a likely point of failure between {start_ts} and {end_ts}.\n"
                f"POF: {ctx.get('pof_timestamp', '-')}\n"
                f"Message: {ctx.get('pof_message', '-')}\n"
                f"CorrelationID: {ctx.get('correlation_id','-')}\n"
                f"Endpoint: {ctx.get('endpoint','-')}\n\n"
                "Does this align with what you observed?"
            )

            next_step = cur_step + 1
            db.put_answer(session_id, next_step, q_text, None)
            db.update_step(session_id, next_step)
            return {
                "session_id": session_id,
                "question": q_text,
                "step": next_step,
                "context": ctx,
            }
        else:
            # No errors in window—fall back with a clarifier
            next_step = cur_step + 1
            q_text = (
                f"I didn't see critical errors between {start_ts} and {end_ts}. "
                "Do you have a correlation ID or endpoint I should focus on?"
            )
            db.put_answer(session_id, next_step, q_text, None)
            db.update_step(session_id, next_step)
            return {
                "session_id": session_id,
                "question": q_text,
                "step": next_step,
                "context": {},
            }

    # --- Default dynamic planner path (no time-window detected) ---
    q = propose_next_question(session_id)
    if q.get("stop"):
        db.close_session(session_id)
        return {
            "session_id": session_id,
            "question": "Thanks. I have enough details. Fetch the summary when ready.",
            "step": cur_step + 1,
            "context": {},
        }

    next_step = cur_step + 1
    db.put_answer(session_id, next_step, q["question"], None)
    db.update_step(session_id, next_step)

    # Optionally surface hints from automated analysis like before
    found = analysis.find_pof_and_corr() or {}
    ctx = {
        k: found.get(k)
        for k in ["pof_timestamp", "pof_message", "correlation_id", "endpoint"]
        if found.get(k)
    }
    if found.get("ai_summary"):
        ctx["ai_summary"] = found["ai_summary"]
    if found.get("ai_label"):
        ctx["ai_label"] = found["ai_label"]

    return {
        "session_id": session_id,
        "question": q["question"],
        "step": next_step,
        "context": ctx,
    }


@router.get("/{session_id}/summary", response_class=PlainTextResponse)
def summary_dyn(session_id: str):
    answers = db.get_answers(session_id)
    found = analysis.find_pof_and_corr() or {}

    # heuristics to pick values from arbitrary dynamic questions
    def find_answer(substring: str) -> Optional[str]:
        s = substring.lower()
        for a in answers:
            q = (a["question"] or "").lower()
            if s in q and a.get("answer"):
                return a["answer"]
        return None

    summary_map = {
        "1. Affected User": find_answer("name") or find_answer("user"),
        "2. Point of Failure (timestamp)": found.get("pof_timestamp"),
        "3. Front-end Channel Application": find_answer("front-end")
        or find_answer("application")
        or find_answer("app"),
        "4. CHS URL/Endpoint": find_answer("endpoint") or found.get("endpoint"),
        "5. CorrelationID": find_answer("correlation") or found.get("correlation_id"),
        "6. Account Used": find_answer("account"),
        "7. Last Working Time": find_answer("last time") or find_answer("last known"),
        "8. Tested on Different Machines/Accounts": find_answer("different machines")
        or find_answer("different accounts")
        or find_answer("tested"),
    }
    if found.get("ai_summary"):
        summary_map["ai_summary"] = found["ai_summary"]
    if found.get("ai_label"):
        summary_map["ai_label"] = found["ai_label"]

    text = format_snow(summary_map, answers)
    return text
