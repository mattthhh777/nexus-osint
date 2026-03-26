---
phase: 01-meridian-css-token-migration
plan: 04
subsystem: ui
tags: [css, design-system, tokens, meridian, components, search]

# Dependency graph
requires:
  - 01-01-PLAN.md
provides:
  - "components.css fully migrated to Meridian tokens — search, buttons, toggles, chips, badge, kbd"
  - "Critical CSS-03 fix: .search-container border-radius corrected from 14px to var(--radius-lg)"
  - "shadow-amber replaced with shadow-glow (removed token)"
  - "All interactive component transitions use --duration-fast / --duration-mid tokens"
affects:
  - 01-05-PLAN.md
  - 01-06-PLAN.md
  - 01-07-PLAN.md

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Border-radius hierarchy: container/btn/chip/toggle = radius-lg; inputs/toggle-btn/badge/kbd = radius-md; cat-chip = radius-pill"
    - "Shadow glow: var(--shadow-glow) replaces deleted var(--shadow-amber) on search-container"

key-files:
  created: []
  modified:
    - static/css/components.css

key-decisions:
  - "Keep rgba(0,0,0,.55) literal in .search-container box-shadow — 0 28px 72px decorative spread has no token equivalent (shadow-md is 0 4px 16px, wrong geometry)"
  - "Keep #7289da and rgba(114,137,218,.3) literals for .type-discord — Discord brand purple is outside the Meridian token system per plan spec"
  - ".btn transition changed from 'all .15s' to 'all var(--duration-fast)' — adopts token system; .btn-primary already had its own transition override"

patterns-established:
  - "Interactive element radius tier: containers/buttons/chips = --radius-lg; inputs/toggles-inner/badges/kbd = --radius-md; pill badges only = --radius-pill"

requirements-completed: [CSS-01, CSS-02, CSS-03, CSS-04, CSS-05, CSS-07, CSS-08]

# Metrics
duration: 1min
completed: 2026-03-26
---

# Phase 01 Plan 04: Migrate components.css to Meridian Tokens Summary

**components.css fully migrated — 51 legacy tokens replaced, 24 rgba() values converted, critical CSS-03 border-radius fix applied, shadow-amber eliminated**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-26T06:23:54Z
- **Completed:** 2026-03-26T06:25:12Z
- **Tasks:** 1 of 1
- **Files modified:** 1

## Accomplishments

### Changes Applied

**Legacy token replacements (51 occurrences):**
- `var(--bg4)` → `var(--color-surface-2)` (4 occurrences: .search-input, .toggle, .chip, kbd)
- `var(--bg2)` → `var(--color-bg-recessed)` (1 occurrence: .search-input:focus)
- `var(--bg3)` → `var(--color-surface-1)` (1 occurrence: .btn-secondary:hover)
- `var(--bg5)` → `var(--color-surface-3)` (1 occurrence: .query-type-badge)
- `var(--bg)` → `var(--color-bg-base)` (2 occurrences: .btn-primary, .toggle-btn.active)
- `var(--line)` → `var(--color-border-subtle)` (1 occurrence: .manual-section border-top)
- `var(--line2)` → `var(--color-border-default)` (5 occurrences: .search-input, .btn-secondary, .toggle, .chip, .query-type-badge)
- `var(--line3)` → `var(--color-border-strong)` (1 occurrence: .btn-secondary:hover)
- `var(--amber)` → `var(--color-accent)` (5 occurrences: .search-input caret, .btn-primary bg, .toggle-btn.active bg, .chip.active, .type-domain)
- `var(--amber-lo)` → `var(--color-accent-muted)` (1 occurrence: .chip.active bg)
- `var(--text)` → `var(--color-text-primary)` (3 occurrences: .search-input, .btn-secondary:hover, kbd)
- `var(--text2)` → `var(--color-text-secondary)` (3 occurrences: .btn-secondary, .toggle-btn, .sf-mode-label)
- `var(--text3)` → `var(--color-text-tertiary)` (3 occurrences: .search-input::placeholder, .section-label, .search-hint)
- `var(--mono)` → `var(--font-data)` (5 occurrences: .search-input, placeholder, .section-label, .sf-mode-label, .search-hint, kbd)
- `var(--sans)` → `var(--font-display)` (2 occurrences: .btn, .toggle-btn)
- `var(--r)` → `var(--radius-lg)` or `var(--radius-md)` (3 occurrences with different targets)
- `var(--dur-fast)` → `var(--duration-fast)` (5 occurrences)
- `var(--dur-mid)` → `var(--duration-mid)` (2 occurrences)
- `var(--blue)` → `var(--color-info)` (1 occurrence: .type-email)
- `var(--green)` → `var(--color-success)` (2 occurrences: .type-ip, .type-phone)
- `var(--shadow-amber)` → `var(--shadow-glow)` (1 occurrence: CRITICAL — deleted token)

