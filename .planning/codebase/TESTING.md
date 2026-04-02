# Testing

**Analysis Date:** 2026-03-25

## Current State: No Tests Exist

**Test coverage: 0%.** There are no test files, no test framework configured, no test dependencies installed, and no test directories in the project.

**Evidence:**
- `requirements.txt` contains zero test packages (no pytest, no httpx test client, no coverage, no factory-boy)
- No `conftest.py`, `pytest.ini`, `pyproject.toml`, `setup.cfg`, or `tox.ini` exists
- No `tests/` directory, no `*_test.py` or `test_*.py` files anywhere in the tree
- No frontend test tooling (no vitest, jest, playwright, cypress, or similar)
- No CI/CD pipeline that runs tests
- No pre-commit hooks that validate code

**Only automated check:** Docker `HEALTHCHECK` in `Dockerfile` (line 25) runs `curl -f http://localhost:8000/health` every 30 seconds. The `/health` endpoint (defined at `api/main.py` line 1259) returns `{"status": "ok", "version": "3.0.0"}` unconditionally -- it does not verify database connectivity, OathNet reachability, or any other dependency.

**Current testing approach:** Manual browser-based testing only.

## Test Framework Recommendation

**Runner:** pytest 8.x
**Config file to create:** `pyproject.toml` (add `[tool.pytest.ini_options]` section)
**Async support:** pytest-asyncio (required for aiosqlite and FastAPI async endpoints)
**HTTP testing:** `httpx` is already in `requirements.txt` -- use `httpx.AsyncClient` with FastAPI's `ASGITransport`
**Mocking:** unittest.mock (stdlib) + `responses` or `respx` for HTTP mocking
**Coverage:** pytest-cov

**Recommended test dependencies to add to `requirements.txt`:**
```
pytest==8.3.4
pytest-asyncio==0.24.0
pytest-cov==6.0.0
respx==0.22.0
```

**Run commands (once configured):**
```bash
pytest                        # Run all tests
pytest -x                     # Stop on first failure
pytest --cov=api --cov=modules --cov-report=term-missing  # Coverage
pytest -k "test_auth"         # Run specific test group
pytest tests/unit/            # Run only unit tests
```

## Test File Organization

**Recommended structure:**
```
tests/
  conftest.py                 # Shared fixtures: test client, mock OathNet, temp DB
  unit/
    test_auth.py              # JWT creation, decode, verify, expiry
    test_rate_limiter.py      # SQLite-backed rate limiter
    test_validators.py        # SearchRequest pydantic validators
    test_detect_type.py       # Query type detection regex
    test_oathnet_client.py    # OathnetClient methods with mocked HTTP
    test_oathnet_models.py    # Dataclass properties (risk_score, breach_count)
    test_sherlock_wrapper.py  # Platform checking logic with mocked HTTP
    test_password_hashing.py  # bcrypt hash/verify roundtrip
  integration/
    test_search_endpoint.py   # Full /api/search SSE flow
    test_login_flow.py        # /api/login + /api/me roundtrip
    test_admin_endpoints.py   # /api/admin/* with auth
    test_health.py            # /health returns expected shape
```

**Naming convention:** `test_{module}.py` files, `test_{behavior}` functions.

**Co-location:** Tests live in a separate `tests/` directory (not co-located) because the source code is split across `api/` and `modules/` with no unified `src/` root.

## What MUST Be Tested: Priority Map

### P0 -- Security-Critical (test first)

**1. JWT Authentication (`api/main.py` lines 252-270)**

Functions: `_create_token()`, `_decode_token()`, `get_current_user()`, `get_admin_user()`

Test cases:
```python
# tests/unit/test_auth.py

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from jose import jwt

def test_create_token_contains_required_claims():
    """Token must contain sub, role, exp, iat."""
    token = _create_token("admin", "admin")
    payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"
    assert "exp" in payload
    assert "iat" in payload

def test_decode_token_rejects_expired():
    """Expired tokens must raise HTTPException 401."""
    expired_payload = {
        "sub": "admin", "role": "admin",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=25),
    }
    token = jwt.encode(expired_payload, JWT_SECRET, algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        _decode_token(token)
    assert exc.value.status_code == 401

def test_decode_token_rejects_wrong_secret():
    """Token signed with wrong key must be rejected."""
    token = jwt.encode({"sub": "admin", "role": "admin", "exp": 9999999999}, "wrong-secret", algorithm="HS256")
    with pytest.raises(HTTPException):
        _decode_token(token)

def test_get_admin_user_rejects_non_admin():
    """Non-admin role must get 403."""
    # Use TestClient with a user-role token
    pass  # Integration test with httpx.AsyncClient
```

