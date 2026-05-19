# NexusOSINT — Revisão R0/R1 (lean, implementável)

**Status:** revisão enxuta dos dois plannings (`REAL_TIME_OSINT_PLAN.md` + `VISUAL_REDESIGN_PLAN.md`) consolidada após avaliação Codex.
**Data:** 2026-05-18
**Autor:** sessão Opus
**Escopo desta revisão:** apenas R0 (Contract shim) + R1 (Safe MVP). Tudo que cai fora dessas fases foi removido deste documento.
**Branches sugeridos:**
- R0 → `v4.1/r0-contract-shim`
- R1 → `v4.1/r1-safe-mvp` (abre só após R0 merged)

---

## 0. Princípios de corte (não-negociáveis)

1. **Contrato primeiro, motor depois.** R0 entrega só schema + adapter + estados visuais; nenhum novo conector externo, nenhuma fonte nova.
2. **Legacy intocado.** `/api/search` v1 e `_legacy_sherlock_from_v2` continuam servindo o frontend atual até `/api/v2/search` rodar 7 dias estável.
3. **UI prepara, não promete.** Componentes Graphite & Ember + Signal v2 ganham forma, mas qualquer painel sem backend real (Source Health, Jobs Queue, Cases persistentes) entra como *empty state honesto*, nunca mock.
4. **Probes sensíveis = compliance gate.** Forgot-password (Twitter/IG/Google), WhatsApp QR, Telegram resolve, Truecaller, HIBP: **fora de R0/R1**. Aparecem só após decisão legal/ToS documentada + feature flag backend + kill switch.
5. **Status 8-state end-to-end.** `pending / running / found / not_found / likely / uncertain / blocked / error`. `likely` **nunca** colapsa em `found` em nenhuma camada (backend, adapter, UI).
6. **Privacidade decide antes da migration.** `search_events.payload` exige decisão Math antes do MVP-4 (R1-2). Sem decisão, R1 não começa.
7. **CLAUDE.md protegido.** Documentar em `docs/CONNECTORS.md` e atualizar `.planning/PROJECT.md`. CLAUDE.md só com aprovação explícita + checkpoint.

---

## 1. R0 — Contract shim (executável agora)

**Objetivo:** entregar `ConnectorResult` + status 8-state + adapter visual sobre o `/api/search` legado, sem tocar no motor real-time.

**Branch:** `v4.1/r0-contract-shim`.
**Pré-requisitos:** working tree limpo (committar `.planning/*` em commit isolado `docs(planning): backlog`; deletar `.tmp_vps_diff.txt`; mover `ultima.md` para `.planning/SESSAO_*`).

### 1.1 Tarefas em ordem

