# Phase 02: XSS Sanitization - Research

**Researched:** 2026-03-26
**Domain:** DOM-based XSS prevention in vanilla JS template literal rendering
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**sanitizeImageUrl() Function (XSS-01, XSS-02)**
- D-01: Protocol allowlist is https-only. Reject `javascript:`, `data:`, `blob:`, `http:`, and any unrecognized scheme.
- D-02: On failure (invalid URL or non-https), return empty string `''`. Callers must handle empty return gracefully (show placeholder).
- D-03: Place the function in `static/js/utils.js` alongside `esc()` and `escAttr()` — same security utility family.
- D-04: Use the `URL` constructor for parsing. If `new URL()` throws, the input is invalid.
- D-05: Apply to all image URL insertions, not just Discord — includes Discord avatars, Discord banners, GHunt avatar, Roblox avatar, any other `src=` or `background-image:url()` from API data.

**Escaping Audit (XSS-03, XSS-04)**
- D-06: `esc()` is required on all string values from API responses inserted into HTML. This includes: usernames, emails, passwords, platform names, dates, descriptions, IDs displayed as text.
- D-07: Interpolations exempt from `esc()`: numeric values (counts, scores, indices), boolean-derived strings, CSS class names from internal logic, element IDs generated internally, animation delays, style values computed from numbers.
- D-08: The grep verification (XSS-04) must cover all files in `static/js/`, not just render.js. Files to audit: render.js, cases.js, history.js, search.js, export.js, panels.js, auth.js, state.js, utils.js.
- D-09: `escAttr()` is insufficient for onclick handler contexts. Ensure all data passed to onclick handlers uses `esc()` for display and `escAttr()` for attribute values, accepting the known limitation.

**Image Error Handlers (XSS-02 related)**
- D-10: Replace inline `onerror` handlers on `<img>` tags with CSS-based fallback + addEventListener. Currently lines 341 and 582 in render.js use inline `onerror` — these are script execution vectors.
- D-11: Fallback pattern: render a placeholder `<div>` sibling with `display:none`. After innerHTML insertion, query the images and attach `error` event listeners that hide the img and show the placeholder. This removes inline script execution from image elements.

### Claude's Discretion
- Implementation order of changes within each file (top-to-bottom or by severity)
- Exact CSS class names for image fallback placeholders
- Whether to add a helper function for the img+placeholder pattern or inline it
- Grep regex pattern for XSS-04 verification

### Deferred Ideas (OUT OF SCOPE)
- Eliminate all inline onclick handlers — Replace with data-* attributes + addEventListener. Enables removing `'unsafe-inline'` from CSP script-src. Tracked in CONCERNS.md as a separate initiative.
- Migrate escAttr() to proper context-aware encoding — full fix requires eliminating inline handlers.
- Content Security Policy hardening — after inline handlers are removed, tighten CSP to remove `'unsafe-inline'`.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| XSS-01 | sanitizeImageUrl() function validates all URLs before insertion into src= or background-image (reject non-https, reject javascript: protocol) | D-01 through D-05 define the full contract. URL constructor API verified. 3 call sites identified in render.js. |
| XSS-02 | Discord avatar and banner URLs from OathNet API pass through sanitizeImageUrl() before DOM insertion | Lines 341, 345 in render.js confirmed. onerror inline handlers at lines 341, 582 must also be replaced per D-10/D-11. |
| XSS-03 | esc() function applied to ALL template literal interpolations in render.js where API data is inserted into HTML | 140 total interpolations audited. 93 already use esc(). ~47 unescaped — audit shows most are numeric/internal (exempt), but escaping gaps exist in cases.js onclick attrs. |
| XSS-04 | grep confirms zero instances of unescaped API data in template literals across all JS files | Grep pattern documented. Files to cover: render.js, cases.js, history.js, search.js, export.js, panels.js, auth.js, state.js, utils.js. export.js uses plain text (not innerHTML) — safe by construction. |
</phase_requirements>

---

## Summary

Phase 02 is a focused security hardening pass on the vanilla JS frontend. The attack surface is DOM-based XSS via template literal innerHTML assignment in `render.js` — the application renders all OSINT module results by building HTML strings and assigning them to `element.innerHTML`. The existing `esc()` function in `utils.js` (line 42) is already applied to 93 of 140 interpolations in render.js, but three categories of XSS risk remain: (1) image URLs from API data bypass URL-scheme validation even when HTML-escaped, (2) inline `onerror` event handlers on `<img>` tags are script execution vectors, and (3) a small number of string interpolations from API data still lack `esc()` wrapping.

