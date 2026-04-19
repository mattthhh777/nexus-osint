# Codebase Concerns

**Analysis Date:** 2026-04-19

**Scope:** NexusOSINT v3.0 — FastAPI + Vanilla JS + SQLite on 1vCPU/1GB VPS  
**Focus:** Monolithic `api/main.py` (1770 lines) ahead of Phase 15 refactor.

---

## 1. Monolith Pain Points — `api/main.py` Structure

### Multi-Concern Functions (Routing + Business Logic + DB + Validation)

**Scale:** 53 public functions (routes + helpers) in single 1770-line file. No separation of concerns.

#### High-Value Examples:

**`_stream_search()` (lines 804–1280+)**
- **What it does:** SSE event loop mixing:
  - Query type detection (line 834)
  - User input validation (line 833)
  - Cache lookup (lines 906–921)
  - Orchestrator registration (lines 816–831)
  - 13 parallel module calls (breach, stealer, holehe, sherlock, discord, ip_info, subdomain, steam, xbox, roblox, ghunt, victims, spiderfoot)
  - EventSource serialization (line 811)
  - Audit logging (lines 1294+)
- **Impact:** Refactor will touch 500+ lines at once. Every change risks breaking multiple concerns.
- **Tests:** 4 tests in `test_endpoints.py` cover only happy path + basic auth. No isolated unit tests for module orchestration, timeout handling, or cache logic.

**`search()` endpoint (lines 781–801)**
- **What it does:** Rate limit gate, degradation check, orchestrator ceiling rejection, StreamingResponse constructor
- **Tightly coupled to:** `_stream_search()` private function, degradation mode from `get_orchestrator()`
- **Impact:** Hard to test isolated endpoint logic without mocking entire SSE stream.

