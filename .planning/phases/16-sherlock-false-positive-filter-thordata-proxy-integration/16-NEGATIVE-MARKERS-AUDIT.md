# Phase 16 — Negative Markers Manual Validation Audit

**Date validated:** 2026-05-01
**Validator:** Claude (Phase 16 Plan 04 execution, automated fetch via httpx)
**Test username:** `nx_fp_check_zzz_999` (nonexistent account)

---

## Method

Each platform URL was fetched via `httpx.Client` with a real browser User-Agent (`Chrome/124.0.0.0`) and `follow_redirects=True`. The first 800KB of response body was inspected for each planned `negative_markers` string from the Phase 16 Plan 02 `PLATFORMS` dict. Status code, body excerpt (first 300 chars), and final URL after redirects were recorded. Fetch was performed directly without Thordata proxy (proxy not active in local dev environment). Where the observed response disagreed with the planned marker, the `PLATFORMS` entry in `modules/sherlock_wrapper.py` was updated inline and documented below.

---

## Platform 1: GitHub

**URL tested:** `https://github.com/nx_fp_check_zzz_999`
**Planned negative markers:** `["Not Found", "Page not found"]`

**Observed:**
- HTTP Status: `404`
- Body (first 200 chars): `'Not Found'` (9 bytes total — plain-text response, no HTML)
- Final URL: `https://github.com/nx_fp_check_zzz_999` (no redirect)

**Marker check:**
- `"Not Found"` — FOUND at index 0 (exact match)
- `"Page not found"` — NOT FOUND (body is only 9 bytes; secondary marker never reached)

**Verdict:** PASS — Primary marker `"Not Found"` correctly triggers the negative short-circuit. Secondary marker `"Page not found"` is absent but harmless (OR logic — any single marker match rejects). No change needed.

**Action taken:** None. `modules/sherlock_wrapper.py` GitHub entry unchanged.

---

## Platform 2: Reddit

**URL tested:** `https://www.reddit.com/user/nx_fp_check_zzz_999`
**Planned negative markers:** `["sorry, nobody on reddit goes by that name"]`

**Observed:**
- HTTP Status: `200`
- Body (first 200 chars): `'\n  <!DOCTYPE html>\n  <html lang="en">\n    <head>...<title>Reddit - Please wait for verification</title>...'`
- Final URL: `https://www.reddit.com/user/nx_fp_check_zzz_999/` (trailing slash added)
- Title: `"Reddit - Please wait for verification"`

**Marker check:**
- `"sorry, nobody on reddit goes by that name"` — NOT FOUND (bot-verification challenge page returned; marker only appears on actual user-not-found page after JS render)

**Verdict:** REVISE — Reddit returns a bot-wall challenge page (`"Please wait for verification"`) for automated httpx requests from non-residential IPs. The planned text marker is unreachable via httpx without a residential proxy or Reddit API credentials. The `claim_value` `"Sorry, nobody on Reddit"` also won't appear in the challenge body, so the engine awards confidence points for all Reddit lookups regardless of account existence — systematic false positive risk.

**Action taken:** `modules/sherlock_wrapper.py` Reddit `negative_markers` updated to `[]` with inline comment documenting bot-wall behavior. Thordata proxy (Phase 16 D-01) may surface real page content in production; retesting recommended after proxy deployment.

---

## Platform 3: X / Twitter

**URL tested:** `https://x.com/nx_fp_check_zzz_999`
**Planned negative markers:** `["this account doesn't exist"]`

**Observed:**
- HTTP Status: `200`
- Body length: `~263KB` (full React SPA bundle)
- Body excerpt (first 200 chars): `'<!DOCTYPE html><html dir="ltr" lang="en"><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" /><link rel="preconnect" ...'`
- Final URL: `https://x.com/nx_fp_check_zzz_999` (no redirect)
- Searched in body: `"doesn't exist"`, `"this account"`, `"doesnt exist"`, `"doesn&#x27;t exist"` — ALL absent from SSR HTML

**Marker check:**
- `"this account doesn't exist"` — NOT FOUND in SSR HTML (React client-side render only)

**Verdict:** REVISE — X/Twitter serves a pure client-side React SPA. The text `"This account doesn't exist"` is injected by the React component tree after JS execution, which `httpx` does not perform. The SSR HTML is structurally identical for existing and nonexistent accounts. No text marker is detectable in the raw HTTP response body.

**Action taken:** `modules/sherlock_wrapper.py` X/Twitter `negative_markers` updated to `[]` with inline comment documenting the SPA limitation.

---

## Platform 4: LinkedIn

**URL tested:** `https://www.linkedin.com/in/nx_fp_check_zzz_999`
**Planned negative markers:** `["page not found", "this page doesn't exist"]`

**Observed:**
- HTTP Status: `999` (LinkedIn proprietary login-wall status code)
- Body (first 200 chars): `'<html><head>\n<script type="text/javascript">\nwindow.onload = function() {\n  // Parse the tracking code from cookies...\n  var trk = "bf";\n  var trkInfo = "bf";...'`
- Final URL: `https://www.linkedin.com/in/nx_fp_check_zzz_999` (no redirect despite JS redirect in body)
- Body is a JavaScript redirect to LinkedIn login page

