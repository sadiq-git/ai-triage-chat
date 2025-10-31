from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv, find_dotenv

# Internal imports
from app.store import db
from app.routers import (
    triage,
    webhook,
    ai as ai_router,
    logs as logs_router,
    labeler as labeler_router,
    triage_dyn,
    chat,
)

# ------------------------------------------------------------------
# 🌟 Environment + App setup
# ------------------------------------------------------------------
load_dotenv(find_dotenv())

app = FastAPI(title="AI Triage POC", version="0.1.0")

# ------------------------------------------------------------------
# 🌐 CORS setup
# ------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=86400,
)

# ------------------------------------------------------------------
# 🗄️ DB Initialization
# ------------------------------------------------------------------
@app.on_event("startup")
def on_startup():
    db.init()

# ------------------------------------------------------------------
# 🧠 Health & Root
# ------------------------------------------------------------------
@app.get("/healthz")
def health():
    return {"ok": True}

@app.get("/")
def root():
    return {"message": "AI Triage API. See /docs"}

# ------------------------------------------------------------------
# 🧩 Routers
# ------------------------------------------------------------------
# Classic components
app.include_router(webhook.router)
app.include_router(triage.router)
app.include_router(ai_router.router)
app.include_router(logs_router.router)
app.include_router(labeler_router.router)

# New dynamic triage + Gemini chat modules
app.include_router(triage_dyn.router)
app.include_router(chat.router)
