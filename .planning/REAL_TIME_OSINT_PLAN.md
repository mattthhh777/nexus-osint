# NexusOSINT — Real-Time OSINT (premium, sem copiar OSINT Industries)

**Status:** Planejamento técnico — sem código. Revisado criticamente em 2026-05-18.
**Autor:** sessão Opus (planejamento), 2026-05-18.
**Branch base:** `master` (limpar `ultima.md`, `.tmp_vps_diff.txt` e committar `.planning/*` antes de abrir branch de execução).
**Escopo:** username + email + telefone, conectores plugáveis, real-time, anti-falso-positivo forte.

---

## Revisão crítica Codex — 2026-05-18

### Veredito

O plano faz sentido como direção de produto, mas estava ambicioso demais para o primeiro corte e misturava três coisas que precisam ser separadas:

1. **Contrato real-time**: schema de conector, status, evidence, confidence, cache/freshness.
2. **Execução persistente**: `search_jobs`/`search_events`, replay SSE, cancelamento, retenção.
3. **Novas fontes externas sensíveis**: forgot-password probing, WhatsApp/Telegram/Truecaller/HIBP.

Executar tudo junto aumenta risco técnico, risco legal, risco de falso positivo, consumo de proxy/quota e retrabalho no frontend. A correção é manter o contrato real-time como prioridade, mas reduzir o MVP para fontes seguras e adaptadores do que já existe.

### Notas pré-revisão

| Critério | Nota | Julgamento |
|---|---:|---|
| Qualidade do planning real-time OSINT | 6.0/10 | Boa arquitetura, escopo excessivo, compliance fraco. |
| Qualidade do planning visual/frontend | 7.5/10 | Forte direção visual, dependências backend demais. |
| Compatibilidade entre os dois planos | 7.0/10 | Modelo mental alinha, timing das fases não. |
| Implementabilidade no repo atual | 6.0/10 | Postgres/Redis ajudam; job store + UI + novos probes num MVP é grande demais. |
| Risco técnico | 7.5/10 | Alto, principalmente persistência + conectores cinza + SSE replay. |
| Clareza de UX | 7.5/10 | Bom foco em evidence/confidence; precisa não prometer live completo antes do backend. |
| Originalidade visual | 8.0/10 | Graphite & Ember diferencia; controlar accent para não voltar ao clichê hacker. |
| Preparação para futuro real-time OSINT | 8.0/10 | ConnectorCard + events são o caminho certo. |
| Segurança/compliance | 5.5/10 | Precisa gates fortes antes de probes externos e payload persistente. |
| Prioridade correta das fases | 6.0/10 | Deve começar por contrato/adaptadores, não por todas as telas e fontes. |

### Correções obrigatórias que sobrescrevem seções abaixo

1. **Repo atual é Postgres + Redis7.** Não reintroduzir SQLite nem padrões antigos.
2. **Status de conector deve ser 8-state:** `pending`, `running`, `found`, `not_found`, `likely`, `uncertain`, `blocked`, `error`. `likely` não pode virar `found`; isso destrói nuance anti-FP no frontend.
3. **MVP não inclui forgot-password probing, Truecaller, WhatsApp/Telegram presence ou HIBP por default.** Esses entram só após revisão legal/ToS, feature flag backend, baseline contra alvos controle e kill switch.
4. **MVP real-time usa fontes seguras:** adapter `sherlock_v2`, adapter OathNet legado, `gravatar` apenas se aprovado por privacidade, e `carrier_lookup` offline. Phone "presence" real fica fora do MVP.
5. **Persistência de events é decisão de privacidade, não detalhe técnico.** Antes da migration: escolher `hash-only + TTL 7d` ou `payload criptografado + TTL curto`. Não armazenar email/phone/telefone em claro por conveniência.
6. **`connector_metrics` e admin Source Health real ficam depois dos primeiros connector runs reais.** Sem dashboard falso com mock production-like.
7. **`/api/search` v1 permanece até `/api/v2/search` rodar 7 dias em produção sem incidente.** Nada de deprecar cedo.
8. **Frontend deve preparar componentes agora, mas live/reconnect/cancel/chain só quando o backend emitir contratos reais.**
9. **`CLAUDE.md` é protegido.** Não atualizar no MVP sem aprovação explícita + checkpoint; documentar primeiro em `docs/CONNECTORS.md` e `.planning/PROJECT.md`.
10. **Worker queue persistente fica limitada ao processo atual no MVP.** `search_jobs` permite replay/auditoria, mas não promete retomar job em voo após restart até haver recovery explícito.

### Faseamento corrigido

| Fase | Objetivo | Pode entrar agora? |
|---|---|---|
| R0 — Contract shim | `ConnectorResult` schema, status 8-state, adapter de eventos legacy `/api/search` para shape novo em teste. | Sim. |
| R1 — Safe MVP | `search_v2`, `job_store`, SSE replay, adapters `sherlock_v2` + OathNet legado + `carrier_lookup` offline. | Sim, após decisões de privacidade. |
| R2 — UI integration | Frontend consome `connector_result`, evidence, freshness, partial results. | Em paralelo com R1, sem mock enganoso. |
| R3 — Source health | `connector_metrics`, admin health real, block/error rate. | Depois de R1 em produção. |
| R4 — Risky probes lab | forgot-password, WhatsApp/Telegram, HIBP, Truecaller. | Só após compliance gate. |
| R5 — Chaining | `chain_suggestion`, parent jobs, case timeline. | Depois de dados reais e quorum confiável. |

---

## 0. Snapshot do estado atual (review)

