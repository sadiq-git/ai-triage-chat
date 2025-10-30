# app/services/llm_client.py
import os
from typing import Optional
from dotenv import load_dotenv, find_dotenv
import google.generativeai as genai

_model = None  # cached model instance

def _init_model():
    """Load .env and initialize the Gemini model once."""
    global _model
    if _model is not None:
        return _model

    # Load .env from project root (works with reloader/spawn too)
    load_dotenv(find_dotenv())

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY (or LLM_API_KEY) in your .env")

    genai.configure(api_key=api_key)
    model_id = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    _model = genai.GenerativeModel(model_id)
    return _model

def ping_gemini():
    """Simple health check."""
    try:
        model = _init_model()
        resp = model.generate_content("ping")
        return {"ok": True, "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), "response": resp.text[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def summarize_logs(pof_message: str, endpoint: str, corr_id: str) -> str:
    """Summarize a log event using Gemini; returns '' on failure."""
    try:
        model = _init_model()
        prompt = (
            "Summarize the application issue in ≤3 short lines. "
            "Use plain English, no PII. Include likely cause keywords (timeout/auth/db/internal-error/network).\n\n"
            f"POF Message: {pof_message}\nEndpoint: {endpoint}\nCorrelation ID: {corr_id}"
        )
        resp = model.generate_content(prompt)
        return (resp.text or "").strip()
    except Exception:
        return ""
    
def label_issue(pof_message: str, endpoint: str, corr_id: str) -> str:
    """
    Uses Gemini to classify the likely category of the issue.
    Returns short snake_case label (e.g., timeout_error, auth_failure, db_error).
    """
    try:
        model = _init_model()
        prompt = (
            "Classify the issue below into one concise category label. "
            "Choose from: timeout_error, auth_failure, network_error, database_error, null_pointer, configuration_error, other.\n\n"
            f"POF Message: {pof_message}\n"
            f"Endpoint: {endpoint}\n"
            f"Correlation ID: {corr_id}\n\n"
            "Return only the label name, nothing else."
        )
        resp = model.generate_content(prompt)
        label = (resp.text or "").strip().lower().replace(" ", "_")
        return label or "unknown"
    except Exception as e:
        return f"[label_error: {e}]"

