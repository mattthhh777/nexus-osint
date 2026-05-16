"""X (Twitter) site-specific validator."""
from __future__ import annotations

import re

from modules.username_check.validators.base import Signal, ValidationContext, ValidationOutcome

_PARSE_CAP = 100_000

_NOT_EXIST_SSR = re.compile(r"this account doesn[‘’']t exist", re.I)
_NOT_FOUND_TITLE = re.compile(
    r"(page not found|this page doesn[‘’']t exist)\s*[|·•]\s*x\b",
    re.I,
)
_OG_TITLE = re.compile(
    r'<meta\b(?=[^>]*\bproperty=["\']og:title["\'])(?=[^>]*\bcontent=["\']([^"\']+)["\'])[^>]*>',
    re.I,
)


class XValidator:
    name = "x_site"

    def validate(self, ctx: ValidationContext) -> ValidationOutcome:
        body = ctx.body_text[:_PARSE_CAP]
        username_lower = ctx.username.lower()
        signals: list[Signal] = []

        if _NOT_EXIST_SSR.search(body) or _NOT_FOUND_TITLE.search(body):
            signals.append(
                Signal("x_not_found_ssr", -100, "ssr_not_found", hard_negative=True)
            )
            return ValidationOutcome(self.name, signals, [])

        og_match = _OG_TITLE.search(body)
        if og_match:
            og_title_lower = og_match.group(1).lower()
            if username_lower in og_title_lower or f"@{username_lower}" in og_title_lower:
                signals.append(Signal("x_og_title_username", 20, "og:title"))

        return ValidationOutcome(self.name, signals, [])
