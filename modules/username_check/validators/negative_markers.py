"""Negative marker validation for username profile responses."""
from __future__ import annotations

import re

from modules.username_check.validators.base import (
    Signal,
    ValidationContext,
    ValidationOutcome,
)

_COMMON_NEGATIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(user|account|profile)\s+(not\s+found|does\s+not\s+exist|unavailable)\b", re.I),
    re.compile(r"\b(page\s+not\s+found|404)\b", re.I),
    re.compile(r"\b(no\s+such\s+user|could(?:n['’]t| not)\s+find)\b", re.I),
    re.compile(r"\b(usuario|usu[aá]rio|conta)\s+n[aã]o\s+encontrad[oa]\b", re.I),
    re.compile(r"\b(utilisateur|compte)\s+introuvable\b", re.I),
    re.compile(r"\b(usuario|cuenta)\s+no\s+encontrad[oa]\b", re.I),
)


class NegativeMarkersValidator:
    name = "negative_markers"

    def validate(self, ctx: ValidationContext) -> ValidationOutcome:
        body_lower = ctx.body_text.lower()
        signals: list[Signal] = []

        for marker in ctx.platform.get("negative_markers", []):
            marker_text = str(marker).strip()
            if marker_text and marker_text.lower() in body_lower:
                signals.append(
                    Signal(
                        "negative_marker_platform",
                        -100,
                        "platform_marker",
                        hard_negative=True,
                    )
                )
                break

        if not signals:
            for pattern in _COMMON_NEGATIVE_PATTERNS:
                if pattern.search(ctx.body_text):
                    signals.append(
                        Signal(
                            "negative_marker_common",
                            -100,
                            "common_regex",
                            hard_negative=True,
                        )
                    )
                    break

        return ValidationOutcome(self.name, signals, [])
