---
phase: 15
slug: refactor-main-py-layers
status: DECIDED
created: "2026-04-19"
milestone: v4.1
discuss_mode: discuss
---

# Phase 15 — Refactor main.py into Layered Architecture

## Objetivo

Separar `api/main.py` (1770 linhas, monolítico) em arquitetura 3-tier pragmática:
**routes (HTTP) → services (regras) → módulos existentes (db, orchestrator, watchdog, modules/clients)**.

Zero breaking changes. Cada camada extraída por vez (horizontal slice). Suite de testes (62/62) verde como gate entre passos.

## Motivação

- main.py concentra rotas, regras de negócio, middleware, admin, auth em um único arquivo
- Qualquer falha afeta o sistema inteiro (sem isolamento)
- Stack traces longos, debug difícil
- Impossível testar camada de regra sem subir HTTP
- Concerns já registra "Backend Monolith: api/main.py is 1262 Lines [HIGH]" em `.planning/codebase/CONCERNS.md`

## Decisões Travadas

### D-01 — Padrão arquitetural: **3-tier pragmático**

Estrutura final:

```
api/
 ├── main.py             # app factory + lifespan + router mounting
 ├── config.py           # env vars + constants (extraído de main.py)
 ├── db.py               # (EXISTE) DatabaseManager
 ├── orchestrator.py     # (EXISTE) AgentOrchestrator
 ├── watchdog.py         # (EXISTE) memory/CPU health
 ├── deps.py             # get_current_user, get_db, get_orchestrator, etc
 ├── schemas.py          # TODOS os Pydantic I/O models
 ├── routes/
 │    ├── __init__.py
 │    ├── auth.py        # /api/login, /api/logout, /api/me
 │    ├── search.py      # /api/search (SSE), /api/search/* queries
 │    ├── admin.py       # /api/admin/*
 │    └── health.py      # /health, /ready
 └── services/
      ├── __init__.py
      ├── auth_service.py
      ├── search_service.py
      └── admin_service.py

modules/                 # (EXISTE, INTOCADO) OSINT clients
 ├── oathnet_client.py
 ├── sherlock_wrapper.py
 ├── spiderfoot_wrapper.py
 └── report_generator.py
```

**Rationale:**
- 3-tier > 5-layer clean/hexagonal: repo é pequeno, API tem ~4 domínios. Camada de repository adicional seria overhead sem ganho.
- `api/` mantém tudo junto. `modules/` permanece como "SDKs externos" (PADRÃO FastAPI ecosystem).

### D-02 — Tratamento de `modules/`: **intocado**

`modules/` permanece como está. Phase 11 estabilizou `httpx.AsyncClient` singleton + lifecycle. Qualquer mudança arrisca regredir. Services importam de `modules/` diretamente.

**Regra:** `api/services/*.py` pode importar de `modules/*`. `api/routes/*.py` **não** importa de `modules/` — só via services.

**Rationale:** Zero custo de regressão em trabalho já estabilizado. Viola 3-tier puro (infra fora do pacote), mas é aceito conscientemente.

### D-03 — Estratégia de migração: **horizontal slice (por camada)**

Ordem de extração (cada passo = 1 commit atômico + smoke test):

| Passo | Ação | Risco |
|-------|------|-------|
| 1 | Extrair `schemas.py` (todos Pydantic models) | BAIXO — sem dependência de estado |
| 2 | Extrair `deps.py` (get_current_user, get_db, etc) | BAIXO — função getter sobre `request.app.state` |
| 3 | Criar `services/*.py` (TODOS os serviços em bloco) | ALTO — concentra lógica de negócio |
| 4 | Criar `routes/*.py` (TODAS as rotas em bloco) | ALTO — remove de main.py |
| 5 | `main.py` vira app factory + lifespan + `include_router()` | MÉDIO — teste integração crítico |

**Objeção técnica registrada (CLAUDE.md regra 5):** Passos 3 e 4 concentram risco por movimentação em bloco. Mitigação: smoke test entre passos (pytest + subir container local + 2 curls manuais em rota representativa).

**Rationale:** Camadas ficam coerentes rápido — planner gera 5 PLAN.md claros, 1 por passo.

### D-04 — Testes: **reorg + sem adicionar novos**

Reorganizar `tests/` flat atual para:

```
tests/
 ├── unit/
 │    ├── test_schemas.py
 │    └── test_services/*.py
 ├── integration/
 │    └── test_*_routes.py
 └── e2e/
      └── test_search_flow.py
```

**Regras:**
- 62/62 testes existentes permanecem verdes como gate entre passos
- Nenhum teste novo adicionado durante Phase 15 (foco no refactor)
- Imports dos testes adaptados a cada passo
- Gaps de cobertura em services/ ficam para fase futura (não bloqueiam Phase 15)