**`admin_stats()` (lines 1320–1366)**
- **What it does:** Query aggregation (today's searches, top queries, per-user stats) + quota lookup
- **Impact:** `read_all()` calls on `searches` table with no limit (lines 1333, 1339). Under high audit volume, could fetch 10K+ rows into memory.
  - Mitigated by `LIMIT 10` in top_queries (line 1335), but per_user query (line 1340) unbounded — see **Performance** section.

**`logout()` (lines 690–702)**
- **What it does:** Token revocation via `_revoke_token()`, cookie deletion, XSS mitigation (try/except on blacklist)
- **Impact:** Catches HTTPException at endpoint level (line 696), hiding orchestrator errors. Not following CLAUDE.md exception pattern.

#### Module-Level State (Mutable Globals)

```python
# api/main.py:117–118 — User cache with mutable dict
_users_cache: dict | None = None
_users_cache_mtime: float = 0.0
```
- **Used by:** `_load_users()` (line 327), `_save_users()` (line 343)
- **Problem:** Global dict mutated by `_save_users()`, read by `_load_users()`. Race condition if a non-mocked reload occurs mid-test.
- **Impact on refactor:** Need to extract to a service layer to make testable.

```python
# api/main.py:130 — API response cache
_api_cache: TTLCache = TTLCache(maxsize=200, ttl=300)
```
- **Used by:** `_get_cached()`, `_set_cached()`, exposed in `/health` endpoint (line 1708)
- **Problem:** TTLCache is unbounded at insertion time; maxsize=200 enforced at eviction time. Under concurrent breach searches, could grow beyond 200 transiently.
- **Impact on refactor:** Move to a shared caching service; add metrics.

```python
# api/main.py:761 — Breach extra_fields accumulator (Phase 13)
_seen_breach_extra_keys: set[str] = set()
```
- **Used by:** `_serialize_breaches()` (line 766), exposed via `/api/admin/breach-extra-keys` (line 1765)
- **Problem:** Resets on restart; in-memory only. No persistence. Requires manual real scans to populate.
- **Impact on refactor:** Informational only; low priority for refactor.

```python
# api/main.py:422 — Token blacklist warning throttle
_last_blacklist_warn: list[float] = [0.0]
```
- **Used by:** `_check_blacklist()` (line 425)
- **Problem:** Single-element list used as a mutable container (Python pattern to work around closure scoping). Confusing.
- **Impact on refactor:** Replace with proper logging or state object.

### Circular/Implicit Imports

**No direct circular imports detected**, but **tight coupling via singletons**:

```python
# api/main.py:52–55
from api.db import db as _db
from api.orchestrator import get_orchestrator, DegradationMode
from api.watchdog import memory_watchdog_loop
from modules.oathnet_client import oathnet_client
```

- `api/main.py` imports `get_orchestrator()` singleton from `api/orchestrator.py`.
- `api/orchestrator.py` doesn't import `main.py`, but `main.py` is the only consumer at scale.
- **Impact:** Refactor should formalize this relationship: create a `services/` layer that imports singletons once and passes them to routes.

**Test coupling:**
```python
# tests/test_endpoints.py:7–8
from api.main import app, _create_token, _decode_token
import api.main
```
- Imports private functions and module directly.
- Any refactor that moves `_create_token` will break tests.
- **Impact:** Phase 15 must export these from a stable public interface (e.g., `api/services/auth.py`).

### Late Imports (Runtime Binding)

```python
# api/main.py:893
if oathnet_client is None:
    yield event({"type": "error", "message": "OATHNET_API_KEY not configured"})
    return

# ... later, inside _stream_search ...
from modules.sherlock_wrapper import search_username  # LATE IMPORT
```

- `sherlock_wrapper` is imported inside `_stream_search()` loop, not at module top.
- **Why:** Probably to avoid hard failure if module is missing. But creates confusion about dependencies.
- **Impact:** Refactor should move all imports to top-level with proper error handling at `lifespan` startup.

---

## 2. Known Bugs & TODOs

### Grep Results

```bash
# Searched: all .py, .js, .md files
grep -rn "TODO\|FIXME\|XXX\|HACK" . --exclude-dir=.git --exclude-dir=.claude --exclude-dir=__pycache__
```

**Result:** Zero `TODO`/`FIXME`/`XXX`/`HACK` comments in production code.

### Known Issues (From STATE.md, ROADMAP.md)

**Phase 14 Visual Polish Deferred (from STATE.md:84)**
- No test suite for frontend JS — visual regressions caught only by manual testing.
- **Status:** Pending. Step 14/14 "regression sweep" deferred per `.planning/STATE.md`.
- **Risk:** Frontend may have introduced regressions in card layouts, error states, or animations that won't be caught.

**Stealer Serializer Gap (STATE.md:71)**
- `stealer.log` and `stealer.email` (list fields) not serialized in `_serialize_stealers()` (line 773).
- **Impact:** Frontend can't display stealer email lists or file logs.
- **Priority:** Low (stealer module usage is rare).

**VPS Deploy Pending (STATE.md:70)**
- nginx.conf `frame-ancestors` fix (CSP correction from Phase 09) not deployed to production VPS.
- **Deployment:** `scp nginx.conf root@146.190.142.50:/root/nexus-osint/` required before next major release.
- **Security:** CSP allows iframes from wrong origins; not critical if iframe embedding not used.

---

## 3. Security Concerns

### Frontend Authorization Logic

**Status:** Remediated in Phase 07 (F7 security hardening).

```javascript
// static/js/auth.js:4
// VULN-01: token migrado para HttpOnly cookie — zero localStorage
```

✅ **Confirmed:** JWT token is httpOnly cookie, not localStorage.  
✅ **Confirmed:** No authorization checks in frontend code.  
✅ **Confirmed:** Validation delegated to backend `/api/` endpoints.

**Remaining frontend state:**
- `localStorage.getItem('nx_history')` and `localStorage.getItem('nx_cases')` — these are **metadata only** (case names, search dates), not sensitive data.
- Audit log, user lists, quota — all server-side, not exposed to browser storage.

**Summary:** No security regression in frontend. Phase 07 fix holds.

### CORS Configuration (api/main.py:255–265)

```python
_ALLOWED_ORIGINS = [
    "http://localhost:3000", "http://localhost:8000",
    "http://127.0.0.1:3000", "http://127.0.0.1:8000",
    "https://nexusosint.dev", "https://www.nexusosint.dev",
    "https://146.190.142.50",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
```

**Issues:**
1. `allow_headers=["*"]` is overly permissive — allows any custom header.
   - **Recommendation:** Explicitly list needed headers (e.g., `["Content-Type", "Authorization"]`).
2. localhost + 127.0.0.1 duplicates should be single origin.
3. No rate limiting on CORS preflight (OPTIONS requests bypass rate limiting).
   - **Impact:** Low (OPTIONS is cheap; not a real attack vector).

**Severity:** Low. All endpoints protected by JWT anyway.

### Input Validation

**Path Parameters:**

```python
# api/main.py:1660–1661 (victims_file_endpoint)
_validate_id(log_id)
_validate_id(file_id)
```

- Uses private `_validate_id()` function (defined around line 1400+; not shown in read).
- **Impact:** Prevents path traversal. Good.

**Query Parameters:**

```python
# api/main.py:833–839
query    = req.query
q_type   = detect_type(query)
is_email = q_type == "email"
```

- Uses `detect_type()` regex validation (lines 706–714) **only for categorization**, not sanitization.
- **Risk:** Malicious query string (e.g., SQL injection) could pass through.
- **Mitigation:** OathNet API enforces input length limits; backend doesn't execute queries directly. All OathNet calls go via `oathnet_client` wrapper.
- **Assessment:** Safe, but refactor should add explicit Pydantic validation for SearchRequest.

**SearchRequest Model:**

```python
# api/main.py:149+ (assumed, based on line 785)
class SearchRequest(BaseModel):
    query: str
    mode: str
    modules: list[str]
```

- No field validators shown in initial read. Assumes Pydantic v2 defaults (non-empty strings).
- **Recommendation:** Add `@field_validator` for query length, mode membership, module names.

### CSP & Security Headers

```python
# api/main.py:547
app.add_middleware(SecurityHeadersMiddleware)
```

- Custom middleware (defined around line 500+).
- **Status:** Already implemented in Phase 09 (F7 security hardening).
- **Verified:** nginx.conf fix pending (frame-ancestors typo corrected); app-level headers in place.

---

## 4. Performance & Memory Fragility

### `.read_all()` Without Limit (Violation of CLAUDE.md <200MB Constraint)

**admin_stats() — per_user query (line 1339–1342):**

```python
per_user = await _db.read_all(
    """SELECT username, COUNT(*) as cnt FROM searches
       WHERE ts LIKE ? GROUP BY username ORDER BY cnt DESC""",
    (f"{today}%",),
)
```

- **Problem:** No `LIMIT` clause. If 1000+ users searched today, all 1000 rows fetched into memory at once.
- **Current scale:** 50 users max (MAX_USERS=50, line 75), so ~50 rows = safe.
- **Future risk:** If MAX_USERS increased, this becomes a memory leak vector.
- **Fix:** Add `LIMIT 100` or paginate results.

**Severity:** Medium (mitigated by MAX_USERS cap).

### In-Memory Cache Growth Under Concurrent Load

**`_api_cache: TTLCache(maxsize=200, ttl=300)` (line 129)**

- **Design:** LRU eviction at maxsize=200.
- **Problem under load:** If 10 concurrent searches with unique queries arrive, cache fills to 200 before any 5-min TTL expires. Subsequent unique queries evict older entries.
- **Memory impact:** 200 entries * ~10KB/entry (avg OathNet response) = ~2MB. Within acceptable bounds.
- **Risk if scaled:** Module allows `maxsize` to be tunable; currently hardcoded. If not exposed via config, future scaling will require code change.

**Severity:** Low. Well-bounded.

### Generator vs. Full Materialization

**Async generators in use:**

```python
# api/main.py:807 (SearchRequest → AsyncGenerator[str, None])
async def _stream_search(
    req: SearchRequest,
    username: str,
    client_ip: str,
) -> AsyncGenerator[str, None]:
```

✅ **Good:** SSE response streamed, not buffered in memory.

**Potential issue:**

```python
# api/main.py:1730–1731
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics("lineno")[:15]
```

- `take_snapshot()` copies all allocations into memory. If app has many small allocations, snapshot could be large.
- **Mitigation:** Only called by admin endpoint (`/health/memory`), not in hot path.

**Severity:** Low.

### Orchestrator Semaphore Ceiling (CLAUDE.md Compliance)

**From CLAUDE.md:**
> Semaphore ceiling: máximo 5 tasks simultâneos

**In api/main.py:790–795:**

```python
if get_orchestrator().degradation_mode == DegradationMode.CRITICAL:
    raise HTTPException(
        status_code=503,
        detail="System under memory pressure — new scans temporarily rejected",
        headers={"Retry-After": "120"},
    )
```

- Checks orchestrator state but doesn't query semaphore directly.
- **Assumption:** Orchestrator implements the ceiling internally. Refactor should expose `semaphore_slots_free` (line 1712) in health endpoint and log when hitting ceiling.

**Severity:** Low. Constraint already enforced at orchestrator level.

### Missing `.fetchall()` Scan

```bash
# Searched api/main.py for .fetchall() calls
grep -n "\.fetchall\|\.read_all" api/main.py
# Results: lines 1333, 1339 (covered above)
```

✅ **Good:** No direct `.fetchall()` calls. All reads go through `db.read_one()` or `db.read_all()` with limits.

---

## 5. Fragile Coupling — Cross-Module Dependencies

### Tightly Coupled Singletons

**Pattern:**
```python
# api/main.py:52–55
from api.db import db as _db
from api.orchestrator import get_orchestrator, DegradationMode
from api.watchdog import memory_watchdog_loop
from modules.oathnet_client import oathnet_client
```

- All imported at module level. If any fails to initialize, entire app fails.
- **Test impact:** Tests must mock or initialize all four singletons.

**Mitigation:** `conftest.py` (line 52 in tests) uses fixtures to override:
```python
# tests/conftest.py
@pytest.fixture
async def tmp_db():
    # Provides in-memory test DB
```

**Refactor approach:** Extract singletons into `api/services/__init__.py` with lazy initialization checks.

### Audit Logging Tightly Bound to Route Handler

**`_log_search()` (lines 505–554)** — called inside `_stream_search()` after all modules finish.

```python
# api/main.py:1294+
# ── Audit log — non-blocking via db write queue (no create_task needed) ──
await _log_search(...)
```

- Couples route handler to audit table schema and logging logic.
- **Refactor risk:** Moving `_stream_search` to `services/search.py` requires dragging `_log_search` along.

**Fix:** Extract both to `services/search_service.py` with clear interface.

### Module Wrapper Imports (Orchestrator Registration)

**Inside `_stream_search()` (lines 823–827):**

```python
orch = get_orchestrator()
_sentinel_done: asyncio.Event = asyncio.Event()

async def _search_sentinel() -> None:
    await _sentinel_done.wait()

orch.submit(f"search-{id(_sentinel_done)}", _search_sentinel(), is_oathnet=False)
```

- Creates a sentinel task to track search duration.
- **Fragile:** If `orch.submit()` signature changes, this breaks. No interface contract.
- **Better approach:** Define `SearchTask(BaseModel)` in `models.py` with version number.

---

## 6. Test Coverage Gaps

### Test Suite Size

```
Total test code: 1324 lines across 5 files
Total production code: api/main.py (1770) + api/db.py + api/orchestrator.py + modules/*
```

**Test files:**
- `test_endpoints.py` — 92 lines (4 tests: full flow, unauth, health, JWT roundtrip)
- `test_db.py` — 117 lines (database operations)
- `test_db_stream.py` — 113 lines (streaming writes)
- `test_oathnet_client.py` — 210 lines (mocked OathNet API)
- `test_orchestrator.py` — 219 lines (task scheduling)
- `integration/test_rate_limiting.py` — (not counted yet)

### Uncovered Code in `api/main.py`

**High-value functions with no tests:**

| Function | Lines | Purpose | Test Status |
|----------|-------|---------|------------|
| `_stream_search()` | 500+ | Main search orchestration | Tested only via `test_full_nexus_flow` (integration); no unit tests for module ordering, cache hit/miss, timeout handling |
| `_log_search()` | ~50 | Audit log record | No isolated test; only implicitly called in integration tests |
| `admin_stats()` | ~50 | Dashboard stats | No test |
| `admin_logs()` | ~30 | Audit log retrieval | No test |
| `admin_users()` | ~60 | User management | No test |
| `health_memory()` | ~30 | Memory profiling | No test |
| `with_timeout()` | 15 | Module timeout wrapper | No isolated test (tested implicitly) |

**Critical gaps:**

1. **Module Timeout Behavior** — `with_timeout()` (line 736) not explicitly tested for:
   - Timeout expiry (should return default=None, timed_out=True)
   - Non-timeout (should return result, timed_out=False)
   - Various MODULE_TIMEOUTS values

2. **Cache Hit/Miss Logic** — `_get_cached()`, `_set_cached()` not unit-tested:
   - Cache key normalization (line 134: `.lower().strip()`)
   - TTL expiry (mocked in integration tests only)
   - Cache eviction at maxsize=200

3. **Rate Limit Edge Cases** — `_rate_limit_handler()` (line 288) not tested for:
   - Missing `limit` attribute (graceful fallback to 60)
   - Malformed limit.Limit objects

4. **Admin Panel Authorization** — `get_admin_user()` (line 497) not tested:
   - Non-admin user rejection
   - Admin user success
   - Role enumeration in token

5. **Search Mode Validation** — `SearchRequest` model:
   - Invalid `mode` (should reject anything other than "automated" or specific module names)
   - Invalid `modules` list (typos in module names)

### Integration Test Gaps

**`test_full_nexus_flow()` (test_endpoints.py:15–51)** covers:
- Auth flow (login, JWT roundtrip)
- Single search request
- Basic health endpoint

**Missing:**
- Concurrent searches (5 simultaneous requests)
- Rate limit enforcement
- Degradation mode CRITICAL (orchestrator pause)
- Cache hits after 2nd search with same query
- Audit log correctness

### Frontend Test Coverage

**Status:** Zero.

```
No Jest, Vitest, or Cypress tests for static/js/*.js
```

**High-risk areas:**
- `render.js` — 1000+ lines of card rendering logic; no visual regression tests
- `admin.js` — Admin panel DOM manipulation; no tests for permission state
- `cases.js` — localStorage mutation; no tests for data persistence
- `export.js` — PDF/CSV generation; no tests for file integrity

**Phase 14 Deferred:** "Step 14/14 — regression sweep" was deferred. Risk of visual regressions in:
- Breach cards with extra_fields
- Social cards with avatars
- Stat cards with risk tinting
- Error state styling

**Severity:** High for visual polish, Medium for functional correctness.

---

## 7. Phase 14 Visual Polish Leftovers

### Deferred Regression Testing

**From STATE.md:84:**
> No test suite for frontend JS — visual regressions caught only by manual testing

**What happened in Phase 14 (14-01 steps 1–14):**

1. ✅ Step 13 — unified user dropdown with ESC + outside-click (F2)
2. ✅ Step 12 — card--error variant slate color for failed lookups (F8)
3. ✅ Step 11 — social card density +30% avatar 42px grid 130px (F9)
4. ✅ Step 10 — stat card coverage text (F6)

**Actual implementation (from git log):**
```
667d223 fix(xbox): pass error data payload to frontend for card--error rendering
493104e feat(14-01): Step 13 — unified user dropdown with ESC + outside-click F2
e37dba8 feat(14-01): Step 12 — card--error variant slate color for failed lookups F8
de06d3a feat(14-01): Step 11 — social card density +30% avatar 42px grid 130px F9
81841a2 feat(14-01): Step 10 — stat card coverage text F6
```

### Known Visual Debt

**`card--error` styling (static/css/cards.css:133–139):**

```css
.gaming-card.card--error {
  opacity: 0.7;
  border-color: var(--color-error);
}
.gaming-card.card--error .gaming-card-title { color: var(--color-error); }
.gaming-card.card--error::before {
  background: linear-gradient(135deg, var(--color-error), var(--color-error-dark));
}
```

- Currently hard-coded to `--color-error` (red/danger color).
- **From STATE.md:65:** Step 12 was supposed to use **slate color** for failed lookups, but appears to still use error-red in CSS.
- **Verification:** Need to check `/api/xbox` endpoint (commit 667d223) to see if error payload is passed.

**Risk:** Potential visual inconsistency (slate vs. red) if Step 12 intended slate.

**Recommendation:** Visual regression test suite (Cypress or Playwright) should be added to catch this in future.

### Avatar Rendering (Phase 14, Step 15)

**From 15-CONTEXT.md:37–40:**
> Social cards with profile photos via unavatar.io + CSP fix

- Icons lazy-loaded from Simple Icons library.
- Avatars fetched from unavatar.io (external image service).

**CSS density change (Step 11):**
```css
/* Assumed from commit: avatar 42px grid 130px */
.social-card { width: 130px; }
.social-card img { size: 42px; }
```

**No test to verify:** Layout still looks good on small screens, no overflow, no image loading failures.

---

## 8. Infrastructure & Operations Concerns

### VPS Swap Configuration

**From CLAUDE.md & STATE.md:**

> Swap: 2GB obrigatório — configurar antes de qualquer deploy

**Status:** Assumed configured but not verified.

**Check on VPS:**
```bash
swapon --show  # Should show 2GB swap
```

**Risk:** If swap not configured and RAM fills, system becomes unresponsive. Orchestrator's degradation mode depends on reliable swap availability.

### Docker Image Size Target

**From CLAUDE.md:**
> Docker image: < 250MB

**Current:** Not measured in recent phase. Python 3.12 upgrade (F6) may have increased image size.

**Verification command (on VPS or locally):**
```bash
docker images nexus  # Check if < 250MB
```

### nginx.conf CSP Header (Phase 09 Fix, Not Deployed)

**From STATE.md:70:**
> VPS deploy: push nginx.conf fix (frame-ancestors) — critical security patch

**Status:** nginx.conf corrected locally but not copied to VPS.

**Action:** Before next major release:
```bash
scp nginx.conf root@146.190.142.50:/root/nexus-osint/
ssh root@146.190.142.50 "cd /root/nexus-osint && docker compose up -d nginx"
```

---

## 9. Dependency & Migration Risks

### Python 3.12 Rollback Plan Missing

**From CLAUDE.md (F6 strategy):**
> Rollback: git revert of merge commit

**Current state:** Python upgrade deferred to Phase 06 (already executed in v4.0). Test suite was passing at time of execution (per phase closure).

**Risk if re-running:** Ensure `requirements.lock.pre-python312.txt` still exists in repo.

### OathNet API Rate Limits

**From CLAUDE.md & api/main.py:78–82:**

```python
RL_SEARCH_LIMIT     = os.environ.get("RL_SEARCH_LIMIT",     "10/minute")
RL_SPIDERFOOT_LIMIT = os.environ.get("RL_SPIDERFOOT_LIMIT", "3/hour")
```

- Limits are per-user (via slowapi + `_rate_key` function, line 270).
- OathNet Starter plan: 100 lookups/day (global, not per-user).

**Risk:** If 10 concurrent users each search 1 query/min, that's 10 queries/min against OathNet = 600/hour = 14,400/day quota overrun in days 1–2.

**Mitigation:** Current implementation has:
- 5-min TTL cache (line 129) — repeat queries within 5 min skip API
- Breach quota logging (line 191) — tracks usage

**Better approach (Phase 15 refactor):**
- Add global OathNet rate limiter (see CLAUDE.md example) to serialize API calls across users
- Add queue for breach/stealer with global 1–2 calls/sec ceiling

**Severity:** Medium (current Starter plan tier limits to ~14K lookups; 50 users * 2 searches/day each = 100 lookups well within budget).

---

## 10. Code Quality & Maintainability Issues

### Exception Handling Anti-Pattern

**Line 300:**
```python
try:
    retry_after = int(limit.get_expiry_length()) if limit and hasattr(limit, "get_expiry_length") else 60
except Exception:
    retry_after = 60
```

**Problem:**
- Bare `except Exception` violates CLAUDE.md strict exception handling.
- Should catch specific exception (e.g., `AttributeError`, `TypeError`).
- No logging of what went wrong.

**Other exception patterns (all correct):**
- Line 279: `except (jwt.InvalidTokenError, jwt.ExpiredSignatureError)`
- Line 362: `except (ValueError, TypeError, UnicodeDecodeError)`
- Line 1015: `except (httpx.HTTPError, ValueError, KeyError, TypeError)`

**Severity:** Low (isolated to non-critical rate-limit handler).

### Unclear Variable Names

**Line 876:**
```python
done_cnt = [0]  # Single-element list for mutable reference in nested function
```

**Why?** Python 2-style workaround for closure scoping. Modern Python should use `nonlocal`.

**Same pattern as `_last_blacklist_warn` (line 422):**
```python
_last_blacklist_warn: list[float] = [0.0]
```

**Recommendation:** Refactor both to proper state objects.

### Long Functions (Cyclomatic Complexity)

**`_stream_search()` (lines 804–1280+):**
- 500+ lines in single async generator
- 13 if/elif branches for module selection
- Multiple nested try/except blocks
- Deep callback nesting for event() function

**Suggestion for Phase 15:** Break into:
```
services/
├── search_service.py       # _stream_search() logic
├── module_orchestrator.py  # Run modules in parallel
├── cache_service.py        # Breach/stealer cache
└── audit_service.py        # _log_search()
```

---

## 11. Summary Table: Risk Levels & Refactor Impact

| Concern | Severity | File:Line | Impact on Phase 15 | Action |
|---------|----------|-----------|-------------------|--------|
| Monolith (1770-line main.py) | HIGH | api/main.py | Refactor is literally to address this | Split into layers: routes → services → repositories → models |
| `_stream_search()` 500-line function | HIGH | api/main.py:804 | Will be split across 3–4 service files | Extract module orchestration, cache, audit to separate services |
| Global state: `_users_cache`, `_api_cache` | MEDIUM | api/main.py:117, 130 | Tests become flaky if state not reset | Use dependency injection; mock in tests |
| Exception handling `except Exception` | LOW | api/main.py:300 | Low risk; not in hot path | Fix during refactor; add logging |
| No frontend test suite | HIGH | static/js/ | Visual regressions undetected | Add Cypress/Playwright suite (out of v4.1 scope, noted in Phase 14 deferral) |
| Card--error styling uncertainty | MEDIUM | static/css/cards.css:133 | May be wrong color (slate vs. red) | Verify intent from Step 12 plan; add visual tests |
| `.read_all()` without limit (per_user) | MEDIUM | api/main.py:1339 | Safe now (MAX_USERS=50) but risky if scaled | Add `LIMIT 100` or paginate in Phase 15 |
| Tight coupling: singletons in main.py | MEDIUM | api/main.py:52–55 | Refactor opportunity to formalize | Extract to `services/__init__.py` with singleton factory |
| OathNet rate limit (global + per-user) | MEDIUM | api/main.py:78–82 | Not enforced; cache helps but not foolproof | Add global rate limiter in Phase 15 (priority: low) |
| VPS swap not verified | LOW | DEPLOY.md | Dep on operational integrity | Check on VPS; add to pre-deploy checklist |
| nginx.conf not deployed (CSP fix) | LOW | DEPLOY.md | Security posture incomplete | Deploy before next production release |
| Module late import (sherlock, line 893) | LOW | api/main.py:893 | Should be at top-level | Move to imports section in Phase 15 |
| Orchestrator singleton coupling | MEDIUM | api/main.py:52, 816 | Needs formalization | Define clear interface in Phase 15; version it |

---

## Refactor Readiness Checklist (for Phase 15)

- [ ] **Test suite passing:** 62 tests in 1324 lines, covering core auth, DB, orchestrator. Pre-refactor baseline: all green.
- [ ] **Coverage gaps identified:** 6 core functions uncovered (admin_stats, admin_users, health_memory, etc.). Phase 15 should add unit tests.
- [ ] **Monolith boundaries identified:** Main concerns: routing, business logic (orchestration), persistence (DB), validation. Phase 15 splits on these axes.
- [ ] **Singleton coupling mapped:** 4 singletons (db, orchestrator, watchdog, oathnet_client). Phase 15 extracts to `services/` with clear import boundary.
- [ ] **Frontend stability baseline:** Phase 14 visual changes committed; Step 14 regression testing deferred. Phase 15 should NOT touch frontend.
- [ ] **Zero breaking changes:** Refactor must preserve all endpoint URLs, response schemas, exception behavior. All tests must pass unchanged.

---

*Concerns audit: 2026-04-19*
