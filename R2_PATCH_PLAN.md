# R2 — Patch Plan (post-deploy WARNs)

**Status:** R2 merged em `a9b471a`, produção PASS funcional, rollback não necessário.
**Escopo deste plano:** corrigir 5 WARNs identificados no smoke dinâmico Playwright. Não inicia R3.
**Regra:** mudanças cirúrgicas, sem refactor amplo. Cada item tem patch isolado + teste.

---

## Inventário dos WARNs

| # | Severidade | Item | Origem |
|---|-----------|------|--------|
| W1 | **HIGH** (privacidade) | Raw target aparece no DOM via legacy `#resTarget` quando `?engine=v2&theme=graphite&ui=signal` roda busca | `static/index.html:188` + `static/js/render.js:166` |
| W2 | MED (visual) | Overflow desktop ~32px em `.signal-shell` | `static/css/signal.css` (signal-layout grid) |
| W3 | LOW (diagnóstico) | `theme=graphite` não marca `<html>` com classe/atributo visível | `static/js/theme-flag.js` |
| W4 | LOW (dívida) | CSP permite `'unsafe-inline'` em script/style | `nginx.conf` / FastAPI middleware |
| W5 | COSMÉTICO | favicon 404 | `static/` (asset ausente) |

Signal proper já é hash-only. localStorage/sessionStorage limpos no smoke. POST `/api/v2/search` 201 + SSE OK. Mobile 390×844 sem overflow.

---

## W1 — Raw target leak no legacy DOM (PRIORIDADE)

### Diagnóstico
Quando usuário entra com `?ui=signal&engine=v2`, o bootstrap aplica `<html class="nx-signal">` mas o legacy `<div id="results">` continua no DOM. `render.js:166` executa `document.getElementById('resTarget').textContent = q;` durante o pipeline legado que ainda dispara em paralelo com o v2. Resultado: o alvo bruto (CPF/email/telefone) fica visível no DOM mesmo quando o usuário está no modo Signal hash-only.

Invariante violada: **modo Signal nunca deve conter raw target em DOM/storage**.

### Patch proposto (para Codex executar)

**Opção A — Defensiva no render legado (RECOMENDADA, menor risco):**
```js
// static/js/render.js — antes da linha 166
if (document.documentElement.classList.contains('nx-signal')) {
  return; // Signal owns the DOM; legacy render is a no-op in Signal mode
}
document.getElementById('resTarget').textContent = q;
```

**Opção B — CSS scope no legacy results em modo signal:**
```css
/* static/css/signal.css */
.nx-signal #results { display: none !important; }
.nx-signal #scanStatus { display: none !important; }
```

**Recomendação:** aplicar **A + B**. A evita escrita do raw target (privacy); B evita flash visual do legacy header. Sem `?ui=signal`, ambas as guardas são no-op — comportamento legado preservado.

### Critério de aceitação
- `?ui=signal` + busca: `#resTarget.textContent === '─'` (placeholder original) e o nó não recebe nenhum dado de input do usuário.
- Sem `?ui=signal`: comportamento legacy idêntico ao atual.
- Sem nova request para `/api/search` em modo Signal puro.

### Arquivos tocados
- `static/js/render.js` (+3 linhas, guard clause)
- `static/css/signal.css` (+2 regras)

---

## W2 — Overflow desktop ~32px em `.signal-shell`

### Diagnóstico
Em viewport ≥1280px, `signal-layout` (3 colunas) excede o container pai em ~32px. Provável causa: `gap` somado a `min-width: 0` ausente em filhos grid, ou padding interno duplicado.

### Patch proposto
Inspecionar `static/css/signal.css` linhas 28–80 e 36+:
```css
.signal-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 16px;
  min-width: 0; /* prevent grid blowout */
}
.signal-panel { min-width: 0; }
```

Ajustar `gap` se necessário; auditar `padding` agregado no `.page` parent.

### Critério de aceitação
- Viewport 1280×800, 1440×900, 1920×1080: `document.body.scrollWidth === document.documentElement.clientWidth`.
- Mobile (390×844) continua sem overflow.

### Arquivos tocados
- `static/css/signal.css`

