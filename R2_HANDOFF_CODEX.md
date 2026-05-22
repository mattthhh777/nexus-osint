# R2 — Handoff Técnico para Codex (continuação)

**Sessão de origem:** Claude Opus 4.7, 2026-05-22.
**Destino:** futuras sessões Codex (Sonnet ou outro modelo) que continuarão o trabalho R2 → R3.
**Princípio:** este doc é leitura obrigatória antes de tocar qualquer arquivo R2. Não pular.

---

## 1. Estado atual

**Branch:** `master`.
**SHA produção:** `a9b471a` (merge: R2 signal UI).
**Status funcional:** PASS. Smoke HTTP/assets/API passou. Smoke dinâmico Playwright PASS funcional. Rollback não necessário.
**Pendências:** 5 WARNs documentados em `R2_PATCH_PLAN.md`. Nenhum bloqueador. Nenhum crash.

---

## 2. Commits R2 (em ordem cronológica)

```
fe5e46e feat(ui): add signal foundation flag
6102a51 feat(ui): bind v2 results to signal shell
085c40f feat(ui): add signal evidence detail
a5c1877 feat(ui): polish signal cases
628b1c1 feat(ui): finalize signal polish
43836d1 fix(ui): refine signal polish review
a9b471a merge: R2 signal UI                ← HEAD produção
```

Pré-R2 (R1 base, NÃO regredir): `d2ca6ad merge: R1 job store safe MVP`.

---

## 3. Arquivos tocados em R2

### Backend (já estável, NÃO mexer sem causa)
```
api/main.py                      (+2 lines)    rotas
api/routes/root.py               (+23 lines)   /api/health etc.
api/routes/search_v2.py          (+672)        v2 search endpoint + SSE
api/routes/spiderfoot.py         (+8)          adapter
api/schemas.py                   (+26)         pydantic models v2
api/services/job_store.py        (+641)        in-memory job store
api/services/search_orchestrator (+203)        G3 quorum aggregation
api/tasks.py                     (+52)         async tasks
```

### Frontend (alvo dos patches W1-W5)
```
static/index.html                (+120 lines)   inclui #signalShell + legacy #results
static/admin.html                (+7)
static/css/connectors.css        (+400)         legacy
static/css/signal.css            (+630)   ★    NX-SIGNAL — fonte do W2 e parte do W1
static/css/tokens-graphite.css   (+84)          theme tokens
static/dev/components-preview.*  (+112)         dev playground (não em produção)
static/js/bootstrap.js           (+14)    ★    aplica .nx-signal no <html>
static/js/cases.js               (+289)
static/js/components/            (+365)         confidence-meter, connector-card, evidence-drawer, status-pill
static/js/export.js              (+21)
static/js/job-replay.js          (+125)
static/js/legacy-adapter.js      (+280)   ★    ponte v2-events → DOM legacy
static/js/render.js              (+49)    ★    contém #resTarget write (linha 166) — fonte W1
static/js/search.js              (+22)
static/js/theme-flag.js          (+42)    ★    aplica/remove tema — fonte W3
static/js/v2-search.js           (+1018)        cliente v2 + SSE
```

★ = arquivos provavelmente tocados pelos patches do `R2_PATCH_PLAN.md`.

---

## 4. Flags de feature (opt-in querystring)

| Flag | Default | Efeito |
|------|---------|--------|
| ausente | legacy puro | `/api/search` legacy, UI legacy |
| `?engine=v2` | — | Frontend chama `/api/v2/search` + SSE; UI ainda legacy |
| `?ui=signal` | — | Aplica `.nx-signal` no `<html>`, mostra Signal shell; **não força v2** |
| `?theme=graphite` | — | Injeta `tokens-graphite.css`; **W3:** não marca `<html>` ainda |
| `?engine=v2&ui=signal` | — | Combo recomendado para Signal completo |
| `?engine=v2&theme=graphite&ui=signal` | — | Combo full Signal + tema graphite (cenário 4 do smoke) |

**Invariante:** flags são ortogonais. `ui=signal` SOZINHO não dispara v2; `engine=v2` SOZINHO não muda UI.

---

## 5. Invariantes de privacidade (NÃO QUEBRAR)

1. **Signal mode é hash-only.** Em qualquer caminho com `.nx-signal` no `<html>`:
   - Raw target NUNCA em DOM
   - Raw target NUNCA em `localStorage`
   - Raw target NUNCA em `sessionStorage`
   - Raw target NUNCA em query params da URL após submit
2. **Backend v2** retorna apenas hashes/fingerprints para o frontend Signal — campos PII vêm apenas em eventos liberados explicitamente.
3. **Console** NUNCA logar raw target. Sempre `hash(target)`.
4. **Cases locais** (sessionStorage/localStorage): se persistirem algo, persistir hash + metadata, nunca raw.
5. **Mockup/canvas** contém dados sintéticos para referência visual — proibido copiar para produção mesmo como exemplo.

**W1 viola item 1 hoje.** Fixar via `R2_PATCH_PLAN.md` antes de declarar Signal proper.

---

## 6. O que NÃO tocar

Lista negativa explícita:

- `meridian.css` — sistema visual Amber/Noir do milestone anterior. Brand protegido.
- `api/services/job_store.py` — R1 estável.
- `api/routes/search_v2.py` — backend v2 funcional.
- Componentes Signal (`static/js/components/*`) — visuais validados.
- `tokens-graphite.css` valores — apenas marcar root com `data-theme`, não mudar tokens.
- `CLAUDE.md` raiz (regra de proteção de arquivos).
- `.env` / `.env.production` (regra de proteção de arquivos).
- `docker-compose.prod.yml` (regra de proteção).
- Schema do banco (PostgreSQL 16) sem janela de manutenção.
- Lógica de autorização no frontend — toda autorização vive no backend (FastAPI).

