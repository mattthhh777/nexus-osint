---
phase: 01-meridian-css-token-migration
plan: 03
subsystem: frontend-css
tags: [css, tokens, meridian, tables, migration]
dependency_graph:
  requires: [01-01]
  provides: [tables-css-meridian]
  affects: [static/css/tables.css]
tech_stack:
  added: []
  patterns: [meridian-token-var, radius-token, duration-token]
key_files:
  created: []
  modified:
    - static/css/tables.css
decisions:
  - Keep .sev-critical and .sev-high row background tints as rgba literals (rgba(239,68,68,.04) and rgba(249,115,22,.03)) — these .04/.03 opacity values are intentionally lighter than the --color-critical-muted and --color-high-muted tokens (which render at .10 opacity). Replacing them with tokens would visibly darken the row tint, violating zero-visual-regression constraint.
metrics:
  duration_minutes: 1
  completed_date: "2026-03-26"
  tasks_completed: 1
  files_modified: 1
---

# Phase 01 Plan 03: Tables CSS Meridian Token Migration Summary

**One-liner:** Migrated tables.css from 30 legacy token occurrences to full Meridian semantic tokens with radius and duration tokens applied to 4 components.

## What Was Done

Performed a complete token migration of `static/css/tables.css` (105 lines). Replaced every legacy CSS variable reference and hardcoded rgba() color value with Meridian design system equivalents. Applied border-radius tokens to severity badges, social badges, password toggle, and load-more button.

## Legacy Token Replacements (30 occurrences)

| Legacy Token | Meridian Token | Occurrences |
|---|---|---|
| `--mono` | `--font-data` | 5 |
| `--text` | `--color-text-primary` | 1 |
| `--text2` | `--color-text-secondary` | 2 |
| `--text3` | `--color-text-tertiary` | 5 |
| `--amber` | `--color-accent` | 4 |
| `--amber-lo` | `--color-accent-muted` | 3 |
| `--red` | `--color-critical` | 2 |
| `--red-lo` | `--color-critical-muted` | 1 |
| `--orange` | `--color-high` | 2 |
| `--green` | `--color-success` | 1 |
| `--green-lo` | `--color-success-muted` | 1 |
| `--bg3` | `--color-surface-1` | 1 |
| `--bg4` | `--color-surface-2` | 1 |
| `--line` | `--color-border-subtle` | 4 |
| `--line2` | `--color-border-default` | 1 |
| `--dur-fast` | `--duration-fast` | 4 |

## Hardcoded rgba() Values Replaced

| Original rgba() | Replacement Token | Location |
|---|---|---|
| `rgba(232,64,64,.2)` | `var(--color-critical-muted)` | .sev-critical .sev-breach-badge border |
| `rgba(232,130,42,.1)` | `var(--color-high-muted)` | .sev-high .sev-breach-badge background |
| `rgba(232,130,42,.2)` | `var(--color-high-muted)` | .sev-high .sev-breach-badge border |
| `rgba(245,166,35,.2)` | `var(--color-accent-muted)` | .sev-medium .sev-breach-badge border |
| `rgba(62,199,140,.2)` | `var(--color-success-muted)` | .social-badge border |
| `rgba(62,199,140,.18)` | `var(--color-success-muted)` | .social-badge:hover box-shadow |
| `rgba(62,199,140,.18)` | `var(--color-success-muted)` | .social-badge:hover background |
| `rgba(255,255,255,.025)` | `var(--color-border-subtle)` | .data-table tr:hover td background |
| `rgba(245,166,35,.04)` | `var(--color-accent-muted)` | .load-more-btn:hover background |
| `rgba(245,166,35,.35)` | `var(--color-accent-border)` | .load-more-btn:hover border-color |

## rgba() Values Kept as Literals

| rgba() Value | Location | Justification |
|---|---|---|
| `rgba(239,68,68,.04)` | `.sev-critical td` background | Row tint at .04 opacity — intentionally lighter than `--color-critical-muted` (~.10). Replacing with token would darken row background, violating zero-visual-regression. Updated from old red (232,64,64) to new red (239,68,68) to align with current token values. |
| `rgba(249,115,22,.03)` | `.sev-high td` background | Row tint at .03 opacity — intentionally lighter than `--color-high-muted`. Same justification. Updated from (232,130,42) to (249,115,22) to match current token palette. |

## Border-Radius Token Replacements

| Element | Old Value | New Token | Token Value |
|---|---|---|---|
| `.sev-breach-badge` | `3px` | `var(--radius-sm)` | 2px |
| `.social-badge` | `5px` | `var(--radius-md)` | 4px |
| `.pwd-toggle` | `3px` | `var(--radius-sm)` | 2px |
| `.load-more-btn` | `6px` | `var(--radius-lg)` | 6px |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Commits

| Task | Commit | Description |
|---|---|---|
| Task 1: Migrate tables.css | `12d32f5` | feat(01-03): migrate tables.css to Meridian tokens |

## Self-Check: PASSED

- static/css/tables.css: FOUND
- Commit 12d32f5: FOUND
