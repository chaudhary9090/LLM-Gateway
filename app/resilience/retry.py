"""Retry strategy with exponential backoff and jitter."""

import asyncio
import random
from typing import Optional

from app.core.exceptions import (
    GatewayException,
    ProviderAuthError,
    ProviderMalformedResponseError,
)
from app.core.logging import logger


def is_error_retryable(exc: Exception) -> bool:
    """Evaluates whether an exception is transient and eligible for retry."""
    if isinstance(exc, (ProviderAuthError, ProviderMalformedResponseError)):
        return False
    if isinstance(exc, GatewayException):
        return exc.is_retryable
    return False


async def wait_with_backoff(
    attempt: int,
    min_wait: float = 0.5,
    max_wait: float = 4.0,
    retry_after: Optional[float] = None,
    jitter: float = 0.2,
) -> float:
    """Calculates backoff delay, respecting Retry-After when present, and sleeps."""
    if retry_after is not None and retry_after > 0:
        delay = min(retry_after, max_wait)
    else:
        calculated = min_wait * (2**attempt)
        jitter_val = random.uniform(0, jitter * calculated)
        delay = min(max_wait, calculated + jitter_val)

    logger.info(f"Retrying after backoff delay: {delay:.2f}s (attempt {attempt + 1})")
    await asyncio.sleep(delay)
    return delay
