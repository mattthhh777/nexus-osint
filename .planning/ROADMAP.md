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

### Phase 03 — F1: Codebase Audit (GATE)

| Field | Value |
|-------|-------|
| **Status** | In Progress |
| **Effort** | 1 session |
| **Risk** | NONE (documentation only) |
| **Deliverable** | AUDIT-REPORT.md (17 findings: 3 CRIT, 4 HIGH, 6 MED, 4 LOW) |
| **Gate** | User approves findings → unlocks all subsequent phases |

---

### Phase 04 — F2: SQLite Hardening

| Field | Value |
|-------|-------|
| **Status** | Pending |
| **Depends on** | Phase 03 |
| **Effort** | 1-2 sessions |
| **Risk** | LOW |
| **Findings** | FIND-01 (WAL), FIND-11 (quota_log) |

**Sub-tasks:** WAL mode + PRAGMAs, single persistent connection, asyncio.Queue write serializer (new `api/db.py`), schema consolidation, bootstrap test suite.

**Key files:** `api/main.py`, new `api/db.py`, new `tests/`

**Verification:** `PRAGMA journal_mode` returns `wal`; 50 concurrent writes without lock errors; all tests pass.

---

### Phase 05 — F3: Async Agent Orchestration

| Field | Value |
|-------|-------|
| **Status** | Pending |
| **Depends on** | Phase 04 |
| **Effort** | 2-3 sessions |
| **Risk** | **MEDIUM** (highest risk — _stream_search refactor) |
| **Findings** | FIND-02 (fire-forget), FIND-08 (subprocess cleanup) |

**Sub-tasks:** TaskOrchestrator with TaskGroup + Semaphore(5) + task registry (new `api/orchestrator.py`), parallelize _stream_search independent modules, fix audit log via DatabaseWriter queue, subprocess hardening in spiderfoot_wrapper.

**Key files:** new `api/orchestrator.py`, `api/main.py` (~400 lines restructured), `modules/spiderfoot_wrapper.py`

**Verification:** Semaphore ceiling enforced; zero task leaks; 100 searches = 100 audit entries; SSE sequence matches golden file.

---

### Phase 06 — F4: Memory-Disciplined Architecture

| Field | Value |
|-------|-------|
| **Status** | Pending |
| **Depends on** | Phase 05 |
| **Effort** | 2 sessions |
| **Risk** | LOW |
| **Findings** | FIND-05 (unbound buffer), FIND-10 (session pool, partial) |

**Sub-tasks:** Generator pipelines for serializers, bound Sherlock response to 512KB, OathnetClient singleton, tracemalloc instrumentation + `/health/memory` endpoint, admin query optimization.

**Key files:** `api/main.py`, `modules/sherlock_wrapper.py`, `modules/oathnet_client.py`

**Verification:** RSS < 200MB after startup + 10 searches; Sherlock truncates > 512KB; single OathnetClient instance.

---

### Phase 07 — F6: Stack Modernization

| Field | Value |
|-------|-------|
| **Status** | Pending |
| **Depends on** | Phase 06 |
| **Effort** | 2 sessions |
| **Risk** | **HIGH** (3 library changes — strict sub-task order) |
| **Findings** | FIND-10 (complete), FIND-16 (duplicate 429) |

**Sub-tasks (strict order):** Python 3.12 compatibility, python-jose → PyJWT, OathnetClient async rewrite (requests → httpx.AsyncClient), dependency cleanup + fix duplicate 429.

**Key files:** `requirements.txt`, `api/main.py`, `modules/oathnet_client.py`, `Dockerfile` (protected)

**Verification:** All tests pass on 3.12; JWT roundtrip with PyJWT; OathNet identical results; fewer pip packages.

---

### Phase 08 — F5: Docker Optimization

| Field | Value |
|-------|-------|
| **Status** | Pending |
| **Depends on** | Phase 06 |
| **Effort** | 1 session |
| **Risk** | LOW |
| **Parallel with** | Phase 07 (different files) |

**Sub-tasks:** Multi-stage Dockerfile (builder + runtime, pinned digest), resource limits in compose (800m RAM, 2800m swap), health check upgrade, deploy runbook.

**Key files:** `Dockerfile` (protected), `docker-compose.yml` (protected), new `DEPLOY.md`

**Verification:** `docker images` < 250MB; survives 50 concurrent requests; health check detects pressure.

---

### Phase 09 — F7: Security Hardening

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

---

### Phase 10 — F8: Health Monitoring

| Field | Value |
|-------|-------|
| **Status** | Pending |
| **Depends on** | Phase 08, Phase 09 |
| **Effort** | 1-2 sessions |
| **Risk** | LOW |

**Sub-tasks:** Real `/health` endpoint (RSS, CPU%, active tasks, semaphore slots, WAL size, uptime), memory watchdog (>80% warn, >85% reduce semaphore, <75% restore), graceful shutdown (drain orchestrator → flush DB → close), degradation modes (NORMAL/REDUCED/CRITICAL).

**Key files:** `api/main.py`, new `api/watchdog.py`, `api/orchestrator.py`

**Verification:** `/health` returns all fields; memory pressure triggers degradation; `docker stop` completes < 35s; all queued logs written before shutdown.

---

## Summary

| Phase | Feature | Sessions | Risk | Key Metric |
|-------|---------|----------|------|------------|
| 03 | F1: Audit | 1 | NONE | 17 findings documented |
| 04 | F2: SQLite | 1/1 | Complete   | 2026-03-31 |
| 05 | F3: Async | 2-3 | Complete    | 2026-04-01 |
| 06 | F4: Memory | 2 | LOW | < 200MB resting RSS |
| 07 | F6: Stack | 2 | **HIGH** | Python 3.12 + PyJWT + httpx |
| 08 | F5: Docker | 1 | LOW | < 250MB image |
| 09 | F7: Security | 2-3 | MED | CSP strict, no unsafe-inline |
| 10 | F8: Health | 1-2 | LOW | Graceful degradation |
| 11 | Cost Optimization | 1-2 | LOW | httpx only, TTL cache, zero fetchall |

**Total estimated effort:** 13-19 sessions
**Highest risk:** Phase 05 (F3, _stream_search refactor), Phase 07 (F6, triple library swap)

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

### Phase 11 — Cost Optimization

| Field | Value |
|-------|-------|
| **Status** | Planned |
| **Depends on** | Phase 04 |
| **Effort** | 1-2 sessions |
| **Risk** | LOW |

**Sub-tasks:** TTL response caching for external APIs, singleton OathnetClient with connection reuse, HTTP client consolidation (httpx only — remove requests+aiohttp), replace .fetchall() with streaming in db.py, migrate OathnetClient to httpx.AsyncClient, exponential backoff for SpiderFoot polling, cache _load_users() with mtime invalidation.

**Key files:** `api/main.py`, `api/db.py`, `modules/oathnet_client.py`, `modules/sherlock_wrapper.py`, `requirements.txt`

**Verification:** Identical search results before/after; only httpx in requirements; zero .fetchall() in hot paths; OathnetClient instantiated once.

**Plans:** 1/1 plans complete

Plans:
- [ ] 11-01-PLAN.md — OathnetClient async httpx migration + singleton pattern
- [ ] 11-02-PLAN.md — HTTP library consolidation (remove aiohttp + requests)
- [ ] 11-03-PLAN.md — DB streaming reads + _load_users cache
- [ ] 11-04-PLAN.md — TTL response cache + SpiderFoot exponential backoff

---

*Roadmap created: 2026-03-30*
