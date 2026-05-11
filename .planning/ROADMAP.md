# NexusOSINT — v4.0 Roadmap

**Milestone:** Low-Resource Agent Architecture & Hardening
**Target:** 1vCPU / 1GB RAM VPS — maximum capability from minimum hardware
**Phases:** 8 (sequential with one parallel opportunity)
**Created:** 2026-03-30

---

## Dependency Chain

```
Phase 03 (F1 Audit) ──► Phase 04 (F2 SQLite) ──► Phase 05 (F3 Async) ──► Phase 06 (F4 Memory)
                                                                                    │
                                                                          ┌─────────┼─────────┐
                                                                          ▼                   ▼
                                                                Phase 07 (F6 Stack)    Phase 08 (F5 Docker)
                                                                          │                   │
                                                                          └─────────┬─────────┘
                                                                                    ▼
                                                                          Phase 09 (F7 Security)
                                                                                    │
                                                                                    ▼
                                                                          Phase 10 (F8 Health)
```

**Recommended serial order:** 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10

---

## Previous Milestone (v3.0.0 — Complete)

| Phase | Plans | Status | Completed |
|-------|-------|--------|-----------|
| 1. Meridian CSS Token Migration | 7/7 | Complete | 2026-03-26 |
| 2. XSS Sanitization | 2/2 | Complete | 2026-03-26 |

*9 plans total, 16/16 requirements met*

---

## Phases

### Phase 03: F1 — Codebase Audit (GATE)

| Field | Value |
|-------|-------|
| **Status** | **Complete** |
| **Completed** | 2026-03-31 |
| **Effort** | 1 session |
| **Risk** | NONE (documentation only) |
| **Deliverable** | AUDIT-REPORT.md (17 findings: 3 CRIT, 4 HIGH, 6 MED, 4 LOW) |
| **Gate** | ✅ User approved findings → all phases unlocked |

---

### Phase 04: F2 — SQLite Hardening

| Field | Value |
|-------|-------|
| **Status** | **Complete** |
| **Completed** | 2026-03-31 |
| **Depends on** | Phase 03 |
| **Effort** | 1 session |
| **Risk** | LOW |
| **Findings** | FIND-01 (WAL), FIND-11 (quota_log) |

**Sub-tasks:** WAL mode + PRAGMAs, single persistent connection, asyncio.Queue write serializer (new `api/db.py`), schema consolidation, bootstrap test suite.

**Key files:** `api/main.py`, `api/db.py`, `tests/`

**Verification:** ✅ `PRAGMA journal_mode` returns `wal`; 50 concurrent writes without lock errors; all tests pass.

**Plans:** 1/1 complete
- [x] 04-01-PLAN.md — WAL mode + single connection + write queue + test bootstrap

---

### Phase 05: F3 — Async Agent Orchestration

| Field | Value |
|-------|-------|
| **Status** | **Complete** |
| **Completed** | 2026-04-01 |
| **Depends on** | Phase 04 |
| **Effort** | 1 session |
| **Risk** | MEDIUM |
| **Findings** | FIND-02 (fire-forget), FIND-08 (subprocess cleanup) |

**Sub-tasks:** TaskOrchestrator with dual Semaphore (Global=5, OathNet=3) + queue bridge + task registry (new `api/orchestrator.py`), fix audit log via direct await.

**Key files:** `api/orchestrator.py`, `api/main.py`

**Verification:** ✅ Semaphore ceiling enforced; zero task leaks; audit log via direct await; 5/5 orchestrator tests pass.

**Plans:** 1/1 complete
- [x] 05-01-PLAN.md — TaskOrchestrator with dual semaphore + queue bridge

**Note:** Orchestrator built and tested but NOT yet wired into `_stream_search`. Integration deferred to Phase 05b (separate scope).

---

### Phase 06: F4 — Memory-Disciplined Architecture

| Field | Value |
|-------|-------|
| **Status** | **Complete** |
| **Completed** | 2026-04-02 |
| **Depends on** | Phase 05 |
| **Effort** | 1 session |
| **Risk** | LOW |
| **Findings** | FIND-05 (unbound buffer), FIND-10 (session pool — resolved Phase 11) |

**Sub-tasks:** ~~Generator pipelines for serializers~~ (not needed — SSE requires complete JSON per event), breach serialize cap at 200, bound Sherlock response body to 512KB, ~~OathnetClient singleton~~ (done Phase 11), tracemalloc instrumentation + `/health/memory` admin endpoint, `/health` enriched with RSS + cache stats, Sherlock async conversion (eliminate deprecated `asyncio.new_event_loop`), ~~admin query optimization~~ (done Phase 11).

