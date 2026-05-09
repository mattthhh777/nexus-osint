import json

import pytest

from api.cache import InMemoryCacheBackend
from api.services import search_service
from modules.oathnet_client import BreachRecord, OathnetMeta, OathnetResult, StealerRecord


def _sample_oathnet_result() -> OathnetResult:
    return OathnetResult(
        success=True,
        query="user@example.com",
        query_type="email",
        breaches=[
            BreachRecord(
                dbname="sample",
                email="user@example.com",
                username="user",
                domain="example.com",
                data_types=["email", "password"],
                extra_fields={"source": "fixture"},
                raw={"secret": "breach raw"},
            )
        ],
        results_found=1,
        stealers=[
            StealerRecord(
                log="log-1",
                url="https://example.com",
                domain=["example.com"],
                username="user",
                email=["user@example.com"],
                raw={"secret": "stealer raw"},
            )
        ],
        stealers_found=1,
        holehe_domains=["example.com"],
        meta=OathnetMeta(plan="starter", left_today=42),
        raw_response={"secret": "top-level raw"},
    )


def test_oathnet_cache_dto_round_trips_without_raw_payloads():
    source = _sample_oathnet_result()

    dto = search_service._oathnet_result_to_cache(source)
    encoded = json.dumps(dto)
    restored = search_service._oathnet_result_from_cache(dto)

    assert "raw_response" not in encoded
    assert '"raw"' not in encoded
    assert restored.breaches[0].email == source.breaches[0].email
    assert restored.breaches[0].extra_fields == source.breaches[0].extra_fields
    assert restored.stealers[0].username == source.stealers[0].username
    assert restored.stealers[0].email == source.stealers[0].email
    assert restored.meta.left_today == source.meta.left_today
    assert restored.holehe_domains == source.holehe_domains


@pytest.mark.asyncio
async def test_redis_cache_hit_skips_second_oathnet_call(monkeypatch):
    cache = InMemoryCacheBackend()
    monkeypatch.setattr(search_service, "cache_backend", cache)
    calls = {"count": 0}

    async def fake_search_breach(query: str) -> OathnetResult:
        calls["count"] += 1
        result = _sample_oathnet_result()
        result.query = query
        return result

    async def cached_breach(query: str) -> OathnetResult:
        cached = await search_service._get_cached("breach", query)
        if cached is not None:
            return cached
        result = await fake_search_breach(query)
        await search_service._set_cached("breach", query, result)
        return result

    first = await cached_breach("User@Example.com")
    second = await cached_breach(" user@example.com ")

    assert calls["count"] == 1
    assert first.breaches[0].email == second.breaches[0].email
