import inspect

import pytest

from api.cache import CacheStats
from api.orchestrator import DegradationMode
from api.routes import health as health_route


class FakeCacheBackend:
    async def stats(self):
        return CacheStats(
            backend="memory",
            reachable=True,
            hits=1,
            misses=2,
            errors=0,
            entries=3,
        )


class FakeOrchestrator:
    degradation_mode = DegradationMode.NORMAL
    active_count = 0
    semaphore_slots_free = 10


@pytest.mark.asyncio
async def test_health_contains_cache_backend_and_legacy_entries(monkeypatch):
    monkeypatch.setattr(health_route, "cache_backend", FakeCacheBackend())

    payload = await health_route.health.__wrapped__(
        request=None,
        orch=FakeOrchestrator(),
        maybe_admin=None,
    )

    assert payload["cache"]["backend"] == "memory"
    assert payload["cache"]["reachable"] is True
    assert payload["cache_entries"] == 3


def test_health_route_no_longer_imports_search_service():
    source = inspect.getsource(health_route)

    assert "api.services.search_service" not in source
    assert "_api_cache" not in source