**Key files:** `api/main.py`, `modules/sherlock_wrapper.py`

**Verification:** ✅ 23/23 tests pass; serializer capped; Sherlock async; tracemalloc active; /health has rss_mb + cache_entries.

**Plans:** 1/1 complete
- [x] 06-01-PLAN.md — Memory Guards + Sherlock Async + Health Instrumentation

**Pending verification on VPS:** RSS < 200MB after startup + 10 searches.

---

### Phase 07: F6 — Stack Modernization

| Field | Value |
|-------|-------|
| **Status** | **Complete** |
| **Completed** | 2026-04-06 |
| **Depends on** | Phase 06 |
| **Effort** | 1-2 sessions |
| **Risk** | MEDIUM |
| **Findings** | FIND-10 (complete), FIND-16 (anchored) |

**Sub-tasks:** Python 3.12 compatibility + upgrade, dependency cleanup, tenacity removal, FIND-16 anchor.

**Key files:** `requirements.txt`, `api/main.py`, `Dockerfile`, `pytest.ini`

**Verification:** ✅ 27/27 tests green on Python 3.12.13; tenacity removed; FIND-16 anchored; FastAPI lifespan migration complete.

**Plans:** 3/3 complete
- [x] 07-01-PLAN.md — Test gate + rollback runbook
- [x] 07-02-PLAN.md — Dependency cleanup + FIND-16
- [x] 07-03-PLAN.md — Python 3.12 Dockerfile upgrade

---

### Phase 08: F5 — Docker Optimization

| Field | Value |
|-------|-------|
| **Status** | **Complete** |
| **Completed** | 2026-04-06 |
| **Depends on** | Phase 06 |
| **Effort** | Rolled into Phase 07 (commit acd2f68) |
| **Risk** | LOW |

**Sub-tasks:** Multi-stage Dockerfile, Python-based privilege drop (no gosu), COPY --chown layer fusion, uvicorn extras removed, .dockerignore expanded, memory limits + swap tuning in compose.

**Key files:** `Dockerfile`, `entrypoint.sh`, `docker-compose.yml`, `.dockerignore`, `requirements.txt`

**Verification:** ✅ Image 225MB (25MB under 250MB target); 27/27 tests green; psutil watchdog active.

---

### Phase 09: F7 — Security Hardening

| Field | Value |
|-------|-------|
| **Status** | Pending |
| **Depends on** | Phase 07 |
| **Effort** | 2-3 sessions |
| **Risk** | MEDIUM |
| **Findings** | FIND-03, FIND-04, FIND-06, FIND-07, FIND-09, FIND-12, FIND-13, FIND-14 |

**Sub-tasks:** Eliminate inline onclick handlers (11+ sites), CSP strict (remove unsafe-inline), JWT httpOnly completion, slowapi per-endpoint rate limiting, JWT_SECRET fail-hard, SpiderFoot target validation, user count limit (50), blacklist fail-closed, localStorage hardening, rate limit comment fix.

**Key files:** `static/js/render.js`, `static/js/auth.js`, `static/js/cases.js`, `static/index.html`, `nginx.conf` (protected), `api/main.py`

**Verification:** Zero CSP violations; no nx_token in localStorage; 11th search/min returns 429; malformed SpiderFoot target returns 400; blacklist fail-closed.

**Plans:** 4 plans
- [x] 09-01-PLAN.md — Backend safety gates: JWT_SECRET fail-hard, blacklist fail-closed, SpiderFoot validator, MAX_USERS cap
- [ ] 09-02-PLAN.md — slowapi per-endpoint rate limiting + remove legacy _check_rate
- [ ] 09-03-PLAN.md — Frontend inline handler purge (73 sites) + bootstrap.js + cases.js localStorage hardening
- [ ] 09-04-PLAN.md — nginx.conf strict CSP + D-13 security headers (PROTECTED FILE — human gate)

---

### Phase 10: F8 — Health Monitoring

| Field | Value |
|-------|-------|
| **Status** | **Complete** |
| **Completed** | 2026-04-08 |
| **Depends on** | Phase 08, Phase 09 |
| **Effort** | 1 session |
| **Risk** | LOW |

**Sub-tasks:** Real `/health` endpoint (RSS, CPU%, active tasks, semaphore slots, WAL size, uptime), memory watchdog (>80% warn, >85% reduce semaphore, <75% restore), graceful shutdown (drain orchestrator → flush DB → close), degradation modes (NORMAL/REDUCED/CRITICAL).

**Key files:** `api/main.py`, new `api/watchdog.py`, `api/orchestrator.py`, `docker-compose.yml`

