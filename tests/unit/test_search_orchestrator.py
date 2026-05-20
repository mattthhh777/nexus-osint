"""Unit tests for the R1-7 search_orchestrator G3 aggregator."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from api.services.search_orchestrator import (
    SINGLE_FOUND_CONFIDENCE_CAP,
    AggregateSummary,
    OrchestratorError,
    aggregate_results,
)
from modules.connectors.base import (
    ConnectorResult,
    ConnectorStatus,
    Evidence,
    TargetType,
    derive_confidence_level,
)


_BASE_TIME = datetime(2026, 5, 20, 0, 0, 0, tzinfo=timezone.utc)


def _result(
    connector: str,
    status: ConnectorStatus,
    *,
    score: int = 0,
    target_type: TargetType = TargetType.USERNAME,
    elapsed_ms: int = 10,
    evidence: list[Evidence] | None = None,
    warnings: list[str] | None = None,
) -> ConnectorResult:
    return ConnectorResult(
        connector=connector,
        target_type=target_type,
        status=status,
        confidence_score=score,
        confidence_level=derive_confidence_level(score),
        evidence=evidence or [],
        warnings=warnings or [],
        raw_url=None,
        data={"target_hash": "0123456789ab"},
        fetched_at=_BASE_TIME,
        cache_hit=False,
        elapsed_ms=elapsed_ms,
    )


class TestG3Quorum:
    def test_three_found_independent_overall_found(self) -> None:
        results = [
            _result("sherlock:github", ConnectorStatus.FOUND, score=90),
            _result("sherlock:reddit", ConnectorStatus.FOUND, score=88),
            _result("oathnet:breach", ConnectorStatus.FOUND, score=92, target_type=TargetType.EMAIL),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.FOUND
        assert summary.overall_confidence == (90 + 88 + 92) // 3
        assert summary.independent_found == 3
        assert summary.found_count == 3

    def test_two_found_plus_not_found_overall_found(self) -> None:
        results = [
            _result("sherlock:github", ConnectorStatus.FOUND, score=88),
            _result("sherlock:reddit", ConnectorStatus.FOUND, score=92),
            _result("oathnet:breach", ConnectorStatus.NOT_FOUND, target_type=TargetType.EMAIL),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.FOUND
        assert summary.overall_confidence == 90
        assert summary.independent_found == 2
        assert summary.not_found_count == 1

    def test_two_found_same_connector_is_not_quorum(self) -> None:
        # Two results from the SAME connector identifier must not satisfy the
        # >=2 INDEPENDENT requirement of G3.
        results = [
            _result("sherlock:github", ConnectorStatus.FOUND, score=85),
            _result("sherlock:github", ConnectorStatus.FOUND, score=90),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.LIKELY
        assert summary.overall_confidence == SINGLE_FOUND_CONFIDENCE_CAP
        assert summary.independent_found == 1

    def test_single_found_demotes_to_likely_with_cap(self) -> None:
        results = [
            _result("sherlock:github", ConnectorStatus.FOUND, score=95),
            _result("sherlock:reddit", ConnectorStatus.LIKELY, score=60),
            _result("sherlock:steam", ConnectorStatus.LIKELY, score=55),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.LIKELY
        # G3 caps single-FOUND at 70 even if connector returned 95.
        assert summary.overall_confidence == SINGLE_FOUND_CONFIDENCE_CAP
        assert summary.found_count == 1
        assert summary.likely_count == 2

    def test_single_found_below_cap_keeps_raw_score(self) -> None:
        results = [
            _result("sherlock:github", ConnectorStatus.FOUND, score=42),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.LIKELY
        assert summary.overall_confidence == 42

    def test_only_likely_returns_likely_with_mean(self) -> None:
        results = [
            _result("sherlock:github", ConnectorStatus.LIKELY, score=50),
            _result("sherlock:reddit", ConnectorStatus.LIKELY, score=70),
            _result("sherlock:steam", ConnectorStatus.LIKELY, score=60),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.LIKELY
        assert summary.overall_confidence == 60

    def test_likely_never_promoted_to_found(self) -> None:
        # Even with five LIKELY at perfect 100 we must remain LIKELY because
        # only FOUND counts for the quorum.
        results = [
            _result("sherlock:github", ConnectorStatus.LIKELY, score=100),
            _result("sherlock:reddit", ConnectorStatus.LIKELY, score=100),
            _result("sherlock:steam", ConnectorStatus.LIKELY, score=100),
            _result("oathnet:victims", ConnectorStatus.LIKELY, score=100),
            _result("carrier_lookup", ConnectorStatus.LIKELY, score=100, target_type=TargetType.PHONE),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.LIKELY
        assert summary.overall_confidence == 100


class TestNegativeAndFailureAggregation:
    def test_all_blocked_returns_blocked(self) -> None:
        results = [
            _result("sherlock:github", ConnectorStatus.BLOCKED, warnings=["cf_challenge"]),
            _result("sherlock:reddit", ConnectorStatus.BLOCKED, warnings=["http_403"]),
            _result("oathnet:breach", ConnectorStatus.BLOCKED, target_type=TargetType.EMAIL, warnings=["rate_limited"]),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.BLOCKED
        assert summary.overall_confidence == 0
        assert summary.blocked_count == 3

    def test_all_error_returns_error(self) -> None:
        results = [
            _result("sherlock:github", ConnectorStatus.ERROR, warnings=["timeout"]),
            _result("oathnet:breach", ConnectorStatus.ERROR, target_type=TargetType.EMAIL, warnings=["oathnet_error"]),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.ERROR
        assert summary.overall_confidence == 0
        assert summary.error_count == 2

    def test_all_not_found_returns_not_found(self) -> None:
        results = [
            _result("sherlock:github", ConnectorStatus.NOT_FOUND),
            _result("sherlock:reddit", ConnectorStatus.NOT_FOUND),
            _result("oathnet:breach", ConnectorStatus.NOT_FOUND, target_type=TargetType.EMAIL),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.NOT_FOUND
        assert summary.overall_confidence == 0
        assert summary.not_found_count == 3

    def test_blocked_never_becomes_not_found(self) -> None:
        # Mixing BLOCKED into an otherwise-NOT_FOUND batch must surface UNCERTAIN,
        # never NOT_FOUND. This guards the "blocked never collapses" invariant.
        results = [
            _result("sherlock:github", ConnectorStatus.NOT_FOUND),
            _result("sherlock:reddit", ConnectorStatus.NOT_FOUND),
            _result("oathnet:breach", ConnectorStatus.BLOCKED, target_type=TargetType.EMAIL),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.UNCERTAIN
        assert summary.blocked_count == 1

    def test_blocked_never_becomes_error(self) -> None:
        # Mixing BLOCKED + ERROR (with no NOT_FOUND) must NOT promote to ERROR.
        # All-ERROR is the only path to ERROR overall, and the BLOCKED row
        # forbids it.
        results = [
            _result("sherlock:github", ConnectorStatus.BLOCKED, warnings=["cf_challenge"]),
            _result("sherlock:reddit", ConnectorStatus.ERROR, warnings=["timeout"]),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.UNCERTAIN
        assert summary.blocked_count == 1
        assert summary.error_count == 1

    def test_not_found_plus_error_returns_uncertain(self) -> None:
        results = [
            _result("sherlock:github", ConnectorStatus.NOT_FOUND),
            _result("oathnet:breach", ConnectorStatus.ERROR, target_type=TargetType.EMAIL, warnings=["timeout"]),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.UNCERTAIN

    def test_uncertain_only_returns_uncertain(self) -> None:
        results = [
            _result("carrier_lookup", ConnectorStatus.UNCERTAIN, target_type=TargetType.PHONE),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.UNCERTAIN

    def test_uncertain_does_not_unlock_blocked_branch(self) -> None:
        # BLOCKED + UNCERTAIN: BLOCKED is not the totality, NOT_FOUND absent,
        # so we fall through to the generic UNCERTAIN branch — never BLOCKED.
        results = [
            _result("sherlock:github", ConnectorStatus.BLOCKED, warnings=["http_429"]),
            _result("carrier_lookup", ConnectorStatus.UNCERTAIN, target_type=TargetType.PHONE),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.UNCERTAIN
        assert summary.blocked_count == 1
        assert summary.uncertain_count == 1


class TestEdgeCases:
    def test_empty_results_returns_empty_uncertain(self) -> None:
        summary = aggregate_results([])
        assert isinstance(summary, AggregateSummary)
        assert summary.overall_status is ConnectorStatus.UNCERTAIN
        assert summary.overall_confidence == 0
        assert summary.connectors_run == ()
        assert summary.found_count == 0
        assert summary.agreement_ratio == 0.0

    def test_unknown_connector_raises(self) -> None:
        results = [
            _result("rogue:scanner", ConnectorStatus.FOUND, score=99),
            _result("sherlock:github", ConnectorStatus.FOUND, score=85),
        ]
        with pytest.raises(OrchestratorError) as exc:
            aggregate_results(results)
        assert "unknown_connector" in str(exc.value)

    def test_connectors_run_deduplicated_in_order(self) -> None:
        results = [
            _result("sherlock:github", ConnectorStatus.FOUND, score=80),
            _result("sherlock:reddit", ConnectorStatus.NOT_FOUND),
            _result("sherlock:github", ConnectorStatus.LIKELY, score=40),
            _result("oathnet:breach", ConnectorStatus.NOT_FOUND, target_type=TargetType.EMAIL),
        ]
        summary = aggregate_results(results)
        assert summary.connectors_run == (
            "sherlock:github",
            "sherlock:reddit",
            "oathnet:breach",
        )

    def test_confidence_score_clamped_within_bounds(self) -> None:
        # Even pathological inputs at the contract boundary must keep the
        # overall confidence inside [0, 100].
        results = [
            _result("sherlock:github", ConnectorStatus.FOUND, score=100),
            _result("sherlock:reddit", ConnectorStatus.FOUND, score=100),
        ]
        summary = aggregate_results(results)
        assert 0 <= summary.overall_confidence <= 100
        assert summary.overall_confidence == 100
        assert summary.overall_confidence_level == "high"

    def test_pending_and_running_counted_but_do_not_drive_overall(self) -> None:
        results = [
            _result("sherlock:github", ConnectorStatus.PENDING),
            _result("sherlock:reddit", ConnectorStatus.RUNNING),
        ]
        summary = aggregate_results(results)
        assert summary.pending_count == 1
        assert summary.running_count == 1
        # No decisive states -> UNCERTAIN fallback.
        assert summary.overall_status is ConnectorStatus.UNCERTAIN
        assert summary.overall_confidence == 0

    def test_pending_alongside_quorum_still_yields_found(self) -> None:
        results = [
            _result("sherlock:github", ConnectorStatus.FOUND, score=90),
            _result("sherlock:reddit", ConnectorStatus.FOUND, score=80),
            _result("sherlock:steam", ConnectorStatus.PENDING),
        ]
        summary = aggregate_results(results)
        assert summary.overall_status is ConnectorStatus.FOUND
        assert summary.pending_count == 1
        assert summary.found_count == 2

    def test_agreement_ratio_excludes_failures(self) -> None:
        # decisive = found + likely + not_found + uncertain (== 3)
        # positive = found + likely (== 2)
        # agreement_ratio = 2/3 ~ 0.6667
        results = [
            _result("sherlock:github", ConnectorStatus.FOUND, score=80),
            _result("sherlock:reddit", ConnectorStatus.LIKELY, score=55),
            _result("oathnet:breach", ConnectorStatus.NOT_FOUND, target_type=TargetType.EMAIL),
            _result("oathnet:stealer", ConnectorStatus.BLOCKED, target_type=TargetType.EMAIL),
        ]
        summary = aggregate_results(results)
        assert summary.agreement_ratio == pytest.approx(2 / 3, abs=1e-4)


def test_summary_is_immutable_dataclass() -> None:
    summary = aggregate_results([])
    with pytest.raises(Exception):
        summary.overall_status = ConnectorStatus.FOUND  # type: ignore[misc]


def test_aggregator_is_pure_independent_of_uuid_provenance() -> None:
    # Sanity smoke: the aggregator is pure; downstream job_id provenance does
    # not affect the summary computation.
    _ = uuid4()
    summary = aggregate_results([_result("sherlock:github", ConnectorStatus.FOUND, score=90)])
    assert summary.overall_status is ConnectorStatus.LIKELY
