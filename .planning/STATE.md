---
gsd_state_version: 1.0
milestone: v4.2.0
milestone_name: Database Migration + Redis7 Cache Fold-In
status: Executing Phase 25
stopped_at: Executing Phase 25 post-migration tuning and backup hardening
last_updated: "2026-05-11T03:35:00-03:00"
progress:
  total_phases: 25
  completed_phases: 24
  total_plans: 38
  completed_plans: 37
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-06 — milestone v4.2)

**Core value:** From the same scan, show 2× more data without additional backend cost — rendering what already arrives in the pipeline.

**Current focus:** Phase 25 — post-migration-tuning-backup-hardening

## Current Position

Phase: 25 (post-migration-tuning-backup-hardening) — EXECUTING
Plan: 1 of 1

## Phase Map

| # | Phase | Status | Notes |
|---|-------|--------|-------|
| 12 | v41-pregate | COMPLETE | Pre-gate commit + zip cleanup |
| 13 | v41-data-instrument | COMPLETE | `/api/admin/breach-extra-keys` + accumulator |
| 14 | visual-polish | COMPLETE | Surgical Results UX polish |
| 15 | refactor-main-py-layers | COMPLETE | Layered architecture refactor |
| 16 | sherlock-false-positive-filter-thordata-proxy-integration | COMPLETE | Confidence scoring + Thordata proxy integration |
| 17 | v4-2-pre-migration-audit-db-abstraction-layer | COMPLETE | SQL inventory + DB abstraction; 3/3 plans complete |
| 18 | redis7-cache-backend | COMPLETE | Redis7 cache replacement; 2/2 plans complete |
| 19 | postgres-container-compose-wiring | COMPLETE | 2/2 plans complete; Postgres healthy in parallel on Hetzner |
| 20 | schema-as-code-alembic-async-test-infra | COMPLETE | Async Alembic + PG test infra verified; 10 DB tests passed |
| 21 | data-port-script-searches-only | COMPLETE | `searches` port script; live PG idempotency verified |
| 22 | repository-layer-switch-code-audit-pass-2 | COMPLETE | asyncpg pool swap + RMW audit verified |
| 23 | concurrency-memory-stress-test | COMPLETE | 10-way burst/cancel stress gate passed |
| 24 | postgres-cutover | COMPLETE | Postgres production cutover passed |
| 25 | post-migration-tuning-backup-hardening | PLANNED | 1-week observation + backups |

## Accumulated Context

### Decisions (v4.1 — all approved 2026-04-15)

- D-01: extra_fields instrumentation approach A+C — admin endpoint + explicit whitelist
- D-02: Phase order: 14 breach before 15 social (higher ROI first)
- D-03: Admin panel polish → v4.2 (out of v4.1 scope)
- D-04: Toggle slider Tier 2.4 dropped
- D-05: SVG brand icons via Lucide + Simple Icons (~50 icons, ~+40KB, lazy-loaded)
- D-06: Social profile data ceiling accepted — Sherlock 4 fields only, no scrapers
- D-07: CLAUDE.md compliance absorbed into DoD of each component phase
- D-08: css.zip + js.zip deleted (VPS permission incident backups)
- CSP fix: form-ancestors → frame-ancestors (typo Phase 09-04, fixed Phase 12)
- Phase 15 D-01: schemas.py is LEAF — only re + pydantic imports, zero api/* or modules/* (enforces import contract)
- Phase 15 D-02: import re kept in main.py (used in detect_type + other guards; cannot remove)
- Phase 15 baseline: test_full_nexus_flow was pre-existing failure (61/62 before Phase 15, not introduced by refactor)
- Phase 16 D-16-01-A: stdlib logging used in api/budget.py (loguru absent from project stack; plans 02-04 must not add loguru)
- Phase 16 D-16-01-B: api/budget.py placed in api/ not modules/ to avoid cross-layer import when health.py reads budget metrics (Pitfall 8)
- Phase 16 D-16-01-C: in-memory budget counters with lazy UTC reset; container restart resets counter (acceptable D-16 trade-off)

### Critical Architecture Insight (F2 pre-check result, Opus session 2026-04-15)

BreachRecord already has 11 typed fields + extra_fields dict that captures ALL
non-KNOWN_FIELDS from OathNet API response. Serializer (api/main.py:757) already
sends "extra": b.extra_fields to the browser. Frontend (render.js:_renderBreachPage)
ignores both discord_id and entire extra dict — this is a data-completeness bug,
not a data-availability issue. Phase 13 discovers real extra keys; Phase 14 renders them.

### Pending Todos

- Phase 06 VPS verification: run RSS measurement on VPS after startup + 10 searches
- Stealer serializer gap: `log` and `email` list fields not serialized — low priority
- VPS deploy: push nginx.conf fix (frame-ancestors) — critical security patch, do before or alongside next deploy

### Roadmap Evolution

- v4.0.0 complete: all 10 phases, 22 plans
- v4.1.0 started: Phase 12 pre-gate complete (2026-04-15)
- 2026-04-19: Backfilled phases 12 (pre-gate), 13 (data-instrument), 14 (visual-polish) into ROADMAP.md — previously only on disk, not registered
- 2026-04-19: Phase 15 added — "Refactor main.py into layered architecture (routes → services → repositories → models → core/utils)". Zero breaking changes constraint. Directory: `.planning/phases/15-refactor-main-py-layers/`
- 2026-04-19: NOTE — STATE.md Phase Map (lines 32–42) lists phases 15–19 as COMPLETE (v41-social-cards, v41-inline-filters, v41-summary-hero, v41-social-avatars, v41-micro-polish), but none of those directories exist; all work happened inside Phase 14 "steps" per git log. Phase Map is aspirational/stale — does NOT represent current roadmap truth. See ROADMAP.md for canonical phase numbering.
- 2026-04-29: Phase 16 added — "Sherlock false-positive filter + Thordata proxy integration" (FP reduction + residential rotating proxy for OSINT agents to bypass DigitalOcean IP blocks). Depends on Phase 15. Directory: `.planning/phases/16-sherlock-false-positive-filter-thordata-proxy-integration/`. Note: gsd-tools `phase add` numbered as 12 due to milestone parsing bug (collided with v4.1 Phase 12 pre-gate); manually renumbered to 16 + dir renamed.
- 2026-05-08: Redis7 Cache Backend folded into v4.2 as Phase 18 to replace process-local `cachetools.TTLCache` with shared Redis7 TTL cache. Directory: `.planning/phases/18-redis7-cache-backend/`. Postgres phases shifted 18-24 → 19-25. Planning only; implementation not started.
- 2026-05-09: Phase 18 implemented and verified. Redis7 service/config, async fail-open cache backend, search cache migration, health cache stats, and `cachetools` removal complete. Targeted tests: 9 passed.

### Blockers/Concerns

- Boundary drift: worktree already contains Phase 22-style `api/db.py` asyncpg driver switch; do not reset without explicit approval
- No test suite for frontend JS — visual regressions caught only by manual testing
- OathNet Starter plan: 100 lookups/day — test with real queries sparingly
- VPS has nginx.conf with frame-ancestors fix — needs scp deploy

## Session Continuity

Last session: 2026-05-10T18:13:30-03:00
Stopped at: Completed Phase 24; production runs on Postgres
Resume file: None
Next action: execute Phase 25 post-migration tuning and backup hardening.

### Phase 16 Planning Summary (2026-04-30)

- 16-01-PLAN.md (wave 1, autonomous=true): api/config.py adds 6 env vars + new api/budget.py daily Thordata bandwidth tracker + .env.example. 6 unit tests.
- 16-02-PLAN.md (wave 2, depends_on=[16-01]): modules/sherlock_wrapper.py rewrite — Thordata sticky-session proxy with 1× rotate retry, multi-signal confidence scoring (status+text+size, 0-100, 3-state classifier), real streaming body cap (256KB), cf-mitigated detection, asyncio.TimeoutError → httpx.TimeoutException fix, SHA256-hashed audit log. ~20 unit tests.
- 16-03-PLAN.md (wave 3, depends_on=[16-01, 16-02]): api/schemas.py SherlockUsernameRequest validator (D-H8/D-H9) + api/services/search_service.py budget circuit breaker + extended SSE serializer (state/confidence/likely/proxy_used) + api/routes/health.py thordata sub-object (admin-gated via new get_optional_admin_user) + api/main.py lifespan non-blocking proxy health check. 9 unit + ~10 integration tests.
- 16-04-PLAN.md (wave 4, depends_on=[16-01..03]): static/js/render.js renderSocial state-branched rendering + Unverified badge + module_error UX (budget_exceeded, invalid_username) + static/css/meridian.css 3 new classes from existing tokens + 16-NEGATIVE-MARKERS-AUDIT.md (5-platform manual validation) + tests/integration/test_phase16_e2e.py (8 E2E tests) + VPS deploy. Brand Amber/Noir preserved.

### Open Risks Forwarded to Execution

- D-H1 enforcement (frontend never recomputes thresholds) — verified by acceptance criteria grep on `p\.confidence\s*[<>=]`. Fail-closed.
- D-H2/D-H3 (no internal scoring leak) — SSE serializer whitelists exact 6 keys per platform item; integration test 6 + 8 audit raw bytes.
- D-H5 (proxy URL never logged with credentials) — `_masked_proxy_log` helper in sherlock_wrapper; lifespan + audit log both use it.
- Thordata sesstime unit correction (Pitfall 2): D-03 says "60" but Thordata docs are minutes; 16-02 implements `_STICKY_SESSTIME_MINUTES = 2`. Documented in 16-02 SUMMARY output.
- Negative markers in PLATFORMS dict are research-derived (16-RESEARCH); 16-04 Task 1 validates 5 representative platforms against real responses before VPS deploy. PLATFORMS may be patched in-flight.

### Hotfix Interleaved — 2026-04-23 → 2026-04-24 [MERGED ✅]

Source: `codex security review.md` (2026-04-23 10:42) → validação cruzada +
deploy em `hotfix/v4.1-security-2026-04-23`. Detalhes completos em
`.planning/hotfixes/2026-04-23-security-high.md`.

3 commits atômicos (fast-forward merged em master 2026-04-24):

- `23af34b` HIGH#1: remove `ports: 8000:8000` (Docker-UFW bypass)
- `6eaddff` HIGH#2: `real_ip_header CF-Connecting-IP` + `--proxy-headers` (rate limit shared bucket)
- `d4f9936` HIGH#3: `PyJWT 2.9.0 → 2.12.1` (GHSA-752w-5fwx-jx9f crit header)

Deploy validado 2026-04-24T03:05:18Z: porta 8000 inacessível, `/health` via
443 OK, logs nginx mostrando IP real pós-reload, 61/61 testes verdes.
Branch merged — backups VPS: `nexus-osint-nexus:pre-hotfix-20260423-backup`.
