# app/services/questioner.py
from typing import Dict, Any, List, Optional
from app.store import db
from app.services.llm_client import _init_model
import json

SYSTEM_HINT = (
    "You are an incident triage copilot. Ask ONE best next question at a time, "
    "based on recent errors and answers so far. Prefer concrete, high-signal questions. "
    "Examples: ask for endpoint, correlation id, last known good time, account type, env/machine checks, "
    "repro steps, auth token freshness, etc. Do NOT ask yes/no if more specific is better.\n"
    "Return JSON with keys: {\"question\": str, \"stop\": bool}. If enough info is gathered, set stop=true."
)

def _recent_labeled_context(limit: int = 25) -> List[Dict[str, Any]]:
    # Use labeled rows so the model sees categories
    rows = db.fetch_recent_logs(limit=limit)
    # Keep only concise fields to keep tokens down
    out = []
    for r in rows:
        out.append({
            "ts": r.get("ts"),
            "level": r.get("level"),
            "message": r.get("message"),
            "correlation_id": r.get("correlation_id"),
            "endpoint": r.get("endpoint"),
            "label": r.get("label"),
        })
    return out

def _answers_so_far(session_id: str) -> List[Dict[str, Any]]:
    return db.get_answers(session_id)

def propose_next_question(session_id: str) -> Dict[str, Any]:
    model = _init_model()
    context = {
        "recent_logs": _recent_labeled_context(),
        "answers_so_far": _answers_so_far(session_id),
    }
    prompt = (
        SYSTEM_HINT
        + "\n\nRecent labeled logs (most recent first):\n"
        + json.dumps(context["recent_logs"], ensure_ascii=False) +
        "\n\nAnswers so far (in order):\n"
        + json.dumps(context["answers_so_far"], ensure_ascii=False) +
        "\n\nReturn ONLY a compact JSON object: {\"question\": str, \"stop\": bool}."
    )
    try:
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip()
        # try to find a json object in the text
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end >= 0 and end > start:
            data = json.loads(text[start:end+1])
        else:
            data = {}
    except Exception:
        data = {}
    # Safe fallback
    if not isinstance(data, dict) or "question" not in data:
        data = {
            "question": "What endpoint or URL were you trying when the error occurred?",
            "stop": False,
        }
    # clamp stop to bool
    data["stop"] = bool(data.get("stop", False))
    return data
