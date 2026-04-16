# NexusOSINT — CLAUDE.md
# Milestone v4.0: Low-Resource Agent Architecture & Hardening
# Stack: FastAPI + Vanilla JS + SQLite + Docker | VPS: 1vCPU / 1GB RAM

---

## FILOSOFIA CENTRAL (LER ANTES DE TUDO)

Estas regras têm precedência absoluta sobre qualquer outra instrução neste arquivo.

### 1. HONESTIDADE NÃO É OPCIONAL

Claude não concorda com decisões técnicas ruins por educação ou para reduzir atrito.
Se o plano ou o código estiver errado, Claude diz que está errado, justifica tecnicamente, e propõe alternativa concreta.
Esse comportamento não é negociável e não é suspenso por "Continuar" (ver regra 5).

### 2. CRIAR, NÃO COPIAR

Referências, docs e padrões da indústria são ponto de partida — nunca destino.
O código produzido para NexusOSINT deve ser adaptado ao contexto exato: stack, constraints de RAM, identidade visual, threat model.
Se a solução "padrão" for inadequada para este contexto → Claude propõe alternativa e justifica.

### 3. NUNCA CONFIE NO FRONTEND

O frontend é território hostil por definição. Todo dado que chega via JS, form, query param ou header é não-confiável.
Validação, sanitização, autorização e toda regra de negócio vivem **exclusivamente no backend (FastAPI)**.
O frontend Vanilla JS existe para exibir e coletar — nunca para decidir.
Sem exceções. Sem "mas é só um painel interno".

### 4. AUTONOMIA TÉCNICA — CLAUDE AGE SEM SER INSTRUÍDO

Math opera via vibe coding com AI como ferramenta principal. Claude tem responsabilidade expandida:

| Domínio | Comportamento padrão de Claude |
|---|---|
| Segurança | Implementa defesas proativamente. Não espera pedido. |
| Performance/memória | Aplica streaming, generators, limites — por default. |
| Qualidade | Recusa pseudo-código, placeholders e TODOs sem implementação. |
| Regressão | Sinaliza quando mudança nova quebra garantia anterior. |
| Problemas fora do escopo | Documenta e sinaliza — não silencia. |

### 5. REGRA DO "CONTINUAR" — SEM AMBIGUIDADE

"Continuar" avança para a próxima tarefa no plano vigente.
"Continuar" **não** cancela uma objeção técnica já levantada por Claude.
Se Claude identificou um problema e Math diz "Continuar" sem resolver o problema:
→ Claude re-enuncia o risco em uma linha, registra no plano, e então avança.
O risco não desaparece por ser ignorado — fica documentado.

---

## MODELO POR PAPEL

> **LIMITAÇÃO REAL — LER COM ATENÇÃO**: Nenhuma variante do Claude sabe qual modelo ela é em runtime.
> A regra abaixo é uma **convenção operacional que o usuário deve aplicar** abrindo sessões separadas conscientemente.
> Não é uma garantia técnica automática — é um protocolo de trabalho.

| Papel | Modelo (API string) | Quando usar |
|---|---|---|
| **Planejamento / Arquitetura / Decisões técnicas** | `claude-opus-4-6` | Antes de qualquer código novo, design de sistema, análise de trade-offs |
| **Implementação / Código / Testes / Refactor** | `claude-sonnet-4-6` | Escrita de código, execução de comandos, testes, iterações rápidas |
| **Revisão rápida / Diagnóstico** | `claude-sonnet-4-6` | Leitura de logs, checagem de outputs |

**Protocolo do usuário**: abrir sessão de planejamento com Opus → aprovar plano → abrir sessão de implementação com Sonnet.
Se plano não estiver aprovado → sem código novo.
Se Sonnet encontrar decisão arquitetural durante implementação → parar, escalar para sessão Opus.

---

## FERRAMENTAS MCP — USO E FALLBACK

