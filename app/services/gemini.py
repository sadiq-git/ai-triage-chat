import requests
import os

API_KEY = os.getenv("GEMINI_API_KEY")

def ask(prompt: str) -> str:
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    r = requests.post(f"{url}?key={API_KEY}", json=payload, headers=headers, timeout=30)
    if r.status_code == 200:
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    return f"[error {r.status_code}] {r.text[:120]}"