**Verification:** `/health` returns all 5 new fields (TestClient verified); 62/62 tests pass; docker stop human verification deferred.

**Plans:** 3/3 complete
- [x] 10-01-PLAN.md — Singleton orchestrator + DegradationMode enum + soft-gate ceiling
- [x] 10-02-PLAN.md — Watchdog module + lifespan integration + /health enrichment + _agents_paused elimination
- [x] 10-03-PLAN.md — docker-compose stop_grace_period 35s + uvicorn --timeout-graceful-shutdown 30

---

## Summary

| Phase | Feature | Sessions | Risk | Status | Completed |
|-------|---------|----------|------|--------|-----------|
| 03 | F1: Audit | 1 | NONE | ✅ Complete | 2026-03-31 |
| 04 | F2: SQLite | 1 | LOW | ✅ Complete | 2026-03-31 |
| 05 | F3: Async | 1 | MED | ✅ Complete | 2026-04-01 |
| 06 | F4: Memory | 1 | LOW | ✅ Complete | 2026-04-02 |
| 07 | F6: Stack | 1-2 | MED | ✅ Complete | 2026-04-06 |
| 08 | F5: Docker | 1 | LOW | ✅ Complete | 2026-04-06 |
| 09 | F7: Security | 2-3 | MED | ✅ Complete | 2026-04-08 |
| 10 | F8: Health | 1 | LOW | ✅ Complete | 2026-04-08 |
| 11 | Cost Opt. | 4 | LOW | ✅ Complete | 2026-04-02 |

**Completed:** 9/9 phases (22 plans)
**Remaining:** 0 phases
**Milestone v4.0.0 COMPLETE**

---

## Requirements Coverage

| Requirement | Phase | Findings Addressed |
|-------------|-------|--------------------|
| F1: Codebase audit with severity report | 03 | All 17 findings |
| F2: SQLite WAL + write serialization | 04 | FIND-01, FIND-11 |
| F3: Async orchestration TaskGroup + Semaphore(5) | 05 | FIND-02, FIND-08 |
| F4: Memory-disciplined architecture < 200MB | 06 | FIND-05, FIND-10 |
| F5: Docker multi-stage < 250MB + OOM protection | 08 | — |
| F6: Python 3.12+ + dependency modernization | 07 | FIND-10, FIND-16 |
| F7: CSP + JWT httpOnly + rate limiting + validation | 09 | FIND-03, FIND-04, FIND-06, FIND-07, FIND-09, FIND-12, FIND-13, FIND-14 |
| F8: Health monitoring + graceful degradation | 10 | — |

**v4.0 requirements mapped:** 8/8
**Findings mapped:** 15/17 (FIND-15, FIND-17 not prioritized — acceptable patterns)

### Phase 11: Cost Optimization

| Field | Value |
|-------|-------|
| **Status** | **Complete** |
| **Completed** | 2026-04-02 |
| **Depends on** | Phase 04 |
| **Effort** | 4 sessions |
| **Risk** | LOW |

**Sub-tasks:** TTL response caching for external APIs, singleton OathnetClient with connection reuse, HTTP client consolidation (httpx only — remove requests+aiohttp), replace .fetchall() with streaming in db.py, migrate OathnetClient to httpx.AsyncClient, exponential backoff for SpiderFoot polling, cache _load_users() with mtime invalidation.

**Key files:** `api/main.py`, `api/db.py`, `modules/oathnet_client.py`, `modules/sherlock_wrapper.py`, `requirements.txt`

**Verification:** ✅ 14/14 observable truths confirmed. Identical search results; only httpx in requirements; zero .fetchall() in hot paths; OathnetClient singleton.

**Plans:** 3/3 plans complete
- [x] 11-01-PLAN.md — OathnetClient async httpx migration + singleton pattern
- [x] 11-02-PLAN.md — HTTP library consolidation (remove aiohttp + requests)
- [x] 11-03-PLAN.md — DB streaming reads + _load_users cache
- [x] 11-04-PLAN.md — TTL response cache + SpiderFoot exponential backoff

---

## Milestone v4.1 — Results UX: Data completeness & presentation

**Started:** 2026-04-15
**Backfilled into roadmap:** 2026-04-19 (phases 12–14 existed on disk but were not registered)

### Phase 12: v4.1 Pre-gate — commit deployed files + delete backup zips + CSP fix

| Field | Value |
|-------|-------|
| **Status** | **Complete** |
| **Completed** | 2026-04-15 |
| **Depends on** | Phase 11 |
| **Effort** | 1 session |
| **Risk** | LOW |

