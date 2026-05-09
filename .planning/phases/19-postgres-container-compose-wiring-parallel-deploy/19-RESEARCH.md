# Phase 19 Research - Postgres Container + Compose Wiring

**Phase:** 19 - postgres-container-compose-wiring-parallel-deploy
**Researched:** 2026-05-09
**Status:** Existing v4.2 research distilled for execution planning

## Summary

Phase 19 does not need new external research. The v4.2 research set already resolves the implementation choices:

- `postgres:16-alpine`
- private Docker network only
- named volume, not bind mount
- password via Docker secret
- `mem_limit: 768m`
- `shm_size: 256mb`
- tuned server command flags
- healthcheck plus `depends_on.condition: service_healthy`
- Nexus memory limit `2500m`

The app remains on SQLite. This phase validates that the Postgres container can coexist with current Nexus, Redis, nginx, and certbot within the 4GB Hetzner budget.

## Key Findings for Planning

### OOM Prevention

Postgres defaults are unsafe for the shared 4GB VPS. The plan must set explicit memory and connection caps:

- `max_connections=20`
- `shared_buffers=256MB`
- `work_mem=8MB`
- `mem_limit: 768m`
- `shm_size: 256mb`

Nexus gets `2500m` as the working cap. Phase 23 later proves whether that cap survives burst load.

### Startup Race Prevention

Plain `depends_on` only orders container start. It does not wait for Postgres readiness. Phase 19 must add:

- `postgres.healthcheck` using `pg_isready`
- `nexus.depends_on.postgres.condition: service_healthy`

### Volume Permissions

The official Postgres image runs as UID 999 and rejects incorrectly owned bind mounts. Use a named Docker volume:

- `postgres_data:/var/lib/postgresql/data`

Do not use `./pgdata` or other bind mounts in this phase.

### Secret Handling

Do not put the Postgres password in `.env.example`, committed Compose literals, or `environment:`. Use:

- top-level `secrets.pg_password.file: ./secrets/pg_password.txt`
- service env `POSTGRES_PASSWORD_FILE=/run/secrets/pg_password`
- `.gitignore` entry for `secrets/`

### No Cutover

Do not set `DATABASE_URL` on the Nexus service yet. Doing so would invite accidental runtime drift before schema and driver work are ready.

## Validation Architecture

Phase 19 verification is mostly configuration and runtime smoke:

1. Static checks:
   - `docker compose config`
   - grep for `postgres:16-alpine`, `POSTGRES_PASSWORD_FILE`, `pg_password`, `postgres_data`, `condition: service_healthy`, `mem_limit: 768m`, `shm_size: 256mb`
   - grep confirms no Postgres `ports:` mapping.

2. Local/runtime checks:
   - `docker compose up -d --build postgres nexus`
   - `docker exec nexus-postgres pg_isready -U nexus -d nexusosint`
   - `docker compose ps` shows `postgres` healthy and `nexus` healthy.

3. VPS checks:
   - secret file exists on VPS with restrictive permissions.
   - `docker compose up -d --build`
   - `docker stats --no-stream` confirms Postgres is under 768MB and Nexus is under 2500MB at rest.
   - public health endpoint still returns healthy.

## Canonical References

- `.planning/research/SUMMARY.md`
- `.planning/research/STACK.md`
- `.planning/research/PITFALLS.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `docker-compose.yml`
- `.env.example`
- `.gitignore`

