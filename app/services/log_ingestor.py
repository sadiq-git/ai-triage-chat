from typing import List, Dict, Any
from app.services.log_parser import parse_payload
from app.store import db

def ingest(payload) -> int:
    rows = parse_payload(payload)
    return db.insert_logs(rows)