**Sub-tasks:** commit files already deployed to VPS, delete `css.zip` / `js.zip` emergency backups (D-08), fix CSP typo `form-ancestors` → `frame-ancestors` in `/js/` block (introduced Phase 09-04).

**Key files:** `nginx.conf`, deployed static/ files, `.planning/PROJECT.md`, `.planning/STATE.md`

**Verification:** ✅ CSP frame-ancestors active; backups removed; PROJECT.md updated with v4.1 scope.

**Plans:** Pre-gate work — no PLAN files (gate work only)

---

### Phase 13: v4.1 Data Instrumentation — admin endpoint for breach extra_fields discovery

| Field | Value |
|-------|-------|
| **Status** | **Complete** |
| **Completed** | 2026-04-15 |
| **Depends on** | Phase 12 |
| **Effort** | 1 session |
| **Risk** | LOW |
| **Tests** | 62/62 passed |

**Sub-tasks:** in-memory `_seen_breach_extra_keys: set[str]` accumulator in `_serialize_breaches()`, admin-only `GET /api/admin/breach-extra-keys` endpoint (Depends(get_admin_user) + RL_ADMIN_LIMIT).

**Key files:** `api/main.py`

**Architecture decision:** in-memory set over new SQLite table — `extra_fields` never persisted, container lifetime sufficient for sampling, zero migration risk, zero write-queue pressure. Safe under GIL without explicit lock.

**Security:** only key names stored (never values); admin-only gate; no PII leakage path.

**Verification:** ✅ Endpoint returns sorted key list + count. Consumed by Phase 14 whitelist.

**Plans:** 1/1 plan complete
- [x] 13-01-SUMMARY.md — Instrumentation endpoint + whitelist seed for Phase 14

---

### Phase 14: Visual Polish — surgical redesign of 12 friction points

| Field | Value |
|-------|-------|
| **Status** | **Complete** |
| **Completed** | 2026-04-18 |
| **Depends on** | Phase 13 |
| **Effort** | 1 session (13 steps + regression sweep) |
| **Risk** | MED (frontend-only but 12 surgical touchpoints) |

**Goal:** elevate the UI from "good open-source" to "commercial intel tool" parity (Dehashed / SpyCloud / Hunter.io), without rewriting components.

**Non-goals:** new features, framework migration, backend changes, brand repaint, CSP changes.

**Key files:** `static/css/tokens.css`, `static/css/components.css`, `static/css/reset.css`, `static/css/layout.css`, `static/js/render.js`, `static/js/utils.js`, `api/modules/xbox_module.py` (error payload passthrough)

**Canonical amber confirmed:** `#f0a030` (Meridian `--color-accent`). `#f59e0b` from original brief does not exist in codebase — discarded.

**Plans:** 1/1 complete
- [x] 14-01-PLAN.md — Surgical redesign of 12 friction points (13 steps, all committed)

---

### Phase 15: Refactor main.py into layered architecture (routes → services → repositories → models → core/utils)

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 14
**Plans:** 1/1 plans complete

**Scope:** audit current `main.py` monolith, propose layered architecture with clear import rules, define safe migration order (zero breaking changes), identify risks.

**Deliverable for execution:** final directory structure, granular reversible refactor checklist, inter-layer import contract, per-step "done" criteria.

**Constraints:** zero breaking changes during migration; FastAPI + SQLite + Docker compatibility preserved; each step reversible via git.

Plans:
- [x] TBD (run /gsd:plan-phase 15 to break down) (completed 2026-04-22)

### Phase 16: Sherlock false-positive filter + Thordata proxy integration

| Field | Value |
|-------|-------|
| **Status** | **✅ COMPLETE (2026-05-01)** |
| **Planned** | 2026-04-29 → 2026-04-30 |
| **Completed** | 2026-05-01 |
| **Depends on** | Phase 15 |
| **Effort** | 2-3 sessions (Sonnet implements) |
| **Risk** | MEDIUM (outbound proxy + scoring rewrite + frontend state contract) |

**Goal:** Reduce Sherlock detection false-positives via multi-signal confidence scoring AND route Sherlock outbound traffic through Thordata residential rotating proxy to bypass DigitalOcean IP blocks (LinkedIn / Instagram / TikTok / etc).

**Requirements:** PHASE16-CONFIG, PHASE16-BUDGET, PHASE16-PROXY, PHASE16-FP-FILTER, PHASE16-BUG-FIXES, PHASE16-NEGATIVE-MARKERS, PHASE16-USERNAME-VALIDATOR, PHASE16-BUDGET-CIRCUIT, PHASE16-HEALTH-METRICS, PHASE16-LIFESPAN-PROXY-CHECK, PHASE16-SERVICE-WIRING, PHASE16-FRONTEND-STATE-RENDER, PHASE16-LIKELY-BADGE, PHASE16-NEGATIVE-MARKERS-AUDIT, PHASE16-E2E-VERIFICATION

