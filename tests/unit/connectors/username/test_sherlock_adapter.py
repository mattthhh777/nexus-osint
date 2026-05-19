"""Unit tests for the R1-4 Sherlock connector adapter."""
from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from modules.connectors.base import ConnectorRequest, ConnectorStatus, TargetType
from modules.connectors.username import sherlock_adapter
from modules.connectors.username.sherlock_adapter import (
    SherlockAdapter,
    map_scored_to_connector_status,
)
from modules.username_check import runner as username_runner
from modules.username_check.runner import PlatformResult, SherlockResult
from modules.username_check.scoring import Evidence as ScoredEvidence
from modules.username_check.scoring import ScoredResult


def _scored(
    validation_status: str,
    *,
    confidence_score: int = 70,
    evidence: list[ScoredEvidence] | None = None,
    warnings: list[str] | None = None,
) -> ScoredResult:
    return ScoredResult(
        validation_status=validation_status,  # type: ignore[arg-type]
        confidence_score=confidence_score,
        confidence_level=validation_status,
        evidence=evidence or [],
        warnings=warnings or [],
    )


def _request() -> ConnectorRequest:
    return ConnectorRequest(
        target_type=TargetType.USERNAME,
        target_value="rawtarget",
        target_hash="abcdef012345",
        timeout_s=7,
        job_id=uuid4(),
    )


@pytest.mark.parametrize(
    ("validation_status", "expected"),
    [
        ("confirmed", ConnectorStatus.FOUND),
        ("likely", ConnectorStatus.LIKELY),
        ("uncertain", ConnectorStatus.UNCERTAIN),
        ("likely_false_positive", ConnectorStatus.NOT_FOUND),
        ("not_found", ConnectorStatus.NOT_FOUND),
    ],
)
def test_map_scored_to_connector_status(
    validation_status: str,
    expected: ConnectorStatus,
) -> None:
    assert map_scored_to_connector_status(_scored(validation_status)) == expected


def test_map_invalid_auth_blocked_warning() -> None:
    scored = _scored("invalid", confidence_score=0, warnings=["login_required"])

    assert map_scored_to_connector_status(scored) == ConnectorStatus.BLOCKED


def test_map_invalid_linkedin_auth_evidence() -> None:
    scored = _scored(
        "invalid",
        confidence_score=0,
        evidence=[ScoredEvidence("linkedin_auth_wall", 0, "blocked")],
    )

    assert map_scored_to_connector_status(scored) == ConnectorStatus.BLOCKED


def test_map_invalid_rate_limit_fetch_error_blocked() -> None:
    scored = _scored(
        "invalid",
        confidence_score=0,
        evidence=[ScoredEvidence("fetch_error", 0, "http_429")],
    )

    assert map_scored_to_connector_status(scored) == ConnectorStatus.BLOCKED


def test_map_invalid_timeout_fetch_error() -> None:
    scored = _scored(
        "invalid",
        confidence_score=0,
        evidence=[ScoredEvidence("fetch_error", 0, "timeout")],
    )

    assert map_scored_to_connector_status(scored) == ConnectorStatus.ERROR


def test_sherlock_adapter_rejects_freeform_platform() -> None:
    with pytest.raises(ValueError):
        SherlockAdapter("johndoe")


def test_legacy_runner_platform_filter_limits_candidates() -> None:
    candidates = [
        {"name": "GitHub"},
        {"name": "Reddit"},
        {"name": "Steam"},
    ]

    assert username_runner._filter_candidate_platforms(candidates, ("GitHub",)) == [
        {"name": "GitHub"}
    ]
    assert username_runner._filter_candidate_platforms(candidates, ("Missing",)) == []


@pytest.mark.asyncio
async def test_sherlock_adapter_calls_legacy_with_single_platform_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []
    platform = PlatformResult(platform="GitHub", url="https://github.com/rawtarget")
    platform._v2_score = _scored(
        "likely",
        confidence_score=72,
        evidence=[ScoredEvidence("profile_marker", 40, "rawtarget marker")],
        warnings=["checked rawtarget"],
    )

    async def fake_legacy_run(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return SherlockResult(success=True, likely=[platform])

    monkeypatch.setattr(sherlock_adapter, "_legacy_run", fake_legacy_run)
    adapter = SherlockAdapter("github")

    async with httpx.AsyncClient() as http:
        result = await adapter.run(_request(), http)

    assert calls == [
        {
            "args": ("rawtarget",),
            "kwargs": {
                "prefer_cli": False,
                "timeout_per": 7,
                "platforms": ("GitHub",),
            },
        }
    ]
    assert result.connector == "sherlock:github"
    assert result.status == ConnectorStatus.LIKELY
    assert result.confidence_score == 72
    assert result.confidence_level == "medium"
    assert result.raw_url is None
    rendered = str(result.model_dump(mode="json"))
    assert "rawtarget" not in rendered
    assert result.data == {"platform": "github"}


@pytest.mark.asyncio
async def test_sherlock_adapter_missing_platform_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_legacy_run(*args, **kwargs):
        return SherlockResult(success=True, not_found=[])

    monkeypatch.setattr(sherlock_adapter, "_legacy_run", fake_legacy_run)
    adapter = SherlockAdapter("sherlock:reddit")

    async with httpx.AsyncClient() as http:
        result = await adapter.run(_request(), http)

    assert result.connector == "sherlock:reddit"
    assert result.status == ConnectorStatus.NOT_FOUND
    assert result.confidence_score == 0
    assert result.warnings == ["no_data_for_platform"]


@pytest.mark.asyncio
async def test_sherlock_adapter_fallback_error_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    platform = PlatformResult(platform="Steam", error="timeout")

    async def fake_legacy_run(*args, **kwargs):
        return SherlockResult(success=True, errors=[platform])

    monkeypatch.setattr(sherlock_adapter, "_legacy_run", fake_legacy_run)
    adapter = SherlockAdapter("steam")

    async with httpx.AsyncClient() as http:
        result = await adapter.run(_request(), http)

    assert result.connector == "sherlock:steam"
    assert result.status == ConnectorStatus.ERROR
    assert result.confidence_score == 0
    assert result.confidence_level == "none"
