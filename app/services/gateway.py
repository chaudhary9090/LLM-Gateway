"""Unified Gateway Service orchestrating routing, caching, resilience, and persistence."""

import asyncio
import json
import time
import uuid
from typing import AsyncIterator, Optional

from app.api.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    CompareRequest,
    CompareResponse,
    EmbeddingData,
    EmbeddingRequest,
    EmbeddingResponse,
    ModelComparisonResult,
)
from app.cache.base import BaseCache
from app.cache.keys import generate_cache_key
from app.cache.semantic import SemanticCache
from app.core.config import Settings
from app.core.exceptions import InvalidRequestError
from app.core.logging import logger
from app.guardrails import detect_prompt_injection, redact_pii
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
        self.semantic_cache = SemanticCache(threshold=settings.semantic_cache_threshold)

    async def complete(
        self,
        request: ChatCompletionRequest,
        client_request_id: Optional[str] = None,
    ) -> ChatCompletionResponse:
        """Executes full chat completion lifecycle."""
        request_id = client_request_id or f"req-{uuid.uuid4().hex[:12]}"
        start_time = time.perf_counter()

        # 0. Guardrails evaluation
        user_prompt = " ".join(m.content for m in request.messages)
        if len(user_prompt) > self.settings.max_prompt_chars:
            raise InvalidRequestError(
                f"Prompt character count ({len(user_prompt)}) exceeds gateway limit ({self.settings.max_prompt_chars})"
            )

        flagged_injection = False
        if self.settings.guardrails_enabled:
            is_injection, pattern_str = detect_prompt_injection(user_prompt)
            if is_injection:
                if self.settings.guardrails_mode == "block":
                    raise InvalidRequestError(
                        f"Prompt rejected by guardrails policy: adversarial injection pattern detected ({pattern_str})."
                    )
                logger.warning(f"Guardrail flagged possible injection: {pattern_str} in request {request_id}")
                flagged_injection = True

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
        if flagged_injection:
            decision.routing_reason += ";guardrail_flagged"

        # 2. Evaluate exact cache eligibility
        is_cache_eligible = self.settings.cache_enabled and request.cache is not False
        cache_key = None
        if is_cache_eligible:
            cache_key = generate_cache_key(
                request=request,
                target_model=decision.target_model,
                schema_version=self.settings.cache_schema_version,
            )

            # Check exact Redis/memory cache
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

                # Async log cache hit (with PII redaction)
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

            # 2b. Evaluate Semantic Cache if enabled and exact match missed
            if self.settings.semantic_cache_enabled:
                semantic_hit = self.semantic_cache.lookup(decision.target_model, user_prompt)
                if semantic_hit:
                    sem_resp, sim = semantic_hit
                    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                    sem_resp.request_id = request_id
                    sem_resp.latency_ms = round(elapsed_ms, 2)
                    sem_resp.cached = True
                    sem_resp.routing_reason = f"{decision.routing_reason};semantic_cache_hit(sim={sim:.2f})"

                    asyncio.create_task(
                        RequestLogRepository.log_request(
                            request_id=request_id,
                            requested_model=decision.requested_model,
                            target_model=decision.target_model,
                            provider=sem_resp.provider,
                            status="success",
                            cache_hit=True,
                            attempt_count=1,
                            fallback_count=0,
                            latency_ms=elapsed_ms,
                            input_tokens=sem_resp.usage.prompt_tokens,
                            output_tokens=sem_resp.usage.completion_tokens,
                            total_tokens=sem_resp.usage.total_tokens,
                            estimated_cost_usd=sem_resp.cost_usd or 0.0,
                            routing_reason=sem_resp.routing_reason,
                        )
                    )
                    return sem_resp

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
                    error_message=redact_pii(str(exc)),
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

        # 6. Store in exact cache and semantic cache
        if is_cache_eligible and cache_key:
            try:
                await self.cache.set(
                    key=cache_key,
                    response=response,
                    ttl_seconds=self.settings.cache_default_ttl_seconds,
                )
            except Exception as e:
                logger.warning(f"Cache set exception: {e}. Skipping cache write.")

        if self.settings.semantic_cache_enabled:
            self.semantic_cache.store(decision.target_model, user_prompt, response)

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

    async def complete_stream(
        self,
        request: ChatCompletionRequest,
        client_request_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Streams completion tokens using Server-Sent Events (SSE). Replays cache as stream if cached."""
        req_id = client_request_id or f"req-{uuid.uuid4().hex[:12]}"

        # Execute standard completion flow to leverage fallback, circuit breaker, and caching
        response = await self.complete(request=request, client_request_id=req_id)
        content = response.choices[0].message.content if response.choices else ""

        # Emit initial role chunk
        role_chunk = {
            "id": response.id,
            "object": "chat.completion.chunk",
            "created": response.created,
            "model": response.model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant"},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(role_chunk)}\n\n"

        # Emit content tokens (split by whitespace/newlines for smooth replay)
        words = content.split(" ")
        for idx, word in enumerate(words):
            token_str = (" " if idx > 0 else "") + word
            chunk = {
                "id": response.id,
                "object": "chat.completion.chunk",
                "created": response.created,
                "model": response.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": token_str},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            # Small pacing pause for natural streaming feel
            await asyncio.sleep(0.015)

        # Emit final stop chunk
        stop_chunk = {
            "id": response.id,
            "object": "chat.completion.chunk",
            "created": response.created,
            "model": response.model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        }
        yield f"data: {json.dumps(stop_chunk)}\n\n"
        yield "data: [DONE]\n\n"

    async def create_embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generates embedding vectors with caching and offline support."""
        inputs = [request.input] if isinstance(request.input, str) else request.input
        target_model = request.model or "text-embedding-3-small"

        # Check Redis cache for embedding
        cache_key = f"embed:{target_model}:{hash(tuple(inputs))}"
        if self.settings.cache_enabled:
            try:
                cached_data = await self.cache.get(cache_key)
                if cached_data:
                    return cached_data
            except Exception:
                pass

        # Choose provider: if local model or local enabled, use local, else mock or primary
        provider = self.orchestrator.registry.get("local")
        if not provider or not provider.enabled:
            provider = self.orchestrator.registry.get("mock-primary") or self.orchestrator.registry.get("openai-main")

        vectors = await provider.embed(texts=inputs, model=target_model)

        total_tokens = sum(len(t.split()) * 2 for t in inputs)
        data_items = [
            EmbeddingData(object="embedding", index=idx, embedding=vec)
            for idx, vec in enumerate(vectors)
        ]
        resp = EmbeddingResponse(
            object="list",
            data=data_items,
            model=target_model,
            usage={"prompt_tokens": total_tokens, "total_tokens": total_tokens},
            cached=False,
        )

        if self.settings.cache_enabled:
            try:
                await self.cache.set(cache_key, resp, ttl_seconds=self.settings.cache_default_ttl_seconds)
            except Exception:
                pass

        return resp

    async def compare_models(self, request: CompareRequest) -> CompareResponse:
        """Executes the same prompt concurrently across multiple models."""
        tasks = []
        prompt_preview = request.messages[-1].content if request.messages else ""

        for m in request.models:
            sub_req = ChatCompletionRequest(
                model=m,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                cache=False,  # Fresh parallel comparison
            )
            tasks.append(self._execute_single_comparison(m, sub_req))

        results = await asyncio.gather(*tasks)
        return CompareResponse(prompt=prompt_preview, results=results)

    async def _execute_single_comparison(
        self, model_name: str, req: ChatCompletionRequest
    ) -> ModelComparisonResult:
        start = time.perf_counter()
        try:
            resp = await self.complete(request=req)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return ModelComparisonResult(
                model=resp.model,
                provider=resp.provider,
                content=resp.choices[0].message.content if resp.choices else "",
                latency_ms=round(elapsed_ms, 2),
                tokens=resp.usage.total_tokens,
                cost_usd=resp.cost_usd or 0.0,
                cached=resp.cached,
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return ModelComparisonResult(
                model=model_name,
                provider="error",
                content="",
                latency_ms=round(elapsed_ms, 2),
                tokens=0,
                cost_usd=0.0,
                cached=False,
                error=str(e),
            )
