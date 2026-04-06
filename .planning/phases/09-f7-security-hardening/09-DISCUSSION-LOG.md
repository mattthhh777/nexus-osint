# Phase 09: F7 — Security Hardening - Discussion Log

**Date:** 2026-04-06
**Mode:** Standard discuss-phase (interactive, recommended-default selections)
**Audience:** Human reference / audit trail. Not consumed by downstream agents.

---

## Pre-discussion Scout

- **73 inline `onclick=`** across 7 files (vs 11+ stated in ROADMAP):
  - `index.html` 39, `admin.html` 17, `render.js` 10, `cases.js` 2, `export.js` 2, `search.js` 2, `history.js` 1
- **localStorage usage:** `nx_cases`, `nx_history` (non-sensitive). No `nx_token` → JWT httpOnly already done in Phase 11 (per PROJECT.md).

## Carrying Forward (locked from prior phases)

- JWT httpOnly migration — done in Phase 11
- Backend-only authorization — CLAUDE.md §3, non-negotiable
- Concurrency Semaphore(5) ceiling — CLAUDE.md, non-negotiable
- Pydantic v2 input validation — already mandated

---

## Gray Area Selection (multi-select)

**Q:** Which gray areas to lock down before planning?

**Options presented:**
1. Inline handler purge + CSP — 73 onclick sites, replacement pattern, CSP strictness, location
2. Rate limiting design — slowapi storage, ceilings, key, nginx interaction
3. Fail-hard + fail-closed semantics — JWT_SECRET, blacklist, SpiderFoot validator
4. Operational caps + headers — user cap, security headers, HSTS

**User selected:** ALL FOUR.

---

## Area 1: Inline Handler Purge + CSP

### Q1.1 — Replacement pattern for 73 onclick sites
- (R) Event delegation w/ `data-action` attributes → **selected**
- Per-element addEventListener
- Hybrid: delegation for lists, direct for static buttons

### Q1.2 — CSP strictness
- (R) Strict: drop unsafe-inline for both script + style → **selected**
- Script-only strict (allow inline styles)
- Report-only first, enforce next phase

### Q1.3 — CSP header location
- (R) `nginx.conf` → **selected**
- FastAPI Starlette middleware
- Both (defense-in-depth)

### Q1.4 — Scope split for the 73 handlers
- (R) One sweep, single phase → **selected**
- Split by file priority (2 waves)
- Split by surface (user-facing → admin)

**Move on:** Next area (Rate limiting)

---

## Area 2: Rate Limiting Design

### Q2.1 — slowapi storage backend
- (R) In-memory → **selected**
- SQLite-backed
- Memory + SQLite hybrid

### Q2.2 — Per-user vs per-IP key
- (R) Per-authenticated-user, fallback to IP → **selected**
- Per-IP only
- Per-IP + per-user (compound)

### Q2.3 — Endpoint ceiling posture
- (R) Conservative defaults → **selected**
- Aggressive defaults
- Liberal defaults, tighten later

### Q2.4 — Interaction with nginx limits
- (R) Keep nginx as outer DDoS shield, slowapi as app-aware inner → **selected**
- Replace nginx limits with slowapi
- Tighten nginx, skip slowapi

**Move on:** Next area (Fail-hard/closed)

---

## Area 3: Fail-hard + Fail-closed Semantics

### Q3.1 — JWT_SECRET missing/default at startup
- (R) Refuse to start, log fatal, exit 1 → **selected**
- Warn loudly + generate ephemeral key
- Refuse start AND require min entropy 32+ bytes

### Q3.2 — Blacklist read error semantics
- (R) Deny all checks, log warning, return 503 → **selected**
- Log warning, allow request through (fail-open)
- Cache last good list, deny only if cache also missing

### Q3.3 — SpiderFoot target validator scope
- (R) Domain (FQDN) + IPv4 only → **selected**
- + IPv6 + CIDR ranges
- + URLs (extract host)

**Move on:** Next area (Operational caps + headers)

---

## Area 4: Operational Caps + Headers

### Q4.1 — User cap of 50 enforcement
- (R) Hard reject on signup, env-configurable → **selected**
- Hard 50 hardcoded
- Waitlist (allow registration, mark inactive)

### Q4.2 — Security headers location
- (R) `nginx.conf` alongside CSP → **selected**
- Starlette middleware (api/main.py)
- Both (defense-in-depth)

### Q4.3 — HSTS posture
- (R) `max-age=31536000; includeSubDomains` → **selected**
- + preload directive
- max-age=300 ramp-up

---

## Wrap-up

**Q:** Ready to write CONTEXT.md or explore more gray areas?
- (R) Write CONTEXT.md → **selected**

**Total decisions captured:** 13 across 4 areas (D-01 through D-13)
**All recommended defaults selected** — Math accepted Claude's analyzed recommendations without override.

---

*Discussion completed: 2026-04-06*
