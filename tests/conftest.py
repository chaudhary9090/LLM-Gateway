"""Pytest fixtures and configuration."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure test database environment
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["CACHE_ENABLED"] = "true"
os.environ["MOCK_PRIMARY_ENABLED"] = "true"
os.environ["MOCK_SECONDARY_ENABLED"] = "true"
os.environ["OPENAI_MAIN_ENABLED"] = "false"
os.environ["OPENAI_BACKUP_ENABLED"] = "false"

from app.api.schemas import ChatCompletionRequest, ChatMessage
from app.cache.redis_cache import InMemoryCache
from app.core.config import Settings
from app.main import create_app
from app.persistence.database import Base, engine
from app.providers.mock import MockProvider
from app.providers.registry import ProviderRegistry
from app.resilience.circuit_breaker import CircuitBreakerRegistry
from app.resilience.fallback import FallbackOrchestrator
from app.routing.router import ModelRouter
from app.services.gateway import GatewayService


@pytest.fixture(autouse=True)
async def prepare_database():
    """Initializes in-memory database tables for each test."""
    import asyncio

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await asyncio.sleep(0.05)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def sample_chat_request() -> ChatCompletionRequest:
    """Fixture providing a standard valid chat completion request."""
    return ChatCompletionRequest(
        model="mock-model",
        messages=[
            ChatMessage(role="system", content="You are a helpful coding assistant."),
            ChatMessage(role="user", content="Write a python function to compute factorial."),
        ],
        temperature=0.7,
        max_tokens=256,
        cache=True,
    )


@pytest.fixture
def in_memory_cache() -> InMemoryCache:
    """Fixture providing an isolated in-memory cache."""
    return InMemoryCache()


@pytest.fixture
def mock_registry() -> ProviderRegistry:
    """Fixture providing registered mock providers."""
    reg = ProviderRegistry()
    reg.register(MockProvider(name="mock-primary", enabled=True, latency_ms=1))
    reg.register(MockProvider(name="mock-secondary", enabled=True, latency_ms=1))
    return reg


@pytest.fixture
def circuit_breakers() -> CircuitBreakerRegistry:
    """Fixture providing isolated circuit breakers with low thresholds for testing."""
    return CircuitBreakerRegistry(
        default_failure_threshold=3,
        default_recovery_timeout=0.2,
        default_half_open_successes=2,
    )


@pytest.fixture
def test_router() -> ModelRouter:
    """Fixture providing a configured router."""
    return ModelRouter("config/models.yaml")


@pytest.fixture
def gateway_service(
    mock_registry: ProviderRegistry,
    circuit_breakers: CircuitBreakerRegistry,
    test_router: ModelRouter,
    in_memory_cache: InMemoryCache,
) -> GatewayService:
    """Fixture providing a fully wired GatewayService for testing."""
    test_settings = Settings(
        cache_enabled=True,
        database_url="sqlite+aiosqlite:///:memory:",
        request_overall_timeout_seconds=5.0,
        provider_timeout_seconds=2.0,
        max_retries=2,
        retry_min_wait_seconds=0.01,
        retry_max_wait_seconds=0.05,
    )
    orchestrator = FallbackOrchestrator(
        registry=mock_registry,
        circuit_breakers=circuit_breakers,
        max_retries=test_settings.max_retries,
        overall_timeout_seconds=test_settings.request_overall_timeout_seconds,
        provider_timeout_seconds=test_settings.provider_timeout_seconds,
        min_wait=test_settings.retry_min_wait_seconds,
        max_wait=test_settings.retry_max_wait_seconds,
    )
    return GatewayService(
        settings=test_settings,
        router=test_router,
        orchestrator=orchestrator,
        cache=in_memory_cache,
    )


@pytest.fixture
async def async_client() -> AsyncClient:
    """Async test client talking to the FastAPI application."""
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield client
