"""FreeLLM-compatible OpenAI gateway with OpenCode-first routing and SSE streaming."""
from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from urllib.parse import urlsplit

import httpx

from src.inference import provider_health


class FreeLLMError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


_RETRYABLE = {404, 408, 409, 429, 500, 502, 503, 504}


def _configuration() -> tuple[str, str]:
    base_url = os.environ.get("FREELLM_BASE_URL", "").strip().rstrip("/")
    api_key = os.environ.get("FREELLM_API_KEY", "").strip()
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or (
            parsed.scheme != "https"
            and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        )
    ):
        raise FreeLLMError(503, "FreeLLM gateway is not configured with a valid HTTPS base URL")
    if not api_key or len(api_key) > 512 or not all(32 < ord(c) < 127 for c in api_key):
        raise FreeLLMError(503, "FreeLLM API key is not configured")
    return base_url, api_key


def _model_id(item: dict) -> str | None:
    value = item.get("id") or item.get("model")
    if not isinstance(value, str) or not value or len(value) > 300:
        return None
    provider = item.get("provider") or item.get("provider_id")
    if isinstance(provider, str) and provider and "::" not in value:
        value = f"{provider}::{value}"
    return value if all(31 < ord(char) < 127 for char in value) else None


def _is_opencode(item: dict, model_id: str) -> bool:
    provider = item.get("provider") or item.get("provider_id") or ""
    owner = item.get("owned_by") or ""
    return (
        isinstance(provider, str) and "opencode" in provider.lower()
    ) or (
        isinstance(owner, str) and "opencode" in owner.lower()
    ) or model_id.lower().startswith(("opencode::", "opencode/"))


def _catalog_items(payload: dict) -> list[dict]:
    items = payload.get("data", payload.get("models", []))
    if not isinstance(items, list):
        raise FreeLLMError(502, "FreeLLM returned an invalid model catalogue")
    result = []
    seen = set()
    for item in items:
        if (
            not isinstance(item, dict)
            or item.get("available") is False
            or item.get("enabled") is False
        ):
            continue
        model_id = _model_id(item)
        if model_id and model_id not in seen:
            seen.add(model_id)
            result.append({**item, "id": model_id})
    return result


async def list_models() -> list[dict]:
    base_url, api_key = _configuration()
    try:
        timeout = httpx.Timeout(15.0, connect=5.0)
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=False, trust_env=False
        ) as client:
            response = await client.get(
                f"{base_url}/models", headers={"Authorization": f"Bearer {api_key}"}
            )
    except (httpx.TimeoutException, httpx.RequestError):
        raise FreeLLMError(502, "FreeLLM model catalogue is unreachable") from None
    if response.status_code in (401, 403):
        raise FreeLLMError(502, "FreeLLM rejected the configured gateway key")
    if response.status_code >= 400 or 300 <= response.status_code < 400:
        raise FreeLLMError(502, "FreeLLM model catalogue request failed")
    try:
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError
        return _catalog_items(payload)
    except (ValueError, TypeError):
        raise FreeLLMError(502, "FreeLLM returned an invalid model catalogue") from None


def _primary_model(items: list[dict], requested: str) -> str:
    available = [item["id"] for item in items]
    opencode = [item["id"] for item in items if _is_opencode(item, item["id"])]
    if requested in {"", "auto", "opencode", "default"}:
        if not opencode:
            raise FreeLLMError(503, "No available OpenCode model was found in the FreeLLM catalogue")
        return opencode[0]
    if requested not in available:
        raise FreeLLMError(404, "Requested model is not present in the FreeLLM catalogue")
    return requested


def _candidate_models(items: list[dict], requested: str) -> list[str]:
    available = [item["id"] for item in items]
    opencode = [item["id"] for item in items if _is_opencode(item, item["id"])]
    primary = _primary_model(items, requested)
    ordered = [primary]
    ordered.extend(model for model in opencode + available if model != primary)
    try:
        max_attempts = int(os.environ.get("FREELLM_MAX_MODEL_ATTEMPTS", "4"))
    except ValueError:
        max_attempts = 4
    max_attempts = max(1, min(max_attempts, 8))
    healthy = [model for model in ordered if provider_health.is_available(model)]
    # If every circuit is open, allow one probe of the preferred model (half-open).
    return (healthy or ordered[:1])[:max_attempts]


