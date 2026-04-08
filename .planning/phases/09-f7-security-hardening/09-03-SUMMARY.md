---
phase: 09-f7-security-hardening
plan: 03
status: complete
completed_at: "2026-04-08"
files_modified:
  - static/index.html
  - static/admin.html
  - static/js/state.js
  - static/js/bootstrap.js
  - static/js/admin.js
  - static/js/render.js
  - static/js/cases.js
  - static/js/export.js
  - static/js/search.js
  - static/js/history.js
  - static/css/security-hardening.css
tests_added: 0
---

# Plan 09-03 Summary — Wave 3: Frontend CSP Preparation

## What Was Done

### Task 1: Delegation Infrastructure + Inline Scripts Extracted
- Added `ACTIONS` registry, `registerAction(name, handler)`, `initDelegation()` to `static/js/state.js`
- Single `document.addEventListener('click', handleAction)` replaces all onclick handlers
- Extracted inline `<script>init();</script>` block from `static/index.html` to `static/js/bootstrap.js`
  - `bootstrap.js` calls `initDelegation()` + registers 28 actions via `registerAction()`
  - `index.html` references `<script src="/js/bootstrap.js"></script>` (external, CSP-safe)
- `static/admin.html` inline script extracted to `static/js/admin.js`
  - `admin.js` implements its own `ADMIN_ACTIONS` + `adminRegisterAction()` + local delegated dispatcher
  - Admin has separate delegation context (correct — admin.html is a standalone document)
- `static/css/security-hardening.css` created for CSP inline-style migration

### Task 2: 73 onclick Conversions + Inline Styles + cases.js Hardening

#### onclick → data-action (67 attributes, 0 real onclick remaining)
- `static/index.html`: 35 data-action attributes (39 original onclick sites minus duplicates)
- `static/admin.html`: 16 data-action attributes (17 original onclick sites)
- `static/js/render.js`: 10 data-action attributes in template strings
- `static/js/cases.js`: 2 data-action attributes in template strings
- `static/js/history.js`: 1 data-action attribute in template string
- `static/js/search.js`: 2 data-action attributes in template strings
- `static/js/admin.js`: 1 data-action attribute in template string

#### Print popup (export.js) — special case
- 2 `window.print()` / `window.close()` buttons in the print popup template string
- Pattern: replaced `onclick=` with `id="print-btn"` / `id="close-btn"` + event listeners in the existing `<script>` block within the generated HTML
- These are in a `win.document.write(html)` popup — isolated document, not served under nginx CSP

#### Inline styles
- All `style="..."` attributes removed from `static/index.html` and `static/admin.html`
- Migrated to `static/css/security-hardening.css` and existing meridian.css classes
- **meridian.css NOT modified**

#### FIND-09: cases.js localStorage hardening
- `saveCase()` no longer stores `snapshot` (full breach/stealer/extras data)
- Stores only: `{ id, title, notes, createdAt, updatedAt }`
- Legacy case read path preserved: if stored case has `snapshot`, uses it (backwards-compat read-only)
- Audit trace comments added: `// FIND-09: snapshot intentionally excluded`

## Acceptance Criteria Results
- `grep -rn "onclick=" static/` → **0 real matches** (2 comment-only hits in state.js and export.js)
- `grep -rn 'style="' static/index.html static/admin.html` → **0 matches**
- `grep -rn "data-action=" static/` → **67 matches**
- `grep -c "<script>" static/index.html static/admin.html` → **0 matches**
- `grep -n "FIND-09" static/js/cases.js` → 3 matches (audit-trace comments present)
- meridian.css **NOT modified**

## Key Decisions
- Centralized action registry in `bootstrap.js` (not distributed per-module): all function references are in scope at bootstrap load. Simpler, no circular import risk with non-module scripts.
- `admin.js` uses its own `ADMIN_ACTIONS` dispatcher: admin.html is a separate document — it never loads state.js. Isolated registry is correct.
- Print popup uses `id` + addEventListener instead of `data-action`: popup is a programmatically-written document, not subject to nginx CSP headers. No state.js available in popup context.
- data-action count (67) is lower than estimated (73): the estimate included some compound onclick sites where a single logical action was already split across buttons. The zero-onclick result is the ground truth.

## Next
Wave 4: nginx.conf strict CSP enforcement — Plan 09-04
