"""Unit tests for the hardened connector runner."""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
import pytest

from modules.connectors import runner
from modules.connectors.base import (
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    Evidence,
    TargetType,
)


class FakeCache:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str], Any] = {}
        self.ttls: dict[tuple[str, str], int | None] = {}
        self.fail_get = False
        self.fail_set = False

    async def get(self, endpoint: str, query: str) -> Any | None:
        if self.fail_get:
            raise ConnectionError("redis unavailable")
        return self.items.get((endpoint, query))

    async def set(
        self,
        endpoint: str,
        query: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        if self.fail_set:
            raise ConnectionError("redis unavailable")
        self.items[(endpoint, query)] = value
        self.ttls[(endpoint, query)] = ttl


class FakeLimiter:
    def __init__(self) -> None:
        self.domains: list[str] = []

    async def acquire(self, domain: str) -> None:
        self.domains.append(domain)


class MockConnector:
    name = "mock"
    target_types = (TargetType.USERNAME,)
    default_timeout_s = 1
    rate_limit_cps = 2.0

    def __init__(
        self,
        result: ConnectorResult | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls = 0

    async def run(self, req: ConnectorRequest, http: httpx.AsyncClient) -> ConnectorResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise AssertionError("mock result missing")
        return self.result


@pytest.fixture
def connector_request() -> ConnectorRequest:
    return ConnectorRequest(
        target_type=TargetType.USERNAME,
        target_value="plain-user-never-logged",
        target_hash="0123456789abcdef",
        job_id=uuid4(),
    )


@pytest.fixture
def found_result() -> ConnectorResult:
    return ConnectorResult(
        connector="mock",
        target_type=TargetType.USERNAME,
        status=ConnectorStatus.FOUND,
        confidence_score=95,
        confidence_level="high",
        fetched_at=datetime.now(timezone.utc),
        elapsed_ms=12,
    )


@pytest.fixture
def not_found_result() -> ConnectorResult:
    return ConnectorResult(
        connector="mock",
        target_type=TargetType.USERNAME,
        status=ConnectorStatus.NOT_FOUND,
        confidence_score=0,
        confidence_level="none",
        fetched_at=datetime.now(timezone.utc),
        elapsed_ms=9,
    )


@pytest.fixture(autouse=True)
def fake_runner_dependencies(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeCache, FakeLimiter]:
    cache = FakeCache()
    limiter = FakeLimiter()
    monkeypatch.setattr(runner, "cache_backend", cache)
    monkeypatch.setattr(runner, "_limiter", limiter)
    monkeypatch.setattr(runner, "_limiters_by_cps", {})
    return cache, limiter


def _wrap(payload: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": 1, "sanitized": True, "payload": payload}


@pytest.mark.asyncio
async def test_run_connector_caches_found_result(
    connector_request: ConnectorRequest,
    found_result: ConnectorResult,
    fake_runner_dependencies: tuple[FakeCache, FakeLimiter],
) -> None:
    cache, _limiter = fake_runner_dependencies
    connector = MockConnector(result=found_result)
    async with httpx.AsyncClient() as http:
        first = await runner.run_connector(connector, connector_request, http)
        second = await runner.run_connector(connector, connector_request, http)

    assert first.status == ConnectorStatus.FOUND
    assert first.cache_hit is False
    assert second.status == ConnectorStatus.FOUND
    assert second.cache_hit is True
    assert connector.calls == 1
    assert list(cache.items) == [("connector:mock", "username:0123456789ab")]
    assert cache.ttls[("connector:mock", "username:0123456789ab")] == 300
    assert connector_request.target_value not in str(list(cache.items))
    cached_envelope = cache.items[("connector:mock", "username:0123456789ab")]
    assert cached_envelope["schema_version"] == 1
    assert cached_envelope["sanitized"] is True
    assert isinstance(cached_envelope["payload"], dict)


@pytest.mark.asyncio
async def test_run_connector_timeout_returns_error(connector_request: ConnectorRequest) -> None:
    connector = MockConnector(error=asyncio.TimeoutError())
    async with httpx.AsyncClient() as http:
        result = await runner.run_connector(connector, connector_request, http)

    assert result.status == ConnectorStatus.ERROR
    assert result.warnings == ["timeout"]
    assert result.cache_hit is False


@pytest.mark.asyncio
async def test_run_connector_cache_key_hashes_malformed_target_hash(
    found_result: ConnectorResult,
    fake_runner_dependencies: tuple[FakeCache, FakeLimiter],
) -> None:
    cache, _limiter = fake_runner_dependencies
    req = ConnectorRequest(
        target_type=TargetType.USERNAME,
        target_value="Plain-User-Never-Logged",
        target_hash="Plain-User-Never-Logged",
        job_id=uuid4(),
    )
    expected_hash = hashlib.sha256(
        "plain-user-never-logged".encode("utf-8")
    ).hexdigest()[:12]
    connector = MockConnector(result=found_result)

    async with httpx.AsyncClient() as http:
        await runner.run_connector(connector, req, http)

    assert list(cache.items) == [("connector:mock", f"username:{expected_hash}")]
    assert req.target_value not in str(list(cache.items))


@pytest.mark.asyncio
async def test_run_connector_sanitizes_sensitive_cache_value(
    fake_runner_dependencies: tuple[FakeCache, FakeLimiter],
) -> None:
    cache, _limiter = fake_runner_dependencies
    req = ConnectorRequest(
        target_type=TargetType.EMAIL,
        target_value="victim@example.com",
        target_hash="abcdef0123456789",
        job_id=uuid4(),
    )
    result = ConnectorResult(
        connector="mock",
        target_type=TargetType.EMAIL,
        status=ConnectorStatus.FOUND,
        confidence_score=92,
        confidence_level="high",
        evidence=[
            Evidence(
                signal="profile_match",
                weight=80,
                detail="email victim@example.com phone +1 555 123 4567",
            )
        ],
        warnings=["query victim@example.com was checked"],
        raw_url="https://example.test/u/victim@example.com?phone=+15551234567",
        data={
            "category": "breach",
            "labels": ["safe-label", "victim@example.com", "+15551234567"],
            "target_value": "victim@example.com",
            "query": "victim@example.com",
            "raw_target": "victim@example.com",
            "payload": {"email": "victim@example.com", "phone": "+15551234567"},
        },
        fetched_at=datetime.now(timezone.utc),
        elapsed_ms=14,
    )
    connector = MockConnector(result=result)

    async with httpx.AsyncClient() as http:
        await runner.run_connector(connector, req, http)

    envelope = next(iter(cache.items.values()))
    assert envelope["schema_version"] == 1
    assert envelope["sanitized"] is True
    cached = envelope["payload"]
    cached_text = str(cached)
    assert "victim@example.com" not in cached_text
    assert "+15551234567" not in cached_text
    assert "+1 555 123 4567" not in cached_text
    assert "target_value" not in cached_text
    assert "raw_target" not in cached_text
    assert "payload" not in cached_text
    assert cached["raw_url"] is None
    assert cached["data"]["target_hash"] == "abcdef012345"
    assert cached["data"]["category"] == "breach"


@pytest.mark.asyncio
async def test_run_connector_cache_fail_open_get_and_set(
    connector_request: ConnectorRequest,
    found_result: ConnectorResult,
    fake_runner_dependencies: tuple[FakeCache, FakeLimiter],
) -> None:
    cache, _limiter = fake_runner_dependencies
    connector = MockConnector(result=found_result)

    cache.fail_get = True
    async with httpx.AsyncClient() as http:
        result = await runner.run_connector(connector, connector_request, http)
    assert result.status == ConnectorStatus.FOUND
    assert connector.calls == 1

    cache.items.clear()
    cache.fail_get = False
    cache.fail_set = True
    connector = MockConnector(result=found_result)
    async with httpx.AsyncClient() as http:
        result = await runner.run_connector(connector, connector_request, http)
    assert result.status == ConnectorStatus.FOUND
    assert connector.calls == 1


@pytest.mark.asyncio
async def test_run_connector_invalid_cache_does_not_become_found(
    connector_request: ConnectorRequest,
    not_found_result: ConnectorResult,
    fake_runner_dependencies: tuple[FakeCache, FakeLimiter],
) -> None:
    cache, _limiter = fake_runner_dependencies
    key = ("connector:mock", "username:0123456789ab")
    payload = not_found_result.model_dump(mode="json")
    payload["status"] = "invalid_status"
    cache.items[key] = _wrap(payload)
    connector = MockConnector(result=not_found_result)

    async with httpx.AsyncClient() as http:
        result = await runner.run_connector(connector, connector_request, http)

    assert result.status == ConnectorStatus.NOT_FOUND
    assert result.cache_hit is False
    assert connector.calls == 1


@pytest.mark.asyncio
async def test_run_connector_unknown_connector_exception_returns_error_without_pii(
    connector_request: ConnectorRequest,
    fake_runner_dependencies: tuple[FakeCache, FakeLimiter],
    caplog: pytest.LogCaptureFixture,
) -> None:
    cache, _limiter = fake_runner_dependencies
    connector = MockConnector(
        error=RuntimeError("victim plain-user-never-logged +15551234567")
    )

    caplog.set_level("WARNING", logger="nexusosint.connectors.runner")
    async with httpx.AsyncClient() as http:
        result = await runner.run_connector(connector, connector_request, http)

    assert result.status == ConnectorStatus.ERROR
    assert result.warnings == ["connector_error"]
    assert cache.items == {}
    assert connector_request.target_value not in caplog.text
    assert "+15551234567" not in caplog.text


@pytest.mark.asyncio
async def test_run_connector_invalid_connector_result_returns_error(
    connector_request: ConnectorRequest,
    fake_runner_dependencies: tuple[FakeCache, FakeLimiter],
) -> None:
    cache, _limiter = fake_runner_dependencies
    connector = MockConnector(
        result={
            "connector": "mock",
            "target_type": "username",
            "status": "invalid_status",
            "confidence_score": 100,
            "confidence_level": "high",
            "fetched_at": datetime.now(timezone.utc),
            "elapsed_ms": 1,
        }  # type: ignore[arg-type]
    )

    async with httpx.AsyncClient() as http:
        result = await runner.run_connector(connector, connector_request, http)

    assert result.status == ConnectorStatus.ERROR
    assert result.warnings == ["connector_error"]
    assert cache.items == {}


@pytest.mark.asyncio
async def test_run_connector_http_429_returns_blocked(connector_request: ConnectorRequest) -> None:
    request = httpx.Request("GET", "https://example.test/rate-limit")
    response = httpx.Response(429, request=request)
    error = httpx.HTTPStatusError("rate limited", request=request, response=response)
    connector = MockConnector(error=error)

    async with httpx.AsyncClient() as http:
        result = await runner.run_connector(connector, connector_request, http)

    assert result.status == ConnectorStatus.BLOCKED
    assert result.warnings == ["http_429"]


@pytest.mark.asyncio
async def test_run_connector_http_500_returns_error(connector_request: ConnectorRequest) -> None:
    request = httpx.Request("GET", "https://example.test/error")
    response = httpx.Response(500, request=request)
    error = httpx.HTTPStatusError("server error", request=request, response=response)
    connector = MockConnector(error=error)

    async with httpx.AsyncClient() as http:
        result = await runner.run_connector(connector, connector_request, http)

    assert result.status == ConnectorStatus.ERROR
    assert result.warnings == ["http_500"]


# ─── HALT regression tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_connector_legacy_cache_without_envelope_rejected_as_miss(
    connector_request: ConnectorRequest,
    found_result: ConnectorResult,
    fake_runner_dependencies: tuple[FakeCache, FakeLimiter],
) -> None:
    """Legacy cache payload (no schema_version envelope) MUST be treated as a miss."""
    cache, _limiter = fake_runner_dependencies
    key = ("connector:mock", "username:0123456789ab")
    legacy_payload = found_result.model_dump(mode="json")
    legacy_payload["raw_url"] = "https://leak.test/?email=victim@example.com"
    legacy_payload["data"] = {
        "category": "breach",
        "email": "victim@example.com",
        "target_hash": "ATTACKERHASH",
    }
    cache.items[key] = legacy_payload  # NO envelope wrapper

    connector = MockConnector(result=found_result)
    async with httpx.AsyncClient() as http:
        result = await runner.run_connector(connector, connector_request, http)

    assert result.cache_hit is False
    assert connector.calls == 1
    rendered = str(result.model_dump(mode="json"))
    assert "victim@example.com" not in rendered
    assert "ATTACKERHASH" not in rendered


@pytest.mark.asyncio
async def test_run_connector_unsanitized_envelope_rejected_as_miss(
    connector_request: ConnectorRequest,
    found_result: ConnectorResult,
    fake_runner_dependencies: tuple[FakeCache, FakeLimiter],
) -> None:
    """Envelope with sanitized=False MUST be rejected as cache miss."""
    cache, _limiter = fake_runner_dependencies
    key = ("connector:mock", "username:0123456789ab")
    payload = found_result.model_dump(mode="json")
    cache.items[key] = {
        "schema_version": 1,
        "sanitized": False,
        "payload": payload,
    }

    connector = MockConnector(result=found_result)
    async with httpx.AsyncClient() as http:
        result = await runner.run_connector(connector, connector_request, http)

    assert result.cache_hit is False
    assert connector.calls == 1


@pytest.mark.asyncio
async def test_run_connector_wrong_schema_version_rejected_as_miss(
    connector_request: ConnectorRequest,
    found_result: ConnectorResult,
    fake_runner_dependencies: tuple[FakeCache, FakeLimiter],
) -> None:
    """Envelope with wrong schema_version MUST be rejected as cache miss."""
    cache, _limiter = fake_runner_dependencies
    key = ("connector:mock", "username:0123456789ab")
    payload = found_result.model_dump(mode="json")
    cache.items[key] = {
        "schema_version": 99,
        "sanitized": True,
        "payload": payload,
    }

    connector = MockConnector(result=found_result)
    async with httpx.AsyncClient() as http:
        result = await runner.run_connector(connector, connector_request, http)

    assert result.cache_hit is False
    assert connector.calls == 1


@pytest.mark.asyncio
async def test_run_connector_cached_payload_with_pii_is_resanitized_on_read(
    connector_request: ConnectorRequest,
    fake_runner_dependencies: tuple[FakeCache, FakeLimiter],
) -> None:
    """Cached envelope containing PII MUST be re-sanitized before returning."""
    cache, _limiter = fake_runner_dependencies
    key = ("connector:mock", "username:0123456789ab")
    poisoned_payload = {
        "connector": "mock",
        "target_type": "username",
        "status": "found",
        "confidence_score": 90,
        "confidence_level": "high",
        "evidence": [
            {
                "signal": "profile_match",
                "weight": 70,
                "detail": "owner victim@example.com phone +15551234567",
            }
        ],
        "warnings": ["seen at https://leak.test/?u=plain-user-never-logged"],
        "raw_url": "https://leak.test/?email=victim@example.com",
        "data": {
            "category": "breach",
            "email": "victim@example.com",
            "phone": "+15551234567",
            "target_hash": "ATTACKERHASH",
        },
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "cache_hit": False,
        "elapsed_ms": 11,
    }
    cache.items[key] = _wrap(poisoned_payload)

    connector = MockConnector()  # connector MUST NOT need to run; cache hit acceptable IFF sanitized
    async with httpx.AsyncClient() as http:
        result = await runner.run_connector(connector, connector_request, http)

    rendered = str(result.model_dump(mode="json"))
    assert "victim@example.com" not in rendered
    assert "+15551234567" not in rendered
    assert "leak.test" not in rendered
    assert result.data["target_hash"] == "0123456789ab"
    assert "ATTACKERHASH" not in rendered
    assert "email" not in result.data
    assert "phone" not in result.data


@pytest.mark.asyncio
async def test_run_connector_broad_httpx_error_returns_generic_without_target_leak(
    connector_request: ConnectorRequest,
    fake_runner_dependencies: tuple[FakeCache, FakeLimiter],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Generic httpx.HTTPError (e.g. ProtocolError) MUST NOT leak URL/target."""
    cache, _limiter = fake_runner_dependencies

    class _LeakyProtocolError(httpx.HTTPError):
        def __init__(self) -> None:
            super().__init__(
                "boom at https://example.test/u/plain-user-never-logged?email=victim@example.com"
            )

    connector = MockConnector(error=_LeakyProtocolError())

    caplog.set_level("WARNING", logger="nexusosint.connectors.runner")
    async with httpx.AsyncClient() as http:
        result = await runner.run_connector(connector, connector_request, http)

    assert result.status == ConnectorStatus.ERROR
    assert result.warnings == ["connector_http_error"]
    assert cache.items == {}
    assert "plain-user-never-logged" not in caplog.text
    assert "victim@example.com" not in caplog.text
    assert "example.test" not in caplog.text
    rendered = str(result.model_dump(mode="json"))
    assert "plain-user-never-logged" not in rendered
    assert "victim@example.com" not in rendered


@pytest.mark.asyncio
async def test_run_connector_canonical_target_hash_wins_over_connector_override(
    connector_request: ConnectorRequest,
    fake_runner_dependencies: tuple[FakeCache, FakeLimiter],
) -> None:
    """A connector cannot inject `data.target_hash` — runner value wins."""
    cache, _limiter = fake_runner_dependencies
    malicious = ConnectorResult(
        connector="mock",
        target_type=TargetType.USERNAME,
        status=ConnectorStatus.FOUND,
        confidence_score=90,
        confidence_level="high",
        fetched_at=datetime.now(timezone.utc),
        elapsed_ms=10,
        data={"target_hash": "DEADBEEFCAFE", "category": "ok"},
    )
    connector = MockConnector(result=malicious)

    async with httpx.AsyncClient() as http:
        await runner.run_connector(connector, connector_request, http)

    envelope = next(iter(cache.items.values()))
    cached_payload = envelope["payload"]
    assert cached_payload["data"]["target_hash"] == "0123456789ab"
    assert "DEADBEEFCAFE" not in str(cached_payload)


@pytest.mark.asyncio
async def test_run_connector_cpf_redacted_in_evidence(
    fake_runner_dependencies: tuple[FakeCache, FakeLimiter],
) -> None:
    """CPF-formatted strings must be redacted from cached evidence/warnings."""
    cache, _limiter = fake_runner_dependencies
    req = ConnectorRequest(
        target_type=TargetType.USERNAME,
        target_value="some-user",
        target_hash="abcdef0123456789",
        job_id=uuid4(),
    )
    result = ConnectorResult(
        connector="mock",
        target_type=TargetType.USERNAME,
        status=ConnectorStatus.FOUND,
        confidence_score=88,
        confidence_level="high",
        evidence=[
            Evidence(
                signal="doc_match",
                weight=75,
                detail="owner CPF 123.456.789-09 plus 987.654.321-00",
            )
        ],
        warnings=["found CPF 111.222.333-44"],
        fetched_at=datetime.now(timezone.utc),
        elapsed_ms=20,
    )
    connector = MockConnector(result=result)

    async with httpx.AsyncClient() as http:
        await runner.run_connector(connector, req, http)

    envelope = next(iter(cache.items.values()))
    cached = envelope["payload"]
    cached_text = str(cached)
    assert "123.456.789-09" not in cached_text
    assert "987.654.321-00" not in cached_text
    assert "111.222.333-44" not in cached_text


def test_limiter_for_uses_distinct_instances_per_cps() -> None:
    """Connectors with different rate_limit_cps must get different limiters."""

    class FastConnector:
        name = "fast"
        target_types = (TargetType.USERNAME,)
        default_timeout_s = 1
        rate_limit_cps = 5.0

        async def run(self, req, http):  # pragma: no cover - not invoked
            raise AssertionError("not used")

    class SlowConnector:
        name = "slow"
        target_types = (TargetType.USERNAME,)
        default_timeout_s = 1
        rate_limit_cps = 0.5

        async def run(self, req, http):  # pragma: no cover - not invoked
            raise AssertionError("not used")

    fast_limiter = runner._limiter_for(FastConnector())
    slow_limiter = runner._limiter_for(SlowConnector())
    default_limiter = runner._limiter_for(MockConnector())  # cps=2.0

    assert fast_limiter is not slow_limiter
    assert fast_limiter is not default_limiter
    assert slow_limiter is not default_limiter
    assert runner._limiter_for(FastConnector()) is fast_limiter
    assert runner._limiter_for(SlowConnector()) is slow_limiter


@pytest.mark.asyncio
async def test_run_connector_rate_limit_cps_routes_to_per_connector_limiter(
    connector_request: ConnectorRequest,
    found_result: ConnectorResult,
    monkeypatch: pytest.MonkeyPatch,
    fake_runner_dependencies: tuple[FakeCache, FakeLimiter],
) -> None:
    """A connector with non-default cps MUST acquire from its own limiter."""
    _cache, default_limiter = fake_runner_dependencies

    class FastConnector(MockConnector):
        name = "fast"
        rate_limit_cps = 5.0

    custom = FakeLimiter()
    monkeypatch.setitem(runner._limiters_by_cps, 5.0, custom)

    connector = FastConnector(result=found_result)
    async with httpx.AsyncClient() as http:
        await runner.run_connector(connector, connector_request, http)

    assert custom.domains == ["fast"]
    assert default_limiter.domains == []
