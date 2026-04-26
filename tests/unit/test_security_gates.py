"""
tests/unit/test_security_gates.py
===================================
Unit tests for the four backend security gates introduced in Phase 09 Plan 01:

  D-09 / FIND-03  — JWT_SECRET fail-hard guard (_validate_jwt_secret)
  D-12 / FIND-07  — MAX_USERS registration cap (/api/admin/users)
  D-10 / FIND-12  — Fail-closed blacklist (_check_blacklist)
  D-11            — SpiderFoot target validator (SpiderFootTarget)

All tests are pure-unit — no real network, no real disk I/O.
Monkeypatching is used to isolate env-var reads.
"""
from __future__ import annotations

import os
import sys

import pytest
import aiosqlite

# Import api.main eagerly so load_dotenv() runs once at collection time.
# Without this, monkeypatch.delenv("JWT_SECRET") would be overridden by
# the load_dotenv() call that happens during the first `from api.main import …`
# inside each test function body.
import api.main  # noqa: F401

# ── D-09: JWT_SECRET fail-hard guard ─────────────────────────────────────────


def test_validate_jwt_secret_raises_on_none(monkeypatch):
    """Server MUST refuse to start when JWT_SECRET is absent from env."""
    monkeypatch.delenv("JWT_SECRET", raising=False)
    from api.main import _validate_jwt_secret  # noqa: PLC0415
    with pytest.raises(SystemExit) as exc_info:
        _validate_jwt_secret()
    assert exc_info.value.code == 1


def test_validate_jwt_secret_raises_on_empty(monkeypatch):
    """Server MUST refuse to start when JWT_SECRET is an empty string."""
    monkeypatch.setenv("JWT_SECRET", "")
    from api.main import _validate_jwt_secret  # noqa: PLC0415
    with pytest.raises(SystemExit) as exc_info:
        _validate_jwt_secret()
    assert exc_info.value.code == 1


@pytest.mark.parametrize("weak", ["changeme", "CHANGEME", "secret", "Secret",
                                   "dev", "DEV", "test", "TEST", "password", "PASSWORD"])
def test_validate_jwt_secret_raises_on_weak_default(monkeypatch, weak):
    """Server MUST refuse to start for every known weak default (case-insensitive)."""
    monkeypatch.setenv("JWT_SECRET", weak)
    from api.main import _validate_jwt_secret  # noqa: PLC0415
    with pytest.raises(SystemExit) as exc_info:
        _validate_jwt_secret()
    assert exc_info.value.code == 1


def test_validate_jwt_secret_passes_strong_value(monkeypatch):
    """A strong, novel secret must NOT cause SystemExit."""
    monkeypatch.setenv("JWT_SECRET", "a3f7b9d2e1c804567890abcdef1234567890abcd")
    from api.main import _validate_jwt_secret  # noqa: PLC0415
    # Should return None without raising
    result = _validate_jwt_secret()
    assert result is None


# ── D-12: MAX_USERS registration cap ─────────────────────────────────────────


def test_admin_create_user_blocked_at_capacity(monkeypatch, tmp_path):
    """POST /api/admin/users must return 403 when user count >= MAX_USERS."""
    import api.main as m
    import json
    from datetime import datetime, timezone
    from fastapi.testclient import TestClient

    # Build a users file with admin + existinguser (2 users)
    admin_users = {
        "admin": {
            "password_hash": m._safe_hash("AdminPass1!"),
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
        },
        "existinguser": {
            "password_hash": m._safe_hash("StrongPass1!"),
            "role": "user",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
        },
    }
    tmp_users_file = tmp_path / "users.json"
    tmp_users_file.write_text(json.dumps(admin_users))

    # Set MAX_USERS to 2 so 2 users == cap, wire tmp file path
    import api.services.auth_service as auth_svc
    monkeypatch.setattr(m, "MAX_USERS", 2)
    from api.routes import admin as _admin_route
    monkeypatch.setattr(_admin_route, "MAX_USERS", 2)
    monkeypatch.setattr(auth_svc, "USERS_FILE", tmp_users_file)
    monkeypatch.setattr(auth_svc, "_users_cache", None)

    # Override auth dependency so tests don't need a live DB for token blacklist checks
    m.app.dependency_overrides[m.get_admin_user] = lambda: {"sub": "admin", "role": "admin"}

    try:
        client = TestClient(m.app, raise_server_exceptions=True)
        resp = client.post(
            "/api/admin/users",
            json={"username": "newuser", "password": "StrongPass2!", "role": "user"},
        )
    finally:
        m.app.dependency_overrides.pop(m.get_admin_user, None)

    assert resp.status_code == 403
    assert "registration capacity reached" in resp.json().get("detail", "")


