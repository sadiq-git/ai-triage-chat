from fastapi import APIRouter
from app.services.llm_client import ping_gemini

router = APIRouter(prefix="/ai", tags=["ai"])

@router.get("/ping")
def ping():
    return ping_gemini()
