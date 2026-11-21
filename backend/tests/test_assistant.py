"""Phase 9 tests: Forma Assistant. No network calls are made."""

from fastapi.testclient import TestClient

from app import assistant
from app.compiler.pipeline import run_pipeline
from app.main import app

client = TestClient(app)


def run_data(source: str) -> dict:
    return run_pipeline(source).to_dict()


def test_without_key_nothing_is_sent(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    def must_not_call(messages):
        raise AssertionError("Groq must not be called without a key")

    monkeypatch.setattr(assistant, "call_groq", must_not_call)
    result = assistant.ask("explain_code", "int x = 1;", run_data("int x = 1;"))
    assert result["ok"] is False
    assert result["configured"] is False
    assert "GROQ_API_KEY" in result["error"]


def test_with_key_returns_model_text(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(assistant, "call_groq", lambda messages: "stub reply")
    result = assistant.ask("explain_code", "int x = 1;", run_data("int x = 1;"))
    assert result == {"ok": True, "configured": True, "text": "stub reply", "error": ""}


def test_prompt_carries_compiler_problems(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    captured = {}

    def capture(messages):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(assistant, "call_groq", capture)
    source = "print(y);"
    assistant.ask("explain_error", source, run_data(source))
    user_text = captured["messages"][1]["content"]
    assert "E301" in user_text
    assert "print(y);" in user_text


def test_unknown_action_is_rejected(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(assistant, "call_groq", lambda messages: "should not run")
    result = assistant.ask("hack", "int x = 1;", run_data("int x = 1;"))
    assert result["ok"] is False


def test_ask_needs_a_question(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(assistant, "call_groq", lambda messages: "should not run")
    result = assistant.ask("ask", "int x = 1;", run_data("int x = 1;"), question="   ")
    assert result["ok"] is False
    assert "question" in result["error"]


def test_long_trace_is_trimmed():
    source = "int i = 0; while (i < 300) { i++; }"
    context = assistant.build_context(source, run_data(source))
    assert len(context["trace"]) == assistant.MAX_TRACE_STEPS
    assert "of" in context["trace_note"]


def test_health_reports_missing_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    data = client.get("/api/health").json()
    assert data["ai_configured"] is False


def test_assist_endpoint_without_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    response = client.post("/api/assist", json={
        "action": "explain_code",
        "source": "int x = 1;",
        "result": run_data("int x = 1;"),
    })
    assert response.status_code == 200
    assert response.json()["configured"] is False