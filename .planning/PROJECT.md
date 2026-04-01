# NexusOSINT

## What This Is

A premium OSINT (Open Source Intelligence) SaaS platform for security professionals, investigators, and intelligence analysts. Aggregates breach data, stealer logs, social media profiles, and infrastructure intel through a unified search interface with SSE streaming results. Production at nexusosint.uk v3.0.0. Engineered for maximum capability on minimal hardware (1GB RAM VPS).

## Core Value

A single search query returns comprehensive intelligence from 13+ OSINT modules with professional-grade data presentation — density without chaos.

## Current Milestone: v4.0 Low-Resource Agent Architecture & Hardening

**Goal:** Transform NexusOSINT into a modular, agent-orchestrated OSINT platform engineered for 1GB RAM / 1 vCPU — maximum capability from minimum hardware through async micro-tasks, memory discipline, and controlled concurrency.

**Target features:**
- F1: Codebase Audit — detect memory leaks, zombie processes, unsafe patterns, evaluate manual security changes
- F2: SQLite Hardening — WAL mode, write serialization via asyncio.Queue, eliminate "database is locked"
- F3: Async Agent Orchestration Lite — TaskGroup + Semaphore-controlled micro-tasks (credential leak, geo-metadata, social scrapers)
- F4: Memory-Disciplined Architecture — <200MB resting footprint, generators everywhere, no bulk collections
- F5: Docker Optimization — multi-stage build <250MB, swap strategy, OOM-resistant config
- F6: Stack Modernization — Python 3.12+, proxy rotation, OathNet rate optimization
- F7: Security Hardening — CSP headers, JWT httpOnly migration, rate limiting per-endpoint
- F8: Health Monitoring — memory/CPU watchdog, graceful degradation under pressure

## Requirements

### Validated

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

### Active

- [ ] Codebase audit with severity report (F1)
- [ ] SQLite WAL mode + write serialization via asyncio.Queue (F2)
- [x] Async agent orchestration with TaskGroup + Semaphore(5) (F3) — Validated in Phase 05: TaskOrchestrator with dual semaphore (Global=5, OathNet=3), queue bridge, task registry
- [ ] Memory-disciplined architecture <200MB resting (F4)
- [ ] Docker multi-stage build <250MB with OOM protection (F5)
- [ ] Python 3.12+ migration with dependency validation (F6)
- [ ] CSP headers + JWT httpOnly + per-endpoint rate limiting (F7)
- [ ] Health monitoring watchdog with graceful degradation (F8)

### Out of Scope

- Next.js / React / Vue migration — vanilla stack is production, rewrite risk too high
- PostgreSQL / Redis — SQLite sufficient at current scale with WAL
- New OSINT data sources beyond OathNet API — focus is architecture, not data expansion
- Mobile app — web-first
- CI/CD pipeline — deploy via scp, not blocking current work
- Tailwind CSS / Shadcn/ui — using custom Meridian design system
- Horizontal scaling / multi-VPS — design for it but deploy on single VPS

## Context

**Production environment:**
- DigitalOcean VPS: 1 vCPU / 1GB RAM / 25GB SSD (SFO3, Ubuntu 24.04)
- Domain nexusosint.uk via Cloudflare
- SSL via Let's Encrypt (certbot container), expires 2026-06-21
- Docker Compose: app (FastAPI/Uvicorn) + Nginx + Certbot
- OathNet API: Starter plan, 100 lookups/day (main operational constraint)
- Deploy via scp (no CI/CD)

**Hardware constraints (non-negotiable):**
- RAM target: <200MB resting footprint
- Swap: 2GB mandatory
- Concurrency ceiling: asyncio.Semaphore(5) — absolute max simultaneous tasks
- Docker image target: <250MB

**Completed milestones (do not redo):**
- v3.0.0: Monolith split (4384→361 lines), Meridian CSS tokens (9 files), XSS sanitization, backend security fixes. 16/16 requirements complete, 9 plans executed.

**Design system:** Meridian — "Night command station" aesthetic. Noir/amber palette. Density without chaos. Max border-radius 6px (except pills).

## Constraints

- **Stack lock**: FastAPI + vanilla HTML/CSS/JS + SQLite + Docker — no framework changes
- **Hardware**: 1 vCPU / 1GB RAM / 25GB SSD — every architectural decision must respect this
- **Memory ceiling**: <200MB resting, Semaphore(5) for concurrent tasks
- **Amber/noir identity**: Color palette is brand identity — never change
- **File protection**: Do NOT modify docker-compose.yml, nginx.conf, Dockerfile, entrypoint.sh, admin.html, modules/*.py without explicit approval
- **Known traps**: Never use passlib, su-exec, `from __future__ import annotations`, `user: "1000:1000"` in compose, `internal: true` on Docker network
- **Sync risk**: Local files may differ from VPS — verify before deploying
- **Gated execution**: F1 (audit) must complete before any implementation begins

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep vanilla JS/CSS stack | Production working, rewrite risk too high | ✓ Good |
| Meridian design system | Consistent visual language, single source of truth | ✓ Good |
| SQLite with WAL, not PostgreSQL | 1GB RAM constraint; WAL handles concurrent reads; asyncio.Queue serializes writes | -- Pending |
| TaskGroup + Semaphore, not heavy processes | OOM prevention on 1GB VPS; TaskGroup auto-cancels on failure | -- Pending |
| Docker target <250MB not <150MB | Realistic with Python 3.12-slim + dependencies | -- Pending |
| F1 audit gates all other features | Must understand current state before changing architecture | -- Pending |
| slowapi for rate limiting | FastAPI-native, per-endpoint control | -- Pending |
| loguru over stdlib logging | Structured logging, never log sensitive data | -- Pending |

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
*Last updated: 2026-04-01 after Phase 05 completion*
