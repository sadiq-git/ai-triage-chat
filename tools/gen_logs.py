import json
import random
from datetime import datetime, timedelta
import uuid
from pathlib import Path

LEVELS = ["INFO", "WARN", "ERROR", "FATAL"]
LABELS = [
    "auth_failure", "network_timeout", "database_error", "cache_error",
    "null_pointer", "api_throttle", "config_error", "other"
]
ENDPOINTS = [
    "/v1/payments", "/v1/transfer", "/v1/login", "/v1/logout", "/v1/report",
    "/v1/cache/refresh", "/v1/db/query", "/v1/settings/update"
]

# 🔢 Generate dummy logs
logs = []
now = datetime.utcnow()
for i in range(200):
    ts = now - timedelta(minutes=random.randint(1, 1440))  # last 24 hours
    label = random.choice(LABELS)
    endpoint = random.choice(ENDPOINTS)
    level = random.choices(LEVELS, weights=[3, 2, 8, 1])[0]
    cid = str(uuid.uuid4())

    message_templates = {
        "auth_failure": [
            f"Auth token expired for session {cid}",
            f"Invalid credentials on endpoint {endpoint}",
        ],
        "network_timeout": [
            f"Upstream timeout contacting {endpoint}",
            f"Socket timeout connecting to {endpoint}",
        ],
        "database_error": [
            f"DB deadlock detected in transaction for {endpoint}",
            f"SQL error: constraint violation at {endpoint}",
        ],
        "cache_error": [
            f"Redis unavailable while accessing cache for {endpoint}",
            f"Cache key missing for {endpoint}",
        ],
        "null_pointer": [
            f"NullPointerException in {endpoint}",
            f"TypeError: Cannot read property 'status' of undefined in {endpoint}",
        ],
        "api_throttle": [
            f"429 Too Many Requests at {endpoint}",
            f"API rate limit exceeded for {endpoint}",
        ],
        "config_error": [
            f"Invalid configuration found in service {endpoint}",
            f"Missing env variable for {endpoint}",
        ],
        "other": [
            f"General warning from {endpoint}",
            f"Unexpected error pattern seen in {endpoint}",
        ],
    }

    logs.append({
        "source": "app.log",
        "ts": ts.isoformat(),
        "level": level,
        "message": random.choice(message_templates[label]),
        "correlation_id": cid,
        "endpoint": endpoint,
        "account": random.choice(["personal", "corporate"]),
        "label": label,
    })

out = Path("synthetic_bulk_extended.jsonl")
out.write_text("\n".join(json.dumps(l) for l in logs))
print(f"✅ Generated {len(logs)} extended dummy logs -> {out.resolve()}")
