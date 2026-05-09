import pytest

from api.cache import InMemoryCacheBackend, RedisCacheBackend


@pytest.mark.asyncio
async def test_in_memory_cache_set_then_get_returns_value():
    cache = InMemoryCacheBackend()

    await cache.set("breach", "User@Example.com ", {"ok": True})

    assert await cache.get("breach", "user@example.com") == {"ok": True}


@pytest.mark.asyncio
async def test_in_memory_cache_ttl_expiry_returns_none():
    cache = InMemoryCacheBackend(ttl_seconds=1)

    await cache.set("breach", "x", {"ok": True}, ttl=0)

    assert await cache.get("breach", "x") is None


@pytest.mark.asyncio
async def test_in_memory_cache_oversized_value_skips_and_increments_errors():
    cache = InMemoryCacheBackend(max_value_bytes=5)

    await cache.set("breach", "x", {"large": "value"})

    assert await cache.get("breach", "x") is None
    stats = await cache.stats()
    assert stats.errors == 1


class FailingRedis:
    async def ping(self):
        return True

    async def get(self, key):
        raise OSError("redis down")

    async def dbsize(self):
        return 0

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_redis_failure_during_get_returns_none_when_fail_open():
    cache = RedisCacheBackend(client_factory=lambda: FailingRedis(), fail_open=True)
    await cache.startup()

    assert await cache.get("breach", "x") is None

    stats = await cache.stats()
    assert stats.misses == 1
    assert stats.errors >= 1


@pytest.mark.asyncio
async def test_stats_returns_expected_keys():
    cache = InMemoryCacheBackend()

    stats = await cache.stats()

    assert set(stats.__dict__) == {"backend", "reachable", "hits", "misses", "errors", "entries"}
