"""FreeLLM gateway integration with OpenCode-first model selection and fallback.

Configure FREELLM_BASE_URL (the gateway's OpenAI-compatible /v1 base URL) and
FREELLM_API_KEY. Model IDs are discovered from the gateway; no provider/model
catalogue is hardcoded in Vonk.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

import httpx


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
        or (parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"})
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
    for item in items:
        if not isinstance(item, dict) or item.get("available") is False or item.get("enabled") is False:
            continue
        model_id = _model_id(item)
        if model_id:
            result.append({**item, "id": model_id})
    return result


async def list_models() -> list[dict]:
    base_url, api_key = _configuration()
    try:
        timeout = httpx.Timeout(15.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
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


def _candidate_models(items: list[dict], requested: str) -> list[str]:
    available = [item["id"] for item in items]
    opencode = [
        item["id"] for item in items
        if _is_opencode(item, item["id"])
    ]
    if requested in {"", "auto", "opencode", "default"}:
        if not opencode:
            raise FreeLLMError(503, "No available OpenCode model was found in the FreeLLM catalogue")
        primary = opencode[0]
    else:
        primary = requested
    # OpenCode is preferred for the default route; all remaining catalogue
    # entries are eligible fallbacks in the order supplied by FreeLLM.
    ordered = [primary]
    ordered.extend(model for model in opencode + available if model != primary)
    return list(dict.fromkeys(ordered))


async def complete(
    *,
    model: str,
    messages: list[dict],
    max_tokens: int = 512,
    temperature: float = 0.7,
) -> dict:
    base_url, api_key = _configuration()
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
    if type(max_tokens) is not int or not 1 <= max_tokens <= 4096:
        raise FreeLLMError(400, "max_tokens must be between 1 and 4096")
    if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2:
        raise FreeLLMError(400, "temperature must be between 0 and 2")

    items = await list_models()
    candidates = _candidate_models(items, model)
    timeout = httpx.Timeout(90.0, connect=10.0, write=15.0, pool=10.0)
    last_status = 502
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        for index, candidate in enumerate(candidates):
            try:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": candidate,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "stream": False,
                    },
                )
            except (httpx.TimeoutException, httpx.RequestError):
                last_status = 502
                if index + 1 < len(candidates):
                    continue
                raise FreeLLMError(502, "FreeLLM inference gateway is unreachable") from None

            if response.status_code in (401, 403):
                raise FreeLLMError(502, "FreeLLM rejected the configured gateway key")
            if response.status_code >= 400 or 300 <= response.status_code < 400:
                last_status = response.status_code
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
                data["vonk"] = {"requested_model": model, "selected_model": candidate,
                                "fallback_used": candidate != candidates[0]}
                return data
            except (ValueError, TypeError):
                raise FreeLLMError(502, "FreeLLM returned an invalid inference response") from None

    raise FreeLLMError(503, f"All eligible FreeLLM models failed (last status {last_status})")
