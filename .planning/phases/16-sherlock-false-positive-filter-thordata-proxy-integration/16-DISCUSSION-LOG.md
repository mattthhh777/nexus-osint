# Phase 16: Sherlock False-Positive Filter + Thordata Proxy Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-29
**Phase:** 16-sherlock-false-positive-filter-thordata-proxy-integration
**Areas discussed:** Proxy session strategy, Proxy fallback, FP filter strategy, Result confidence display, Cost / budget controls
**Mode:** caveman-full + "faça o melhor" → Claude locked recommended defaults across Areas 2-6

---

## Area 1 — Proxy Scope (auto-locked, NOT discussed by user)

| Option | Description | Selected |
|--------|-------------|----------|
| Sherlock only | Proxy only `modules/sherlock_wrapper.py`. OathNet = paid API; SpiderFoot = internal container. | ✓ |
| Sherlock + Holehe + outbound scrapers | Wider scope. | |
| All outbound | Includes paid APIs + internal services. | |

**User's choice:** N/A — locked by Claude (recommended). User did not select Area 1 from gray-area menu.
**Notes:** OathNet is paid HTTP API (no IP block issue). SpiderFoot runs as internal Docker container (no outbound from app perspective). Only Sherlock issues direct scraping requests to public social platforms.

---

## Area 2 — Proxy Session Strategy

### Q1: Default rotation mode per search

| Option | Description | Selected |
|--------|-------------|----------|
| A — Sticky per search_id | One residential IP for all 25 platforms in one search. Reduces TLS handshakes. Risk: IP burn loses entire search. | |
| B — Rotate per request | Each platform gets different IP. Max bypass; ~25× TLS handshakes; +latency. | |
| C — Hybrid | Sticky per search; rotate only on retry after 4xx/429. | ✓ |

**User's choice:** C (locked by Claude after "faça o melhor").
**Notes:** Best of both — keepalive reuse for happy path; IP rotation when burned.

### Q2: Sticky session TTL

| Option | Description | Selected |
|--------|-------------|----------|
| 30s | Tight; risks expiry mid-search. | |
| 60s | Covers full Sherlock search (~10-30s) + retry margin. | ✓ |
| 5min | Excessive; wastes Thordata sticky pool. | |
| Thordata default (10min) | Wasteful. | |

**User's choice:** 60s (locked by Claude).

### Q3: Per-domain outbound rate limit

| Option | Description | Selected |
|--------|-------------|----------|
| 0.5 req/s | Conservative scraper-friendly. | |
| 1 req/s | Sufficient — Sherlock hits each domain only once per search. | ✓ |
| 2 req/s | Implicit current. | |

**User's choice:** 1 req/s (locked by Claude). CLAUDE.md outbound rate limiter mandate.

### Q4: httpx max_connections with proxy active

| Option | Description | Selected |
|--------|-------------|----------|
| 15 | Current value; idle slots when proxy active. | |
| 8 | Proxy adds latency; 8 = 25 platforms / ~3 waves. Reduces Thordata bandwidth. | ✓ |
| 5 | Aligns with global Semaphore but throttles waves. | |

**User's choice:** 8 (locked by Claude).

---

## Area 3 — Proxy Fallback

### Q1: Behavior when proxy fails (timeout / 502 / auth / ProxyError)

| Option | Description | Selected |
|--------|-------------|----------|
| Hard fail | Mark platform error immediately, no retry. | |
| Direct fallback | Bypass proxy on failure — but DO IP re-triggers blocks → false `not_found`. | |
| Retry 1× via proxy (rotate), then mark error | Forces IP rotation; honest error if still failing. No silent bypass. | ✓ |

**User's choice:** Retry 1× via proxy → mark `error: proxy_unavailable` (locked by Claude).
**Notes:** Direct fallback explicitly rejected — would defeat phase purpose by producing false negatives.

### Q2: Startup health check

| Option | Description | Selected |
|--------|-------------|----------|
| None | No early signal of misconfiguration. | |
| Blocking check | App refuses to start if proxy down. | |
| Non-blocking via api.ipify.org | Logs IP; on failure degrades to no-proxy + WARNING. | ✓ |

