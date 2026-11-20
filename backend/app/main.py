from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.compiler.pipeline import VERSION, run_pipeline

BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
load_dotenv(BACKEND_DIR / ".env")

app = FastAPI(title="FormaLang", version=VERSION)


class RunRequest(BaseModel):
    source: str


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


# Serve the frontend. Mounted last so the /api routes take precedence.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")