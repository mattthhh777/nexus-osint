"""Adapter from legacy Sherlock username scoring to ConnectorResult.

R1-4 scope only. This module does not persist jobs/events and does not create
new probes; it wraps the existing username runner with a single-platform filter.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Iterable

import httpx

from modules.connectors.base import (
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    Evidence as ConnectorEvidence,
    TargetType,
    derive_confidence_level,
)
from modules.username_check.runner import (
    PlatformResult,
    SherlockResult,
    search_username as _legacy_run,
)
from modules.username_check.scoring import Evidence as ScoredEvidence
from modules.username_check.scoring import ScoredResult


SUPPORTED_SHERLOCK_PLATFORMS: dict[str, str] = {
    "github": "GitHub",
    "reddit": "Reddit",
    "steam": "Steam",
}
_STATUS_MAP: dict[str, ConnectorStatus] = {
    "confirmed": ConnectorStatus.FOUND,
    "likely": ConnectorStatus.LIKELY,
    "uncertain": ConnectorStatus.UNCERTAIN,
    "likely_false_positive": ConnectorStatus.NOT_FOUND,
    "not_found": ConnectorStatus.NOT_FOUND,
}
_BLOCKED_WARNINGS = {
    "bot_check",
    "login_required",
    "redirect_to_login",
    "cf_challenge",
}
_BLOCKED_FETCH_ERRORS = {
    "cf_challenge",
    "http_401",
    "http_403",
    "http_429",
    "login_required",
    "redirect_to_login",
}
_REDACTED = "[redacted]"


def _normalize_platform(platform: str) -> str:
    candidate = str(platform).strip().casefold()
    parts = candidate.split(":", 1)
    if len(parts) == 2:
        prefix, suffix = parts
        if prefix != "sherlock":
            raise ValueError("unsupported_sherlock_platform")
        candidate = suffix
    if candidate not in SUPPORTED_SHERLOCK_PLATFORMS:
        raise ValueError("unsupported_sherlock_platform")
    return candidate


def _safe_text(value: str, target_value: str) -> str:
    if not value:
        return value
    target = target_value.strip()
    if not target:
        return value
    return re.sub(re.escape(target), _REDACTED, value, flags=re.IGNORECASE)


def _map_invalid(scored: ScoredResult) -> ConnectorStatus:
    warnings = {str(warning).casefold() for warning in scored.warnings}
    if warnings & _BLOCKED_WARNINGS:
        return ConnectorStatus.BLOCKED
    for item in scored.evidence:
        signal = str(item.signal).casefold()
        detail = str(item.detail).casefold()
        if signal.startswith("linkedin_auth"):
            return ConnectorStatus.BLOCKED
        if signal == "fetch_error" and detail in _BLOCKED_FETCH_ERRORS:
            return ConnectorStatus.BLOCKED
    return ConnectorStatus.ERROR


def map_scored_to_connector_status(scored: ScoredResult) -> ConnectorStatus:
    """Map legacy 6-state Sherlock scoring into the canonical 8-state enum."""
    if scored.validation_status == "invalid":
        return _map_invalid(scored)
    return _STATUS_MAP.get(scored.validation_status, ConnectorStatus.UNCERTAIN)


def _iter_platform_results(result: SherlockResult) -> Iterable[PlatformResult]:
    yield from result.found
    yield from result.likely
    yield from result.not_found
    yield from result.errors


def _find_platform_result(
    result: SherlockResult,
    platform_display: str,
) -> PlatformResult | None:
    expected = platform_display.casefold()
    for item in _iter_platform_results(result):
        if str(item.platform).casefold() == expected:
            return item
    return None


def _fallback_score(platform: PlatformResult) -> ScoredResult:
    if platform.error:
        return ScoredResult(
            validation_status="invalid",
            confidence_score=0,
            confidence_level="invalid",
            evidence=[ScoredEvidence(signal="fetch_error", weight=0, detail=platform.error)],
            warnings=[],
        )
    return ScoredResult(
        validation_status="not_found",
        confidence_score=0,
        confidence_level="not_found",
        evidence=[],
        warnings=["missing_v2_score"],
    )


def _evidence_from_score(scored: ScoredResult, target_value: str) -> list[ConnectorEvidence]:
    return [
        ConnectorEvidence(
            signal=_safe_text(str(item.signal), target_value),
            weight=item.weight,
            detail=_safe_text(str(item.detail or ""), target_value),
        )
        for item in scored.evidence
    ]


class SherlockAdapter:
    """Connector wrapper for one approved Sherlock platform."""

    target_types = (TargetType.USERNAME,)
    default_timeout_s = 30
    rate_limit_cps = 2.0

    def __init__(self, platform: str) -> None:
        self._platform = _normalize_platform(platform)
        self._platform_display = SUPPORTED_SHERLOCK_PLATFORMS[self._platform]
        self.name = f"sherlock:{self._platform}"

    async def run(
        self,
        req: ConnectorRequest,
        http: httpx.AsyncClient,
    ) -> ConnectorResult:
        del http
        started = time.monotonic()
        raw_results = await _legacy_run(
            req.target_value,
            prefer_cli=False,
            timeout_per=req.timeout_s,
            platforms=(self._platform_display,),
        )
        platform_data = _find_platform_result(raw_results, self._platform_display)
        if platform_data is None:
            return ConnectorResult(
                connector=self.name,
                target_type=TargetType.USERNAME,
                status=ConnectorStatus.NOT_FOUND,
                confidence_score=0,
                confidence_level="none",
                evidence=[],
                warnings=["no_data_for_platform"],
                data={"platform": self._platform},
                fetched_at=datetime.now(timezone.utc),
                cache_hit=False,
                elapsed_ms=int((time.monotonic() - started) * 1000),
            )

        scored = platform_data._v2_score or _fallback_score(platform_data)
        status = map_scored_to_connector_status(scored)
        score = max(0, min(100, int(scored.confidence_score)))
        return ConnectorResult(
            connector=self.name,
            target_type=TargetType.USERNAME,
            status=status,
            confidence_score=score,
            confidence_level=derive_confidence_level(score),
            evidence=_evidence_from_score(scored, req.target_value),
            warnings=[
                _safe_text(str(warning), req.target_value)
                for warning in scored.warnings
            ],
            raw_url=None,
            data={"platform": self._platform},
            fetched_at=datetime.now(timezone.utc),
            cache_hit=False,
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )
