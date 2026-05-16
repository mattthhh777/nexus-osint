"""TikTok-specific validator."""
from __future__ import annotations

import re

from modules.username_check.validators.base import Signal, ValidationContext, ValidationOutcome
from modules.username_check.validators.sites.matching import username_token_present

_PARSE_CAP = 100_000

_NOT_FOUND = re.compile(r"(couldn['’]t find this account|\"statusCode\"\s*:\s*10221)", re.I)
_OG_URL = re.compile(
    r'<meta\b(?=[^>]*\bproperty=["\']og:url["\'])(?=[^>]*\bcontent=["\']([^"\']+)["\'])[^>]*>',
    re.I,
)


class TikTokValidator:
    name = "tiktok_site"

    def validate(self, ctx: ValidationContext) -> ValidationOutcome:
        body = ctx.body_text[:_PARSE_CAP]
        signals: list[Signal] = []

        if _NOT_FOUND.search(body):
            signals.append(
                Signal("tiktok_not_found", -100, "not_found_ssr", hard_negative=True)
            )
            return ValidationOutcome(self.name, signals, [])

        og_match = _OG_URL.search(body)
        if og_match and username_token_present(og_match.group(1), ctx.username):
            signals.append(Signal("tiktok_og_url_username", 20, "og:url"))

        return ValidationOutcome(self.name, signals, [])
