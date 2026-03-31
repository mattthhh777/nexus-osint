# NexusOSINT v4.0 — F1 Codebase Audit Report

**Date:** 2026-03-30
**Auditor:** Claude Opus 4.6 (automated static analysis)
**Scope:** All source files in nexus_osint repository
**Commit:** 9eedfe1 (master)
**Milestone Gate:** This audit must be reviewed and approved before any v4.0 code changes.

---

## Executive Summary

**17 findings** across the full codebase: **3 CRITICAL, 4 HIGH, 6 MEDIUM, 4 LOW**.

The platform is functionally solid for v3.0 production but has architectural gaps that will surface under concurrent load on a 1GB RAM VPS. The three critical issues — missing WAL mode, untracked async tasks, and ephemeral JWT secret — are all addressable with targeted changes in early v4.0 phases.

No active security vulnerabilities were found. XSS protections from v3.0.0 Phase 2 are intact. Frontend uses `esc()`/`escAttr()`/`sanitizeImageUrl()` consistently. Authentication uses HttpOnly cookies with bcrypt hashing.

**No test suite exists.** Every code change is a regression gamble until tests are bootstrapped in F2.

---

## Findings

### CRITICAL (P0) — Must fix before scaling

---

#### FIND-01: No WAL Mode on SQLite

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **Category** | Reliability |
| **Location** | `api/main.py:373-404` (`_init_audit_db()`) |
| **Fix Phase** | F2 (SQLite Hardening) |
| **Effort** | S |

**Description:** SQLite is initialized without any PRAGMA statements. Default journal mode is DELETE, which is the slowest and least concurrent mode. Under concurrent searches, writers block readers and vice versa, leading to "database is locked" errors.

**Evidence:**
```python
async def _init_audit_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(AUDIT_DB) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS searches (...)""")
        # No PRAGMA journal_mode=WAL
        # No PRAGMA synchronous=NORMAL
        # No PRAGMA busy_timeout
        await db.commit()
```

**Impact:** Under 3+ concurrent searches, audit log writes will contend with rate limiter reads. On a 1vCPU VPS with no write serialization, "database is locked" errors are near-certain under moderate load.

**Fix:** Add to `_init_audit_db()`:
```python
await db.execute("PRAGMA journal_mode=WAL")
await db.execute("PRAGMA synchronous=NORMAL")
await db.execute("PRAGMA busy_timeout=5000")
```

---

#### FIND-02: Fire-and-Forget Audit Logging

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **Category** | Reliability |
| **Location** | `api/main.py:1081-1089` |
| **Fix Phase** | F3 (Async Agent Orchestration) |
| **Effort** | M |

**Description:** Search audit log is written via `asyncio.create_task()` without tracking. The task is not awaited, not registered, and not monitored. If the server shuts down before the task completes, the audit entry is lost.

**Evidence:**
```python
# ── Audit log (fire and forget) ─────────────────────
asyncio.create_task(_log_search(
    username=username, ip=client_ip, query=query,
    query_type=q_type, mode=req.mode,
    modules_run=list(set(ran)),
    breach_count=breach_count,
    stealer_count=stealer_count,
    social_count=social_count,
    elapsed_s=elapsed,
))
```

**Impact:** Audit log entries can be silently lost on shutdown or crash. No task registry means no visibility into pending writes. This is the only `asyncio.create_task()` without tracking in the entire codebase.

**Fix:** Route through DatabaseWriter queue (F2) so writes are guaranteed to flush before shutdown, or use FastAPI `BackgroundTasks` with graceful shutdown handler.

---

#### FIND-03: JWT_SECRET Ephemeral Fallback

| Field | Value |
|-------|-------|
| **Severity** | CRITICAL |
| **Category** | Security |
| **Location** | `api/main.py:46-56` |
| **Fix Phase** | F7 (Security Hardening) |
| **Effort** | S |

**Description:** If `JWT_SECRET` is not set in `.env`, the application generates an ephemeral secret derived from `OATHNET_API_KEY` + 8 bytes of randomness. This secret changes on every restart, invalidating all active sessions.

**Evidence:**
```python
_jwt_fallback = hashlib.sha256(
    (OATHNET_API_KEY + "nexusosint_jwt_v3_" + os.urandom(8).hex()).encode()
).hexdigest()
JWT_SECRET = os.getenv("JWT_SECRET") or _jwt_fallback
if not os.getenv("JWT_SECRET"):
    import warnings
    warnings.warn("JWT_SECRET not set in .env — using ephemeral secret...")
```

**Impact:** Every container restart logs out all users. The warning is only visible in stdout, not in the web UI. If `.env` is misconfigured in production, this silently degrades user experience.

