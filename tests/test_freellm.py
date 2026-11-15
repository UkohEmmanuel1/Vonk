import asyncio

import httpx
import pytest


@pytest.fixture(autouse=True)
def isolated_health_db(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_PROVIDER_HEALTH_DB", str(tmp_path / "provider-health.sqlite3"))

from src.inference.freellm import FreeLLMError, complete, list_models


def _mock_client(monkeypatch, handler):
    original = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )


def test_catalogue_prioritizes_opencode_and_filters_unavailable(monkeypatch):
    monkeypatch.setenv("FREELLM_BASE_URL", "https://gateway.example/v1")
    monkeypatch.setenv("FREELLM_API_KEY", "test-key")

    def handler(request):
        assert request.url.path == "/v1/models"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "groq::llama", "provider": "groq"},
                    {"id": "opencode::free-model", "provider": "opencode"},
                    {
                        "id": "opencode::disabled",
                        "provider": "opencode",
                        "available": False,
                    },
                ]
            },
        )

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
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "opencode::first", "provider": "opencode"},
                        {"id": "groq::backup", "provider": "groq"},
                    ]
                },
            )
        import json
        body = json.loads(request.content)
        attempted.append(body["model"])
        if body["model"] == "opencode::first":
            return httpx.Response(429, json={"error": "limited"})
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": "ok"}}]
        })

    _mock_client(monkeypatch, handler)
    result = asyncio.run(
        complete(
            model="opencode", messages=[{"role": "user", "content": "hello"}]
        )
    )
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



def test_circuit_breaker_opens_after_repeated_provider_failures(tmp_path, monkeypatch):
    from src.inference import provider_health

    monkeypatch.setenv("NEXUS_PROVIDER_HEALTH_DB", str(tmp_path / "health.sqlite3"))
    for _ in range(3):
        provider_health.record_failure("provider::model", "rate_limit")
    assert provider_health.is_available("provider::model") is False
    snapshot = provider_health.snapshot()
    assert snapshot[0]["circuit"] == "open"


def test_circuit_breaker_resets_after_success(tmp_path, monkeypatch):
    from src.inference import provider_health

    monkeypatch.setenv("NEXUS_PROVIDER_HEALTH_DB", str(tmp_path / "health.sqlite3"))
    for _ in range(3):
        provider_health.record_failure("provider::model", "upstream")
    provider_health.record_success("provider::model")
    assert provider_health.is_available("provider::model") is True
    assert provider_health.snapshot()[0]["consecutive_failures"] == 0


def test_streaming_forwards_sse_and_uses_gateway_stream_flag(monkeypatch):
    monkeypatch.setenv("FREELLM_BASE_URL", "https://gateway.example/v1")
    monkeypatch.setenv("FREELLM_API_KEY", "test-key")

    def handler(request):
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [
                {"id": "opencode::stream-model", "provider": "opencode"}
            ]})
        assert request.url.path == "/v1/chat/completions"
        import json
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text='data: {"choices":[{"delta":{"content":"hello"}}]}\\n\\ndata: [DONE]\\n\\n',
        )

    _mock_client(monkeypatch, handler)

    async def collect():
        return [chunk async for chunk in stream(
            model="opencode", messages=[{"role": "user", "content": "hello"}]
        )]

    from src.inference.freellm import stream
    chunks = asyncio.run(collect())
    assert any("hello" in chunk for chunk in chunks)