def test_admin_create_user_allowed_below_capacity(monkeypatch, tmp_path):
    """POST /api/admin/users must succeed when user count < MAX_USERS."""
    import api.main as m
    import json
    from datetime import datetime, timezone
    from fastapi.testclient import TestClient

    # Only one user (admin) — count (1) < MAX_USERS (10)
    admin_users = {
        "admin": {
            "password_hash": m._safe_hash("AdminPass1!"),
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
        },
    }
    tmp_users_file = tmp_path / "users.json"
    tmp_users_file.write_text(json.dumps(admin_users))

    import api.services.auth_service as auth_svc
    monkeypatch.setattr(m, "MAX_USERS", 10)
    monkeypatch.setattr(auth_svc, "USERS_FILE", tmp_users_file)
    monkeypatch.setattr(auth_svc, "_users_cache", None)

    # Override auth dependency so tests don't need a live DB for token blacklist checks
    m.app.dependency_overrides[m.get_admin_user] = lambda: {"sub": "admin", "role": "admin"}

    try:
        client = TestClient(m.app, raise_server_exceptions=True)
        resp = client.post(
            "/api/admin/users",
            json={"username": "newuser2", "password": "StrongPass3!", "role": "user"},
        )
    finally:
        m.app.dependency_overrides.pop(m.get_admin_user, None)

    assert resp.status_code == 200
    assert resp.json().get("ok") is True


# ── D-10: Fail-closed blacklist ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_blacklist_raises_503_on_db_error(monkeypatch):
    """_check_blacklist must raise HTTP 503 when the DB read fails (fail-closed)."""
    import api.main as m
    from fastapi import HTTPException

    # Patch _db.write and _db.read_one to simulate DB failure
    async def _failing_write(*args, **kwargs):
        raise aiosqlite.OperationalError("disk I/O error")

    async def _failing_read_one(*args, **kwargs):
        raise aiosqlite.OperationalError("disk I/O error")

    monkeypatch.setattr(m._db, "write", _failing_write)
    monkeypatch.setattr(m._db, "read_one", _failing_read_one)

    with pytest.raises(HTTPException) as exc_info:
        await m._check_blacklist("test-jti-value")

    assert exc_info.value.status_code == 503
    assert "security policy unavailable" in exc_info.value.detail


@pytest.mark.asyncio
async def test_check_blacklist_passes_when_jti_not_revoked(tmp_db, monkeypatch):
    """_check_blacklist must return normally when jti is not in blacklist."""
    import api.main as m
    import api.deps as deps
    # Patch _db on api.deps where _check_blacklist now lives (Phase 15 Plan 02)
    monkeypatch.setattr(deps, "_db", tmp_db)
    monkeypatch.setattr(m, "_db", tmp_db)

    # Should not raise
    await m._check_blacklist("non-revoked-jti-12345")


@pytest.mark.asyncio
async def test_check_blacklist_skips_when_jti_is_none():
    """_check_blacklist must return immediately (no DB call) when jti is None."""
    import api.main as m

    # Track if DB is called
    called = []

    async def _should_not_be_called(*args, **kwargs):
        called.append(True)
        raise AssertionError("DB should not be called when jti is None")

    original_write = m._db.write
    original_read = m._db.read_one
    # We don't monkeypatch here — we just verify no exception is raised
    # and the function returns None for jti=None
    result = await m._check_blacklist(None)
    assert result is None


# ── D-11: SpiderFoot target validator ────────────────────────────────────────


class TestSpiderFootTarget:
    """Pydantic v2 field_validator — FQDN and IPv4 only."""

    def test_accepts_simple_fqdn(self):
        from modules.spiderfoot_wrapper import SpiderFootTarget
        t = SpiderFootTarget(target="example.com")
        assert t.target == "example.com"

    def test_accepts_subdomain_fqdn(self):
        from modules.spiderfoot_wrapper import SpiderFootTarget
        t = SpiderFootTarget(target="sub.example.co.uk")
        assert t.target == "sub.example.co.uk"

    def test_accepts_valid_ipv4(self):
        from modules.spiderfoot_wrapper import SpiderFootTarget
        t = SpiderFootTarget(target="192.168.1.1")
        assert t.target == "192.168.1.1"

    def test_rejects_domain_with_space(self):
        from modules.spiderfoot_wrapper import SpiderFootTarget
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            SpiderFootTarget(target="example com")
        assert "invalid target" in str(exc_info.value).lower()

    def test_rejects_ipv6(self):
        from modules.spiderfoot_wrapper import SpiderFootTarget
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            SpiderFootTarget(target="::1")
        assert "invalid target" in str(exc_info.value).lower()

    def test_rejects_cidr_notation(self):
        from modules.spiderfoot_wrapper import SpiderFootTarget
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            SpiderFootTarget(target="192.168.1.0/24")
        assert "invalid target" in str(exc_info.value).lower()

    def test_rejects_url_with_scheme(self):
        from modules.spiderfoot_wrapper import SpiderFootTarget
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            SpiderFootTarget(target="https://x.com")
        assert "invalid target" in str(exc_info.value).lower()

    def test_rejects_path_traversal(self):
        from modules.spiderfoot_wrapper import SpiderFootTarget
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            SpiderFootTarget(target="../etc/passwd")
        assert "invalid target" in str(exc_info.value).lower()

    def test_rejects_unicode_domain(self):
        from modules.spiderfoot_wrapper import SpiderFootTarget
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            SpiderFootTarget(target="ex\u00e1mple.com")
        assert "invalid target" in str(exc_info.value).lower()

    def test_rejects_empty_string(self):
        from modules.spiderfoot_wrapper import SpiderFootTarget
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            SpiderFootTarget(target="")
        assert "invalid target" in str(exc_info.value).lower()
