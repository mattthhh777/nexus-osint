# R2 — Smoke Script Spec (Playwright reutilizável)

**Objetivo:** especificação de um smoke E2E reutilizável que valide as invariantes do R2 Signal UI antes e depois de qualquer patch. **Spec apenas — não implementar nesta sessão.**

**Stack obrigatória:** Playwright (já presente nos artefatos `.playwright-mcp/`). Vanilla JS no produto → smoke também sem framework UI.

---

## Localização e nomenclatura

```
tests/
├── e2e/
│   ├── r2_signal_smoke.spec.js      ← arquivo único, 4 cenários
│   └── fixtures/
│       └── auth.js                  ← setup de login (env vars ou storage state)
└── playwright.config.js              ← config base (baseURL, headless, timeouts)
```

Convenções:
- Sufixo `_smoke.spec.js` distingue smoke (rápido, blocking) de E2E full.
- Cenários como `test.describe` blocks → 1 describe por combinação de flags.
- Sem snapshots visuais nesta primeira versão (pixel-diff fica para v2).

---

## Comandos

```bash
# Local — contra dev server (http://localhost:8000)
npm run smoke:r2

# Local headed — debug visual
npm run smoke:r2 -- --headed --debug

# Contra produção — opt-in explícito
SMOKE_BASE_URL=https://nexusosint.uk npm run smoke:r2

# Single scenario
npx playwright test r2_signal_smoke.spec.js -g "ui=signal hash-only"
```

`package.json` (proposta):
```json
{
  "scripts": {
    "smoke:r2": "playwright test tests/e2e/r2_signal_smoke.spec.js --reporter=line",
    "smoke:r2:ci": "playwright test tests/e2e/r2_signal_smoke.spec.js --reporter=github"
  }
}
```

---

## Variáveis de ambiente

| Var | Obrigatório | Default | Uso |
|-----|-------------|---------|-----|
| `SMOKE_BASE_URL` | não | `http://localhost:8000` | URL base |
| `SMOKE_USER` | sim para cenários autenticados | — | Login user |
| `SMOKE_PASS` | sim para cenários autenticados | — | Login pass |
| `SMOKE_TARGET` | sim para cenários de busca | — | Alvo sintético (NUNCA usar PII real) |
| `SMOKE_HEADFUL_LOGIN` | não | `false` | Se `true`, abre browser para login manual no primeiro run e salva `storageState.json` |

**Regra de privacidade:** `SMOKE_TARGET` deve ser um valor sintético controlado pelo time (ex: `test+r2@nexusosint.local`). Nunca PII real, mesmo em smoke local.

---

## Cenários (4 describes obrigatórios)

### Cenário 1 — Baseline legacy (`/` sem flags)

**Setup:** navegar para `${SMOKE_BASE_URL}/` (sem query string).

**Asserts:**
- `<html>` SEM classe `nx-signal`
- `<html>` SEM `data-theme`
- `#signalShell` com `aria-hidden="true"` e `display !== 'block'`
- Antes de qualquer busca: zero requests para `/api/v2/search`
- Console: zero erros (warnings cosméticos OK)
- `localStorage` e `sessionStorage` sem chaves contendo o valor de `SMOKE_TARGET` (raw)

**Não fazer:** disparar busca neste cenário (mantém leve, ~2s).

---

### Cenário 2 — `?engine=v2` puro (sem Signal UI)

**Setup:** navegar para `${SMOKE_BASE_URL}/?engine=v2`. Login se necessário.

**Asserts:**
- `<html>` SEM classe `nx-signal`
- `#signalShell` continua `aria-hidden="true"`
- Após busca controlada com `SMOKE_TARGET`:
  - request POST para `/api/v2/search` retorna 201
  - SSE connection aberta para o job_id retornado
  - DOM legacy popula normalmente (`#resTarget`, `#results`)
- Console: zero erros críticos

**Trade-off documentado:** este cenário valida que o backend v2 funciona sem o frontend novo (rollback parcial).

---

### Cenário 3 — `?ui=signal` puro (sem forçar v2)

**Setup:** navegar para `${SMOKE_BASE_URL}/?ui=signal`.

**Asserts:**
- `<html>` COM classe `nx-signal`
- `#signalShell` com `aria-hidden="false"` e visível (`display === 'grid'` ou similar)
- Sem busca disparada: zero requests para `/api/v2/search` E `/api/search`
- Empty states Signal renderizados (textos "Nenhuma investigação em curso", "Nada em fila", etc.)
- `data-theme` ausente (tema default)
- Console: zero erros

