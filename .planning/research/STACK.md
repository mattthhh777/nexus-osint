# Stack Research — SQLite → PostgreSQL Migration

**Domain:** OSINT platform backend (FastAPI + async agents)
**Researched:** 2026-05-07
**Confidence:** HIGH (driver, versions, pooling) / MEDIUM (RAM estimates — environment-dependent)

---

## Executive Recommendation

| Decision | Choice | One-liner |
|---|---|---|
| Driver | **asyncpg 0.31.0** | Native async, ~5x faster than psycopg3, mínimo overhead de RAM |
| Postgres version | **PostgreSQL 16-alpine** (16.x latest) | Maduro, ecossistema estável, suficiente para o workload do NexusOSINT |
| Pooling | **asyncpg built-in pool** (sem PgBouncer) | 10 agents simultâneos não justifica processo separado |
| Migrations | **Alembic async** | Padrão do ecossistema FastAPI/SQLAlchemy, autogenerate funcional |
| Backup | **pg_dump via cron** (diário + retenção 7d) | WAL archiving é overkill para single-instance interno |
| ORM/Query | **asyncpg cru + SQLAlchemy 2.0 Core** (sem ORM) | Manter padrão atual de queries explícitas, ORM adiciona RAM e indireção |

**RAM target consolidado**: Postgres ~250-350MB + FastAPI ~200-300MB ≈ **~600MB resting**, dentro do envelope de 4GB com folga real.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| PostgreSQL | **16-alpine** (16.x mais recente) | Banco relacional principal | v16 tem 1+ ano em produção, extensões estáveis, bug fixes consolidados. v17 ainda tem riscos de regressão para um produto pequeno. Alpine reduz imagem em ~60% vs debian-slim. |
| asyncpg | **0.31.0** (lançado 2025-11-24) | Driver PostgreSQL async-native | Built from scratch para asyncio. ~5x mais rápido que psycopg3 em workloads de alta concorrência. Suporta Postgres 9.5–18 e Python 3.9–3.14. Sem dependência de libpq. |
| SQLAlchemy Core | **2.0.x** (latest) | Query builder + schema definition | Usado APENAS como Core (sem ORM session). Garante schema-as-code para Alembic, mas executa via asyncpg cru. Evita overhead do ORM (sessions, identity map, lazy loading). |
| Alembic | **1.13+** | Database migrations | Padrão de facto. Suporta async via template `-t async`. Autogenerate compara MetaData ↔ DB. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncpg-stubs | latest | Type hints para asyncpg | Dev-only — asyncpg não tem stubs nativos completos |
| psycopg2-binary | 2.9+ | Driver síncrono para Alembic offline | Apenas para `alembic upgrade` em scripts de deploy (Alembic offline mode é síncrono). Não usar em runtime. |
| greenlet | latest | Requerido por SQLAlchemy async | Dependência transitiva de SQLAlchemy 2.0 async. Já entra via pip. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `pgcli` | REPL melhorado para Postgres | `pip install pgcli` — autocomplete, syntax highlight para debugging local |
| `pg_dump` / `pg_restore` | Backup logical | Já vem na imagem `postgres:16-alpine`; chamar via `docker exec` no cron |
| `EXPLAIN (ANALYZE, BUFFERS)` | Query profiling | Substitui o `EXPLAIN QUERY PLAN` do SQLite — output muito mais rico |

---

## Installation

```bash
# Core (runtime)
pip install asyncpg==0.31.0
pip install "sqlalchemy[asyncio]>=2.0,<2.1"
pip install alembic>=1.13
pip install psycopg2-binary>=2.9     # Alembic offline only

# Dev
pip install asyncpg-stubs
pip install pgcli                     # local debugging
```

**`requirements.txt` delta** (a adicionar):

```
asyncpg==0.31.0
sqlalchemy[asyncio]>=2.0.30,<2.1
alembic>=1.13.0
psycopg2-binary>=2.9.9
greenlet>=3.0
```

**A remover** após migração completa:
```
aiosqlite
```

---

## Docker Compose — Configuração validada para 4GB VPS

