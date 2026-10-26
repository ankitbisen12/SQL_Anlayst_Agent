import json

from fastapi.testclient import TestClient

import api.main as api_main


def fake_stream(question, history):
    yield {"type": "status", "step": "generate_sql", "message": "Writing the SQL query"}
    yield {"type": "sql", "sql": "SELECT 1"}
    yield {"type": "token", "content": "Hello"}
    yield {"type": "done", "intent": "data_question", "sql": "SELECT 1", "answer": "Hello", "attempts": 1, "latency_ms": 5}


def parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        data = [line[6:] for line in block.splitlines() if line.startswith("data: ")]
        if data:
            events.append(json.loads(data[0]))
    return events


def test_health():
    assert TestClient(api_main.app).get("/api/health").json() == {"status": "ok"}


def test_stream_emits_events(monkeypatch):
    monkeypatch.setattr(api_main, "stream_agent", fake_stream)
    resp = TestClient(api_main.app).post("/api/chat/stream", json={"question": "hi", "history": []})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert [e["type"] for e in parse_sse(resp.text)] == ["status", "sql", "token", "done"]


def test_stream_reports_errors_without_leaking_internals(monkeypatch):
    def broken(question, history):
        raise RuntimeError("boom")
        yield  # pragma: no cover

    monkeypatch.setattr(api_main, "stream_agent", broken)
    resp = TestClient(api_main.app).post("/api/chat/stream", json={"question": "hi"})
    assert parse_sse(resp.text)[-1]["type"] == "error"
    assert "boom" not in resp.text


def test_validation_rejects_empty_question():
    assert TestClient(api_main.app).post("/api/chat/stream", json={"question": ""}).status_code == 422


def test_api_key_enforced(monkeypatch):
    monkeypatch.setattr(api_main.settings, "app_api_key", "secret")
    monkeypatch.setattr(api_main, "stream_agent", fake_stream)
    client = TestClient(api_main.app)
    assert client.post("/api/chat/stream", json={"question": "hi"}).status_code == 401
    assert client.post("/api/chat/stream", json={"question": "hi"}, headers={"X-API-Key": "secret"}).status_code == 200
