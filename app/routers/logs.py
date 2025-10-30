from fastapi import APIRouter
from app.store import db

router = APIRouter(prefix="/logs", tags=["logs"])

@router.get("/by-correlation/{corr_id}")
def by_correlation(corr_id: str):
    rows = db.search_correlation(corr_id)
    return {"count": len(rows), "logs": rows[:200]}  # cap for safety
