"""Unit tests for ApiKeyPolicy rate limits, daily budgets, and allowed models."""

import pytest

from app.core.exceptions import GatewayException
from app.persistence.api_keys import ApiKeyPolicy, RateLimitExceededError


def test_api_key_rpm_rate_limiting():
    # Policy with 3 requests per minute limit
    policy = ApiKeyPolicy(name="test-tenant", rate_limit_rpm=3)

    policy.check_and_record_request("cheap")
    policy.check_and_record_request("cheap")
    policy.check_and_record_request("cheap")

    # 4th request must be rejected with RateLimitExceededError
    with pytest.raises(RateLimitExceededError) as exc_info:
        policy.check_and_record_request("cheap")

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after > 0


def test_api_key_daily_token_budget():
    # Policy with 1,000 tokens daily budget
    policy = ApiKeyPolicy(name="test-budget", daily_token_budget=1000)

    policy.check_and_record_request("cheap")
    policy.record_usage(tokens=950, cost_usd=0.001)

    policy.check_and_record_request("cheap")
    policy.record_usage(tokens=100, cost_usd=0.0001)  # Total 1050 > 1000

    # Next request exceeds daily budget
    with pytest.raises(RateLimitExceededError) as exc_info:
        policy.check_and_record_request("cheap")

    assert "Daily token budget" in exc_info.value.message


def test_api_key_allowed_models_restriction():
    # Policy restricted only to "cheap" and "local-model"
    policy = ApiKeyPolicy(name="test-restricted", allowed_models=["cheap", "local-model"])

    # Permitted model
    policy.check_and_record_request("cheap")

    # Forbidden model
    with pytest.raises(GatewayException) as exc_info:
        policy.check_and_record_request("claude-3-5-sonnet")

    assert exc_info.value.status_code == 403
    assert "not allowed" in exc_info.value.message
