# NexusOSINT — Refactoring Milestone Roadmap

**Milestone:** CSS Token Migration + XSS Sanitization
**Project:** NexusOSINT v3.0.0 (Production at nexusosint.uk)
**Granularity:** Coarse
**Phases:** 2
**Created:** 2026-03-25

---

## Phases

- [ ] **Phase 1: Meridian CSS Token Migration** - All 9 CSS files fully adopt Meridian design system tokens, eliminating every legacy token, hardcoded rgba(), out-of-spec border-radius, and arbitrary spacing/font/shadow value
- [ ] **Phase 2: XSS Sanitization** - All API data inserted into the DOM passes through esc() or sanitizeImageUrl(), with zero unescaped template literal interpolations confirmed by grep

---

## Phase Details

### Phase 1: Meridian CSS Token Migration
**Goal**: Every CSS file uses only Meridian design system tokens — token propagation works correctly, zero legacy tokens remain, and the live site looks identical to before
**Depends on**: Nothing (first phase)
**Requirements**: CSS-01, CSS-02, CSS-03, CSS-04, CSS-05, CSS-06, CSS-07, CSS-08, CSS-09, CSS-10, CSS-11, CSS-12
**Success Criteria** (what must be TRUE):
  1. Changing --color-accent in tokens.css causes ALL amber accent elements on the live site to update simultaneously (token propagation verified end-to-end)
  2. Zero hardcoded rgba() color values remain in any of the 9 CSS files — all replaced by named token references
  3. Zero occurrences of legacy tokens (--bg, --text, --amber, --line, --mono, --sans, --r, --dur-*, --bg2 through --bg5, --red, --green, --blue) remain outside tokens.css
  4. Every border-radius value in the codebase is one of the four design system values: 2px, 4px, 6px, or 999px — no 8px, 10px, 12px, or 14px values remain
  5. A side-by-side visual comparison of the live site before and after migration shows no difference in layout, color, spacing, typography, or shadows
**Plans**: TBD
**UI hint**: yes

### Phase 2: XSS Sanitization
**Goal**: No unescaped API data can reach the DOM — esc() is applied to every template literal interpolation in render.js and sanitizeImageUrl() guards all URL insertions
**Depends on**: Phase 1
**Requirements**: XSS-01, XSS-02, XSS-03, XSS-04
**Success Criteria** (what must be TRUE):
  1. sanitizeImageUrl() rejects javascript: and data: URIs and any non-https URL before they can reach a src= attribute or background-image value — verified by unit test or manual proof
  2. Discord avatar and banner URLs from the OathNet API are visually rendered only when they pass sanitizeImageUrl() — a crafted javascript: avatar_url produces no script execution and falls back to the placeholder
  3. Every template literal interpolation in render.js that inserts API-controlled data is wrapped in esc() — no raw variable interpolations exist for string values from search results
  4. grep across all static/js/ files returns zero instances of unescaped API data interpolated directly into innerHTML template literals
**Plans**: TBD
**UI hint**: yes

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Meridian CSS Token Migration | 3/7 | In Progress|  |
| 2. XSS Sanitization | 0/? | Not started | - |

---

## Coverage

| Requirement | Phase | Status |
|-------------|-------|--------|
| CSS-01 | Phase 1 | Pending |
| CSS-02 | Phase 1 | Pending |
| CSS-03 | Phase 1 | Pending |
| CSS-04 | Phase 1 | Pending |
| CSS-05 | Phase 1 | Pending |
| CSS-06 | Phase 1 | Pending |
| CSS-07 | Phase 1 | Pending |
| CSS-08 | Phase 1 | Pending |
| CSS-09 | Phase 1 | Pending |
| CSS-10 | Phase 1 | Pending |
| CSS-11 | Phase 1 | Pending |
| CSS-12 | Phase 1 | Pending |
| XSS-01 | Phase 2 | Pending |
| XSS-02 | Phase 2 | Pending |
| XSS-03 | Phase 2 | Pending |
| XSS-04 | Phase 2 | Pending |

**v1 requirements mapped:** 16/16
**Unmapped:** 0

---

*Roadmap created: 2026-03-25*