```yaml
services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: nexusosint
      POSTGRES_USER: nexus
      POSTGRES_PASSWORD_FILE: /run/secrets/pg_password
      POSTGRES_INITDB_ARGS: "--data-checksums"
    command: >
      postgres
      -c shared_buffers=256MB
      -c effective_cache_size=512MB
      -c work_mem=8MB
      -c maintenance_work_mem=64MB
      -c max_connections=30
      -c wal_buffers=8MB
      -c random_page_cost=1.1
      -c effective_io_concurrency=200
      -c log_min_duration_statement=500
    shm_size: 256mb              # CRÍTICO: default 64MB quebra Postgres
    volumes:
      - ./pgdata:/var/lib/postgresql/data
      - ./backups:/backups
    deploy:
      resources:
        limits:
          memory: 700m            # teto duro — protege FastAPI de starvation
        reservations:
          memory: 300m
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nexus -d nexusosint"]
      interval: 10s
      timeout: 5s
      retries: 5
    secrets:
      - pg_password

  nexus:
    # ... config existente
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: "postgresql+asyncpg://nexus@postgres:5432/nexusosint"
    deploy:
      resources:
        limits:
          memory: 2800m           # reduzido de 3500m para dar espaço ao Postgres

secrets:
  pg_password:
    file: ./secrets/pg_password.txt
```

**Justificativa do tuning (postgres-low-mem profile):**

| Param | Valor | Racional para 4GB VPS coexistindo com FastAPI |
|---|---|---|
| `shared_buffers` | 256MB | ~6% da RAM total. Padrão é 25%, mas FastAPI também precisa de espaço. |
| `effective_cache_size` | 512MB | Hint ao planner — não aloca RAM, só informa. |
| `work_mem` | 8MB | Por operação de sort/hash. Com 30 conexões max, pico teórico = 240MB. |
| `maintenance_work_mem` | 64MB | Para VACUUM, CREATE INDEX. |
| `max_connections` | 30 | NexusOSINT usa Semaphore(10), mas reserva margem para Alembic, pgcli, backup. |
| `shm_size` (Docker) | 256MB | Default Docker = 64MB — quebra Postgres com queries de hash join sérias. |
| `mem_limit` container | 700MB | Hard ceiling — observado ~250-350MB resting + buffers. |

---

## Connection Pooling — asyncpg pool (sem PgBouncer)

**Decisão:** asyncpg built-in pool. PgBouncer é overkill para single-instance com 10 agents.

```python
# api/db.py
import asyncpg
from contextlib import asynccontextmanager

class Database:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=2,             # warm pool — evita cold start no primeiro request
            max_size=10,            # alinhado com Semaphore(10) do orchestrator
            max_inactive_connection_lifetime=300.0,  # 5min — recicla conexões idle
            command_timeout=30.0,   # statement timeout default
            server_settings={
                'application_name': 'nexus_osint',
                'jit': 'off',       # JIT do Postgres consome RAM extra; off para queries pequenas
            },
        )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    @asynccontextmanager
    async def acquire(self):
        async with self._pool.acquire() as conn:
            yield conn
```

**Por que NÃO PgBouncer (agora)**:
- Adiciona um processo, ~10-20MB RAM, mais um ponto de falha
- Transaction-mode pooling do PgBouncer quebra prepared statements do asyncpg sem flag `statement_cache_size=0` (degrada perf)
- Útil apenas com 100+ conexões ou múltiplas instâncias da app — não é o caso aqui

**Quando reconsiderar**: se NexusOSINT escalar para múltiplas réplicas FastAPI atrás de um load balancer.

---

## Migration Strategy — Alembic async

```bash
# Inicialização (uma vez)
alembic init -t async migrations

# Configurar alembic.ini → sqlalchemy.url usa postgresql+asyncpg://...
# Configurar migrations/env.py → target_metadata = Base.metadata
```

**Workflow recomendado:**

1. Definir schema em `api/models.py` usando SQLAlchemy 2.0 Core (`MetaData`, `Table`)
2. `alembic revision --autogenerate -m "initial schema"` → gera migration baseada no diff
3. Revisar migration manualmente (autogenerate erra em renames, type changes sutis)
4. `alembic upgrade head` → aplica
5. **Migração de dados SQLite→Postgres**: script Python isolado (`scripts/migrate_sqlite_to_pg.py`) que lê do aiosqlite e escreve via asyncpg em batches de 1000 rows. **Não fazer via Alembic** — Alembic é para schema, não data dump.

