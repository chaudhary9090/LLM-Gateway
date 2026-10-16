"""Unit tests for Server-Sent Events (SSE) streaming chat completions."""

import json

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_streaming_chat_completion_and_cache_replay(async_client: AsyncClient):
    payload = {
        "model": "cheap",
        "messages": [{"role": "user", "content": "Tell me a quick fact about caching."}],
        "temperature": 0.7,
        "stream": True,
        "cache": True,
    }

    # 1. Fresh Streaming Request
    chunks = []
    async with async_client.stream("POST", "/v1/chat/completions", json=payload) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        async for line in response.aiter_lines():
            line = line.strip()
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:].strip()
            if data_str == "[DONE]":
                break
            parsed = json.loads(data_str)
            chunks.append(parsed)

    assert len(chunks) > 1
    assert chunks[0]["object"] == "chat.completion.chunk"
    # First or subsequent chunks have delta content
    has_content = any("content" in c["choices"][0]["delta"] for c in chunks)
    assert has_content is True

    # 2. Replay from cache as a stream
    cached_chunks = []
    async with async_client.stream("POST", "/v1/chat/completions", json=payload) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        async for line in response.aiter_lines():
            line = line.strip()
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:].strip()
            if data_str == "[DONE]":
                break
            cached_chunks.append(json.loads(data_str))

    assert len(cached_chunks) > 1
    has_cached_content = any("content" in c["choices"][0]["delta"] for c in cached_chunks)
    assert has_cached_content is True

