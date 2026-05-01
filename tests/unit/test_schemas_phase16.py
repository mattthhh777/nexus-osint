"""Unit tests for Phase 16 SherlockUsernameRequest validator in api/schemas.py.

Tests verify D-H8/D-H9 requirements:
- Strict regex ^[A-Za-z0-9_.-]{1,64}$ enforced
- URL injection chars rejected
- Input never echoed in validation error messages (CLAUDE.md regra 3)
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.schemas import SherlockUsernameRequest


def test_valid_alphanumeric_underscore():
    """Alphanumeric + underscore combo validates."""
    req = SherlockUsernameRequest(username="alice_42")
    assert req.username == "alice_42"


def test_valid_dot_hyphen():
    """Dot and hyphen are allowed per regex."""
    req = SherlockUsernameRequest(username="alice.bob-42")
    assert req.username == "alice.bob-42"


def test_slash_rejected():
    """Forward slash is URL injection — must be rejected."""
    with pytest.raises(ValidationError):
        SherlockUsernameRequest(username="alice/bob")


def test_space_rejected():
    """Space is not in allowed charset — must be rejected."""
    with pytest.raises(ValidationError):
        SherlockUsernameRequest(username="alice bob")


def test_null_byte_rejected():
    """Null byte is a control char — must be rejected."""
    with pytest.raises(ValidationError):
        SherlockUsernameRequest(username="alice\x00bob")


def test_max_length_cap_at_64():
    """65-char username exceeds the 64-char limit — must be rejected."""
    with pytest.raises(ValidationError):
        SherlockUsernameRequest(username="a" * 65)


def test_empty_string_rejected():
    """Empty string violates the length floor of 1 — must be rejected."""
    with pytest.raises(ValidationError):
        SherlockUsernameRequest(username="")


def test_url_injection_chars_rejected():
    """? and = are URL injection chars — must be rejected."""
    with pytest.raises(ValidationError):
        SherlockUsernameRequest(username="alice?attack=1")


def test_validation_error_does_not_echo_input():
    """D-H9: the raw input string must NOT appear in the ValidationError repr.

    Validation errors are generic ('Invalid username') — never echo the raw
    value back to the caller (CLAUDE.md regra 3 — frontend is hostile territory).
    """
    bad_input = "alice/injection<script>"
    with pytest.raises(ValidationError) as exc_info:
        SherlockUsernameRequest(username=bad_input)
    # The error repr must NOT contain the raw malicious input
    assert bad_input not in repr(exc_info.value), (
        f"Raw input was echoed in ValidationError: {repr(exc_info.value)}"
    )
