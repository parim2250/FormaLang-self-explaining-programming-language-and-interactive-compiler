"""Forma Assistant: optional Groq explanations built from compiler data.

The assistant never runs or checks code. It only explains what the compiler
already produced. Without GROQ_API_KEY, no request is sent to Groq.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
TIMEOUT_SECONDS = 30
MAX_TRACE_STEPS = 40
MAX_QUESTION_CHARS = 500

ACTIONS = {
    "explain_code": "Explain what this FormaLang program does, step by step, in plain language.",
    "explain_error": "Explain the problem the compiler reported, why it happened, and how to fix it.",
    "explain_output": "Explain why the program printed this output.",
    "explain_flow": "Explain how the compiler stages and the execution trace ran for this program.",
    "suggest_fix": "Suggest a minimal fix for the reported problem. Show only the corrected line.",
    "ask": "Answer the user's question about this program.",
}

SYSTEM_PROMPT = (
    "You are Forma Assistant, the explainer inside FormaLang, a small C-style teaching language. "
    "You receive structured data from FormaLang's own compiler: stages, problems, symbols, "
    "output and execution trace. Base every statement on that data. "
    "Do not claim to have run the code yourself. Keep answers short: a few sentences or a short list. "
    "If the data does not answer the question, say so."
)


class GroqError(Exception):
    """Groq answered with an HTTP error. Carries the status and Groq's own message."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def is_configured() -> bool:
    return bool(os.environ.get("GROQ_API_KEY", "").strip())


def model_name() -> str:
    return os.environ.get("GROQ_MODEL", "").strip() or DEFAULT_MODEL


def build_context(source: str, result: dict[str, Any]) -> dict[str, Any]:
    trace = list(result.get("trace") or [])
    half = MAX_TRACE_STEPS // 2
    if len(trace) > MAX_TRACE_STEPS:
        trace_part = trace[:half] + trace[-half:]
        trace_note = f"Showing the first {half} and last {half} of {len(trace)} steps."
    else:
        trace_part = trace
        trace_note = f"All {len(trace)} steps shown."
    return {
        "source": source,
        "ok": result.get("ok"),
        "stages": result.get("stages", []),
        "problems": result.get("diagnostics", []),
        "output": result.get("output", []),
        "symbols": result.get("symbols", []),
        "trace": trace_part,
        "trace_note": trace_note,
    }


def build_messages(action: str, source: str, result: dict[str, Any], question: str = "") -> list[dict[str, str]]:
    if action not in ACTIONS:
        raise ValueError(f"Unknown assistant action '{action}'.")
    task = ACTIONS[action]
    if action == "ask":
        question = question.strip()[:MAX_QUESTION_CHARS]
        if not question:
            raise ValueError("Type a question first.")
        task = f"{task} Question: {question}"
    context = build_context(source, result)
    user = f"{task}\n\nCompiler data (JSON):\n{json.dumps(context, ensure_ascii=False, indent=1)}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _groq_detail(response: httpx.Response) -> str:
    """Pull Groq's own error message out of the response body."""
    try:
        return str(response.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return response.text[:200] or "no details returned"


def call_groq(messages: list[dict[str, str]]) -> str:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    response = httpx.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model_name(), "messages": messages, "temperature": 0.2, "max_tokens": 600},
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        raise GroqError(response.status_code, _groq_detail(response))
    return response.json()["choices"][0]["message"]["content"].strip()


def _http_error_text(error: GroqError) -> str:
    if error.status == 401:
        return "Groq rejected the API key (HTTP 401). Check GROQ_API_KEY in backend/.env, then restart the server."
    if error.status == 404:
        return (
            f"Groq could not find the model '{model_name()}' (HTTP 404): {error.detail}. "
            "Set GROQ_MODEL in backend/.env to a model your account can use, then restart the server."
        )
    return f"Groq returned HTTP {error.status}: {error.detail}"


def ask(action: str, source: str, result: dict[str, Any], question: str = "") -> dict[str, Any]:
    if not is_configured():
        return {
            "ok": False,
            "configured": False,
            "text": "",
            "error": "AI is not configured. Add GROQ_API_KEY to backend/.env and restart the server. The compiler works without it.",
        }
    try:
        messages = build_messages(action, source, result, question)
    except ValueError as error:
        return {"ok": False, "configured": True, "text": "", "error": str(error)}
    try:
        text = call_groq(messages)
    except GroqError as error:
        return {"ok": False, "configured": True, "text": "", "error": _http_error_text(error)}
    except httpx.HTTPError:
        return {
            "ok": False,
            "configured": True,
            "text": "",
            "error": "Could not reach Groq. Check the internet connection.",
        }
    return {"ok": True, "configured": True, "text": text, "error": ""}