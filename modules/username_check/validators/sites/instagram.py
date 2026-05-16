"""Instagram-specific validator."""
from __future__ import annotations

import re

from modules.username_check.validators.base import Signal, ValidationContext, ValidationOutcome

_PARSE_CAP = 100_000

_LOGIN_REDIRECT = re.compile(r"/accounts/login|login_required=true", re.I)
_REQUIRE_LOGIN_JSON = re.compile(r'"requiresLogin"\s*:\s*true', re.I)
_NOT_AVAILABLE_SSR = re.compile(
    r"sorry,?\s+this\s+page\s+(isn['']t|is\s+not)\s+available",
    re.I,
)
_OG_PROFILE_TYPE = re.compile(
    r'<meta\b(?=[^>]*\bproperty=["\']og:type["\'])(?=[^>]*\bcontent=["\']profile["\'])[^>]*>',
    re.I,
)


class InstagramValidator:
    name = "instagram_site"

    def validate(self, ctx: ValidationContext) -> ValidationOutcome:
        final_url = (ctx.fetch_result.final_url or ctx.original_url).lower()
        body = ctx.body_text[:_PARSE_CAP]
        signals: list[Signal] = []
        warnings: list[str] = []

        if _LOGIN_REDIRECT.search(final_url):
            signals.append(
                Signal("instagram_login_wall", 0, "login_redirect")
            )
            warnings.append("login_required")

        if _NOT_AVAILABLE_SSR.search(body):
            signals.append(
                Signal("instagram_not_available_ssr", -100, "not_available", hard_negative=True)
            )

        if _REQUIRE_LOGIN_JSON.search(body):
            if not any(s.name == "instagram_login_wall" for s in signals):
                signals.append(
                    Signal(
                        "instagram_require_login_json",
                        0,
                        "requiresLogin_json",
                    )
                )
                warnings.append("login_required")

        if _OG_PROFILE_TYPE.search(body):
            signals.append(
                Signal("instagram_og_profile_type", 25, "og:type_profile", hard_positive=True)
            )

        return ValidationOutcome(self.name, signals, warnings)
