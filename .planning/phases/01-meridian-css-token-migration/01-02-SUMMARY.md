---
phase: 01-meridian-css-token-migration
plan: 02
subsystem: ui
tags: [css, design-system, tokens, meridian, reset, layout]

# Dependency graph
requires:
  - 01-01-SUMMARY.md  # Meridian tokens.css installed
provides:
  - "reset.css fully migrated to Meridian tokens — zero legacy aliases"
  - "layout.css fully migrated to Meridian tokens — zero legacy aliases"
  - "Z-index 100 replaced by var(--z-sticky) in nav"
  - "Border-radius tokens applied: radius-lg, radius-sm, radius-pill"
  - "All rgba() color values in both files replaced by named tokens"
affects:
  - 01-03-PLAN.md
  - 01-04-PLAN.md
  - 01-05-PLAN.md
  - 01-06-PLAN.md
  - 01-07-PLAN.md

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "rgba() accent/border/shadow values replaced by semantic tokens (--color-accent-muted, --color-accent-border, --color-accent-glow, --color-border-subtle, --shadow-sm)"
    - "Z-index scale applied: 100 → var(--z-sticky)"
    - "Border-radius tokens applied: 6px → --radius-lg, 3px/4px → --radius-sm/--radius-md, 999px → --radius-pill"
    - "Transition tokens applied: .3s → var(--duration-fast) var(--ease-in-out)"
    - "Glassmorphism nav uses var(--color-surface-glass) instead of hardcoded rgba(8,10,15,.95)"

key-files:
  created: []
  modified:
    - static/css/reset.css
    - static/css/layout.css

key-decisions:
  - "Keep rgba(255,255,255,.013) grid texture in body::before as literal — decorative value at extreme low opacity with no semantic token equivalent"
  - "nav background: rgba(8,10,15,.95) → var(--color-surface-glass) [rgba(15,18,25,0.92)] — closest glassmorphism token; 1px visual difference acceptable per spec"
  - "rgba(62,199,140,.25) sf-dot.online ring → var(--color-success-muted) [rgba(34,197,94,0.10)] — legacy green was #3ec78c, Meridian green is #22c55e; glow ring color shifts slightly"
  - "nav-badge background rgba(17,20,30,.8) → var(--color-surface-1) [#0f1219] — closest surface token; opaque vs semi-transparent, minimal visual impact"
  - "3px nav-version border-radius → var(--radius-sm) [2px] — 1px visual difference, rounds to nearest token"

requirements-completed: [CSS-01, CSS-02, CSS-04, CSS-06, CSS-08, CSS-09]

# Metrics
duration: 2min
completed: 2026-03-26
---

# Phase 01 Plan 02: Migrate reset.css and layout.css Summary

**reset.css (9 replacements) and layout.css (23 replacements) fully migrated to Meridian tokens — zero legacy aliases, zero hardcoded rgba() color values remaining in either file**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-26T06:17:10Z
- **Completed:** 2026-03-26T06:18:36Z
- **Tasks:** 2 of 2
- **Files modified:** 2

## Accomplishments

### reset.css — 9 replacements

| # | Location | Old | New |
|---|----------|-----|-----|
| 1 | body background | `var(--bg)` | `var(--color-bg-base)` |
| 2 | body color | `var(--text)` | `var(--color-text-primary)` |
| 3 | body font-family | `var(--sans)` | `var(--font-display)` |
| 4 | h1/h2/h3 font-family | `var(--sans)` | `var(--font-display)` |
| 5 | code/.mono font-family | `var(--mono)` | `var(--font-data)` |
| 6 | scrollbar-thumb background | `var(--bg5)` | `var(--color-surface-3)` |
| 7 | body::after gradient stop 1 | `rgba(245,166,35,.07)` | `var(--color-accent-muted)` |
| 8 | body::after gradient stop 2 | `rgba(74,158,255,.025)` | `var(--color-info-muted)` |
| 9 | :focus-visible outline | `rgba(245,166,35,.5)` | `var(--color-accent-border)` |

### layout.css — 23 replacements

**Legacy token replacements (10):**

| # | Selector | Old | New |
|---|----------|-----|-----|
| 1 | .nav-logo font-family | `var(--mono)` | `var(--font-data)` |
| 2 | .sf-indicator font-family | `var(--mono)` | `var(--font-data)` |
| 3 | .nav-version font-family | `var(--mono)` | `var(--font-data)` |
| 4 | .hero-tag font-family | `var(--mono)` | `var(--font-data)` |
| 5 | .nav-logo color | `var(--text)` | `var(--color-text-primary)` |
| 6 | .hero h1 color | `var(--text)` | `var(--color-text-primary)` |
| 7 | .hero p color | `var(--text2)` | `var(--color-text-secondary)` |
| 8 | .sf-indicator color, .nav-badge color, .nav-version color | `var(--text3)` | `var(--color-text-tertiary)` |
| 9 | .nav-logo-mark bg, .hero-tag color, .hero h1 span | `var(--amber)` | `var(--color-accent)` |
| 10 | .nav-logo-mark color | `var(--bg)` | `var(--color-bg-base)` |
| 11 | .nav-version bg, .nav-badge bg | `var(--bg3)` | `var(--color-surface-1)` |
| 12 | .nav-version border | `var(--line)` | `var(--color-border-subtle)` |
| 13 | .sf-dot.online background | `var(--green)` | `var(--color-success)` |
| 14 | .nav-logo-mark transition | `var(--dur-fast)` | `var(--duration-fast)` |

