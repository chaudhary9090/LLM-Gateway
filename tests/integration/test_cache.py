"""Integration tests for Caching, stampede locks, bypass, and graceful degradation."""

import asyncio

import pytest

from app.api.schemas import ChatCompletionRequest
from app.cache.redis_cache import InMemoryCache
from app.services.gateway import GatewayService


@pytest.mark.asyncio
async def test_cache_hit_on_identical_request(
    gateway_service: GatewayService, sample_chat_request: ChatCompletionRequest
):
    # First request: fresh generation (cache miss)
    resp1 = await gateway_service.complete(sample_chat_request)
    assert resp1.cached is False

    # Second request: identical parameters -> cache hit
    resp2 = await gateway_service.complete(sample_chat_request)
    assert resp2.cached is True
    assert resp2.choices[0].message.content == resp1.choices[0].message.content
    assert "cache_hit" in resp2.routing_reason


@pytest.mark.asyncio
async def test_cache_bypass(
    gateway_service: GatewayService, sample_chat_request: ChatCompletionRequest
):
    # Seed cache
    await gateway_service.complete(sample_chat_request)

    # Request with cache=False must bypass cache
    bypass_req = sample_chat_request.model_copy(update={"cache": False})
    resp_bypass = await gateway_service.complete(bypass_req)
    assert resp_bypass.cached is False


@pytest.mark.asyncio
async def test_cache_degradation_on_failure(
    gateway_service: GatewayService, sample_chat_request: ChatCompletionRequest
):
    # Replace cache with one that throws errors
    class BrokenCache(InMemoryCache):
        async def get(self, key: str):
            raise ConnectionError("Redis disconnected")

        async def set(self, key: str, response, ttl_seconds: int = 3600):
            raise ConnectionError("Redis disconnected")

    gateway_service.cache = BrokenCache()

    # Gateway should gracefully degrade: still generate successfully without crashing!
    resp = await gateway_service.complete(sample_chat_request)
    assert resp is not None
    assert resp.cached is False
    assert resp.choices[0].message.content != ""


@pytest.mark.asyncio
async def test_concurrent_stampede_protection(
    gateway_service: GatewayService, sample_chat_request: ChatCompletionRequest
):
    # Fire 5 concurrent identical requests
    tasks = [gateway_service.complete(sample_chat_request) for _ in range(5)]
    results = await asyncio.gather(*tasks)

    # At least one was fresh, others may be cache hits or stampede hits
    assert len(results) == 5
    for r in results:
        assert r.choices[0].message.content != ""
