"""Integration tests for SQLite persistence, pagination, and stats aggregation."""

import pytest

from app.persistence.repository import RequestLogRepository


@pytest.mark.asyncio
async def test_request_logging_and_stats():
    # 1. Log a success request
    await RequestLogRepository.log_request(
        request_id="req-test-1",
        requested_model="mock-model",
        target_model="mock-model",
        provider="mock-primary",
        status="success",
        cache_hit=False,
        attempt_count=1,
        fallback_count=0,
        latency_ms=45.2,
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        estimated_cost_usd=0.00025,
        routing_reason="direct",
    )

    # 2. Log a cached request
    await RequestLogRepository.log_request(
        request_id="req-test-2",
        requested_model="mock-model",
        target_model="mock-model",
        provider="mock-primary",
        status="success",
        cache_hit=True,
        attempt_count=1,
        fallback_count=0,
        latency_ms=2.1,
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        estimated_cost_usd=0.00025,
        routing_reason="cache_hit",
    )

    # 3. Log a failed request
    await RequestLogRepository.log_request(
        request_id="req-test-3",
        requested_model="gpt-4o",
        target_model="gpt-4o",
        provider="openai-main",
        status="failure",
        cache_hit=False,
        attempt_count=2,
        fallback_count=1,
        latency_ms=120.0,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        estimated_cost_usd=0.0,
        error_message="Provider timeout",
    )

    # Verify paginated logs
    items, total = await RequestLogRepository.get_paginated_logs(page=1, page_size=10)
    assert total == 3
    assert len(items) == 3

    # Filter by status
    success_items, s_total = await RequestLogRepository.get_paginated_logs(status="success")
    assert s_total == 2

    # Filter by provider
    openai_items, o_total = await RequestLogRepository.get_paginated_logs(provider="openai-main")
    assert o_total == 1
    assert openai_items[0].status == "failure"

    # Verify aggregated stats
    stats = await RequestLogRepository.get_aggregated_stats()
    assert stats.total_requests == 3
    assert stats.successful_requests == 2
    assert stats.failed_requests == 1
    assert stats.cache_hits == 1
    assert stats.cache_misses == 2
    assert stats.fallback_count == 1
    assert stats.total_tokens == 300
    assert stats.total_estimated_cost_usd > 0
    assert stats.latency_p50_ms > 0
