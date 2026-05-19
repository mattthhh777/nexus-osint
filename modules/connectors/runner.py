"""Hardened connector runner.

Applies cache lookup, outbound rate limiting, timeout handling, and hash-only
audit logs around Connector implementations.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from api.cache import cache_backend
from modules.connectors.base import (
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    TargetType,
)
from modules.username_check.rate_limit import OutboundRateLimiter

logger = logging.getLogger("nexusosint.connectors.runner")

_CACHEABLE_STATUSES = {
    ConnectorStatus.FOUND,
    ConnectorStatus.LIKELY,
    ConnectorStatus.NOT_FOUND,
    ConnectorStatus.UNCERTAIN,
}
_CONNECTOR_CACHE_ENDPOINT_PREFIX = "connector"
_HASH_PATTERN = re.compile(r"^[0-9a-f]{12,64}$")
_limiter = OutboundRateLimiter(calls_per_second=2.0)


class Connector(Protocol):
    name: str
    target_types: tuple[TargetType, ...]
    default_timeout_s: int
    rate_limit_cps: float

    async def run(
        self,
        req: ConnectorRequest,
        http: httpx.AsyncClient,
    ) -> ConnectorResult: ...


async def run_connector(
    connector: Connector,
    req: ConnectorRequest,
    http: httpx.AsyncClient,
    *,
    cache_ttl_s: int = 300,
) -> ConnectorResult:
    """Run one connector with cache, rate limit, timeout, and hash-only logs."""
    safe_target_hash = _safe_target_hash(req)
    cache_endpoint, cache_query = _cache_parts(connector, req, safe_target_hash)

    cached = await _get_cached_result(cache_endpoint, cache_query, connector.name)
    if cached is not None:
        cached.cache_hit = True
        logger.info(
            "connector cache hit | connector=%s target_hash=%s status=%s",
            connector.name,
            safe_target_hash,
            cached.status.value,
        )
        return cached

    await _limiter.acquire(connector.name)

    started = time.monotonic()
    timeout_s = _timeout_s(connector, req)
    try:
        result = await asyncio.wait_for(
            connector.run(req, http),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "connector timeout | connector=%s target_hash=%s timeout_s=%s",
            connector.name,
            safe_target_hash,
            timeout_s,
        )
        return _error_result(connector, req, ConnectorStatus.ERROR, "timeout", started)
    except httpx.HTTPStatusError as exc:
        status = (
            ConnectorStatus.BLOCKED
            if exc.response.status_code in {401, 403, 429}
            else ConnectorStatus.ERROR
        )
        logger.warning(
            "connector http status | connector=%s target_hash=%s http_status=%s",
            connector.name,
            safe_target_hash,
            exc.response.status_code,
        )
        return _error_result(
            connector,
            req,
            status,
            f"http_{exc.response.status_code}",
            started,
        )
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        logger.warning(
            "connector network error | connector=%s target_hash=%s type=%s",
            connector.name,
            safe_target_hash,
            type(exc).__name__,
        )
        return _error_result(
            connector,
            req,
            ConnectorStatus.ERROR,
            type(exc).__name__,
            started,
        )

    if result.elapsed_ms == 0:
        result.elapsed_ms = int((time.monotonic() - started) * 1000)

    logger.info(
        "connector complete | connector=%s target_hash=%s status=%s cache_hit=%s elapsed_ms=%s",
        connector.name,
        safe_target_hash,
        result.status.value,
        result.cache_hit,
        result.elapsed_ms,
    )

    if result.status in _CACHEABLE_STATUSES:
        await _set_cached_result(
            cache_endpoint,
            cache_query,
            result,
            cache_ttl_s,
            connector.name,
        )

    return result


def _cache_parts(
    connector: Connector,
    req: ConnectorRequest,
    safe_target_hash: str,
) -> tuple[str, str]:
    endpoint = f"{_CONNECTOR_CACHE_ENDPOINT_PREFIX}:{connector.name}"
    query = f"{req.target_type.value}:{safe_target_hash}"
    return endpoint, query


async def _get_cached_result(
    endpoint: str,
    query: str,
    connector_name: str,
) -> ConnectorResult | None:
    try:
        cached = await cache_backend.get(endpoint, query)
    except (ConnectionError, TimeoutError, OSError, ValueError, TypeError) as exc:
        logger.warning(
            "connector cache get failed open | connector=%s type=%s",
            connector_name,
            type(exc).__name__,
        )
        return None
    if cached is None:
        return None
    try:
        return _result_from_cache(cached)
    except (ValidationError, ValueError, TypeError) as exc:
        logger.warning(
            "connector cache parse failed | connector=%s type=%s",
            connector_name,
            type(exc).__name__,
        )
        return None


async def _set_cached_result(
    endpoint: str,
    query: str,
    result: ConnectorResult,
    cache_ttl_s: int,
    connector_name: str,
) -> None:
    try:
        await cache_backend.set(
            endpoint,
            query,
            result.model_dump(mode="json"),
            ttl=cache_ttl_s,
        )
    except (ConnectionError, TimeoutError, OSError, ValueError, TypeError) as exc:
        logger.warning(
            "connector cache set failed open | connector=%s type=%s",
            connector_name,
            type(exc).__name__,
        )


def _result_from_cache(cached: Any) -> ConnectorResult:
    if isinstance(cached, str):
        return ConnectorResult.model_validate_json(cached)
    if isinstance(cached, dict):
        return ConnectorResult.model_validate(cached)
    raise TypeError("unsupported connector cache payload")


def _timeout_s(connector: Connector, req: ConnectorRequest) -> int:
    timeout = getattr(connector, "default_timeout_s", req.timeout_s)
    try:
        parsed = int(timeout)
    except (TypeError, ValueError):
        parsed = int(req.timeout_s)
    return max(parsed, 1)


def _safe_target_hash(req: ConnectorRequest) -> str:
    candidate = req.target_hash.strip().lower()
    if _HASH_PATTERN.fullmatch(candidate):
        return candidate[:12]
    normalized = req.target_value.strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def _error_result(
    connector: Connector,
    req: ConnectorRequest,
    status: ConnectorStatus,
    reason: str,
    started: float,
) -> ConnectorResult:
    return ConnectorResult(
        connector=connector.name,
        target_type=req.target_type,
        status=status,
        confidence_score=0,
        confidence_level="none",
        evidence=[],
        warnings=[reason],
        fetched_at=datetime.now(timezone.utc),
        cache_hit=False,
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )
