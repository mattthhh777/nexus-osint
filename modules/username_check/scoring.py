"""Validation v2 scoring for username checks."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from modules.username_check.validators.base import Signal, ValidationOutcome

ValidationStatus = Literal[
    "confirmed",
    "likely",
    "uncertain",
    "likely_false_positive",
    "not_found",
    "invalid",
]


@dataclass(frozen=True)
class Evidence:
    signal: str
    weight: int
    detail: str = ""


@dataclass(frozen=True)
class ScoredResult:
    validation_status: ValidationStatus
    confidence_score: int
    confidence_level: str
    evidence: list[Evidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    baseline_used: bool = False


def _flatten(outcomes: list[ValidationOutcome]) -> tuple[list[Signal], list[str], bool]:
    signals: list[Signal] = []
    warnings: list[str] = []
    baseline_used = False
    for outcome in outcomes:
        if outcome.validator == "baseline_compare":
            baseline_used = "baseline_disabled" not in outcome.warnings
        signals.extend(outcome.signals)
        warnings.extend(outcome.warnings)
    return signals, warnings, baseline_used


def combine_outcomes(
    outcomes: list[ValidationOutcome],
    *,
    reliability: str = "normal",
    fetch_error: str | None = None,
) -> ScoredResult:
    if fetch_error:
        return ScoredResult(
            validation_status="invalid",
            confidence_score=0,
            confidence_level="invalid",
            evidence=[Evidence("fetch_error", 0, fetch_error)],
            warnings=[],
            baseline_used=False,
        )

    signals, warnings, baseline_used = _flatten(outcomes)
    evidence = [Evidence(s.name, s.weight, s.detail) for s in signals]
    hard_positive = any(signal.hard_positive for signal in signals)
    hard_negative = any(signal.hard_negative for signal in signals)
    baseline_indistinguishable = any(
        signal.name == "baseline_indistinguishable" for signal in signals
    )
    positive_count = sum(1 for signal in signals if signal.weight > 0)
    raw_score = sum(signal.weight for signal in signals)

    if hard_negative:
        status: ValidationStatus = (
            "likely_false_positive" if baseline_indistinguishable or raw_score > 0 else "not_found"
        )
        score = max(0, min(29, raw_score + 40))
    else:
        score = max(0, min(100, raw_score))
        if reliability == "low" and not hard_positive:
            score = min(score, 84)
        if score >= 85 and (hard_positive or positive_count >= 3):
            status = "confirmed"
        elif score >= 60 and positive_count >= 2:
            status = "likely"
        elif score >= 30 or positive_count >= 1:
            status = "uncertain"
        elif score >= 10:
            status = "likely_false_positive"
        else:
            status = "not_found"

    if not evidence:
        evidence = [Evidence("no_validation_signals", 0, "no_match")]

    return ScoredResult(
        validation_status=status,
        confidence_score=score,
        confidence_level=status,
        evidence=evidence,
        warnings=warnings,
        baseline_used=baseline_used,
    )
