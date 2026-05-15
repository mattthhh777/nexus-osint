"""Budget accounting adapter for username checks."""
from __future__ import annotations

import api.budget as _budget


def __getattr__(name: str) -> object:
    return getattr(_budget, name)


def record_usage(bytes_used: int) -> None:
    _budget.record_usage(bytes_used)