| # | Tarefa | Arquivos prováveis | Critério de aceite |
|---|---|---|---|
| R0-1 | Criar pacote `modules/connectors/` com `__init__.py` + `base.py` (schemas Pydantic v2 + enums). | `modules/connectors/__init__.py`, `modules/connectors/base.py` | `pytest tests/unit/connectors/test_base.py` verde. `from modules.connectors.base import ConnectorResult, ConnectorStatus, TargetType, Evidence` funciona. |
| R0-2 | Tokens visuais Graphite & Ember sob **feature flag visual** (`?theme=graphite` query param ou cookie `ui_theme=graphite`). Não tocar `meridian.css` original. | `static/css/tokens-graphite.css` (novo), `static/css/connectors.css` (novo), `static/js/theme-flag.js` (novo) | Flag off → visual atual idêntico (zero diff). Flag on → tokens novos aplicam só em elementos com classe `nx-v2`. |
| R0-3 | Componentes UI base (sem dados live): `StatusPill` 8-state, `ConnectorCard` empty/loading/loaded, `ConfidenceMeter`, `EvidenceDrawer` empty state. Vanilla JS, sem Lit, sem CDN. | `static/js/components/status-pill.js`, `static/js/components/connector-card.js`, `static/js/components/confidence-meter.js`, `static/js/components/evidence-drawer.js` | Storybook ASCII no `static/dev/components-preview.html` renderiza os 8 estados + empty states. Acessível por teclado (tab/enter). |
| R0-4 | Adapter legacy: traduz eventos atuais de `/api/search` (`_stream_search`) para `ConnectorResult` shape **em memória no client** (sem mudar backend). | `static/js/legacy-adapter.js` (novo), patch leve em `static/js/render.js` para chamar adapter quando flag visual on. | Buscar username com flag on → cada módulo do `_stream_search` aparece como `ConnectorCard` com status 8-state derivado. `likely` do sherlock continua `likely`, **não** vira `found`. |
| R0-5 | Cleanup de copy + remoção da quota OathNet do nav. Texto "Find anything on anyone" sai do hero (substituir por "Confirme. Não suponha." ou similar — decisão Math). | `static/index.html`, `static/admin.html` | Visual diff aprovado. Quota só visível em `/admin` (já existe). |
| R0-6 | Documentar contrato em `docs/CONNECTORS.md` (novo). Atualizar `.planning/PROJECT.md` com decisão R0/R1. **Não tocar `CLAUDE.md`.** | `docs/CONNECTORS.md` (novo), `.planning/PROJECT.md` (append) | PR review aprova doc. |
| R0-7 | Casebook: melhorar metadados do `localStorage` case (created_at, target_hash, summary_snapshot). Botão "Export PDF" continua usando `report_generator.py` existente. **Sem promover a entidade persistente.** | `static/js/cases.js` (verificar existência; criar se faltar), `modules/report_generator.py` (verificar template) | Salvar case → reabrir → vê metadados + botão export PDF funcional. |

### 1.2 Contrato `ConnectorResult` (R0-1) — fonte de verdade

```python
# modules/connectors/base.py
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TargetType(str, Enum):
    USERNAME = "username"
    EMAIL = "email"
    PHONE = "phone"


class ConnectorStatus(str, Enum):
    PENDING = "pending"        # planejado, não executado ainda
    RUNNING = "running"        # em execução (lifecycle)
    FOUND = "found"            # match confirmado por quórum
    LIKELY = "likely"          # sinal positivo sem quórum suficiente — NUNCA vira found
    NOT_FOUND = "not_found"    # negativo confirmado
    UNCERTAIN = "uncertain"    # sinais divergentes
    BLOCKED = "blocked"        # bot wall, CF, captcha, auth required — NÃO é not_found
    ERROR = "error"            # timeout, network, parse fail


ConfidenceLevel = Literal["high", "medium", "low", "none"]


class Evidence(BaseModel):
    signal: str                    # ex.: "status_code_200", "claim_text_match", "carrier_known"
    weight: int = Field(ge=-100, le=100)
    detail: str = ""


class ConnectorRequest(BaseModel):
    target_type: TargetType
    target_value: str              # normalizado: lower email, E.164 phone, trimmed username
    target_hash: str               # SHA-256[:12] do target_value normalizado
    timeout_s: int = 15
    job_id: UUID


class ConnectorResult(BaseModel):
    connector: str                 # "sherlock:tiktok" | "oathnet:breach" | "carrier_lookup" | ...
    target_type: TargetType
    status: ConnectorStatus
    confidence_score: int = Field(ge=0, le=100)
    confidence_level: ConfidenceLevel
    evidence: list[Evidence] = []
    warnings: list[str] = []
    raw_url: str | None = None     # URL pública consultada; nunca com query sensível
    data: dict = {}                # campos enriquecidos (avatar, country, mx, etc.) — sem PII em claro
    fetched_at: datetime
    cache_hit: bool = False
    elapsed_ms: int = Field(ge=0)
```

**Regras de derivação `confidence_level` (compartilhadas backend + frontend):**

```
confidence_score >= 85 → "high"
confidence_score >= 60 → "medium"
confidence_score >= 30 → "low"
confidence_score <  30 → "none"
```

