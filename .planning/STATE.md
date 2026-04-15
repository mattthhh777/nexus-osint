---
gsd_state_version: 1.0
milestone: v4.1.0
milestone_name: Results UX — Data completeness & presentation
status: PRE-GATE COMPLETE — Phase 13 ready for execution
stopped_at: Phase 12 pre-gate commit done (2026-04-15)
last_updated: "2026-04-15T07:00:00.000Z"
progress:
  total_phases: 8
  completed_phases: 1
  total_plans: 0
  completed_plans: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-15 — milestone v4.1)

**Core value:** From the same scan, show 2× more data without additional backend cost — rendering what already arrives in the pipeline.

**Current focus:** Phase 13 — Data Instrumentation (extra_fields discovery)

## Current Position

Phase 12 (v41-pregate) — **COMPLETE**
- ✅ Deleted static/css.zip + static/js.zip (emergency backup artifacts)
- ✅ Committed 7 deployed-but-unversioned files (nginx.conf, 4× CSS, index.html, auth.js)
- ✅ Fixed security bug: form-ancestors → frame-ancestors in nginx /js/ CSP block

Phase 13 (v41-data-instrument) — **NEXT**

## Phase Map

| # | Phase | Status | Notes |
|---|-------|--------|-------|
| 12 | v41-pregate | ✅ COMPLETE | Pre-gate commit + zip cleanup |
| 13 | v41-data-instrument | ⏳ NEXT | Admin endpoint + extra_fields whitelist |
| 14 | v41-breach-cards | ☐ | Flat table → 2-col cards |
| 15 | v41-social-cards | ☐ | Emoji chips → SVG brand icon cards |
| 16 | v41-inline-filters | ☐ | Filter input in panels >10 entries |
| 17 | v41-summary-hero | ☐ | 4 stat cards at results top |
| 18 | v41-copy-expand | ☐ | Per-field copy + raw JSON modal |
| 19 | v41-micro-polish | ☐ | press-feedback, sf-dot, placeholder rotativo |

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

### Blockers/Concerns

- No test suite for frontend JS — visual regressions caught only by manual testing
- OathNet Starter plan: 100 lookups/day — test with real queries sparingly
- VPS has nginx.conf with frame-ancestors fix — needs scp deploy

## Session Continuity

Last session: 2026-04-15 Opus planning + Sonnet pre-gate
Stopped at: Phase 12 complete, PROJECT.md + STATE.md updated
Resume file: None
Next action: Phase 13 — create .planning/phases/13-v41-data-instrument/ and plan the admin endpoint
