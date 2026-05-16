"""Medium-specific validator."""
from __future__ import annotations

import re

from modules.username_check.validators.base import Signal, ValidationContext, ValidationOutcome
from modules.username_check.validators.sites.matching import username_token_present

_PARSE_CAP = 50_000

_NOT_FOUND = re.compile(
    r"(profile not found|404\s*[–—-]\s*an error occurred|"
    r"this page doesn['']t exist|page not found)",
    re.I,
)
_OG_TITLE = re.compile(
    r'<meta\b(?=[^>]*\bproperty=["\']og:title["\'])(?=[^>]*\bcontent=["\']([^"\']+)["\'])[^>]*>',
    re.I,
)


class MediumValidator:
    name = "medium_site"

    def validate(self, ctx: ValidationContext) -> ValidationOutcome:
        body = ctx.body_text[:_PARSE_CAP]
        signals: list[Signal] = []

        if _NOT_FOUND.search(body):
            signals.append(
                Signal("medium_not_found", -100, "not_found_ssr", hard_negative=True)
            )
            return ValidationOutcome(self.name, signals, [])

        og_match = _OG_TITLE.search(body)
        if og_match and username_token_present(og_match.group(1), ctx.username):
            signals.append(Signal("medium_og_title_username", 15, "og:title"))

        return ValidationOutcome(self.name, signals, [])
