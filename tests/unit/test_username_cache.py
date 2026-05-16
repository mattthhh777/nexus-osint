from __future__ import annotations

import pytest

from api.cache import InMemoryCacheBackend
import modules.username_check.cache as username_cache


def test_username_cache_key_includes_validator_version():
    first = username_cache.username_cache_key(" Alice ")
    second = username_cache.username_cache_key("alice")
    assert first == second
    assert len(first) == 64


@pytest.mark.asyncio
async def test_username_result_cache_round_trip(monkeypatch):
    backend = InMemoryCacheBackend()
    monkeypatch.setattr(username_cache, "cache_backend", backend)
    payload = {
        "username": "alice",
        "found_count": 1,
        "likely_count": 0,
        "total_checked": 1,
        "source": "internal",
        "proxy_used": False,
        "platforms": [],
    }

    await username_cache.set_cached_username_result("Alice", payload)

    assert await username_cache.get_cached_username_result(" alice ") == payload
