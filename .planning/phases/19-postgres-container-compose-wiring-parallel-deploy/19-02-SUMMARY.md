---
phase: 19-postgres-container-compose-wiring-parallel-deploy
plan: 02
status: complete
completed: 2026-05-09
requirements-completed: [DBM-05, DBM-06, DBM-07, DBM-08, DBM-09, DBM-10]
key-files:
  modified:
    - DEPLOY.md
    - .planning/phases/19-postgres-container-compose-wiring-parallel-deploy/19-02-SUMMARY.md
key-decisions:
  - "VPS secret was created locally at secrets/pg_password.txt with mode 600."
  - "Deploy used git archive because the VPS worktree had unrelated dirty files."
  - "Nexus remains on SQLite; DATABASE_URL is absent."
---

# Phase 19 Plan 02 Summary - Compose Validation and Hetzner Smoke

## Objective

Document the Postgres secret bootstrap requirement, validate Compose, deploy the parallel Postgres service to Hetzner, and capture runtime smoke evidence.

## Tasks Completed

1. **Secret bootstrap documentation**
   - Added a Phase 19 Postgres section to `DEPLOY.md`.
   - Documented `secrets/pg_password.txt` creation and mode hardening.
   - Stated the secret must never be committed.
   - Stated Phase 19 does not cut Nexus over to Postgres; Nexus remains on SQLite until Phase 24.
   - Commit: `dc16e30`

2. **Local Compose validation**
   - `docker compose config --quiet` -> `COMPOSE_CONFIG_OK`.
   - Locked string scan found `postgres:16-alpine`, `POSTGRES_PASSWORD_FILE`, `pg_password`, `postgres_data`, `condition: service_healthy`, `memory: 2500m`, `mem_limit: 768m`, `shm_size: 256mb`, and `name: nexus_net`.
   - Manual service block check -> `POSTGRES_NO_PORTS`.

3. **Hetzner deploy and smoke test**
   - Pushed `master` through `dc16e30`.
   - Created `/home/deploy/nexus-osint/secrets/pg_password.txt` on the VPS with mode `600`.
   - Deployed the committed tree by `git archive` because the VPS worktree had unrelated dirty files.
   - `docker compose config --quiet` on VPS -> `VPS_COMPOSE_CONFIG_OK`.
   - `docker compose up -d --build` completed.

## Runtime Evidence

`docker compose ps` on Hetzner:

```text
nexus-nginx      Up 19 seconds             0.0.0.0:80->80/tcp, [::]:80->80/tcp, 0.0.0.0:443->443/tcp, [::]:443->443/tcp
nexus-osint      Up 19 seconds (healthy)   8000/tcp
nexus-postgres   Up 25 seconds (healthy)   5432/tcp
nexus-redis      Up 25 seconds (healthy)   6379/tcp
```

`docker exec nexus-postgres pg_isready -U nexus -d nexusosint`:

```text
/var/run/postgresql:5432 - accepting connections
```

Public health:

```text
{"status":"healthy","version":"3.0.0","degradation_mode":"normal","cache":{"backend":"redis","reachable":true}}
```

Memory at rest:

```text
nexus-postgres   28.99MiB / 768MiB     3.78%
nexus-osint      59.09MiB / 2.441GiB   2.36%
```

Port exposure and cutover checks:

```text
POSTGRES_NO_PUBLIC_PORT
DATABASE_URL_ABSENT
```

## Deviations from Plan

- Used archive-based deploy instead of `git pull` because the VPS worktree had many unrelated dirty files.
- Did not run migrations and did not set `DATABASE_URL`, as required.

## Outcome

DBM-05 through DBM-10 are runtime-verified in production Compose. Postgres is running in parallel, private-only, healthy, secret-backed, and within the memory budget. Nexus remains healthy on SQLite.

## Self-Check: PASSED
