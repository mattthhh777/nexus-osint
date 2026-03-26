# Phase 02: XSS Sanitization - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-26
**Phase:** 02-xss-sanitization
**Areas discussed:** sanitizeImageUrl() design, Escaping audit scope, Image error handlers, Cross-file audit scope
**Mode:** --auto (all decisions auto-selected)

---

## sanitizeImageUrl() Design

| Option | Description | Selected |
|--------|-------------|----------|
| https-only | Reject all non-https protocols, return empty string on failure | [auto] |
| https + data: for base64 | Allow data: URIs for inline images | |
| Allowlist of CDN domains | Only accept URLs from known Discord/platform CDNs | |

**User's choice:** [auto] https-only (recommended default — most secure)
**Notes:** Place in utils.js alongside esc(). Use URL constructor for validation.

---

## Escaping Audit Scope

| Option | Description | Selected |
|--------|-------------|----------|
| All API strings | esc() on all string data from API; exempt numbers/booleans/internal values | [auto] |
| Display strings only | Only escape values shown to users, skip hidden attributes | |
| Everything | esc() on every interpolation including numbers | |

**User's choice:** [auto] All API strings (recommended default)
**Notes:** Systematic grep verification across all JS files per XSS-04.

---

## Image Error Handlers

| Option | Description | Selected |
|--------|-------------|----------|
| CSS fallback + addEventListener | Remove inline onerror, use JS event listeners after innerHTML | [auto] |
| Keep inline onerror | Accept the script execution vector, focus on URL validation | |
| CSS-only (:not loaded) | Pure CSS approach without any JS error handling | |

**User's choice:** [auto] CSS fallback + addEventListener (recommended default — removes inline script vector)
**Notes:** Aligns with CONCERNS.md recommendation. Pattern: placeholder div sibling + error listener.

---

## Cross-file Audit Scope

| Option | Description | Selected |
|--------|-------------|----------|
| All JS files | Audit all 9 files in static/js/ per XSS-04 text | [auto] |
| render.js only | Focus on the primary rendering file | |
| render.js + cases.js + history.js | Files that generate HTML from data | |

**User's choice:** [auto] All JS files (recommended default — matches XSS-04 requirement)
**Notes:** Files: render.js, cases.js, history.js, search.js, export.js, panels.js, auth.js, state.js, utils.js.

---

## Claude's Discretion

- Implementation order within files
- CSS class names for image fallback placeholders
- Helper function vs inline pattern for img+placeholder
- Grep regex for XSS-04 verification

## Deferred Ideas

- Eliminate inline onclick handlers (separate initiative)
- Migrate escAttr() to context-aware encoding
- CSP hardening after inline handlers removed