**Constraints:** zero regression on Phase 06 F4 body cap (512KB global); no expansion of Phase 14 D-06 4-field display ceiling; Phase 15 leaf-module rule for `api/config.py` and `api/schemas.py` preserved; `httpx.AsyncClient` only (no `requests`/`aiohttp`); CLAUDE.md "Não Confie no Frontend" enforced — backend-only thresholds, validators, budget enforcement; brand Amber/Noir untouched.

**Wave-based execution order:**
- Wave 1: Plan 01 (foundation — config + budget tracker)
- Wave 2: Plan 02 (sherlock_wrapper rewrite — proxy + scoring + bug fixes)
- Wave 3: Plan 03 (route wiring — validator + circuit breaker + /health metrics + lifespan)
- Wave 4: Plan 04 (frontend state render + negative-markers audit + E2E tests + deploy)

Plans:
- [x] 16-01-PLAN.md — Configuration foundation: 6 env vars in api/config.py + api/budget.py daily tracker + .env.example
- [x] 16-02-PLAN.md — Sherlock engine rewrite: Thordata proxy injection (sticky session, 1× rotate retry) + multi-signal confidence scoring (status/text/size, 0-100, threshold-based 3-state) + real streaming body cap (256KB) + cf-mitigated detection + httpx.TimeoutException fix + audit log with SHA256 hash
- [x] 16-03-PLAN.md — Route wiring: SherlockUsernameRequest pydantic validator + budget circuit breaker in service layer + extended SSE serializer (state/confidence/likely/proxy_used) + /health admin-gated thordata sub-object + lifespan non-blocking proxy health check
- [x] 16-04-PLAN.md — Frontend state rendering (renderSocial state-branched, Unverified badge, muted likely cards) + module_error UX (budget_exceeded/invalid_username) + negative-markers manual validation audit (5 platforms) + E2E SSE round-trip tests + VPS deploy

---

## Milestone v4.2 — Database Migration (SQLite → PostgreSQL)

**Defined:** 2026-05-07 | **Timeline:** 6-10 weeks / 9 phases | **Stack target:** PostgreSQL 16-alpine + asyncpg 0.31 + Alembic 1.13 async + SQLAlchemy 2.0 Core + Redis 7 Alpine cache

**Locked params:** UUID PKs all tables · JSONB payload on `searches` · pool max_size=10 / min_size=2 · `max_connections=20` · nexus `mem_limit=2500MB` · postgres `mem_limit=768MB` · `shared_buffers=256MB` · `work_mem=8MB` · `shm_size=256MB` · greenfield drop `token_blacklist`/`rate_limits` · preserve `searches`+`quota_log` · `pg_dump` 7d · SQLite snapshot 30d.

**Open Risks:** R-01 nexus mem 2500MB tight (Phase 23 = gate, OOM → 2700MB). R-02 UUID +30% idx on dropped tables (accepted). R-03 JSONB scope creep (accepted). R-04 PG READ COMMITTED ≠ SQLite SERIALIZABLE (Phase 22 RMW audit critical).

---

### Phase 17: v4.2 Pre-Migration Audit & DB Abstraction Layer

**Goal:** Discipline before driver swap — audit SQL dialect violations and introduce a thin repository layer so Phase 22 driver swap is contained to one module.
**Requirements:** DBM-01, DBM-02, DBM-03, DBM-04
**Depends on:** Phase 16
**Risk:** LOW — still on SQLite at end of phase
**Plans:** 3/3 plans complete

**Deliverable:** `grep -rE "AUTOINCREMENT|INSERT OR REPLACE|datetime\(|strftime\(|rowid|fetchone\(|fetchall\("` audit report; `SQL_INVENTORY.md`; `?`→`$N` placeholder map; `db.fetch_one/fetch_all/execute/transaction` repository layer wrapping aiosqlite; all call sites refactored to use it.

**Avoids:** PITFALLS Pitfall 1 (dialect drift), Pitfall 4 (asyncpg API differs), sed-replace disaster.

Plans:
- [x] 17-01-PLAN.md — SQL inventory + placeholder map + rowid fix (DBM-01, DBM-03, DBM-04)
- [x] 17-02-PLAN.md — fetch_*/execute/transaction abstraction + DatabaseError (DBM-02 base)
- [x] 17-03-PLAN.md — contain aiosqlite to api/db.py + call-site refactor (DBM-02 closure)