### 1.3 Adapter legacy (R0-4) — contrato de tradução

Mapear evento atual `_stream_search` → `ConnectorResult` no client:

| Evento legacy | Connector name | Status derivado | Confidence derivada |
|---|---|---|---|
| sherlock `confirmed` | `sherlock:<platform>` | `found` | score do scoring 6-state |
| sherlock `likely` | `sherlock:<platform>` | `likely` | score do scoring |
| sherlock `unconfirmed` | `sherlock:<platform>` | `uncertain` | score baixo |
| sherlock `not_found` | `sherlock:<platform>` | `not_found` | 0 |
| sherlock `auth_blocked` / `cf_challenge` | `sherlock:<platform>` | `blocked` | 0 |
| sherlock `error` / `timeout` | `sherlock:<platform>` | `error` | 0 |
| oathnet breach record | `oathnet:breach` | `found` se ≥1 record, senão `not_found` | derivada de count |
| oathnet stealer | `oathnet:stealer` | idem | idem |
| oathnet ip_info | `oathnet:ip` | `found`/`not_found` | derivada |
| spiderfoot event | `spiderfoot:<event_type>` | `likely` por default | médio |

**Proibido no adapter:**
- Converter `likely` em `found`.
- Converter `blocked` em `not_found` ou `error`.
- Inventar `confidence_score` se backend não enviou; usar `0` + `confidence_level="none"`.
- Mostrar `target_value` em qualquer log do client; só `target_hash`.

### 1.4 Critérios de aceite R0

- [ ] Buscar username com flag off → comportamento idêntico ao atual (regression zero).
- [ ] Buscar username com flag on (`?theme=graphite`) → renderiza `ConnectorCard` por módulo, status 8-state correto, evidence drawer com signals reais ou empty state honesto.
- [ ] `likely` aparece como `likely` no UI (chip mostarda), **nunca** como `found` verde.
- [ ] `blocked` aparece como `blocked` (terra), distinto de `error` (ember).
- [ ] Storybook `static/dev/components-preview.html` renderiza os 8 estados sem dados reais.
- [ ] `docs/CONNECTORS.md` descreve schema + tabela de mapeamento legacy.
- [ ] Quota OathNet sumiu do nav; hero copy trocado.
- [ ] Memory resting do container <500 MB (sem regressão).
- [ ] PR review verde; checkpoint GSD salvo.

---

## 2. R1 — Safe MVP (após R0 merged + decisões de privacidade aprovadas)

**Objetivo:** motor real-time mínimo (`/api/v2/search` + job store + SSE replay) com **apenas fontes seguras** (adapters legacy + carrier offline + gravatar opcional). Zero probe sensível.

**Branch:** `v4.1/r1-safe-mvp`.

### 2.1 Gate bloqueante antes de R1-1

Math precisa responder **antes** de qualquer tarefa R1:

| # | Decisão | Opções | Bloqueia |
|---|---|---|---|
| G1 | Persistência de `search_events.payload` | (a) hash-only + TTL 7d (b) ChaCha20Poly1305 + TTL 30d | R1-2 (migration) |
| G2 | Gravatar no MVP | (a) permitir MD5 de email → terceiro com disclosure (b) adiar gravatar | R1-10 (adapter email) |
| G3 | Quórum mínimo para `status=found` agregado | (a) ≥2 conectores independentes (b) 1 conector com score ≥90 + `hard_positive` | R1-7 (orchestrator) |
| G4 | Reusar Thordata para email/phone | (a) sim, dentro da quota 1 GB/dia (b) orçar proxy separado | R1-5/R1-10 |

**Decisões fora de R1 (não decidir agora):**
- HIBP API → fora.
- Truecaller → fora (descartado do roadmap default).
- Forgot-password probes → fora.
- WhatsApp QR / Telegram resolve / Apple ID probe → fora.

### 2.2 Tarefas em ordem