**Marker check:**
- `"page not found"` — NOT FOUND (login-wall JS page, not a 404)
- `"this page doesn't exist"` — NOT FOUND (same reason)

**Verdict:** REVISE — LinkedIn returns HTTP 999 (proprietary code for "login required") for all unauthenticated requests, regardless of whether the profile exists. Negative markers are unreachable from an unauthenticated httpx client. The `claim_value` `"Page not found"` also won't appear in the login-wall body, so the engine awards confidence points for all LinkedIn lookups — systematic false positive risk.

**Action taken:** `modules/sherlock_wrapper.py` LinkedIn `negative_markers` updated to `[]` with inline comment documenting HTTP 999 login-wall behavior. Authenticated session or residential proxy required for reliable LinkedIn checking.

---

## Platform 5: Instagram

**URL tested:** `https://www.instagram.com/nx_fp_check_zzz_999/`
**Planned negative markers:** `["sorry, this page isn't available", "page not found"]`

**Observed:**
- HTTP Status: `200`
- Body length: `~805KB` (full React SPA including CSS-in-JS variables)
- Body excerpt (first 200 chars): `'<!DOCTYPE html><html class="_9dls _ar44" lang="en" dir="ltr"><head><link data-default-icon="https://static.cdninstagram.com/rsrc.php/yr/r/rzWiSjZRxk5.webp" rel="icon" sizes="192x192"...'`
- Final URL: `https://www.instagram.com/nx_fp_check_zzz_999/` (no redirect)
- Title: `"Instagram"` (identical for all pages — no 404 title differentiation)
- Searched in body: `"sorry, this page"`, `"page not found"`, `"isn't available"` — ALL absent

**Marker check:**
- `"sorry, this page isn't available"` — NOT FOUND in SSR HTML
- `"page not found"` — NOT FOUND in SSR HTML

**Verdict:** REVISE — Instagram serves an ~800KB React SPA for all requests. Account-existence information is loaded asynchronously after page mount. The SSR HTML is structurally identical for existing and nonexistent accounts. No text marker is detectable in the raw HTTP response without browser JS execution.

**Action taken:** `modules/sherlock_wrapper.py` Instagram `negative_markers` updated to `[]` with inline comment documenting the SPA/login-wall behavior.

---

## Summary

| Platform   | HTTP Status | Planned Marker Present in SSR? | Verdict | Action |
|------------|-------------|-------------------------------|---------|--------|
| GitHub     | 404         | YES (`"Not Found"`)           | PASS    | None   |
| Reddit     | 200         | NO (bot-wall challenge page)  | REVISE  | `negative_markers = []` |
| X/Twitter  | 200         | NO (React SPA, client-side)   | REVISE  | `negative_markers = []` |
| LinkedIn   | 999         | NO (login-wall JS redirect)   | REVISE  | `negative_markers = []` |
| Instagram  | 200         | NO (React SPA, 805KB bundle)  | REVISE  | `negative_markers = []` |

**PASS count:** 1  
**REVISE count:** 4

### PLATFORMS dict patches applied to `modules/sherlock_wrapper.py`

1. `Twitter / X` — `negative_markers` set to `[]`, inline comment added explaining SPA rendering limitation
2. `Instagram` — `negative_markers` set to `[]`, inline comment added explaining SPA/login-wall behavior
3. `Reddit` — `negative_markers` set to `[]`, inline comment added explaining bot-wall challenge page
4. `LinkedIn` — `negative_markers` set to `[]`, inline comment added explaining HTTP 999 login-wall

### Note on remaining 20 platforms

The remaining 20 platforms (GitLab, TikTok, Pinterest, YouTube, Twitch, Steam, Keybase, HackerNews, Dev.to, Medium, Mastodon, Flickr, Vimeo, SoundCloud, Spotify, DockerHub, NPM, PyPI, Telegram, Snapchat) were not spot-checked in this audit. Their negative markers were derived from research in `16-RESEARCH.md` and are expected to be accurate for server-rendered pages that include 404 content in the initial SSR HTML. Priority platforms for future re-validation: Telegram and Snapchat (both have SPA characteristics similar to X/Twitter).

### Systemic finding

The 4 REVISE verdicts reveal a systemic limitation: major social platforms (X/Twitter, Instagram, Reddit with bot protection, LinkedIn) serve JavaScript SPAs where account-existence signals are injected client-side. `httpx`-based text-marker detection is fundamentally incompatible with these platforms from a non-residential IP. The Thordata residential proxy integration (Phase 16 D-01..D-07) mitigates IP blocking but does NOT solve the client-side rendering problem. For these 4 platforms, the confidence scoring will tend to produce false positives. Tracked for v4.2 improvement (possible options: JSON API endpoints, authenticated session, or browser automation for spot-checks).
