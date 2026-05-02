---
phase: 16-sherlock-false-positive-filter-thordata-proxy-integration
plan: 04
status: COMPLETE
completed: "2026-05-01"
commits:
  - e3a0304  # renderSocial state-branched + Unverified badge + module_error UX + CSS
  - aba6b64  # negative markers audit + PLATFORMS patch for 4 SPA platforms
  - 53174a0  # E2E tests + ssl.SSLError fix in _thordata_startup_check
---

# 16-04 SUMMARY — Frontend, Audit, Tests

## Task 1 — Negative-Markers Manual Validation Audit

Validated 5 representative platforms against real 404 responses. Documented in
`16-NEGATIVE-MARKERS-AUDIT.md`. 4 platforms required PLATFORMS dict patches
(GitHub, Reddit, LinkedIn, Instagram — SPA/login-wall behaviour differs from
research-derived markers). X/Twitter: PASS.

## Task 2 — renderSocial Extension + CSS

**`static/js/render.js`** — `renderSocial(s)` extended:
- Unified `items = [...s.found, ...(s.likely || [])]`; confirmed sorted before likely.
- `state === "likely"` → `.social-card--likely` + `Unverified` badge.
- Top badge stays `s.found_count`; inline `+N unverified` when `s.likely_count > 0`.
- D-H1 enforced: `p.state` consumed directly — zero `p.confidence` comparisons.

**`static/js/search.js`** — `module_error` for `module === "sherlock"`:
- `budget_exceeded` → "Sherlock budget exceeded — try tomorrow" (no raw `retry_after`).
- `invalid_username` → "Invalid username format" (no input echo, D-H9).

**`static/css/cards.css`** — 4 classes appended after existing `.social-card-*` block:
`.social-card--likely`, `.social-card-badge`, `.social-card-badge--unverified`, `.panel-likely-count`.
Zero hardcoded hex — all `var(--color-*)` tokens.

## Task 3 — End-to-End Integration Tests

`tests/integration/test_phase16_e2e.py` — 8 tests:
1. Confirmed-only SSE shape
2. Mixed found + likely (state assertions)
3. `proxy_used=True` reflected
4. Budget exceeded → `module_error`, Sherlock NOT invoked
5. Invalid username → `module_error`, Sherlock NOT invoked
6. D-H2/D-H3 byte-level audit (no internal scoring fields in raw SSE)
7. D-H13 audit log (`username_hash=` present, plaintext absent)
8. Serialization tightness (exactly 6 keys per platform item)

**Phase 16 suite (5 files): 53/53. Project suite: 111/111.**

## Bug Fix — `_thordata_startup_check`

Added `ssl.SSLError` + `OSError` to except clause. These escape httpx when proxy
responds to CONNECT but TLS tunnel fails. Per D-07 all proxy startup failures must
degrade gracefully.

## Audit Results

| Check | Result |
|---|---|
| D-H1: no `p.confidence` comparison in JS | PASS |
| D-H2/D-H3: no internal scoring fields in SSE bytes | PASS |
| Brand: no new hex in CSS | PASS |
| `social-card--likely` + `Unverified` badge in render.js | PASS |
| `budget_exceeded` / `invalid_username` friendly messages | PASS |
| Negative markers: 5 platforms audited | PASS |

## Task 4 — Deploy

VPS deploy pending next session (local smoke deferred — no Thordata credentials in
local dev env). Phase 16 code complete; all tests green.

## Phase 16 Closing

All 4 plans complete:
- 16-01: config + budget tracker
- 16-02: sherlock_wrapper Thordata proxy + confidence scoring
- 16-03: route layer — validator + budget circuit breaker + extended SSE + health/thordata
- 16-04: frontend state rendering + Unverified badge + E2E tests + ssl.SSLError fix
