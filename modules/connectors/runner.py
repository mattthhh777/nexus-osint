"""Hardened connector runner.

Applies cache lookup, outbound rate limiting, timeout handling, and hash-only
audit logs around Connector implementations.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
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

_REDACTED = "[redacted]"
_CACHE_SCHEMA_VERSION = 1
_CACHEABLE_STATUSES = {
    ConnectorStatus.FOUND,
    ConnectorStatus.LIKELY,
    ConnectorStatus.NOT_FOUND,
    ConnectorStatus.UNCERTAIN,
}
_CONNECTOR_CACHE_ENDPOINT_PREFIX = "connector"
_HASH_PATTERN = re.compile(r"^[0-9a-f]{12,64}$")
_EMAIL_PATTERN = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+", re.I)
_PHONE_PATTERN = re.compile(r"\+?\d[\d\s().\-]{6,}\d")
_URL_PATTERN = re.compile(r"https?://\S+", re.I)
_CPF_PATTERN = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
_SENSITIVE_KEYS = {
    "email",
    "phone",
    "query",
    "raw",
    "raw_query",
    "raw_response",
    "raw_target",
    "target",
    "target_value",
}
_SAFE_DATA_KEYS = {
    "category",
    "labels",
    "platform",
    "source",
    "tags",
}
_limiter = OutboundRateLimiter(calls_per_second=2.0)
_limiters_by_cps: dict[float, OutboundRateLimiter] = {}


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

    cached = await _get_cached_result(
        cache_endpoint,
        cache_query,
        connector.name,
        safe_target_hash,
    )
    if cached is not None:
        cached.cache_hit = True
        logger.info(
            "connector cache hit | connector=%s target_hash=%s status=%s",
            connector.name,
            safe_target_hash,
            cached.status.value,
        )
        return cached

    await _limiter_for(connector).acquire(connector.name)

    started = time.monotonic()
    timeout_s = _timeout_s(connector, req)
    try:
        raw_result = await asyncio.wait_for(
            connector.run(req, http),
            timeout=timeout_s,
        )
        result = ConnectorResult.model_validate(raw_result)
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
    except httpx.HTTPError as exc:
        logger.warning(
            "connector http error | connector=%s target_hash=%s type=%s",
            connector.name,
            safe_target_hash,
            type(exc).__name__,
        )
        return _error_result(
            connector,
            req,
            ConnectorStatus.ERROR,
            "connector_http_error",
            started,
        )
    except (
        ValidationError,
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
    ) as exc:
        logger.warning(
            "connector execution error | connector=%s target_hash=%s type=%s",
            connector.name,
            safe_target_hash,
            type(exc).__name__,
        )
        return _error_result(
            connector,
            req,
            ConnectorStatus.ERROR,
            "connector_error",
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
        sanitized_payload = _sanitize_result_for_cache(
            result,
            safe_target_hash,
            req.target_value,
        )
        envelope = _wrap_cache_envelope(sanitized_payload)
        await _set_cached_result(
            cache_endpoint,
            cache_query,
            envelope,
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
    safe_target_hash: str,
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
        return _result_from_cache(cached, safe_target_hash)
    except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.warning(
            "connector cache parse failed | connector=%s type=%s",
            connector_name,
            type(exc).__name__,
        )
        return None


async def _set_cached_result(
    endpoint: str,
    query: str,
    result: dict[str, Any],
    cache_ttl_s: int,
    connector_name: str,
) -> None:
    try:
        await cache_backend.set(
            endpoint,
            query,
            result,
            ttl=cache_ttl_s,
        )
    except (ConnectionError, TimeoutError, OSError, ValueError, TypeError) as exc:
        logger.warning(
            "connector cache set failed open | connector=%s type=%s",
            connector_name,
            type(exc).__name__,
        )


def _wrap_cache_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": _CACHE_SCHEMA_VERSION,
        "sanitized": True,
        "payload": payload,
    }


def _result_from_cache(cached: Any, safe_target_hash: str) -> ConnectorResult:
    if isinstance(cached, str):
        cached = json.loads(cached)
    if not isinstance(cached, dict):
        raise TypeError("unsupported connector cache payload")
    if cached.get("schema_version") != _CACHE_SCHEMA_VERSION:
        raise ValueError("legacy connector cache payload rejected")
    if not cached.get("sanitized"):
        raise ValueError("unsanitized connector cache payload rejected")
    payload = cached.get("payload")
    if not isinstance(payload, dict):
        raise TypeError("missing connector cache payload")
    resanitized = _resanitize_cached_payload(payload, safe_target_hash)
    return ConnectorResult.model_validate(resanitized)


def _resanitize_cached_payload(
    payload: dict[str, Any],
    safe_target_hash: str,
) -> dict[str, Any]:
    sanitized = dict(payload)
    sanitized["raw_url"] = _sanitize_url(payload.get("raw_url"), "")
    sanitized["warnings"] = [
        _sanitize_text(str(warning), "")
        for warning in (payload.get("warnings") or [])
    ]
    sanitized["evidence"] = [
        _sanitize_evidence(item, "")
        for item in (payload.get("evidence") or [])
        if isinstance(item, dict)
    ]
    sanitized["data"] = _sanitize_data(payload.get("data"), safe_target_hash, "")
    sanitized["cache_hit"] = False
    return sanitized


def _timeout_s(connector: Connector, req: ConnectorRequest) -> int:
    timeout = getattr(connector, "default_timeout_s", req.timeout_s)
    try:
        parsed = int(timeout)
    except (TypeError, ValueError):
        parsed = int(req.timeout_s)
    return max(parsed, 1)


def _limiter_for(connector: Connector) -> OutboundRateLimiter:
    cps = _connector_rate_limit_cps(connector)
    if cps == 2.0:
        return _limiter
    limiter = _limiters_by_cps.get(cps)
    if limiter is None:
        limiter = OutboundRateLimiter(calls_per_second=cps)
        _limiters_by_cps[cps] = limiter
    return limiter


def _connector_rate_limit_cps(connector: Connector) -> float:
    try:
        cps = float(getattr(connector, "rate_limit_cps", 2.0))
    except (TypeError, ValueError):
        return 2.0
    if cps <= 0:
        return 2.0
    return cps


def _safe_target_hash(req: ConnectorRequest) -> str:
    candidate = req.target_hash.strip().lower()
    if _HASH_PATTERN.fullmatch(candidate):
        return candidate[:12]
    normalized = req.target_value.strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def _sanitize_result_for_cache(
    result: ConnectorResult,
    safe_target_hash: str,
    target_value: str,
) -> dict[str, Any]:
    payload = result.model_dump(mode="json")
    payload["connector"] = _sanitize_text(str(payload.get("connector") or ""), target_value)
    payload["cache_hit"] = False
    payload["raw_url"] = _sanitize_url(payload.get("raw_url"), target_value)
    payload["warnings"] = [
        _sanitize_text(str(warning), target_value)
        for warning in (payload.get("warnings") or [])
    ]
    payload["evidence"] = [
        _sanitize_evidence(item, target_value)
        for item in (payload.get("evidence") or [])
        if isinstance(item, dict)
    ]
    payload["data"] = _sanitize_data(payload.get("data"), safe_target_hash, target_value)
    return payload


def _sanitize_evidence(item: dict[str, Any], target_value: str) -> dict[str, Any]:
    return {
        "signal": _sanitize_text(str(item.get("signal") or ""), target_value),
        "weight": item.get("weight", 0),
        "detail": _sanitize_text(str(item.get("detail") or ""), target_value),
    }


def _sanitize_data(
    value: Any,
    safe_target_hash: str,
    target_value: str,
) -> dict[str, Any]:
    sanitized: dict[str, Any] = {"target_hash": safe_target_hash}
    if not isinstance(value, dict):
        return sanitized
    for key, item in value.items():
        normalized_key = str(key).lower()
        # Canonical target_hash is set by the runner. A connector or cached
        # payload MUST NOT override it.
        if normalized_key == "target_hash":
            continue
        if normalized_key in _SENSITIVE_KEYS:
            continue
        if normalized_key not in _SAFE_DATA_KEYS:
            continue
        sanitized[str(key)] = _sanitize_safe_value(item, target_value)
    return sanitized


def _sanitize_safe_value(value: Any, target_value: str) -> Any:
    if isinstance(value, str):
        return _sanitize_text(value, target_value)
    if isinstance(value, list):
        return [_sanitize_safe_value(item, target_value) for item in value[:25]]
    if isinstance(value, tuple):
        return [_sanitize_safe_value(item, target_value) for item in value[:25]]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return _REDACTED


def _sanitize_url(value: Any, target_value: str) -> str | None:
    if value is None:
        return None
    text = str(value)
    if _contains_sensitive_text(text, target_value):
        return None
    return text


def _sanitize_text(value: str, target_value: str) -> str:
    if not value:
        return value
    redacted = value
    raw_target = target_value.strip()
    if raw_target:
        redacted = re.sub(re.escape(raw_target), _REDACTED, redacted, flags=re.I)
    redacted = _EMAIL_PATTERN.sub(_REDACTED, redacted)
    redacted = _CPF_PATTERN.sub(_REDACTED, redacted)
    redacted = _PHONE_PATTERN.sub(_REDACTED, redacted)
    redacted = _URL_PATTERN.sub(_REDACTED, redacted)
    return redacted


def _contains_sensitive_text(value: str, target_value: str) -> bool:
    raw_target = target_value.strip()
    if raw_target and raw_target.casefold() in value.casefold():
        return True
    return any(
        pattern.search(value)
        for pattern in (_EMAIL_PATTERN, _CPF_PATTERN, _PHONE_PATTERN, _URL_PATTERN)
    )


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
