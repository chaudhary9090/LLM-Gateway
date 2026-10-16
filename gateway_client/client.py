"""Python Client SDK for LLM Gateway (Sync & Async)."""

import json
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Union

import httpx


class GatewayError(Exception):
    """Base exception raised for LLM Gateway API errors."""

    def __init__(self, message: str, status_code: int = 500, error_code: str = "gateway_error", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


class RateLimitError(GatewayError):
    """Raised when rate limit or token/cost budget is exceeded (HTTP 429)."""
    pass


class AuthError(GatewayError):
    """Raised on invalid or missing gateway API key (HTTP 401)."""
    pass


def _map_error(status_code: int, response_text: str) -> GatewayError:
    try:
        data = json.loads(response_text)
        err = data.get("error", data)
        msg = err.get("message", response_text)
        code = err.get("code", f"http_{status_code}")
        details = err.get("details", {})
    except Exception:
        msg = response_text
        code = f"http_{status_code}"
        details = {}

    if status_code == 429:
        return RateLimitError(message=msg, status_code=status_code, error_code=code, details=details)
    if status_code == 401:
        return AuthError(message=msg, status_code=status_code, error_code=code, details=details)
    return GatewayError(message=msg, status_code=status_code, error_code=code, details=details)


# -------------------------------------------------------------
# SYNC CLIENT IMPLEMENTATION
# -------------------------------------------------------------

class SyncChatCompletions:
    def __init__(self, client: "GatewayClient"):
        self._client = client

    def create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False,
        cache: bool = True,
        task_type: Optional[str] = None,
        timeout: Optional[float] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Union[Dict[str, Any], Iterator[Dict[str, Any]]]:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            "cache": cache,
        }
        if task_type:
            payload["task_type"] = task_type

        url = f"{self._client.base_url}/v1/chat/completions"
        req_headers = self._client._build_headers(headers)

        if not stream:
            with httpx.Client(timeout=timeout or self._client.timeout) as http:
                res = http.post(url, json=payload, headers=req_headers)
                if res.status_code != 200:
                    raise _map_error(res.status_code, res.text)
                return res.json()

        def stream_generator() -> Iterator[Dict[str, Any]]:
            with httpx.Client(timeout=timeout or self._client.timeout) as http:
                with http.stream("POST", url, json=payload, headers=req_headers) as res:
                    if res.status_code != 200:
                        body = res.read().decode("utf-8")
                        raise _map_error(res.status_code, body)
                    for line in res.iter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            yield json.loads(data_str)
                        except Exception:
                            continue

        return stream_generator()


class SyncChatResource:
    def __init__(self, client: "GatewayClient"):
        self.completions = SyncChatCompletions(client)


class GatewayClient:
    """Synchronous Python client for LLM Gateway."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.chat = SyncChatResource(self)

    def _build_headers(self, custom: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "GatewayClient-Python/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key
        if custom:
            headers.update(custom)
        return headers

    def health(self) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as http:
            res = http.get(f"{self.base_url}/health", headers=self._build_headers())
            return res.json()

    def ready(self) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as http:
            res = http.get(f"{self.base_url}/ready", headers=self._build_headers())
            return res.json()

    def stats(self) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as http:
            res = http.get(f"{self.base_url}/stats", headers=self._build_headers())
            return res.json()

    def models(self) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=self.timeout) as http:
            res = http.get(f"{self.base_url}/models", headers=self._build_headers())
            return res.json()


# -------------------------------------------------------------
# ASYNC CLIENT IMPLEMENTATION
# -------------------------------------------------------------

class AsyncChatCompletions:
    def __init__(self, client: "AsyncGatewayClient"):
        self._client = client

    async def create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False,
        cache: bool = True,
        task_type: Optional[str] = None,
        timeout: Optional[float] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Union[Dict[str, Any], AsyncIterator[Dict[str, Any]]]:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            "cache": cache,
        }
        if task_type:
            payload["task_type"] = task_type

        url = f"{self._client.base_url}/v1/chat/completions"
        req_headers = self._client._build_headers(headers)

        if not stream:
            async with httpx.AsyncClient(timeout=timeout or self._client.timeout) as http:
                res = await http.post(url, json=payload, headers=req_headers)
                if res.status_code != 200:
                    raise _map_error(res.status_code, res.text)
                return res.json()

        async def async_stream_generator() -> AsyncIterator[Dict[str, Any]]:
            async with httpx.AsyncClient(timeout=timeout or self._client.timeout) as http:
                async with http.stream("POST", url, json=payload, headers=req_headers) as res:
                    if res.status_code != 200:
                        body = (await res.aread()).decode("utf-8")
                        raise _map_error(res.status_code, body)
                    async for line in res.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            yield json.loads(data_str)
                        except Exception:
                            continue

        return async_stream_generator()


class AsyncChatResource:
    def __init__(self, client: "AsyncGatewayClient"):
        self.completions = AsyncChatCompletions(client)


class AsyncGatewayClient:
    """Asynchronous Python client for LLM Gateway."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.chat = AsyncChatResource(self)

    def _build_headers(self, custom: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AsyncGatewayClient-Python/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key
        if custom:
            headers.update(custom)
        return headers

    async def health(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            res = await http.get(f"{self.base_url}/health", headers=self._build_headers())
            return res.json()

    async def ready(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            res = await http.get(f"{self.base_url}/ready", headers=self._build_headers())
            return res.json()

    async def stats(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            res = await http.get(f"{self.base_url}/stats", headers=self._build_headers())
            return res.json()

    async def models(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout) as http:
            res = await http.get(f"{self.base_url}/models", headers=self._build_headers())
            return res.json()
