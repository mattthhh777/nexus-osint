"""Async search cache backends for Redis7 and fail-open in-memory fallback."""
from __future__ import annotations

import json
import logging
import socket
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable, Protocol

from api.config import (
    CACHE_FAIL_OPEN,
    CACHE_KEY_PREFIX,
    CACHE_MAX_VALUE_BYTES,
    CACHE_TTL_SECONDS,
    REDIS_URL,
)

try:
    import redis.asyncio as redis_asyncio
    from redis.exceptions import RedisError
except ImportError:  # pragma: no cover - local env may not have deps installed yet
    redis_asyncio = None

    class RedisError(Exception):
        """Fallback RedisError when redis package is not installed."""


logger = logging.getLogger("nexusosint.cache")


@dataclass
class CacheStats:
    backend: str
    reachable: bool
    hits: int
    misses: int
    errors: int
    entries: int | None


class CacheBackend(Protocol):
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...
    async def get(self, endpoint: str, query: str) -> Any | None: ...
    async def set(self, endpoint: str, query: str, value: Any, ttl: int | None = None) -> None: ...
    async def stats(self) -> CacheStats: ...


def _cache_key(endpoint: str, query: str) -> str:
    normalized = query.lower().strip()
    digest = sha256(normalized.encode("utf-8")).hexdigest()
    return f"{CACHE_KEY_PREFIX}:{endpoint}:{digest}"


class InMemoryCacheBackend:
    def __init__(
        self,
        ttl_seconds: int = CACHE_TTL_SECONDS,
        max_value_bytes: int = CACHE_MAX_VALUE_BYTES,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_value_bytes = max_value_bytes
        self._items: dict[str, tuple[float, str]] = {}
        self._hits = 0
        self._misses = 0
        self._errors = 0

    async def startup(self) -> None:
        return None

    async def shutdown(self) -> None:
        self._items.clear()

    async def get(self, endpoint: str, query: str) -> Any | None:
        key = _cache_key(endpoint, query)
        item = self._items.get(key)
        if item is None:
            self._misses += 1
            return None
        expires_at, payload = item
        if expires_at <= time.monotonic():
            self._items.pop(key, None)
            self._misses += 1
            return None
        try:
            value = json.loads(payload)
        except json.JSONDecodeError:
            self._items.pop(key, None)
            self._errors += 1
            self._misses += 1
            return None
        self._hits += 1
        return value

    async def set(self, endpoint: str, query: str, value: Any, ttl: int | None = None) -> None:
        if value is None:
            return
        try:
            payload = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError):
            self._errors += 1
            return
        if len(payload.encode("utf-8")) > self._max_value_bytes:
            self._errors += 1
            return
        expires_at = time.monotonic() + (ttl if ttl is not None else self._ttl_seconds)
        self._items[_cache_key(endpoint, query)] = (expires_at, payload)

    async def stats(self) -> CacheStats:
        now = time.monotonic()
        expired = [key for key, (expires_at, _) in self._items.items() if expires_at <= now]
        for key in expired:
            self._items.pop(key, None)
        return CacheStats(
            backend="memory",
            reachable=True,
            hits=self._hits,
            misses=self._misses,
            errors=self._errors,
            entries=len(self._items),
        )


class RedisCacheBackend:
    def __init__(
        self,
        redis_url: str = REDIS_URL,
        ttl_seconds: int = CACHE_TTL_SECONDS,
        fail_open: bool = CACHE_FAIL_OPEN,
        max_value_bytes: int = CACHE_MAX_VALUE_BYTES,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._ttl_seconds = ttl_seconds
        self._fail_open = fail_open
        self._max_value_bytes = max_value_bytes
        self._client_factory = client_factory
        self._client: Any | None = None
        self._reachable = False
        self._hits = 0
        self._misses = 0
        self._errors = 0

    async def startup(self) -> None:
        try:
            if self._client is None:
                if self._client_factory is not None:
                    self._client = self._client_factory()
                else:
                    if redis_asyncio is None:
                        raise RedisError("redis package is not installed")
                    self._client = redis_asyncio.from_url(
                        self._redis_url,
                        decode_responses=True,
                        socket_connect_timeout=1,
                        socket_timeout=1,
                    )
            await self._client.ping()
            self._reachable = True
        except (RedisError, OSError, socket.timeout, TimeoutError) as exc:
            self._reachable = False
            self._errors += 1
            logger.warning("Cache startup failed open: %s", type(exc).__name__)
            if not self._fail_open:
                raise

    async def shutdown(self) -> None:
        if self._client is None:
            return
        try:
            await self._client.aclose()
        except (RedisError, OSError, socket.timeout, TimeoutError) as exc:
            self._errors += 1
            logger.warning("Cache shutdown failed open: %s", type(exc).__name__)
        finally:
            self._client = None
            self._reachable = False

    async def get(self, endpoint: str, query: str) -> Any | None:
        if self._client is None:
            self._misses += 1
            return None
        try:
            payload = await self._client.get(_cache_key(endpoint, query))
            if payload is None:
                self._misses += 1
                return None
            value = json.loads(payload)
        except (RedisError, json.JSONDecodeError, TypeError, ValueError, OSError, socket.timeout, TimeoutError) as exc:
            self._errors += 1
            self._misses += 1
            self._reachable = False
            logger.warning("Cache get failed open: %s", type(exc).__name__)
            if not self._fail_open:
                raise
            return None
        self._hits += 1
        self._reachable = True
        return value

    async def set(self, endpoint: str, query: str, value: Any, ttl: int | None = None) -> None:
        if value is None or self._client is None:
            return
        try:
            payload = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
            if len(payload.encode("utf-8")) > self._max_value_bytes:
                self._errors += 1
                return
            await self._client.setex(_cache_key(endpoint, query), ttl or self._ttl_seconds, payload)
            self._reachable = True
        except (RedisError, TypeError, ValueError, OSError, socket.timeout, TimeoutError) as exc:
            self._errors += 1
            self._reachable = False
            logger.warning("Cache set failed open: %s", type(exc).__name__)
            if not self._fail_open:
                raise

    async def stats(self) -> CacheStats:
        entries: int | None = None
        if self._client is not None:
            try:
                entries = await self._client.dbsize()
                self._reachable = True
            except (RedisError, OSError, socket.timeout, TimeoutError) as exc:
                self._errors += 1
                self._reachable = False
                logger.warning("Cache stats failed open: %s", type(exc).__name__)
                if not self._fail_open:
                    raise
        return CacheStats(
            backend="redis",
            reachable=self._reachable,
            hits=self._hits,
            misses=self._misses,
            errors=self._errors,
            entries=entries,
        )


cache_backend: CacheBackend = RedisCacheBackend()