### GSD (Get Shit Done)
```
/gsd:execute-phase   → Executar fase do plano (pós-aprovação Opus)
/gsd:next            → Avançar para próxima tarefa
/gsd:status          → Estado atual do milestone
/gsd:checkpoint      → Salvar progresso antes de mudanças arriscadas
/gsd:quick           → Fixes pequenos, docs, tarefas ad-hoc
/gsd:debug           → Investigação e bug fixing
```

**Fallback se GSD indisponível**: registrar progresso no início do prompt:
```
[SESSÃO MANUAL] Feature ativa: F{N} | Última tarefa: {descrição} | Pendente: {próxima}
```

### claude-mem
```
mem-search "NexusOSINT v4.0"   → início de sessão obrigatório
timeline-report                  → antes de decisões arquiteturais
```

**Fallback se claude-mem indisponível**: iniciar sessão com resumo explícito de contexto no prompt.
Não pular a etapa — sem contexto, sem código.

### Magic MCP (21st.dev)
**Escopo**: mudanças no frontend Vanilla JS.
**Regra**: output do Magic MCP é ponto de partida — adaptar ao design system Amber/Noir antes de aceitar.
**Fallback**: implementar componente manualmente seguindo meridian.css.

### n8n-mcp
**Decisão**: **fora do escopo do v4.0.**
Motivo: adiciona dependência externa e complexidade operacional sem necessidade imediata.
Health watchdog (F8) usa alertas internos via FastAPI + psutil. Revisitar em v5.0.

### Obsidian Skills
```
obsidian-markdown   → documentação de decisões ao final de cada sessão
```
**Fallback**: documentar decisão em comentário no topo do arquivo modificado + registrar em PROJECT.md.

---

## CONTEXTO TÉCNICO DO PROJETO

### Stack (imutável)
```
Backend:   FastAPI (Python 3.12+)
Frontend:  Vanilla JS — nunca fonte de verdade para lógica de negócio
Database:  SQLite com WAL mode + serialização via asyncio.Queue
Container: Docker multi-stage, target <250MB, deploy em DO VPS
```

### Hardware Constraints (não-negociáveis)
```
VPS:               DigitalOcean 1vCPU / 1GB RAM / 25GB SSD
RAM resting:       < 200MB
RAM alerta:        > 400MB → investigar ativamente (possível leak crescendo)
RAM limite Docker: 800m (deixar ~200MB para SO)
RAM swap total:    2800m (800m RAM + 2GB swap)
Swap:              2GB obrigatório — configurar antes de qualquer deploy
Concurrency:       asyncio.Semaphore(max=5) — teto absoluto
Docker image:      < 250MB
SQLite readers:    máximo 3 conexões de leitura simultâneas com WAL
                   (acima disso, pressão no VPS 1GB se torna mensurável)
```

### Identidade Visual (protegida)
```
Brand:  Amber/Noir — nenhuma mudança sem aprovação explícita
CSS:    Sistema Meridian (milestone anterior — 16/16 completo)
XSS:    Corrigido no milestone anterior — não regredir
```

---

## PADRÃO DE EXCEPTION HANDLING (obrigatório em todo código novo)

`except Exception` genérico é proibido. Padrão correto por camada:

```python
# ── FastAPI endpoint ────────────────────────────────────────────────────────
@router.get("/scan/{target}")
async def run_scan(target: str):
    try:
        result = await orchestrator.run(target)
        return result
    except ValueError as e:
        # Input inválido — 400, sem stack trace no log
        raise HTTPException(status_code=400, detail=str(e))
    except asyncio.TimeoutError:
        # Agente travou — 504, logar sem dados do alvo
        logger.warning("Scan timeout | target_hash={}", hash(target))
        raise HTTPException(status_code=504, detail="Scan timed out")
    except aiosqlite.Error as e:
        # Falha de DB — 503
        logger.error("DB error during scan: {}", type(e).__name__)
        raise HTTPException(status_code=503, detail="Database unavailable")
    except Exception as e:
        # Inesperado — 500, logar completo para debug, nunca expor ao cliente
        logger.exception("Unhandled error in scan endpoint")
        raise HTTPException(status_code=500, detail="Internal error")

# ── Agente async (dentro do TaskGroup) ─────────────────────────────────────
async def agent_coro(target: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"https://api.example.com/{target}")
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        logger.warning("Agent timeout | target_hash={}", hash(target))
        return {"status": "timeout", "data": None}
    except httpx.HTTPStatusError as e:
        logger.warning("Agent HTTP {} | target_hash={}", e.response.status_code, hash(target))
        return {"status": "http_error", "code": e.response.status_code, "data": None}
    # NÃO capturar Exception genérico em agentes
    # Deixar propagar para TaskGroup — cancela todas as tasks, erro sobe com contexto
```

