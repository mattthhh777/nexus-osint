# NexusOSINT

## What This Is

A premium OSINT (Open Source Intelligence) SaaS platform for security professionals, investigators, and intelligence analysts. Aggregates breach data, stealer logs, social media profiles, and infrastructure intel through a unified search interface with SSE streaming results. Production at nexusosint.uk v4.0.0. Engineered for maximum capability on minimal hardware (1GB RAM VPS).

## Core Value

A single search query returns comprehensive intelligence from 13+ OSINT modules with professional-grade data presentation — density without chaos. From the same scan, show 2× more data without additional backend cost by rendering what already arrives.

## Current Milestone: v4.2 Database Migration — SQLite → PostgreSQL

**Goal:** Replace SQLite with PostgreSQL to remove single-writer bottleneck, unlock concurrent agent writes, leverage native JSONB for `extra_fields`, and prepare for full-text search on breach data. Hardware constraint that originally locked SQLite (1GB RAM DigitalOcean) no longer applies — Hetzner VPS provides 4GB RAM headroom. Migration is data-preserving with rollback playbook.

**Target features:**

- PostgreSQL setup — docker-compose service + tuning for 4GB host (shared_buffers, work_mem, max_connections)
- asyncpg driver — async connection pool with bounded size, replace `aiosqlite.Connection` + write Queue
- Alembic migrations — schema versioning, port current SQLite schema to Postgres-native types (JSONB for `extra_fields`)
- Data migration tool — dump SQLite → load Postgres with row-count + checksum validation
- Connection layer refactor — repository layer swaps engine without route-level changes
- Backup automation — pg_dump cron + retention policy + restore drill
- Rollback playbook — keep SQLite snapshot during cutover window, documented revert path
- Maintenance window cutover — single planned downtime, dual-write not in scope

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep vanilla JS/CSS stack | Production working, rewrite risk too high | ✅ Good |
| Meridian design system | Consistent visual language, single source of truth | ✅ Good |
| SQLite with WAL, not PostgreSQL | 1GB RAM constraint at DigitalOcean; WAL + asyncio.Queue single-writer | ⚠️ Superseded by v4.2 — VPS migrated to Hetzner 4GB; Postgres now justified |
| TaskGroup + Semaphore, not heavy processes | OOM prevention on 1GB VPS; dual semaphore (Global=5, OathNet=3) | ✅ Validated Phase 05 |
| httpx as sole HTTP client | Remove requests + aiohttp — 15MB container reduction | ✅ Validated Phase 11 |
| TTLCache for API responses | maxsize=200, ttl=300s — preserves OathNet 100/day quota | ✅ Validated Phase 11 |
| tracemalloc in production | ~3-5% CPU overhead acceptable on 1vCPU for diagnostics | ✅ Validated Phase 06 |
| Breach serialize cap at 200 | SSE needs complete JSON; cursor pagination for rest | ✅ Validated Phase 06 |
| Docker image target 306MB accepted | 250MB hard constraint not met with python:3.12-slim + deps; F5 Docker Optimization is venue for reduction | ✅ User-accepted Phase 07 |
| v4.1 D-01: extra_fields instrumentation (A+C) | Admin endpoint discovers real keys empirically; frontend uses explicit whitelist — avoids internal API fields polluting UI | ✅ Approved 2026-04-15 |
| v4.1 D-02: Breach cards before social cards (14→15) | Breach has richer data already in pipeline; higher ROI first | ✅ Approved 2026-04-15 |
| v4.1 D-03: Admin panel out of v4.1 scope | Low ROI vs complexity; reserved for v4.2 | ✅ Approved 2026-04-15 |
| v4.1 D-04: Toggle slider Tier 2.4 dropped | Low ROI, not requested by user research | ✅ Approved 2026-04-15 |
| v4.1 D-05: SVG brand icons via Lucide + Simple Icons | ~50 icons +~40KB — lazy-load via sprite; no emoji icons per CLAUDE.md | ✅ Approved 2026-04-15 |
| v4.1 D-06: Social profile data ceiling accepted | Sherlock returns only 4 fields; full parity with references requires custom scrapers (v5.0+ scope, ~$400/mo APIs); 50% visual impact at 10% cost | ✅ Approved 2026-04-15 |
| v4.1 D-07: CLAUDE.md compliance absorbed into each phase DoD | Touch targets, aria-labels, cursor — applied per-component, not a separate phase | ✅ Approved 2026-04-15 |
| v4.1 D-08: css.zip + js.zip deleted | Emergency backups from VPS permission incident — no longer needed | ✅ Approved 2026-04-15 |
| v4.1 CSP fix: form-ancestors → frame-ancestors in /js/ block | Typo introduced Phase 09-04; X-Frame-Options DENY still present but CSP frame-ancestors was non-functional | ✅ Fixed pre-gate commit 2026-04-15 |