### 0.1 Git
- Branch `master`, 1 commit à frente do `origin/master` (`37db14e fix: harden auth routes and add security e2e`).
- Working tree sujo:
  - Deletado: `PROPOSTA_MELHORIAS_API_PERFORMANCE.md` (movido para `.planning/`).
  - Modificado: `tests/e2e/README.md`, `tests/e2e/security-smoke.spec.ts`.
  - Untracked: `.planning/MAIGRET_VALIDATION_PLAN.md`, `.planning/PROPOSTA_MELHORIAS_API_PERFORMANCE.md`, `.planning/SESSAO_2026-05-12.md`, `.planning/hotfixes/CODEX_REVIEW_OPUS_PLAN.md`, `.tmp_vps_diff.txt`, `ultima.md`.
- Recomendação antes de iniciar: commit do `.planning/*` em commit isolado `docs(planning): backlog`; deletar `.tmp_vps_diff.txt` (lixo) e `ultima.md` (snapshot de sessão, mover para `.planning/SESSAO_*`).

### 0.2 Stack confirmada
- Backend: FastAPI 0.136 + asyncpg 0.31 + Redis 5.1 + SQLAlchemy 2.0 + Alembic.
- Frontend: Vanilla JS (3 648 LOC em 11 arquivos sob `static/js/`).
- Auth: JWT HS256 httpOnly + bcrypt + slowapi rate limit.
- Cache: `RedisCacheBackend` com fail-open + `InMemoryCacheBackend` fallback (`api/cache.py`).
- DB: `DatabaseManager` asyncpg pool 2-10 (`api/db.py`).
- Orquestração: `TaskOrchestrator` dual semaphore 5 global / 3 OathNet + `DegradationMode` NORMAL/REDUCED/CRITICAL (`api/orchestrator.py`).
- Memória: `memory_watchdog_loop` + `tracemalloc` ativo em produção.

### 0.3 Capacidades OSINT já implementadas
| Capacidade | Estado | Onde |
|---|---|---|
| Username (Sherlock + Maigret 500 sites) | **Pronto** | `modules/sherlock_wrapper.py` + `modules/username_check/*` |
| Validators plugáveis com signals/scoring 6-estados | **Pronto** | `modules/username_check/validators/*` + `scoring.py` |
| 8 validators site-specific (GitHub, IG, X, LinkedIn, Reddit, TikTok, YT, Medium) | **Pronto** | `modules/username_check/validators/sites/` |
| Breach + Stealer + Holehe + Discord + IP + Steam + Xbox + Roblox + GHunt + Victims | **Pronto via OathNet (pago)** | `modules/oathnet_client.py` (604 LOC) |
| SpiderFoot 14 tipos de evento | **Pronto** | `modules/spiderfoot_wrapper.py` |
| Proxy residencial Thordata sticky + IP rotation | **Pronto** | `modules/username_check/proxy.py` + `fetcher.py` |
| Outbound rate limit token-bucket por domínio | **Pronto** | `modules/username_check/rate_limit.py` |
| Cache Redis fail-open com TTL configurável | **Pronto** | `api/cache.py` |
| Audit log com SHA-256 hash do alvo | **Pronto** | `modules/username_check/audit.py` |
| SSE streaming progressivo | **Pronto** | `api/services/search_service.py::_stream_search` |

### 0.4 Gaps reais vs. OSINT Industries
| Lacuna | Impacto |
|---|---|
| Sem framework de **conector plugável** — username/email/phone são caminhos hardcoded no SSE | Adicionar fonte nova exige editar `_stream_search` (~980 LOC). Não escala. |
| **Email real-time** depende inteiramente de OathNet (pago, banco fechado). Sem probes públicos. | Sem fallback gratuito; quota da OathNet bloqueia. |
| **Phone real-time** inexistente. OathNet retorna `phone` só dentro de breach record, não busca direta. | Recurso ausente prometido no escopo do projeto. |
| Sem **status unificado** `found/not_found/uncertain/blocked/error` — cada módulo emite payload próprio | Frontend renderiza N formas diferentes; difícil correlação. |
| Sem **worker queue persistente** — se cliente desconecta, search morre | Sem retry, sem reconectar, sem auditoria pós-fato. |
| Sem **"forgot password" probing** (Google/Twitter/IG/Instagram revelam parte do email/phone) | Sinal público de alta qualidade ignorado. |
| Sem **chaining** entre fontes (email → username → social → phone) | OSINT Industries faz isso por default. |

---

## 1. Arquitetura proposta

### 1.1 Diagrama de camadas

```
                          ┌──────────────────────────┐
                          │  Vanilla JS UI (static/) │
                          │  - search bar            │
                          │  - SSE consumer          │
                          │  - evidence drawer       │
                          └────────────┬─────────────┘
                                       │  POST /api/v2/search
                                       │  GET  /api/v2/search/{job_id}/events (SSE)
                                       ▼
              ┌────────────────────────────────────────────┐
              │  api/routes/search_v2.py  (NEW)            │
              │  - input validation (Pydantic v2)          │
              │  - target type detection                   │
              │  - job create + enqueue                    │
              │  - SSE replay from job stream              │
              └────────────────────────┬───────────────────┘
                                       │
                                       ▼
              ┌────────────────────────────────────────────┐
              │  api/services/search_orchestrator.py (NEW) │
              │  - resolve connectors by target type       │
              │  - submit to TaskOrchestrator              │
              │  - merge results into job stream           │
              │  - chain workflows (email → username, …)   │
              └────────────────────────┬───────────────────┘
                                       │
              ┌─────────┬──────────────┼──────────────┬─────────┐
              ▼         ▼              ▼              ▼         ▼
           username   email          phone       legacy      enrichment
           connectors connectors    connectors   OathNet      (chain)
              │         │              │              │         │
              ▼         ▼              ▼              ▼         ▼
        ┌──────────────────────────────────────────────────────────┐
        │  modules/connectors/base.py  (NEW)                       │
        │  Connector ABC + ConnectorRequest/Result/Evidence schema │
        │  + status enum {pending, running, found, not_found,      │
        │                 likely, uncertain, blocked, error}       │
        └──────────────────────────────────────────────────────────┘
                                       │
                                       ▼
              ┌─────────────────────────────────────────────┐
              │  Shared infra (já existe — reusar)          │
              │  - OutboundRateLimiter (por domínio)        │
              │  - ThordataProxy (sticky + rotate)          │
              │  - RedisCacheBackend (TTL por conector)     │
              │  - asyncpg.Pool (search_jobs persistence)   │
              │  - audit log (SHA-256 hashed targets)       │
              └─────────────────────────────────────────────┘
```