---

## 7. Como testar (pré + pós patch)

### Antes de qualquer patch
1. Rodar `R2_SMOKE_SPEC.md` cenário 1 e 3 → devem passar imediato (não dependem dos patches).
2. Cenário 4 com assert W1 → vai falhar (raw target leak). **Esperado.** Esse é o teste que vai virar GREEN após W1 patch.
3. Cenário 4 com assert `data-theme=graphite` → vai falhar antes do W3. **Esperado.**

### Após cada patch
1. Cenário 1 (legacy) — sempre GREEN, garante zero regressão.
2. Cenário N relacionado ao patch — vira GREEN.
3. `git diff --stat` ≤ 30 linhas no patch. Acima disso → revisar escopo (provável over-engineering).

### Smoke local rápido (sem Playwright pronto)
```bash
# Server local
docker compose up -d
curl -fsS http://localhost:8000/api/health | jq .

# Manual em 4 URLs
open http://localhost:8000/
open http://localhost:8000/?engine=v2
open http://localhost:8000/?ui=signal
open "http://localhost:8000/?engine=v2&theme=graphite&ui=signal"
```

---

## 8. Rollback

**Se patch quebrar produção:**
```bash
# Rollback código (no VPS)
ssh root@87.99.153.11 "cd /root/nexus-osint && git fetch && git reset --hard a9b471a && docker compose up -d --build"

# Verificar
curl -fsS https://nexusosint.uk/api/health
```

`a9b471a` é o known-good. Qualquer patch que precise reverter → volta para esse SHA, investiga, repatcha.

**Rollback de schema:** N/A para R2 patches (nenhum toca DB).

---

## 9. Como deployar (após patches aprovados)

Seguir `CLAUDE.md` raiz seção "DEPLOY":
```bash
# 1. Garantir commit em master
git status   # working tree clean
git log -1 --oneline

# 2. SCP arquivos alterados
scp -r static/ root@87.99.153.11:/root/nexus-osint/

# 3. Rebuild e restart
ssh root@87.99.153.11 "cd /root/nexus-osint && docker compose up -d --build"

# 4. Validar
curl -fsS https://nexusosint.uk/api/health
# Smoke manual nas 4 URLs do item 7

# 5. Se quebrar → rollback item 8
```

**Regras de deploy (do CLAUDE.md):**
- Deploy só após `git commit` em master.
- Nunca enviar `.env` via SCP (já existe no VPS).
- Logs em caso de falha: `ssh root@87.99.153.11 "docker logs nexus_osint-nexus-1 --tail 50"`.

---

## 10. Próximos passos (ordem)

1. **Codex implementa W1** (privacy critical) → commit isolado → smoke cenário 4 vira GREEN
2. **Codex implementa W3** (data-theme) → commit isolado → smoke cenário 4 100% GREEN
3. **Codex implementa W2** (overflow) → commit isolado → asserts viewport GREEN
4. **Codex implementa smoke real** seguindo `R2_SMOKE_SPEC.md`
5. **Codex roda smoke contra produção** → 4/4 GREEN
6. **Math aprova merge** → deploy
7. **Math abre R3** (escopo separado: limpar dívida CSP W4, refinar visual, novos componentes Signal)

**Não pular passos. Não combinar W1+W2+W3 em commit único.** Granularidade ajuda rollback se um deles introduzir regressão.

---

## 11. Comunicação com Math

- Math é direto. Sem preamble. Sem hedging.
- "Continuar" = avançar no plano vigente. Não cancela objeção técnica em aberto.
- Honestidade técnica: discordar se proposta for ruim, justificar tecnicamente, propor alternativa.
- Pseudo-código, placeholders, `# seu código aqui` → proibido.
- Memory feedback: plans vão em **root UPPERCASE** (este arquivo), não em `~/.claude/plans/`.

---

## 12. Referências rápidas

```
SHA produção:        a9b471a
Branch:              master
Stack:               FastAPI + Vanilla JS + PostgreSQL 16 + asyncpg.Pool + Docker
VPS:                 Hetzner root@87.99.153.11 (nexusosint.uk via Cloudflare)
Memory limits:       resting <500MB, alerta >2000MB, crítico >85%
Async ceiling:       asyncio.Semaphore(max=10)
Postgres pool:       min=2 max=10 command_timeout=30
Brand:               Amber/Noir — protegido, sem mudança sem aprovação
Tema novo:           Graphite (opt-in via ?theme=graphite)
UI nova:             Signal (opt-in via ?ui=signal)
Engine novo:         v2 (opt-in via ?engine=v2)
```

---

## 13. Artefatos relacionados nesta sessão

- `R2_PATCH_PLAN.md` — 5 WARNs com diagnóstico, patch proposto, critério de aceitação
- `R2_SMOKE_SPEC.md` — Spec do smoke Playwright (4 cenários)
- `R2_VISUAL_QA.md` — Veredito visual final + 5 melhorias de maior impacto
- `.planning/R2_POST_R1_VISUAL_DELTA.md` — Plano canonical pré-implementação (histórico)
- `.planning/CODEX_HANDOFF.md` — Handoff genérico pré-R2 (referência histórica)
- `.playwright-mcp/` — Artefatos da sessão de smoke dinâmico (logs console + snapshots YAML, 2026-05-21)

Leia os 3 primeiros antes de tocar código. Os 2 seguintes são referência histórica.
