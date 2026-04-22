---
gsd_state_version: 1.0
milestone: v4.1
milestone_name: Results UX — Data completeness & presentation
status: Ready for Phase 15
stopped_at: Phase 14 complete (13 steps + regression sweep committed). Phase 15 CONTEXT.md + 15-01-PLAN.md ready.
last_updated: "2026-04-22T12:30:00.000Z"
progress:
  total_phases: 15
  completed_phases: 14
  total_plans: 19
  completed_plans: 19
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-15 — milestone v4.1)

**Core value:** From the same scan, show 2× more data without additional backend cost — rendering what already arrives in the pipeline.

**Current focus:** Phase 14 — visual-polish

## Current Position

Phase: 15 (refactor-main-py-layers) — READY TO EXECUTE
Plan: 1 of N (15-01-PLAN.md ready — Wave 1: extract Pydantic schemas)

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

### Blockers/Concerns

- No test suite for frontend JS — visual regressions caught only by manual testing
- OathNet Starter plan: 100 lookups/day — test with real queries sparingly
- VPS has nginx.conf with frame-ancestors fix — needs scp deploy

## Session Continuity

Last session: 2026-04-22 resume — Phase 14 closed, Phase 15 ready
Stopped at: Phase 14 SUMMARY written, ROADMAP + STATE updated. 15-01-PLAN.md (Wave 1) awaiting execution.
Resume file: None
Next action: `/gsd:execute-phase 15` — Wave 1: extract Pydantic models to `api/schemas.py`. Gate: 62/62 tests green after.