### 1.2 Decisões de design

| Decisão | Escolha | Justificativa |
|---|---|---|
| Padrão de extensão | **Connector ABC + registry** (não plugin marketplace ainda) | Simples, type-safe, sem subprocess. Plugin externo fica para v2. |
| Persistência de job | **Postgres `search_jobs` + `search_events` (append-only)** | Permite reconectar SSE, auditoria, retry, escalabilidade. Reusar `asyncpg.Pool`. |
| Worker model | **TaskOrchestrator existente + fila Postgres** (não Celery, não Redis Streams) | VPS 4 GB não comporta Celery worker dedicado. asyncio basta. |
| Transport para client | **SSE** (mantém) + endpoint REST de polling para reconectar | SSE já existe e funciona; polling como fallback. WebSocket fica para v2. |
| Status enum | **8-state** unificado: `pending / running / found / not_found / likely / uncertain / blocked / error` | `pending/running` são lifecycle; `found/likely/uncertain/not_found` são outcome; `blocked/error` são falhas distinguíveis. `likely` fica distinto de `found` para evitar falso positivo visual. |
| Score | **0-100 por resultado** com `confidence_level` derivado (`high≥85`, `medium≥60`, `low≥30`, `none<30`) | Compatível com `scoring.py` atual. |
| Cache | **TTL por conector + key namespace por tipo de alvo** | Email tem TTL maior (24 h), phone menor (1 h), username 5 min como hoje. |
| Anti-FP | **Mínimo 2 validators concordantes para `found`** + baseline opcional + negative markers | Reusa pipeline atual. Estende para email/phone. |
| Rate limit out | **Reusar `OutboundRateLimiter`** com perfis por conector (calls_per_second tunável) | Já existe e funciona; só expor configuração. |
| Logging | **Audit estruturado SHA-256 hash do alvo** (nunca log de email/phone em claro) | CLAUDE.md regra 3 + LGPD. |

---

## 2. Estrutura de arquivos — criar vs. alterar

### 2.1 Criar

```
modules/
  connectors/
    __init__.py
    base.py                      # Connector ABC, schemas, enums, registry helpers
    registry.py                  # connector lookup por target_type + name
    runner.py                    # executa connector com timeout + rate limit + cache
    username/
      __init__.py
      sherlock_adapter.py        # adapta sherlock_wrapper p/ ConnectorResult
      maigret_adapter.py         # adapta maigret p/ ConnectorResult (separar de sherlock)
    email/
      __init__.py
      gravatar.py                # GET https://gravatar.com/{md5}.json — público, sem key
      github_email.py            # GET commits públicos do usuário e extrai noreply
      forgot_pwd_twitter.py      # LAB ONLY — compliance/ToS gate + kill switch
      forgot_pwd_instagram.py    # LAB ONLY — compliance/ToS gate + kill switch
      forgot_pwd_google.py       # LAB ONLY — compliance/ToS gate + kill switch
      hibp_breach.py             # OPTIONAL — requer key, ToS check, user disclosure
    phone/
      __init__.py
      whatsapp_qr.py             # LAB ONLY — presença de conta exige compliance gate
      telegram_resolve.py        # LAB ONLY — presença pública instável, alto FP
      truecaller_lookup.py       # DESCARTAR do MVP/v1 default; só lab com aprovação legal
      carrier_lookup.py          # libphonenumbers-based, offline (carrier + country + type)
      forgot_pwd_phone_apple.py  # LAB ONLY — compliance/ToS gate + kill switch

api/
  routes/
    search_v2.py                 # POST /api/v2/search + GET /api/v2/search/{id}/events
  services/
    search_orchestrator.py       # job lifecycle + connector dispatch + chain
    job_store.py                 # CRUD em search_jobs / search_events
  schemas/                       # promover schemas.py para pacote
    __init__.py
    targets.py                   # TargetType, TargetRequest, target detection
    connectors.py                # ConnectorRequest, ConnectorResult, Evidence
    jobs.py                      # SearchJob, JobEvent, JobStatus

migrations/
  versions/
    NNNN_real_time_osint_jobs.py # cria search_jobs/search_events; connector_metrics fica pós-MVP

static/
  js/
    connectors-render.js         # renderiza ConnectorResult unificado (status chip + evidence drawer)
    job-replay.js                # SSE reconnect + polling fallback
  css/
    connectors.css               # estilos do status chip e evidence drawer

tests/
  unit/connectors/
    test_base.py
    test_registry.py
    test_runner.py
    email/test_gravatar.py
    email/test_mx_check.py
    phone/test_carrier_lookup.py
    lab/test_forgot_pwd_twitter.py   # só quando compliance gate aprovar
    lab/test_whatsapp.py             # só quando compliance gate aprovar
  integration/
    test_search_v2_api.py
    test_job_store.py
  e2e/
    realtime-search.spec.ts
```

