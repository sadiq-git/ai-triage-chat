from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List

class StartSessionRequest(BaseModel):
    initiator: Optional[str] = None

class AnswerRequest(BaseModel):
    answer: str = Field(..., description="User's answer text")

class LogEntry(BaseModel):
    timestamp: Optional[str] = None
    level: Optional[str] = None
    message: Optional[str] = None
    source: Optional[str] = None
    correlation_id: Optional[str] = None
    endpoint: Optional[str] = None
    account: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None

class IngestRequest(BaseModel):
    logs: Optional[List[LogEntry]] = None
    jsonl: Optional[str] = None
