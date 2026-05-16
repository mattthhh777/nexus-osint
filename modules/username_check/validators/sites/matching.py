"""Site-specific username matching helpers."""
from __future__ import annotations

import re


def username_token_present(value: str, username: str) -> bool:
    """Match username as a token, not as a substring inside another handle."""
    clean_username = username.strip().lstrip("@").casefold()
    if not clean_username:
        return False
    pattern = re.compile(
        rf"(?<![a-z0-9_.-])@?{re.escape(clean_username)}(?![a-z0-9_.-])",
        re.I,
    )
    return pattern.search(value.casefold()) is not None


def username_exact(value: str, username: str) -> bool:
    return value.strip().lstrip("@").casefold() == username.strip().lstrip("@").casefold()
