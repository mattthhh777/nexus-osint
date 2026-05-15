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