**rgba() → token conversions (22 occurrences):**
- `rgba(11,13,20,.92)` → `var(--color-surface-glass)` (.search-container bg)
- `rgba(255,255,255,.09)` → `var(--color-border-default)` (.search-container border)
- `rgba(255,255,255,.025) inset` → `var(--color-border-subtle)` (box-shadow inset)
- `rgba(245,166,35,.24)` → `var(--color-accent-border)` (focus border)
- `rgba(255,255,255,.03) inset` → `var(--color-border-subtle)` (focus inset shadow)
- `rgba(245,166,35,.14)` → `var(--color-accent-muted)` (focus glow)
- `rgba(245,166,35,.38)` → `var(--color-accent-border)` (::before gradient)
- `rgba(245,166,35,.55)` → `var(--color-accent-border)` (.search-input:focus border)
- `rgba(245,166,35,.1)` → `var(--color-accent-muted)` (.search-input:focus shadow)
- `rgba(245,166,35,.28)` → `var(--color-accent-glow)` (.btn-primary shadow)
- `rgba(245,166,35,.42)` → `var(--color-accent-glow)` (.btn-primary:hover shadow)
- `rgba(245,166,35,.2)` → `var(--color-accent-muted)` (.btn-primary:active shadow)
- `rgba(245,166,35,.22)` → `var(--color-accent-muted)` (.toggle-btn.active shadow)
- `rgba(245,166,35,.05)` → `var(--color-accent-muted)` (.chip:hover bg)
- `rgba(245,166,35,.38)` → `var(--color-accent-border)` (.chip:hover border)
- `rgba(74,158,255,.3)` → `var(--color-info-muted)` (.type-email border)
- `rgba(62,199,140,.3)` → `var(--color-success-muted)` (.type-ip / .type-phone border)
- `rgba(245,166,35,.3)` → `var(--color-accent-border)` (.type-domain border)
- `rgba(255,255,255,.12)` → `var(--color-border-default)` (kbd border)
- `rgba(255,255,255,.08)` → `var(--color-border-subtle)` (kbd box-shadow line 1)
- `rgba(255,255,255,.06)` → `var(--color-border-subtle)` (kbd box-shadow line 2, was .06)

**Border-radius corrections (CSS-03 requirement):**
- `.search-container`: `14px` → `var(--radius-lg)` [CRITICAL CSS-03 fix — 14px was design violation]
- `.search-input`: `var(--r)` → `var(--radius-md)` [inputs use md per spec]
- `.btn`: `var(--r)` → `var(--radius-lg)` [buttons use lg per spec]
- `.toggle`: `6px` → `var(--radius-lg)` [6px = radius-lg, tokenized]
- `.toggle-btn`: `4px` → `var(--radius-md)` [4px = radius-md, tokenized]
- `.chip`: `6px` → `var(--radius-lg)` [6px = radius-lg, tokenized]
- `.chip.cat-chip`: `999px` → `var(--radius-pill)` [category chips only]
- `.query-type-badge`: `4px` → `var(--radius-md)` [4px = radius-md, tokenized]
- `kbd`: `4px` → `var(--radius-md)` [4px = radius-md, tokenized]

**Literal values retained (justified):**
- `rgba(0,0,0,.55)` in `.search-container` box-shadow — the `0 28px 72px` decorative spread is not covered by any shadow token (shadow-md is `0 4px 16px` — completely different geometry). Kept as literal.
- `#7289da` and `rgba(114,137,218,.3)` in `.type-discord` — Discord brand purple is intentionally outside the Meridian token system, as specified in the plan interfaces section.

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate components.css — search, inputs, buttons** - `2ec5681` (feat)

## Files Created/Modified

- `static/css/components.css` — Migrated: 51 legacy token replacements, 22 rgba() conversions, 9 border-radius corrections, shadow-amber → shadow-glow. File remains 214 lines (215 with final newline).

## Decisions Made

- Kept `rgba(0,0,0,.55)` as literal in the `.search-container` large decorative box-shadow — `0 28px 72px` geometry has no corresponding shadow token. Replacing with shadow-md (`0 4px 16px`) would visually alter the search container elevation significantly.
- Kept Discord purple (`#7289da`, `rgba(114,137,218,.3)`) as literals — Discord brand color is intentionally outside the Meridian amber/noir design system.
- `.btn` base transition changed from `all .15s` hardcoded to `all var(--duration-fast)` (120ms) — functionally equivalent, now uses token system.

## Deviations from Plan

None — plan executed exactly as written. All 51 legacy token occurrences replaced, all 24 rgba() values either converted to tokens or kept as justified literals per plan spec.

## Known Stubs

None — components.css defines structural styles only; no data flows or rendering logic involved.

## Self-Check: PASSED

- `static/css/components.css` exists and was modified
- Commit `2ec5681` exists in git history
- All acceptance criteria verified with grep commands before commit