**Regras derivadas**:
- Em agentes async: não capturar `Exception` — deixar TaskGroup gerenciar cancelamento
- Em endpoints: sempre converter para `HTTPException` com status correto
- Nunca expor detalhes da exceção ao cliente — apenas ao log interno
- Nunca logar dados que identifiquem o alvo — usar hash

---

## RATE LIMITING — ENTRADA E SAÍDA

### Entrada (requests para a API do NexusOSINT)
- `slowapi` com limites por endpoint e por usuário autenticado
- Endpoints de scan: teto menor que endpoints de leitura

### Saída (requests dos agentes OSINT para APIs externas)
O problema mais frequente em produção para plataformas OSINT — e o mais ignorado.

```python
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta

class OutboundRateLimiter:
    """Token bucket por domínio — evita ban de IP em APIs externas."""

    def __init__(self, calls_per_second: float = 1.0):
        self._semaphores: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(1)
        )
        self._last_call: dict[str, datetime] = {}
        self._min_interval = timedelta(seconds=1.0 / calls_per_second)

    async def acquire(self, domain: str) -> None:
        async with self._semaphores[domain]:
            if domain in self._last_call:
                elapsed = datetime.now() - self._last_call[domain]
                if elapsed < self._min_interval:
                    await asyncio.sleep((self._min_interval - elapsed).total_seconds())
            self._last_call[domain] = datetime.now()

# Instância global — compartilhada entre todos os agentes
outbound_limiter = OutboundRateLimiter(calls_per_second=2.0)
```

**Limites recomendados por tipo**:
- APIs públicas sem autenticação: 1 req/s por domínio
- APIs com key (Shodan, VirusTotal, etc): 50% do limite documentado da API
- Scrapers HTML: 0.5 req/s por domínio + User-Agent rotativo

---

## FEATURES DO MILESTONE v4.0

Execute nesta ordem — cada feature é gate para a próxima.

---

### F1 — Codebase Audit
**Objetivo**: detectar memory leaks, zombie processes, unsafe patterns.
**Ferramentas**: `smart-explore` + `timeline-report`

**Definition of Done**:
- [ ] Relatório com todos os findings classificados (CRIT/HIGH/MED/LOW)
- [ ] Zero findings CRIT sem plano de mitigação documentado
- [ ] Frontend com lógica de autorização identificado e marcado para remoção em F7
- [ ] Lista de dependências desatualizadas gerada (input para F6)
- [ ] Nenhum `except Exception` genérico sem tratamento específico encontrado sem registro

---

### F2 — SQLite Hardening
**Objetivo**: eliminar "database is locked" sob carga de agents.

```python
# CORRETO: single connection + WAL + write serialization via Queue
# ERRADO: "connection pooling" SQLite — não existe, piora o problema

class Database:
    def __init__(self, path: str):
        self._path = path
        self._conn: aiosqlite.Connection | None = None
        self._write_queue: asyncio.Queue = asyncio.Queue()

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")  # WAL+NORMAL = seguro e rápido
        await self._conn.execute("PRAGMA busy_timeout=5000")   # aguardar até 5s antes de erro
        asyncio.create_task(self._write_worker())  # único worker de escrita

    async def _write_worker(self) -> None:
        while True:
            query, params, future = await self._write_queue.get()
            try:
                await self._conn.execute(query, params)
                await self._conn.commit()
                future.set_result(None)
            except aiosqlite.Error as e:
                future.set_exception(e)
```

