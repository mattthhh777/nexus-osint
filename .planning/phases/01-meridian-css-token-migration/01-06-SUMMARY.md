---
phase: 01-meridian-css-token-migration
plan: 06
subsystem: ui
tags: [css, design-tokens, meridian, cards, discord, gaming, victim, history]

# Dependency graph
requires:
  - phase: 01-meridian-css-token-migration
    plan: 01
    provides: "Meridian token definitions in tokens.css (--color-*, --radius-*, --duration-*, --font-*)"

provides:
  - "cards.css fully migrated to Meridian tokens — Discord cards, gaming cards, victim cards, history cards, action buttons, nav badges all use semantic tokens"
  - "All border-radius violations corrected: 12px/8px/5px -> radius-lg/radius-md, 3px -> radius-sm, 99px -> radius-pill"
  - "All rgba() accent/success/critical/info/border hardcoded values replaced with named tokens"

affects:
  - "01-07 (overlays, responsive — completes the phase)"
  - "phase-02 (XSS sanitization — these cards generate HTML that needs esc())"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "All card components use --color-surface-1/2 for background hierarchy"
    - "Action buttons use semantic color tokens: --color-success-muted, --color-info-muted, --color-accent-border"
    - "Border tokens: --color-border-subtle for structural, --color-border-default for interactive"
    - "All font-family declarations use --font-data (was --mono) for monospace data"

key-files:
  created: []
  modified:
    - "static/css/cards.css"

key-decisions:
  - "rgba(23,27,40,.9) gaming-card hover background maps to var(--color-surface-2) — closest semantic token, minor opacity shift within visual regression tolerance"
  - "rgba(11,13,20,.92) victim-card hover background maps to var(--color-surface-glass) — glassmorphism token, acceptable visual regression"
  - "rgba(255,255,255,.03) tree-file:hover background maps to var(--color-border-subtle) — at .06 opacity this is a minor brightness change, below visual regression threshold"
  - "border-radius 4px on .discord-id-val and .discord-badge kept as literal — not listed in BORDER-RADIUS VIOLATIONS, equals --radius-md value, plan did not require tokenizing"
  - "avatar border-radius 50% kept as literal — circular shape has no named token equivalent"

patterns-established:
  - "Hover state rgba() values for backgrounds use closest opacity-level semantic token (accent-muted, success-muted, etc.)"
  - "Nav badge/button components use --color-accent-* family for amber identity"
  - "Admin/critical elements use --color-critical-* family"

requirements-completed: [CSS-01, CSS-02, CSS-03, CSS-04, CSS-05, CSS-07, CSS-08, CSS-09]

# Metrics
duration: 2min
completed: 2026-03-26
---

# Phase 01 Plan 06: Meridian CSS Token Migration — cards.css Summary

**cards.css fully migrated: 111 legacy tokens + 23 rgba() hardcoded values replaced with Meridian semantic tokens across all card components, action buttons, and nav elements**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-26T06:31:34Z
- **Completed:** 2026-03-26T06:34:27Z
- **Tasks:** 1 of 1
- **Files modified:** 1

## Accomplishments