**Fix:** In production (`ENV=prod`), fail hard on startup if `JWT_SECRET` is not set. Keep ephemeral fallback only for development.

---

### HIGH (P1) — Fix before production hardening

---

#### FIND-04: CSP with 'unsafe-inline'

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Category** | Security |
| **Location** | `nginx.conf:58` |
| **Fix Phase** | F7 (Security Hardening) |
| **Effort** | M |

**Description:** Content Security Policy includes `script-src 'self' 'unsafe-inline'`, which allows arbitrary inline JavaScript execution. This significantly weakens XSS protection provided by the escaping layer.

**Root Cause:** `index.html` has 11+ inline `onclick`, `oninput`, `onkeydown` handlers and an inline `<script>init();</script>` block. `admin.html` has inline CSS. These require `'unsafe-inline'` to function.

**Impact:** An XSS bypass that gets past the `esc()` wrapper would execute in the page context. CSP is the last line of defense, and `unsafe-inline` defeats it.

**Fix:** Migrate all inline event handlers to `addEventListener()` with `data-*` attributes. Extract inline scripts to external JS files. Then remove `'unsafe-inline'` from CSP.

---

#### FIND-05: Unbound HTML Response Buffering in Sherlock

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Category** | Memory |
| **Location** | `modules/sherlock_wrapper.py:298` |
| **Fix Phase** | F4 (Memory-Disciplined Architecture) |
| **Effort** | S |

**Description:** `await resp.text(errors="ignore")` reads the entire HTTP response body into memory with no size limit. If a target platform returns an unusually large page (>10MB), this could exhaust memory on the 1GB VPS.

**Evidence:**
```python
body = await resp.text(errors="ignore")
```
The comment above (line 297) notes "Read a limited amount of HTML to avoid large payloads" but no limit is implemented.

**Impact:** Single large response could spike RSS by 10-100MB. With 5 concurrent Sherlock checks (Semaphore ceiling), worst case is 500MB of buffered HTML.

**Fix:** Add explicit size limit: `body = await resp.content.read(524288)` (512KB) then decode.

---

#### FIND-06: No User Count Limit

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Category** | Security |
| **Location** | `api/main.py:1204-1234` (`admin_create_user`) |
| **Fix Phase** | F7 (Security Hardening) |
| **Effort** | S |

**Description:** The user creation endpoint has no limit on how many users can be created. `_load_users()` (line 217) reads the entire `users.json` into memory as a dict. With hundreds of users, this dict grows unbounded.

**Impact:** A compromised admin account could create thousands of users, growing the in-memory dict and degrading performance. Low likelihood but easy to prevent.

**Fix:** Add check: `if len(users) >= 50: raise HTTPException(400, "User limit reached")`

---

#### FIND-07: SpiderFoot Target Not Validated

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Category** | Security |
| **Location** | `api/main.py:1275` |
| **Fix Phase** | F7 (Security Hardening) |
| **Effort** | S |

**Description:** The SpiderFoot scan target is passed directly from the user's search query to the SpiderFoot API without format validation. While SpiderFoot itself should validate inputs, defense-in-depth requires server-side validation.

**Impact:** Malformed targets could trigger unexpected SpiderFoot behavior or waste scan resources.

**Fix:** Validate target matches expected patterns (email, domain, IP, username regex) before forwarding.

---

### MEDIUM (P2) — Address during relevant phase

---

#### FIND-08: Subprocess Timeout Cleanup

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Category** | Reliability |
| **Location** | `modules/spiderfoot_wrapper.py:294-323` |
| **Fix Phase** | F3 (Async Agent Orchestration) |
| **Effort** | M |

**Description:** `subprocess.run()` with `timeout=timeout` kills the process on timeout, but if SpiderFoot forks child processes, those children may survive as zombies.

**Mitigation:** SpiderFoot is typically single-process. Python 3.11+ handles subprocess cleanup better. Risk is low but worth hardening.

**Fix:** After `subprocess.TimeoutExpired`, explicitly `proc.kill()` + `proc.wait()` to reap children.

---

#### FIND-09: localStorage Stores Sensitive Breach Data

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Category** | Security |
| **Location** | `static/js/cases.js:4,39,52,60,69` |
| **Fix Phase** | F7 (Security Hardening) |
| **Effort** | M |

**Description:** The cases system stores full search results (including breach passwords, emails, stealer logs) in `localStorage`. While localStorage is same-origin only, any XSS bypass would grant access to all stored case data.

**Mitigation:** XSS protections (esc(), CSP) prevent exfiltration. Acceptable risk for an OSINT tool, but should be hardened.

**Fix:** Store only case metadata (query, timestamp, module list) in localStorage. Load full results on demand.

