"""OpenAI-compatible HTTP provider adapter."""

import time
import uuid
from typing import Optional

import httpx

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


class OpenAICompatibleProvider(BaseProvider):
    """Adapter for any OpenAI-compatible API (OpenAI, Groq, Together, DeepInfra, vLLM, etc.)."""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: Optional[str] = None,
        default_model: str = "gpt-4o-mini",
        timeout_seconds: float = 15.0,
        enabled: bool = True,
        client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(name=name, provider_type="openai-compatible", enabled=enabled)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
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
        start_time = time.perf_counter()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LLM-Gateway/0.1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        endpoint = f"{self.base_url}/chat/completions"
        effective_timeout = timeout or self.timeout_seconds

        client_to_close = None
        if self._client:
            client = self._client
        else:
            client = httpx.AsyncClient(timeout=effective_timeout)
            client_to_close = client

        try:
            response = await client.post(endpoint, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                provider_name=self.name,
                message=f"Request timed out after {effective_timeout}s: {exc}",
            ) from exc
        except (httpx.NetworkError, httpx.ConnectError) as exc:
            raise ProviderConnectionError(
                provider_name=self.name,
                message=f"Network connection failed: {exc}",
            ) from exc
        except Exception as exc:
            raise ProviderConnectionError(
                provider_name=self.name,
                message=f"Unexpected transport error: {exc}",
            ) from exc
        finally:
            if client_to_close:
                await client_to_close.aclose()

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # Handle HTTP status codes
        if response.status_code in (401, 403):
            raise ProviderAuthError(
                provider_name=self.name,
                message=f"Authentication error {response.status_code}: {response.text[:200]}",
            )
        elif response.status_code == 429:
            retry_after_str = response.headers.get("Retry-After")
            retry_after = (
                float(retry_after_str) if retry_after_str and retry_after_str.isdigit() else None
            )
            raise ProviderRateLimitError(
                provider_name=self.name,
                message=f"Rate limited by provider: {response.text[:200]}",
                retry_after=retry_after,
            )
        elif response.status_code >= 500:
            raise ProviderServerError(
                provider_name=self.name,
                message=f"Upstream returned status {response.status_code}: {response.text[:200]}",
            )
        elif response.status_code != 200:
            raise ProviderServerError(
                provider_name=self.name,
                message=f"Provider unexpected status {response.status_code}: {response.text[:200]}",
            )

        # Parse JSON response
        try:
            data = response.json()
        except Exception as exc:
            raise ProviderMalformedResponseError(
                provider_name=self.name,
                message=f"Failed to parse provider response JSON: {exc}",
            ) from exc

        # Extract choices
        raw_choices = data.get("choices", [])
        if not raw_choices or not isinstance(raw_choices, list):
            raise ProviderMalformedResponseError(
                provider_name=self.name,
                message="Provider response missing 'choices' array",
            )

        choices = []
        for i, choice in enumerate(raw_choices):
            msg = choice.get("message", {})
            choices.append(
                ChatChoice(
                    index=choice.get("index", i),
                    message=ChoiceMessage(
                        role=msg.get("role", "assistant"),
                        content=msg.get("content", ""),
                    ),
                    finish_reason=choice.get("finish_reason", "stop") or "stop",
                )
            )

        # Extract usage
        raw_usage = data.get("usage", {})
        prompt_tokens = raw_usage.get("prompt_tokens")
        completion_tokens = raw_usage.get("completion_tokens")
        total_tokens = raw_usage.get("total_tokens")

        is_estimated = False
        if prompt_tokens is None or completion_tokens is None:
            prompt_tokens = max(1, sum(len(m.content.split()) for m in request.messages))
            completion_tokens = max(1, len(choices[0].message.content.split()))
            total_tokens = prompt_tokens + completion_tokens
            is_estimated = True
        elif total_tokens is None:
            total_tokens = prompt_tokens + completion_tokens

        usage = UsageInfo(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            is_estimated=is_estimated,
        )

        return ChatCompletionResponse(
            id=data.get("id", f"cmpl-{uuid.uuid4().hex[:12]}"),
            request_id=f"req-{uuid.uuid4().hex[:8]}",
            model=model,
            provider=self.name,
            choices=choices,
            usage=usage,
            cached=False,
            latency_ms=round(elapsed_ms, 2),
        )

    async def health_check(self) -> bool:
        if not self.enabled:
            return False
        client = self._get_client(timeout=5.0)
        try:
            # Use GET /models as health probe
            endpoint = f"{self.base_url}/models"
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            resp = await client.get(endpoint, headers=headers)
            return resp.status_code in (200, 401)  # 401 means server is reachable
        except Exception:
            return False
        finally:
            if not self._client:
                await client.aclose()

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Calls upstream /embeddings endpoint."""
        client = self._get_client(timeout=self.timeout_seconds)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            url = f"{self.base_url}/embeddings"
            res = await client.post(url, json={"input": texts, "model": model}, headers=headers)
            if res.status_code == 200:
                data = res.json().get("data", [])
                return [item.get("embedding", []) for item in data]
            raise ProviderServerError(
                provider_name=self.name,
                message=f"Upstream embeddings returned HTTP {res.status_code}",
            )
        finally:
            if not self._client:
                await client.aclose()