**User's choice:** Non-blocking ipify check (locked by Claude).

---

## Area 4 — FP Filter Strategy

### Q1: How to reduce false-positives

| Option | Description | Selected |
|--------|-------------|----------|
| A — Multi-signal | status + text + size sanity. | |
| B — Sherlock upstream data.json | 300+ platforms, regex-rich. Inflates UI + bandwidth, regresses D-06. | |
| C — Confidence score 0-100 | Numeric output, threshold-based display. | |
| D — Combo A+C | Multi-signal feeds confidence score. | ✓ |
| Per-platform negative_markers | Reject match even if positive claim hits (custom 404 fix). | ✓ (added) |

**User's choice:** D + negative_markers (locked by Claude).
**Score formula chosen:**
- status_code match → +40
- text marker match → +40
- size sanity (>3KB) → +20
- cap 100

---

## Area 5 — Result Confidence Display

### Q1: Result format

| Option | Description | Selected |
|--------|-------------|----------|
| Binary found/not-found | Current. Lies when FP exists. | |
| Score numeric only | Confuses operator on threshold. | |
| 3-state confirmed/likely/not_found | Honest + actionable. | ✓ |

**User's choice:** 3-state (locked by Claude).
**Backend → frontend contract:** state pre-classified backend; frontend never recomputes.

---

## Area 6 — Cost / Budget Controls

### Q1: Body cap for Sherlock-specific requests

| Option | Description | Selected |
|--------|-------------|----------|
| Keep 512KB only | F4 global cap, no Sherlock-specific tightening. | |
| Sherlock-specific 256KB | Profile pages well under; cuts spam landing pages. | ✓ |

### Q2: Daily budget

| Option | Description | Selected |
|--------|-------------|----------|
| None | Bill surprise risk. | |
| Soft-only WARNING | No hard ceiling. | |
| Soft 500MB + hard 1GB circuit breaker | WARNING then 503 + Retry-After. | ✓ |

### Q3: Per-search cap

| Option | Description | Selected |
|--------|-------------|----------|
| None | Unbounded. | |
| 1MB | 25 platforms × ~40KB avg. Returns partial + log INFO when hit. | ✓ |

### Q4: Health metrics

| Option | Description | Selected |
|--------|-------------|----------|
| Public | Leaks bandwidth patterns. | |
| Admin-gated | Same gate as `/health/memory`. | ✓ |

**User's choice:** Sherlock-256KB + soft-500MB/hard-1GB + per-search-1MB + admin-gated metrics (all locked by Claude).

---

## Security Hardening — User-Triggered Addendum

User explicitly invoked CLAUDE.md "Não Confie no Frontend" mandate ("não esqueça de deixar seguro e não confiar no front end"). 15 hardening decisions (D-H1..D-H15) recorded in CONTEXT.md `<decisions>` section. Topics covered:
- Threshold + score classification backend-only
- Raw signal scores not exposed to frontend
- `negative_markers` never serialized
- Budget enforcement backend-only
- Proxy URL never logged or surfaced to client
- `.env.example` placeholder for credential-leak-free deploy docs
- Pydantic regex username validator + reject-list
- Per-search loguru audit log with SHA256-truncated username hash
- Admin-gated `/health` Thordata metrics
- Per-layer exception handling (no bare `except Exception`)

---

## Claude's Discretion

- Internal helper function naming inside `sherlock_wrapper.py`.
- Whether budget tracker lives in `sherlock_wrapper.py` or `api/budget.py`.
- `/health` Thordata payload shape (nested vs flat).
- Specific `negative_markers` strings — researcher to derive from real-world 404 page samples.
- Thordata sticky session syntax — researcher to confirm via Thordata docs (Context7 / web fetch).

## Deferred Ideas

- Upstream Sherlock data.json migration (v4.2+).
- Persistent Thordata budget across restarts.
- Per-platform proxy bypass list.
- CLI fallback through proxy.
- WebSocket/SSE live progress.
- ML-trained confidence model.