### 2.2 Alterar

| Arquivo | Mudança |
|---|---|
| `api/main.py` | Registrar `search_v2.router`. Não tocar no `search.router` antigo (deprecar em v2). |
| `api/orchestrator.py` | Sem mudanças no MVP. Em v1 adicionar método `submit_to_job(job_id, name, coro)` para roteamento. |
| `api/config.py` | Adicionar: `CONNECTOR_DEFAULT_TIMEOUT`, `CONNECTOR_CACHE_TTL_{USERNAME,EMAIL,PHONE}`, `CONNECTORS_ENABLED` (lista CSV), `JOB_TTL_SECONDS`, `JOB_MAX_AGE_DAYS`. |
| `api/services/search_service.py` | Refactor: extrair `_stream_search` longa em helpers; manter `/api/search` v1 funcionando. Sem regressão. |
| `modules/username_check/runner.py` | Implementar adapter para retornar `ConnectorResult` em vez de `SherlockResult`. Manter wrapper legado. |
| `modules/sherlock_wrapper.py` | Manter como façade legada; chamar internamente o adapter novo. |
| `requirements.txt` | Adicionar: `phonenumbers==9.0.x` (carrier/region offline), `email-validator==2.x` (rfc/mx check sem rede), `dnspython==2.6.x` (MX/SPF lookup para email). |
| `static/js/render.js` | Adicionar renderer para `connector_result` event (novo tipo SSE). |
| `static/js/search.js` | Apontar busca nova para `/api/v2/search`; manter fallback p/ `/api/search`. |

---

## 3. Organização dos módulos username/email/phone

### 3.1 Contrato Connector (base.py)

```python
# Pseudocódigo de contrato — NÃO implementar agora.

class TargetType(str, Enum):
    USERNAME = "username"
    EMAIL = "email"
    PHONE = "phone"

class ConnectorStatus(str, Enum):
    PENDING = "pending"     # planejado, ainda não executado
    RUNNING = "running"     # em execução; usado em eventos/lifecycle
    FOUND = "found"
    LIKELY = "likely"       # sinal positivo sem quorum suficiente
    NOT_FOUND = "not_found"
    UNCERTAIN = "uncertain"
    BLOCKED = "blocked"   # bot wall, CF challenge, login required
    ERROR = "error"       # timeout, network, parse fail

class Evidence(BaseModel):
    signal: str           # ex.: "status_code_200", "claim_text_match"
    weight: int           # -100..+100
    detail: str = ""

class ConnectorRequest(BaseModel):
    target_type: TargetType
    target_value: str             # já normalizado (lower email, E.164 phone)
    target_hash: str              # SHA-256[:12] p/ logs
    timeout_s: int = 15
    job_id: UUID

class ConnectorResult(BaseModel):
    connector: str                # "sherlock:tiktok", "oathnet:breach", "carrier_lookup"
    target_type: TargetType
    status: ConnectorStatus
    confidence_score: int         # 0..100
    confidence_level: Literal["high", "medium", "low", "none"]
    evidence: list[Evidence]
    warnings: list[str] = []
    raw_url: str | None = None    # URL pública consultada (NUNCA com query sensível)
    data: dict = {}               # campos enriquecidos (avatar, country, mx, etc.)
    fetched_at: datetime
    cache_hit: bool = False
    elapsed_ms: int

class Connector(Protocol):
    name: str                          # "gravatar"
    target_types: tuple[TargetType, ...]
    default_timeout_s: int
    rate_limit_cps: float              # calls per second p/ OutboundRateLimiter

    async def run(self, req: ConnectorRequest, http: httpx.AsyncClient) -> ConnectorResult: ...
```

### 3.2 Conectores por tipo (MVP scope)

**Username (refactor — reusar):**
- `sherlock:<platform>` — um por platform da lista curada
- `maigret:<site>` — top-N do banco Maigret

**Email (MVP seguro):**
- `gravatar` — opcional no MVP; envia MD5 do email a terceiro, então exige disclosure de fonte/cache e rate limit. 404 = `not_found`; 200 = `likely` ou `found` só com evidência forte.
- `mx_check` — DNS lookup do domínio via `dnspython`; valida domínio/deliverability, mas nunca prova conta individual.
- Adapter OathNet legado — expõe dados já existentes no formato `ConnectorResult`, sem adicionar nova fonte.

**Email (lab/v1 após compliance gate):**
- `github_email` — só se houver endpoint confiável e ToS compatível; não assumir `?author-email=` como contrato público estável.
- `forgot_pwd_twitter`, `forgot_pwd_instagram`, `forgot_pwd_google` — desabilitados por default. Alto risco de ToS, bloqueio, falso positivo e mudança de endpoint.
- `hibp_breach` — opcional com key e ToS/disclosure; não tratar como fonte gratuita pública.

**Phone (MVP seguro):**
- `carrier_lookup` — offline via `phonenumbers` lib (carrier + country + line_type). Resultado máximo: `likely`/`uncertain`, nunca "found account".
- Adapter OathNet legado — phone só quando vier de breach/stealer existente.

**Phone (lab/v1 após compliance gate):**
- `whatsapp_qr`, `telegram_resolve`, `forgot_pwd_apple` — não entram no MVP; presença de conta por probing é sensível e instável.
- `truecaller_lookup` — fora do v1 default. Só considerar com aprovação legal explícita.

### 3.3 Registry

```python
# modules/connectors/registry.py — contrato
def connectors_for(target_type: TargetType) -> list[Connector]: ...
def enabled_connectors(target_type: TargetType, env: list[str]) -> list[Connector]: ...
```

---

## 4. Validação e anti-falso-positivo

### 4.1 Reusar o que existe
- `modules/username_check/validators/base.py` — `Signal`, `ValidationOutcome` já bem desenhados.
- `modules/username_check/scoring.py::combine_outcomes` — lógica de 6-estados, peso, baseline_indistinguishable, auth_blocked, login_inconclusive.
- `validators/sites/*` — 8 validators site-specific.
- `negative_markers.py` — short-circuit por marcador negativo.
- `baseline_compare.py` — fetch de username inválido conhecido p/ comparar respostas.

### 4.2 Estender para email/phone

| Camada | Username (já existe) | Email (novo) | Phone (novo) |
|---|---|---|---|
| Sintaxe | regex `[A-Za-z0-9_.-]{1,64}` (`SherlockUsernameRequest`) | `email-validator` lib (RFC 5322 + length cap) | `phonenumbers.parse` + `is_valid_number` (E.164) |
| Pre-flight (sem rede) | — | `mx_check` (existe MX? domínio descartável?) | `carrier_lookup` (país, carrier, line_type) |
| Probe primário | HTTP GET no perfil | gravatar/mx/OathNet adapter no MVP; github_email só após gate | carrier_lookup/OathNet adapter no MVP; wa.me/t.me só após gate |
| Probe secundário (corroboração) | site-specific validator (8 plataformas) | forgot_pwd_* apenas lab/feature flag | forgot_pwd_apple apenas lab/feature flag |
| Baseline compare | username inválido aleatório | email inválido aleatório `nx-{rand}@{domain}` | phone inválido `+{country}0000000000` |
| Status final | `combine_outcomes` (signal weights) | **mesmo `combine_outcomes`** | **mesmo `combine_outcomes`** |
| Regra "found" forte | ≥2 signals positivos + score ≥85 | ≥2 signals positivos + score ≥85 | ≥2 signals positivos + score ≥85 |

### 4.3 Regras anti-FP universais (aplicar no `search_orchestrator`)
1. **Quórum mínimo:** `status=found` só se ≥2 conectores independentes retornaram `found` OU 1 conector com `confidence_score ≥90 + hard_positive`.
2. **Discordância:** se conectores divergem (1 found + 1 not_found), final = `uncertain` (não `found`).
3. **Bot/auth wall não conta como negativo:** `BLOCKED` ≠ `NOT_FOUND`. Conta como inconclusivo no agregado.
4. **Baseline obrigatório p/ conector novo:** sem baseline aprovado, conector roda em "shadow mode" (gera evidence mas não muda status final).
5. **Negative markers fortes:** ex.: "this account doesn't exist" em IG → hard_negative imediato.
6. **Rate-limit / 429 / 403:** `status=BLOCKED` + warning, nunca `NOT_FOUND`.

### 4.4 Métricas de validação (estender `cache.py::UsernameValidationMetrics`)
- `connector_runs_total{connector,status}`
- `connector_latency_ms_p50/p95/p99{connector}`
- `connector_block_rate{connector}`
- `connector_fp_rate{connector}` (estimado via baseline em CI)
- `agreement_rate{target_type}` (% buscas com ≥2 conectores em acordo)

---

## 5. Fluxo completo de uma busca

```
CLIENT                    API                       ORCHESTRATOR              CONNECTORS               STORE
  │                        │                              │                       │                       │
  │  POST /api/v2/search   │                              │                       │                       │
  │  {target:"+5511…"}     │                              │                       │                       │
  ├───────────────────────►│                              │                       │                       │
  │                        │ validate + detect type       │                       │                       │
  │                        │ create SearchJob (uuid)      │                       │                       │
  │                        ├─────────────────────────────────────────────────────────────────────────────►│
  │                        │                              │                       │  INSERT search_jobs   │
  │                        │ enqueue                      │                       │                       │
  │                        ├─────────────────────────────►│                       │                       │
  │  201 {job_id}          │                              │                       │                       │
  │◄───────────────────────┤                              │                       │                       │
  │                        │                              │                       │                       │
  │  GET …/events (SSE)    │                              │                       │                       │
  ├───────────────────────►│                              │                       │                       │
  │                        │ stream from search_events    │                       │                       │
  │                        │ (replay if reconnect)        │                       │                       │
  │                        │                              │                       │                       │
  │                        │                              │ resolve connectors    │                       │
  │                        │                              │ for target_type=phone │                       │
  │                        │                              │ → [carrier, oathnet   │                       │
  │                        │                              │    adapters, labs off]│                       │
  │                        │                              │                       │                       │
  │                        │                              │ orchestrator.submit(  │                       │
  │                        │                              │   each as task,       │                       │
  │                        │                              │   semaphore 5/3)      │                       │
  │                        │                              ├──────────────────────►│                       │
  │                        │                              │                       │ rate_limit.acquire    │
  │                        │                              │                       │ cache.get → miss      │
  │                        │                              │                       │ http GET (proxy?)     │
  │                        │                              │                       │ validators → score    │
  │                        │                              │                       │ ConnectorResult       │
  │                        │                              │◄──────────────────────┤                       │
  │                        │                              │ INSERT search_events  │
  │                        │                              ├─────────────────────────────────────────────►│
  │                        │ poll search_events           │                       │                       │
  │                        │ emit `event: connector`      │                       │                       │
  │  data: {connector:…}   │                              │                       │                       │
  │◄───────────────────────┤                              │                       │                       │
  │                        │                              │ all done → aggregate  │                       │
  │                        │                              │ apply quorum rules    │                       │
  │                        │                              │ UPDATE search_jobs    │                       │
  │                        │                              │   status=done         │                       │
  │                        │                              ├─────────────────────────────────────────────►│
  │                        │ emit `event: summary`        │                       │                       │
  │  data: {summary, conf} │                              │                       │                       │
  │◄───────────────────────┤                              │                       │                       │
  │                        │ close stream                 │                       │                       │
```