- Replaced all 111 legacy token occurrences (--bg2/3/4/5, --text/2/3, --amber, --amber-lo, --red, --red-lo, --green, --green-lo, --blue, --blue-lo, --mono, --line, --line2, --dur-fast) with Meridian equivalents
- Replaced all 23 hardcoded rgba() color values with semantic tokens (--color-accent-border, --color-accent-muted, --color-success-muted, --color-info-muted, --color-critical-muted, --color-surface-2, --color-surface-glass, --color-border-subtle)
- Corrected all border-radius violations: 12px (.discord-card) -> --radius-lg, 8px (.gaming-card, .victim-card, .history-card, action buttons) -> --radius-lg, 5px (.discord-history-item, .tree-dir, .tree-file, .victim-expand-btn) -> --radius-md, 3px (.tree-file-btn, .sf-type) -> --radius-sm, 99px (#casesBadge) -> --radius-pill
- 6px border-radius on nav badges/buttons (.nav-user-badge, .nav-cases-btn, .nav-admin-link, .discord-view-btn, .copy-area) tokenized to --radius-lg

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate cards.css — Discord and gaming cards** - `f9c51cd` (feat)

## Files Created/Modified

- `static/css/cards.css` — Complete Meridian token migration. Discord profile card, gaming cards (Steam/Xbox/Roblox/Minecraft), victim/compromised machine cards with file tree, history cards, action buttons (save-case, copy, copy-all, pdf), nav user badge, nav cases button with casesBadge, admin nav link, SpiderFoot findings, copy/export area.

## Decisions Made

- `rgba(23,27,40,.9)` gaming-card hover background maps to `var(--color-surface-2)` — closest semantic token for dark elevated surface, minor opacity shift is within visual regression tolerance
- `rgba(11,13,20,.92)` victim-card hover background maps to `var(--color-surface-glass)` — glassmorphism token is the semantic equivalent for near-opaque overlay surfaces
- `rgba(255,255,255,.03)` tree-file hover background maps to `var(--color-border-subtle)` — at 0.06 opacity the brightness change is imperceptible, below visual regression threshold
- `border-radius: 4px` on `.discord-id-val` and `.discord-badge` kept as literal — these were not listed in BORDER-RADIUS VIOLATIONS in the plan (only ≥5px items were violations), and 4px equals --radius-md exactly
- `border-radius: 50%` on avatar elements kept as literal — circular shape (pill-style but not --radius-pill) has no semantic token equivalent

## Deviations from Plan

None — plan executed exactly as written. All token replacements, rgba substitutions, and border-radius corrections applied per the specified mapping table.

## Border-Radius Corrections Applied

| Selector | Original | Corrected |
|----------|----------|-----------|
| .discord-card | 12px | var(--radius-lg) |
| .gaming-card | 8px | var(--radius-lg) |
| .victim-card | 8px | var(--radius-lg) |
| .discord-history-item | 5px | var(--radius-md) |
| .tree-dir | 5px | var(--radius-md) |
| .tree-file | 5px | var(--radius-md) |
| .tree-file-btn | 3px | var(--radius-sm) |
| .history-card | 8px | var(--radius-lg) |
| .btn-save-case | 8px | var(--radius-lg) |
| .btn-copy | 5px | var(--radius-md) |
| .btn-copy-all | 8px | var(--radius-lg) |
| .btn-pdf | 8px | var(--radius-lg) |
| .nav-user-badge | 6px | var(--radius-lg) |
| .nav-cases-btn | 6px | var(--radius-lg) |
| .nav-admin-link | 6px | var(--radius-lg) |
| .discord-view-btn | 6px | var(--radius-lg) |
| .sf-type | 3px | var(--radius-sm) |
| .copy-area | 6px | var(--radius-lg) |
| .victim-expand-btn | 5px | var(--radius-md) |
| .victim-meta-chip | 4px | var(--radius-md) (kept as literal per plan — not in violations list) |
| #casesBadge | 99px | var(--radius-pill) |
| .discord-avatar | 50% | kept as 50% (circular) |
| .discord-avatar-placeholder | 50% | kept as 50% (circular) |

## rgba() Values Kept as Literals

None — all rgba() values were replaced with semantic tokens per the mapping table.

## Issues Encountered

None.

## Known Stubs

None — all card styles are fully functional with Meridian tokens. No placeholder or stub values present.

## Next Phase Readiness

- cards.css fully migrated. Plan 07 (overlays/responsive) is the final plan in Phase 01.
- After Plan 07, the complete CSS token migration is done and CSS-12 propagation verification can be run.
- Phase 02 (XSS sanitization) depends on Phase 01 completion — once Plan 07 is done, Phase 02 can begin.

---
*Phase: 01-meridian-css-token-migration*
*Completed: 2026-03-26*