**2. Password Hashing (`api/main.py` lines 204-218)**

Functions: `_safe_hash()`, `_safe_verify()`

Test cases:
```python
# tests/unit/test_password_hashing.py

def test_hash_verify_roundtrip():
    """Hashed password must verify correctly."""
    hashed = _safe_hash("mypassword123")
    assert _safe_verify("mypassword123", hashed) is True

def test_wrong_password_fails_verify():
    hashed = _safe_hash("correct")
    assert _safe_verify("wrong", hashed) is False

def test_hash_is_not_plaintext():
    hashed = _safe_hash("secret")
    assert "secret" not in hashed
```

**3. Rate Limiter (`api/main.py` lines 132-163)**

Functions: `_init_rate_table()`, `_check_rate()`

Test cases:
```python
# tests/unit/test_rate_limiter.py

@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limit(tmp_path):
    """Requests within limit return True."""
    # Override AUDIT_DB to tmp_path / "test.db"
    for i in range(5):
        assert await _check_rate("test:ip", 5, 60) is True

@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit(tmp_path):
    """6th request in window of 5 returns False."""
    for i in range(5):
        await _check_rate("test:ip", 5, 60)
    assert await _check_rate("test:ip", 5, 60) is False

@pytest.mark.asyncio
async def test_rate_limiter_fail_closed_on_db_error():
    """If DB is unreachable, rate limiter returns False (fail-closed)."""
    # Corrupt or remove DB file, verify returns False
    pass
```

**4. Login Rate Limiting (`api/main.py` line 409)**

The login endpoint limits to 5 attempts per IP per 60 seconds. Test that the 6th attempt returns HTTP 429.

### P1 -- Core Business Logic

**5. Input Sanitization (`api/main.py` lines 71-101)**

Model: `SearchRequest` with `sanitize_query`, `validate_mode`, `validate_sf_mode` validators

Test cases:
```python
# tests/unit/test_validators.py

def test_query_strips_whitespace():
    req = SearchRequest(query="  test@email.com  ")
    assert req.query == "test@email.com"

def test_query_rejects_empty():
    with pytest.raises(ValidationError):
        SearchRequest(query="")

def test_query_rejects_too_short():
    with pytest.raises(ValidationError):
        SearchRequest(query="a")

def test_query_rejects_too_long():
    with pytest.raises(ValidationError):
        SearchRequest(query="a" * 257)

def test_query_strips_null_bytes():
    req = SearchRequest(query="test\x00user")
    assert "\x00" not in req.query

def test_query_strips_sql_injection_chars():
    req = SearchRequest(query="test'; DROP TABLE--")
    assert ";" not in req.query
    assert "'" not in req.query

def test_mode_defaults_invalid_to_automated():
    req = SearchRequest(query="test", mode="invalid")
    assert req.mode == "automated"

def test_spiderfoot_mode_defaults_invalid_to_passive():
    req = SearchRequest(query="test", spiderfoot_mode="aggressive")
    assert req.spiderfoot_mode == "passive"
```

**6. Query Type Detection (`api/main.py` lines 435-443)**

Function: `detect_type()`

Test cases:
```python
# tests/unit/test_detect_type.py

@pytest.mark.parametrize("input,expected", [
    ("user@example.com", "email"),
    ("192.168.1.1", "ip"),
    ("example.com", "domain"),
    ("123456789012345678", "discord_id"),   # 18 digits
    ("+14155551234", "phone"),
    ("7654321", "steam_id"),                # 7 digits
    ("johndoe", "username"),
    ("john.doe", "username"),               # dot not a domain
    ("john_doe123", "username"),
])
def test_detect_type(input, expected):
    assert detect_type(input) == expected
```

**7. OathNet Client (`modules/oathnet_client.py`)**

Class: `OathnetClient` -- all methods use `requests.Session` which must be mocked.

