"""Unit tests for retry classification and exponential backoff."""

import pytest

from app.core.exceptions import (
    AuthenticationError,
    InvalidRequestError,
    ModelNotFoundError,
    ProviderAuthError,
    ProviderConnectionError,
    ProviderMalformedResponseError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
)
from app.resilience.retry import is_error_retryable, wait_with_backoff


def test_retryable_exceptions():
    # Transient errors MUST be retryable
    assert is_error_retryable(ProviderRateLimitError(provider_name="test")) is True
    assert is_error_retryable(ProviderServerError(provider_name="test")) is True
    assert is_error_retryable(ProviderTimeoutError(provider_name="test")) is True
    assert is_error_retryable(ProviderConnectionError(provider_name="test")) is True


def test_non_retryable_exceptions():
    # Permanent errors must NEVER be retried
    assert is_error_retryable(ProviderAuthError(provider_name="test")) is False
    assert is_error_retryable(ProviderMalformedResponseError(provider_name="test")) is False
    assert is_error_retryable(AuthenticationError()) is False
    assert is_error_retryable(InvalidRequestError("bad input")) is False
    assert is_error_retryable(ModelNotFoundError("missing-model")) is False
    assert is_error_retryable(ValueError("syntax error")) is False


@pytest.mark.asyncio
async def test_backoff_timing_and_retry_after():
    # Standard exponential delay with min_wait
    delay = await wait_with_backoff(attempt=0, min_wait=0.01, max_wait=0.1)
    assert 0.01 <= delay <= 0.1

    # Retry-After header override
    delay_custom = await wait_with_backoff(attempt=0, min_wait=0.01, max_wait=0.1, retry_after=0.05)
    assert delay_custom == 0.05