| # | Tarefa | Arquivos prováveis | Critério de aceite |
|---|---|---|---|
| R1-1 | `modules/connectors/runner.py` — executa connector com timeout + `OutboundRateLimiter` + cache Redis + audit log SHA-256. | `modules/connectors/runner.py` | Unit: timeout vira `ConnectorStatus.ERROR`; 429 vira `BLOCKED`; cache hit retorna `cache_hit=True`. |
| R1-2 | Alembic migration: `search_jobs` + `search_events`. **`connector_metrics` fica fora.** Schema obedece decisão G1. | `migrations/versions/NNNN_real_time_osint_jobs.py` | `alembic upgrade head` em Postgres efêmero + VPS staging. Rollback `alembic downgrade -1` limpo. |
| R1-3 | `api/services/job_store.py` — CRUD asyncpg + `fetch_stream` para replay (cursor server-side, nunca `fetch_all` em events). | `api/services/job_store.py` | Integration test: criar job, inserir 50 events, replay com `from_seq=10` retorna 40 events em ordem. |
| R1-4 | Adapter `modules/connectors/username/sherlock_adapter.py` — envolve `search_username` existente, mapeia para `ConnectorResult`. | `modules/connectors/username/__init__.py`, `modules/connectors/username/sherlock_adapter.py` | Smoke E2E: busca retorna ≥1 `ConnectorResult` com status válido. `likely` preserva. |
| R1-5 | Adapter OathNet legado → `ConnectorResult` (breach, stealer, ip_info, victims). **Sem nova fonte.** | `modules/connectors/oathnet_adapter.py` | Eventos sanitizados (sem `target_value` em claro no payload); quota/cache preservados. |
| R1-6 | Conector `carrier_lookup` (offline via `phonenumbers` lib). Status máximo `likely` (nunca `found`, porque carrier não prova conta). | `modules/connectors/phone/__init__.py`, `modules/connectors/phone/carrier_lookup.py`, `requirements.txt` (+`phonenumbers==9.0.x`) | Unit cobre BR mobile, US landline, número inválido. Zero rede. |
| R1-7 | `api/services/search_orchestrator.py` — resolve connectors por target_type, submete via `TaskOrchestrator` (semaphore 5/3 existente), agrega `summary` aplicando regra G3. | `api/services/search_orchestrator.py` | Unit: 5 cenários (todos found, 1 found + 1 not_found → uncertain, todos blocked → blocked agregado, etc.). |
| R1-8 | `api/routes/search_v2.py` — `POST /api/v2/search`, `GET /api/v2/search/{job_id}/events?from_seq=N` (SSE replay), `GET /api/v2/search/{job_id}`. **Sem DELETE/cancel cooperativo em R1** (cai em R2). | `api/routes/search_v2.py`, `api/main.py` (registrar router) | E2E Playwright: POST → 201 com `job_id`; SSE retorna eventos em ordem; reconnect com `from_seq` retoma. |
| R1-9 | Frontend `static/js/v2-search.js` consome `/api/v2/search` (atrás de feature flag `?engine=v2`). Reusa componentes R0-3. **Sem fake "cancel" button.** | `static/js/v2-search.js`, `static/js/job-replay.js` | E2E: busca via flag v2 mostra `connector_result` events em tempo real; reconnect funciona. Flag off → `/api/search` legacy. |
| R1-10 | Conector `gravatar` (**condicional a G2 = (a)**). Envia MD5 de email, status máximo `likely`. Se G2 = (b), pular essa tarefa. | `modules/connectors/email/__init__.py`, `modules/connectors/email/gravatar.py` | Unit com `respx` mockando 200/404; status `likely` em 200, `not_found` em 404. |
| R1-11 | Job cleanup loop (TTL conforme decisão G1). Reusa padrão de `blacklist_purge_loop`. | `api/tasks.py` (estender) | Integration: jobs expirados são removidos; events em cascata via `ON DELETE CASCADE`. |
| R1-12 | `docs/CONNECTORS.md` atualizado com fontes R1 + tabela de status. `.planning/PROJECT.md` registra G1-G4 escolhidas. | `docs/CONNECTORS.md`, `.planning/PROJECT.md` | Math aprova. |

