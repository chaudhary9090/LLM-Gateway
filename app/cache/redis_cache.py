"""Redis and fallback in-memory cache implementations."""

import asyncio
import json
import time
from typing import Dict, Optional, Tuple

import redis.asyncio as aioredis

from app.api.schemas import ChatCompletionResponse
from app.cache.base import BaseCache
from app.core.logging import logger


class RedisCache(BaseCache):
    """Production Redis caching backend with graceful degradation and stampede locking."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None
        self._available: bool = True

    async def _get_client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
        return self._redis

    async def get(self, key: str) -> Optional[ChatCompletionResponse]:
        try:
            client = await self._get_client()
            raw = await client.get(key)
            if not raw:
                return None
            data = json.loads(raw)
            resp = ChatCompletionResponse.model_validate(data)
            resp.cached = True
            return resp
        except Exception as e:
            logger.warning(f"Redis cache GET error for key '{key}': {e}. Treating as cache miss.")
            return None

    async def set(
        self, key: str, response: ChatCompletionResponse, ttl_seconds: int = 3600
    ) -> bool:
        try:
            client = await self._get_client()
            # Mark cached=False in serialized payload so it can be stamped on retrieval
            payload = response.model_dump(mode="json")
            payload["cached"] = True
            raw = json.dumps(payload)
            await client.set(key, raw, ex=ttl_seconds)
            return True
        except Exception as e:
            logger.warning(
                f"Redis cache SET error for key '{key}': {e}. Proceeding without caching."
            )
            return False

    async def acquire_lock(self, key: str, timeout_seconds: float = 10.0) -> bool:
        try:
            client = await self._get_client()
            lock_key = f"lock:{key}"
            # Redis SET NX EX acquires lock atomically with expiration
            acquired = await client.set(lock_key, "1", nx=True, ex=int(max(1, timeout_seconds)))
            return bool(acquired)
        except Exception as e:
            logger.warning(f"Redis lock acquire error for '{key}': {e}. Proceeding without lock.")
            return True

    async def release_lock(self, key: str) -> bool:
        try:
            client = await self._get_client()
            lock_key = f"lock:{key}"
            await client.delete(lock_key)
            return True
        except Exception as e:
            logger.warning(f"Redis lock release error for '{key}': {e}")
            return False

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            pong = await client.ping()
            return bool(pong)
        except Exception:
            return False

    async def close(self) -> None:
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass


class InMemoryCache(BaseCache):
    """Resilient in-memory cache for standalone local execution and unit tests without Redis."""

    def __init__(self):
        # key -> (payload_json, expiry_timestamp)
        self._store: Dict[str, Tuple[str, float]] = {}
        self._locks: Dict[str, float] = {}
        self._async_lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[ChatCompletionResponse]:
        async with self._async_lock:
            entry = self._store.get(key)
            if not entry:
                return None
            raw_json, expiry = entry
            if time.time() > expiry:
                del self._store[key]
                return None
            data = json.loads(raw_json)
            resp = ChatCompletionResponse.model_validate(data)
            resp.cached = True
            return resp

    async def set(
        self, key: str, response: ChatCompletionResponse, ttl_seconds: int = 3600
    ) -> bool:
        async with self._async_lock:
            payload = response.model_dump(mode="json")
            payload["cached"] = True
            raw_json = json.dumps(payload)
            self._store[key] = (raw_json, time.time() + ttl_seconds)
            return True

    async def acquire_lock(self, key: str, timeout_seconds: float = 10.0) -> bool:
        async with self._async_lock:
            now = time.time()
            if key in self._locks and now < self._locks[key]:
                return False
            self._locks[key] = now + timeout_seconds
            return True

    async def release_lock(self, key: str) -> bool:
        async with self._async_lock:
            self._locks.pop(key, None)
            return True

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        self._store.clear()
        self._locks.clear()
