"""End-to-End tests for all REST endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert "app" in data


@pytest.mark.asyncio
async def test_ready_endpoint(async_client: AsyncClient):
    resp = await async_client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "dependencies" in data
    assert "database" in data["dependencies"]
    assert "cache" in data["dependencies"]


@pytest.mark.asyncio
async def test_chat_completions_e2e(async_client: AsyncClient):
    payload = {
        "model": "mock-model",
        "messages": [{"role": "user", "content": "Explain quantum computing in one sentence."}],
        "temperature": 0.5,
        "max_tokens": 100,
    }
    resp = await async_client.post("/v1/chat/completions", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["object"] == "chat.completion"
    assert data["model"] == "mock-model"
    assert data["provider"] in ("mock-primary", "mock-secondary")
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["usage"]["total_tokens"] > 0
    assert data["cached"] is False
    assert resp.headers.get("X-Request-ID") is not None


@pytest.mark.asyncio
async def test_providers_endpoint_does_not_leak_secrets(async_client: AsyncClient):
    resp = await async_client.get("/providers")
    assert resp.status_code == 200
    providers = resp.json()
    assert isinstance(providers, list)
    assert len(providers) > 0
    for p in providers:
        assert "name" in p
        assert "type" in p
        assert "circuit_state" in p
        # Check that no sensitive credentials exist in response
        assert "api_key" not in p
        assert "secret" not in p
        assert "token" not in p


@pytest.mark.asyncio
async def test_models_endpoint(async_client: AsyncClient):
    resp = await async_client.get("/models")
    assert resp.status_code == 200
    models = resp.json()
    assert isinstance(models, list)
    model_names = [m["name"] for m in models]
    assert "mock-model" in model_names


@pytest.mark.asyncio
async def test_stats_and_logs_endpoints(async_client: AsyncClient):
    # Make a completion request first
    payload = {
        "model": "mock-model",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    await async_client.post("/v1/chat/completions", json=payload)

    # Check /stats
    stats_resp = await async_client.get("/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_requests"] >= 1

    # Check /logs
    logs_resp = await async_client.get("/logs?page=1&page_size=10")
    assert logs_resp.status_code == 200
    logs = logs_resp.json()
    assert logs["total"] >= 1
    assert len(logs["items"]) >= 1


@pytest.mark.asyncio
async def test_metrics_endpoint(async_client: AsyncClient):
    resp = await async_client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert "llm_gateway_requests_total" in text
    assert "llm_gateway_cache_hits_total" in text


@pytest.mark.asyncio
async def test_validation_error_structured_response(async_client: AsyncClient):
    # Send empty messages list -> should return 400 with ErrorResponse
    invalid_payload = {
        "model": "mock-model",
        "messages": [],
    }
    resp = await async_client.post("/v1/chat/completions", json=invalid_payload)
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "validation_error"
    assert data["error"]["is_retryable"] is False