---

## W3 — `theme=graphite` sem marcador no `<html>`

### Diagnóstico
`theme-flag.js` carrega o stylesheet `tokens-graphite.css` mas não adiciona `data-theme="graphite"` ou classe ao root. Isso impede:
- QA visual rápido por inspeção de DOM
- CSS condicional futuro `[data-theme="graphite"] .foo {}`
- Smoke tests assertarem o tema ativo sem checar CSSOM

### Patch proposto
**Decisão arquitetural:** marcar `<html>` com `data-theme` é diagnóstico **e** habilitador. Custo trivial, benefício alto.

```js
// static/js/theme-flag.js — após inject do <link>
document.documentElement.dataset.theme = 'graphite';
```

Adicionar limpeza no caminho sem flag para garantir idempotência:
```js
if (!params.has('theme')) {
  delete document.documentElement.dataset.theme;
}
```

### Critério de aceitação
- `?theme=graphite` → `document.documentElement.getAttribute('data-theme') === 'graphite'`
- Sem `?theme=*` → atributo ausente
- Tokens visuais inalterados (apenas marcador, sem regra CSS nova ainda)

### Arquivos tocados
- `static/js/theme-flag.js`

---

## W4 — CSP `'unsafe-inline'` (dívida técnica)

### Diagnóstico
Dívida pré-R2 herdada. Frontend Vanilla JS tem scripts/styles inline. Tirar agora exige refactor amplo dos `onclick=`, `style="…"` e `<script>…</script>` inline.

### Decisão
**Adiar para feature dedicada (não R2 patch).** Criar issue/phase própria. Registrar como dívida conhecida com escopo definido:
1. Auditar todos `onclick=`, `onload=` etc. → handlers via `addEventListener` em JS externo
2. Mover estilos inline para classes utilitárias em CSS já existente
3. Remover `'unsafe-inline'` do CSP em `nginx.conf` apenas após 1+2

**Não tocar nesta rodada de patches.**

---

## W5 — favicon 404 (cosmético)

### Diagnóstico
Console mostra `GET /favicon.ico 404`. Cosmético, sem impacto funcional.

### Patch proposto
Opção A: adicionar `static/favicon.ico` 32×32 com identidade Amber/Noir.
Opção B: `<link rel="icon" href="data:,">` em `index.html` para silenciar request.

**Recomendação:** A (asset real, brand-aligned). Aguarda asset do design system.

### Critério de aceitação
- `GET /favicon.ico` retorna 200
- Console sem 404 cosmético

---

## Ordem de execução recomendada (Codex)

1. **W1** (privacy, alta) → patch + teste
2. **W3** (habilitador de testes futuros) → patch + teste
3. **W2** (visual desktop) → patch + teste
4. **W5** (cosmético, se asset disponível) → opcional
5. **W4** → não nesta rodada; criar issue

Cada item em **commit separado** seguindo Conventional Commits:
- `fix(ui): prevent raw target leak in signal mode (W1)`
- `feat(ui): mark html with data-theme=graphite (W3)`
- `fix(ui): remove signal-shell desktop overflow (W2)`
- `chore(ui): add favicon (W5)`

---

## Testes obrigatórios antes de merge

- [ ] Smoke Playwright (ver `R2_SMOKE_SPEC.md`) passa em todos 4 cenários
- [ ] Manual: `?ui=signal&engine=v2` busca real → DOM sem raw target
- [ ] Manual: desktop 1920×1080 sem overflow horizontal
- [ ] Manual: legacy mode (`/` sem flags) idêntico ao pré-patch
- [ ] `git diff --stat` ≤ 30 linhas alteradas por commit (cirurgia, não refactor)

---

## Não fazer nesta rodada

- Tocar lógica do v2 search ou SSE
- Mudar componentes Signal (`confidence-meter`, `connector-card`, `evidence-drawer`, `status-pill`)
- Modificar tokens visuais (`tokens-graphite.css`)
- Refactor de `legacy-adapter.js` além do guard do W1
- Mexer em CSP / nginx (W4 fica para sua própria feature)
- Copiar dados do mockup/canvas para produção