### 5.1 Eventos SSE (contrato)

| `event:` | payload | quando |
|---|---|---|
| `job_started` | `{job_id, target_type, target_hash, connectors_planned: [...]}` | imediato após enqueue |
| `connector_started` | `{connector, status:"running", started_at}` | antes do `run()` |
| `connector_result` | `ConnectorResult` (sanitizado) | quando connector termina |
| `connector_error` | `{connector, status:"error", error_type, message}` | exception capturada; mensagem genérica, sem alvo |
| `progress` | `{done, total, pct}` | a cada N resultados |
| `summary` | `{job_id, overall_status, overall_confidence, found_count, blocked_count, error_count, chained_jobs?: [...]}` | ao final |
| `chain_suggestion` | `{from_connector, suggested_target_type, suggested_value_hash}` | em v1, quando encontra `email` em breach do phone, etc. |
| `done` | `{elapsed_s}` | sempre por último |

**Regra de status:** `pending/running` aparecem em lifecycle; `found/not_found/likely/uncertain/blocked/error` aparecem em resultado. UI deve renderizar todos sem inventar thresholds.

---

## 6. Persistência e retorno de resultados

### 6.1 Schema novo (Alembic migration)

```sql
-- search_jobs: 1 linha por busca
CREATE TABLE search_jobs (
    id              UUID PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id),
    target_type     TEXT NOT NULL,           -- 'username' | 'email' | 'phone'
    target_hash     TEXT NOT NULL,           -- SHA-256[:12] do alvo normalizado
    target_encrypted BYTEA,                  -- só se JOB_ENCRYPT_TARGETS=1; nunca obrigatório no MVP
    status          TEXT NOT NULL,           -- 'queued' | 'running' | 'done' | 'failed' | 'cancelled'
    overall_status  TEXT,                    -- 'found' | 'not_found' | 'likely' | 'uncertain' | 'blocked' | 'error'
    overall_confidence INTEGER,              -- 0..100
    connectors_planned TEXT[],               -- ['gravatar', 'github_email', ...]
    connectors_run     TEXT[],
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    elapsed_ms      INTEGER,
    parent_job_id   UUID REFERENCES search_jobs(id),  -- chain
    expires_at      TIMESTAMPTZ NOT NULL              -- TTL — purgar por job batch
);
CREATE INDEX ix_search_jobs_user_id_created_at ON search_jobs(user_id, created_at DESC);
CREATE INDEX ix_search_jobs_expires_at ON search_jobs(expires_at);
CREATE INDEX ix_search_jobs_target_hash ON search_jobs(target_hash);

-- search_events: append-only — permite replay SSE
CREATE TABLE search_events (
    id          BIGSERIAL PRIMARY KEY,
    job_id      UUID NOT NULL REFERENCES search_jobs(id) ON DELETE CASCADE,
    seq         INTEGER NOT NULL,            -- ordem dentro do job
    event_type  TEXT NOT NULL,               -- 'connector_result' | 'progress' | 'summary' | ...
    payload     JSONB NOT NULL,              -- ConnectorResult sanitizado; sem target em claro
    emitted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (job_id, seq)
);
CREATE INDEX ix_search_events_job_id_seq ON search_events(job_id, seq);

-- connector_metrics: agregado horário p/ admin dashboard
CREATE TABLE connector_metrics (
    bucket_hour TIMESTAMPTZ NOT NULL,
    connector   TEXT NOT NULL,
    status      TEXT NOT NULL,
    runs        INTEGER NOT NULL DEFAULT 0,
    latency_ms_sum BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (bucket_hour, connector, status)
);
```

### 6.2 Retenção e privacidade
- `expires_at = created_at + JOB_MAX_AGE_DAYS` (default revisado: 7 dias no MVP; 30 dias só com payload criptografado e aprovação).
- Job batch cleanup via `tasks.py` (reusa padrão do `blacklist_purge_loop`).
- `target_encrypted` opcional (env flag `JOB_ENCRYPT_TARGETS=1`); chave em `.env`, nunca em DB. Hash sempre presente.
- `search_events.payload` deve ser sanitizado: sem `target_value`, sem raw response, sem email/phone completo quando não for indispensável para evidência.
- Se o produto exigir replay com dados sensíveis completos, payload deve ser criptografado antes de persistir. Não adiar essa decisão para depois da migration.
- Audit log mantém só hash + counts.

### 6.3 API de retorno
- `POST /api/v2/search` → `201 {job_id, sse_url}`. Síncrono apenas se `?wait=true&timeout=10s` (small searches).
- `GET /api/v2/search/{job_id}` → snapshot do `search_jobs` + summary.
- `GET /api/v2/search/{job_id}/events?from_seq=N` → SSE com replay desde `seq=N` (reconnect-friendly).
- `GET /api/v2/search/{job_id}/results` → snapshot final consolidado (após `done`).
- `DELETE /api/v2/search/{job_id}` → cancela job em execução (cooperativo via flag em registry).

---

## 7. Roadmap em fases

### MVP — "Contrato real-time + adapters seguros"

**Objetivo:** provar contrato `Connector` + persistência mínima de job + SSE com replay, sem abrir superfície legal nova.

**Branch:** `v4.1/realtime-osint-mvp` (após committar `.planning/*`).

