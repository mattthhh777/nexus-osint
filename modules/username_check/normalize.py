"""Normalize internal username check results into v2 API shape."""
from __future__ import annotations

from datetime import datetime, timezone

from modules.username_check.runner import PlatformResult
from modules.username_check.scoring import ScoredResult


def _fetch_status(result: PlatformResult) -> str:
    if result.error in {"timeout", "connection_error", "proxy_unavailable", "cf_challenge"}:
        return result.error
    if result.error:
        return "http_error" if result.error.startswith("http_") else "invalid"
    return "ok"


def normalize_platform(
    username: str,
    platform: PlatformResult,
    scored: ScoredResult,
) -> dict:
    fetch_result = platform._fetch_result
    return {
        "source": "sherlock",
        "username": username,
        "platform": platform.platform,
        "category": platform.category,
        "icon": platform.icon,
        "url_original": platform.url,
        "url_final": fetch_result.final_url if fetch_result else platform.url,
        "redirect_chain": fetch_result.redirect_chain if fetch_result else [],
        "http_status": fetch_result.status_code if fetch_result else None,
        "fetch_status": _fetch_status(platform),
        "validation_status": scored.validation_status,
        "confidence_score": scored.confidence_score,
        "confidence_level": scored.confidence_level,
        "evidence": [
            {"signal": item.signal, "weight": item.weight, "detail": item.detail}
            for item in scored.evidence
        ],
        "warnings": scored.warnings,
        "error": platform.error,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "reliability": platform.reliability,
        "baseline_used": scored.baseline_used,
    }


def normalize_result(username: str, result) -> dict:
    platforms: list[dict] = []
    for platform in result.found + result.likely + result.not_found + result.errors:
        scored = platform._v2_score
        if scored is not None:
            platforms.append(normalize_platform(username, platform, scored))
    found_count = sum(1 for item in platforms if item["validation_status"] == "confirmed")
    likely_count = sum(1 for item in platforms if item["validation_status"] == "likely")
    return {
        "username": username,
        "found_count": found_count,
        "likely_count": likely_count,
        "total_checked": result.total_checked,
        "source": result.source,
        "proxy_used": result.proxy_used,
        "platforms": platforms,
    }
