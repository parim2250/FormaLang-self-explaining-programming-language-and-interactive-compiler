
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_tokens_endpoint_lists_tokens_with_paths():
    r = client.post("/api/tokens", json={"source": "int x = 1;"})
    assert r.status_code == 200
    body = r.json()
    kinds = [t["kind"] for t in body["tokens"]]
    assert kinds[:2] == ["TYPE", "IDENT"]
    assert body["errors"] == []


def test_every_token_has_one_transition_per_step_of_its_path():
    r = client.post("/api/tokens", json={"source": "int total = 10 + 2;\nprint(total);"})
    for t in r.json()["tokens"]:
        assert isinstance(t["path"], list)
        assert len(t["transitions"]) == max(0, len(t["path"]) - 1)


def test_lexical_error_is_reported_not_raised():
    r = client.post("/api/tokens", json={"source": "int x = 1 # 2;"})
    assert r.status_code == 200
    assert any(e["code"] == "E102" for e in r.json()["errors"])