**Invariante crítica:** `ui=signal` sozinho **não** força o engine v2 — usuário pode estar em Signal UI lendo cases locais.

---

### Cenário 4 — Combo completo `?engine=v2&theme=graphite&ui=signal`

**Setup:** navegar para `${SMOKE_BASE_URL}/?engine=v2&theme=graphite&ui=signal`. Login + busca com `SMOKE_TARGET`.

**Asserts pré-busca:**
- `<html>` com classe `nx-signal`
- `<html>` com `data-theme="graphite"` (após patch W3; antes do patch este assert falha — esperado)
- Tokens graphite ativos (computed style do `--bg-base` muda)

**Asserts pós-busca (PRIVACY-CRITICAL):**
- POST `/api/v2/search` 201, SSE OK, job_id presente
- **`#resTarget.textContent` permanece `'─'` (placeholder)** — esta é a guarda W1
- `document.body.innerText` NÃO contém o valor literal de `SMOKE_TARGET`
- `JSON.stringify(localStorage)` NÃO contém o valor literal de `SMOKE_TARGET`
- `JSON.stringify(sessionStorage)` NÃO contém o valor literal de `SMOKE_TARGET`
- Signal evidence drawer/panels populam via eventos SSE (hash-only)
- Console: zero erros, zero warnings novos

**Asserts viewport:**
- Desktop 1280×800: `document.body.scrollWidth === document.documentElement.clientWidth` (sem overflow horizontal)
- Mobile 390×844 (re-run com `page.setViewportSize`): idem

---

## Critérios de aceitação globais (todos cenários)

1. **Privacy invariant:** em cenários com `ui=signal`, raw target nunca em DOM nem storage.
2. **Opt-in invariant:** sem flags → legacy puro; flags isoladas não cascateiam (ui≠engine, engine≠ui).
3. **No regression:** legacy mode (cenário 1) tem mesmo comportamento pré-R2.
4. **Console clean:** zero errors em todos cenários. Warnings cosméticos (favicon 404) toleráveis até W5.
5. **Viewport:** sem overflow horizontal em desktop ≥1280px nem mobile 390px.

---

## O que NÃO testar nesta primeira versão

- Pixel-diff visual (snapshots) — adicionar em fase visual QA dedicada
- Autenticação completa (login/logout flow) — fora do escopo R2 smoke
- Performance (LCP/CLS) — usar Lighthouse separado
- API surface além de `/api/v2/search` POST + SSE — fora do smoke UI

---

## Hooks de autenticação

**Estratégia:** `storageState.json` gerado uma vez via login manual headful, reutilizado em CI.

```js
// tests/e2e/fixtures/auth.js (spec)
import { test as base } from '@playwright/test';

export const test = base.extend({
  authedPage: async ({ browser }, use) => {
    const context = await browser.newContext({
      storageState: process.env.SMOKE_STORAGE_STATE || 'tests/e2e/.auth/storageState.json'
    });
    const page = await context.newPage();
    await use(page);
    await context.close();
  }
});
```

**Privacy:** `.auth/storageState.json` em `.gitignore`. Nunca commitar.

---

## Output esperado

```
Running 4 tests using 1 worker
  ✓ baseline legacy (1.8s)
  ✓ engine=v2 puro (4.2s)
  ✓ ui=signal puro (2.1s)
  ✓ combo engine=v2&theme=graphite&ui=signal (6.8s)

4 passed (15.0s)
```

Total wall-time alvo: **< 30s**. Acima disso → split em smoke vs E2E full.

---

## Bloqueadores conhecidos (pré-condições)

- W3 patch precisa estar aplicado antes do Cenário 4 passar 100% (assert do `data-theme`).
- Antes do W1 patch: assert "DOM sem raw target" no Cenário 4 vai falhar — esperado. Smoke serve para **provar** que o patch funcionou.
- Backend v2 (`/api/v2/search`) precisa estar disponível no `SMOKE_BASE_URL`.

---

## Próximos passos (não nesta sessão)

1. Codex implementa `playwright.config.js` + `r2_signal_smoke.spec.js` seguindo esta spec
2. Run local headful para gerar `storageState.json`
3. Run headless 4 cenários → 4 GREEN obrigatórios antes de qualquer patch ir para master
4. Integrar smoke ao pre-merge hook ou CI workflow
