"""Integration tests for OpenAICompatibleProvider adapter using mock HTTP transport."""

import httpx
import pytest

from app.api.schemas import ChatCompletionRequest, ChatMessage
from app.core.exceptions import (
    ProviderAuthError,
    ProviderMalformedResponseError,
    ProviderRateLimitError,
    ProviderServerError,
)
from app.providers.openai_compatible import OpenAICompatibleProvider


@pytest.mark.asyncio
async def test_openai_adapter_success():
    mock_response_data = {
        "id": "chatcmpl-test-123",
        "object": "chat.completion",
        "created": 1677652288,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello there! How can I help?"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 8,
            "total_tokens": 20,
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Bearer sk-test-key"
        return httpx.Response(200, json=mock_response_data)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)

    provider = OpenAICompatibleProvider(
        name="test-openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-test-key",
        client=client,
    )

    req = ChatCompletionRequest(
        model="gpt-4o-mini",
        messages=[ChatMessage(role="user", content="Hi")],
    )

    resp = await provider.generate(req, model="gpt-4o-mini", timeout=5.0)

    assert resp.model == "gpt-4o-mini"
    assert resp.provider == "test-openai"
    assert resp.choices[0].message.content == "Hello there! How can I help?"
    assert resp.usage.prompt_tokens == 12
    assert resp.usage.completion_tokens == 8
    assert resp.usage.total_tokens == 20
    assert resp.cached is False


@pytest.mark.asyncio
async def test_openai_adapter_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        "test-openai", "https://api.openai.com/v1", api_key="bad-key", client=client
    )

    req = ChatCompletionRequest(
        model="gpt-4o-mini", messages=[ChatMessage(role="user", content="Hi")]
    )
    with pytest.raises(ProviderAuthError):
        await provider.generate(req, "gpt-4o-mini", timeout=5.0)


@pytest.mark.asyncio
async def test_openai_adapter_rate_limit():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, headers={"Retry-After": "2"}, json={"error": {"message": "Rate limited"}}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider("test-openai", "https://api.openai.com/v1", client=client)

    req = ChatCompletionRequest(
        model="gpt-4o-mini", messages=[ChatMessage(role="user", content="Hi")]
    )
    with pytest.raises(ProviderRateLimitError) as exc_info:
        await provider.generate(req, "gpt-4o-mini", timeout=5.0)
    assert exc_info.value.retry_after == 2.0


@pytest.mark.asyncio
async def test_openai_adapter_server_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider("test-openai", "https://api.openai.com/v1", client=client)

    req = ChatCompletionRequest(
        model="gpt-4o-mini", messages=[ChatMessage(role="user", content="Hi")]
    )
    with pytest.raises(ProviderServerError):
        await provider.generate(req, "gpt-4o-mini", timeout=5.0)


@pytest.mark.asyncio
async def test_openai_adapter_malformed_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="Not a JSON payload")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider("test-openai", "https://api.openai.com/v1", client=client)

    req = ChatCompletionRequest(
        model="gpt-4o-mini", messages=[ChatMessage(role="user", content="Hi")]
    )
    with pytest.raises(ProviderMalformedResponseError):
        await provider.generate(req, "gpt-4o-mini", timeout=5.0)
