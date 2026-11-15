# FreeLLM inference gateway

Vonk can use a separately hosted FreeLLM-compatible gateway for managed inference.
Vonk does not bundle or host the upstream provider models.

## Configuration

Set these variables in the Vonk API service environment:

- `FREELLM_BASE_URL`: the gateway's OpenAI-compatible base URL, including its
  `/v1` path (for example, the URL shown by your FreeLLM deployment).
- `FREELLM_API_KEY`: a gateway key issued by that FreeLLM deployment.

Use HTTPS for remote gateways. Plain HTTP is accepted only for loopback
addresses during local development. Do not commit either value.

## Model discovery and routing

`GET /v1/models` fetches the live FreeLLM catalogue and returns available model
IDs. The managed default is `opencode`: Vonk resolves it to the first available
OpenCode model reported by the catalogue. If no OpenCode model is available,
Vonk returns a clear service-unavailable error instead of silently choosing a
different default.

`POST /v1/chat/completions` accepts an OpenAI-style chat request:

```json
{
  "model": "opencode",
  "messages": [{"role": "user", "content": "Explain vector databases."}],
  "max_tokens": 512,
  "temperature": 0.7
}
```

A specific model ID from `GET /v1/models` can be supplied instead. If that
model is temporarily unavailable, rate-limited, or returns a retryable upstream
failure, Vonk tries other catalogue models. OpenCode models are ordered first;
other available models follow in the order returned by FreeLLM. Authentication
failures are not retried against other models.

The upstream gateway remains responsible for its provider credentials, provider
terms, and any routing behaviour it implements internally. Vonk's fallback is
an additional model-level retry layer and is bounded by the catalogue returned
for each request.

## Existing BYOK route

`POST /v1/chat/byok` remains separate and continues to use the caller's
`X-Provider-Key`. Managed FreeLLM credentials are never returned to clients or
used for BYOK requests.

## Operational notes

- Configure a gateway key with only the permissions required for inference.
- Monitor FreeLLM provider quotas; free tiers are not unlimited.
- Catalogue and provider availability can change. Vonk fetches the catalogue
  for each model-list or inference request rather than treating example model
  IDs as permanent.
- Streaming is not yet exposed on the managed FreeLLM route.