**Regra**: Alembic gerencia schema. Migration de dados é script one-shot, idempotente, com checkpoint.

---

## Backup Strategy — pg_dump via cron

**Decisão**: pg_dump diário + retenção 7 dias. WAL archiving fica para v5.0 se RPO ficar inaceitável.

```bash
# /etc/cron.d/nexus-backup (no VPS)
0 3 * * * root /root/nexus-osint/scripts/backup.sh >> /var/log/nexus-backup.log 2>&1
```

```bash
#!/bin/bash
# scripts/backup.sh
set -euo pipefail
BACKUP_DIR=/root/nexus-osint/backups
TS=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

docker exec nexus-postgres-1 pg_dump \
    -U nexus -d nexusosint \
    --format=custom --compress=9 \
    --file=/backups/nexus_${TS}.dump

# Retenção
find ${BACKUP_DIR} -name 'nexus_*.dump' -mtime +${RETENTION_DAYS} -delete
```

**Justificativa**:
- 80GB SSD comporta facilmente 7 dumps comprimidos (estimativa: <500MB cada com compress=9)
- pg_dump format `custom` permite restore seletivo de tabelas
- WAL archiving exigiria ~2-5GB/semana em writes + um servidor de archive (S3/storage externo) — complexidade injustificada
- RPO efetivo: até 24h (aceitável para OSINT platform interno; alvos não são transacionais críticos)

**Quando migrar para WAL-G/pgBackRest**: se o produto crescer para múltiplos clientes pagantes com SLA explícito.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **asyncpg** | psycopg3 (async) | Se precisar de `LISTEN/NOTIFY` async ergonômico, `COPY` com pipeline mode, ou se o time já conhece psycopg2 — psycopg3 tem API mais familiar |
| **asyncpg cru + SA Core** | SQLAlchemy 2.0 ORM | Se aparecer um time grande precisando de produtividade > performance — ORM facilita CRUD mas custa RAM e indireção |
| **PostgreSQL 16** | PostgreSQL 17 | Para projeto novo com tolerância a issues iniciais. v17 tem ~2x throughput em write contention pesado, melhorias de VACUUM. Reavaliar em v5.0 quando tiver maturidade. |
| **asyncpg pool** | PgBouncer | Quando houver múltiplas instâncias FastAPI ou >100 conexões totais |
| **Alembic** | Raw SQL migrations (`yoyo-migrations`, `dbmate`) | Se quiser zero dependência Python para migrations e não precisar de autogenerate |
| **pg_dump cron** | WAL-G + S3 | Quando RPO < 1h for requisito; quando houver SLA explícito; quando DB crescer >10GB |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `asyncpg` sem pool (`asyncpg.connect` direto) | Cria conexão TCP+TLS por request — derruba latência e satura `max_connections` rápido | `asyncpg.create_pool` com `min_size=2, max_size=10` |
| `postgres:latest` ou `postgres:16` (sem `-alpine`) | ~430MB vs ~240MB do alpine; consome RAM extra com glibc + libs desnecessárias | `postgres:16-alpine` com digest fixado |
| Default `shm_size` Docker (64MB) | Postgres falha com `could not resize shared memory` em queries com hash join | `shm_size: 256mb` no compose |
| SQLAlchemy ORM com `lazy='select'` | N+1 queries silenciosos, RAM cresce com session de longa duração — anti-pattern para async-heavy | SA Core + queries explícitas, ou `selectinload` quando ORM for inevitável |
| `psycopg2` síncrono em runtime async | Bloqueia event loop, mata o ganho de async do FastAPI | `asyncpg` para runtime; `psycopg2-binary` apenas para Alembic offline |
| PgBouncer transaction mode + asyncpg sem `statement_cache_size=0` | Prepared statements quebram entre conexões pooladas → erros aleatórios `prepared statement does not exist` | Sem PgBouncer agora; se vier, configurar `statement_cache_size=0` no asyncpg |
| `pg_dump` enquanto VACUUM FULL roda | Lock contention, dump pode falhar | Cron 03:00 (low-traffic) + `lock_timeout=10s` no script |
| Autogenerate Alembic sem revisar | Erra em renames (vê DROP+ADD), perde dados | Sempre revisar manualmente o arquivo gerado antes de `upgrade` |

---

## Stack Patterns by Variant