Test cases:
```python
# tests/unit/test_oathnet_client.py
# Use respx or responses to mock HTTP calls

def test_client_rejects_empty_api_key():
    with pytest.raises(ValueError, match="cannot be empty"):
        OathnetClient(api_key="")

def test_search_breach_parses_results(mock_oathnet):
    """Mock /service/search-breach response, verify BreachRecord parsing."""
    client = OathnetClient(api_key="test-key")
    result = client.search_breach("test@example.com")
    assert result.success is True
    assert result.breach_count > 0
    assert result.breaches[0].email == "test@example.com"

def test_search_breach_handles_401(mock_oathnet_401):
    client = OathnetClient(api_key="bad-key")
    result = client.search_breach("test@example.com")
    assert result.success is False
    assert "401" in result.error

def test_search_breach_handles_timeout(mock_oathnet_timeout):
    client = OathnetClient(api_key="test-key", timeout=1)
    result = client.search_breach("test@example.com")
    assert result.success is False
    assert "timed out" in result.error.lower()

def test_handle_429_rate_limit():
    """HTTP 429 from OathNet returns descriptive error."""
    pass

def test_parse_meta_extracts_quota():
    data = {"_meta": {"user": {"plan": "pro"}, "lookups": {"used_today": 5, "left_today": 95, "daily_limit": 100}}}
    meta = OathnetClient._parse_meta(data)
    assert meta.plan == "pro"
    assert meta.used_today == 5
    assert meta.left_today == 95

def test_risk_score_capped_at_100():
    result = OathnetResult()
    result.breaches = [BreachRecord()] * 10   # 10 * 15 = 150 -> capped at 100
    assert result.risk_score == 100

def test_risk_score_combines_sources():
    result = OathnetResult()
    result.breaches = [BreachRecord()] * 2       # 30
    result.stealers = [StealerRecord()] * 1      # 20
    result.holehe_domains = ["a.com", "b.com"]   # 6
    assert result.risk_score == 56
```

**8. Sherlock Wrapper (`modules/sherlock_wrapper.py`)**

Functions: `_check_platform()`, `_run_async_checks()`, `search_username()`

Test cases:
```python
# tests/unit/test_sherlock_wrapper.py
# Use aiohttp mocking (aioresponses)

@pytest.mark.asyncio
async def test_check_platform_status_code_found():
    """Platform returning 200 with status_code claim -> found=True."""
    pass

@pytest.mark.asyncio
async def test_check_platform_text_absent_found():
    """Page without 'Sorry' text and status 200 -> found=True."""
    pass

@pytest.mark.asyncio
async def test_check_platform_timeout():
    """Timeout -> error='timeout', found=False."""
    pass

def test_search_username_strips_at_sign():
    """Input '@johndoe' should search 'johndoe'."""
    # Mock all HTTP, verify username passed without @
    pass

def test_sherlock_result_risk_score():
    r = SherlockResult()
    r.found = [PlatformResult(found=True)] * 10
    assert r.risk_score == 40  # 10 * 4 = 40
    r.found = [PlatformResult(found=True)] * 20
    assert r.risk_score == 60  # capped at 60
```

### P2 -- Integration Tests

**9. Search SSE Endpoint (`api/main.py` line 494)**

The `/api/search` endpoint returns an SSE stream. Test the full flow.

```python
# tests/integration/test_search_endpoint.py

@pytest.mark.asyncio
async def test_search_returns_sse_stream(auth_client, mock_oathnet):
    """POST /api/search returns text/event-stream with start and done events."""
    async with auth_client.stream(
        "POST", "/api/search",
        json={"query": "test@example.com"},
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        events = []
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
        assert events[0]["type"] == "start"
        assert events[-1]["type"] == "done"

@pytest.mark.asyncio
async def test_search_requires_auth(anon_client):
    """POST /api/search without token returns 401."""
    resp = await anon_client.post("/api/search", json={"query": "test"})
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_search_rate_limited(auth_client):
    """21st search in 60s returns 429."""
    for i in range(20):
        await auth_client.post("/api/search", json={"query": f"test{i}"})
    resp = await auth_client.post("/api/search", json={"query": "test_over"})
    assert resp.status_code == 429
```

**10. Login Flow (`api/main.py` lines 405-424)**

```python
# tests/integration/test_login_flow.py

@pytest.mark.asyncio
async def test_login_returns_jwt(client, test_users):
    resp = await client.post("/api/login", json={"username": "admin", "password": "testpass"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["username"] == "admin"
    assert data["role"] == "admin"

@pytest.mark.asyncio
async def test_login_invalid_password(client, test_users):
    resp = await client.post("/api/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401

@pytest.mark.asyncio
async def test_me_endpoint_with_valid_token(auth_client):
    resp = await auth_client.get("/api/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"
```

**11. Admin Endpoints (`api/main.py` lines 916-1052)**

Test that `/api/admin/stats`, `/api/admin/logs`, `/api/admin/users` require admin role and return expected shapes.

### P3 -- Frontend (Lower Priority)

