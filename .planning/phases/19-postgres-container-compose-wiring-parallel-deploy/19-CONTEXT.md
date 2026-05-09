# Phase 19: Postgres Container + Compose Wiring - Context

**Gathered:** 2026-05-09
**Status:** Ready for execution planning
**Source:** GSD resume selection: discuss first, then continue with recommended defaults.

<domain>
## Phase Boundary

Stand up PostgreSQL 16 beside the existing SQLite runtime, without cutting the app over to Postgres.

This phase delivers Compose/runtime infrastructure only:

1. Add a private Postgres service to `docker-compose.yml`.
2. Add Docker secret wiring for the Postgres password.
3. Add named Postgres storage and healthcheck.
4. Gate `nexus` startup on Postgres health so Phase 20+ can rely on the service existing.
5. Reduce the Nexus memory budget to leave room for Postgres on the 4GB Hetzner VPS.
6. Deploy and smoke-test the parallel Postgres container.

Out of scope:

- No `DATABASE_URL` flip to Postgres.
- No Alembic setup.
- No schema creation beyond the default empty database.
- No SQLite data port.
- No asyncpg driver swap in `api/db.py`.
- No production cutover or maintenance-window write freeze.

Requirements covered: **DBM-05..DBM-10**.
</domain>

<decisions>
## Implementation Decisions

### Runtime Shape
- Use `postgres:16-alpine`.
- Keep Postgres reachable only on Docker private networking.
- Do not add `ports:` for Postgres.
- Reuse the existing Compose `internal` network key, but set its Docker network `name` to `nexus_net` so DBM-05 is satisfied without rewriting every service reference.
- Add `container_name: nexus-postgres`.
- Set `restart: unless-stopped`.
- Set `security_opt: ["no-new-privileges:true"]`.

### Postgres Tuning
- Set `mem_limit: 768m`.
- Also set `deploy.resources.limits.memory: 768m` and reservation `300m`.
- Set `shm_size: 256mb`.
- Use command flags:
  - `shared_buffers=256MB`
  - `work_mem=8MB`
  - `max_connections=20`
  - `idle_in_transaction_session_timeout=60s`
  - `maintenance_work_mem=64MB`
  - `effective_cache_size=768MB`
  - `jit=off`
  - `log_min_duration_statement=1000`

### Credentials
- Use Docker secret `pg_password`.
- Store secret file path as `./secrets/pg_password.txt`.
- Never commit the real secret file.
- Add `.gitignore` coverage for `secrets/`.
- Use `POSTGRES_PASSWORD_FILE=/run/secrets/pg_password`.
- Do not put the password in `environment:` or `.env.example`.

### Database Names
- Use `POSTGRES_DB=nexusosint`.
- Use `POSTGRES_USER=nexus`.
- Set `POSTGRES_INITDB_ARGS=--encoding=UTF8 --locale=C.UTF-8 --data-checksums`.

### Nexus Container
- App remains on SQLite at end of phase.
- Do not set `DATABASE_URL` in `nexus.environment` yet.
- Add `depends_on.postgres.condition: service_healthy`.
- Change Nexus memory limit to `2500m`.
- Keep Phase 23 as the gate that proves `nexus` peak stays under 2500m.

### Verification and Deploy
- Verify with `docker compose config`.
- Verify Postgres health with `pg_isready`.
- Verify no public Postgres port with `docker compose ps` and compose grep.
- On VPS, create the secret file before `docker compose up -d --build`.
- Deploy only after local commit.

### Claude's Discretion
- Exact placement of Postgres service in `docker-compose.yml`.
- Whether to include non-allocating tuning hints beyond the locked DBM values.
- Whether to add comments, as long as they are short and operationally useful.
</decisions>

<canonical_refs>
## Canonical References

### Phase Scope and Requirements
- `.planning/ROADMAP.md` - Phase 19 goal, deliverable, risk, and requirement IDs.
- `.planning/REQUIREMENTS.md` - DBM-05 through DBM-10 exact acceptance requirements and locked tuning values.
- `.planning/STATE.md` - Current milestone state and Phase 18 completion.

### Migration Research
- `.planning/research/SUMMARY.md` - v4.2 migration architecture and phase ordering.
- `.planning/research/STACK.md` - Postgres 16-alpine, asyncpg, Compose, and low-memory tuning recommendations.
- `.planning/research/PITFALLS.md` - OOM, startup race, volume permissions, public port, and backup pitfalls.
- `.planning/research/ARCHITECTURE.md` - Target architecture and component boundaries.

### Existing Runtime
- `docker-compose.yml` - Current Nexus, Redis, nginx, certbot services and network/volume patterns.
- `.env.example` - Public env reference; must not receive the Postgres password.
- `.gitignore` - Must ignore `secrets/`.
- `CLAUDE.md` - VPS constraints, deploy rules, protected files, and schema-change deploy warnings.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `docker-compose.yml` already has a private `internal` bridge network, named volumes, healthchecks, and Redis private-service precedent.
- Redis Phase 18 established the pattern: private service, no public `ports:`, healthcheck, named volume.
- Nexus currently runs on SQLite and does not use `DATABASE_URL`; this phase must not change DB runtime behavior.

### Established Patterns
- Compose services use explicit `container_name`.
- Production deploy uses `docker compose up -d --build`.
- Secrets are not committed; `.env` is protected and gitignored.

### Integration Points
- Postgres joins the same private app network used by Nexus.
- Nexus gets health-gated on Postgres for future phases, but still reads/writes SQLite in Phase 19.
- Phase 20 will consume this service for Alembic/schema work.
</code_context>

<specifics>
## Specific Ideas

The executor should prefer grep-verifiable Compose text and live Docker checks:

- `rg -n "postgres:16-alpine|POSTGRES_PASSWORD_FILE|pg_password|postgres_data|condition: service_healthy|mem_limit: 768m|shm_size: 256mb" docker-compose.yml`
- `docker compose config`
- `docker compose up -d --build postgres nexus`
- `docker exec nexus-postgres pg_isready -U nexus -d nexusosint`
- `docker compose ps`

For VPS deploy, create `/home/deploy/nexus-osint/secrets/pg_password.txt` with mode `600` before starting the Postgres service.
</specifics>

<deferred>
## Deferred Ideas

- App role split (`nexus_app` without DDL rights) can be added in Phase 20/25 once schema exists.
- Backup cron and restore drill belong to Phase 25.
- `DATABASE_URL` and asyncpg pool belong to Phase 22.
- Maintenance-window runbook belongs to Phase 24.
</deferred>

---

*Phase: 19-postgres-container-compose-wiring-parallel-deploy*
*Context gathered: 2026-05-09*