---

#### FIND-10: requests.Session Without Pool Limits

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Category** | Performance |
| **Location** | `modules/oathnet_client.py:127` |
| **Fix Phase** | F6 (Stack Modernization) |
| **Effort** | S |

**Description:** `requests.Session()` created per OathnetClient instance without explicit connection pool configuration. Default pool size (10) is reasonable, but not explicitly configured.

**Fix:** Replaced entirely when OathnetClient migrates to `httpx.AsyncClient` in F6.

---

#### FIND-11: quota_log Table Created Twice

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Category** | Maintainability |
| **Location** | `api/main.py:114` and `api/main.py:1137` |
| **Fix Phase** | F2 (SQLite Hardening) |
| **Effort** | S |

**Description:** `CREATE TABLE IF NOT EXISTS quota_log` appears in both `_save_quota()` (line 114) and `admin_stats()` (line 1137). Harmless but indicates schema initialization is scattered.

**Fix:** Consolidate all table creation into `_init_audit_db()`.

---

#### FIND-12: Blacklist Check Fails Open

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Category** | Security |
| **Location** | `api/main.py:325` |
| **Fix Phase** | F7 (Security Hardening) |
| **Effort** | S |

**Description:** `_check_blacklist()` returns `False` (token not blacklisted) if the database is unavailable. This means revoked tokens are accepted when the DB is down.

**Contrast:** The rate limiter correctly fails closed (line 163 — blocks requests on DB error).

**Fix:** Change to fail-closed: return `True` (token IS blacklisted) on DB error, consistent with rate limiter pattern.

---

#### FIND-13: Rate Limit Comment Mismatch

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Category** | Maintainability |
| **Location** | `api/main.py:688` |
| **Fix Phase** | F7 (Security Hardening) |
| **Effort** | S |

**Description:** Comment says "20 searches/minute" but code implements `10/60` (10 per 60 seconds). Misleading for future maintainers.

**Fix:** Update comment to match code, or update code to match intent.

---

### LOW (P3) — Informational, fix opportunistically

---

#### FIND-14: innerHTML += Pattern in Pagination

| Field | Value |
|-------|-------|
| **Severity** | LOW |
| **Category** | Performance |
| **Location** | `static/js/render.js:935` |
| **Fix Phase** | F7 (Security Hardening) |
| **Effort** | M |

**Description:** `list.innerHTML += newItems.map(...).join('')` re-parses the entire existing DOM on each pagination load. Should use `insertAdjacentHTML('beforeend', ...)` instead.

---

#### FIND-15: Bare except Exception Catches (25+ instances)

| Field | Value |
|-------|-------|
| **Severity** | LOW |
| **Category** | Maintainability |
| **Location** | `api/main.py` (various lines) |
| **Fix Phase** | — (not prioritized) |
| **Effort** | L |

**Description:** 25+ `except Exception as exc:` catches throughout `_stream_search` and admin endpoints. All are properly logged or re-raised. No silent failures found. This is acceptable for a resilient streaming architecture where individual module failures should not crash the entire search.

**Assessment:** No action required. The pattern is intentional for fault isolation in SSE streaming.

---

#### FIND-16: Duplicate HTTP 429 Check

| Field | Value |
|-------|-------|
| **Severity** | LOW |
| **Category** | Maintainability |
| **Location** | `modules/oathnet_client.py:173-180` |
| **Fix Phase** | F6 (Stack Modernization) |
| **Effort** | S |

**Description:** HTTP 429 status handled twice — lines 173-174 and 179-180. Second check is unreachable.

**Fix:** Remove duplicate block during OathnetClient async rewrite.

---

#### FIND-17: Imports Inside Functions

| Field | Value |
|-------|-------|
| **Severity** | LOW |
| **Category** | Performance |
| **Location** | `api/main.py:762,1026,1346,1377,1409,1426` |
| **Fix Phase** | — (not prioritized) |
| **Effort** | S |

**Description:** Module imports inside functions (`from modules.oathnet_client import OathnetClient`) add micro-overhead per call. Acceptable for lazy loading pattern — keeps startup fast and avoids circular imports.

**Assessment:** No action required. Pattern is intentional.

---

## Architecture Assessment

### Codebase Structure

