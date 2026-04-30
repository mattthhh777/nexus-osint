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
| **Status** | **Planned (4/4 PLAN.md drafted)** |
| **Planned** | 2026-04-29 → 2026-04-30 |
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

*Roadmap created: 2026-03-30 | Last updated: 2026-04-30 (Phase 16 planning complete — 4 PLAN.md drafted, ready for Sonnet execution)*