**Verification note (2026-05-08):** Phase 17 focused tests pass (`13 passed`). Full suite is `121 passed, 2 failed`; remaining failures are pre-existing/out-of-scope rate-limit and endpoint fixture issues documented in `17-03-SUMMARY.md`.

---

### Phase 18: Redis7 Cache Backend

**Goal:** Replace process-local `cachetools.TTLCache` with shared Redis7 cache so duplicate OSINT calls are avoided across restarts/workers and cache observability is no longer tied to an in-memory object.
**Requirements:** CACHE-01, CACHE-02, CACHE-03, CACHE-04, CACHE-05, CACHE-06, CACHE-07, CACHE-08, CACHE-09, CACHE-10
**Depends on:** Phase 17
**Risk:** MEDIUM — cache touches hot search path, but must fail open and preserve search output semantics
**Plans:** 2/2 plans complete

**Deliverable:** `redis:7-alpine` service on private `internal` network with no public port mapping; async `api/cache.py` contract with Redis backend and in-memory fallback; search cache migrated from sync `TTLCache` to async cache helpers; `/health` exposes cache backend/reachable/hit/miss/error stats; `cachetools` removed after migration.

**Avoids:** Process-local cache misses after restart, cache observability coupled to `search_service`, Redis outage causing search HTTP 500s, cache storing raw OathNet responses.

Plans:
- [x] 18-01-PLAN.md — Redis runtime/config + async cache backend + lifecycle wiring
- [x] 18-02-PLAN.md — Search-service Redis migration + health stats + `cachetools` removal

**Verification note (2026-05-09):** Phase 18 targeted tests pass (`9 passed`); `python -m compileall api` passes; `TTLCache|cachetools|_api_cache` grep returns no matches in `api` and `requirements.txt`.

---

### Phase 19: Postgres Container + Compose Wiring (parallel deploy)

**Goal:** Stand up Postgres alongside SQLite without cutover risk. App still on SQLite at end of phase.
**Requirements:** DBM-05, DBM-06, DBM-07, DBM-08, DBM-09, DBM-10
**Depends on:** Phase 18
**Risk:** MEDIUM — VPS RAM envelope tight; nexus `mem_limit` reduction observable in production
**Status:** COMPLETE
**Plans:** 2/2 plans executed

**Deliverable:** `docker-compose.yml` with `postgres:16-alpine`, named volume `postgres_data`, healthcheck, `condition: service_healthy` gating on nexus, password as Docker secret, `mem_limit=768MB`, `shm_size=256MB`, tuned `command:` flags (`shared_buffers=256MB`, `work_mem=8MB`, `max_connections=20`, `idle_in_transaction_session_timeout=60s`), no public port mapping. Nexus `mem_limit` reduced to 2500MB.

**Avoids:** Pitfalls 7 (OOM), 8 (startup race), 9 (volume permissions — named volume not bind), Anti-Pattern 4 (public Postgres).

Plans:
- [x] 19-01: Postgres service + secrets + memory wiring
- [x] 19-02: Compose validation + Hetzner parallel deploy smoke

**Verification note (2026-05-09):** Local and VPS `docker compose config --quiet` pass; Hetzner `nexus-postgres` is healthy; `pg_isready -U nexus -d nexusosint` accepts connections; public `/health` is healthy; Postgres has no public 5432 mapping; `DATABASE_URL` is absent so Nexus remains on SQLite.

---

### Phase 20: Schema-as-Code + Alembic Async + Test Infra

**Goal:** Schema defined and reviewed before any data touches it. Test infra works on real PG before code is written against PG.
**Requirements:** DBM-11, DBM-12, DBM-13, DBM-14, DBM-15, DBM-16, DBM-17, DBM-18, DBM-19
**Depends on:** Phase 19
**Risk:** MEDIUM — type-mapping landmines silent until Phase 21
**Status:** COMPLETE
**Plans:** 1/1 plans complete

**Deliverable:** `alembic init -t async migrations`; baseline migration with `MetaData`/`Table` for all tables (greenfield schema using TIMESTAMPTZ / BOOLEAN / JSONB / UUID `gen_random_uuid()` / `TEXT[]`); `pgcrypto` extension enabled; per-table indexes including FK indexes (Postgres does NOT auto-index FKs); CHECK constraints (not ENUM) for status fields; `searches.payload JSONB` + GIN index; template-database test fixtures; `docker-compose.test.yml` with tmpfs PG on port 5433.

**Verification:** `\d+ table_name` confirms TIMESTAMPTZ; `grep -i "TIMESTAMP[^T]" migrations/` returns zero; FK index cross-check passes.

