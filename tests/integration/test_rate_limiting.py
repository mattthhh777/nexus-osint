"""
tests/integration/test_rate_limiting.py
========================================
Integration tests for slowapi rate limiting (Phase 09 Plan 02 — Wave 2).

Verifies:
  - /api/login: 429 after RL_LOGIN_LIMIT exceeded (default 5/minute, keyed by IP)
  - /api/admin/users (POST): 429 after RL_REGISTER_LIMIT exceeded (default 3/hour)
  - /api/search: 429 after RL_SEARCH_LIMIT exceeded (default 10/minute, per user)
  - Per-user isolation: user A hitting limit does NOT block user B
  - Retry-After header present on 429 responses
  - Legacy _check_rate function removed from codebase (FIND-04)

Note on slowapi internals: limits are captured at decoration time from the module-level
RL_* constant strings. Monkeypatching the constants post-import has no effect on the
active limit. Tests therefore exhaust the real defaults (5, 10, 3) so they verify
actual production behavior.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

# JWT_SECRET must be set before importing api.main — load_dotenv() runs at import time
_TEST_SECRET = "test-secret-for-rate-limit-tests-only-never-prod-abcdef123456"
os.environ.setdefault("JWT_SECRET", _TEST_SECRET)

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import api.main as m  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_cookie(sub: str, role: str = "user") -> str:
    """Mint a valid JWT cookie for test auth."""
    payload = {
        "sub": sub,
        "role": role,
        "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "jti": f"test-jti-{sub}",
    }
    return jwt.encode(payload, _TEST_SECRET, algorithm="HS256")


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Clear all rate-limit counters before each test."""
    m.limiter._storage.reset()
    yield
    m.limiter._storage.reset()


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    """TestClient with correct JWT_SECRET and no lifespan side effects."""
    monkeypatch.setattr(m, "JWT_SECRET", _TEST_SECRET)
    return TestClient(m.app, raise_server_exceptions=False)


# ── /api/login — rate limited by IP, real limit 5/minute ─────────────────────


def test_login_429_after_five_attempts(client):
    """6th POST to /api/login from same IP returns HTTP 429 (RL_LOGIN_LIMIT=5/minute)."""
    for i in range(5):
        r = client.post("/api/login", json={"username": "x", "password": "y"})
        # Each returns 401 (wrong creds) — NOT 429
        assert r.status_code != 429, f"Hit 429 too early on attempt {i + 1}"

    # 6th request — same IP → rate limited
    r = client.post("/api/login", json={"username": "x", "password": "y"})
    assert r.status_code == 429


def test_login_429_has_retry_after(client):
    """429 response from /api/login must include Retry-After header."""
    for _ in range(5):
        client.post("/api/login", json={"username": "x", "password": "y"})

    r = client.post("/api/login", json={"username": "x", "password": "y"})
    assert r.status_code == 429
    # Retry-After is set by slowapi's _rate_limit_exceeded_handler
    assert "retry-after" in {h.lower() for h in r.headers}, (
        f"Retry-After header missing. Got: {dict(r.headers)}"
    )


def test_login_no_check_rate_db_writes(client, monkeypatch):
    """_check_rate function must be removed; no rate_limits DB writes during login (FIND-04)."""
    assert not hasattr(m, "_check_rate"), (
        "_check_rate still exists in api.main — FIND-04 not fully remediated"
    )

    writes: list[str] = []
    original_write = m._db.write

    async def _spy_write(query: str, params=()):
        if "rate_limits" in query:
            writes.append(query)
        return await original_write(query, params)

    monkeypatch.setattr(m._db, "write", _spy_write)

    client.post("/api/login", json={"username": "admin", "password": "wrongpass"})
    assert writes == [], f"Unexpected rate_limits DB writes during login: {writes}"


# ── /api/search — per-user rate limiting, real limit 10/minute ───────────────


def test_search_429_after_ten_requests(monkeypatch):
    """11th POST to /api/search by the same user returns HTTP 429 (RL_SEARCH_LIMIT=10/minute)."""
    token = _make_cookie("alice", "user")
    monkeypatch.setattr(m, "JWT_SECRET", _TEST_SECRET)

    client = TestClient(m.app, raise_server_exceptions=False)
    client.cookies["nx_session"] = token
    m.app.dependency_overrides[m.get_current_user] = lambda: {"sub": "alice", "role": "user"}

    try:
        for i in range(10):
            r = client.post(
                "/api/search",
                json={"query": "testuser", "mode": "manual", "modules": []},
            )
            assert r.status_code != 429, f"Hit 429 too early on search {i + 1} (got {r.status_code})"

        r = client.post(
            "/api/search",
            json={"query": "testuser", "mode": "manual", "modules": []},
        )
        assert r.status_code == 429
    finally:
        m.app.dependency_overrides.pop(m.get_current_user, None)