The implementation is pure JavaScript with no build step, no framework, and no library dependencies. All fixes are applied directly to `static/js/utils.js` and `static/js/render.js` (primary) plus verification sweeps across `cases.js`, `history.js`, and the remaining JS files. The `URL` constructor is the correct tool for protocol validation — it is universally available in modern browsers and throws synchronously on malformed input, making it ideal for the sanitizeImageUrl() guard.

The deferred onClick handler remediation (which would eliminate `escAttr()` context issues entirely) is explicitly out of scope. The plan must work within the existing onclick-in-template-literal pattern, accepting the known limitation documented in D-09.

**Primary recommendation:** Implement sanitizeImageUrl() in utils.js first (single function, 5 lines), then apply it to all 3 image URL insertion sites in render.js, then replace the 2 inline onerror handlers, then sweep render.js for any remaining unescaped string interpolations from API data.

---

## Standard Stack

### Core (already present, no installation needed)

| Asset | Location | Purpose | Notes |
|-------|----------|---------|-------|
| `esc()` | `static/js/utils.js` line 42 | HTML-escapes &, <, >, " for text content | Already used 93× in render.js |
| `escAttr()` | `static/js/utils.js` line 49 | Attribute escaping for \, ', " | Used in onclick params — known incomplete for newlines/backticks |
| `URL` constructor | Browser built-in | Parse and validate URLs | Throws on invalid input; `.protocol` property gives scheme |
| Template literal + innerHTML | Pattern throughout render.js | All results rendering | No build step — changes are live immediately |

### No external libraries required

This phase installs nothing. sanitizeImageUrl() is implemented as a plain JavaScript function using the built-in `URL` API, added to the existing `utils.js` file.

---

## Architecture Patterns

### Pattern 1: sanitizeImageUrl() Contract

**What:** A pure function that validates a URL string and returns the validated URL or empty string.

**When to use:** At every point where an API-sourced value is inserted into `src=` or `background-image:url(...)`.

**Correct implementation (verified against OWASP DOM XSS Prevention Cheat Sheet):**

```javascript
// Place in static/js/utils.js, after escAttr() at line 52
function sanitizeImageUrl(url) {
  if (!url) return '';
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' ? url : '';
  } catch (e) {
    return '';
  }
}
```

**Why URL constructor:** `new URL()` throws a `TypeError` on any value that is not a valid URL (empty string, relative path, `javascript:alert(1)` without a host — actually, note below). It surfaces the `.protocol` property which is normalized and reliable for allowlist checking.

**Critical edge case — URL constructor does NOT throw for `javascript:` URIs:**
`new URL('javascript:alert(1)')` is VALID and parses successfully with `protocol === 'javascript:'`. The function above handles this correctly (protocol check returns `''`), but this is the key reason you cannot simply check `new URL()` without also checking `.protocol`. The try/catch alone is insufficient — you must check protocol after parsing.

**Callers handle empty return:** When `sanitizeImageUrl()` returns `''`, callers must not insert the empty string into `src=` (a browser will request the current page URL as a relative path). Use a conditional: if `sanitizeImageUrl(url)` is falsy, use placeholder instead.

### Pattern 2: Applying sanitizeImageUrl() at Call Sites

Three call sites in render.js:

**Call site 1 — Discord avatar (render.js line 341):**
```javascript
// Before:
const avatarHtml = u.avatar_url
  ? `<img class="discord-avatar" src="${esc(u.avatar_url)}" alt="avatar" onerror="...">`
    + `<div class="discord-avatar-placeholder" style="display:none">💬</div>`
  : `<div class="discord-avatar-placeholder">💬</div>`;

// After:
const safeAvatarUrl = sanitizeImageUrl(u.avatar_url);
const avatarHtml = safeAvatarUrl
  ? `<img class="discord-avatar" src="${safeAvatarUrl}" alt="avatar" data-fallback="true">`
    + `<div class="discord-avatar-placeholder" style="display:none">💬</div>`
  : `<div class="discord-avatar-placeholder">💬</div>`;
```

