"""Validator registry for username checks."""
from __future__ import annotations

from collections.abc import Iterable

from modules.username_check.validators.base import (
    Signal,
    ValidationContext,
    ValidationOutcome,
    Validator,
    ValidatorError,
)
from modules.username_check.validators.generic_content import GenericContentValidator
from modules.username_check.validators.negative_markers import NegativeMarkersValidator
from modules.username_check.validators.url_final import UrlFinalValidator


def default_validators() -> list[Validator]:
    return [
        GenericContentValidator(),
        UrlFinalValidator(),
        NegativeMarkersValidator(),
    ]


def _resolve_site_validator(platform_name: str) -> Validator | None:
    name_lower = platform_name.lower()
    if name_lower.startswith("maigret: "):
        name_lower = name_lower[9:]

    if "github" in name_lower:
        from modules.username_check.validators.sites.github import GitHubValidator
        return GitHubValidator()
    if "instagram" in name_lower:
        from modules.username_check.validators.sites.instagram import InstagramValidator
        return InstagramValidator()
    if "twitter" in name_lower or name_lower in {"x", "x / twitter", "twitter / x"}:
        from modules.username_check.validators.sites.x import XValidator
        return XValidator()
    if "linkedin" in name_lower:
        from modules.username_check.validators.sites.linkedin import LinkedInValidator
        return LinkedInValidator()
    if "reddit" in name_lower:
        from modules.username_check.validators.sites.reddit import RedditValidator
        return RedditValidator()
    if "tiktok" in name_lower:
        from modules.username_check.validators.sites.tiktok import TikTokValidator
        return TikTokValidator()
    if "youtube" in name_lower:
        from modules.username_check.validators.sites.youtube import YouTubeValidator
        return YouTubeValidator()
    if "medium" in name_lower:
        from modules.username_check.validators.sites.medium import MediumValidator
        return MediumValidator()
    return None


def for_platform(platform_name: str) -> list[Validator]:
    """Returns default validators plus optional site-specific validator."""
    validators: list[Validator] = default_validators()
    site = _resolve_site_validator(platform_name)
    if site is not None:
        validators.append(site)
    return validators


def validate_all(
    ctx: ValidationContext,
    validators: Iterable[Validator] | None = None,
) -> list[ValidationOutcome]:
    outcomes: list[ValidationOutcome] = []
    for validator in validators if validators is not None else default_validators():
        try:
            outcomes.append(validator.validate(ctx))
        except (ValidatorError, ValueError, TypeError) as exc:
            outcomes.append(
                ValidationOutcome(
                    validator=validator.name,
                    signals=[
                        Signal(
                            "validator_error",
                            0,
                            type(exc).__name__,
                        )
                    ],
                    warnings=[f"validator_error:{validator.name}"],
                )
            )
    return outcomes
