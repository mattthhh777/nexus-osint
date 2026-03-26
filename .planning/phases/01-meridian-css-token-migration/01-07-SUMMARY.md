---
phase: 01-meridian-css-token-migration
plan: 07
subsystem: ui
tags: [css, design-tokens, meridian, overlays, responsive]

# Dependency graph
requires:
  - phase: 01-meridian-css-token-migration/01-01
    provides: "Meridian tokens.css with full semantic token set"
provides:
  - "overlays.css fully migrated to Meridian tokens — zero legacy references"
  - "responsive.css border-radius violations corrected — three mobile overrides tokenized"
  - "shadow-amber reference removed; file-viewer-overlay z-index using --z-modal"
affects: [xss-sanitization, deployment]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "backdrop overlay rgba(0,0,0,.5/.75) kept as literals — no semantic token equivalent for dimmer values"
    - "rgba box-shadow literals (0,0,0,.55/.65/.75) kept — decorative spread with no token equivalent"
    - "z-index 500 → --z-modal (200): file viewer is a modal dialog, capped below --z-toast (999)"

key-files:
  created: []
  modified:
    - static/css/overlays.css
    - static/css/responsive.css

key-decisions:
  - "file-viewer-overlay z-index 500 → var(--z-modal): 500 was between z-modal (200) and z-toast (999); file viewer is a modal dialog so z-modal is semantically correct"
  - "rgba(0,0,0,.5/.75) backdrop/overlay literals intentionally kept — no semantic token for black overlay dimmers"
  - "rgba(0,0,0,.55/.65/.75) box-shadow literals intentionally kept — decorative spread values with no token equivalent"
  - "responsive.css border-radius overrides now explicitly reinforce var(--radius-lg) = 6px on mobile instead of overriding to larger hardcoded values"

patterns-established:
  - "All auth-card, auth-logo elements use --radius-lg (6px) matching Meridian max-radius constraint"
  - "auth-input uses --radius-md (4px) — inputs intentionally tighter than cards"
  - "cases-panel transition uses var(--duration-mid) var(--ease-in-out) — standard panel slide animation"

requirements-completed: [CSS-01, CSS-02, CSS-03, CSS-04, CSS-05, CSS-07, CSS-08, CSS-09]

# Metrics
duration: 8min
completed: 2026-03-26
---

# Phase 01 Plan 07: Overlays and Responsive CSS Migration Summary

**Complete Meridian token migration of overlays.css (41 legacy replacements) and responsive.css (3 border-radius fixes), eliminating shadow-amber, correcting z-index 500 to --z-modal, and tokenizing all mobile breakpoint border-radius overrides.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-26T06:37:00Z
- **Completed:** 2026-03-26T06:45:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Migrated 41 legacy token occurrences in overlays.css to Meridian semantic tokens
- Fixed 5 border-radius violations in overlays.css (toast 10px, auth-card 14px, auth-logo 14px, case-card 10px, file-viewer 12px) — all corrected to var(--radius-lg)
- auth-input border-radius corrected from var(--r) to var(--radius-md) (inputs use tighter 4px radius)
- Replaced var(--shadow-amber) with var(--shadow-glow) — shadow-amber no longer exists in tokens.css after plan 01
- Corrected file-viewer-overlay z-index from hardcoded 500 to var(--z-modal)
- Converted cases-panel transition from hardcoded cubic-bezier to var(--duration-mid) var(--ease-in-out)
- Fixed 3 border-radius violations in responsive.css — mobile overrides now reinforce 6px instead of incorrectly overriding to 10px/12px

## Changes by File

### overlays.css

| Category | Count |
|----------|-------|
| Color tokens replaced | 28 |
| Font tokens replaced | 5 |
| Border-radius violations fixed | 6 |
| Z-index fixed (500 → --z-modal) | 1 |
| shadow-amber replaced with shadow-glow | 1 |
| Transition tokenized | 1 |
| **Total changes** | **42** |

### responsive.css

| Category | Count |
|----------|-------|
| Border-radius violations fixed | 3 |
| **Total changes** | **3** |

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate overlays.css** - `c923916` (feat)
2. **Task 2: Fix border-radius in responsive.css** - `bdcaa67` (feat)

**Plan metadata:** (see final commit below)

## Files Created/Modified

- `static/css/overlays.css` - Fully migrated to Meridian tokens; 41 legacy references eliminated
- `static/css/responsive.css` - Three border-radius overrides tokenized with var(--radius-lg)

## Decisions Made

- **z-index 500 → --z-modal (200):** The file viewer overlay was using z-index: 500 — positioned between --z-modal (200) and --z-toast (999). The file viewer is semantically a modal dialog, so --z-modal is the correct semantic layer. The design system uses --z-toast (999) exclusively for transient notifications; no other UI layer should exceed --z-modal.
- **rgba(0,0,0,.5/.75) backdrop dimmer kept as literal:** These values appear in .cases-overlay and .file-viewer-overlay backgrounds respectively. They serve as dimming overlays with no semantic token equivalent. Per prior decisions in this migration, backdrop dimmer literals below 50% threshold with no semantic equivalent are kept as literals.
- **rgba(0,0,0,.55/.65/.75) box-shadow literals kept:** Decorative shadow spreads (toast, auth-card, file-viewer) have no token equivalent. Consistent with decisions from previous plans.
- **responsive.css border-radius approach:** Changed from removing the lines to keeping them with var(--radius-lg). This explicitly reinforces the 6px value on mobile, preventing any future desktop change from bleeding through to mobile unintentionally.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None — both files are purely presentational CSS with no data wiring.

## Next Phase Readiness

- All 9 CSS files in Phase 01 are now fully migrated to Meridian tokens
- Phase 01 (Meridian CSS Token Migration) is complete — ready for phase transition
- Phase 02 (XSS Sanitization) can proceed — no CSS dependencies

---
*Phase: 01-meridian-css-token-migration*
*Completed: 2026-03-26*
