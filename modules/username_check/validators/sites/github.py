"""GitHub-specific validator."""
from __future__ import annotations

import re

from modules.username_check.validators.base import Signal, ValidationContext, ValidationOutcome

_PARSE_CAP = 100_000

_ADDITIONAL_NAME = re.compile(
    r'itemprop=["\']additionalName["\'][^>]*>\s*([^<]+)',
    re.I,
)
_AVATAR = re.compile(r"avatars\.githubusercontent\.com/u/\d+", re.I)
_NOT_FOUND_TITLE = re.compile(
    r"(not found|this is not the web page you are looking for)\s*[·•\-|]\s*github",
    re.I,
)


class GitHubValidator:
    name = "github_site"

    def validate(self, ctx: ValidationContext) -> ValidationOutcome:
        body = ctx.body_text[:_PARSE_CAP]
        username_lower = ctx.username.lower()
        signals: list[Signal] = []

        if _NOT_FOUND_TITLE.search(body):
            signals.append(
                Signal("github_not_found_title", -50, "title_not_found", hard_negative=True)
            )
            return ValidationOutcome(self.name, signals, [])

        match = _ADDITIONAL_NAME.search(body)
        if match and username_lower in match.group(1).strip().lower():
            signals.append(
                Signal(
                    "github_username_itemprop",
                    30,
                    "itemprop_additionalName",
                    hard_positive=True,
                )
            )

        if _AVATAR.search(body):
            signals.append(Signal("github_avatar_url", 20, "avatars.githubusercontent.com"))

        return ValidationOutcome(self.name, signals, [])
