"""OathNet connector adapter for R1-5.

Wraps the existing async OathNet client and emits safe ConnectorResult objects
for the approved R1 connectors only: breach, stealer, and victims.
"""
from __future__ import annotations

import re
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

import modules.oathnet_client as oathnet_module
from modules.connectors.base import (
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    Evidence,
    TargetType,
    derive_confidence_level,
)
from modules.oathnet_client import (
    DEFAULT_BREACH_PAGE_SIZE,
    DEFAULT_STEALER_PAGE_SIZE,
    DEFAULT_VICTIMS_FIELDS,
    DEFAULT_VICTIMS_PAGE_SIZE,
    OathnetResult,
)


_BLOCKED_STATUS_CODES = {401, 403, 429}
_DEFERRED_FEATURES = {"ip", "ip_info"}
_HTTP_STATUS_RE = re.compile(r"\bhttp\s*(\d{3})\b|\b(\d{3})\b", re.IGNORECASE)


class OathNetClientLike(Protocol):
    async def search_breach(
        self,
        query: str,
        cursor: str = "",
        session_id: str = "",
        page_size: int = DEFAULT_BREACH_PAGE_SIZE,
    ) -> OathnetResult: ...

    async def search_stealer_v2(
        self,
        query: str,
        cursor: str = "",
        session_id: str = "",
        page_size: int = DEFAULT_STEALER_PAGE_SIZE,
        fields: list[str] | tuple[str, ...] | None = None,
    ) -> OathnetResult: ...

    async def victims_search(
        self,
        query: str = "",
        page_size: int = DEFAULT_VICTIMS_PAGE_SIZE,
        cursor: str = "",
        session_id: str = "",
        fields: list[str] | tuple[str, ...] | None = DEFAULT_VICTIMS_FIELDS,
        **filters: Any,
    ) -> tuple[bool, dict]: ...


@dataclass(frozen=True)
class _FeatureConfig:
    suffix: str
    category: str
    target_types: tuple[TargetType, ...]
    found_score: int
    likely_score: int


_FEATURES: dict[str, _FeatureConfig] = {
    "breach": _FeatureConfig(
        suffix="breach",
        category="breach",
        target_types=(TargetType.EMAIL, TargetType.USERNAME, TargetType.PHONE),
        found_score=90,
        likely_score=0,
    ),
    "stealer": _FeatureConfig(
        suffix="stealer",
        category="stealer",
        target_types=(TargetType.EMAIL, TargetType.USERNAME, TargetType.PHONE),
        found_score=92,
        likely_score=0,
    ),
    "victims": _FeatureConfig(
        suffix="victims",
        category="victims",
        target_types=(TargetType.EMAIL, TargetType.USERNAME),
        found_score=85,
        likely_score=65,
    ),
}


def _normalize_feature(feature: str) -> str:
    candidate = str(feature).strip().casefold()
    if not candidate:
        raise ValueError("unsupported_oathnet_connector")
    parts = candidate.split(":", 1)
    if len(parts) == 2:
        prefix, suffix = parts
        if prefix != "oathnet":
            raise ValueError("unsupported_oathnet_connector")
        candidate = suffix
    if candidate in _DEFERRED_FEATURES:
        raise ValueError("oathnet_ip_deferred")
    if candidate not in _FEATURES:
        raise ValueError("unsupported_oathnet_connector")
    return candidate


def _safe_count(*values: Any) -> int:
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return max(value, 0)
        if isinstance(value, list):
            return len(value)
    return 0


def _http_status_from_error(value: str) -> int | None:
    for match in _HTTP_STATUS_RE.finditer(value):
        raw = match.group(1) or match.group(2)
        if raw is None:
            continue
        try:
            return int(raw)
        except ValueError:
            continue
    return None


