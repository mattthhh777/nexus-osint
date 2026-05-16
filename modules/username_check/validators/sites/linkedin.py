"""LinkedIn-specific validator."""
from __future__ import annotations

from modules.username_check.validators.base import Signal, ValidationContext, ValidationOutcome


class LinkedInValidator:
    name = "linkedin_site"

    def validate(self, ctx: ValidationContext) -> ValidationOutcome:
        signals: list[Signal] = []
        warnings: list[str] = []

        if ctx.fetch_result.status_code == 999:
            signals.append(
                Signal("linkedin_auth_wall_999", -100, "status_999", hard_negative=True)
            )
            warnings.append("login_required")
            return ValidationOutcome(self.name, signals, warnings)

        final_url = (ctx.fetch_result.final_url or ctx.original_url).lower()
        if "authwall" in final_url:
            signals.append(
                Signal("linkedin_authwall_redirect", -100, "authwall", hard_negative=True)
            )
            warnings.append("login_required")

        return ValidationOutcome(self.name, signals, warnings)
