# Testing Patterns

**Analysis Date:** 2026-04-19

## Test Framework

**Runner:**
- pytest 8.0+ with pytest-asyncio 0.23+
- Config: `pytest.ini` at project root (minimal, 5 lines)

**Assertion Library:**
- pytest built-in assertions (no external assertion library)
- Pattern: `assert condition`, `assert value == expected`, `assert row is not None`

**Run Commands:**
```bash
pytest                    # Run all tests in tests/
pytest -v                 # Verbose output (show each test)
pytest -k test_db         # Run tests matching pattern
pytest --tb=short         # Short traceback format
pytest -x                 # Stop on first failure
pytest --co -q            # Collect tests without running
```

**Current Test Count:** 62 tests collected

## Test File Organization

**Location:**
- Tests co-located in `tests/` directory (separate from `api/`, `modules/`, `static/`)
- Subdirectories by category, not by layer

**Directory Structure:**
```
tests/
├── conftest.py              # Shared fixtures (pytest session/function scope)
├── test_db.py               # DatabaseManager unit tests (5 tests)
├── test_db_stream.py        # DatabaseManager streaming read tests (5 tests)
├── test_endpoints.py        # FastAPI endpoint integration tests (4 tests)
├── test_oathnet_client.py   # OathnetClient async client unit tests (7 tests)
├── test_orchestrator.py     # TaskOrchestrator concurrent execution tests (6 tests)
├── integration/
│   ├── __init__.py
│   └── test_rate_limiting.py  # slowapi rate limiter integration tests (7 tests)
└── unit/
    ├── __init__.py
    └── test_security_gates.py  # Security validation & capacity gate tests (21 tests)
```

**Naming:**
- Test files: `test_<module>.py` (e.g., `test_db.py` for `api/db.py`)
- Test functions: `test_<scenario>` (e.g., `test_wal_mode`, `test_write_serialization`)
- Async test functions: `async def test_<scenario>` (pytest-asyncio detects automatically via `asyncio_mode = auto`)

## Test Structure

**Suite Organization (from `tests/test_db.py`):**
```python
import pytest
import pytest_asyncio

@pytest.mark.asyncio
async def test_wal_mode(tmp_db: DatabaseManager) -> None:
    """Docstring describing what is tested."""
    # Arrange: setup test preconditions (fixtures already set up)
    row = await tmp_db.read_one("PRAGMA journal_mode")
    
    # Act: execute the code being tested
    value = list(row.values())[0]
    
    # Assert: verify the result
    assert value == "wal", f"Expected WAL mode, got {value!r}"
```

**Patterns:**
- Setup: via pytest fixtures (see below)
- Teardown: automatic via fixture cleanup (e.g., `await manager.shutdown()`)
- Assertion: pytest `assert` statements with descriptive messages
- Helpers: module-level async functions prefixed with `_` (e.g., `async def _fast_module()`)

## Mocking

**Framework:** respx for mocking httpx.AsyncClient

**Patterns (from `tests/test_oathnet_client.py`):**
```python
import respx
import httpx

@pytest.mark.asyncio
@respx.mock
async def test_search_breach_returns_breach_records(client: OathnetClient) -> None:
    """Mock httpx.AsyncClient calls — no real network traffic."""
    mock_response = {
        "success": True,
        "data": {
            "results_found": 2,
            "results": [
                {
                    "dbname": "TestDB",
                    "email": "test@example.com",
                    # ... fields ...
                },
            ],
        },
    }
    # Mock the specific endpoint
    respx.get(f"{OATHNET_BASE_URL}/service/search-breach").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    
    # Now call the client — it uses the mocked response
    result = await client.search_breach("test@example.com")
    assert result.success is True
```

**When to Use:**
- HTTPx calls: always mock with respx (no real API traffic in tests)
- Database calls: use in-memory or temp SQLite (see fixtures below)
- File I/O: use `tmp_path` fixture for temp directories

**What NOT to Mock:**
- Async database operations (test the real SQLite with temp files)
- The orchestrator's semaphore behavior (test the actual concurrent execution)
- Error handling in endpoints (test real exception paths, not mocks)

## Fixtures and Factories

**Test Data (from `tests/conftest.py`):**
```python
@pytest_asyncio.fixture
async def tmp_db(tmp_path: Path) -> DatabaseManager:
    """
    Yield a fully started DatabaseManager backed by a temp file.
    Shutdown is called automatically after each test.
    """
    db_path = tmp_path / "test_audit.db"
    manager = DatabaseManager(db_path=db_path)
    await manager.startup()
    yield manager
    await manager.shutdown()
```

**Fixture Scope:**
- `session`: `event_loop_policy` (sets asyncio event loop policy once per session)
- `function`: `tmp_db` (fresh database for each test)

**Location:**
- Shared fixtures: `tests/conftest.py` (imported automatically by pytest)
- Module-specific fixtures: in test file itself (e.g., `client` fixture in `test_oathnet_client.py`)

**Factory Pattern (for test helpers):**
```python
# From test_orchestrator.py
async def _fast_module(name: str, value: Any = None, *, delay: float = 0.0) -> Any:
    """Simulate a module that completes quickly after an optional sleep."""
    if delay:
        await asyncio.sleep(delay)
    return value if value is not None else f"result_{name}"

async def _failing_module(exc: Exception) -> None:
    """Simulate a module that raises an exception."""
    raise exc
```

## Coverage

**Requirements:** No explicit minimum enforced (coverage tool not configured)

**View Coverage:**
```bash
pytest --cov=api --cov=modules --cov-report=html
```
(pytest-cov plugin not currently in requirements, but would work if installed)

