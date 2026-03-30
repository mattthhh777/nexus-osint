# NexusOSINT — CLAUDE.md
# Milestone v4.0: Low-Resource Agent Architecture & Hardening
# Stack: FastAPI + Vanilla JS + SQLite + Docker | VPS: 1vCPU / 1GB RAM

---

## MODELO POR PAPEL (OBRIGATORIO)

| Papel | Modelo | Quando usar |
|---|---|---|
| **Planejamento / Arquitetura / Decisoes tecnicas** | `claude-opus-4-5` | Antes de qualquer codigo novo, design de sistema, analise de trade-offs, decisoes que afetam multiplos arquivos |
| **Implementacao / Codigo / Testes / Refactor** | `claude-sonnet-4-5` | Escrita de codigo, execucao de comandos, testes, iteracoes rapidas |
| **Revisao rapida / Diagnostico** | `claude-sonnet-4-5` | Leitura de logs, checagem de outputs, respostas curtas |

**Regra**: Opus planeja. Sonnet executa. Nunca inverter.
Se a tarefa nao tiver plano aprovado → pare e planeje com Opus primeiro.

---

## FERRAMENTAS INSTALADAS — USO OBRIGATORIO

### GSD (Get Shit Done) — Orquestracao de Milestone
```
/gsd:new-project     → Iniciar novo sub-projeto ou feature branch
/gsd:execute-phase   → Executar fase do plano (use apos Opus planejar)
/gsd:next            → Avancar para proxima tarefa na fila
/gsd:status          → Ver estado atual do milestone
/gsd:checkpoint      → Salvar progresso antes de mudancas arriscadas
```
**Regra**: toda feature do v4.0 comeca com `/gsd:execute-phase` e termina com `/gsd:checkpoint`.

### claude-mem — Memoria Persistente
```
mem-search           → Buscar decisoes tecnicas de sessoes anteriores
make-plan            → Gerar plano com contexto historico do projeto
smart-explore        → Explorar codebase com memoria de contexto
timeline-report      → Ver historico de progresso do milestone
do                   → Executar tarefa com memoria ativa
```
**Regra**: no inicio de cada sessao, rodar `mem-search "NexusOSINT v4.0"` para restaurar contexto.
Antes de decisoes arquiteturais, rodar `timeline-report` para nao contradizer decisoes anteriores.

### Magic MCP (21st.dev) — Componentes UI
**Quando usar**: qualquer mudanca no frontend Vanilla JS (dashboard, health monitor UI, novas views).
**Nao usar para**: logica backend, SQLite, async agents — esse nao e o dominio dele.

### ui-ux-pro-max — Design System
**Quando usar**: criacao ou alteracao de componentes visuais do NexusOSINT.
**Constraint obrigatorio**: preservar identidade Amber/Noir. Nenhuma mudanca de cor sem aprovacao explicita.
Skills relevantes para v4.0: `ui-styling`, `design-system`, `banner-design`.

