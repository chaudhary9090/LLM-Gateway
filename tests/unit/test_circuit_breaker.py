"""Unit tests for Circuit Breaker state transitions."""

import asyncio

import pytest

from app.core.exceptions import CircuitBreakerOpenError
from app.resilience.circuit_breaker import CircuitBreaker, CircuitState


@pytest.mark.asyncio
async def test_circuit_breaker_transitions():
    cb = CircuitBreaker(
        name="test-provider",
        failure_threshold=3,
        recovery_timeout_seconds=0.1,  # Short recovery for fast testing
        half_open_successes=2,
    )

    # Initial state CLOSED
    assert cb.state == CircuitState.CLOSED
    allowed, _ = await cb.can_execute()
    assert allowed is True

    # 1st and 2nd failures: stays CLOSED
    await cb.record_failure()
    await cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    # 3rd failure: reaches threshold, trips to OPEN
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN

    # In OPEN state: rejects requests immediately
    allowed, remaining = await cb.can_execute()
    assert allowed is False
    assert remaining > 0

    with pytest.raises(CircuitBreakerOpenError):
        await cb.check_and_acquire()

    # Wait for recovery timeout
    await asyncio.sleep(0.12)

    # First request after recovery timeout transitions to HALF_OPEN
    allowed, _ = await cb.can_execute()
    assert allowed is True
    assert cb.state == CircuitState.HALF_OPEN

    # 1st success in HALF_OPEN: stays HALF_OPEN
    await cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN

    # 2nd consecutive success in HALF_OPEN: transitions to CLOSED
    await cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_failure_reopens():
    cb = CircuitBreaker(
        name="test-provider",
        failure_threshold=2,
        recovery_timeout_seconds=0.1,
        half_open_successes=2,
    )
    await cb.record_failure()
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN

    await asyncio.sleep(0.12)
    # Probing enters HALF_OPEN
    await cb.can_execute()
    assert cb.state == CircuitState.HALF_OPEN

    # Any failure in HALF_OPEN immediately trips back to OPEN
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN
