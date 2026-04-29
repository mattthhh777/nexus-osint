---
gsd_state_version: 1.0
milestone: v3.0.0
milestone_name: — Complete)
status: Phase 15 COMPLETE
stopped_at: Phase 16 context gathered
last_updated: "2026-04-29T03:56:42.659Z"
progress:
  total_phases: 9
  completed_phases: 7
  total_plans: 18
  completed_plans: 18
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-15 — milestone v4.1)

**Core value:** From the same scan, show 2× more data without additional backend cost — rendering what already arrives in the pipeline.

**Current focus:** Phase 15 — refactor-main-py-layers

## Current Position

Phase: 15 (refactor-main-py-layers) — EXECUTING
Plan: 1 of 4

## Phase Map

| # | Phase | Status | Notes |
|---|-------|--------|-------|
| 12 | v41-pregate | ✅ COMPLETE | Pre-gate commit + zip cleanup |
| 13 | v41-data-instrument | ✅ COMPLETE | `/api/admin/breach-extra-keys` + accumulator |
| 14 | v41-breach-cards | ✅ COMPLETE | Flat table → 2-col cards + extra_fields + per-field copy |
| 15 | v41-social-cards | ✅ COMPLETE | Emoji chips → SVG brand icon cards (25 platforms) |
| 16 | v41-inline-filters | ✅ COMPLETE | Filter input: social (>10 platforms) + holehe (>10 domains), debounce 150ms |
| 17 | v41-summary-hero | ✅ COMPLETE | Clickable stat cards + risk tinting + ↓ view hint |
| 18 | v41-social-avatars | ✅ COMPLETE | Social cards com foto de perfil via unavatar.io + CSP fix |
| 19 | v41-micro-polish | ✅ COMPLETE | press-feedback, sf-dot pulse/offline, placeholder rotativo |

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

### Blockers/Concerns

- No test suite for frontend JS — visual regressions caught only by manual testing
- OathNet Starter plan: 100 lookups/day — test with real queries sparingly
- VPS has nginx.conf with frame-ancestors fix — needs scp deploy

## Session Continuity

Last session: 2026-04-29T03:56:42.654Z
Stopped at: Phase 16 context gathered
Resume file: .planning/phases/16-sherlock-false-positive-filter-thordata-proxy-integration/16-CONTEXT.md
Next action: Plan 03 — introduzir app.state.db/orchestrator + get_db()/get_orchestrator() em deps.py.

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