| # | Tarefa | Aceitação |
|---|---|---|
| MVP-1 | Criar `modules/connectors/base.py` com schemas Pydantic v2 + enum `ConnectorStatus`. | `pytest tests/unit/connectors/test_base.py` verde. |
| MVP-2 | Criar `modules/connectors/runner.py` com `run_connector(req, conn, http)` aplicando timeout + rate limit + cache + audit log. | Teste com mock connector OK / timeout / blocked. |
| MVP-3 | Decisão de privacidade antes da migration: payload sanitizado/hash-only TTL 7d **ou** payload criptografado. | Decisão registrada em `.planning/PROJECT.md`; sem isso, parar. |
| MVP-4 | Migration Alembic `search_jobs` + `search_events` apenas. `connector_metrics` fica pós-MVP. | `alembic upgrade head` em Postgres efêmero e VPS staging. |
| MVP-5 | `api/services/job_store.py` — CRUD com `asyncpg.Pool` + `fetch_stream` p/ replay. | Integration test pickup/replay, sem `fetch_all` em events. |
| MVP-6 | Adapter `modules/connectors/username/sherlock_adapter.py` (envolve `search_username` existente, mapeia para `ConnectorResult`). | Smoke test E2E: search username retorna ≥1 ConnectorResult. |
| MVP-7 | Adapter OathNet legado → `ConnectorResult` para breach/stealer/victims sem mudar fonte. | Eventos sanitizados; quota/cache preservados. |
| MVP-8 | 1 conector email seguro: `gravatar.py` **ou** adiar se privacidade não aprovada. | Unit test com `respx` mockando 200/404; status máximo `likely` sem corroboração. |
| MVP-9 | 1 conector phone seguro: `carrier_lookup.py` (offline via `phonenumbers`). | Unit test cobre país, line_type. Não bate em rede. |
| MVP-10 | `api/routes/search_v2.py` + `api/services/search_orchestrator.py`. SSE replay funcionando. | E2E Playwright: search phone retorna `connector_result` event. |
| MVP-11 | Quórum + agregado `summary` event no orchestrator. | Unit test cobre 5 cenários (todos found, 1 found 1 not_found, todos blocked, etc.). |
| MVP-12 | Frontend mínimo: `connectors-render.js` consome `connector_result`; evidence drawer só com dados reais ou empty state. | Visual diff aprovado; sem Source Health falso. |
| MVP-13 | Documentar contrato em `docs/CONNECTORS.md` + exemplos. Atualizar `.planning/PROJECT.md`; `CLAUDE.md` só com aprovação explícita. | Math aprova doc. |

**Critérios de aceitação MVP:**
- Buscar `+5511999999999` retorna `carrier_lookup` (offline) + `summary` em <3s, sem declarar conta encontrada.
- Buscar `test@gmail.com` retorna `gravatar` apenas se gate de privacidade aprovado; caso contrário retorna validação/adapter seguro + `summary`.
- Buscar `username` retorna ≥10 `connector_result` events (sherlock + maigret adapters).
- Desconectar SSE no meio → reconectar com `?from_seq=N` retoma sem perda.
- Memory resting do container <500 MB.
- Zero regressão no endpoint legado `/api/search`.

---

### v1 — "Métricas reais + expansão controlada"

**Branch:** `v4.2/realtime-osint-v1`. Inicia após MVP em produção 7 dias sem incidente.

| # | Tarefa | Aceitação |
|---|---|---|
| v1-1 | `connector_metrics` + admin Source Health real. | Dados vêm de runs reais; block/error/latency batem com DB. |
| v1-2 | Cache TTL por conector configurável (config.py: `CACHE_TTL_{CONNECTOR_NAME}`). | Doc + smoke test. |
| v1-3 | Job reconnect/cancel UI no frontend (botão "Cancel" + indicador "reconnecting…"). | E2E Playwright. |
| v1-4 | Baseline CI: cada conector novo roda contra alvo controle. | Job falha se baseline gera `found`. |
| v1-5 | LGPD: endpoint `/api/v2/search/{job_id}` aceita `DELETE` que purga events + job (não só TTL). | E2E + audit log. |
| v1-6 | Conectores email seguros adicionais: `mx_check`, depois `github_email` se ToS aprovado. | Unit + baseline; shadow mode antes de afetar summary. |
| v1-7 | Conectores phone externos só após compliance gate (`whatsapp_qr`, `telegram_resolve`, `forgot_pwd_apple`). | Feature flag off por default + kill switch. |
| v1-8 | Workflow chaining gera `chain_suggestion` events quando encontra alvo enriquecido. | E2E com fluxo real documentado; sem usar carrier offline como prova de conta. |
| v1-9 | Export PDF do job. Reutilizar `modules/report_generator.py`; evitar visual "estilo OSINT Industries" copiado. | PDF abre, contém todos conectores e evidence. |
| v1-10 | Deprecar `/api/search` v1 só após `/api/v2/search` 7 dias em produção sem incidente. | Header presente, log emitido, rollback simples. |

**Critérios de aceitação v1:**
- ≥3 conectores email seguros rodando em produção com `block_rate < 30%` durante 7 dias.
- ≥1 conector phone offline + ≥1 fonte phone externa em shadow mode, se compliance aprovar.
- Quórum efetivo: `agreement_rate ≥ 70%` em alvos `found`.
- Chaining funciona em ≥1 fluxo documentado com evidência real, sem promover `likely` para `found`.
- Memory resting <600 MB.

---

### v2 — "Plataforma extensível"

**Branch série:** `v5.0/*`. Não iniciar sem refletir aprendizados de v1 em CLAUDE.md.

