import re
import json
from typing import Dict, Any, List, Optional
from dateutil import parser as dtp
from app.config import CORRELATION_ID_REGEX, ENDPOINT_REGEX, ACCOUNT_HINT_REGEX, ERROR_LEVELS

CID = re.compile(CORRELATION_ID_REGEX)
URL = re.compile(ENDPOINT_REGEX)
ACC = re.compile(ACCOUNT_HINT_REGEX, re.IGNORECASE)

def normalize_ts(ts: Optional[str]) -> Optional[str]:
    if not ts:
        return None
    try:
        return dtp.parse(ts).isoformat()
    except Exception:
        return None

def level_from_message(level: Optional[str], msg: Optional[str]) -> Optional[str]:
    if level:
        u = level.upper()
        for e in ERROR_LEVELS + ["WARN","INFO","DEBUG","TRACE"]:
            if u.startswith(e):
                return e
    if msg:
        upper = msg.upper()
        for e in ERROR_LEVELS:
            if e in upper:
                return e
    return level or "INFO"

def parse_one(raw: Dict[str, Any]) -> Dict[str, Any]:
    msg = raw.get("message") or raw.get("msg") or raw.get("log") or ""
    text = json.dumps(raw, default=str) + " " + (msg or "")
    found_cid = None
    m = CID.search(text)
    if m:
        found_cid = m.group(0)
    found_url = None
    m2 = URL.search(text)
    if m2:
        found_url = m2.group(0)
    found_acc = None
    m3 = ACC.search(text)
    if m3:
        found_acc = m3.group(0).lower()
    ts = normalize_ts(raw.get("timestamp") or raw.get("@timestamp") or raw.get("time") or raw.get("ts"))
    level = level_from_message(raw.get("level"), msg)
    return {
        "source": raw.get("source") or raw.get("logger") or raw.get("service"),
        "ts": ts,
        "level": level,
        "message": msg or text[:512],
        "correlation_id": raw.get("correlation_id") or found_cid,
        "endpoint": raw.get("endpoint") or found_url,
        "account": raw.get("account") or found_acc,
    }

def parse_payload(payload: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if isinstance(payload, list):
        for item in payload:
            rows.append(parse_one(dict(item)))
        return rows
    if isinstance(payload, str):
        for line in payload.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                obj = {"message": line}
            rows.append(parse_one(obj))
        return rows
    if isinstance(payload, dict):
        rows.append(parse_one(payload))
        return rows
    return rows
