# NexusOSINT

## What This Is

A premium OSINT (Open Source Intelligence) SaaS platform for security professionals, investigators, and intelligence analysts. Aggregates breach data, stealer logs, social media profiles, and infrastructure intel through a unified search interface with SSE streaming results. Production at nexusosint.uk v3.0.0.

## Core Value

A single search query returns comprehensive intelligence from 13+ OSINT modules with professional-grade data presentation — density without chaos.

## Requirements

### Validated

- ✓ JWT authentication with multi-user support and admin roles — existing
- ✓ SSE streaming search across 13+ OSINT modules in parallel — existing
- ✓ Breach data display with severity badges, password masking, pagination — existing
- ✓ Stealer log browsing with file tree and file viewer — existing
- ✓ Rich cards for Discord, Steam, Xbox, Roblox, GHunt, Minecraft, IP Info — existing
- ✓ Sherlock social media scanning (25 platforms) — existing
- ✓ Cases system with notes (localStorage) — existing
- ✓ Search history (localStorage) — existing
- ✓ Export to JSON, CSV, TXT, PDF — existing
- ✓ Admin panel with audit logs, user management, quota monitoring — existing
- ✓ Rate limiting (Nginx + SQLite-backed in-process) — existing
- ✓ Docker deployment with Nginx reverse proxy, SSL, Cloudflare — existing
- ✓ Frontend modularized into 9 CSS + 9 JS files (Phase 1 complete) — existing
- ✓ Security bugs fixed: admin_stats context manager, rate limit fail-closed, imports organized — existing

### Active

- [ ] Migrate all CSS from legacy tokens to Meridian design system (Phase 2)
- [ ] Sanitize all XSS vectors in frontend template literals (Phase 4)

### Out of Scope

- Next.js / React / Vue migration — current vanilla stack is in production, not rewriting now
- n8n integration — never existed, not needed for current milestone
- PostgreSQL / Redis migration — SQLite sufficient for current scale
- Tailwind CSS / Shadcn/ui — using custom CSS with Meridian design system
- New features (report integration, server-side cases, credit system) — separate milestone
- Test suite creation — important but separate initiative
- OathNet client async migration (requests → httpx) — works fine via asyncio.to_thread
- JWT httpOnly cookie migration — requires backend+frontend coordination, planned separately

## Context

**Production environment:**
- DigitalOcean VPS (SFO3, Ubuntu 24.04), domain nexusosint.uk via Cloudflare
- SSL via Let's Encrypt (certbot container), expires 2026-06-21
- Docker Compose: app (FastAPI/Uvicorn) + Nginx + Certbot
- OathNet API: Starter plan, 100 lookups/day (main operational constraint)
- Deploy via scp (no CI/CD, no git-based deploy)

**Completed refactoring (do not redo):**
- Phase 1: Monolith index.html (4384 lines) split into 361-line HTML + 9 CSS files + 9 JS files
- Phase 3: Backend security bugs fixed (admin_stats db context, rate limit fail-closed, import cleanup, duplicate password check removed)

**Remaining refactoring:**
- Phase 2: 9 CSS files still use legacy tokens (--bg, --text, --amber, rgba hardcoded). Must migrate to Meridian design system tokens (--color-bg-base, --color-text-primary, --color-accent, etc.)
- Phase 4: XSS sanitization — esc() not applied consistently in render.js template literals, Discord avatar/banner URLs not validated

**Design system:** Meridian — "Night command station" aesthetic. Noir/amber palette. Density without chaos. Max border-radius 6px (except pills). Full token spec in BRIEFING_IMPLEMENTACAO.md §3.2.

## Constraints

- **Stack lock**: FastAPI + vanilla HTML/CSS/JS + SQLite + Docker — no framework changes this milestone
- **Zero visual regression**: Phase 2 token migration must produce identical visual output
- **Amber/noir identity**: Color palette is brand identity — never change accent to green/blue/other
- **File protection**: Do NOT modify docker-compose.yml, nginx.conf, Dockerfile, entrypoint.sh, admin.html, modules/*.py
- **Known traps**: Never use passlib, slowapi, su-exec, `from __future__ import annotations`, `user: "1000:1000"` in compose, `internal: true` on Docker network
- **Sync risk**: Local files may differ from VPS — verify before deploying

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep vanilla JS/CSS stack | Production working, rewrite risk too high for current goals | ✓ Good |
| Meridian design system over ad-hoc tokens | Consistent visual language, single source of truth for all CSS | — Pending |
| Phase 1 before Phase 2 | Must separate files before migrating tokens (can't refactor monolith) | ✓ Good |
| Phase 3 before Phase 4 | Backend security more critical than frontend XSS | ✓ Good |
| Skip research for this milestone | Domain well-understood, work is CSS migration + XSS fixes, not new features | — Pending |

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
*Last updated: 2026-03-25 after initialization (brownfield)*
