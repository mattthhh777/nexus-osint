"""Reddit-specific validator."""
from __future__ import annotations

import re

from modules.username_check.validators.base import Signal, ValidationContext, ValidationOutcome

_PARSE_CAP = 50_000

_BOT_CHALLENGE = re.compile(
    r"(robot or human|please wait.*?verification|verify you are human|"
    r"verify.*?not a robot|captcha|cf-chl-bypass)",
    re.I,
)
_NO_USER = re.compile(r"nobody on reddit goes by that name", re.I)
_SUSPENDED = re.compile(r"account has been (suspended|banned)", re.I)


class RedditValidator:
    name = "reddit_site"

    def validate(self, ctx: ValidationContext) -> ValidationOutcome:
        body = ctx.body_text[:_PARSE_CAP]
        signals: list[Signal] = []
        warnings: list[str] = []

        if _BOT_CHALLENGE.search(body):
            signals.append(
                Signal("reddit_bot_challenge", -100, "bot_challenge", hard_negative=True)
            )
            warnings.append("bot_check")
            return ValidationOutcome(self.name, signals, warnings)

        if _NO_USER.search(body):
            signals.append(
                Signal("reddit_no_user", -100, "no_user_ssr", hard_negative=True)
            )

        if _SUSPENDED.search(body):
            warnings.append("account_suspended")

        return ValidationOutcome(self.name, signals, warnings)
