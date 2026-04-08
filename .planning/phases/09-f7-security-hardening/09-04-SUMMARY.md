---
phase: 09-f7-security-hardening
plan: 04
status: complete
completed_at: "2026-04-08"
files_modified:
  - nginx.conf
tests_added: 0
---

# Plan 09-04 Summary — Wave 4: nginx.conf Strict CSP Enforcement

## What Was Done

### Task 2: Strict CSP + Full D-13 Security Header Set

**Changes from previous nginx.conf:**

| Header | Before | After |
|---|---|---|
| Content-Security-Policy | `unsafe-inline` in script-src + style-src | No `unsafe-inline`; Google Fonts in style-src/font-src |
| Strict-Transport-Security | `max-age=63072000; includeSubDomains; preload` | `max-age=31536000; includeSubDomains` (no preload per D-13) |
| X-Frame-Options | `DENY` | `DENY` (unchanged) |
| X-Content-Type-Options | `nosniff` | `nosniff` (unchanged) |
| Referrer-Policy | `no-referrer` | `strict-origin-when-cross-origin` |
| Permissions-Policy | already present | `geolocation=(), microphone=(), camera=()` |

**nginx inheritance trap fix:**
- `/css/` location block: defines own `add_header Cache-Control` → server-block headers were lost → all 6 security headers now repeated inside the block
- `/js/` location block: same issue → headers repeated
- `location /` block: defines own `add_header Cache-Control` → headers repeated
- Result: every response path emits all 6 security headers

## Acceptance Criteria Results
- `grep -c "Content-Security-Policy" nginx.conf` → **4** (server + /css/ + /js/ + /) ✅
- `grep -c "Strict-Transport-Security" nginx.conf` → **4** ✅
- `grep -c "X-Content-Type-Options" nginx.conf` → **4** ✅
- `grep -c "X-Frame-Options" nginx.conf` → **4** ✅
- `grep -c "Referrer-Policy" nginx.conf` → **4** ✅
- `grep -c "Permissions-Policy" nginx.conf` → **4** ✅
- `grep -c "unsafe-inline" nginx.conf` → **0** ✅
- `grep -n "preload" nginx.conf` → **0** ✅
- `grep -c "limit_req_zone" nginx.conf` → **2** (unchanged) ✅

## Key Decisions
- Google Fonts kept in `style-src`/`font-src`: removing them would cause font fallbacks + DevTools CSP violations from the `<link>` tag in index.html. Allowing external CDN for fonts is a standard, accepted CSP trade-off.
- No `preload` in HSTS: D-13 explicit requirement. Preload is irrevocable and requires domain readiness verification.
- `Referrer-Policy: strict-origin-when-cross-origin` (not `no-referrer`): allows same-origin referer for internal navigation; strips referer for cross-origin requests.

## Verification (to be done on VPS after deploy)
```bash
# After docker compose up and nginx reload:
curl -sI https://nexusosint.uk/ | grep -iE "content-security-policy|strict-transport|x-content-type|x-frame|referrer-policy|permissions-policy"
curl -sI https://nexusosint.uk/css/meridian.css | grep -iE "content-security-policy|x-content-type"
curl -sI https://nexusosint.uk/js/state.js | grep -iE "content-security-policy|x-content-type"
```

## Next
Phase 09 (F7 Security Hardening) complete — deploy to VPS and verify headers live.