| File | Lines | Role |
|------|-------|------|
| `api/main.py` | 1447 | Backend monolith — all routes, auth, DB, streaming |
| `modules/oathnet_client.py` | 546 | OathNet API client (sync, requests-based) |
| `modules/spiderfoot_wrapper.py` | 530 | SpiderFoot integration (subprocess + httpx) |
| `modules/sherlock_wrapper.py` | 394 | Social media scanner (aiohttp + subprocess) |
| `modules/report_generator.py` | ~100 | HTML report generation with proper escaping |
| `static/js/render.js` | 945 | Frontend rendering (largest JS file) |
| `static/js/export.js` | 735 | Export to JSON/CSV/TXT/PDF |
| `static/js/cases.js` | 127 | Case management (localStorage) |
| `static/js/auth.js` | 106 | Authentication (HttpOnly cookies) |
| `static/js/utils.js` | 99 | Escaping, sanitization, validation |
| `static/index.html` | 360 | Main SPA page |
| `static/admin.html` | ~1426 | Admin panel (inline CSS/JS) |

### Complexity Hotspots

1. **`_stream_search()` (main.py:696-1097)** — 400 lines, sequential module execution. 12 OSINT modules run one after another. Independent modules (Sherlock, IP info, Subdomains, Steam, Xbox, Roblox, GHunt, Minecraft) could run in parallel via `asyncio.gather()` for significant latency reduction.

2. **`admin.html` (~1426 lines)** — Monolithic admin page with all CSS and JS inline. Will be the hardest file to make CSP-compliant in F7.

### What's Working Well

- **XSS protection**: All `innerHTML` uses `esc()` wrapper. `sanitizeImageUrl()` and `sanitizeUrl()` validate protocols. Inline `onerror` handlers replaced with programmatic `addEventListener`. (v3.0.0 Phase 2 work is solid.)
- **Authentication**: JWT in HttpOnly cookies, bcrypt hashing, token revocation via blacklist, rate limiting on login.
- **Nginx security headers**: HSTS (2 years), X-Frame-Options DENY, X-Content-Type-Options, Referrer-Policy, Permissions-Policy — all A+ grade.
- **Docker security**: Non-root execution via gosu, no-new-privileges on Nginx.
- **Rate limiting**: Dual-layer (Nginx + SQLite-backed in-process), persistent across restarts.
- **Error handling**: All 25+ exception catches are logged. No silent failures.

### What Needs Work (addressed by v4.0 features)

- **No WAL mode** → F2
- **No write serialization** → F2
- **No task tracking** → F3
- **No memory bounds** → F4
- **Single-stage Docker** → F5
- **Sync HTTP client** → F6
- **CSP unsafe-inline** → F7
- **No health monitoring** → F8
- **No test suite** → F2 (bootstrap)

---

## Risk Matrix

| Finding | Likelihood | Impact | Risk Score |
|---------|-----------|--------|------------|
| FIND-01 (No WAL) | HIGH (concurrent searches) | MEDIUM (locked DB, lost logs) | **HIGH** |
| FIND-02 (Fire-forget) | LOW (normal ops) | HIGH (data loss on shutdown) | **MEDIUM** |
| FIND-03 (JWT ephemeral) | LOW (if .env correct) | HIGH (all sessions lost) | **MEDIUM** |
| FIND-04 (CSP unsafe-inline) | LOW (requires XSS bypass) | HIGH (full JS execution) | **MEDIUM** |
| FIND-05 (Unbound buffer) | LOW (rare large responses) | HIGH (OOM on 1GB VPS) | **MEDIUM** |
| FIND-06 (No user limit) | LOW (requires admin access) | LOW (memory growth) | **LOW** |
| FIND-07 (SpiderFoot validation) | LOW (defense in depth) | LOW (wasted scan) | **LOW** |

---

## Recommendations Priority

### P0 — Before any v4.0 code (addressed in F2)
1. Enable WAL mode (FIND-01)
2. Bootstrap test suite

### P1 — Early v4.0 phases (F2-F4)
3. Write serialization via asyncio.Queue (FIND-01 complete fix)
4. Replace fire-and-forget with tracked tasks (FIND-02)
5. Bound response buffering (FIND-05)
6. Fix quota_log duplication (FIND-11)

### P2 — Security hardening phase (F7)
7. JWT_SECRET fail-hard in production (FIND-03)
8. Remove CSP unsafe-inline (FIND-04)
9. User count limit (FIND-06)
10. SpiderFoot target validation (FIND-07)
11. Blacklist fail-closed (FIND-12)
12. Rate limit comment fix (FIND-13)

### P3 — Opportunistic
13-17. Low-severity items (FIND-14 through FIND-17)

---

## Gate Approval

**F1 is complete when:**
- [ ] This report has been reviewed by the project owner
- [ ] Severity assignments are approved
- [ ] Phase-to-finding mapping is confirmed
- [ ] ROADMAP.md created with v4.0 phases

**No code changes until this gate is cleared.**

---

*Generated: 2026-03-30 | Auditor: Claude Opus 4.6 | Scope: Full repository*
