---
phase: 01-meridian-css-token-migration
plan: 01
subsystem: ui
tags: [css, design-system, tokens, meridian]

# Dependency graph
requires: []
provides:
  - "Single authoritative :root block with all 79 Meridian design tokens"
  - "Eliminated legacy alias tokens (--bg, --amber, --text, --mono, etc.)"
  - "Eliminated duplicate legacy shadow/easing/duration declarations"
affects:
  - 01-02-PLAN.md
  - 01-03-PLAN.md
  - 01-04-PLAN.md
  - 01-05-PLAN.md
  - 01-06-PLAN.md
  - 01-07-PLAN.md

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Meridian design system: single :root block, semantic token naming (--color-*, --font-*, --shadow-*, --duration-*, --z-*)"

key-files:
  created: []
  modified:
    - static/css/tokens.css

key-decisions:
  - "Remove legacy aliases immediately (--bg, --amber, --text, --mono, --r, --dur-*) — other 8 CSS files will tolerate unresolved vars during migration window per plan spec"
  - "Remove duplicate legacy shadow block entirely — canonical shadow values (0 1px 3px, 0 2px 8px, etc.) retained in Meridian block"

patterns-established:
  - "Token precedence: tokens.css single :root is the authoritative source, no fallback aliases"

requirements-completed: [CSS-10, CSS-12]

# Metrics
duration: 1min
completed: 2026-03-26
---

# Phase 01 Plan 01: Install Clean Meridian tokens.css Summary

**Single :root block with 79 Meridian design tokens installed in tokens.css — legacy alias block (25 vars) and duplicate shadow/easing/duration block eliminated**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-26T06:13:40Z
- **Completed:** 2026-03-26T06:14:42Z
- **Tasks:** 1 of 1
- **Files modified:** 1

## Accomplishments

- Replaced 155-line tokens.css (with 2 extra blocks) with clean 127-line single :root declaration
- Removed LEGACY ALIASES block: 25 vars (--bg, --bg2-5, --line, --line2-3, --amber, --amber-lo, --amber-glow, --red, --red-lo, --orange, --green, --green-lo, --blue, --blue-lo, --text, --text2-3, --mono, --sans, --r)
- Removed duplicate legacy shadow/easing/duration block: --shadow-xs/sm/md/lg (different values), --shadow-amber, --shadow-inset (legacy), --ease-out/in-out (duplicates), --dur-fast/mid/slow
- All 79 Meridian tokens verified present with correct values from BRIEFING §3.2

## Task Commits

Each task was committed atomically:

1. **Task 1: Install clean Meridian tokens.css** - `ff9fa72` (feat)

## Files Created/Modified

- `static/css/tokens.css` - Replaced: removed legacy aliases block (lines 113-137) and duplicate shadow/easing/duration block (lines 139-155). Single :root with 79 Meridian tokens, 127 lines total.

## Decisions Made

- Accepted that the other 8 CSS files will have temporarily unresolved var() references for legacy tokens (--bg, --amber, etc.) during the migration window. The plan explicitly permits this — browser falls back to inherited/initial values. Plans 02-07 will resolve each file sequentially.
- The canonical Meridian shadow values (shadow-xs: 0 1px 3px, shadow-sm: 0 2px 8px, etc.) differ from the old legacy values (shadow-xs: 0 1px 4px, shadow-sm: 0 2px 12px). The Meridian values from BRIEFING §3.2 were used as specified.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None - this plan installs token definitions only, no UI data flows involved.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- tokens.css is the clean Meridian source of truth
- Plans 02-07 can proceed to migrate each CSS file from legacy tokens to Meridian tokens
- The migration is sequential: each plan migrates one CSS file and removes the corresponding legacy var() references
- Until all 8 CSS files are migrated, some styles will fall back to initial values for legacy token references — this is expected behavior during the migration window

---
*Phase: 01-meridian-css-token-migration*
*Completed: 2026-03-26*