**Frontend testing is deferred** because the frontend is vanilla JS with DOM manipulation (no framework). If frontend tests are added later:

**Recommended tool:** Playwright (end-to-end)

**Testable frontend modules:**
- `static/js/auth.js` -- `apiFetch()` 401 handling, `checkAuth()` flow, `submitAuth()` form submission
- `static/js/search.js` -- `startSearch()` SSE parsing, `handleEvent()` event routing
- `static/js/render.js` -- `renderResults()` DOM output for various result shapes
- `static/js/utils.js` -- `detectType()` (mirrors backend `detect_type()`), `esc()` XSS escaping, `riskLabel()` score thresholds
- `static/js/export.js` -- `writeClipboard()` fallback logic
- `static/js/cases.js` -- localStorage CRUD for saved cases
- `static/js/history.js` -- localStorage search history

**Pure-function candidates extractable for unit testing (no DOM):**
- `detectType()` in `static/js/utils.js` line 11 -- identical regex logic to backend
- `riskLabel()` in `static/js/utils.js` line 34 -- score-to-label mapping
- `esc()` in `static/js/utils.js` line 42 -- HTML escaping
- `formatBytes()` in `static/js/utils.js` line 69 -- byte formatting

## Shared Test Fixtures

```python
# tests/conftest.py

import asyncio
import json
import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Override paths BEFORE importing app
@pytest.fixture(autouse=True)
def isolate_data_dir(tmp_path, monkeypatch):
    """Redirect DATA_DIR, USERS_FILE, AUDIT_DB to temp directory."""
    monkeypatch.setattr("api.main.DATA_DIR", tmp_path)
    monkeypatch.setattr("api.main.USERS_FILE", tmp_path / "users.json")
    monkeypatch.setattr("api.main.AUDIT_DB", tmp_path / "audit.db")
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-for-testing")
    monkeypatch.setenv("OATHNET_API_KEY", "test-oathnet-key")

@pytest.fixture
def test_users(isolate_data_dir, tmp_path):
    """Create a test users.json with admin user (password: testpass)."""
    from api.main import _safe_hash
    users = {
        "admin": {
            "password_hash": _safe_hash("testpass"),
            "role": "admin",
            "created_at": "2026-01-01T00:00:00Z",
            "active": True,
        }
    }
    (tmp_path / "users.json").write_text(json.dumps(users))
    return users

@pytest_asyncio.fixture
async def client():
    """Unauthenticated async test client."""
    from api.main import app, startup
    await startup()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest_asyncio.fixture
async def auth_client(client, test_users):
    """Authenticated async test client with admin JWT."""
    resp = await client.post("/api/login", json={"username": "admin", "password": "testpass"})
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    yield client
```

## Mocking Strategy

**What to mock:**
- All HTTP calls to OathNet API (`requests.Session.get/post` in `modules/oathnet_client.py`) -- use `respx` or `responses`
- All HTTP calls to external platforms in `modules/sherlock_wrapper.py` -- use `aioresponses`
- `time.time()` when testing rate limiter window expiry
- File system paths (`DATA_DIR`, `USERS_FILE`, `AUDIT_DB`) -- redirect to `tmp_path`

**What NOT to mock:**
- SQLite operations (use real temp databases via `tmp_path`)
- Pydantic validation (test real validators)
- JWT encode/decode (test with real `python-jose`)
- FastAPI request handling (use real `httpx.AsyncClient` with `ASGITransport`)

## Coverage Targets

**No coverage is enforced currently.** Recommended initial targets:

| Area | Target | Rationale |
|------|--------|-----------|
| `api/main.py` auth functions | 90% | Security-critical path |
| `api/main.py` validators | 100% | Input sanitization must be complete |
| `api/main.py` rate limiter | 90% | Abuse prevention |
| `modules/oathnet_client.py` | 80% | Core business logic, HTTP edge cases |
| `modules/sherlock_wrapper.py` | 70% | Many platform definitions, test engine not each site |
| Overall | 60% | Starting target for a project with 0% today |

## Docker Integration

The existing `Dockerfile` healthcheck (`HEALTHCHECK` at line 25) is the only automated check in production. To run tests in Docker:

```bash
# Add to Dockerfile (or separate test stage):
RUN pip install pytest pytest-asyncio pytest-cov respx

# Run tests:
docker exec nexus_osint pytest tests/ -v
```

Alternatively, run tests outside Docker since the app has no Docker-specific dependencies beyond file paths (which are overridden in fixtures via `monkeypatch`).

---

*Testing analysis: 2026-03-25*