### 2.3 Contratos SSE (R1-8) — fonte de verdade

Eventos emitidos por `GET /api/v2/search/{job_id}/events`:

```json
{ "event": "job_started",
  "seq": 1,
  "data": { "job_id": "uuid", "target_type": "phone", "target_hash": "a1b2c3d4e5f6",
            "connectors_planned": ["carrier_lookup", "oathnet:breach", "oathnet:stealer"] } }

{ "event": "connector_started",
  "seq": 2,
  "data": { "connector": "carrier_lookup", "status": "running", "started_at": "2026-05-18T17:12:08Z" } }

{ "event": "connector_result",
  "seq": 3,
  "data": { /* ConnectorResult sanitizado — sem target_value em claro */ } }

{ "event": "connector_error",
  "seq": 4,
  "data": { "connector": "oathnet:breach", "status": "error", "error_type": "timeout",
            "message": "upstream timeout" } }

{ "event": "progress",
  "seq": 5,
  "data": { "done": 2, "total": 3, "pct": 67 } }

{ "event": "summary",
  "seq": 6,
  "data": { "job_id": "uuid", "overall_status": "likely", "overall_confidence": 72,
            "found_count": 0, "likely_count": 2, "not_found_count": 1,
            "blocked_count": 0, "error_count": 0,
            "agreement_ratio": 0.67 } }

{ "event": "done",
  "seq": 7,
  "data": { "elapsed_s": 4.2 } }
```

**Regras imutáveis:**
- `seq` monotônico crescente por job; cliente deduplica.
- `overall_status` segue regra G3; **nunca** promove `likely` para `found`.
- `payload` de `connector_result` **nunca** contém `target_value` em claro (apenas `target_hash` quando aplicável).
- `connector_error.message` é genérica; detalhes vão para log interno com `target_hash`.

### 2.4 Schema `search_jobs` / `search_events` (R1-2)

Versão mínima R1 — `connector_metrics` fica para depois:

```sql
CREATE TABLE search_jobs (
    id              UUID PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id),
    target_type     TEXT NOT NULL,
    target_hash     TEXT NOT NULL,
    target_encrypted BYTEA,                    -- preenchido apenas se G1 = (b)
    status          TEXT NOT NULL,             -- 'queued'|'running'|'done'|'failed'
    overall_status  TEXT,                      -- 8-state final
    overall_confidence INTEGER,
    connectors_planned TEXT[],
    connectors_run     TEXT[],
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    elapsed_ms      INTEGER,
    expires_at      TIMESTAMPTZ NOT NULL       -- TTL conforme G1
);
CREATE INDEX ix_search_jobs_user_id_created_at ON search_jobs(user_id, created_at DESC);
CREATE INDEX ix_search_jobs_expires_at ON search_jobs(expires_at);

CREATE TABLE search_events (
    id          BIGSERIAL PRIMARY KEY,
    job_id      UUID NOT NULL REFERENCES search_jobs(id) ON DELETE CASCADE,
    seq         INTEGER NOT NULL,
    event_type  TEXT NOT NULL,
    payload     JSONB NOT NULL,                -- sanitizado conforme G1
    emitted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (job_id, seq)
);
CREATE INDEX ix_search_events_job_id_seq ON search_events(job_id, seq);
```

**Variação por decisão G1:**
- G1 = (a) hash-only + TTL 7d → `target_encrypted` fica `NULL`; payload contém apenas hashes + metadata; `expires_at = created_at + INTERVAL '7 days'`.
- G1 = (b) ChaCha20Poly1305 + TTL 30d → `target_encrypted` populado (chave em `.env`, nunca em DB); payload pode conter campos com referência ao job para descriptografar sob demanda; `expires_at = created_at + INTERVAL '30 days'`.

