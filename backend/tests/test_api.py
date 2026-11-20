from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_run_returns_contract_fields():
    r = client.post("/api/run", json={"source": "int x = 1;"})
    body = r.json()
    for key in ["ok", "output", "diagnostics", "stages", "tokens", "ast", "symbols", "trace"]:
        assert key in body


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "FormaLang" in r.text