def _classify_error(value: str) -> tuple[ConnectorStatus, str]:
    text = str(value or "").casefold()
    status_code = _http_status_from_error(text)
    if status_code in _BLOCKED_STATUS_CODES:
        if status_code == 429:
            return ConnectorStatus.BLOCKED, "rate_limited"
        if status_code == 401:
            return ConnectorStatus.BLOCKED, "auth_blocked"
        return ConnectorStatus.BLOCKED, "access_blocked"
    if any(token in text for token in ("rate limit", "too many requests")):
        return ConnectorStatus.BLOCKED, "rate_limited"
    if any(token in text for token in ("api key", "auth", "forbidden", "quota")):
        return ConnectorStatus.BLOCKED, "auth_blocked"
    if any(token in text for token in ("cloudflare", "challenge", "captcha", "blocked")):
        return ConnectorStatus.BLOCKED, "challenge_blocked"
    if status_code is not None and status_code >= 500:
        return ConnectorStatus.ERROR, "oathnet_server_error"
    if "timeout" in text or "timed out" in text:
        return ConnectorStatus.ERROR, "oathnet_timeout"
    if "network" in text or "connect" in text:
        return ConnectorStatus.ERROR, "oathnet_network_error"
    return ConnectorStatus.ERROR, "oathnet_error"


def _safe_data(category: str, count: int, *, has_more: bool) -> dict[str, Any]:
    labels = [f"record_count:{count}"]
    if has_more:
        labels.append("has_more:true")
    return {
        "source": "oathnet",
        "category": category,
        "labels": labels,
    }


def _count_evidence(signal: str, weight: int, count: int) -> list[Evidence]:
    return [Evidence(signal=signal, weight=weight, detail=f"records_found={count}")]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