### n8n-mcp — Workflows de Automacao
**Quando usar**: se o milestone exigir integracao com pipelines externos, webhooks ou automacao de tarefas de OSINT recorrentes.
**Para v4.0 especificamente**: avaliar uso para o health watchdog (Feature #8) — alertas automaticos quando memoria > threshold.

### Obsidian Skills — Documentacao
```
obsidian-markdown     → Gerar documentacao tecnica do milestone
timeline-report       → Exportar progresso para vault de projetos
```
**Regra**: toda decisao arquitetural relevante deve ser documentada via `obsidian-markdown` ao final da sessao.

---

## CONTEXTO TECNICO DO PROJETO

### Stack (imutavel)
```
Backend:   FastAPI (Python 3.12+)
Frontend:  Vanilla JS (sem frameworks)
Database:  SQLite com WAL mode + serializacao via asyncio.Queue
Container: Docker multi-stage, target <250MB (realista), deploy em DO VPS
```

### Hardware Constraints (nao-negociaveis)
```
VPS:         DigitalOcean 1vCPU / 1GB RAM / 25GB SSD
RAM target:  < 200MB resting footprint
Swap:        2GB obrigatorio (configurar antes de qualquer deploy)
Concurrency: asyncio.Semaphore(max=5) — teto absoluto de tasks simultaneas
Docker:      < 250MB (meta realista com Python 3.12-slim)
```

### Identidade Visual (protegida)
```
Brand:       Amber/Noir — nenhuma mudanca sem aprovacao explicita
CSS:         Sistema Meridian (milestone anterior — 16/16 completo)
XSS:         Corrigido no milestone anterior — nao regredir
```

---

## FEATURES DO MILESTONE v4.0

Execute nesta ordem — cada feature e gate para a proxima:

### F1 — Codebase Audit (GATE: deve completar antes das demais)
**Objetivo**: detectar memory leaks, zombie processes, unsafe patterns, avaliar mudancas manuais de seguranca.
**Entregavel**: relatorio de auditoria com severidade (CRIT/HIGH/MED/LOW) antes de qualquer codigo novo.
**Ferramenta**: `smart-explore` (claude-mem) para mapear codebase + `timeline-report` para contexto historico.

### F2 — SQLite Hardening
**Objetivo**: eliminar "database is locked" sob carga de agents.
**Arquitetura correta** (Opus deve validar antes de implementar):
```python
# CORRETO: single connection + WAL + write serialization via Queue
# ERRADO: "connection pooling" SQLite — nao existe e piora o problema
```
- WAL mode: `PRAGMA journal_mode=WAL`
- Serializacao: `asyncio.Queue` para writes + single `aiosqlite` connection
- Read: multiplos readers OK com WAL (nao bloqueiam writes)

### F3 — Async Agent Orchestration (Lite)
**Objetivo**: micro-tasks controlados por semaphore (credential leak checker, geo-metadata, social scrapers).
**Arquitetura correta** (Opus valida):
```python
# CORRETO: TaskGroup (Python 3.11+) + Semaphore + task registry
# ERRADO: asyncio.create_task() fire-and-forget sem registry = OOM garantido
async with asyncio.TaskGroup() as tg:
    task = tg.create_task(agent_coro())
# TaskGroup cancela tudo se uma task falhar — sem orphans
```
- Semaphore ceiling: `asyncio.Semaphore(5)` — teto absoluto
- Task registry: dict de tasks ativas para monitorar e cancelar
- Backpressure: se semaphore cheio → queue de espera, nao drop silencioso

### F4 — Memory-Disciplined Architecture
**Objetivo**: < 200MB resting, zero bulk collections em memoria.
- Generators/async generators para todo pipeline de dados
- `sys.getsizeof()` + `tracemalloc` em dev para medir antes/depois
- Streaming de resultados SQLite (nao `.fetchall()`)
- Limitar tamanho de cache em memoria com `maxsize` em LRU caches

### F5 — Docker Optimization
**Objetivo**: multi-stage build, swap configurado, OOM-resistant.
```dockerfile
# Stage 1: build (pode ser pesado)
FROM python:3.12-slim AS builder
# Stage 2: runtime (somente o necessario)
FROM python:3.12-slim AS runtime
# Usar digest fixo — nunca :latest
# Exemplo: FROM python:3.12-slim@sha256:<digest>
```
- `deploy.resources.limits.memory: 800m` no compose (deixar 200MB para SO)
- `--memory-swap: 2800m` (RAM + swap)
- Health check obrigatorio no compose

### F6 — Stack Modernization
**Objetivo**: Python 3.12 + proxy rotation + OathNet optimization.
**Gate**: inventario de dependencias → test suite verde → bump de versao.
**ATENCAO**: Nao executar sem test suite passando — Python 3.12 pode quebrar dependencias.

### F7 — Security Hardening
**Objetivo**: CSP headers, JWT httpOnly migration, rate limiting evolution, input validation.
- CSP: nao usar `unsafe-inline` — se quebrar o frontend, corrigir o frontend
- JWT httpOnly: migracao requer invalidacao de tokens existentes — planejar janela de manutencao
- Rate limiting: `slowapi` (FastAPI-native) com limites por endpoint, nao global

### F8 — Health Monitoring
**Objetivo**: watchdog de memoria/CPU + graceful degradation.
```python
# psutil para metricas + threshold-based task pausing
import psutil
if psutil.virtual_memory().percent > 85:
    # Pausar novos agents, nao derrubar os existentes
    await semaphore_guard.pause_new_tasks()
```
- Endpoint `/health` com metricas reais (nao so HTTP 200)
- Graceful degradation: reduzir concurrency ceiling automaticamente sob pressao
- Avaliar n8n-mcp para alertas externos quando RAM > 85%

---

## REGRAS DE PROTECAO DE ARQUIVOS

Os seguintes arquivos NAO podem ser modificados sem aprovacao explicita:

```
CLAUDE.md              → este arquivo
.env / .env.production → segredos — nunca logar, nunca commitar
meridian.css           → sistema visual Amber/Noir (milestone anterior)
docker-compose.prod.yml → configuracao de producao
```

Qualquer mudanca nesses arquivos requer:
1. Justificativa tecnica explicita
2. Checkpoint GSD salvo antes da mudanca
3. Confirmacao do usuario

---

## WORKFLOW DE SESSAO (seguir sempre)

```
INICIO DE SESSAO:
1. mem-search "NexusOSINT v4.0" → restaurar contexto
2. timeline-report → ver onde parou
3. /gsd:status → ver feature ativa

ANTES DE NOVO CODIGO:
4. Opus planeja → diagrama ASCII + trade-offs + edge cases
5. Usuario aprova o plano
6. /gsd:execute-phase → Sonnet implementa

DURANTE IMPLEMENTACAO:
7. Sonnet: codigo completo, type hints, testes, sem pseudo-codigo
8. Se surgir decisao arquitetural → PARAR, voltar ao Opus

FIM DE SESSAO:
9. /gsd:checkpoint → salvar progresso
10. obsidian-markdown → documentar decisoes tecnicas da sessao
11. mem-search salva contexto automaticamente
```

---

## REGRAS DE OURO

| Regra | Status |
|---|---|
| Opus planeja, Sonnet implementa — nunca inverter | OBRIGATORIO |
| F1 (Audit) completa antes de qualquer codigo novo | OBRIGATORIO |
| SQLite: asyncio.Queue + single connection — nao "pooling" | OBRIGATORIO |
| Async agents: TaskGroup + registry — nao create_task fire-and-forget | OBRIGATORIO |
| Semaphore ceiling: maximo 5 tasks simultaneas | OBRIGATORIO |
| Docker target: <250MB (nao <150MB) | OBRIGATORIO |
| Brand Amber/Noir: nenhuma mudanca sem aprovacao | OBRIGATORIO |
| Sem pseudo-codigo, sem placeholders, sem "# seu codigo aqui" | PROIBIDO |
| Sem `except Exception` generico | PROIBIDO |
| Sem segredos hardcoded | PROIBIDO |
| Sem `.fetchall()` em queries grandes — usar streaming | PROIBIDO |
| Sem `asyncio.create_task()` sem task registry | PROIBIDO |
| Python 3.12 upgrade sem test suite verde | PROIBIDO |

---

## REFERENCIAS RAPIDAS

```
Async agents:        asyncio.TaskGroup (PEP 654, Python 3.11+)
SQLite async:        aiosqlite + WAL mode
Memory profiling:    tracemalloc + psutil
Rate limiting:       slowapi (FastAPI)
HTTP client:         httpx.AsyncClient (nunca requests sincrono)
Logging:             loguru (estruturado, nunca dados sensiveis)
Testes async:        pytest-asyncio + respx (mock httpx)
Docker multi-stage:  python:3.12-slim com digest fixo
VPS swap:            fallocate -l 2G /swapfile
```

---

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.

---

## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