**Definition of Done**:
- [ ] Todos os writes passam pela Queue — zero writes diretos fora do worker
- [ ] `PRAGMA journal_mode=WAL` confirmado ativo em runtime
- [ ] Máximo 3 conexões de leitura simultâneas respeitado
- [ ] Teste de carga com 5 agentes simultâneos sem "database is locked"
- [ ] `busy_timeout` configurado

---

### F3 — Async Agent Orchestration (Lite)
**Objetivo**: micro-tasks com TaskGroup + Semaphore + registry.

```python
# CORRETO: TaskGroup + registry
# ERRADO: create_task() fire-and-forget = OOM garantido

class AgentOrchestrator:
    def __init__(self, max_concurrent: int = 5):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._registry: dict[str, asyncio.Task] = {}
        self._paused = False

    async def run_agent(self, agent_id: str, coro) -> None:
        if self._paused:
            raise RuntimeError("Orchestrator paused — system under memory pressure")
        async with self._semaphore:
            async with asyncio.TaskGroup() as tg:
                task = tg.create_task(coro)
                self._registry[agent_id] = task
            self._registry.pop(agent_id, None)

    async def cancel_all(self) -> None:
        for task in self._registry.values():
            task.cancel()
        await asyncio.gather(*self._registry.values(), return_exceptions=True)
        self._registry.clear()

    def pause_new_tasks(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False
```

**Definition of Done**:
- [ ] Zero `asyncio.create_task()` fire-and-forget no codebase
- [ ] Registry auditável via endpoint `/health/agents`
- [ ] Cancelamento limpo testado (nenhum task órfão após `cancel_all`)
- [ ] Semaphore cheio retorna 429 com `Retry-After` — não drop silencioso

---

### F4 — Memory-Disciplined Architecture
**Objetivo**: < 200MB resting, zero bulk collections em memória.

**Definition of Done**:
- [ ] Zero `.fetchall()` em queries que podem retornar > 100 rows
- [ ] Todos os pipelines usando async generators
- [ ] `tracemalloc` snapshot antes/depois — redução mensurável documentada
- [ ] LRU caches com `maxsize` explícito (nunca unbounded)
- [ ] `psutil.virtual_memory()` em resting < 200MB confirmado

---

### F5 — Docker Optimization
**Objetivo**: multi-stage build, swap configurado, OOM-resistant.

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runtime
# Fixar digest após estabilizar — nunca :latest em produção
COPY --from=builder /install /usr/local
COPY ./app /app
WORKDIR /app

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
# workers=1: single process no VPS 1vCPU/1GB — asyncio gerencia concorrência internamente
```

```yaml
# docker-compose.yml
services:
  nexus:
    deploy:
      resources:
        limits:
          memory: 800m
        reservations:
          memory: 200m
    mem_swappiness: 10  # swap apenas sob pressão real, não agressivamente
```

**Definition of Done**:
- [ ] `docker images nexus` < 250MB
- [ ] `/swapfile` 2GB ativo no VPS (`swapon --show`)
- [ ] Health check respondendo em < 10s após start
- [ ] `docker stats` em resting: memory < 200MB

---

### F6 — Stack Modernization
**Objetivo**: Python 3.12 + proxy rotation + OathNet optimization.

**Estratégia de rollback (obrigatória antes de executar)**:
```bash
# Snapshot antes do upgrade
pip freeze > requirements.lock.pre-python312.txt
docker tag nexus:latest nexus:pre-python312-backup

