"""
Integration tests for FastAPI endpoints: /health, /config, sessions, and messages.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert data["database"] == "connected"


def test_config_endpoint():
    response = client.get("/config")
    assert response.status_code == 200
    data = response.json()
    assert "active_provider" in data
    assert "similarity_threshold" in data
    assert "supported_providers" in data


def test_session_lifecycle():
    # 1. Create Session
    create_res = client.post("/sessions", json={"user_metadata": {"title": "Test PM Session"}})
    assert create_res.status_code == 201
    session_data = create_res.json()
    session_id = session_data["id"]
    assert session_data["user_metadata"]["title"] == "Test PM Session"

    # 2. List Sessions
    list_res = client.get("/sessions")
    assert list_res.status_code == 200
    sessions = list_res.json()
    assert any(s["id"] == session_id for s in sessions)

    # 3. Get Session History
    hist_res = client.get(f"/sessions/{session_id}")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert "messages" in hist_data
    assert "artifacts" in hist_data

    # 4. Delete Session
    del_res = client.delete(f"/sessions/{session_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # 5. Verify 404 after deletion
    get_del = client.get(f"/sessions/{session_id}")
    assert get_del.status_code == 404


def test_test_model_endpoint():
    res = client.post("/config/test-model", json={"provider": "ollama", "model": "phi3"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "phi3" in data["model"]


def test_send_message_endpoint():
    # 1. Create a session
    create_res = client.post("/sessions", json={"user_metadata": {"title": "API Turn Test"}})
    assert create_res.status_code == 201
    session_id = create_res.json()["id"]

    # 2. Send a grounded question
    msg_res = client.post(
        f"/sessions/{session_id}/messages",
        json={"content": "What did Elena Verna say about B2B pricing experiments?"}
    )
    assert msg_res.status_code == 200
    data = msg_res.json()
    assert "assistant_message" in data
    assert "citations" in data
    assert len(data["citations"]) > 0
    assert data["provider_used"] == "ollama"
    assert len(data["assistant_message"]["content"]) > 0


def test_batch_delete_sessions():
    res1 = client.post("/sessions", json={"user_metadata": {"title": "Batch Test 1"}})
    res2 = client.post("/sessions", json={"user_metadata": {"title": "Batch Test 2"}})
    assert res1.status_code == 201
    assert res2.status_code == 201
    id1 = res1.json()["id"]
    id2 = res2.json()["id"]

    batch_del = client.post("/sessions/batch-delete", json={"ids": [id1, id2]})
    assert batch_del.status_code == 200
    assert batch_del.json()["deleted_count"] == 2

    assert client.get(f"/sessions/{id1}").status_code == 404
    assert client.get(f"/sessions/{id2}").status_code == 404

