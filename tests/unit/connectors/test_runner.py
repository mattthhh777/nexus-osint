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
    TargetType,
)


class FakeCache:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str], Any] = {}

    async def get(self, endpoint: str, query: str) -> Any | None:
        return self.items.get((endpoint, query))

    async def set(
        self,
        endpoint: str,
        query: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        self.items[(endpoint, query)] = value


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


@pytest.fixture(autouse=True)
def fake_runner_dependencies(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeCache, FakeLimiter]:
    cache = FakeCache()
    limiter = FakeLimiter()
    monkeypatch.setattr(runner, "cache_backend", cache)
    monkeypatch.setattr(runner, "_limiter", limiter)
    return cache, limiter


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
    assert connector_request.target_value not in str(list(cache.items))


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
