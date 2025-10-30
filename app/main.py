from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv, find_dotenv

from app.store import db
from app.routers import triage, webhook
from app.routers import ai as ai_router
from app.routers import logs as logs_router
from app.routers import labeler as labeler_router
from app.routers import triage_dyn as triage_dyn_router


# from app.routers import triage_dyn as triage_dyn_router  # (when you enable dynamic mode)

load_dotenv(find_dotenv())

app = FastAPI(title="AI Triage POC", version="0.1.0")

app.include_router(triage_dyn_router.router)

# CORS first
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=86400,
)

@app.on_event("startup")
def on_startup():
    db.init()

@app.get("/healthz")
def health():
    return {"ok": True}

@app.get("/")
def root():
    return {"message": "AI Triage API. See /docs"}

# Routers
app.include_router(webhook.router)
app.include_router(triage.router)
app.include_router(ai_router.router)
app.include_router(logs_router.router)
app.include_router(labeler_router.router)
# app.include_router(triage_dyn_router.router)  # (uncomment when you add the dynamic endpoints)