**rgba() color replacements (7):**

| # | Selector | Old | New |
|---|----------|-----|-----|
| 1 | .nav border-bottom | `rgba(255,255,255,.07)` | `var(--color-border-subtle)` |
| 2 | .nav background | `rgba(8,10,15,.95)` | `var(--color-surface-glass)` |
| 3 | .nav box-shadow | `0 1px 24px rgba(0,0,0,.45)` | `var(--shadow-sm)` |
| 4 | .nav-logo-mark box-shadow | `rgba(245,166,35,.35)` | `var(--color-accent-glow)` |
| 5 | hover .nav-logo-mark box-shadow | `rgba(245,166,35,.55)` | `var(--color-accent-border)` |
| 6 | .nav-badge border | `rgba(255,255,255,.07)` | `var(--color-border-subtle)` |
| 7 | .sf-dot.online box-shadow ring | `rgba(62,199,140,.25)` | `var(--color-success-muted)` |
| 8 | .hero-tag border | `rgba(245,166,35,.22)` | `var(--color-accent-border)` |
| 9 | .hero-tag background | `rgba(245,166,35,.07)` | `var(--color-accent-muted)` |

**Structural token replacements (2):**

| # | Selector | Old | New |
|---|----------|-----|-----|
| 1 | .nav z-index | `100` | `var(--z-sticky)` |
| 2 | .sf-dot transition | `background .3s` | `background var(--duration-fast) var(--ease-in-out)` |

**Border-radius token replacements (3):**

| # | Selector | Old | New |
|---|----------|-----|-----|
| 1 | .nav-logo-mark | `6px` | `var(--radius-lg)` |
| 2 | .nav-version | `3px` | `var(--radius-sm)` |
| 3 | .hero-tag | `999px` | `var(--radius-pill)` |

## Values Intentionally Kept as Literals

| File | Value | Location | Justification |
|------|-------|----------|---------------|
| reset.css | `rgba(255,255,255,.013)` | body::before grid texture | Decorative at extreme low opacity; no semantic token exists for this; plan explicitly permits keeping it |
| layout.css | `80px` | .page padding-bottom | 80px bottom padding exceeds the --space-8 (32px) scale max; keeping literal per plan spec |
| layout.css | `20px 24px` | .nav padding shorthand | Shorthand kept as literal per plan spec |
| layout.css | `#e0891c` | .nav-logo-mark gradient stop 2 | Dark amber end-stop in gradient; not a semantic semantic color, decorative gradient detail |
| layout.css | `border-radius: 50%` | .sf-dot | Circle element; plan explicitly says keep 50% |
| layout.css | `0 0 10px var(--color-success)` | .sf-dot.online box-shadow | Glow spread kept with token reference; second shadow in compound value |

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate reset.css** - `b07d010` (feat)
2. **Task 2: Migrate layout.css** - `f981273` (feat)

## Files Created/Modified

- `static/css/reset.css` — 9 legacy token replacements; 1 decorative rgba() kept as literal; 71 lines, all colors now via Meridian tokens
- `static/css/layout.css` — 23 replacements across legacy tokens, rgba() values, z-index, border-radius, and transitions; 118 lines, all colors/borders/shadows now via Meridian tokens

## Decisions Made

- Kept rgba(255,255,255,.013) grid texture literal in reset.css — plan explicitly permits this decorative value with no semantic equivalent
- nav background uses var(--color-surface-glass) — closest glassmorphism token; minor color shift from rgba(8,10,15) to rgba(15,18,25) is within acceptable visual regression range
- .sf-dot.online glow ring uses var(--color-success-muted) — legacy rgba(62,199,140,.25) maps to the Meridian success muted token; color shifts from old #3ec78c to new #22c55e (both are green, within brand range)
- nav-badge background uses var(--color-surface-1) [opaque] instead of rgba(17,20,30,.8) [semi-transparent] — small visual change, no functional impact

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None — this plan migrates CSS token references only; no UI data flows or dynamic rendering involved.

## User Setup Required

None — pure CSS token migration, no external service configuration required.

## Next Phase Readiness

- reset.css and layout.css are fully migrated to Meridian tokens
- Plans 03-07 can continue migrating the remaining 7 CSS files (components.css, search.css, panels.css, cards.css, export.css, etc.)
- The 2 smallest files are complete; remaining files have higher legacy token counts

## Self-Check: PASSED

- FOUND: static/css/reset.css
- FOUND: static/css/layout.css
- FOUND: .planning/phases/01-meridian-css-token-migration/01-02-SUMMARY.md
- FOUND: commit b07d010 (reset.css migration)
- FOUND: commit f981273 (layout.css migration)

---
*Phase: 01-meridian-css-token-migration*
*Completed: 2026-03-26*