**Avoids:** Pitfall 2 (type mapping), Performance Trap "Missing indexes on FKs".

Plans:
- [x] 20-01: Postgres schema and test infra

**Verification note (2026-05-10):** `docker compose -f docker-compose.test.yml up -d test-postgres` passed; `alembic upgrade head` passed against live test Postgres; `pytest tests/test_db.py tests/test_db_stream.py -q` returned `10 passed`; schema grep found no `TIMESTAMP` without TZ, `CREATE TYPE`, or `ENUM`.

---

### Phase 21: Data Port Script (`searches` only)

**Goal:** Greenfield + selective preserve. `searches` is the only table with historical value.
**Requirements:** DBM-20, DBM-21, DBM-22, DBM-23
**Depends on:** Phase 20
**Risk:** MEDIUM — type fixups must be exact; row-count parity is the safety net
**Plans:** 1/1 plans complete

**Deliverable:** `scripts/port_searches.py` using `asyncpg.copy_records_to_table` in 1000-row batches; type fixups (ISO TEXT → datetime → TIMESTAMPTZ; CSV `modules_run` → `TEXT[]`; INTEGER `success` → BOOLEAN; legacy NULL payload → `'{}'::jsonb`); row-count parity assertion; idempotent (truncate-then-load on rerun); timed on staging copy of production.

**Avoids:** Pitfall 11 (cutover data loss — script tested before maintenance window).

Plans:
- [x] 21-01: Idempotent searches port script

**Verification note (2026-05-10):** `pytest tests/test_port_searches.py -q` returned `6 passed`; `pytest tests/test_db.py tests/test_db_stream.py tests/test_port_searches.py -q` returned `16 passed`; CLI truncate guard exits before mutation unless `--confirm-truncate truncate-and-port-searches` is supplied.

---

### Phase 22: Repository Layer Switch + Code Audit Pass 2

**Goal:** Swap implementation behind Phase 17 abstraction. Audit isolation-level race conditions specifically (PG READ COMMITTED ≠ SQLite SERIALIZABLE).
**Requirements:** DBM-24, DBM-25, DBM-26, DBM-27, DBM-28, DBM-29, DBM-30, DBM-31
**Depends on:** Phase 21
**Risk:** HIGH — most code-touching phase; missed RMW pattern = silent lost-update bug in production
**Plans:** 1/1 plans complete

**Deliverable:** `api/db.py` rewritten on asyncpg pool (max_size=10, min_size=2, command_timeout=30); `_writer_loop` and `asyncio.Queue` deleted (lines 34, 46-47, 193-222 of current `api/db.py`); `?` → `$N` placeholders rewritten at all call sites; `INSERT OR REPLACE` → `ON CONFLICT DO UPDATE`; every `SELECT then UPDATE` reviewed and replaced with atomic `UPDATE col = col + 1` or `SELECT FOR UPDATE`; pool always inside `async with`; `idle_in_transaction_session_timeout=60s`; `/health` exposes `pool.get_idle_size()`.

**Avoids:** Pitfall 5 (cancellation leaks), Pitfall 6 (RMW races), Anti-Pattern 1 (re-implementing the queue).

Plans:
- [x] 22-01: asyncpg driver swap

**Verification note (2026-05-10):** `pytest tests/test_db.py tests/test_db_stream.py tests/test_db_abstraction.py tests/test_health.py tests/test_endpoints.py tests/integration/test_phase16_routes.py tests/test_port_searches.py -q` returned `39 passed`; runtime DB-path anti-pattern grep found no SQLite writer queue, `INSERT OR`, or forbidden future imports in Phase 22 files; RMW audit found no update sites.

---

### Phase 23: Concurrency & Memory Stress Test (GATE)

**Goal:** Verify new architecture under load matching production burst patterns BEFORE the irreversible cutover.
**Requirements:** DBM-32, DBM-33, DBM-34, DBM-35, DBM-36, DBM-37
**Depends on:** Phase 22
**Risk:** HIGH — gate for cutover; OOM here = bump nexus `mem_limit` to 2700MB before Phase 24
**Plans:** 1/1 plans complete

**Deliverable:** Test scenario: 10 concurrent agents × N scans + `cancel_all` mid-burst, repeated; `pg_stat_activity` clean (zero `idle in transaction`) after each cycle; `docker stats postgres` peak < 768MB; `docker stats nexus` peak < 2500MB; `/health` reports `pool.get_idle_size()` recovering between bursts; counter consistency under concurrency verified; slow-query log reviewed.

**Gate criteria:** All four pass → proceed to Phase 24. Any OOM → revisit `mem_limit` to 2700MB and re-run; any pool leak → fix in Phase 22 and re-run; never enter Phase 24 with red metrics.

