"""Circuit Breaker pattern implementation with Closed, Open, and Half-Open states."""

import asyncio
import enum
import time
from typing import Dict, Tuple

from app.core.exceptions import CircuitBreakerOpenError
from app.core.logging import logger


class CircuitState(str, enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Monitors provider failure rates and trips open to prevent cascading failures."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        half_open_successes: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.half_open_successes = half_open_successes

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._opened_at: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    async def can_execute(self) -> Tuple[bool, float]:
        """Checks if a request can proceed through the circuit breaker.
        Returns (is_allowed, remaining_reset_seconds).
        """
        async with self._lock:
            now = time.time()
            if self._state == CircuitState.CLOSED:
                return True, 0.0

            if self._state == CircuitState.OPEN:
                elapsed = now - self._opened_at
                if elapsed >= self.recovery_timeout_seconds:
                    logger.info(
                        f"CircuitBreaker '{self.name}': Recovery timeout reached. Transitioning OPEN -> HALF_OPEN"
                    )
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    return True, 0.0
                remaining = self.recovery_timeout_seconds - elapsed
                return False, max(0.0, remaining)

            if self._state == CircuitState.HALF_OPEN:
                # In half-open, allow execution to probe provider health
                return True, 0.0

            return True, 0.0

    async def check_and_acquire(self) -> None:
        """Raises CircuitBreakerOpenError if the breaker is OPEN."""
        allowed, remaining = await self.can_execute()
        if not allowed:
            raise CircuitBreakerOpenError(provider_name=self.name, reset_in_seconds=remaining)

    async def record_success(self) -> None:
        """Records a successful request, resetting counters or transitioning to CLOSED."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_successes:
                    logger.info(
                        f"CircuitBreaker '{self.name}': {self._success_count} consecutive successes in HALF_OPEN. "
                        "Transitioning HALF_OPEN -> CLOSED."
                    )
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    async def record_failure(self) -> None:
        """Records a provider failure, incrementing counters or tripping to OPEN."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    f"CircuitBreaker '{self.name}': Failure in HALF_OPEN state. Transitioning back to OPEN."
                )
                self._state = CircuitState.OPEN
                self._opened_at = time.time()
                self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    logger.warning(
                        f"CircuitBreaker '{self.name}': Failure threshold ({self.failure_threshold}) reached. "
                        "Transitioning CLOSED -> OPEN."
                    )
                    self._state = CircuitState.OPEN
                    self._opened_at = time.time()

    async def reset(self) -> None:
        """Resets the circuit breaker to CLOSED state."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._opened_at = 0.0


class CircuitBreakerRegistry:
    """Manages circuit breakers for all registered providers."""

    def __init__(
        self,
        default_failure_threshold: int = 5,
        default_recovery_timeout: float = 30.0,
        default_half_open_successes: int = 2,
    ):
        self.default_failure_threshold = default_failure_threshold
        self.default_recovery_timeout = default_recovery_timeout
        self.default_half_open_successes = default_half_open_successes
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    def get_or_create(self, provider_name: str) -> CircuitBreaker:
        if provider_name not in self._breakers:
            self._breakers[provider_name] = CircuitBreaker(
                name=provider_name,
                failure_threshold=self.default_failure_threshold,
                recovery_timeout_seconds=self.default_recovery_timeout,
                half_open_successes=self.default_half_open_successes,
            )
        return self._breakers[provider_name]

    def is_open(self, provider_name: str) -> bool:
        breaker = self._breakers.get(provider_name)
        if not breaker:
            return False
        return breaker.state == CircuitState.OPEN
