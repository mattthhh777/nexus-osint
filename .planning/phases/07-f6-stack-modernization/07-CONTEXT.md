# Phase 07: F6 Stack Modernization - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Modernize the Python runtime to 3.12, remove unused dependencies, fix the duplicate 429 handler (FIND-16), and produce a full rollback runbook.

**Already complete — do NOT re-do:**
- `python-jose → PyJWT`: Done. `PyJWT==2.9.0` is in requirements.txt, `import jwt` in `api/main.py`.
- `requests → httpx`: Done in Phase 11. `aiohttp` and `requests` are gone from requirements.txt.

**In scope for this phase:**
- Extend integration test suite to 4 tests (gate for 3.12 upgrade)
- Write full rollback runbook before touching Dockerfile/requirements
- Upgrade Dockerfile base image: `python:3.11-slim` → `python:3.12-slim`
- Verify all tests pass under 3.12 (upgrade gate)
- Remove `tenacity==8.5.0` from requirements.txt (unused, unwired)
- Fix FIND-16: remove duplicate 429 check in `modules/oathnet_client.py` (lines ~179-180)

</domain>

<decisions>
## Implementation Decisions

### Test Gate (before 3.12 upgrade)
- **D-01:** Extend `tests/test_endpoints.py` to 4 tests before the upgrade: existing `test_full_nexus_flow` (login + admin stats), existing `test_unauthorized_access`, + new `test_health_endpoint` (`/health` returns 200 with expected keys), + new `test_jwt_roundtrip` (encode → decode with PyJWT, verifies HS256 roundtrip and expiry). All 4 must be green before Dockerfile change.

### Rollback
- **D-02:** Full rollback runbook required in a dedicated doc (e.g., `DEPLOY.md` or inline in phase plan) before any file is changed. Must include: `pip freeze > requirements.lock.pre-py312.txt`, `docker tag nexus:latest nexus:pre-py312-backup`, and step-by-step revert commands. Matches the CLAUDE.md F6 rollback template exactly.

### Dependency Cleanup
- **D-03:** Remove `tenacity==8.5.0` from `requirements.txt`. It is unused and unwired throughout the codebase. SpiderFoot already has manual exponential backoff. If retry logic is needed in the future, adding it back is a one-line change.

### Claude's Discretion
- Whether to pin Python 3.12 to a digest after the upgrade stabilizes (planner decides based on Docker image size impact).
- Whether to add `--check-untyped-defs` or any mypy/pyright flags during 3.12 compat check.
- FIND-16 fix approach (remove duplicate block at lines ~179-180 in oathnet_client.py — approach is obvious from CONCERNS.md).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Guidelines
- `CLAUDE.md` §F6 — Rollback strategy template, upgrade order requirements (test suite green first, rollback documented first)

### Files Being Modified
- `requirements.txt` — Remove tenacity, verify no other unused packages
- `Dockerfile` — Protected file; change base image only (`python:3.11-slim` → `python:3.12-slim`)
- `modules/oathnet_client.py` — FIND-16: duplicate 429 check at lines ~174 and ~179-180

### Test Gate
- `tests/test_endpoints.py` — Existing 2 tests to extend to 4; conftest.py may need reading for `tmp_db` fixture
- `pytest.ini` — Test runner config (modified recently)

### Issue Reference
- `.planning/codebase/CONCERNS.md` §"Duplicate HTTP 429 Handling" — Exact location and fix approach for FIND-16

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/test_endpoints.py`: 2 existing async integration tests using `httpx.ASGITransport` — extend this file, do NOT create a new one.
- `api/main.py` lines 314-330: JWT encode/decode functions (`_create_token`, `_verify_token`) — use these directly in the JWT roundtrip test.

### Established Patterns
- Tests use `httpx.AsyncClient` with `ASGITransport(app=app)` — keep this pattern for new tests.
- `tmp_db` fixture (in conftest.py) overrides the DB dependency — new tests must use this fixture.
- PyJWT already imported and working: `import jwt` / `from jwt.exceptions import InvalidTokenError as JWTError`.

### Integration Points
- `modules/oathnet_client.py`: FIND-16 fix is isolated to one method, no cascading changes expected.
- `Dockerfile`: multi-stage build already in place (`builder` + `runtime` stages) — only the `FROM python:3.11-slim` lines need updating (both stages).

</code_context>

<specifics>
## Specific Ideas

- The 3.12 upgrade is specifically `python:3.11-slim → python:3.12-slim` in both Dockerfile stages — not a local Python upgrade.
- Docker image must remain < 250MB after upgrade (carry-forward constraint).
- Rollback runbook format: matches CLAUDE.md template verbatim (`pip freeze > requirements.lock.pre-python312.txt`, `docker tag nexus:latest nexus:pre-python312-backup`).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 07-f6-stack-modernization*
*Context gathered: 2026-04-06*