# Reverter se upgrade falhar
docker tag nexus:pre-python312-backup nexus:latest
pip install -r requirements.lock.pre-python312.txt
```

**Gate de entrada**:
- [ ] Test suite passando no Python atual (linha de base documentada)
- [ ] Lista de dependências com versão mínima Python mapeada
- [ ] Backup do environment salvo

**Definition of Done**:
- [ ] Test suite passando em Python 3.12 (mesma cobertura da linha de base)
- [ ] Zero warnings de deprecation do Python 3.12
- [ ] `docker images nexus` ainda < 250MB após upgrade

---

### F7 — Security Hardening
**Objetivo**: CSP, JWT httpOnly, rate limiting, validação de input.

**Todas as defesas vivem no backend. Sem exceção.**

**Plano de migração JWT** (janela de manutenção obrigatória):
```
1. Deploy com suporte dual: aceita tokens antigos e novos por 24h
2. Forçar re-login via endpoint /auth/invalidate-all
3. Após 24h: remover suporte ao formato antigo
4. Rollback: reverter para imagem pré-F7 + restaurar tabela de sessions
```

**Checklist de segurança**:
- [ ] CSP sem `unsafe-inline` — se quebrar frontend, corrigir o frontend (não o CSP)
- [ ] JWT em httpOnly cookie — zero token em localStorage/sessionStorage
- [ ] Todos os inputs validados por Pydantic models com validators explícitos
- [ ] Rate limiting por endpoint E por usuário autenticado
- [ ] Headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Strict-Transport-Security`
- [ ] Zero dados de usuário em query params de URL
- [ ] Auditoria: nenhum frontend com lógica de permissão restante

**Definition of Done**:
- [ ] Score A em securityheaders.com
- [ ] Zero findings de autorização no frontend
- [ ] Teste manual nos endpoints de autenticação e scan

---

### F8 — Health Monitoring
**Objetivo**: watchdog de memória/CPU + graceful degradation.

n8n-mcp fora do escopo — alertas internos via FastAPI + psutil.

```python
import psutil
from fastapi import APIRouter, Depends

router = APIRouter()

MEMORY_ALERT_MB = 400    # investigar ativamente
MEMORY_CRITICAL_PCT = 85 # pausar novos agents
CPU_ALERT_PCT = 80

@router.get("/health")
async def health_check(orchestrator: AgentOrchestrator = Depends(get_orchestrator)):
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.1)
    mem_mb = mem.used / 1024 / 1024

    if mem.percent > MEMORY_CRITICAL_PCT:
        orchestrator.pause_new_tasks()
        logger.warning("Memory critical {:.0f}% — new agents paused", mem.percent)
    elif mem_mb > MEMORY_ALERT_MB:
        logger.warning("Memory alert {:.0f}MB — investigate", mem_mb)

    return {
        "status": "degraded" if orchestrator._paused else "healthy",
        "memory_used_mb": round(mem_mb, 1),
        "memory_pct": mem.percent,
        "cpu_pct": cpu,
        "active_agents": len(orchestrator._registry),
        "agents_paused": orchestrator._paused,
        "swap_used_mb": round(psutil.swap_memory().used / 1024 / 1024, 1),
    }
```

**Definition of Done**:
- [ ] `/health` retorna dados reais (não só HTTP 200)
- [ ] Threshold alerta (400MB) e crítico (85%) funcionais
- [ ] Graceful degradation: agents pausam — não derrubam
- [ ] Log de warning quando thresholds são atingidos

---

## ESTRATÉGIA DE TESTES

### Estrutura mínima
```
tests/
├── unit/           → lógica pura, sem I/O
├── integration/    → FastAPI TestClient + SQLite :memory:
└── e2e/            → cenários completos com agentes mockados
```

### Cobertura mínima aceitável

| Camada | Mínimo | Foco |
|---|---|---|
| Unit | 80% | Validators, parsers, rate limiter, orchestrator logic |
| Integration | 60% | Endpoints FastAPI, fluxo de autenticação, SQLite |
| E2E | Cenários críticos | Scan completo, autenticação, health check |

### Como mockar agentes OSINT

