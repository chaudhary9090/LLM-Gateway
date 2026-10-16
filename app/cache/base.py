"""Base cache interface."""

from abc import ABC, abstractmethod
from typing import Optional

from app.api.schemas import ChatCompletionResponse


class BaseCache(ABC):
    """Abstract interface for gateway response caching and locking."""

    @abstractmethod
    async def get(self, key: str) -> Optional[ChatCompletionResponse]:
        """Retrieves cached completion response if present."""
        pass

    @abstractmethod
    async def set(self, key: str, response: ChatCompletionResponse, ttl_seconds: int) -> bool:
        """Stores normalized completion response in cache with TTL."""
        pass

    @abstractmethod
    async def acquire_lock(self, key: str, timeout_seconds: float) -> bool:
        """Acquires a single-flight lock for identical concurrent requests."""
        pass

    @abstractmethod
    async def release_lock(self, key: str) -> bool:
        """Releases the single-flight lock."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Checks if the cache backend is healthy."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Closes cache client connections."""
        pass
