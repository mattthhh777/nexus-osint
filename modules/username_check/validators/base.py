"""Base validator interfaces and data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from modules.username_check.fetcher import FetchResult


class ValidatorError(RuntimeError):
    """Expected validator failure that can be isolated without aborting search."""


@dataclass(frozen=True)
class Signal:
    name: str
    weight: int
    detail: str = ""
    hard_positive: bool = False
    hard_negative: bool = False


@dataclass(frozen=True)
class ValidationOutcome:
    validator: str
    signals: list[Signal] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ValidationContext:
    username: str
    platform: dict
    fetch_result: FetchResult
    body_text: str
    original_url: str

    @property
    def platform_name(self) -> str:
        return str(self.platform.get("name", ""))


class Validator(Protocol):
    name: str

    def validate(self, ctx: ValidationContext) -> ValidationOutcome:
        ...