```python
# respx para mockar httpx — nunca requests reais em teste
import pytest
import respx
import httpx

@pytest.mark.asyncio
@respx.mock
async def test_agent_timeout():
    respx.get("https://api.shodan.io/...").mock(side_effect=httpx.TimeoutException)
    result = await agent_coro("1.2.3.4")
    assert result["status"] == "timeout"

# conftest.py — fixture de banco em memória
@pytest.fixture
async def db():
    async with aiosqlite.connect(":memory:") as conn:
        await setup_schema(conn)
        yield conn
```

### "Test suite verde" para gate do F6
- Zero falhas em unit/ e integration/
- E2E: cenários de scan, auth e health passando
- `pytest --tb=short -q` termina com exit code 0
- Sem `pytest.mark.skip` sem justificativa documentada

---

## ESTRATÉGIA DE BRANCHING

```
main
  └── v4.0/f1-audit           → F1 (abre agora)
  └── v4.0/f2-sqlite          → F2 (abre após F1 merged)
  └── v4.0/f3-orchestration   → F3
  └── v4.0/f4-memory          → F4
  └── v4.0/f5-docker          → F5
  └── v4.0/f6-modernization   → F6
  └── v4.0/f7-security        → F7
  └── v4.0/f8-health          → F8
```

**Regras**:
- Um branch por feature, criado apenas quando a feature anterior estiver merged
- Branches em série — não paralelo (constraints de hardware não permitem testes paralelos seguros)
- Sem feature flags — gates são branches
- PR: testes passando + checkpoint GSD + sem warnings novos introduzidos
- Rollback: `git revert` do merge commit — sem branches de rollback separados

---

## REGRAS DE PROTEÇÃO DE ARQUIVOS

NÃO modificar sem aprovação explícita + checkpoint GSD + confirmação do usuário:

```
CLAUDE.md               → este arquivo
.env / .env.production  → segredos — nunca logar, nunca commitar
meridian.css            → sistema visual Amber/Noir
docker-compose.prod.yml → configuração de produção
```

---

## WORKFLOW DE SESSÃO

```
INÍCIO DE SESSÃO:
1a. mem-search "NexusOSINT v4.0" → restaurar contexto
1b. [FALLBACK se claude-mem falhar] → incluir contexto manualmente no prompt
2.  timeline-report → ver onde parou
3.  /gsd:status → ver feature ativa e Definition of Done pendente

ANTES DE NOVO CÓDIGO (sessão Opus):
4.  Opus planeja → diagrama ASCII + trade-offs + edge cases + segurança + outbound rate limits
5.  Usuário aprova o plano
6.  /gsd:execute-phase → sessão Sonnet implementa

DURANTE IMPLEMENTAÇÃO (sessão Sonnet):
7.  Código completo, type hints, exception handling correto — sem pseudo-código
8.  Se surgir decisão arquitetural → parar, escalar para sessão Opus
9.  Se surgir problema de segurança fora do escopo → documentar, sinalizar

FIM DE SESSÃO:
10. /gsd:checkpoint → salvar progresso
11. obsidian-markdown → documentar decisões técnicas
    [FALLBACK] → registrar em PROJECT.md se Obsidian indisponível
```

---

## REGRAS DE OURO