### 2.5 Critérios de aceite R1

- [ ] `POST /api/v2/search` + busca de phone (placeholder `+5511XXXXXXXXX`) → `summary` em <3s com `carrier_lookup` (`likely` máximo, **nunca** `found`).
- [ ] Busca username → ≥10 `connector_result` events via `sherlock_adapter`; `likely` preserva ponta-a-ponta.
- [ ] Desconectar SSE no meio → reconectar com `?from_seq=N` retoma sem perda.
- [ ] Flag `?engine=v2` off → `/api/search` legacy responde idêntico (regression zero).
- [ ] `search_events.payload` obedece G1 (auditar 5 jobs aleatórios em staging).
- [ ] Memory resting <500 MB; sob 5 buscas simultâneas <2000 MB (não atinge alerta).
- [ ] Zero `except Exception` genérico; zero `target_value` em log estruturado.
- [ ] `docker images nexus` <250 MB (após `phonenumbers` somado).
- [ ] Test suite: unit ≥80% (`connectors/`, `job_store`, `orchestrator`), integration ≥60% (`search_v2` API + SSE), E2E `realtime-search.spec.ts` verde.
- [ ] `docs/CONNECTORS.md` reflete G1-G4. `CLAUDE.md` intocado.

---

## 3. UI preparada (Signal v2 + Graphite & Ember) — sem promessas falsas

Princípios para R0/R1 no frontend:

| Tela / componente | R0 | R1 | Pós-R1 |
|---|---|---|---|
| Workspace shell (sidebar + topbar) | Sob flag visual, monta layout vazio | Conecta com `/api/v2/search` para "active investigation" | — |
| Live view (Gantt + connector grid) | Componentes prontos, dados legacy via adapter | Dados reais SSE; Gantt usa `connector_started` + `connector_result.elapsed_ms` | — |
| Status pill 8-state | Sim | Sim | — |
| Confidence meter | Sim, dados do scoring atual via adapter | Dados de `overall_confidence` | — |
| Evidence drawer | Sim, com signals do scoring v2 (já existem em backend) | Mesmo, mais ricos via `ConnectorResult.evidence` | — |
| Cmd+K quick search | **Não** (não inventar UX nova ainda) | **Não** | R2+ |
| Source Health (admin) | Empty state honesto: "metrics unavailable until connector_metrics exists" + link `docs/CONNECTORS.md` | Mesmo (connector_metrics fica para R2/R3) | R3 |
| Jobs & Queue (admin) | Empty state honesto | Mostra `search_jobs` recentes (read-only, sem cancel) | R2 |
| Cases | localStorage com metadados melhorados (R0-7) + export PDF | Mesmo + `job_id` referenciado | R3+ (entidade persistente) |
| Casebook export (PDF/JSON) | PDF via `report_generator.py` existente | PDF inclui `connector_result` + evidence | — |
| Cancel / Pause / Retry buttons | **Não criar** | **Não criar** (backend não tem cancel cooperativo em R1) | R2 |
| Chain graph | **Não** | **Não** | R5 |
| Marketplace / billing / multi-tenancy | **Não** | **Não** | v2/v5 |

**Anti-padrões proibidos em R0/R1:**
- Qualquer barra de progresso com porcentagem inventada (`Math.random()`-style).
- Qualquer source health % sem `connector_metrics`.
- Qualquer chip "uptime 99%" sem dado real.
- Botão "Retry" que só esconde card.
- Botão "Cancel" que não chama backend cooperativo.
- Lit/Stencil/qualquer framework via CDN.
- Renomear `index.html` ou mover rota raiz.

---

## 4. Casebook — escopo R0/R1

**Mantido:** export PDF/JSON via `modules/report_generator.py` (já existe).

**R0-7 melhora:**
- Metadados do case salvo (`localStorage`): `created_at`, `updated_at`, `target_hash`, `target_type`, `summary_snapshot` (status agregado + counts).
- UI: lista de cases ordenada por `updated_at` desc; cada item mostra status pill + counts.
- Botão "Export PDF" usa template existente; adiciona footer "NexusOSINT · case_id · generated_at".

