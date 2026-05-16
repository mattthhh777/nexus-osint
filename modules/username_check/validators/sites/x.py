"""X (Twitter) site-specific validator."""
from __future__ import annotations

import re

from modules.username_check.validators.base import Signal, ValidationContext, ValidationOutcome
from modules.username_check.validators.sites.matching import username_token_present

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
        signals: list[Signal] = []

        if _NOT_EXIST_SSR.search(body) or _NOT_FOUND_TITLE.search(body):
            signals.append(
                Signal("x_not_found_ssr", -100, "ssr_not_found", hard_negative=True)
            )
            return ValidationOutcome(self.name, signals, [])

        og_match = _OG_TITLE.search(body)
        if og_match:
            if username_token_present(og_match.group(1), ctx.username):
                signals.append(Signal("x_og_title_username", 20, "og:title"))

        return ValidationOutcome(self.name, signals, [])