| Regra | Status |
|---|---|
| Opus planeja, Sonnet executa — protocolo do usuário, não automático | OBRIGATÓRIO |
| F1 (Audit) completa antes de qualquer código novo | OBRIGATÓRIO |
| Todo dado do frontend é não-confiável por definição | OBRIGATÓRIO |
| Validação, autorização e regras de negócio vivem exclusivamente no backend | OBRIGATÓRIO |
| Claude sinaliza problemas de segurança mesmo fora do escopo da task | OBRIGATÓRIO |
| Claude discorda e justifica quando a decisão técnica é errada | OBRIGATÓRIO |
| "Continuar" avança a task — não cancela objeção técnica em aberto | OBRIGATÓRIO |
| Exception handling correto por camada — sem `except Exception` genérico | OBRIGATÓRIO |
| Rate limiting de saída em todos os agentes OSINT | OBRIGATÓRIO |
| SQLite: asyncio.Queue + single writer + máx 3 readers simultâneos | OBRIGATÓRIO |
| Async agents: TaskGroup + registry — sem fire-and-forget | OBRIGATÓRIO |
| Semaphore ceiling: máximo 5 tasks simultâneas | OBRIGATÓRIO |
| Docker target: < 250MB | OBRIGATÓRIO |
| Brand Amber/Noir: nenhuma mudança sem aprovação | OBRIGATÓRIO |
| Rollback documentado antes de executar F6 e F7 | OBRIGATÓRIO |
| Test suite verde antes de F6 — cobertura mínima documentada | OBRIGATÓRIO |
| Sem pseudo-código, placeholders ou "# seu código aqui" | PROIBIDO |
| Sem `except Exception` genérico | PROIBIDO |
| Sem segredos hardcoded | PROIBIDO |
| Sem `.fetchall()` em queries > 100 rows | PROIBIDO |
| Sem `asyncio.create_task()` sem registry | PROIBIDO |
| Sem lógica de autorização no frontend | PROIBIDO |
| Python 3.12 upgrade sem test suite verde + rollback pronto | PROIBIDO |
| JWT migration sem janela de manutenção planejada | PROIBIDO |

---

## REFERÊNCIAS RÁPIDAS

```
Async agents:        asyncio.TaskGroup (PEP 654, Python 3.11+)
SQLite async:        aiosqlite + WAL + busy_timeout=5000
Memory profiling:    tracemalloc + psutil
Rate limiting in:    slowapi (FastAPI, por endpoint + por usuário)
Rate limiting out:   OutboundRateLimiter (token bucket por domínio)
HTTP client:         httpx.AsyncClient com timeout explícito — nunca requests síncrono
Input validation:    pydantic v2 com field validators — nunca confiar no frontend
Logging:             loguru — estruturado, nunca PII, nunca dados do alvo sem hash
Testes async:        pytest-asyncio + respx (mock httpx)
Docker multi-stage:  python:3.12-slim (digest fixo após estabilizar)
VPS swap:            fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
Security headers:    starlette middleware — não JS
Memory thresholds:   resting < 200MB | alerta > 400MB | crítico > 85% RAM
SQLite readers:      máx 3 simultâneos com WAL no VPS 1GB
```

---

## DEPLOY — VPS PRODUCTION

**VPS**: DigitalOcean `root@146.190.142.50`

Após qualquer mudança de código aprovada e commitada, Claude faz o deploy assim:

```bash
# 1. Enviar arquivos alterados para o VPS
scp -r api/ static/ nginx.conf docker-compose.yml root@146.190.142.50:/root/nexus_osint/

# 2. Rebuild e restart no VPS
ssh root@146.190.142.50 "cd /root/nexus_osint && docker compose up -d --build"
```

**Regras de deploy**:
- Deploy só ocorre após `git commit` bem-sucedido
- Nunca fazer deploy de branch diferente de `master` sem aprovação explícita
- Se `docker compose up` falhar no VPS → investigar logs antes de qualquer rollback: `ssh root@146.190.142.50 "docker logs nexus_osint-nexus-1 --tail 50"`
- Deploy de mudanças de schema de banco de dados exige janela de manutenção planejada
- Nunca enviar `.env` ou arquivos de segredos via SCP — esses já existem no VPS

---

## DEVELOPER PROFILE

**Math** — low-code / vibe coding, desenvolvedor principal do NexusOSINT (produto commercial).
Claude atua como co-engenheiro sênior autônomo. Segurança, performance, qualidade e integridade arquitetural são defaults — não dependem de instrução explícita.

Estilo: Math é direto. Claude responde na mesma moeda — sem preamble.
"Continuar" = avançar no plano. Objeções técnicas abertas são re-enunciadas em uma linha antes de avançar.