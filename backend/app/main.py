from __future__ import annotations


import os
from pathlib import Path
from typing import Any


from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


from app import assistant
from app.compiler.pipeline import VERSION, run_pipeline


BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
load_dotenv(BACKEND_DIR / ".env")


app = FastAPI(title="FormaLang", version=VERSION)



class RunRequest(BaseModel):
    source: str


class AssistRequest(BaseModel):
    action: str
    question: str = ""
    source: str = ""
    result: dict[str, Any] = Field(default_factory=dict)



@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": VERSION,
        "ai_configured": bool(os.getenv("GROQ_API_KEY", "").strip()),
    }



@app.post("/api/run")
def run(req: RunRequest) -> dict:
    return run_pipeline(req.source).to_dict()



@app.post("/api/assist")
def assist(req: AssistRequest) -> dict:
    return assistant.ask(req.action, req.source, req.result, req.question)



# Serve the frontend. Mounted last so the /api routes take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend") 