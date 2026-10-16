"""Deterministic mock provider for local development, CI tests, and load testing."""

import asyncio
import random
import time
import uuid
from typing import Optional

from app.api.schemas import (
    ChatChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChoiceMessage,
    UsageInfo,
)
from app.core.exceptions import (
    ProviderAuthError,
    ProviderConnectionError,
    ProviderMalformedResponseError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
)
from app.providers.base import BaseProvider


class MockProvider(BaseProvider):
    """Deterministic mock LLM provider simulating real provider behavior and failure modes."""

    def __init__(
        self,
        name: str = "mock-primary",
        enabled: bool = True,
        latency_ms: int = 10,
        failure_rate: float = 0.0,
        forced_failure: Optional[str] = None,
    ):
        super().__init__(name=name, provider_type="mock", enabled=enabled)
        self.latency_ms = latency_ms
        self.failure_rate = failure_rate
        self.forced_failure = forced_failure
        self.healthy_status = True

    async def generate(
        self,
        request: ChatCompletionRequest,
        model: str,
        timeout: float,
    ) -> ChatCompletionResponse:
        start_time = time.perf_counter()

        # Check for simulated failures passed via request metadata or provider state
        simulate_error = self.forced_failure
        sim_meta = (request.metadata or {}).get("simulate_error")
        if sim_meta and not simulate_error:
            target_prov = (request.metadata or {}).get("target_provider")
            if not target_prov or target_prov == self.name:
                simulate_error = sim_meta

        # Random failure injection based on failure_rate if not forced
        if not simulate_error and self.failure_rate > 0.0:
            if random.random() < self.failure_rate:
                simulate_error = "500"


        # Apply simulated latency
        delay_seconds = self.latency_ms / 1000.0
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        # Handle specific error simulations
        if simulate_error:
            if simulate_error == "429":
                raise ProviderRateLimitError(provider_name=self.name, retry_after=1.0)
            elif simulate_error == "500":
                raise ProviderServerError(
                    provider_name=self.name, message="Mock internal server error"
                )
            elif simulate_error == "timeout":
                raise ProviderTimeoutError(provider_name=self.name, message="Mock provider timeout")
            elif simulate_error == "connection":
                raise ProviderConnectionError(
                    provider_name=self.name, message="Mock connection dropped"
                )
            elif simulate_error == "401":
                raise ProviderAuthError(
                    provider_name=self.name, message="Mock invalid API credentials"
                )
            elif simulate_error == "malformed":
                raise ProviderMalformedResponseError(
                    provider_name=self.name, message="Mock unparseable JSON"
                )

        # Determine prompt length and token counts deterministically
        last_user_message = next(
            (m.content for m in reversed(request.messages) if m.role == "user"),
            request.messages[-1].content,
        )

        prompt_tokens = max(1, sum(len(m.content.split()) for m in request.messages))
        completion_text = f"Mock response from [{self.name}] for model [{model}]: Received '{last_user_message[:40]}...'"
        completion_tokens = max(1, len(completion_text.split()))

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return ChatCompletionResponse(
            id=f"mock-cmpl-{uuid.uuid4().hex[:12]}",
            request_id=f"req-{uuid.uuid4().hex[:8]}",
            model=model,
            provider=self.name,
            choices=[
                ChatChoice(
                    index=0,
                    message=ChoiceMessage(role="assistant", content=completion_text),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                is_estimated=False,
            ),
            cached=False,
            latency_ms=round(elapsed_ms, 2),
        )

    async def health_check(self) -> bool:
        return self.enabled and self.healthy_status

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Generates deterministic mock embedding vectors."""
        import hashlib
        import math

        results = []
        for text in texts:
            dim = 128
            vec = [0.0] * dim
            h = hashlib.sha256(text.encode("utf-8")).digest()
            for i in range(dim):
                byte_val = h[i % len(h)]
                vec[i] = ((byte_val / 255.0) * 2.0) - 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            results.append([round(x / norm, 6) for x in vec])
        return results