def test_search_per_user_isolation(monkeypatch):
    """User A hitting the search rate limit must NOT block user B.

    Uses two separate TestClient instances with cookies set at the client level
    to avoid the per-request cookies deprecation and ensure correct cookie forwarding.
    """
    token_a = _make_cookie("user_a", "user")
    token_b = _make_cookie("user_b", "user")

    monkeypatch.setattr(m, "JWT_SECRET", _TEST_SECRET)

    # Client A — always sends user_a cookie
    client_a = TestClient(m.app, raise_server_exceptions=False)
    client_a.cookies["nx_session"] = token_a

    # Client B — always sends user_b cookie
    client_b = TestClient(m.app, raise_server_exceptions=False)
    client_b.cookies["nx_session"] = token_b

    m.app.dependency_overrides[m.get_current_user] = lambda: {"sub": "user_a", "role": "user"}

    try:
        # Exhaust user_a's limit (10 requests) — query >=2 chars to pass validation
        for _ in range(10):
            client_a.post(
                "/api/search",
                json={"query": "xx", "mode": "manual", "modules": []},
            )

        # user_a is now rate limited
        r_a = client_a.post(
            "/api/search",
            json={"query": "xx", "mode": "manual", "modules": []},
        )
        assert r_a.status_code == 429

        # user_b must NOT be blocked — different key (u:user_b vs u:user_a)
        m.app.dependency_overrides[m.get_current_user] = lambda: {"sub": "user_b", "role": "user"}
        r_b = client_b.post(
            "/api/search",
            json={"query": "xx", "mode": "manual", "modules": []},
        )
        assert r_b.status_code != 429, (
            f"User B incorrectly blocked (status {r_b.status_code}) — "
            "per-user key isolation broken"
        )
    finally:
        m.app.dependency_overrides.pop(m.get_current_user, None)


def test_search_429_has_retry_after(monkeypatch):
    """429 from /api/search must include Retry-After header."""
    token = _make_cookie("bob", "user")
    monkeypatch.setattr(m, "JWT_SECRET", _TEST_SECRET)

    client = TestClient(m.app, raise_server_exceptions=False)
    client.cookies["nx_session"] = token
    m.app.dependency_overrides[m.get_current_user] = lambda: {"sub": "bob", "role": "user"}

    try:
        for _ in range(10):
            client.post(
                "/api/search",
                json={"query": "xx", "mode": "manual", "modules": []},
            )
        r = client.post(
            "/api/search",
            json={"query": "xx", "mode": "manual", "modules": []},
        )
        assert r.status_code == 429
        assert "retry-after" in {h.lower() for h in r.headers}
    finally:
        m.app.dependency_overrides.pop(m.get_current_user, None)


# ── /api/admin/users (POST) — registration cap, real limit 3/hour ────────────


def test_admin_create_user_429_after_register_limit(client, tmp_path, monkeypatch):
    """4th POST to /api/admin/users returns HTTP 429 (RL_REGISTER_LIMIT=3/hour)."""
    import json as _json

    admin_users = {
        "admin": {
            "password_hash": m._safe_hash("AdminPass1!"),
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
        }
    }
    tmp_users_file = tmp_path / "users.json"
    tmp_users_file.write_text(_json.dumps(admin_users))

    monkeypatch.setattr(m, "MAX_USERS", 100)
    monkeypatch.setattr(m, "USERS_FILE", tmp_users_file)
    monkeypatch.setattr(m, "_users_cache", None)

    m.app.dependency_overrides[m.get_admin_user] = lambda: {"sub": "admin", "role": "admin"}

    try:
        for i in range(3):
            r = client.post(
                "/api/admin/users",
                json={"username": f"newuser{i}", "password": "StrongPass1!", "role": "user"},
            )
            assert r.status_code != 429, f"Hit 429 too early on create {i + 1}"

        # 4th request — rate limited
        r = client.post(
            "/api/admin/users",
            json={"username": "extra", "password": "StrongPass2!", "role": "user"},
        )
        assert r.status_code == 429
    finally:
        m.app.dependency_overrides.pop(m.get_admin_user, None)
