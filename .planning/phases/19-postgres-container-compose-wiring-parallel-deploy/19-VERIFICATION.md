# Phase 19 Verification - Postgres Container Compose Wiring

**Date:** 2026-05-09
**Verdict:** PASSED

## Goal

Stand up Postgres alongside SQLite without cutover risk. App still on SQLite at end of phase.

## Requirement Coverage

- DBM-05: `postgres:16-alpine` runs on private `nexus_net`; no public `5432` mapping.
- DBM-06: Postgres memory/tuning flags are configured and runtime memory is below `768MiB`.
- DBM-07: `postgres_data` named volume created on Hetzner.
- DBM-08: Postgres healthcheck is healthy and Nexus waits on service health.
- DBM-09: Postgres password is Docker-secret backed by `secrets/pg_password.txt`.
- DBM-10: Nexus memory limit is `2500m`; runtime memory is below budget.

## Evidence

- Local `docker compose config --quiet` passed.
- VPS `docker compose config --quiet` passed.
- `docker compose up -d --build` completed on Hetzner.
- `docker compose ps` showed `nexus-postgres` as healthy and only `5432/tcp`, with no host mapping.
- `docker exec nexus-postgres pg_isready -U nexus -d nexusosint` returned accepting connections.
- `curl -fsS https://nexusosint.uk/health` returned `status: healthy`.
- `docker stats --no-stream nexus-postgres nexus-osint` showed:
  - `nexus-postgres`: `28.99MiB / 768MiB`
  - `nexus-osint`: `59.09MiB / 2.441GiB`
- `DATABASE_URL_ABSENT` confirmed Nexus remains on SQLite.

## Non-Actions Confirmed

- No migrations were run.
- No `DATABASE_URL` was set.
- No Postgres cutover was performed.

## Result

Phase 19 is complete. Production now has healthy parallel Postgres infrastructure ready for later schema and cutover phases.
