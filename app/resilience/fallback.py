"""Fallback orchestrator managing provider switching, retries, and overall deadlines."""

import asyncio
import time
from typing import Any, Dict, List, Tuple

from app.api.schemas import ChatCompletionRequest, ChatCompletionResponse
from app.core.exceptions import (
    AllProvidersFailedError,
    ProviderTimeoutError,
    RequestTimeoutError,
)
from app.core.logging import logger
from app.providers.registry import ProviderRegistry
from app.resilience.circuit_breaker import CircuitBreakerRegistry
from app.resilience.retry import is_error_retryable, wait_with_backoff
from app.routing.policies import RoutingDecision


class FallbackOrchestrator:
    """Executes requests across candidate providers with retries, circuit breaking, and deadlines."""

    def __init__(
        self,
        registry: ProviderRegistry,
        circuit_breakers: CircuitBreakerRegistry,
        max_retries: int = 3,
        overall_timeout_seconds: float = 30.0,
        provider_timeout_seconds: float = 10.0,
        min_wait: float = 0.5,
        max_wait: float = 4.0,
    ):
        self.registry = registry
        self.circuit_breakers = circuit_breakers
        self.max_retries = max_retries
        self.overall_timeout_seconds = overall_timeout_seconds
        self.provider_timeout_seconds = provider_timeout_seconds
        self.min_wait = min_wait
        self.max_wait = max_wait

    async def execute_with_fallback(
        self,
        request: ChatCompletionRequest,
        decision: RoutingDecision,
    ) -> Tuple[ChatCompletionResponse, List[Dict[str, Any]], int]:
        """Runs the request against primary and fallback providers within an overall deadline.
        Returns: (response, attempt_history, fallback_count)
        """
        # Calculate deadline
        request_timeout = request.timeout or self.overall_timeout_seconds
        deadline = time.time() + request_timeout

        candidate_providers = [decision.primary_provider] + [
            p for p in decision.fallback_providers if p != decision.primary_provider
        ]

        attempt_history: List[Dict[str, Any]] = []
        fallback_count = 0

        for provider_idx, provider_name in enumerate(candidate_providers):
            provider = self.registry.get(provider_name)
            if not provider or not provider.enabled:
                attempt_history.append(
                    {
                        "provider": provider_name,
                        "model": decision.target_model,
                        "attempt": 1,
                        "elapsed_ms": 0.0,
                        "outcome": "skipped",
                        "error_category": "provider_disabled_or_not_found",
                        "message": f"Provider '{provider_name}' is disabled or not configured.",
                    }
                )
                continue

            breaker = self.circuit_breakers.get_or_create(provider_name)
            can_exec, reset_in = await breaker.can_execute()
            if not can_exec:
                attempt_history.append(
                    {
                        "provider": provider_name,
                        "model": decision.target_model,
                        "attempt": 1,
                        "elapsed_ms": 0.0,
                        "outcome": "circuit_open",
                        "error_category": "circuit_breaker_open",
                        "message": f"Circuit breaker OPEN, retry after {reset_in:.1f}s",
                    }
                )
                if provider_idx > 0:
                    fallback_count += 1
                continue

            if provider_idx > 0:
                fallback_count += 1
                logger.info(
                    f"Failing over to fallback provider '{provider_name}' (fallback #{fallback_count})"
                )

            # Try up to max_retries attempts on this provider
            for attempt in range(self.max_retries):
                now = time.time()
                remaining_budget = deadline - now
                if remaining_budget <= 0:
                    raise RequestTimeoutError(deadline_seconds=request_timeout)

                bounded_timeout = min(self.provider_timeout_seconds, remaining_budget)
                attempt_start = time.perf_counter()

                try:
                    try:
                        response = await asyncio.wait_for(
                            provider.generate(
                                request=request,
                                model=decision.target_model,
                                timeout=bounded_timeout,
                            ),
                            timeout=bounded_timeout,
                        )
                    except asyncio.TimeoutError:
                        if time.time() >= deadline:
                            raise RequestTimeoutError(deadline_seconds=request_timeout)
                        raise ProviderTimeoutError(provider_name=provider_name)
                    elapsed_ms = (time.perf_counter() - attempt_start) * 1000.0
                    await breaker.record_success()

                    attempt_history.append(
                        {
                            "provider": provider_name,
                            "model": decision.target_model,
                            "attempt": attempt + 1,
                            "elapsed_ms": round(elapsed_ms, 2),
                            "outcome": "success",
                            "error_category": None,
                            "message": "OK",
                        }
                    )

                    return response, attempt_history, fallback_count

                except Exception as exc:
                    elapsed_ms = (time.perf_counter() - attempt_start) * 1000.0
                    await breaker.record_failure()

                    error_cat = getattr(exc, "error_code", exc.__class__.__name__)
                    error_msg = str(exc)

                    attempt_history.append(
                        {
                            "provider": provider_name,
                            "model": decision.target_model,
                            "attempt": attempt + 1,
                            "elapsed_ms": round(elapsed_ms, 2),
                            "outcome": "failure",
                            "error_category": error_cat,
                            "message": error_msg,
                        }
                    )

                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries} failed on provider '{provider_name}': {exc}"
                    )

                    # Check if error is transient and we have remaining retries
                    if not is_error_retryable(exc) or (attempt + 1) >= self.max_retries:
                        break  # Fall back to next provider in the chain

                    # Calculate backoff delay
                    retry_after = getattr(exc, "retry_after", None)
                    delay = await wait_with_backoff(
                        attempt=attempt,
                        min_wait=self.min_wait,
                        max_wait=self.max_wait,
                        retry_after=retry_after,
                    )

                    if (time.time() + delay) > deadline:
                        raise RequestTimeoutError(deadline_seconds=request_timeout)

        # If all candidate providers failed
        raise AllProvidersFailedError(attempts=attempt_history)
