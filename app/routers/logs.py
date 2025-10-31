from fastapi import APIRouter
from app.store import db
from fastapi import APIRouter, Query
from typing import Optional
from app.services import analysis

router = APIRouter(prefix="/logs", tags=["logs"])

@router.get("/by-correlation/{corr_id}")
def by_correlation(corr_id: str):
    rows = db.search_correlation(corr_id)
    return {"count": len(rows), "logs": rows[:200]}  # cap for safety

@router.get("/window")
def get_logs_window(
    start: Optional[str] = Query(None, description="ISO timestamp start (inclusive)"),
    end: Optional[str]   = Query(None, description="ISO timestamp end (inclusive)"),
    limit: int = Query(200, ge=1, le=10000),
    summarize: bool = Query(False, description="If true, also return ai_summary/ai_label")
):
    """
    Fetch logs within a time window. Example:
      /logs/window?start=2025-10-29T09:30:00Z&end=2025-10-29T09:40:00Z&limit=200&summarize=true
    """
    if summarize:
        return analysis.summarize_window(start, end, limit)
    return {"logs": db.fetch_logs_window(start, end, limit)}
