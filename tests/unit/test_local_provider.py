"""Unit tests for LocalProvider adapter (Ollama/LM Studio/vLLM)."""

import httpx
import pytest

from app.api.schemas import ChatCompletionRequest, ChatMessage
from app.core.exceptions import (
    ProviderConnectionError,
    ProviderServerError,
    ProviderTimeoutError,
)
from app.providers.local import LocalProvider


@pytest.mark.asyncio
async def test_local_provider_successful_generate():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            status_code=200,
            json={
                "id": "ollama-cmpl-123",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "llama3.2",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Offline intelligence ready.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 5,
                    "total_tokens": 17,
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    provider = LocalProvider(
        name="local",
        base_url="http://localhost:11434/v1",
        default_model="llama3.2",
        client=client,
    )

    req = ChatCompletionRequest(
        model="llama3.2",
        messages=[ChatMessage(role="user", content="Hello local model!")],
    )

    resp = await provider.generate(request=req, model="llama3.2", timeout=10.0)
    assert resp.provider == "local"
    assert resp.model == "llama3.2"
    assert resp.choices[0].message.content == "Offline intelligence ready."
    assert resp.usage.total_tokens == 17
    assert resp.cost_usd == 0.0  # Zero cost for local models
    assert resp.cached is False


@pytest.mark.asyncio
async def test_local_provider_connection_error():
    def mock_handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused to localhost:11434")

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    provider = LocalProvider(
        name="local",
        base_url="http://localhost:11434/v1",
        client=client,
    )

    req = ChatCompletionRequest(
        model="llama3.2",
        messages=[ChatMessage(role="user", content="Ping")],
    )

    with pytest.raises(ProviderConnectionError) as exc_info:
        await provider.generate(request=req, model="llama3.2", timeout=5.0)

    assert "Could not connect to local engine" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_local_provider_timeout_error():
    def mock_handler(_: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Read timed out")

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    provider = LocalProvider(
        name="local",
        base_url="http://localhost:11434/v1",
        client=client,
    )

    req = ChatCompletionRequest(
        model="llama3.2",
        messages=[ChatMessage(role="user", content="Long prompt")],
    )

    with pytest.raises(ProviderTimeoutError) as exc_info:
        await provider.generate(request=req, model="llama3.2", timeout=2.0)

    assert "timed out" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_local_provider_server_error():
    def mock_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=500, text="Internal engine out of VRAM")

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    provider = LocalProvider(
        name="local",
        base_url="http://localhost:11434/v1",
        client=client,
    )

    req = ChatCompletionRequest(
        model="llama3.2",
        messages=[ChatMessage(role="user", content="Generate")],
    )

    with pytest.raises(ProviderServerError) as exc_info:
        await provider.generate(request=req, model="llama3.2", timeout=5.0)

    assert exc_info.value.status_code == 502
    assert "500" in exc_info.value.message


@pytest.mark.asyncio
async def test_local_provider_health_check_and_discovery():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        if "/models" in request.url.path:
            return httpx.Response(
                status_code=200,
                json={"data": [{"id": "llama3.2:latest"}, {"id": "mistral:latest"}]},
            )
        if "/api/tags" in request.url.path:
            return httpx.Response(
                status_code=200,
                json={"models": [{"name": "llama3.2:latest"}, {"name": "qwen2.5:latest"}]},
            )
        return httpx.Response(status_code=404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    provider = LocalProvider(
        name="local",
        base_url="http://localhost:11434/v1",
        client=client,
    )

    is_healthy = await provider.health_check()
    assert is_healthy is True

    discovered = await provider.list_models()
    assert "llama3.2" in discovered or "llama3.2:latest" in discovered
