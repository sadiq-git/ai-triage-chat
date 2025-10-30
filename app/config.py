from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "triage.db"
ERROR_LEVELS = ["ERROR", "FATAL", "EXCEPTION", "CRITICAL"]
CORRELATION_ID_REGEX = r"(?i)\b(?:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}|[0-9a-f]{16,40})\b"
ENDPOINT_REGEX = r"https?://[\w\.-]+(?::\d+)?(?:/[\w\-\./%\?=&]+)?"
ACCOUNT_HINT_REGEX = r"\b(?:corp(?:orate)?|personal|test|svc|service)\b"
