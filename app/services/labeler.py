# app/services/labeler.py
from typing import List, Dict, Any
from app.store import db
from app.services.llm_client import _init_model
import time
import os
from collections import defaultdict, Counter

# Supported labels
CANDIDATE_LABELS = [
    "network_timeout", "auth_failure", "database_error", "null_pointer",
    "service_unavailable", "bad_request", "rate_limit_exceeded",
    "cache_error", "configuration_error", "other"
]

# Rule keywords (lowercased match)
RULES = [
    ("network_timeout",      ["timeout", "timed out", "gateway timeout", "upstream timeout", "retrying request"]),
    ("auth_failure",         ["401", "unauthorized", "forbidden", "invalid token", "expired token", "oauth"]),
    ("database_error",       ["sqlstate", "db", "postgres", "mysql", "connection refused", "deadlock"]),
    ("null_pointer",         ["nullpointer", "null pointer", "npe"]),
    ("service_unavailable",  ["503", "service unavailable", "backend down", "dependency down"]),
    ("bad_request",          ["400", "bad request", "malformed", "invalid payload", "schema"]),
    ("rate_limit_exceeded",  ["429", "rate limit", "too many requests", "throttl"]),
    ("cache_error",          ["redis", "memcache", "cache", "eviction"]),
    ("configuration_error",  ["config", "env var", "misconfig", "invalid setting"]),
]

def _rule_label(msg: str) -> str | None:
    m = (msg or "").lower()
    for label, needles in RULES:
        if any(n in m for n in needles):
            return label
    return None

# cache + throttling for Gemini fallbacks
_LABEL_CACHE: Dict[str, str] = {}
MAX_AI_CALLS_PER_RUN = int(os.getenv("LABELER_MAX_AI_CALLS", "10"))
SLEEP_BETWEEN_AI_CALLS = float(os.getenv("LABELER_AI_SLEEP_SEC", "0.2"))

def ai_label_for_message(message: str, endpoint: str = "", corr_id: str = "", _ai_calls=[0]) -> str:
    # 1) rules
    rule = _rule_label(message)
    if rule:
        return rule

    # 2) memoize by normalized message
    key = (message or "").strip().lower()
    if key in _LABEL_CACHE:
        return _LABEL_CACHE[key]

    # 3) guardrail
    if _ai_calls[0] >= MAX_AI_CALLS_PER_RUN:
        return "other"

    # 4) Gemini fallback
    try:
        model = _init_model()
        prompt = (
            "Classify the issue message into ONE label from this list: "
            f"{', '.join(CANDIDATE_LABELS)}.\n"
            "Return only the label.\n\n"
            f"Message: {message}\nEndpoint: {endpoint}\nCorrelationID: {corr_id}"
        )
        _ai_calls[0] += 1
        resp = model.generate_content(prompt)
        time.sleep(SLEEP_BETWEEN_AI_CALLS)
        label = (resp.text or "").strip().lower().replace(" ", "_")
        if label not in CANDIDATE_LABELS:
            label = "other"
        _LABEL_CACHE[key] = label
        return label
    except Exception:
        return "other"

def _majority_label(items: List[Dict[str, Any]]) -> str:
    counts = Counter([i["label"] for i in items])
    # prefer non-"other" on ties
    majority = max(counts.items(), key=lambda kv: (kv[0] != "other", kv[1]))[0]
    return majority

def label_recent_logs(limit: int = 500) -> List[Dict[str, Any]]:
    """Label recent logs; apply correlation_id majority; persist labels."""
    rows = db.fetch_recent_logs(limit=limit)
    provisional = []
    ai_counter = [0]
    for r in rows:
        lbl = ai_label_for_message(
            r.get("message", ""),
            r.get("endpoint", ""),
            r.get("correlation_id", ""),
            _ai_calls=ai_counter,
        )
        provisional.append({**r, "label": lbl})

    # group by correlation_id and apply majority vote
    by_corr: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in provisional:
        by_corr[item.get("correlation_id")].append(item)

    resolved: List[Dict[str, Any]] = []
    for corr_id, items in by_corr.items():
        if not corr_id:  # no corr id: keep as-is
            resolved.extend(items)
            continue
        majority = _majority_label(items)
        for i in items:
            i["label"] = majority
        resolved.extend(items)

    # persist
    out = []
    for item in resolved:
        db.upsert_log_label(item["id"], item["label"])
        out.append({"id": item["id"], "label": item["label"]})
    return out

def label_stats() -> Dict[str, int]:
    """Return histogram of labels from DB."""
    return db.count_labels()