| # | Tarefa | Resumo |
|---|---|---|
| v2-1 | **Conector YAML-driven** — registrar novos sites sem código (template + validators auto). | Reduz custo de adicionar site de horas → minutos. |
| v2-2 | **Phone enrichment avançado**: HLR lookup (pago opcional), carrier portability check, country fraud risk score. | Camada de inteligência. |
| v2-3 | **Email enrichment**: SMTP probe deliverability, avatar dedup (gravatar vs LinkedIn), domain age. | Profundidade. |
| v2-4 | **Graph view** — UI: alvo no centro, conectores e chained jobs como relações auditáveis. | Inspirar-se em investigação visual, mas evitar copiar Maltego/OSINT Industries. |
| v2-5 | **Search templates** — sequências pré-definidas ("Investigate Discord user", "Phone forensics"). | UX. |
| v2-6 | **WebSocket alternativo** ao SSE para bi-directional (cancel mid-job, dynamic refine). | Substitui polling de cancel. |
| v2-7 | **Connector marketplace** — instalar conector via repo Git (sandbox subprocess + manifesto assinado). | Plataforma. |
| v2-8 | **Multi-tenancy** — namespaces de busca por organização, billing per connector run. | Comercial. |
| v2-9 | **Workflow DSL** — JSON pipeline: `if found(phone) then run(email_via_breach) chain to username`. | Power user. |
| v2-10 | **Webhook out** — notificar URL externa quando job termina (Zapier/n8n). | Integração. |

---

## 8. Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| **Forgot-password probing** banido pelas plataformas (Twitter/IG/Google atualizam endpoints) | Alta | Alto | Fora do MVP/v1 default. Lab-only com revisão ToS/legal, baseline CI, feature flag backend e kill switch. |
| **Truecaller scraping é juridicamente cinza** | Média | Alto (legal) | Remover do roadmap default. Só reabrir com aprovação legal explícita e fonte autorizada. |
| **Banimento de IP do VPS** por probing agressivo | Média | Médio | Reusar `ThordataProxy` para email/phone também (não só username). Rate limit out por domínio sempre ativo. |
| **Job table cresce sem limite** | Média | Médio | TTL hard 30 dias + cleanup loop + `VACUUM` agendado via `pg_cron` ou cron externo. |
| **LGPD: armazenar email/phone em claro em `search_events.payload`** | Alta | Alto | Gate bloqueante antes da migration: payload sanitizado/hash-only TTL 7d ou criptografia. Sem decisão, sem MVP-4. |
| **Falso positivo viraliza** (cliente acredita em `found` errado) | Média | Alto | Quórum ≥2 + status `uncertain` por default em discordância + UI mostra evidence drawer sempre. |
| **Memória explode com job persistente** | Baixa | Médio | Replay via cursor `fetch_stream` (já existe em `DatabaseManager`), nunca `fetch_all` em events. |
| **SSE longo segura conexão e watchdog pausa orchestrator** | Baixa | Médio | Job execution desacoplado do SSE (worker independente); SSE só lê events. |
| **OathNet vira dependência crítica para email** | Já é | Médio | MVP cria adapter e adiciona só fontes seguras; forgot_pwd/HIBP não são fallback default sem compliance. |

---

## 9. Pontos abertos — decisão Math obrigatória antes do MVP-1

1. **Persistência de dados sensíveis em `search_events.payload`**: payload sanitizado/hash-only + TTL 7d **OU** ChaCha20Poly1305 + TTL maior? Decisão bloqueia MVP-4.
2. **Reusar Thordata para email/phone**: aumenta consumo da quota (1 GB/dia). OK ou orçar proxy separado?
3. **Truecaller conector**: recomendação Codex = descartar do roadmap default. Reabrir só com aprovação legal.
4. **HIBP API**: comprar key e revisar ToS/disclosure **OU** manter fora. Não substituir por forgot-pwd como fallback default.
5. **`/api/search` v1**: manter até `/api/v2/search` ficar 7 dias estável em produção. Deprecação só depois.
6. **Quórum mínimo para `found`**: ≥2 conectores independentes **OU** 1 conector com score ≥90 + `hard_positive`. `likely` permanece status separado.
7. **Gravatar privacy**: permitir MD5 de email para terceiro no MVP **OU** adiar `gravatar` e começar só com adapter/OathNet/mx/carrier.

---

## 10. Definition of Done agregada (todas as fases)

- [ ] Zero `except Exception` genérico em código novo (CLAUDE.md regra).
- [ ] Todo conector com timeout explícito + rate limit + cache + audit log SHA-256.
- [ ] Zero target em claro em logs estruturados.
- [ ] Zero lógica de autorização no frontend (CLAUDE.md regra 3).
- [ ] Nenhum conector lab/risky habilitado sem revisão legal/ToS, feature flag backend e kill switch.
- [ ] `ConnectorStatus` 8-state preservado end-to-end; frontend não converte `likely` em `found`.
- [ ] Docker image continua <250 MB após novas deps.
- [ ] Memory resting <600 MB com job store ativo.
- [ ] Test suite verde: unit ≥80%, integration ≥60%, E2E cobre `realtime-search.spec.ts`.
- [ ] Rollback documentado por fase (revert do merge commit do feature).
- [ ] `docs/CONNECTORS.md` + `.planning/PROJECT.md` atualizados; `CLAUDE.md` só com aprovação explícita.
- [ ] Conferência manual: SSE reconnect, cancel, summary, evidence drawer.

---

**Fim do plano. Próximo passo:** Math responde os 7 pontos abertos da seção 9. Depois abrir branch `v4.1/realtime-osint-mvp` e executar MVP-1 a MVP-3. MVP-4 só começa após decisão de privacidade.
