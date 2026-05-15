"""Final URL and redirect validators."""
from __future__ import annotations

import urllib.parse

from modules.username_check.validators.base import (
    Signal,
    ValidationContext,
    ValidationOutcome,
)

_LOGIN_WORDS = ("login", "signin", "sign-in", "auth", "session")
_SEARCH_WORDS = ("search", "find", "users")


def _path_segments(url: str) -> list[str]:
    parsed = urllib.parse.urlparse(url)
    return [segment for segment in parsed.path.split("/") if segment]


def _same_host(left: str, right: str) -> bool:
    return (urllib.parse.urlparse(left).hostname or "").lower() == (
        urllib.parse.urlparse(right).hostname or ""
    ).lower()


class UrlFinalValidator:
    name = "url_final"

    def validate(self, ctx: ValidationContext) -> ValidationOutcome:
        final_url = ctx.fetch_result.final_url or ctx.original_url
        final_lower = final_url.lower()
        username_lower = ctx.username.lower()
        original_segments = _path_segments(ctx.original_url)
        final_segments = _path_segments(final_url)
        signals: list[Signal] = []
        warnings: list[str] = []

        if username_lower in final_lower:
            signals.append(Signal("final_url_contains_username", 25, "final_url"))

        if final_url.rstrip("/") == ctx.original_url.rstrip("/"):
            signals.append(Signal("final_url_matches_expected", 15, "final_url"))

        if ctx.fetch_result.redirect_chain:
            if _same_host(ctx.original_url, final_url) and not final_segments:
                signals.append(
                    Signal(
                        "redirect_to_homepage",
                        -50,
                        "homepage",
                        hard_negative=True,
                    )
                )
            if any(word in final_lower for word in _LOGIN_WORDS):
                warnings.append("redirect_to_login")
            if any(word in final_lower for word in _SEARCH_WORDS):
                signals.append(Signal("redirect_to_search", -30, "search"))
            if (
                original_segments
                and final_segments
                and original_segments[-1].lower() == username_lower
                and final_segments[-1].lower() != username_lower
                and not any(word in final_lower for word in _LOGIN_WORDS + _SEARCH_WORDS)
            ):
                signals.append(
                    Signal(
                        "redirect_to_other_profile",
                        -50,
                        "profile_shape",
                        hard_negative=True,
                    )
                )

        return ValidationOutcome(self.name, signals, warnings)
