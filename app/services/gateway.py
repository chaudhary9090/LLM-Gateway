"""Unified Gateway Service orchestrating routing, caching, resilience, and persistence."""

import asyncio
import time
import uuid
from typing import Optional

from app.api.schemas import ChatCompletionRequest, ChatCompletionResponse
from app.cache.base import BaseCache
from app.cache.keys import generate_cache_key
from app.core.config import Settings
from app.core.logging import logger
from app.persistence.repository import RequestLogRepository
from app.resilience.fallback import FallbackOrchestrator
from app.routing.router import ModelRouter
from app.services.cost import calculate_estimated_cost_usd


class GatewayService:
    """Core gateway business logic coordinator."""

    def __init__(
        self,
        settings: Settings,
        router: ModelRouter,
        orchestrator: FallbackOrchestrator,
        cache: BaseCache,
    ):
        self.settings = settings
        self.router = router
        self.orchestrator = orchestrator
        self.cache = cache

    async def complete(
        self,
        request: ChatCompletionRequest,
        client_request_id: Optional[str] = None,
    ) -> ChatCompletionResponse:
        """Executes full chat completion lifecycle."""
        request_id = client_request_id or f"req-{uuid.uuid4().hex[:12]}"
        start_time = time.perf_counter()

        # 1. Resolve routing decision
        decision = self.router.route(
            request=request,
            circuit_open_checker=self.orchestrator.circuit_breakers.is_open,
            provider_enabled_checker=lambda p: (
                self.orchestrator.registry.get(p).enabled
                if self.orchestrator.registry.get(p)
                else False
            ),
        )

        # 2. Evaluate cache eligibility
        is_cache_eligible = self.settings.cache_enabled and request.cache is not False
        cache_key = None
        if is_cache_eligible:
            cache_key = generate_cache_key(
                request=request,
                target_model=decision.target_model,
                schema_version=self.settings.cache_schema_version,
            )

            # Check cache
            cached_response = None
            try:
                cached_response = await self.cache.get(cache_key)
            except Exception as e:
                logger.warning(f"Cache get exception: {e}. Degrading to fresh generation.")

            if cached_response is not None:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                cached_response.request_id = request_id
                cached_response.latency_ms = round(elapsed_ms, 2)
                cached_response.routing_reason = f"{decision.routing_reason};cache_hit"

                # Async log cache hit
                asyncio.create_task(
                    RequestLogRepository.log_request(
                        request_id=request_id,
                        requested_model=decision.requested_model,
                        target_model=decision.target_model,
                        provider=cached_response.provider,
                        status="success",
                        cache_hit=True,
                        attempt_count=1,
                        fallback_count=0,
                        latency_ms=elapsed_ms,
                        input_tokens=cached_response.usage.prompt_tokens,
                        output_tokens=cached_response.usage.completion_tokens,
                        total_tokens=cached_response.usage.total_tokens,
                        estimated_cost_usd=cached_response.cost_usd or 0.0,
                        routing_reason=cached_response.routing_reason,
                    )
                )

                logger.info(f"Cache HIT for request {request_id} (key: {cache_key})")
                return cached_response

        # 3. Cache stampede protection (single-flight locking)
        lock_acquired = False
        if is_cache_eligible and cache_key:
            try:
                lock_acquired = await self.cache.acquire_lock(
                    cache_key,
                    timeout_seconds=self.settings.cache_lock_timeout_seconds,
                )
            except Exception:
                lock_acquired = False

            if not lock_acquired:
                # Concurrent request is in-flight; wait briefly and check cache again
                await asyncio.sleep(0.15)
                try:
                    recheck = await self.cache.get(cache_key)
                except Exception:
                    recheck = None
                if recheck is not None:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                    recheck.request_id = request_id
                    recheck.latency_ms = round(elapsed_ms, 2)
                    recheck.routing_reason = f"{decision.routing_reason};stampede_cache_hit"
                    return recheck

        # 4. Execute with retries and fallback
        response = None
        attempt_history = []
        fallback_count = 0

        try:
            (
                response,
                attempt_history,
                fallback_count,
            ) = await self.orchestrator.execute_with_fallback(
                request=request,
                decision=decision,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            # Log failed request telemetry
            asyncio.create_task(
                RequestLogRepository.log_request(
                    request_id=request_id,
                    requested_model=decision.requested_model,
                    target_model=decision.target_model,
                    provider=decision.primary_provider,
                    status="failure",
                    cache_hit=False,
                    attempt_count=len(attempt_history) or 1,
                    fallback_count=fallback_count,
                    latency_ms=elapsed_ms,
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    estimated_cost_usd=0.0,
                    routing_reason=decision.routing_reason,
                    error_message=str(exc),
                )
            )
            raise exc
        finally:
            if lock_acquired and cache_key:
                await self.cache.release_lock(cache_key)

        # 5. Calculate cost & annotate response
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        cost_usd = calculate_estimated_cost_usd(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            input_cost_per_1k=decision.input_cost_per_1k,
            output_cost_per_1k=decision.output_cost_per_1k,
        )

        response.request_id = request_id
        response.cached = False
        response.latency_ms = round(elapsed_ms, 2)
        response.cost_usd = cost_usd
        response.routing_reason = decision.routing_reason

        # 6. Store in cache if eligible
        if is_cache_eligible and cache_key:
            try:
                await self.cache.set(
                    key=cache_key,
                    response=response,
                    ttl_seconds=self.settings.cache_default_ttl_seconds,
                )
            except Exception as e:
                logger.warning(f"Cache set exception: {e}. Skipping cache write.")

        # 7. Persist audit telemetry asynchronously
        asyncio.create_task(
            RequestLogRepository.log_request(
                request_id=request_id,
                requested_model=decision.requested_model,
                target_model=decision.target_model,
                provider=response.provider,
                status="success",
                cache_hit=False,
                attempt_count=len(attempt_history),
                fallback_count=fallback_count,
                latency_ms=elapsed_ms,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                estimated_cost_usd=cost_usd,
                routing_reason=decision.routing_reason,
            )
        )

        return response