## Requirements

### Validated (v4.0 complete)

- ✓ JWT authentication with multi-user support and admin roles — v3.0.0
- ✓ SSE streaming search across 13+ OSINT modules in parallel — v3.0.0
- ✓ Breach data display with severity badges, password masking, pagination — v3.0.0
- ✓ Stealer log browsing with file tree and file viewer — v3.0.0
- ✓ Rich cards for Discord, Steam, Xbox, Roblox, GHunt, Minecraft, IP Info — v3.0.0
- ✓ Sherlock social media scanning (25 platforms) — v3.0.0
- ✓ Cases system with notes (localStorage) — v3.0.0
- ✓ Search history (localStorage) — v3.0.0
- ✓ Export to JSON, CSV, TXT, PDF — v3.0.0
- ✓ Admin panel with audit logs, user management, quota monitoring — v3.0.0
- ✓ Rate limiting (Nginx + SQLite-backed in-process) — v3.0.0
- ✓ Docker deployment with Nginx reverse proxy, SSL, Cloudflare — v3.0.0
- ✓ Frontend modularized into 9 CSS + 9 JS files — v3.0.0 Phase 1
- ✓ Meridian CSS design system tokens (16/16 requirements complete) — v3.0.0 Phase 1
- ✓ XSS sanitization: sanitizeImageUrl, esc(), escAttr() on all API data — v3.0.0 Phase 2
- ✓ Security bugs fixed: admin_stats context manager, rate limit fail-closed — v3.0.0
- ✓ Codebase audit (F1) — 17 findings, all addressed. Phase 03
- ✓ SQLite WAL + asyncio.Queue single-writer serialization (F2) — Phase 04
- ✓ Async TaskOrchestrator (F3) — TaskGroup + dual semaphore (Global=5, OathNet=3) — Phase 05
- ✓ Memory discipline <200MB resting (F4) — generators, fetch caps, tracemalloc — Phase 06
- ✓ Docker multi-stage build (F5) — OOM limits, health check, memory reservations — Phase 05/07
- ✓ Python 3.12 migration (F6) — 27/27 tests green, tenacity removed — Phase 07
- ✓ CSP headers + JWT httpOnly + slowapi rate limiting (F7) — Phase 09
- ✓ Health watchdog + graceful degradation /health endpoint (F8) — Phase 10
- ✓ Mobile responsive layout — breakpoints 640px/768px — Phase 12 (pre-gate)

### Active (v4.1 in progress)

- [ ] Breach data extra fields instrumentation — Phase 13
- [ ] Breach cards: 2-col card per entry with extra_fields — Phase 14
- [ ] Social profile cards: SVG brand icons, platform-branded — Phase 15
- [ ] Inline panel filters (>10 results) — Phase 16
- [ ] Results summary hero (4 stat cards) — Phase 17
- [ ] Per-field copy + raw JSON expand modal — Phase 18
- [ ] Micro-polish: press-feedback, sf-dot mobile, placeholder rotativo — Phase 19

### Out of Scope

- Next.js / React / Vue migration — vanilla stack is production, rewrite risk too high
- Redis — Postgres LISTEN/NOTIFY + in-memory caches sufficient at current scale (revisit if pubsub needs grow)
- New OSINT data sources beyond OathNet API — focus is presentation, not data expansion
- Mobile app — web-first
- CI/CD pipeline — deploy via scp, not blocking current work
- Tailwind CSS / Shadcn/ui — using custom Meridian design system
- Horizontal scaling / multi-VPS — design for it but deploy on single VPS
- Admin panel redesign — v4.2
- Custom scrapers (TikTok, Strava, full social enrichment) — v5.0, ~$400/mo APIs
- Dark mode toggle — permanent single-theme Amber/Noir
- i18n — Portuguese only for now
- PWA/offline — out of scope

## Context

**Production environment:**
- Hetzner VPS: 3 vCPU / 4GB RAM / 80GB SSD (IP 87.99.153.11, Ubuntu)
- Domain nexusosint.uk via Cloudflare
- SSL via Let's Encrypt (certbot container)
- Docker Compose: app (FastAPI/Uvicorn) + Nginx + Certbot + (v4.2) Postgres
- OathNet API: Starter plan, 100 lookups/day (main operational constraint)
- Deploy via scp (no CI/CD)

