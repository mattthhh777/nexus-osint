# Phase 02: XSS Sanitization - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Ensure no unescaped API data can reach the DOM. Create `sanitizeImageUrl()` to validate image URLs, apply `esc()` to all template literal interpolations of API data, and verify zero unescaped vectors remain across all JS files.

**Out of scope:** Eliminating inline onclick handlers (noted as separate initiative), backend changes, new features, CSP policy changes.

</domain>

<decisions>
## Implementation Decisions

### sanitizeImageUrl() Function (XSS-01, XSS-02)
- **D-01:** Protocol allowlist is **https-only**. Reject `javascript:`, `data:`, `blob:`, `http:`, and any unrecognized scheme.
- **D-02:** On failure (invalid URL or non-https), return **empty string** `''`. Callers must handle empty return gracefully (show placeholder).
- **D-03:** Place the function in **`static/js/utils.js`** alongside `esc()` and `escAttr()` — same security utility family.
- **D-04:** Use the `URL` constructor for parsing. If `new URL()` throws, the input is invalid.
- **D-05:** Apply to **all image URL insertions**, not just Discord — includes Discord avatars, Discord banners, GHunt avatar, Roblox avatar, any other `src=` or `background-image:url()` from API data.

### Escaping Audit (XSS-03, XSS-04)
- **D-06:** `esc()` is required on **all string values from API responses** inserted into HTML. This includes: usernames, emails, passwords, platform names, dates, descriptions, IDs displayed as text.
- **D-07:** Interpolations that are **exempt from esc()**: numeric values (counts, scores, indices), boolean-derived strings, CSS class names from internal logic, element IDs generated internally, animation delays, style values computed from numbers.
- **D-08:** The grep verification (XSS-04) must cover **all files in static/js/**, not just render.js. Files to audit: render.js, cases.js, history.js, search.js, export.js, panels.js, auth.js, state.js, utils.js.
- **D-09:** `escAttr()` is insufficient for onclick handler contexts (misses newlines, backticks). However, eliminating onclick handlers is **out of scope** for this phase. Instead: ensure all data passed to onclick handlers uses `esc()` for display and `escAttr()` for attribute values, accepting the known limitation.

### Image Error Handlers (XSS-02 related)
- **D-10:** Replace inline `onerror` handlers on `<img>` tags with **CSS-based fallback + addEventListener**. Currently lines 341 and 582 in render.js use inline `onerror` — these are script execution vectors.
- **D-11:** Fallback pattern: render a placeholder `<div>` sibling with `display:none`. After innerHTML insertion, query the images and attach `error` event listeners that hide the img and show the placeholder. This removes inline script execution from image elements.

### Claude's Discretion
- Implementation order of changes within each file (top-to-bottom or by severity)
- Exact CSS class names for image fallback placeholders
- Whether to add a helper function for the img+placeholder pattern or inline it
- Grep regex pattern for XSS-04 verification

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Security Context
- `.planning/codebase/CONCERNS.md` — XSS vectors documented in detail (Discord avatar, escaping gaps, onerror handlers, inline onclick)
- `BRIEFING_IMPLEMENTACAO.md` — Original refactoring plan with Phase 4 XSS requirements

### Implementation Files
- `static/js/utils.js` — Contains `esc()` (line 42) and `escAttr()` (line 49) functions; sanitizeImageUrl() will be added here
- `static/js/render.js` — Primary target: 930 lines, 140 template interpolations, 93 existing esc() calls, 11 onclick handlers
- `static/js/cases.js` — Template literals for case card rendering
- `static/js/history.js` — Template literals for history list rendering
- `static/js/search.js` — SSE event parsing with JSON.parse
- `static/js/export.js` — Export rendering
- `static/js/panels.js` — Panel rendering

### Requirements
- `.planning/REQUIREMENTS.md` — XSS-01 through XSS-04 acceptance criteria

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `esc()` in utils.js (line 42): HTML escapes &, <, >, " — already used 93 times in render.js
- `escAttr()` in utils.js (line 49): Attribute escaping for \, ', " — used in onclick handler params
- Template literal pattern throughout render.js — consistent `${esc(value)}` when escaping is applied

### Established Patterns
- All rendering is string concatenation via template literals → innerHTML assignment
- Image rendering uses conditional ternary: `u.avatar_url ? \`<img src="...">\` : \`<div>placeholder</div>\``
- Error handling for images uses inline onerror to show/hide sibling elements

### Integration Points
- `sanitizeImageUrl()` will be called in render.js wherever image URLs from API data are inserted
- After `innerHTML` assignment in render.js functions, new event listeners can be attached to rendered images
- No build step — changes are immediate, loaded as script tags in index.html

### Current XSS Surface (from codebase scout)
- 140 total `${}` interpolations in render.js
- 93 already use `esc()` — approximately 47 unescaped (mix of safe numbers and missing escapes)
- 11 inline onclick handlers with `escAttr()` for params
- 2 inline onerror handlers (lines 341, 582)
- Discord avatar: `src="${esc(u.avatar_url)}"` — escapes HTML but doesn't validate URL protocol
- Discord banner: `background-image:url('${esc(u.banner_url)}')` — same issue
- GHunt avatar: `src="${esc(pic)}"` — same issue

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches for XSS sanitization. Follow OWASP recommendations for DOM-based XSS prevention.

</specifics>

<deferred>
## Deferred Ideas

- **Eliminate all inline onclick handlers** — Replace with data-* attributes + addEventListener. This enables removing `'unsafe-inline'` from CSP script-src. Tracked in CONCERNS.md as a separate initiative.
- **Migrate escAttr() to proper context-aware encoding** — Current implementation is incomplete for JS string contexts. Full fix requires eliminating inline handlers.
- **Content Security Policy hardening** — After inline handlers are removed, tighten CSP to remove `'unsafe-inline'`.

</deferred>

---

*Phase: 02-xss-sanitization*
*Context gathered: 2026-03-26*
