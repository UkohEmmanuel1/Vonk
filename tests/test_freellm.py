import asyncio

import httpx
import pytest

from src.inference.freellm import FreeLLMError, complete, list_models


def _mock_client(monkeypatch, handler):
    original = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )


def test_catalogue_prioritizes_opencode_and_filters_unavailable(monkeypatch):
    monkeypatch.setenv("FREELLM_BASE_URL", "https://gateway.example/v1")
    monkeypatch.setenv("FREELLM_API_KEY", "test-key")

    def handler(request):
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [
            {"id": "groq::llama", "provider": "groq"},
            {"id": "opencode::free-model", "provider": "opencode"},
            {"id": "opencode::disabled", "provider": "opencode", "available": False},
        ]})

    _mock_client(monkeypatch, handler)
    items = asyncio.run(list_models())
    assert [item["id"] for item in items] == [
        "groq::llama", "opencode::free-model"
    ]


def test_fallback_uses_next_catalogue_model_after_rate_limit(monkeypatch):
    monkeypatch.setenv("FREELLM_BASE_URL", "https://gateway.example/v1")
    monkeypatch.setenv("FREELLM_API_KEY", "test-key")
    attempted = []

    def handler(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [
                {"id": "opencode::first", "provider": "opencode"},
                {"id": "groq::backup", "provider": "groq"},
            ]})
        import json
        body = json.loads(request.content)
        attempted.append(body["model"])
        if body["model"] == "opencode::first":
            return httpx.Response(429, json={"error": "limited"})
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": "ok"}}]
        })

    _mock_client(monkeypatch, handler)
    result = asyncio.run(complete(
        model="opencode", messages=[{"role": "user", "content": "hello"}]
    ))
    assert attempted == ["opencode::first", "groq::backup"]
    assert result["vonk"]["fallback_used"] is True
    assert result["choices"][0]["message"]["content"] == "ok"


def test_gateway_key_is_required(monkeypatch):
    monkeypatch.delenv("FREELLM_API_KEY", raising=False)
    monkeypatch.setenv("FREELLM_BASE_URL", "https://gateway.example/v1")
    with pytest.raises(FreeLLMError):
        asyncio.run(list_models())


def test_insecure_remote_gateway_url_is_rejected(monkeypatch):
    monkeypatch.setenv("FREELLM_BASE_URL", "http://gateway.example/v1")
    monkeypatch.setenv("FREELLM_API_KEY", "test-key")
    with pytest.raises(FreeLLMError):
        asyncio.run(list_models())
