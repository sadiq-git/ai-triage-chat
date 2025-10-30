from typing import Optional, Dict, Any
from app.store import db
from app.services.llm_client import summarize_logs, label_issue  # <-- add label_issue

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