class OathNetAdapter:
    """Connector wrapper for one approved OathNet feature."""

    default_timeout_s = 45
    rate_limit_cps = 1.0

    def __init__(
        self,
        feature: str,
        *,
        client: OathNetClientLike | None = None,
    ) -> None:
        self._feature = _normalize_feature(feature)
        self._config = _FEATURES[self._feature]
        self._client = client
        self.name = f"oathnet:{self._feature}"
        self.target_types = self._config.target_types

    async def run(
        self,
        req: ConnectorRequest,
        http: httpx.AsyncClient,
    ) -> ConnectorResult:
        del http
        if req.target_type not in self.target_types:
            raise ValueError("unsupported_target_type")
        started = time.monotonic()
        client = self._client or oathnet_module.oathnet_client
        if client is None:
            return self._failure_result(
                req,
                ConnectorStatus.BLOCKED,
                "auth_blocked",
                started,
            )

        try:
            if self._feature == "breach":
                result = await client.search_breach(
                    req.target_value,
                    page_size=DEFAULT_BREACH_PAGE_SIZE,
                )
                return self._from_oathnet_result(req, result, "breach_records_found", started)
            if self._feature == "stealer":
                result = await client.search_stealer_v2(
                    req.target_value,
                    page_size=DEFAULT_STEALER_PAGE_SIZE,
                )
                return self._from_oathnet_result(req, result, "stealer_records_found", started)
            ok, data = await client.victims_search(
                "",
                DEFAULT_VICTIMS_PAGE_SIZE,
                "",
                "",
                fields=DEFAULT_VICTIMS_FIELDS,
                **self._victims_filters(req),
            )
            return self._from_victims_result(req, ok, data, started)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in _BLOCKED_STATUS_CODES:
                status = ConnectorStatus.BLOCKED
                reason = _classify_error(f"HTTP {exc.response.status_code}")[1]
            else:
                status = ConnectorStatus.ERROR
                reason = "oathnet_server_error" if exc.response.status_code >= 500 else "oathnet_error"
            return self._failure_result(req, status, reason, started)
        except httpx.TimeoutException:
            return self._failure_result(req, ConnectorStatus.ERROR, "oathnet_timeout", started)
        except httpx.NetworkError:
            return self._failure_result(req, ConnectorStatus.ERROR, "oathnet_network_error", started)
        except httpx.HTTPError:
            return self._failure_result(req, ConnectorStatus.ERROR, "oathnet_error", started)
        except (ValueError, KeyError, TypeError, AttributeError, RuntimeError):
            return self._failure_result(req, ConnectorStatus.ERROR, "oathnet_error", started)

    def _from_oathnet_result(
        self,
        req: ConnectorRequest,
        result: OathnetResult,
        signal: str,
        started: float,
    ) -> ConnectorResult:
        if not result.success:
            status, reason = _classify_error(result.error)
            return self._failure_result(req, status, reason, started)

        if self._feature == "breach":
            count = _safe_count(result.results_found, result.breaches)
        else:
            count = _safe_count(result.stealers_found, result.stealers)
        if count > 0:
            status = ConnectorStatus.FOUND
            score = self._config.found_score
            evidence = _count_evidence(signal, 80, count)
        else:
            status = ConnectorStatus.NOT_FOUND
            score = 0
            evidence = _count_evidence(signal, 0, 0)

        return self._result(
            req,
            status=status,
            score=score,
            evidence=evidence,
            warnings=[],
            data=_safe_data(
                self._config.category,
                count,
                has_more=bool(result.next_cursor),
            ),
            started=started,
        )

    def _from_victims_result(
        self,
        req: ConnectorRequest,
        ok: bool,
        data: Mapping[str, Any],
        started: float,
    ) -> ConnectorResult:
        if not ok:
            status, reason = _classify_error(str(data.get("error", "")))
            return self._failure_result(req, status, reason, started)
        items = data.get("items", [])
        meta = data.get("meta", {})
        if not isinstance(items, list):
            items = []
        if not isinstance(meta, Mapping):
            meta = {}
        count = _safe_count(meta.get("total"), items)
        has_more = bool(meta.get("has_more") or data.get("next_cursor"))
        if count <= 0:
            return self._result(
                req,
                status=ConnectorStatus.NOT_FOUND,
                score=0,
                evidence=_count_evidence("victim_records_found", 0, 0),
                warnings=[],
                data=_safe_data(self._config.category, 0, has_more=False),
                started=started,
            )
        if req.target_type == TargetType.EMAIL:
            status = ConnectorStatus.FOUND
            score = self._config.found_score
            weight = 80
        else:
            status = ConnectorStatus.LIKELY
            score = self._config.likely_score
            weight = 55
        return self._result(
            req,
            status=status,
            score=score,
            evidence=_count_evidence("victim_records_found", weight, count),
            warnings=[],
            data=_safe_data(self._config.category, count, has_more=has_more),
            started=started,
        )

    @staticmethod
    def _victims_filters(req: ConnectorRequest) -> dict[str, str]:
        if req.target_type == TargetType.EMAIL:
            return {"email": req.target_value}
        if req.target_type == TargetType.USERNAME:
            return {"username": req.target_value}
        raise ValueError("unsupported_target_type")

    def _failure_result(
        self,
        req: ConnectorRequest,
        status: ConnectorStatus,
        reason: str,
        started: float,
    ) -> ConnectorResult:
        return self._result(
            req,
            status=status,
            score=0,
            evidence=[],
            warnings=[reason],
            data=_safe_data(self._config.category, 0, has_more=False),
            started=started,
        )

    def _result(
        self,
        req: ConnectorRequest,
        *,
        status: ConnectorStatus,
        score: int,
        evidence: list[Evidence],
        warnings: list[str],
        data: dict[str, Any],
        started: float,
    ) -> ConnectorResult:
        safe_score = max(0, min(100, int(score)))
        return ConnectorResult(
            connector=self.name,
            target_type=req.target_type,
            status=status,
            confidence_score=safe_score,
            confidence_level=derive_confidence_level(safe_score),
            evidence=evidence,
            warnings=warnings,
            raw_url=None,
            data=data,
            fetched_at=_now(),
            cache_hit=False,
            elapsed_ms=_elapsed_ms(started),
        )
