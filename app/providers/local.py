"""Local LLM Provider adapter for Ollama, LM Studio, llama.cpp, and vLLM."""

import time
import uuid
from typing import Any, Dict, List, Optional

import httpx

from app.api.schemas import (
    ChatChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChoiceMessage,
    UsageInfo,
)
from app.core.exceptions import (
    ProviderConnectionError,
    ProviderMalformedResponseError,
    ProviderServerError,
    ProviderTimeoutError,
)
from app.core.logging import logger
from app.providers.base import BaseProvider


class LocalProvider(BaseProvider):
    """Adapter for local OpenAI-compatible engines (Ollama, LM Studio, llama.cpp, vLLM)."""

    def __init__(
        self,
        name: str = "local",
        base_url: str = "http://localhost:11434/v1",
        default_model: str = "llama3.2",
        timeout_seconds: float = 30.0,
        enabled: bool = True,
        client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(name=name, provider_type="local", enabled=enabled)
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds
        self._client = client

    def _get_client(self, timeout: float) -> httpx.AsyncClient:
        if self._client:
            return self._client
        return httpx.AsyncClient(timeout=timeout)

    async def generate(
        self,
        request: ChatCompletionRequest,
        model: str,
        timeout: float,
    ) -> ChatCompletionResponse:
        """Executes a completion request against the local engine."""
        start_time = time.perf_counter()
        target_model = model or self.default_model

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LLM-Gateway/0.1.0 (LocalEngine)",
        }

        should_close = self._client is None
        client = self._get_client(timeout=timeout or self.timeout_seconds)

        try:
            logger.info(f"LocalProvider '{self.name}' dispatching to {url} for model '{target_model}'")
            response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(
                provider_name=self.name,
                message=f"Local engine timed out after {timeout}s: {e}",
            ) from e
        except httpx.ConnectError as e:
            raise ProviderConnectionError(
                provider_name=self.name,
                message=f"Could not connect to local engine at {url}. Is Ollama or LM Studio running? ({e})",
            ) from e
        except Exception as e:
            raise ProviderConnectionError(
                provider_name=self.name,
                message=f"Network error communicating with local engine: {e}",
            ) from e
        finally:
            if should_close:
                await client.aclose()

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        if response.status_code >= 500:
            raise ProviderServerError(
                provider_name=self.name,
                message=f"Local engine error ({response.status_code}): {response.text[:200]}",
            )

        if response.status_code != 200:
            raise ProviderServerError(
                provider_name=self.name,
                message=f"Local engine returned unexpected HTTP {response.status_code}: {response.text[:200]}",
            )

        try:
            data = response.json()
        except Exception as e:
            raise ProviderMalformedResponseError(
                provider_name=self.name,
                message=f"Failed to parse JSON response from local engine: {e}",
            ) from e

        choices_raw = data.get("choices", [])
        if not choices_raw or not isinstance(choices_raw, list):
            raise ProviderMalformedResponseError(
                provider_name=self.name,
                message="Local engine response missing valid 'choices' array",
            )

        normalized_choices: List[ChatChoice] = []
        for idx, c in enumerate(choices_raw):
            msg = c.get("message", {})
            normalized_choices.append(
                ChatChoice(
                    index=c.get("index", idx),
                    message=ChoiceMessage(
                        role=msg.get("role", "assistant"),
                        content=msg.get("content", ""),
                    ),
                    finish_reason=c.get("finish_reason", "stop") or "stop",
                )
            )

        usage_raw = data.get("usage", {})
        prompt_tokens = usage_raw.get("prompt_tokens")
        completion_tokens = usage_raw.get("completion_tokens")
        total_tokens = usage_raw.get("total_tokens")

        is_estimated = False
        if prompt_tokens is None or completion_tokens is None:
            # Estimate if local engine didn't supply usage counts
            prompt_tokens = sum(len(m.content.split()) * 2 for m in request.messages)
            content_sample = normalized_choices[0].message.content if normalized_choices else ""
            completion_tokens = len(content_sample.split()) * 2
            total_tokens = prompt_tokens + completion_tokens
            is_estimated = True

        usage = UsageInfo(
            prompt_tokens=prompt_tokens or 0,
            completion_tokens=completion_tokens or 0,
            total_tokens=total_tokens or ((prompt_tokens or 0) + (completion_tokens or 0)),
            is_estimated=is_estimated,
        )

        return ChatCompletionResponse(
            id=data.get("id", f"local-{uuid.uuid4().hex[:12]}"),
            request_id=f"req-{uuid.uuid4().hex[:12]}",
            created=data.get("created", int(time.time())),
            model=data.get("model", target_model),
            provider=self.name,
            choices=normalized_choices,
            usage=usage,
            cached=False,
            latency_ms=round(elapsed_ms, 2),
            cost_usd=0.0,  # Local inference is zero-cost
            routing_reason="local_inference",
        )

    async def health_check(self) -> bool:
        """Pings local engine models endpoint to verify readiness."""
        if not self.enabled:
            return False

        urls_to_try = [f"{self.base_url}/models"]
        # If Ollama default port, also try native /api/tags
        if "11434" in self.base_url:
            base_root = self.base_url.replace("/v1", "")
            urls_to_try.append(f"{base_root}/api/tags")

        should_close = self._client is None
        client = self._get_client(timeout=1.5)

        try:
            for url in urls_to_try:
                try:
                    res = await client.get(url)
                    if res.status_code == 200:
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            return False
        finally:
            if should_close:
                await client.aclose()

    async def list_models(self) -> List[str]:
        """Discovers models currently downloaded or served locally."""
        if not self.enabled:
            return []

        should_close = self._client is None
        client = self._get_client(timeout=2.0)
        discovered: List[str] = []

        try:
            # Try native Ollama endpoint /api/tags
            if "11434" in self.base_url:
                base_root = self.base_url.replace("/v1", "")
                try:
                    res = await client.get(f"{base_root}/api/tags")
                    if res.status_code == 200:
                        tags_data = res.json().get("models", [])
                        for item in tags_data:
                            name = item.get("name")
                            if name:
                                discovered.append(name.split(":")[0])
                                discovered.append(name)
                except Exception:
                    pass

            # Try OpenAI /models
            if not discovered:
                res = await client.get(f"{self.base_url}/models")
                if res.status_code == 200:
                    models_data = res.json().get("data", [])
                    for item in models_data:
                        m_id = item.get("id")
                        if m_id:
                            discovered.append(m_id)
        except Exception as e:
            logger.debug(f"LocalProvider {self.name} model discovery skipped: {e}")
        finally:
            if should_close:
                await client.aclose()

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for m in discovered:
            if m not in seen:
                seen.add(m)
                unique.append(m)
        return unique

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Generates embedding vectors via local engine (Ollama/vLLM) with fallback."""
        should_close = self._client is None
        client = self._get_client(timeout=self.timeout_seconds)
        results = []

        try:
            # 1. Try standard OpenAI /embeddings
            url = f"{self.base_url}/embeddings"
            res = await client.post(url, json={"input": texts, "model": model})
            if res.status_code == 200:
                data = res.json().get("data", [])
                for item in data:
                    results.append(item.get("embedding", []))
                if results:
                    return results
        except Exception as e:
            logger.debug(f"LocalProvider {self.name} embeddings failed on {url}: {e}")
        finally:
            if should_close:
                await client.aclose()

        # Fallback to deterministic projection if local model is not loaded
        import hashlib
        import math

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