**Rationale:** Não misturar objetivos (refactor vs aumento de cobertura). CLAUDE.md já documenta estrutura `tests/{unit,integration,e2e}` como padrão.

### D-05 — Acesso a estado global: **Depends() em routes + parâmetro em services**

**Padrão canônico FastAPI:**

```python
# api/deps.py
def get_db(request: Request) -> DatabaseManager:
    return request.app.state.db

def get_orchestrator(request: Request) -> AgentOrchestrator:
    return request.app.state.orchestrator

# api/routes/search.py
@router.post("/search")
async def search(
    payload: SearchIn,
    db: DatabaseManager = Depends(get_db),
    orch: AgentOrchestrator = Depends(get_orchestrator),
):
    return await search_service.run(payload, db, orch)

# api/services/search_service.py — assinatura explícita, zero dependência de Request
async def run(payload: SearchIn, db: DatabaseManager, orch: AgentOrchestrator) -> SearchOut:
    ...
```

**Regras derivadas:**
- Services **nunca** recebem `Request` — apenas tipos de domínio (db, orch, payload, etc)
- Services podem chamar outros services passando os mesmos args
- Testes unit de service: mock direto dos args (sem FastAPI)
- Testes integration: `app.dependency_overrides[get_db] = lambda: fake_db`

**Rationale:** Testabilidade máxima, reuso fora de HTTP, zero acoplamento de service a FastAPI.

## Contrato de Imports Entre Camadas (derivado das decisões)

| De → Para | Permitido? | Notas |
|-----------|-----------|-------|
| `routes/*` → `services/*` | SIM | Orquestração HTTP chama lógica |
| `routes/*` → `schemas` | SIM | Pydantic models |
| `routes/*` → `deps` | SIM | Depends() providers |
| `routes/*` → `modules/` | **NÃO** | Só via service |
| `routes/*` → `routes/*` | NÃO | Routes não se conhecem |
| `services/*` → `modules/` | SIM | Clientes externos |
| `services/*` → `db.py`, `orchestrator.py` | SIM | Via parâmetro (não import de estado) |
| `services/*` → `schemas` | SIM | Retorno/entrada |
| `services/*` → `services/*` | SIM | Composição de serviços |
| `services/*` → `routes/*` | **NÃO** | Dependência invertida — proibido |
| `deps.py` → `db.py`, `orchestrator.py` | SIM | Getter reads app.state |
| `deps.py` → `services/*` | NÃO | Deps só fornecem infra |
| `schemas.py` → qualquer outro | NÃO | Schemas são folha da árvore |

## Out-of-Scope (Phase 15 NÃO faz)

- Aumento de cobertura de testes (gap documentado, vira fase futura)
- Reescrita de `modules/` clients (Phase 11 já estabilizou)
- Mudança no DatabaseManager, AgentOrchestrator, Watchdog (já modulares)
- Migração para ORM (SQLite raw permanece)
- Feature flags ou strangler-wrap (CLAUDE.md proíbe)
- Python version upgrade (isso é F6 em outra milestone)
- Qualquer mudança comportamental — só reestruturação

## Definition of Done (por passo)

Cada passo de 1-5 só merge se:
1. `pytest` retorna exit code 0 (suite 62/62 verde)
2. `docker compose build` sucesso
3. `docker compose up` sobe em < 15s
4. `curl /health` retorna 200
5. Smoke test manual: 1 login + 1 search bem-sucedidos
6. `grep -n "from api.main import" .` deve diminuir monotonicamente

## Gate de Entrada para Phase 15

- [ ] Phase 14 (visual-polish) completa e merged em `main`
- [ ] Branch `v4.1/f15-refactor-main-py-layers` criada a partir de `main`
- [ ] `.planning/codebase/STRUCTURE.md` atualizado (via `/gsd:map-codebase`)
- [ ] Suite baseline verde: `pytest -q` = 62/62

## Input para Planner

Planner deve produzir **5 PLAN.md files**, um por passo de D-03. Cada plan contém:
- `read_first`: arquivos a estudar antes
- Ações concretas (criar arquivo X, mover função Y, etc)
- Grep commands verificáveis (ex: `grep -c "class SearchIn" api/schemas.py` = 1)
- Smoke test específico para aquele passo
- Definition of Done conforme lista acima

Planner NÃO precisa:
- Discutir padrão arquitetural (locked D-01)
- Mexer em `modules/` (locked D-02)
- Inventar ordem de migração (locked D-03)
- Adicionar novos testes (locked D-04)
- Propor DI pattern (locked D-05)

## Session Log

**Discussão conduzida:** 2026-04-19 (Opus session)
**Gray areas exploradas:** 5 (padrão, modules/, migração, testes, app.state)
**Gray areas residuais:** Nenhuma — usuário fechou discussão
**Próximo passo:** `/gsd:map-codebase` → `/gsd:plan-phase 15 --skip-research`
