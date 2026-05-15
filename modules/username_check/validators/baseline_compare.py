"""Compare candidate response against a negative baseline response."""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from modules.username_check.baseline import BaselineResult
from modules.username_check.validators.base import (
    Signal,
    ValidationContext,
    ValidationOutcome,
)

_COMPARE_CAP = 100_000
_VOLATILE = re.compile(
    r'((?:csrf[_-]?token|nonce|timestamp|build[_-]?id|request[_-]?id|trace[_-]?id)'
    r'\s*[:=]\s*["\']?[A-Za-z0-9._:-]+["\']?|'
    r'data-id="\d+"|/static/[a-f0-9]{8,}|\d{10,})',
    re.I,
)
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class BaselineValidationContext:
    validation: ValidationContext
    baseline: BaselineResult | None


def normalize_body(body: str) -> str:
    capped = body[:_COMPARE_CAP]
    normalized = _VOLATILE.sub("", capped)
    normalized = _WHITESPACE.sub(" ", normalized)
    return normalized.strip().lower()


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_body(left), normalize_body(right)).ratio()


class BaselineCompareValidator:
    name = "baseline_compare"

    def validate(self, ctx: BaselineValidationContext) -> ValidationOutcome:
        baseline = ctx.baseline
        if baseline is None:
            return ValidationOutcome(self.name, [], ["baseline_disabled"])
        if not baseline.ok or baseline.fetch_result is None:
            return ValidationOutcome(
                self.name,
                [],
                [f"baseline_unavailable:{baseline.error or 'unknown'}"],
            )

        current = ctx.validation.fetch_result
        baseline_text = baseline.fetch_result.body.decode("utf-8", errors="replace")
        ratio = similarity(ctx.validation.body_text, baseline_text)
        signals: list[Signal] = []

        if current.status_code == 200 and baseline.fetch_result.status_code == 200 and ratio >= 0.92:
            signals.append(
                Signal(
                    "baseline_indistinguishable",
                    -60,
                    f"{ratio:.2f}",
                    hard_negative=True,
                )
            )
        elif ratio <= 0.50:
            signals.append(Signal("baseline_different", 20, f"{ratio:.2f}"))

        warnings = ["baseline_cache_hit"] if baseline.cache_hit else []
        return ValidationOutcome(self.name, signals, warnings)
