"""End-to-End tests for automatic fallback and deadline enforcement."""

import pytest

from app.api.schemas import ChatCompletionRequest, ChatMessage
from app.core.exceptions import AllProvidersFailedError, RequestTimeoutError
from app.providers.mock import MockProvider
from app.services.gateway import GatewayService


@pytest.mark.asyncio
async def test_primary_failure_fallback_to_secondary(gateway_service: GatewayService):
    # Force primary mock provider to fail with 500 error
    primary = gateway_service.orchestrator.registry.get("mock-primary")
    assert isinstance(primary, MockProvider)
    primary.forced_failure = "500"

    secondary = gateway_service.orchestrator.registry.get("mock-secondary")
    assert isinstance(secondary, MockProvider)
    secondary.forced_failure = None

    req = ChatCompletionRequest(
        model="mock-model",
        messages=[ChatMessage(role="user", content="Test fallback scenario")],
    )

    resp = await gateway_service.complete(req)

    # Response should have fallen back and succeeded via mock-secondary
    assert resp is not None
    assert resp.provider == "mock-secondary"
    assert "mock-secondary" in resp.choices[0].message.content


@pytest.mark.asyncio
async def test_all_providers_failing_raises_structured_error(gateway_service: GatewayService):
    # Force both mock-primary and mock-secondary to fail
    primary = gateway_service.orchestrator.registry.get("mock-primary")
    secondary = gateway_service.orchestrator.registry.get("mock-secondary")
    assert isinstance(primary, MockProvider)
    assert isinstance(secondary, MockProvider)
    primary.forced_failure = "500"
    secondary.forced_failure = "500"

    req = ChatCompletionRequest(
        model="mock-model",
        messages=[ChatMessage(role="user", content="Will fail completely")],
    )

    with pytest.raises(AllProvidersFailedError) as exc_info:
        await gateway_service.complete(req)

    attempts = exc_info.value.attempts
    assert len(attempts) >= 2
    for attempt in attempts:
        assert attempt["outcome"] == "failure"


@pytest.mark.asyncio
async def test_request_deadline_enforcement(gateway_service: GatewayService):
    # Set mock latency higher than request timeout
    primary = gateway_service.orchestrator.registry.get("mock-primary")
    assert isinstance(primary, MockProvider)
    primary.latency_ms = 400  # 400ms latency

    req = ChatCompletionRequest(
        model="mock-model",
        messages=[ChatMessage(role="user", content="Should timeout")],
        timeout=0.1,  # 100ms overall budget
    )

    # Fallback orchestrator overall timeout should trigger RequestTimeoutError
    with pytest.raises(RequestTimeoutError):
        await gateway_service.complete(req)
