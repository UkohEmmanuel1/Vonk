"""Public discovery, operational checks, and shared-proxy regression tests."""

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.inference.server import create_app


@pytest.fixture
def production_client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_KEYS_DB", str(tmp_path / "keys.db"))
    monkeypatch.setenv("NEXUS_ADMIN_KEY", "admin")
    monkeypatch.setenv("NEXUS_RATE_LIMIT", "1000")
    engine = MagicMock()
    engine.model_id = "test-model"
    engine.generate.return_value = "hello"
    engine.tokenizer.encode.return_value = [1]
    with TestClient(create_app(engine, api_key="client")) as client:
        yield client


def test_public_discovery_schema_and_readiness(production_client):
    client = production_client
    assert client.get("/").json()["openapi"] == "/openapi.json"
    assert client.get("/ready").json()["status"] == "ready"
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/chat"]["post"]["security"] == [{"ApiKey": []}]
    assert "security" not in schema["paths"]["/health"]["get"]
    assert "client" not in str(schema)


def test_readiness_detects_unavailable_storage(production_client, monkeypatch):
    @contextmanager
    def unavailable(self):
        raise OSError("private filesystem path")
        yield  # pragma: no cover

    monkeypatch.setattr("src.utils.key_manager.KeyManager._connect", unavailable)
    result = production_client.get("/ready")
    assert result.status_code == 503
    assert "private" not in result.text
    assert production_client.get("/health").status_code == 200


def test_successful_users_do_not_share_auth_failure_budget(production_client):
    for _ in range(301):
        assert (
            production_client.post(
                "/chat", json={"message": "hi"}, headers={"X-API-Key": "client"}
            ).status_code
            == 200
        )


def test_request_ids_are_unique_and_credentials_are_not_logged(production_client, caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="src.inference.server"):
        first = production_client.post(
            "/chat?secret=query-secret",
            json={"message": "private-prompt"},
            headers={"X-API-Key": "client", "X-Request-ID": "untrusted-id"},
        )
        second = production_client.get("/health")
    assert len(first.headers["X-Request-ID"]) == 32
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]
    assert first.headers["X-Request-ID"] in caplog.text
    assert "query-secret" not in caplog.text
    assert "private-prompt" not in caplog.text



def test_managed_freellm_routes_are_authenticated_and_support_streaming(
    production_client, monkeypatch
):
    async def models():
        return [{"id": "opencode::sample", "provider": "opencode"}]

    async def completion(**kwargs):
        return {
            "choices": [{"message": {"role": "assistant", "content": "managed"}}],
            "model": "opencode::sample",
        }

    async def streaming(**kwargs):
        yield 'data: {"choices":[{"delta":{"content":"managed"}}]}\n\n'

    monkeypatch.setattr("src.inference.server.list_freellm_models", models)
    monkeypatch.setattr("src.inference.server.complete_freellm", completion)
    monkeypatch.setattr("src.inference.server.stream_freellm", streaming)
    monkeypatch.setenv("NEXUS_PROVIDER_HEALTH_DB", ":memory:")

    headers = {"X-API-Key": "client"}
    assert production_client.get("/v1/models").status_code == 401
    catalogue = production_client.get("/v1/models", headers=headers)
    assert catalogue.status_code == 200
    assert catalogue.json()["data"][0]["id"] == "opencode::sample"

    response = production_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "managed"

    streamed = production_client.post(
        "/v1/chat/completions",
        headers=headers,
        json={"messages": [{"role": "user", "content": "hello"}], "stream": True},
    )
    assert streamed.status_code == 200
    assert "text/event-stream" in streamed.headers["content-type"]
    assert "managed" in streamed.text

    health = production_client.get("/v1/provider-health", headers=headers)
    assert health.status_code == 200