**Hardware constraints (current — Hetzner):**
- RAM target: <500MB app resting; <2000MB alert; >85% (~3400MB) critical → pause new agents
- Postgres budget (v4.2): ~300MB shared_buffers + work_mem; total system resting <1.2GB
- Swap: 1GB recommended safety net
- Concurrency ceiling: asyncio.Semaphore(10) — Postgres connection pool max 8 (leave headroom)
- Docker image target: <250MB app image (Postgres image separate)

**Design system:** Meridian — "Night command station" aesthetic. Noir/amber palette.
Density without chaos. Max border-radius 6px (except pills).

**Completed milestones:**
- v3.0.0: Monolith split (4384→361 lines), Meridian CSS tokens (9 files), XSS sanitization, backend security fixes. 16/16 requirements complete, 9 plans executed.
- v4.0.0: Low-resource agent architecture + hardening. 10 phases, 22 plans completed.

## Constraints

- **Stack lock**: FastAPI + vanilla HTML/CSS/JS + Docker — no framework changes (DB layer evolving in v4.2: SQLite → PostgreSQL)
- **Hardware**: 3 vCPU / 4GB RAM / 80GB SSD (Hetzner) — every architectural decision must respect this
- **Memory ceiling**: <500MB app resting + ~300MB Postgres; Semaphore(10) for concurrent tasks; pool max 8
- **Amber/noir identity**: Color palette is brand identity — never change
- **File protection**: Do NOT modify docker-compose.yml, nginx.conf, Dockerfile, entrypoint.sh, admin.html, modules/*.py without explicit approval (nginx.conf pre-gate exception was for CSP fix)
- **Known traps**: Never use passlib, su-exec, `from __future__ import annotations`, `user: "1000:1000"` in compose, `internal: true` on Docker network
- **Frontend scope**: v4.1 changes are frontend-only except Phase 13 (1 admin endpoint)
- **DoD transversal (Phases 14-19)**:
  - Zero emoji as functional icons — SVG only
  - Touch targets ≥44×44px on mobile
  - `aria-label` on all icon-only buttons
  - `cursor: pointer` on all custom clickable elements
  - Tested at viewport 375px without horizontal scroll
  - Respects `prefers-reduced-motion`
  - Zero regression on securityheaders.com score (A)

## Known Risks (v4.1)

| Risk | Mitigation |
|------|------------|
| `extra_fields` may be empty in real queries | Phase 13 resolves empirically before Phase 14 |
| +40KB SVGs on already dense page | Lazy-load via `<use href>` sprite, not inline |
| Inline filters may lag with many results | Debounce 150ms + virtualize if >100 items |
| 2-col breach cards break at <360px | Fallback to 1-col below narrow breakpoint |

## Backend Architecture Reference (for v4.1 frontend work)

### BreachRecord fields (modules/oathnet_client.py:36-48)

| Field | Type | Notes |
|-------|------|-------|
| dbname, email, username, password | str | Base fields |
| ip, domain, date, country | str | Context fields |
| discord_id, phone | str | Alias-resolved in parser |
| data_types | list[str] | Breach category tags |
| extra_fields | dict | All non-KNOWN_FIELDS from OathNet API |

**Serializer** (`api/main.py:757-761`): sends all 10 typed fields + `extra` key.  
**Frontend gap**: `render.js:_renderBreachPage` currently reads only 8 fields; ignores `discord_id` and entire `extra` dict.

### StealerRecord fields (modules/oathnet_client.py:53-62)

| Field | Type |
|-------|------|
| url, username, password | str |
| domain, email | list[str] |
| log_id, pwned_at | str |

**Serializer gap**: `log` and `email` list not serialized — low priority fix.

### Social profile (sherlock_wrapper.py)

Sherlock returns only 4 fields per platform: `platform`, `url`, `icon`, `category`.  
No enriched data (bio, creation date, followers, verified status) without custom scrapers.  
This ceiling is accepted (D-06). Cards will show what's available elegantly.

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-06 — v4.2 milestone kickoff (SQLite → PostgreSQL migration)*

## 2026-05-19 — R0/R1 decisions baked

- G1 = hash-only + TTL 7d for `search_events.payload`.
- G2 = defer Gravatar enrichment; skip R1-10.
- G3 = require at least two independent connectors for `overall_status='found'`.
- G4 = reuse Thordata under the existing 1GB/day quota.

Execution branch series:

- R0: `v4.1/r0-contract-shim` -> 7 tasks -> contract shim, no engine change.
- R1: `v4.1/r1-safe-mvp` -> 11 tasks, with R1-10 skipped -> safe MVP with `/api/v2/search`.

See `.planning/R0_R1_REVISION.md`, `.planning/CODEX_HANDOFF.md`, and `docs/CONNECTORS.md`.
