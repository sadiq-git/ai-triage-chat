from fastapi import APIRouter
from app.models import IngestRequest
from app.services import log_ingestor

router = APIRouter(prefix="/webhook", tags=["webhook"])

@router.post("/logs")
def webhook_logs(req: IngestRequest):
    payload = None
    if req.logs is not None:
        payload = [l.model_dump() for l in req.logs]
    elif req.jsonl is not None:
        payload = req.jsonl
    else:
        payload = []
    count = log_ingestor.ingest(payload)
    return {"ingested": count}
