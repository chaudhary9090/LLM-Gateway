"""Unit tests for Embeddings and Model Comparison."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_embeddings_endpoint(async_client: AsyncClient):
    res = await async_client.post(
        "/v1/embeddings",
        json={
            "input": ["Unified LLM gateways provide resilience", "Redis caches identical requests"],
            "model": "text-embedding-3-small",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["object"] == "list"
    assert len(data["data"]) == 2
    assert len(data["data"][0]["embedding"]) == 128
    assert data["usage"]["total_tokens"] > 0


@pytest.mark.asyncio
async def test_model_comparison_endpoint(async_client: AsyncClient):
    res = await async_client.post(
        "/v1/compare",
        json={
            "models": ["gpt-4o-mini", "mock-model"],
            "messages": [{"role": "user", "content": "What is 2 + 2?"}],
            "temperature": 0.0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) == 2
    models_compared = [r["model"] for r in data["results"]]
    assert "gpt-4o-mini" in models_compared or "mock-model" in models_compared
    assert data["results"][0]["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_models_reload_endpoint(async_client: AsyncClient):
    res = await async_client.post("/v1/models/reload")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["models_count"] > 0