**R1 adiciona:**
- Case pode referenciar `job_id` (R1) para retomar investigation no live view.
- Export PDF inclui evidence drawer de cada conector (signals + weights).
- Export JSON inclui `ConnectorResult[]` completos (sanitizados).

**Fora de R0/R1 (não fazer):**
- Cases persistentes em DB (espera `cases` table — R3+).
- Compartilhamento de case via signed URL.
- Multi-user collaboration.

---

## 5. Ordem de execução consolidada

```
[clean working tree]
    ↓
[commit .planning/* em "docs(planning): backlog"]
    ↓
branch v4.1/r0-contract-shim
    ├── R0-1 (ConnectorResult schema)
    ├── R0-2 (tokens Graphite & Ember sob flag)
    ├── R0-3 (componentes UI base)
    ├── R0-4 (adapter legacy)
    ├── R0-5 (cleanup copy + nav)
    ├── R0-6 (docs/CONNECTORS.md + PROJECT.md)
    └── R0-7 (casebook metadata + export)
    ↓
PR + review + merge → master
    ↓
deploy + smoke prod (flag off por default)
    ↓
[Math responde G1-G4]
    ↓
branch v4.1/r1-safe-mvp
    ├── R1-1 (connector runner)
    ├── R1-2 (Alembic migration conforme G1)
    ├── R1-3 (job_store + fetch_stream)
    ├── R1-4 (sherlock_adapter)
    ├── R1-5 (oathnet_adapter)
    ├── R1-6 (carrier_lookup offline)
    ├── R1-7 (search_orchestrator + quórum G3)
    ├── R1-8 (routes/search_v2.py + SSE replay)
    ├── R1-9 (frontend v2-search.js sob flag ?engine=v2)
    ├── R1-10 (gravatar — apenas se G2=a)
    ├── R1-11 (job cleanup loop)
    └── R1-12 (docs)
    ↓
PR + review + merge → master
    ↓
deploy + 7 dias prod com flag off por default
    ↓
ligar flag para subset de users → monitorar → ligar para todos
    ↓
[só depois disso considerar R2 (Source Health real) + R3 (Jobs & Queue) + R4 (probes lab)]
```

---

## 6. O que **não** entra em R0/R1 (decisão registrada)

| Item | Por quê | Quando revisitar |
|---|---|---|
| Forgot-password probing (Twitter/IG/Google) | ToS incerto, endpoints instáveis, FP alto | R4, após compliance gate |
| WhatsApp QR / Telegram resolve / Apple ID | Probe sensível, instável, legal cinza | R4, após compliance gate |
| Truecaller | Juridicamente cinza | Removido do roadmap default; reabrir só com aprovação legal |
| HIBP API | Custo + ToS + disclosure obrigatório | Pós-R4, decisão separada |
| `connector_metrics` table + Source Health real | Precisa de runs reais para popular | R2/R3 |
| Cancel/retry cooperativo de job | Requer protocolo cooperativo no orchestrator | R2 |
| Chain suggestions (phone → email descoberto) | Requer fontes ricas e quórum confiável | R5 |
| Cases persistentes em DB | Espera estabilizar job store | R3+ |
| Chain graph (SVG) | UI cara, requer ≥2 investigations vinculadas | R5+ |
| Connector marketplace (YAML / sandbox) | Plataforma — fora do MVP | v2/v5 |
| Multi-tenancy / billing / API keys per-user | Comercial — fora do hardening atual | v2/v5 |
| Atlas Paper light theme | Custo 1.6× CSS para tema secundário | v2 do redesign |
| Renomear `index.html` / criar landing pública | Arrisca auth atual | Pós-R1 |
| Lit / Stencil / framework via CDN | CSP/hardening + disponibilidade | Reavaliar em R2+ com asset local pinado |

---

