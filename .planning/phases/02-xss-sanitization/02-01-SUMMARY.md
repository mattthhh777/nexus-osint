---
phase: 02-xss-sanitization
plan: 01
status: complete
completed: 2026-03-26
---

# Plan 02-01 Summary: Image URL Sanitization

## What was done

Added `sanitizeImageUrl()` to `static/js/utils.js` and applied it to all image/URL insertion sites in `static/js/render.js`. Removed all inline `onerror=` handlers.

## Changes

### static/js/utils.js
- Added `sanitizeImageUrl(url)` after `escAttr()` (line 55)
- Uses `URL` constructor + `https:` protocol allowlist
- Returns `''` on invalid URL, non-https, or null/undefined input

### static/js/render.js
- Discord avatar: `esc(u.avatar_url)` → `sanitizeImageUrl(u.avatar_url)` via precomputed `safeAvatarUrl`; inline `onerror` removed; `data-fallback="true"` added
- Discord banner: `esc(u.banner_url)` → `sanitizeImageUrl(u.banner_url)` via precomputed `safeBannerUrl`
- GHunt avatar: `esc(pic)` → `sanitizeImageUrl(pic)` via precomputed `safePic`; inline `onerror` removed; `data-fallback="true"` added
- GHunt href URLs: `reviews_url` and `photos_url` sanitized via `safeReviewsUrl` / `safePhotosUrl`
- Steam profileurl: sanitized via `safeSteamUrl` before href insertion
- Post-innerHTML event listener added: `el.querySelectorAll('img[data-fallback]').forEach(...)` attaches `error` handlers programmatically

## Verification

```
function sanitizeImageUrl  → utils.js:55 ✓
sanitizeImageUrl( calls    → 6 in render.js ✓
onerror= remaining         → 0 ✓
data-fallback markers      → 4 ✓
querySelectorAll listener  → render.js:713 ✓
```

## Requirements satisfied
- XSS-01: `javascript:` and `data:` URIs rejected by protocol allowlist
- XSS-02: Discord avatar/banner, GHunt avatar, GHunt hrefs, Steam profileurl all sanitized; inline onerror handlers eliminated
