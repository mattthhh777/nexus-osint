"""YouTube-specific validator."""
from __future__ import annotations

import re

from modules.username_check.validators.base import Signal, ValidationContext, ValidationOutcome
from modules.username_check.validators.sites.matching import username_token_present

_PARSE_CAP = 100_000

_NOT_FOUND = re.compile(
    r"(this page isn['']t available|404 not found|channel not found|"
    r"this channel does not exist)",
    re.I,
)
_OG_TITLE = re.compile(
    r'<meta\b(?=[^>]*\bproperty=["\']og:title["\'])(?=[^>]*\bcontent=["\']([^"\']+)["\'])[^>]*>',
    re.I,
)
_OG_URL = re.compile(
    r'<meta\b(?=[^>]*\bproperty=["\']og:url["\'])(?=[^>]*\bcontent=["\']([^"\']+)["\'])[^>]*>',
    re.I,
)


class YouTubeValidator:
    name = "youtube_site"

    def validate(self, ctx: ValidationContext) -> ValidationOutcome:
        body = ctx.body_text[:_PARSE_CAP]
        signals: list[Signal] = []

        if _NOT_FOUND.search(body):
            signals.append(
                Signal("youtube_not_found", -100, "not_found_ssr", hard_negative=True)
            )
            return ValidationOutcome(self.name, signals, [])

        og_title_match = _OG_TITLE.search(body)
        if og_title_match and username_token_present(og_title_match.group(1), ctx.username):
            signals.append(Signal("youtube_og_title_username", 15, "og:title"))

        og_url_match = _OG_URL.search(body)
        if og_url_match and username_token_present(og_url_match.group(1), ctx.username):
            signals.append(Signal("youtube_og_url_username", 20, "og:url"))

        return ValidationOutcome(self.name, signals, [])