**Call site 2 — Discord banner (render.js line 345):**
```javascript
// Before:
const bannerStyle = u.banner_url
  ? `class="discord-banner has-banner" style="background-image:url('${esc(u.banner_url)}')"`
  : `class="discord-banner"`;

// After:
const safeBannerUrl = sanitizeImageUrl(u.banner_url);
const bannerStyle = safeBannerUrl
  ? `class="discord-banner has-banner" style="background-image:url('${safeBannerUrl}')"`
  : `class="discord-banner"`;
```

**Call site 3 — GHunt avatar (render.js line 580):**
```javascript
// Before:
${pic ? `<img src="${esc(pic)}" alt="Google avatar"
    style="..." onerror="this.style.display='none'">` : ''}

// After:
${sanitizeImageUrl(pic) ? `<img src="${sanitizeImageUrl(pic)}" alt="Google avatar"
    style="..." data-fallback="true">` : ''}
```

Note: `sanitizeImageUrl(pic)` is called twice in the after pattern above — to avoid this, precompute `const safePic = sanitizeImageUrl(pic)` before the template literal.

### Pattern 3: Replacing Inline onerror Handlers (D-10, D-11)

**The problem:** `onerror="this.style.display='none';..."` is an inline event handler that fires script execution.

**The solution:** After innerHTML assignment, query newly inserted images and attach event listeners programmatically.

```javascript
// After setting el.innerHTML = ... (at the end of renderExtras() or equivalent):
el.querySelectorAll('img[data-fallback]').forEach(img => {
  img.addEventListener('error', () => {
    img.style.display = 'none';
    const placeholder = img.nextElementSibling;
    if (placeholder) placeholder.style.display = 'flex';
  });
});
```

**Key structural requirement:** The `<img>` tag and its sibling placeholder `<div>` must remain adjacent in the generated HTML. The `nextElementSibling` pattern works because the placeholder div is always rendered immediately after the img. Mark images that need error handling with `data-fallback="true"` so the event listener attachment loop is scoped and unambiguous.

**Where to apply:**
- Discord avatar at line 341 — already has sibling placeholder div structure
- GHunt avatar at line 580 — currently no sibling placeholder; the after-innerHTML attachment pattern changes this to `img.style.display = 'none'` only (no placeholder needed based on existing UI design)

**Rendering pipeline:** The Discord card HTML is built into `parts[]` array and then joined into `el.innerHTML` in a single assignment at line 702. The event listener attachment must happen AFTER that innerHTML assignment, not inside the template string.

### Pattern 4: esc() Exemption Rules (D-07)

**Exempt from esc()** — verified safe, no wrapping needed:

| Pattern | Example | Why safe |
|---------|---------|----------|
| Numeric literals | `${c.val}`, `${docs}`, `${i}` | Numbers cannot contain HTML |
| Numeric variables from API (number type) | `${o.breach_count}`, `${victims.total}` | JS number coercion cannot produce HTML |
| Boolean-derived strings | `${d.proxy ? '⚠ Yes' : '✓ No'}` | Literal strings from code, not from API |
| CSS classes from internal logic | `${'sev-' + sev}` where sev is computed internally | Not from API |
| animation-delay | `${i * 0.07}s` | Arithmetic result |
| Internal IDs | `${nodeId}` where nodeId is `replace(/[^a-zA-Z0-9-_]/g,'_')` sanitized | Sanitized before use |
| `toLocaleString()` output | `${total.toLocaleString()}` | Number formatting, not API string |

**Must have esc()** — API string values:

| Pattern | Fields |
|---------|--------|
| User-supplied identifiers | username, global_name, gamertag, personaname |
| Free-text fields | description, realname, error messages |
| Dates from API | creation_date, pwned_at, timestamp strings |
| IDs rendered as text | discord id, steam id, gaia_id, uuid |
| Platform/category names | platform, category in social results |
| URL display text | `p.url.slice(0,60)` in social table |

### Pattern 5: The href= Special Case

The `href="${esc(p.url)}"` pattern in the social results (lines 258, 267) uses `esc()` which HTML-escapes but does not validate the URL protocol. This allows `javascript:alert()` in href attributes.

**Decision from CONTEXT.md:** D-05 specifies that sanitizeImageUrl() applies to `src=` and `background-image`. The href= case for social profile URLs is not explicitly addressed. However, CONCERNS.md documents the XSS surface via href.

**Research finding:** OWASP DOM XSS Prevention recommends URL validation for href attributes when URLs come from untrusted data. The social profile URLs (p.url) come from the Sherlock module — these are URLs constructed by the backend from known platform templates (e.g., `https://twitter.com/username`), making them lower risk than pure user-supplied data. The GHunt URLs (reviews_url, photos_url) come from OathNet API and carry slightly higher risk.

