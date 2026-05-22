# R2 — Visual QA Final

**Escopo:** veredito visual subjetivo do Signal UI em produção após R2 (`a9b471a`).
**Base:** smoke dinâmico Playwright 2026-05-21, snapshots em `.playwright-mcp/`, mockup/canvas como referência aspiracional.
**Princípio:** mockup é norte direcional; produto não copia dados fake — apenas a linguagem visual.

---

## Veredito global

**Funcional:** Signal UI entrega o esquema 3-painéis (Camadas / Evidência / Cases), respeita hash-only no painel novo, mantém legacy intacto via opt-in. Empty states claros, copy técnica e séria. Mobile não tem overflow.

**Visual:** o Signal proper está em um patamar acima do legacy — tem identidade. Mas ainda parece um shell estrutural sem o "peso" visual que o mockup transmite. Falta densidade tipográfica, hierarquia mais agressiva e detalhes signature (texturas, micro-states) que diferenciam UI funcional de UI "premium investigativa".

**Posição:** **B+** em produção. Mockup é **A+**. Os 5 ajustes abaixo fecham metade do gap sem reescrever nada.

---

## O que está bom (manter)

1. **Hash-only consistency.** Signal painel principal respeita a invariante — copy "Sem achados simulados" alinhada à identidade técnica honesta.
2. **Empty states com personalidade.** "Cases ficam só neste navegador", "Signal aguarda eventos reais do motor v2" — copy é informativa **e** posicionamento de produto.
3. **Tema Graphite.** Tokens substituem ambient adequadamente — escuridão controlada, não é black-on-black amador.
4. **Tipografia mono em metadados.** Reforça leitura forense.
5. **Sem regressão no Amber/Noir legacy.** Quem entra em `/` sem flags vê o produto original — risco zero de quebra brand.
6. **Mobile 390×844 sem overflow.** Trabalho responsivo correto desde o início.
7. **Componentes isolados** (`confidence-meter`, `connector-card`, `evidence-drawer`, `status-pill`) — fundação correta para iterar sem refactor.

---

## O que ainda parece genérico

1. **Painéis flutuam visualmente.** As 3 colunas do `signal-layout` parecem cards Bootstrap default — falta âncora visual (linha vertical separadora? gradiente sutil de profundidade? sombra direcional?).
2. **Tipografia plana.** Títulos H2/H3 não exploram hierarquia o suficiente. Mockup tinha contrast jump grande entre kicker → título → meta. Produção tem decay linear.
3. **Estados vazios são bonitos mas vazios.** Sem investigação ativa, o usuário vê 3 quadros idênticos de empty. Falta um "centro de gravidade" — algo visual que diga "isto é o produto" mesmo sem dados.
4. **Status pills funcionam mas não brilham.** Cor sozinha resolve estado; mockup mostrava status com ícone + cor + animação sutil em "ativo".
5. **Overflow desktop ~32px** (W2) atrapalha a sensação de polish. Pequena coisa, impacto grande na percepção.
6. **Sem indicador visual do tema ativo.** `theme=graphite` é silencioso (W3). Para QA visual rápido isto importa.

---

## 5 ajustes visuais de maior impacto (R2.x)

Em ordem de ROI (impacto visual / esforço):

### 1. Separadores verticais no `signal-layout` (1h, impacto alto)
Adicionar `border-left: 1px solid var(--border-muted)` no painel central. Cria leitura clara "esquerda = entrada / centro = atual / direita = histórico" sem mudar layout.

```css
.signal-panel--evidence {
  border-left: 1px solid var(--border-muted);
  border-right: 1px solid var(--border-muted);
  padding-inline: 24px;
}
```

### 2. Hierarchy jump nos títulos (1h, impacto alto)
Aumentar contraste tipográfico kicker → título:
```css
.signal-kicker { font-size: 11px; letter-spacing: 0.12em; opacity: 0.6; text-transform: uppercase; }
.signal-panel h3 { font-size: 22px; font-weight: 600; letter-spacing: -0.01em; }
```
Mockup tem essa hierarquia. Produção está mais flat.

### 3. Empty state "centro de gravidade" (2h, impacto alto)
Quando nenhum investigation está ativa, mostrar um visual signature no painel central (camadas) — tipo um diagrama ASCII estático dos 3 layers (G1/G2/G3) ou um pulse animation sutil. Não dados fake — **diagrama estrutural** do que o produto faz.

Exemplo aceitável (sem PII):
```
┌─ G1 ──────────┐
│ Coleta        │  aguardando target
└───────────────┘
       ↓
┌─ G2 ──────────┐
│ Triagem       │  —
└───────────────┘
       ↓
┌─ G3 ──────────┐
│ Quorum        │  —
└───────────────┘
```

### 4. Fix W2 overflow + W3 data-theme (≤1h juntos)
Não é "novo visual" — é remover ruído. Mas o impacto percebido é grande porque produto sem overflow desktop **sente** mais polido.

### 5. Status pill com ícone (1h, impacto médio-alto)
Adicionar svg inline antes do label:
- `idle`: círculo vazio
- `active`: círculo preenchido com pulse `@keyframes`
- `done`: check
- `error`: x

Cor sozinha resolve para usuário sighted, mas ícone aumenta legibilidade em milisegundos de scan visual e reforça identidade técnica.

**Total estimado:** 5–6h de trabalho visual cirúrgico para passar de B+ → A−.

---

## O que fica para R3 (não fazer agora)

- **Animações de entrada** dos painéis (slide-up + fade) — só faz sentido depois da hierarquia tipográfica resolvida (#2).
- **Density mode toggle** (compact vs comfortable) — feature, não polish.
- **Theme proper** (não só graphite tokens, mas Signal-only color palette diferenciada do Amber/Noir) — decisão de brand, exige aprovação.
- **Connector cards expandidos** com mini-charts — depende de dados estáveis do backend G3 quorum.
- **Evidence drawer redesign** com timeline — feature.
- **Dashboard de cases visual** com cards ao invés de lista — fase própria.
- **Loading states elaborados** (skeletons custom) — quando houver mais tempo.
- **Acessibilidade audit completo** (ARIA, focus rings, contraste WCAG AA) — milestone próprio.
- **CSP `unsafe-inline` removal** (W4) — feature dedicada por exigir refactor amplo.

---

## Métricas para próxima avaliação visual

Quando R2.x patches + visual tweaks (#1-#5) forem aplicados, rodar:
1. Side-by-side screenshot do mesmo cenário 4 antes/depois → diff visual
2. 3 usuários reais (não devs) descrevem o produto em 1 frase olhando o painel
3. Comparar com mockup canvas → quanto do "feel" foi capturado (0-100%)
4. Meta para R3: 70%+ do mockup feel capturado

---

## Conclusão

R2 entregou **fundação correta**, **invariantes de privacidade respeitadas** (exceto W1 que tem patch pronto), **identidade visual nascente**. Não é o produto final mas é uma base **adulta** para iterar. Os 5 ajustes acima fecham o gap visual sem ressuscitar o mockup como código.

**Próximo passo recomendado:** rodar os patches W1-W3 do `R2_PATCH_PLAN.md` primeiro (correção), depois os 5 ajustes visuais acima (refinamento). Tratar como duas fases:

- **R2.1 = patches** (correção, semana 1)
- **R2.2 = polish visual** (refinamento, semana 2)
- **R3 = features novas** (depois das duas fases acima)
