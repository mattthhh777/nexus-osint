"""Tests for ConnectorResult schema and derive_confidence_level."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from modules.connectors.base import (
    ConfidenceLevel,
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    Evidence,
    TargetType,
    derive_confidence_level,
)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100, "high"),
        (85, "high"),
        (84, "medium"),
        (60, "medium"),
        (59, "low"),
        (30, "low"),
        (29, "none"),
        (0, "none"),
    ],
)
def test_derive_confidence_level(score: int, expected: ConfidenceLevel) -> None:
    assert derive_confidence_level(score) == expected


def test_connector_status_has_eight_states() -> None:
    expected = {
        "pending", "running", "found", "not_found",
        "likely", "uncertain", "blocked", "error",
    }
    assert {s.value for s in ConnectorStatus} == expected


def test_likely_is_distinct_from_found() -> None:
    assert ConnectorStatus.LIKELY != ConnectorStatus.FOUND
    assert ConnectorStatus.LIKELY.value == "likely"


def test_blocked_is_distinct_from_error_and_not_found() -> None:
    assert ConnectorStatus.BLOCKED != ConnectorStatus.ERROR
    assert ConnectorStatus.BLOCKED != ConnectorStatus.NOT_FOUND


def test_connector_result_valid_construction() -> None:
    result = ConnectorResult(
        connector="sherlock:github",
        target_type=TargetType.USERNAME,
        status=ConnectorStatus.FOUND,
        confidence_score=92,
        confidence_level="high",
        evidence=[Evidence(signal="profile_match", weight=80, detail="200 OK")],
        fetched_at=datetime.now(timezone.utc),
        elapsed_ms=345,
    )
    assert result.connector == "sherlock:github"
    assert result.confidence_score == 92


def test_connector_request_requires_job_id() -> None:
    req = ConnectorRequest(
        target_type=TargetType.PHONE,
        target_value="+5511999999999",
        target_hash="a1b2c3d4e5f6",
        job_id=uuid4(),
    )
    assert req.timeout_s == 15  # default


def test_evidence_weight_bounds() -> None:
    with pytest.raises(ValueError):
        Evidence(signal="bad", weight=150)
    with pytest.raises(ValueError):
        Evidence(signal="bad", weight=-200)


def test_confidence_score_bounds() -> None:
    with pytest.raises(ValueError):
        ConnectorResult(
            connector="x",
            target_type=TargetType.USERNAME,
            status=ConnectorStatus.FOUND,
            confidence_score=150,
            confidence_level="high",
            fetched_at=datetime.now(timezone.utc),
            elapsed_ms=0,
        )