**Recommendation (Claude's discretion):** Apply `sanitizeImageUrl()` to href values from GHunt (reviews_url, photos_url) and Steam (profile.profileurl) since these are raw API data. For social profile URLs (p.url), esc() is acceptable given Sherlock constructs them from templates — but this should be documented as a known remaining risk rather than a fixed gap.

### Anti-Patterns to Avoid

- **Using esc() alone for image src attributes:** `esc()` does not validate URL scheme. `esc('javascript:alert()')` returns `'javascript:alert()'` — still executable in src.
- **Checking for empty string after sanitizeImageUrl() with falsy check only:** An API value of `'0'` is falsy — use `=== ''` check or simply `if (!sanitizeImageUrl(url))`.
- **Attaching error listeners before innerHTML is set:** Event listeners on elements not yet in the DOM are lost when innerHTML is replaced.
- **Calling sanitizeImageUrl() twice in a template literal:** Precompute into a variable before the template.
- **Escaping numeric fields:** `${esc(o.breach_count)}` — `esc()` returns `'─'` when the value is 0/falsy because `esc(0)` returns `'─'` per line 43. This would break count displays that legitimately show 0.

**CRITICAL: esc(0) returns '─', not '0'**

The existing `esc()` function has this behavior:
```javascript
function esc(s) {
  if (!s) return '─';  // 0, '', null, undefined all return '─'
  return String(s)...
}
```

This means `esc(0)` returns `'─'`, not `'0'`. This is why numeric values MUST NOT be wrapped in `esc()`. The exemption in D-07 for numeric values is not just a style preference — it is functionally required. Wrapping counts in `esc()` would display `─` instead of `0` wherever a count is zero.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| URL scheme validation | Custom regex for `javascript:`, `data:`, etc. | `new URL()` + `.protocol` check | Regex fails on obscure encodings; URL constructor normalizes the scheme |
| HTML entity encoding | Custom replace chains | `esc()` already in utils.js | Already battle-tested and used 93× in codebase |
| Attribute encoding | Custom escaping | `escAttr()` already in utils.js | Consistent with existing pattern; full fix deferred per decisions |

**Key insight:** The infrastructure already exists. This phase is entirely about applying existing tools (`esc()`, the `URL` API) to the remaining unprotected insertion points, plus adding the one missing function (`sanitizeImageUrl()`).

---

## Complete XSS Surface Inventory

This section maps every image URL insertion site and every remaining unescaped API string interpolation identified in the codebase audit.

### Image URL Insertion Sites (require sanitizeImageUrl)

| File | Line | Variable | API Source | Current State | Required Fix |
|------|------|----------|------------|---------------|--------------|
| render.js | 341 | `u.avatar_url` | OathNet discord endpoint | `esc()` only | `sanitizeImageUrl()` + remove onerror |
| render.js | 345 | `u.banner_url` | OathNet discord endpoint | `esc()` only | `sanitizeImageUrl()` |
| render.js | 580 | `pic` (GHunt profile picture) | OathNet ghunt endpoint | `esc()` only | `sanitizeImageUrl()` + remove onerror |

**Roblox avatar (rAvatar):** Extracted from API at line 504 but never inserted into DOM — not currently a risk. The variable is declared but the Roblox card template does not include an `<img>` tag. If an img tag is ever added, sanitizeImageUrl() must be applied.

**discord_roblox avatar:** Extracted at line 683 but never inserted into DOM — same situation as rAvatar.

### Inline onerror Handlers (require replacement)

| File | Line | Handler | Replacement Pattern |
|------|------|---------|---------------------|
| render.js | 341 | `onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"` | `data-fallback="true"` + post-innerHTML addEventListener |
| render.js | 582 | `onerror="this.style.display='none'"` | `data-fallback="true"` + post-innerHTML addEventListener |

### Unescaped API String Interpolations Found During Audit

The following are the key patterns to verify during implementation. Most unescaped `${}` in render.js are numeric/internal (safe per D-07). Specific gaps:

**render.js — cases that need review:**

| Line | Pattern | Safe? | Reason |
|------|---------|-------|--------|
| 258 | `${p.icon||'🔗'}` | Yes | Emoji literals from code, not from API |
| 363 | `style="width:56px..."` | Yes | Hardcoded inline style |
| 431 | `${profile.communityvisibilitystate===3?'Public':'Private'}` | Yes | Boolean-derived |
| 447 | `${scr.gamerscore || m.gamerscore || '─'}` | No — should be `esc(String(gamerscore))` | API string used as text |
| 460 | `${esc(String(gamerscore))}` | Yes — already escaped | Already fixed |
| 481 | `${g.completionPercentage!=null ? esc(String(g.completionPercentage))+'%' : ''}` | Yes | Already escaped |
| 660 | `${victims.total}` | Yes | Number |
| 671 | `${victims.total - victims.items.length}` | Yes | Arithmetic |

**cases.js — gaps identified:**

| Line | Pattern | Issue |
|------|---------|-------|
| 111 | `onclick="loadCase('${c.id}')"` | `c.id` is internally generated (`'case_' + Date.now()`) — safe |
| 113 | `<span style="color:${rc}">${c.rl} ${c.risk}</span>` | `c.rl` comes from `riskLabel()` which returns `['CRITICAL'|'HIGH'|'MEDIUM'|'LOW', color]` — internal strings, safe. `c.risk` is a number. |
| 114 | `${c.breach_count}B ${c.stealer_count}S ${c.social_count}Soc` | Numbers — safe |
| 115 | `${esc(c.timestamp)}` | Already escaped |
| 118 | `onclick="deleteCase('${c.id}')"` | `c.id` is internal — safe |
| 122-123 | `onblur="saveCaseNote('${c.id}', this.value)"` and `onfocus="...cases.find(x=>x.id==='${c.id}')..."` | `c.id` is internal — safe |

**history.js — gaps identified:**

| Line | Pattern | Issue |
|------|---------|-------|
| 30 | `onclick="rerunSearch('${esc(h.query)}')"` | `esc()` applied but `escAttr()` would be more appropriate for attribute context — known limitation per D-09 |
| 33 | `${h.rl} ${h.risk}` | `h.rl` from internal `riskLabel()` — safe. `h.risk` is number — safe. |

**export.js — safe by construction:** All export functions build plain text strings joined with `\n` and sent to clipboard via `writeClipboard()`. They never call `innerHTML`. No escaping needed here — the data goes to clipboard text, not HTML.

**panels.js — safe:** Uses `textContent`, `classList`, `createElement`, and `insertBefore` (DOM API, not innerHTML). No template literals with API data.

**auth.js, state.js, utils.js — safe:** auth.js uses `textContent` assignments; state.js is pure state; utils.js is pure functions.

**search.js — verify:** SSE event parsing uses `JSON.parse()` — not an innerHTML concern, but verify no parsed API values are interpolated into innerHTML without esc().

---

## Common Pitfalls

### Pitfall 1: esc(0) Returns '─' Not '0'

**What goes wrong:** Developer wraps a count field in `esc()` to "be safe," and all zero counts display as `─` instead of `0`.

**Why it happens:** `esc()` line 43 does `if (!s) return '─'` — 0 is falsy in JS.

**How to avoid:** Never wrap numeric values in `esc()`. The D-07 exemption for numeric types is functionally required, not just stylistic.

**Warning signs:** Stats showing `─ — ─` instead of `0 0 0` after implementation.

### Pitfall 2: URL Constructor Allows javascript: Protocol

**What goes wrong:** Developer writes `try { new URL(url); return url; } catch { return ''; }` without checking `.protocol`, assuming that if it parses it's safe.

**Why it happens:** `new URL('javascript:alert(1)')` does NOT throw — it parses with `protocol === 'javascript:'`. The try/catch alone does not prevent this attack.

**How to avoid:** Always check `parsed.protocol === 'https:'` after parsing. Return `''` for any other protocol, including `http:`, `data:`, `blob:`.

**Warning signs:** Crafted test `sanitizeImageUrl('javascript:alert(1)')` returns a non-empty string.

### Pitfall 3: Event Listeners Attached Before innerHTML Assignment

**What goes wrong:** addEventListener calls run, but then innerHTML is replaced, destroying the DOM elements the listeners were attached to.

**Why it happens:** In render.js, the Discord card HTML is built into the `parts[]` array across multiple iterations, and then all parts are joined and assigned to `el.innerHTML` at line 702 in a single write. Any event listener attachment must happen AFTER this single assignment.

**How to avoid:** Structure the implementation as:
1. Build `parts[]` array (including `data-fallback="true"` markers in img tags)
2. Assign `el.innerHTML = parts.join(...)`
3. THEN call `el.querySelectorAll('img[data-fallback]').forEach(...)` to attach error listeners

**Warning signs:** Image error fallback never triggers.

### Pitfall 4: sanitizeImageUrl('') Behavior

**What goes wrong:** An empty avatar_url string is sanitized to `''`, then used in `const safeUrl = sanitizeImageUrl('')` and the caller checks `if (safeUrl)` — this is correct. But if the original conditional was `if (u.avatar_url)` and the developer changes it to `if (safeUrl)`, they may introduce a subtle bug where a valid-but-sanitized-away URL shows a placeholder instead of nothing (which was the original behavior).

**How to avoid:** Verify the placeholder shown when `sanitizeImageUrl()` returns `''` is the same placeholder shown when `u.avatar_url` is null/undefined. The user experience should be identical: placeholder emoji, no broken image icon.

### Pitfall 5: Grep Verification Produces False Negatives

**What goes wrong:** The XSS-04 grep pattern does not catch all unescaped interpolations because of line wrapping, string concatenation (non-template style), or `+` string joins.

**Why it happens:** render.js uses both template literals AND string concatenation with `+`. The breach table rows (lines 96-113) use string concatenation, not template literals.

**How to avoid:** Run two grep passes:
- Template literal pattern: `\$\{[^}]*\}` in context of template literals (backtick strings)
- String concatenation pattern: `'` + variable + `'` patterns in innerHTML-assigned strings

The full XSS-04 verification requires code review of string concatenation patterns, not just template literal grep.

---

## Code Examples

### sanitizeImageUrl() — Complete Function

```javascript
// Source: OWASP DOM XSS Prevention Cheat Sheet + MDN URL API
// Add to static/js/utils.js after escAttr() at line 52

function sanitizeImageUrl(url) {
  if (!url) return '';
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' ? url : '';
  } catch (e) {
    return '';
  }
}
```

### Post-innerHTML Event Listener Attachment

```javascript
// After el.innerHTML = parts.join('<hr ...>') at line 702 in renderExtras():
el.querySelectorAll('img[data-fallback]').forEach(img => {
  img.addEventListener('error', function() {
    this.style.display = 'none';
    const sibling = this.nextElementSibling;
    if (sibling) sibling.style.display = 'flex';
  });
});
```

### Discord Avatar Template (after fix)

```javascript
// Source: Current render.js lines 340-343, modified per D-01/D-10/D-11
const safeAvatarUrl = sanitizeImageUrl(u.avatar_url);
const avatarHtml = safeAvatarUrl
  ? `<img class="discord-avatar" src="${safeAvatarUrl}" alt="avatar" data-fallback="true">`
    + `<div class="discord-avatar-placeholder" style="display:none">💬</div>`
  : `<div class="discord-avatar-placeholder">💬</div>`;
```

### Discord Banner Template (after fix)

```javascript
// Source: Current render.js line 344-346, modified per D-01
const safeBannerUrl = sanitizeImageUrl(u.banner_url);
const bannerStyle = safeBannerUrl
  ? `class="discord-banner has-banner" style="background-image:url('${safeBannerUrl}')"`
  : `class="discord-banner"`;
```

### GHunt Avatar Template (after fix)

```javascript
// Source: Current render.js lines 579-582, modified per D-01/D-10
const safePic = sanitizeImageUrl(pic);
// In the template:
${safePic ? `<img src="${safePic}" alt="Google avatar"
    style="width:56px;height:56px;border-radius:50%;border:2px solid var(--line2);flex-shrink:0"
    data-fallback="true">` : ''}
// Note: GHunt avatar has no sibling placeholder — the error listener just hides the img
```

### XSS-04 Grep Pattern (Claude's discretion — recommended approach)

```bash
# Find template literal interpolations NOT wrapped in esc() or sanitizeImageUrl()
# in files that assign to innerHTML
# Run from project root:
grep -n '\${[^}]*}' static/js/render.js | grep -v 'esc(' | grep -v 'sanitizeImageUrl(' | grep -v 'encodeURIComponent('
```

This grep is a starting point, not a complete verification. Results must be reviewed manually against the D-07 exemption list (numeric, boolean-derived, internal strings).

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| innerHTML with unvalidated URLs | sanitizeImageUrl() guard before insertion | Eliminates javascript: and data: URI injection via img src / CSS background-image |
| Inline onerror event handlers | Post-innerHTML addEventListener via data-fallback marker | Removes script execution vectors from img markup |
| esc() applied inconsistently | esc() applied to all API string values, with explicit numeric exemption | Closes remaining text-context XSS vectors |

---

## Open Questions

1. **href= attributes from API data**
   - What we know: `p.url` (social profiles), `profile.profileurl` (Steam), `reviews_url`, `photos_url` (GHunt) are inserted into `href="${esc(...)}"`  — HTML-escaped but not protocol-validated.
   - What's unclear: Requirements XSS-01 through XSS-04 focus on `src=` and `background-image`. The CONTEXT.md D-05 specifies sanitizeImageUrl() for "src= or background-image:url()". The href= case is not explicitly in scope.
   - Recommendation: Apply `sanitizeImageUrl()` to GHunt URLs (reviews_url, photos_url) and Steam profileurl as a conservative extension of D-05. For social profile URLs (p.url) from Sherlock, esc() is acceptable since Sherlock constructs them from known templates. Document this gap.

2. **XSS-04 grep — string concatenation patterns**
   - What we know: render.js breach table rows (lines 96-113) use string concatenation with `+`, not template literals. These are already wrapped in `esc()`.
   - What's unclear: Whether any concatenation-style innerHTML assignment elsewhere has gaps that the template-literal grep would miss.
   - Recommendation: Verify breach/stealer concatenation-style rows manually in addition to the grep pass. They are already escaped, but the grep verification should document that concatenation patterns were also checked.

---

## Environment Availability

Step 2.6: SKIPPED — this phase is purely JavaScript code changes with no external dependencies. No tools, services, runtimes, or databases are required beyond the browser and a text editor. No installation steps needed.

---

## Validation Architecture

`workflow.nyquist_validation` is explicitly `false` in `.planning/config.json`. This section is skipped.

---

## Project Constraints (from CLAUDE.md)

These directives apply to Phase 02 and must be verified during planning:

| Constraint | Implication for Phase 02 |
|------------|--------------------------|
| Stack lock: FastAPI + vanilla HTML/CSS/JS + SQLite + Docker — no framework changes | sanitizeImageUrl() must be plain JS. No library imports. |
| Zero visual regression | Image fallback placeholder must look identical to current onerror behavior. Placeholder div already exists in Discord avatar HTML — structure preserved. |
| File protection: Do NOT modify docker-compose.yml, nginx.conf, Dockerfile, entrypoint.sh, admin.html, modules/*.py | All changes are in `static/js/utils.js` and `static/js/render.js` only. |
| No test framework present | XSS-04 verification is manual grep + code review, not automated test. |
| 2-space indentation in JS files | New code in utils.js and render.js must use 2-space indentation. |
| Single quotes for strings in JS | `sanitizeImageUrl()` implementation uses single quotes. |
| Section banners: `// ── subsection ──` style | If adding a subsection banner for sanitizeImageUrl in utils.js, use this pattern. |
| camelCase for function names | `sanitizeImageUrl` is already camelCase. |

---

## Sources

### Primary (HIGH confidence)

- Direct audit of `static/js/render.js` (930 lines, read in full) — all template interpolations catalogued
- Direct audit of `static/js/utils.js` — existing esc() and escAttr() contract confirmed
- Direct audit of `static/js/cases.js`, `history.js`, `panels.js`, `export.js` — secondary files reviewed
- `.planning/codebase/CONCERNS.md` — XSS vector documentation verified against actual code
- `.planning/phases/02-xss-sanitization/02-CONTEXT.md` — all locked decisions read and applied

### Secondary (MEDIUM confidence)

- OWASP DOM XSS Prevention Cheat Sheet (authoritative, well-known) — URL constructor pattern for sanitizeImageUrl(), href= attribute risk classification
- MDN Web Docs: URL API — `new URL()` behavior with `javascript:` URIs (does not throw; returns protocol 'javascript:')

### Tertiary (LOW confidence)

- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all functions and their behavior verified by direct code reading
- Architecture patterns: HIGH — patterns derived from actual code, not assumptions
- Pitfalls: HIGH — esc(0) behavior and URL constructor javascript: behavior verified from source code

**Research date:** 2026-03-26
**Valid until:** 2026-06-26 (stable — pure JS, no external library versions to expire)
