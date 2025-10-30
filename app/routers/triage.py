import uuid
from fastapi import APIRouter, HTTPException
from app.models import StartSessionRequest, AnswerRequest
from app.store import db
from app.services import analysis
from app.services.formatter import format_snow
from fastapi.responses import PlainTextResponse
from app.services.llm_client import summarize_logs, label_issue



router = APIRouter(prefix="/triage", tags=["triage"])

QUESTIONS = [
    "Hello! I'm here to help you with your issue today. Could you please start by providing your name or the name of the affected user?",
    "What is the front-end channel application that's displaying the error?",
    "Let me check our logs for relevant details... (Scanning). I found some details in the logs. One major point of failure (POF) occurred at {POF_TS}. Does this sound familiar as the issue you're facing?",
    "I've also pulled a CorrelationID from the logs: {CORR_ID}. Can you confirm if this is the same one you're seeing?",
    "Please provide the CHS URL or endpoint that you are trying to access.",
    "Which account are you using to access this service? Is it a personal or a corporate account?",
    "When was the last time this system/application worked for you? Please provide the date or duration since then.",
    "Have you tested this issue on different machines or with different accounts/users? If so, what were the results?",
    "The development team has mentioned that a full log analysis is required. Are you able to access these logs, or would you like me to assist with that?",
    "To summarize the information we've gathered, I'll prepare a SNOW-ready summary. Please confirm if everything looks correct."
]

def build_question(step: int):
    if step == 2 or step == 3:
        found = analysis.find_pof_and_corr()
        pof_ts = found["pof_timestamp"] if found else "-"
        corr = found["correlation_id"] if found else "-"
        text = QUESTIONS[step].replace("{POF_TS}", str(pof_ts)).replace("{CORR_ID}", str(corr))
        return text, found or {}
    return QUESTIONS[step], {}

@router.post("/start")
def start_session(req: StartSessionRequest):
    sid = str(uuid.uuid4())
    db.create_session(sid)
    q, _ = build_question(0)
    db.put_answer(sid, 0, q, None)
    return {"session_id": sid, "question": q, "step": 0}

@router.post("/{session_id}/answer")
def answer(session_id: str, req: AnswerRequest):
    sess = db.get_session(session_id)
    if not sess or sess["closed"] == 1:
        raise HTTPException(status_code=404, detail="Session not found or closed")
    step = sess["step"]
    # Save answer to current step question
    curr = db.get_answers(session_id)[-1] if db.get_answers(session_id) else {"question": QUESTIONS[0]}
    db.put_answer(session_id, step, curr["question"], req.answer)

    # Advance
    step += 1
    if step >= len(QUESTIONS):
        db.close_session(session_id)
        return {"message": "Session complete. Retrieve summary.", "summary_url": f"/triage/{session_id}/summary"}

    q, context = build_question(step)
    db.update_step(session_id, step)
    db.put_answer(session_id, step, q, None)
    return {"session_id": session_id, "question": q, "step": step, "context": context}

@router.get("/{session_id}")
def get_session(session_id: str):
    s = db.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": s, "answers": db.get_answers(session_id)}

@router.get("/{session_id}/summary", response_class=PlainTextResponse)
def summary(session_id: str):
    answers = db.get_answers(session_id)
    summary_map = {
        "1. Affected User": answers[0]["answer"] if len(answers) > 0 else None,
        "2. Point of Failure (timestamp)": None,
        "3. Front-end Channel Application": answers[1]["answer"] if len(answers) > 1 else None,
        "4. CHS URL/Endpoint": answers[4]["answer"] if len(answers) > 4 else None,
        "5. CorrelationID": None,
        "6. Account Used": answers[5]["answer"] if len(answers) > 5 else None,
        "7. Last Working Time": answers[6]["answer"] if len(answers) > 6 else None,
        "8. Tested on Different Machines/Accounts": answers[7]["answer"] if len(answers) > 7 else None,
    }

    found = analysis.find_pof_and_corr()
    if found:
        summary_map["2. Point of Failure (timestamp)"] = found.get("pof_timestamp")
        summary_map["5. CorrelationID"] = found.get("correlation_id")
        if found.get("ai_summary"):
            summary_map["ai_summary"] = found["ai_summary"]   # consumed by formatter
        if found.get("ai_label"):
            summary_map["ai_label"] = found["ai_label"]       # consumed by formatter

    text = format_snow(summary_map, answers)
    return text