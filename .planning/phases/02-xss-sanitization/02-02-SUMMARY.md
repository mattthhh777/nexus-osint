---
phase: 02-xss-sanitization
plan: 02
status: complete
completed: 2026-03-26
---

# Plan 02-02 Summary: Escaping Audit (XSS-03, XSS-04)

## What was done

Swept all static/js/ files for unescaped API string interpolations in innerHTML contexts. Fixed three remaining gaps.

## Changes

### static/js/render.js
- Line 785: `${pwned}` → `${esc(pwned)}` — `pwned` is a date string from the victims API (`v.pwned_at`). Date strings are API-controlled and must be escaped per D-06.

### static/js/panels.js
- Line 23: `${label}` → `${esc(label)}` in `addModuleRow()` — `label` comes from SSE event data (`evt.query_type`, `evt.label`, or constructed from `evt.module`/`evt.error`). Error messages in particular can contain arbitrary characters.

### static/js/history.js
- Line 30: `esc(h.query)` → `escAttr(h.query)` in `onclick="rerunSearch('...')"` — Per D-09, attribute value contexts require `escAttr()` which escapes single quotes (preventing JS string breakout in onclick params). `esc()` does not escape `'`.

## Files with no changes required
- `static/js/cases.js` — All API string data escaped. Onclick params use generated `c.id` (Date.now() based, only digits).
- `static/js/export.js` — Uses `textContent` assignment, not innerHTML. Safe by construction.
- `static/js/search.js` — `buildCatChips()` and `buildModChips()` use internal constants from CATEGORIES/MOD_LABELS, not API data.
- `static/js/auth.js`, `static/js/state.js`, `static/js/utils.js` — No innerHTML template literal assignments with API data.
- `static/js/render.js` — All other interpolations verified: numeric values (exempt D-07), pre-escaped HTML strings (badgesHtml, histHtml), textContent assignments.

## Verification

```
esc(pwned)   → render.js:785  ✓
esc(label)   → panels.js:23   ✓
escAttr()    → history.js:30  ✓
```

## Requirements satisfied
- XSS-03: All template literal interpolations in render.js inserting API-controlled data are wrapped in esc()
- XSS-04: Audit confirmed — zero unescaped API string data in innerHTML across static/js/ files