**Avoids:** Discovering OOM or pool leaks in production.

Plans:
- [x] 23-01: Postgres pool stress gate

**Verification note (2026-05-10):** `scripts/stress_postgres_pool.py` passed 10-concurrency burst + cancellation cycles; app-container gate returned `rows=762 counter=762 idle_in_transaction=0 pool_size=10 pool_idle_size=10`; Docker stats stayed below limits (`postgres=36.8MiB`, `nexus=75.54MiB` observed); `/health` recovered `db.idle_size` from 2 to 2.

---

### Phase 24: Cutover (maintenance window, ≤ 30 min) — IRREVERSIBLE

**Goal:** Execute the documented playbook exactly. No improvisation in the maintenance window.
**Requirements:** DBM-38, DBM-39, DBM-40, DBM-41, DBM-42, DBM-43, DBM-44, DBM-45, DBM-46
**Depends on:** Phase 23 (gate green)
**Risk:** CRITICAL — irreversible; rollback is "restore SQLite snapshot + revert image tag"
**Plans:** 1/1 plans complete

**Deliverable:**
1. Pre-flight: SQLite snapshot (`cp nexus.db nexus.db.pre-pg-$(date +%Y%m%d)`), Docker image tagged `pre-pg-backup`, `git rev-parse HEAD` saved to runbook.
2. Read-only mode flag flipped → 503 + `Retry-After` for writes; GETs continue.
3. Drain `orchestrator._registry` to zero (poll, max 60s).
4. Run `port_searches.py` → assert row-count parity → run `SELECT setval(pg_get_serial_sequence(...))` on every serial PK (only if any sequences remain — UUID-all may eliminate).
5. Flip `DATABASE_URL` env to `postgresql+asyncpg://...` → `docker compose up -d --build nexus`.
6. Smoke test: `/health`, sample `/search`, `/admin`, dashboard.
7. Read-only mode off; announce restored.
8. SQLite file kept read-only on disk for 30 days.

**Rollback playbook:** must be tested on staging beforehand. Failure to test = abort Phase 24.

**Avoids:** Sequence collisions, lost in-flight writes, no rollback path.

**Verification note (2026-05-10):** Production cutover complete. SQLite snapshot
`audit.db.pre-pg-20260510T210438Z` retained read-only, `DATABASE_URL` flipped to
Postgres, `port_searches.py` asserted 19-row parity, `/health` reports healthy
Postgres pool (`db.size=2`, `db.idle_size=2`), and public `/` returns 200.

Plans:
- [x] 24-01-PLAN.md — Hetzner PostgreSQL cutover

---

### Phase 25: Post-Migration Tuning + Backup Hardening (1-week observation)

**Goal:** Tuning needs real production traffic data; defer optimization until measured.
**Requirements:** DBM-47, DBM-48, DBM-49, DBM-50, DBM-51, DBM-52, DBM-53
**Depends on:** Phase 24 (1 week production traffic minimum)
**Risk:** LOW — observation phase
**Plans:** 1/1 plans complete; DBM-47/48 remain time-gated until one week of production traffic is available

**Deliverable:** `pg_stat_statements` review → partial indexes on confirmed hot paths only; per-table autovacuum tuning for `searches` if churn justifies (`autovacuum_vacuum_scale_factor=0.05`); bloat report (`n_dead_tup / n_live_tup`) baselined; `pg_dump` cron at 03:00 with 7-day retention; restore drill on staging passes; `aiosqlite` removed from `requirements.txt`; CLAUDE.md updated to reflect F2 obsoletion (asyncio.Queue write serializer removed, SQLite section archived).

**Avoids:** Pre-optimizing without data; backup-you-have-not-restored anti-pattern (Pitfalls 10, 12).

Plans:
- [x] 25-01-PLAN.md — Backup hardening and Postgres docs

**Execution note (2026-05-11):** Backup automation is active on the VPS at
03:00 with 7-day retention, restore drill passed against
`nexusosint-20260511T033857Z.sql.gz` with `searches_count=19`, bloat baseline
shows `searches` live `19` / dead `0`, `requirements.txt` has no `aiosqlite`,
and `CLAUDE.md` now reflects the Postgres/asyncpg architecture. DBM-47/48 are
not complete yet because the Phase 24 cutover happened on 2026-05-10; earliest
honest one-week traffic review is 2026-05-17.

---

*Roadmap created: 2026-03-30 | Last updated: 2026-05-09 (Redis7 cache backend folded into v4.2 as Phase 18; Postgres phases shifted 18-24 → 19-25)*
