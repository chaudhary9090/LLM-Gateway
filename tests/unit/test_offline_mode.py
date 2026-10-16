"""Unit tests for OFFLINE_MODE routing enforcement and Ollama auto-discovery."""

import httpx
import pytest

from app.api.schemas import ChatCompletionRequest, ChatMessage
from app.core.config import Settings
from app.routing.router import ModelRouter
from app.services.discovery import discover_local_models


def test_offline_mode_filters_outbound_providers():
    router = ModelRouter("config/models.yaml", offline_mode=True)
    req = ChatCompletionRequest(
        model="gpt-4o",
        messages=[ChatMessage(role="user", content="Test offline constraint")],
    )

    # In models.yaml, gpt-4o has primary: openai-main, fallbacks: [openai-backup, local, mock-primary]
    # Under offline_mode=True, openai-main and openai-backup MUST be filtered out!
    decision = router.route(
        req,
        provider_enabled_checker=lambda _: True,
        circuit_open_checker=lambda _: False,
    )

    assert decision.primary_provider in ("local", "mock-primary")
    for fb in decision.fallback_providers:
        assert fb in ("local", "mock-primary", "mock-secondary")
        assert "openai" not in fb


def test_cheap_routes_to_local_when_available():
    router = ModelRouter("config/models.yaml", offline_mode=False)
    req = ChatCompletionRequest(
        model="cheap",
        messages=[ChatMessage(role="user", content="Write a haiku")],
    )

    # When local provider is enabled and not open, "cheap" routes to local-model or llama3.2
    decision = router.route(
        req,
        provider_enabled_checker=lambda p: p in ("local", "mock-primary"),
        circuit_open_checker=lambda _: False,
    )

    assert decision.target_model in ("local-model", "llama3.2")
    assert decision.primary_provider == "local"
    assert "local_preferred" in decision.routing_reason


@pytest.mark.asyncio
async def test_auto_discovery_registers_models(monkeypatch):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        if "/api/tags" in request.url.path:
            return httpx.Response(
                status_code=200,
                json={
                    "models": [
                        {"name": "phi3:mini"},
                        {"name": "deepseek-coder:6.7b"},
                    ]
                },
            )
        return httpx.Response(status_code=404)

    # Mock httpx.AsyncClient inside discovery module
    real_async_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(mock_handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr("httpx.AsyncClient", fake_async_client)

    router = ModelRouter("config/models.yaml")
    settings = Settings(local_enabled=True, ollama_auto_discover=True)

    added = await discover_local_models(router=router, settings=settings)
    assert added >= 2
    assert "phi3" in router.models or "phi3:mini" in router.models
    assert "deepseek-coder" in router.models or "deepseek-coder:6.7b" in router.models
