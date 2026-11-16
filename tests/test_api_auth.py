"""
Endpoint tests: the user identity must come from the verified token, never from X-User-ID.

Run: uv run --with pytest --with httpx pytest tests/test_api_auth.py
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import auth  # noqa: E402
import main  # noqa: E402

TOKENS = {
    "bob-token": auth.AuthenticatedUser(user_id="bob-sub", username="bob"),
}


class _FakeVerifier:
    def verify(self, token):
        if token not in TOKENS:
            import jwt
            raise jwt.InvalidTokenError("unknown test token")
        return TOKENS[token]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(auth, "get_verifier", lambda: _FakeVerifier())
    return TestClient(main.app)


BOB = {"Authorization": "Bearer bob-token"}


@pytest.mark.parametrize("method,path", [
    ("get", "/v1/list/models"),
    ("get", "/v1/list/mcp_server"),
    ("post", "/v1/remove/history"),
    ("post", "/v1/stop/stream/some-stream"),
    ("delete", "/v1/remove/mcp_server/x"),
])
def test_requests_without_token_are_rejected(client, method, path):
    r = getattr(client, method)(path, headers={"X-User-ID": "alice-sub"})
    assert r.status_code == 401


def test_old_shared_api_key_is_rejected(client):
    r = client.get("/v1/list/models", headers={"Authorization": "Bearer 123456"})
    assert r.status_code == 401


def test_x_user_id_header_is_ignored_for_history(client, monkeypatch):
    deleted = []

    async def fake_delete(user_id):
        deleted.append(user_id)

    monkeypatch.setattr(main, "DDB_TABLE", "test-table")
    monkeypatch.setattr(main, "delete_user_message", fake_delete)
    r = client.post("/v1/remove/history", headers={**BOB, "X-User-ID": "alice-sub"})
    assert r.status_code == 200
    assert deleted == ["bob-sub"]


def test_cannot_stop_or_delete_another_users_stream(client, monkeypatch):
    deleted = []

    async def fake_get_stream_id(stream_id):
        return "alice-sub"

    async def fake_delete_stream_id(stream_id):
        deleted.append(stream_id)

    monkeypatch.setattr(main, "get_stream_id", fake_get_stream_id)
    monkeypatch.setattr(main, "delete_stream_id", fake_delete_stream_id)
    r = client.post("/v1/stop/stream/alice-stream", headers={**BOB, "X-User-ID": "alice-sub"})
    assert r.json()["errno"] == -1
    assert deleted == []


def test_list_models_with_valid_token(client):
    r = client.get("/v1/list/models", headers=BOB)
    assert r.status_code == 200
