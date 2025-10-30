from fastapi import APIRouter, Query
from app.services.labeler import label_recent_logs, label_stats

router = APIRouter(prefix="/labeler", tags=["labeler"])

@router.post("/analyze")
def analyze(limit: int = Query(300, ge=1, le=2000)):
    return {"labeled": label_recent_logs(limit)}

@router.get("/stats")
def stats():
    return {"stats": label_stats()}
