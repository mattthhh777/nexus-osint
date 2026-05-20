"""Search orchestrator — R1-7 G3 aggregation.

Pure aggregation of `ConnectorResult` lists into an overall job summary applying
the G3 quorum rule:

- ``>=2`` independent connectors returning ``FOUND`` -> overall ``FOUND``.
- A single ``FOUND`` -> overall ``LIKELY`` with confidence capped at 70.
- ``LIKELY`` only -> overall ``LIKELY``.
- All ``BLOCKED`` -> overall ``BLOCKED``.
- All ``ERROR`` -> overall ``ERROR``.
- All ``NOT_FOUND`` -> overall ``NOT_FOUND``.
- ``NOT_FOUND`` mixed with ``BLOCKED``/``ERROR`` -> overall ``UNCERTAIN``.

Hard invariants enforced here:

- ``LIKELY`` never gets promoted to ``FOUND`` outside the quorum rule.
- ``BLOCKED`` never collapses to ``NOT_FOUND`` or ``ERROR``.
- Connector identities are validated against the closed registry shared with
  ``api.services.job_store`` to prevent rogue identifiers from poisoning quorum
  arithmetic.

The orchestrator does not perform I/O. R1-7 stops short of API/SSE wiring; the
HTTP surface and `search_v2` route arrive in R1-8.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from api.services.job_store import ALLOWED_CONNECTOR_IDS
from modules.connectors.base import (
    ConfidenceLevel,
    ConnectorResult,
    ConnectorStatus,
    derive_confidence_level,
)


SINGLE_FOUND_CONFIDENCE_CAP = 70


class OrchestratorError(ValueError):
    """Raised when aggregator input violates orchestration invariants."""


@dataclass(frozen=True)
class AggregateSummary:
    """Hash-safe summary of a multi-connector search run."""

    overall_status: ConnectorStatus
    overall_confidence: int
    overall_confidence_level: ConfidenceLevel
    found_count: int
    likely_count: int
    not_found_count: int
    uncertain_count: int
    blocked_count: int
    error_count: int
    pending_count: int
    running_count: int
    independent_found: int
    agreement_ratio: float
    connectors_run: tuple[str, ...] = field(default_factory=tuple)


def _validate_registry(results: Sequence[ConnectorResult]) -> None:
    for item in results:
        if item.connector not in ALLOWED_CONNECTOR_IDS:
            raise OrchestratorError(f"unknown_connector:{item.connector}")


def _filter_status(
    results: Iterable[ConnectorResult],
    status: ConnectorStatus,
) -> list[ConnectorResult]:
    return [item for item in results if item.status is status]


def _bounded_mean(scores: Iterable[int]) -> int:
    values = [max(0, min(100, int(score))) for score in scores]
    if not values:
        return 0
    return max(0, min(100, sum(values) // len(values)))


def _empty_summary() -> AggregateSummary:
    return AggregateSummary(
        overall_status=ConnectorStatus.UNCERTAIN,
        overall_confidence=0,
        overall_confidence_level=derive_confidence_level(0),
        found_count=0,
        likely_count=0,
        not_found_count=0,
        uncertain_count=0,
        blocked_count=0,
        error_count=0,
        pending_count=0,
        running_count=0,
        independent_found=0,
        agreement_ratio=0.0,
        connectors_run=(),
    )


def aggregate_results(results: Sequence[ConnectorResult]) -> AggregateSummary:
    """Aggregate connector results into a single G3-compliant summary.

    Args:
        results: Connector outputs already validated against the canonical
            8-state schema. Must reference connector identifiers present in the
            closed connector registry. Callers should not pass results for
            connectors that have not finished (``pending``/``running``); those
            states are tolerated and counted but never promote overall status.

    Returns:
        ``AggregateSummary`` with overall status, bounded confidence (0-100),
        per-status counters, and the list of distinct connector identifiers
        that produced this batch.

    Raises:
        OrchestratorError: when a result references a connector identifier not
            registered in ``ALLOWED_CONNECTOR_IDS``.
    """
    if not results:
        return _empty_summary()

    _validate_registry(results)

    found = _filter_status(results, ConnectorStatus.FOUND)
    likely = _filter_status(results, ConnectorStatus.LIKELY)
    not_found = _filter_status(results, ConnectorStatus.NOT_FOUND)
    uncertain = _filter_status(results, ConnectorStatus.UNCERTAIN)
    blocked = _filter_status(results, ConnectorStatus.BLOCKED)
    error = _filter_status(results, ConnectorStatus.ERROR)
    pending = _filter_status(results, ConnectorStatus.PENDING)
    running = _filter_status(results, ConnectorStatus.RUNNING)

    independent_found = {item.connector for item in found}
    total = len(results)
    total_decisive = len(found) + len(likely) + len(not_found) + len(uncertain)

    if len(independent_found) >= 2:
        overall = ConnectorStatus.FOUND
        confidence = _bounded_mean(item.confidence_score for item in found)
    elif found:
        overall = ConnectorStatus.LIKELY
        raw_score = max(item.confidence_score for item in found)
        confidence = min(max(0, int(raw_score)), SINGLE_FOUND_CONFIDENCE_CAP)
    elif likely:
        overall = ConnectorStatus.LIKELY
        confidence = _bounded_mean(item.confidence_score for item in likely)
    elif not_found and (blocked or error):
        overall = ConnectorStatus.UNCERTAIN
        confidence = 0
    elif blocked and len(blocked) == total:
        overall = ConnectorStatus.BLOCKED
        confidence = 0
    elif error and len(error) == total:
        overall = ConnectorStatus.ERROR
        confidence = 0
    elif not_found and len(not_found) == total:
        overall = ConnectorStatus.NOT_FOUND
        confidence = 0
    else:
        overall = ConnectorStatus.UNCERTAIN
        confidence = 0

    agreement_ratio = (
        (len(found) + len(likely)) / total_decisive if total_decisive else 0.0
    )

    seen: list[str] = []
    seen_set: set[str] = set()
    for item in results:
        if item.connector in seen_set:
            continue
        seen.append(item.connector)
        seen_set.add(item.connector)

    return AggregateSummary(
        overall_status=overall,
        overall_confidence=confidence,
        overall_confidence_level=derive_confidence_level(confidence),
        found_count=len(found),
        likely_count=len(likely),
        not_found_count=len(not_found),
        uncertain_count=len(uncertain),
        blocked_count=len(blocked),
        error_count=len(error),
        pending_count=len(pending),
        running_count=len(running),
        independent_found=len(independent_found),
        agreement_ratio=round(agreement_ratio, 4),
        connectors_run=tuple(seen),
    )


__all__ = [
    "AggregateSummary",
    "OrchestratorError",
    "SINGLE_FOUND_CONFIDENCE_CAP",
    "aggregate_results",
]
