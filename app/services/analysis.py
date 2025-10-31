from typing import Optional, Dict, Any
from app.store import db
from app.services.llm_client import summarize_logs, label_issue 
from typing import Optional, Dict, Any, List
from app.store import db

def find_pof_and_corr(start_ts: Optional[str] = None, end_ts: Optional[str] = None) -> Optional[Dict[str, Any]]:
    pof = db.find_pof_window(start_ts, end_ts)
    if not pof:
        return None

    result = {
        "pof_timestamp": pof.get("ts"),
        "pof_message": pof.get("message"),
        "correlation_id": pof.get("correlation_id"),
        "endpoint": pof.get("endpoint"),
    }

    # AI bits
    ai_summary = summarize_logs(
        pof_message=pof.get("message") or "",
        endpoint=pof.get("endpoint") or "",
        corr_id=pof.get("correlation_id") or "",
    )
    if ai_summary:
        result["ai_summary"] = ai_summary

    ai_label = label_issue(
        pof_message=pof.get("message") or "",
        endpoint=pof.get("endpoint") or "",
        corr_id=pof.get("correlation_id") or "",
    )
    if ai_label:
        result["ai_label"] = ai_label

    return result
from typing import Optional, Dict, Any, List
from app.store import db

try:
    # you already call into llm_client elsewhere
    from app.services.llm_client import summarize_logs as _summarize_logs
except Exception:
    _summarize_logs = None  # fallback later

def summarize_window(start_ts: Optional[str], end_ts: Optional[str], limit: int = 200) -> Dict[str, Any]:
    """
    Fetch logs in [start_ts, end_ts] and produce an (ai_summary, ai_label) using LLM if available.
    """
    logs = db.fetch_logs_window(start_ts, end_ts, limit)
    if not logs:
        return {"logs": [], "ai_summary": "No logs found in this time window.", "ai_label": None}

    # Prepare a compact text block for summarization
    lines: List[str] = []
    for r in logs:
        parts = [r.get("ts") or "-", r.get("level") or "-", r.get("endpoint") or "-", r.get("correlation_id") or "-", r.get("message") or ""]
        lines.append(" | ".join(parts))
    text_block = "\n".join(lines)

    ai_summary = None
    ai_label = None

    if _summarize_logs:
        try:
            out = _summarize_logs(text_block)  # your existing summarizer returns text; or dict if you made it so
            if isinstance(out, dict):
                ai_summary = out.get("summary") or out.get("text")
                ai_label = out.get("label")
            else:
                ai_summary = str(out)
        except Exception:
            ai_summary = "Summary unavailable (LLM error)."
    else:
        # Fallback lightweight heuristic
        ai_summary = "Window summary (heuristic):\n- {} records\n- levels: {}".format(
            len(logs),
            ", ".join(sorted({r.get("level") or "-" for r in logs}))
        )

    return {"logs": logs, "ai_summary": ai_summary, "ai_label": ai_label}

