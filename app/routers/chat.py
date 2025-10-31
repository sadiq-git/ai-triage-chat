# app/routers/chat.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services import llm_client

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str
    context: dict | None = None
    session_id: str | None = None

@router.post("")
async def chat(req: ChatRequest):
    """
    General Gemini Chat endpoint.
    Used by React UI when user types freeform questions (not just triage steps).
    """
    try:
        model = llm_client._init_model()
        full_prompt = req.message

        # Include context (from triage-dyn or logs)
        if req.context:
            full_prompt += f"\nContext:\n{req.context}"

        result = model.generate_content(full_prompt)
        return {"reply": result.text.strip()}

    except Exception as e:
        # Optional: auto fallback to REST API call if SDK fails
        from app.services.llm_fallback import ask
        try:
            reply = ask(req.message)
            return {"reply": reply}
        except Exception as fallback_err:
            raise HTTPException(
                status_code=500,
                detail=f"Gemini error: {str(e)} | fallback error: {str(fallback_err)}"
            )