**Se a app crescer para >2 réplicas FastAPI:**
- Adicionar PgBouncer em transaction mode
- asyncpg com `statement_cache_size=0`
- Reduzir `max_size` do pool por instância (ex: 5)

**Se RPO virar requisito de negócio (<1h perda):**
- Migrar de pg_dump para WAL archiving via WAL-G
- Storage externo (S3/B2) para WAL segments
- Base backup semanal + WAL contínuo

**Se DB ultrapassar 10GB:**
- Reavaliar `shared_buffers` (subir para 512MB-1GB se RAM permitir)
- Particionar tabelas de scans por data
- Avaliar upgrade para Postgres 17 pelos ganhos de VACUUM

**Se latência de read virar gargalo:**
- Não adicionar Redis ainda — primeiro medir com `pg_stat_statements`
- Indexes corretos resolvem 90% dos casos antes de cache

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| asyncpg 0.31.0 | PostgreSQL 9.5–18 | Testado com Postgres 16/17 sem issues conhecidos |
| asyncpg 0.31.0 | Python 3.9–3.14 | NexusOSINT em 3.12 → suporte de 1ª classe |
| SQLAlchemy 2.0.x async | asyncpg ≥0.27 | Usar `create_async_engine("postgresql+asyncpg://...")` |
| Alembic 1.13+ | SQLAlchemy 2.0 | Usar template `-t async` na inicialização |
| postgres:16-alpine | Docker shm_size ≥256MB | Default 64MB do Docker quebra queries complexas |
| psycopg2-binary 2.9 | Postgres 16/17 | Apenas para Alembic offline; não para runtime |

---

## Sources

- [asyncpg PyPI 0.31.0 (Nov 2025)](https://pypi.org/project/asyncpg/) — versão e compatibilidade Python/Postgres — **HIGH**
- [asyncpg GitHub releases](https://github.com/MagicStack/asyncpg/releases) — changelog 0.30→0.31 — **HIGH**
- [Postgres Docker Hub — postgres:16-alpine](https://hub.docker.com/_/postgres) — image tags oficiais — **HIGH**
- [Postgres 17 Release](https://www.postgresql.org/about/news/postgresql-17-released-2936/) — features e perf gains — **HIGH**
- [PostgreSQL Tuning Wiki](https://wiki.postgresql.org/wiki/Tuning_Your_PostgreSQL_Server) — shared_buffers, work_mem — **HIGH**
- [Instaclustr — Postgres Docker shared memory](https://www.instaclustr.com/blog/postgresql-docker-and-shared-memory/) — shm_size 64MB issue — **HIGH**
- [asyncpg FAQ — PgBouncer](https://magicstack.github.io/asyncpg/current/faq.html) — pooling guidance — **HIGH**
- [GitHub asyncpg #339 — PgBouncer transaction mode](https://github.com/MagicStack/asyncpg/issues/339) — `statement_cache_size=0` requirement — **HIGH**
- [PostgreSQL Continuous Archiving docs](https://www.postgresql.org/docs/current/continuous-archiving.html) — WAL archiving spec — **HIGH**
- [SISL — pg_dump vs WAL-G](https://sisl.pl/en/blog/postgresql-backups-pgdump-wal-g-managed) — backup strategy comparison — **MEDIUM**
- [TestDriven.io — FastAPI + Async SQLAlchemy + Alembic](https://testdriven.io/blog/fastapi-sqlmodel/) — Alembic async setup pattern — **MEDIUM**
- [Berk Karaal — FastAPI async SQLAlchemy 2 Alembic Postgres Docker](https://berkkaraal.com/blog/2024/09/19/setup-fastapi-project-with-async-sqlalchemy-2-alembic-postgresql-and-docker/) — receita completa — **MEDIUM**
- [TigerData — psycopg2 vs psycopg3 benchmark](https://www.tigerdata.com/blog/psycopg2-vs-psycopg3-performance-benchmark) — perf numbers — **MEDIUM**
- [fernandoarteaga.dev — Psycopg3 vs Asyncpg](https://fernandoarteaga.dev/blog/psycopg-vs-asyncpg/) — driver comparison — **MEDIUM**

---

*Stack research for: NexusOSINT v4.2 — SQLite → PostgreSQL migration*
*Researched: 2026-05-07*