## 7. Riscos R0/R1 e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Adapter legacy converte `likely` em `found` por bug de mapping | Média | Alto (falso positivo viraliza) | Unit test específico: cada estado legacy → estado 8-state esperado; CI quebra se mapping mudar sem update do teste. |
| Flag visual on por engano em prod antes de R0 estar polido | Baixa | Médio | Default off; flag só por query param/cookie explícito; smoke E2E roda com flag on e off. |
| Migration R1-2 lock prolongado em `users` (FK em `search_jobs`) | Baixa | Médio | Migration adiciona apenas tabelas novas; FK opcional com `ON DELETE SET NULL`; deploy fora de horário de pico. |
| Decisão G1 = (b) (criptografia) vira blocker porque key management não foi pensado | Média | Médio | Pré-acordar com Math: chave em `.env`, rotacionada manualmente; `cryptography` lib já em deps; documentar rotação em `docs/CONNECTORS.md`. |
| SSE replay vaza event de job de outro user | Baixa | Crítico (LGPD + segurança) | `GET /api/v2/search/{job_id}/events` valida `user_id == current_user.id`; integration test cobre cross-user 403. |
| `phonenumbers` lib infla docker image >250 MB | Baixa | Médio | Medir após instalação; se passar, considerar `phonenumbers-lite` ou geocoder excluído. |
| Cliente do Codex assume "summary" como real-time confiável e exibe sem evidence | Média | Médio (UX honesto) | EvidenceDrawer obrigatório no template; sem `summary` exibido sem botão "Why?" funcional. |

---

## 8. Definition of Done (R0/R1 agregada)

- [ ] Zero `except Exception` genérico em código novo (CLAUDE.md regra).
- [ ] Todo conector com timeout explícito + rate limit + cache + audit log SHA-256.
- [ ] Zero `target_value` em claro em logs estruturados ou em `search_events.payload`.
- [ ] Zero lógica de autorização no frontend.
- [ ] Zero probe sensível habilitado (forgot-pwd, WhatsApp, Telegram, Truecaller, HIBP).
- [ ] `ConnectorStatus` 8-state preservado end-to-end; nenhuma camada colapsa `likely` em `found`.
- [ ] `docker images nexus` <250 MB.
- [ ] Memory resting <500 MB; sob 5 buscas <2000 MB.
- [ ] Test suite verde (unit ≥80%, integration ≥60%, E2E coverage do realtime-search).
- [ ] Rollback documentado por fase (revert do merge commit + rollback Alembic em R1).
- [ ] `docs/CONNECTORS.md` + `.planning/PROJECT.md` atualizados.
- [ ] `CLAUDE.md` **intocado** (a menos que Math aprove explicitamente + checkpoint).
- [ ] Conferência manual: SSE reconnect, summary, evidence drawer, flag visual, flag engine.

---

## 9. Perguntas Math (gate R1)

Responder antes de abrir branch `v4.1/r1-safe-mvp`:

1. **G1** — `search_events.payload`: **(a)** hash-only + TTL 7d ou **(b)** ChaCha20Poly1305 + TTL 30d?
2. **G2** — Gravatar no MVP: **(a)** permitir MD5 de email → terceiro com disclosure ou **(b)** adiar?
3. **G3** — Quórum `status=found` agregado: **(a)** ≥2 conectores independentes ou **(b)** 1 conector com score ≥90 + `hard_positive`?
4. **G4** — Reusar Thordata para email/phone: **(a)** sim, dentro da quota 1 GB/dia ou **(b)** orçar proxy separado?

(Truecaller / HIBP / forgot-pwd / WhatsApp / Telegram / Apple ID **não** estão sob decisão agora — todos fora do roadmap R0/R1.)

---

**Fim da revisão R0/R1.** Próximo passo: Math aprova R0 inteiro (sem decisões bloqueantes), abrir branch `v4.1/r0-contract-shim`, executar R0-1 a R0-7. R1 só começa após G1-G4 respondidas.