**Current Status:**
- 62 tests across unit, integration, and component layers
- Test suite covers: database (WAL + write queue), orchestrator (semaphore + concurrent execution), authentication, endpoints, rate limiting, security gates
- Known gaps: frontend (no Playwright/Cypress), full end-to-end flows beyond /api/search, some error paths in wrappers (sherlock, spiderfoot)

## Test Types

**Unit Tests:**
- Scope: Single function or small component in isolation
- Example: `test_wal_mode()` — tests PRAGMA journal_mode is active after startup
- Example: `test_init_creates_async_client()` — tests OathnetClient initializes httpx.AsyncClient with correct headers
- Mocking: respx for network, fixtures for database
- Location: `tests/unit/`, `tests/test_*.py` (most tests are unit)

**Integration Tests:**
- Scope: Multiple components working together (e.g., FastAPI + database + authentication)
- Example: `test_full_nexus_flow()` — login → admin stats (requires session cookie + DB)
- Example: `test_login_429_after_five_attempts()` — authentication + slowapi rate limiter
- Setup: Dependency override to inject test fixtures into FastAPI app
- Location: `tests/integration/`, `tests/test_endpoints.py`

**E2E Tests:**
- Not formalized in codebase (no Playwright, no real browser automation)
- Closest equivalent: `test_full_nexus_flow()` which simulates browser-like behavior (credentials, cookies)

## Common Patterns

**Async Testing (via pytest-asyncio):**
```python
# ✅ Decorator + async def
@pytest.mark.asyncio
async def test_write_serialization(tmp_db: DatabaseManager) -> None:
    """Fire 50 concurrent writes — all must succeed."""
    insert_sql = "INSERT INTO quota_log (...) VALUES (...)"
    
    # Create 50 concurrent tasks
    tasks = [
        tmp_db.write_await(insert_sql, params)
        for i in range(50)
    ]
    
    # Wait for all — if any fails, gather() raises
    await asyncio.gather(*tasks)
    
    # Verify result
    rows = await tmp_db.read_all("SELECT COUNT(*) as cnt FROM quota_log")
    assert rows[0]["cnt"] == 50
```

**Sync Test with Async Fixtures:**
```python
# ✅ Sync test can use async fixtures (pytest-asyncio manages event loop)
def test_init_creates_async_client(client: OathnetClient) -> None:
    """Fixture 'client' is async fixture, test is sync."""
    assert isinstance(client._client, httpx.AsyncClient)
```

**Error Testing:**
```python
@pytest.mark.asyncio
async def test_module_error_delivered_to_queue():
    """Module exception must be delivered to result queue, not raised."""
    orchestrator = TaskOrchestrator()
    test_exc = ValueError("Test error")
    
    orchestrator.submit("failing_mod", _failing_module(test_exc), is_oathnet=False)
    
    results = {}
    async for name, result in orchestrator.results():
        results[name] = result
    
    # Exception is in result dict, not raised
    assert isinstance(results["failing_mod"], ValueError)
    assert str(results["failing_mod"]) == "Test error"
```

**JWT/Token Testing:**
```python
@pytest.mark.asyncio
async def test_jwt_roundtrip():
    """Create, encode, decode token — verify all claims intact."""
    token = _create_token("alice", "admin")
    assert isinstance(token, str) and len(token) > 20
    
    decoded = _decode_token(token)
    assert decoded["sub"] == "alice"
    assert decoded["role"] == "admin"
    assert "exp" in decoded
    assert "iat" in decoded
    assert "jti" in decoded
    
    # Tamper test: flip last 4 chars — must raise 401
    tampered = token[:-4] + "AAAA"
    with pytest.raises(HTTPException) as exc_info:
        _decode_token(tampered)
    assert exc_info.value.status_code == 401
```

**Database Write Testing (with wait):**
```python
@pytest.mark.asyncio
async def test_startup_shutdown_persists(tmp_path: Path) -> None:
    """Data written before shutdown must be readable after restart."""
    db_path = tmp_path / "persist_test.db"
    
    # First manager: write and shutdown
    mgr1 = DatabaseManager(db_path=db_path)
    await mgr1.startup()
    await mgr1.write_await(
        "INSERT INTO searches (...) VALUES (...)",
        ("2026-01-01T00:00:00Z", "testuser", "127.0.0.1", "test_query", ...),
    )
    await mgr1.shutdown()
    
    # Second manager: verify persistence
    mgr2 = DatabaseManager(db_path=db_path)
    await mgr2.startup()
    row = await mgr2.read_one("SELECT username FROM searches WHERE query = ?", ("test_query",))
    await mgr2.shutdown()
    
    assert row is not None
    assert row["username"] == "testuser"
```

## Configuration

**pytest.ini (5 lines):**
```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
testpaths = tests
pythonpath = . api
```

**Meaning:**
- `asyncio_mode = auto`: pytest-asyncio auto-detects `@pytest.mark.asyncio` without needing `asyncio_fixture_loop` everywhere
- `asyncio_default_fixture_loop_scope = function`: each async fixture gets its own event loop (not shared across tests)
- `testpaths = tests`: only look for tests in `tests/` directory
- `pythonpath = . api`: modules importable as `from api.db import db` (not relative imports)

## Test Execution & CI

**Local Execution:**
```bash
pytest                      # Run all 62 tests
pytest -v --tb=short       # Verbose, short tracebacks
pytest tests/unit/         # Run only unit tests
pytest -k "test_db"        # Run tests matching "test_db"
```

**GitHub Actions / CI:**
- Not visible in current codebase (no `.github/workflows/`)
- Manual testing cycle: developer runs `pytest` before commit

**Before Phase 15 Execution:**
- Requirement: test suite must pass with exit code 0
- Baseline: 62 tests passing (current state)
- Refactor constraint: must preserve all 62 tests (no tests removed)
- New tests: may be added if new functionality requires it

---

*Testing analysis: 2026-04-19*