def _validate(messages: list[dict], max_tokens: int, temperature: float) -> None:
    if not isinstance(messages, list) or not 1 <= len(messages) <= 100:
        raise FreeLLMError(400, "Invalid conversation messages")
    if any(
        not isinstance(message, dict)
        or message.get("role") not in {"system", "user", "assistant"}
        or not isinstance(message.get("content"), str)
        or not message["content"].strip()
        for message in messages
    ):
        raise FreeLLMError(400, "Invalid conversation messages")
    if sum(len(message["content"]) for message in messages) > 120000:
        raise FreeLLMError(400, "Conversation too large")
    if type(max_tokens) is not int or not 1 <= max_tokens <= 4096:
        raise FreeLLMError(400, "max_tokens must be between 1 and 4096")
    if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2:
        raise FreeLLMError(400, "temperature must be between 0 and 2")


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


def _payload(model: str, messages: list[dict], max_tokens: int, temperature: float, stream: bool):
    return {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream,
    }


def _failure_kind(status: int) -> str:
    if status == 429:
        return "rate_limit"
    if status >= 500:
        return "upstream"
    return "invalid"


async def complete(
    *,
    model: str,
    messages: list[dict],
    max_tokens: int = 512,
    temperature: float = 0.7,
) -> dict:
    _validate(messages, max_tokens, temperature)
    base_url, api_key = _configuration()
    items = await list_models()
    primary = _primary_model(items, model)
    candidates = _candidate_models(items, model)
    timeout = httpx.Timeout(90.0, connect=10.0, write=15.0, pool=10.0)
    last_status = 502
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        for index, candidate in enumerate(candidates):
            try:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=_headers(api_key),
                    json=_payload(candidate, messages, max_tokens, temperature, False),
                )
            except httpx.TimeoutException:
                provider_health.record_failure(candidate, "timeout")
                last_status = 502
                continue
            except httpx.RequestError:
                provider_health.record_failure(candidate, "network")
                last_status = 502
                continue
            if response.status_code in (401, 403):
                raise FreeLLMError(502, "FreeLLM rejected the configured gateway key")
            if response.status_code >= 400 or 300 <= response.status_code < 400:
                last_status = response.status_code
                provider_health.record_failure(candidate, _failure_kind(last_status))
                if response.status_code in _RETRYABLE and index + 1 < len(candidates):
                    continue
                if response.status_code in _RETRYABLE:
                    break
                raise FreeLLMError(400, "FreeLLM rejected the model or conversation")
            try:
                data = response.json()
                if not isinstance(data, dict) or not isinstance(data.get("choices"), list) or not data["choices"]:
                    raise ValueError
                data["model"] = candidate
                data["vonk"] = {
                    "requested_model": model,
                    "selected_model": candidate,
                    "fallback_used": candidate != primary,
                }
                provider_health.record_success(candidate)
                return data
            except (ValueError, TypeError):
                provider_health.record_failure(candidate, "upstream")
                raise FreeLLMError(502, "FreeLLM returned an invalid inference response") from None
    raise FreeLLMError(503, f"All eligible FreeLLM models failed (last status {last_status})")


async def stream(
    *,
    model: str,
    messages: list[dict],
    max_tokens: int = 512,
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    """Stream SSE frames; fallback is attempted only before the first emitted frame."""
    _validate(messages, max_tokens, temperature)
    base_url, api_key = _configuration()
    items = await list_models()
    candidates = _candidate_models(items, model)
    timeout = httpx.Timeout(120.0, connect=10.0, write=15.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        for index, candidate in enumerate(candidates):
            emitted = False
            try:
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    headers={**_headers(api_key), "Accept": "text/event-stream"},
                    json=_payload(candidate, messages, max_tokens, temperature, True),
                ) as response:
                    if response.status_code in (401, 403):
                        raise FreeLLMError(502, "FreeLLM rejected the configured gateway key")
                    if response.status_code >= 400 or 300 <= response.status_code < 400:
                        provider_health.record_failure(candidate, _failure_kind(response.status_code))
                        if response.status_code in _RETRYABLE and index + 1 < len(candidates):
                            continue
                        raise FreeLLMError(503, "FreeLLM could not start a streaming response")
                    provider_health.record_success(candidate)
                    emitted = False
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        emitted = True
                        yield line + "\n\n"
                    if not emitted:
                        provider_health.record_failure(candidate, "upstream")
                        raise FreeLLMError(502, "FreeLLM returned an empty stream")
                    return
            except (httpx.TimeoutException, httpx.RequestError):
                provider_health.record_failure(candidate, "timeout")
                if index + 1 < len(candidates):
                    continue
                raise FreeLLMError(502, "FreeLLM streaming gateway is unreachable") from None
    raise FreeLLMError(503, "All eligible FreeLLM streaming models failed")
