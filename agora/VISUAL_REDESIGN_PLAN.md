# NexusOSINT — Visual Redesign Plan

**Status:** Planejamento de produto + visual + frontend. Sem código. Revisado criticamente em 2026-05-18.
**Autor:** sessão Opus (planejamento), 2026-05-18.
**Companheiro:** [`REAL_TIME_OSINT_PLAN.md`](./REAL_TIME_OSINT_PLAN.md) (motor backend). Este plano serve aquele.
**Branch base:** `master` (depois de limpar working tree).
**Restrição honrada:** identidade Amber/Noir pode evoluir por pedido do usuário, mas mudança final de brand continua gate de aprovação Math. No repo atual, usar camada nova de tokens sob feature flag; não editar arquivo protegido sem aprovação explícita.

---

## Revisão crítica Codex — 2026-05-18

### Veredito

O plano visual é forte na direção de produto: sair de "search bar + painéis" para workspace de investigação é correto. O problema é timing. Várias telas dependem de backend ainda inexistente (`search_jobs`, `search_events`, `connector_metrics`, cancelamento, chaining, cases persistentes). Implementar essas telas agora com mock production-like cria retrabalho e risco de prometer capacidade falsa.

Correção: construir agora o **design system**, o **shell de workspace**, os **componentes real-time-ready** e o **adapter visual para dados legacy**. Adiar live completo, Source Health real, Jobs Queue, chain graph e cases first-class até o motor emitir contratos reais.

### Compatibilidade com o plano real-time revisado

| Necessidade real-time | Estado do plano visual | Correção |
|---|---|---|
| Jobs assíncronos | Bem previsto, mas cedo demais para tela completa. | Preparar estados visuais; ligar só quando `/api/v2/search` existir. |
| Progresso real-time | Bom conceito de live view. | Primeiro consumir adapter legacy; depois `connector_result`. |
| Resultados parciais | ConnectorCard resolve. | Não hardcodar tabs; derivar de `connector.category`. |
| Novos conectores | Bem endereçado. | Frontend não pode ter allowlist rígida. |
| Source health | Planejado, mas backend não existe. | Mostrar empty state/admin placeholder honesto; sem métricas mockadas. |
| Cache/freshness | Bem previsto. | Exigir `cache_hit` + `fetched_at`; em v1 mostrar "freshness unavailable" quando ausente. |
| Confidence/evidence | Ponto forte. | Evidence drawer só com evidence real; skeleton/empty se não vier. |
| Status `pending/running/found/not_found/likely/uncertain/blocked/error` | Plano citava 5-state/likely extra. | Adotar 8-state end-to-end. `likely` separado de `found`. |

### Cortes obrigatórios para evitar retrabalho

1. **Não criar dashboard Source Health com dados mockados.** Admin falso destrói confiança. Criar shell/empty state "metrics unavailable until connector_metrics exists".
2. **Não criar Jobs & Queue real antes de `search_jobs`.** Pode criar componentes visuais, não tela funcional.
3. **Não promover Cases para entidade first-class antes de backend persistente.** Hoje cases são `localStorage` metadata; dossiê real espera job store/cases API.
4. **Não renomear `index.html`/landing no início.** Root atual mistura auth + app; mexer cedo arrisca login. Fazer shell autenticado sob flag visual primeiro.
5. **Não usar CDN para Lit.** CSP/hardening e disponibilidade pedem asset local pinado ou manter Vanilla factories no estágio 0/1.
6. **Não criar permissões por conector no frontend.** Backend decide plano/role; frontend só renderiza capabilities retornadas por API.
7. **Não usar mock como fonte de verdade.** Mock só em demo/dev; production mostra empty/unavailable.
8. **Não trocar toda arquitetura visual em paralelo ao motor.** Primeiro token/componentes e adapter legacy; depois live real.

### Implementar agora

- Graphite & Ember tokens sob flag visual; accent usado com parcimônia (<10% da tela).
- Cleanup de copy: remover "Find anything on anyone" e quota OathNet do nav.
- ConnectorCard, StatusPill 8-state, ConfidenceMeter, Risk summary e EvidenceDrawer com empty state.
- Adapter visual para `sherlock_v2`/legacy events atuais, sem esperar `/api/v2/search`.
- Histórico/cases: melhorar navegação e metadados, mas sem prometer dossiê persistente.
- Admin: cards "Source Health unavailable" e "Jobs unavailable" com link para docs, não métricas fake.

### Esperar motor real-time

- Live view com replay/reconnect.
- Cancel/resume/retry de job.
- Source Health com block/error/latency reais.
- Jobs & Queue.
- Chain suggestions e multi-target case timeline.
- Cases persistentes e exports baseados em `search_jobs`.
- Role/plan gating por conector.

---

## Ferramentas usadas / não usadas

| Recurso | Uso |
|---|---|
| Leitura `static/{index,admin}.html` + `tokens.css` + `panels.css` + `cards.css` | Sim — base do diagnóstico |
| Cross-ref com `REAL_TIME_OSINT_PLAN.md` (motor backend planejado) | Sim — todo redesign acomoda esse motor |
| Knowledge de SaaS pattern library (Linear, Stripe, Vercel, Maltego, Observable, Pinpoint, FT Terminal) | Sim — inline |
| Skill `ui-ux-pro-max` / `frontend-design` via `Skill` tool | Plano original não invocou. Revisão Codex 2026-05-18 aplicou `frontend-design` como checklist crítico. |
| MCP Figma | **Indisponível** — nenhum `file_key` fornecido. Mockups serão ASCII + descrição textual. Se Math quiser Figma posteriormente, abrir thread separada. |
| MCP Playwright | Não usado — frontend ainda não existe pra screenshot do redesign. |
| Skill `brainstorming` | Não invocada via Skill tool, mas estrutura aplicada (3 conceitos comparados, recomendação justificada). |

---

## 1. Diagnóstico do visual atual

### 1.1 Snapshot técnico

| Item | Valor |
|---|---|
| Páginas HTML | 2 — `index.html` (344 linhas), `admin.html` (365 linhas) |
| CSS | 11 arquivos, 3 087 LOC. Token system Meridian (`tokens.css`) bem desenhado. |
| JS | 11 arquivos, 3 648 LOC, Vanilla. Sem framework. |
| Fontes | Space Grotesk + JetBrains Mono + Inter (3 famílias — boa hierarquia, mas pesado: 2 Google Fonts requests) |
| Tema | Dark único. Sem light. Sem theme switcher. |
| Cor primária | Amber `#f0a030` sobre `#060810` (preto-azulado quase puro) |
| Layout main | Single-page: hero centralizado → search bar → painéis colapsáveis verticais → histórico bottom |
| Layout admin | Sidebar fixa esquerda + main right. Padrão SaaS clássico — funciona. |

### 1.2 O que funciona hoje
1. **Token system real.** `tokens.css` tem 3 tiers de superfície, 4 tiers de texto, escala severity, spacing 8px, radius tight (2-10px), shadows graduadas. Base sólida — preservar arquitetura, repintar cores.
2. **Hierarquia tipográfica.** Space Grotesk display + JetBrains Mono p/ dados é decisão acertada (não-cliché, legível, profissional p/ hashes/IPs).
3. **Scan progress vertical com dot animado por módulo.** Conceito certo — só precisa virar `connector_status` real-time.
4. **Risk badge agregado + stat-grid** comunica "search summary" rapidamente.
5. **Saved Cases panel slide-in.** UX correta (drawer lateral, não overlay full-screen). Manter padrão.
6. **Painéis colapsáveis com badge counter.** Densidade controlada. Padrão repetível.
7. **Admin sidebar bem estruturado** (Overview / Management / Infrastructure). Vocabulário enxuto.

### 1.3 O que parece copiado da OathNet (ou Snusbase/H8mail/IntelX)
1. **Hero central gigante "Find anything on anyone, instantly."** É o copy-fingerprint da categoria. OathNet, Snusbase, IntelX, H8mail usam variações. Imediatamente comunica "ferramenta de breach lookup", não "plataforma de investigação".
2. **Search bar single-input + Automated/Manual toggle.** OathNet usa o mesmo padrão. Confunde NexusOSINT com OathNet (o próprio produto consome OathNet API — risco de identidade).
3. **Painel "Security Breaches" + "Stolen Information" + "Email Services"** com badge counter. Layout que OathNet popularizou.
4. **Amber #f0a030 sobre near-black `#060810`.** OathNet usa amber-vermelho. Snusbase usa amarelo. Categoria inteira gravita em amber/yellow + dark. Diferenciação visual zero.
5. **Quota pill no nav** mostrando "OathNet xxx left today" expõe diretamente o vendor que é nossa dependência — comunica "thin wrapper".

### 1.4 O que parece genérico SaaS
1. **Stats grid de 5 cards no topo do resultado.** Padrão Vercel/Linear dashboard. Zero diferenciação.
2. **Admin: sidebar + main + breadcrumb-less page-title.** Identico a 50+ admin templates Tailwind.
3. **Toast bottom-center, modal centered overlay, tabela `<thead>/<tbody>` raw.** Sem voz visual própria.
4. **Glow accent + drop-shadow nos botões primários.** Padrão Apple/Linear genérico (não ruim, só não distintivo).

### 1.5 O que prejudica UX
1. **Single-page sem hierarquia investigativa.** Uma busca substitui a anterior na mesma view. Não há conceito de "caso ativo" persistente, só "save case" como ato manual.
2. **Resultados agrupados por categoria fixa** (Breach/Stealer/Social/Email). Não há agrupamento por **alvo enriquecido** (ex.: phone descoberto via breach → ver tudo relacionado).
3. **Risk badge mostra número agregado sem explicar.** `RISK 67` não diz se vem de 12 breaches antigos ou 2 stealer logs recentes.
4. **Confidence ausente do header de resultado.** Só aparece em sherlock platforms.
5. **Evidence ausente.** Frontend não revela por que um sherlock platform virou `confirmed` (validators rodaram mas evidence não chega ao client — `_legacy_sherlock_from_v2` joga fora `evidence` array).
6. **Cursor blinking `█` + glow pulsante + cf_challenge cor critical** = barulho visual constante. Cansa em sessão de 30+ min.
7. **Histórico embaixo de tudo, requer scroll.** Power user vai voltar a buscas antigas 20×/dia.
8. **Manual mode revela chips de módulos por categoria** mas categoria de módulo ≠ target type. Modelo mental confuso.
9. **Sem feedback de cache hit / freshness.** Resultado cached parece idêntico a resultado fresh. Investigador precisa saber.

### 1.6 O que está poluído ou confuso
1. **5 ícones SVG inline diferentes só no nav-user-menu.** Asset inflation. Switch para sprite ou icon font (Lucide via inline-svg pode resolver — padrão único).
2. **`.panel` aparece em 3 contextos** com semântica diferente (search panel, result panel, admin panel). Nome muito genérico.
3. **Versioning CSS via query string `?v=202604180100`** misturado: às vezes `?v=` mesma data, às vezes não. Cache-busting inconsistente.
4. **Hero copy + tag + título + subtítulo + search + mode toggle + manual chips** = 7 elementos verticais antes de qualquer resultado. Hierarquia raza.
5. **Multiple "PDF" buttons** (result-header + export panel). Decisão duplicada.
6. **Mistura emoji + SVG icons** (📁, 📋 alongside SVG icons). Inconsistente.

### 1.7 O que hoje **não está preparado** para real-time
1. **Painéis hardcoded por módulo legacy.** `panelBreach`, `panelStealer`, `panelSocial`, `panelEmail`, `panelExtras`. Adicionar `whatsapp_qr` ou `telegram_resolve` = editar HTML + JS render.
2. **`scan-modules`** é lista vertical fixa com nomes legacy. Para 50+ conectores vira parede de texto.
3. **Sem job lifecycle.** Estado vive na sessão SSE. Reconectar/cancelar/queued/running/failed inexistentes na UI.
4. **Sem source health view.** Se TikTok está bloqueando 80% dos requests, ninguém sabe.
5. **Sem evidence drawer.** Validators v2 já produzem `Evidence[]` no backend; frontend joga fora.
6. **Sem confidence per-result distinto de risk.** Risk agregado domina; confidence por-fonte ausente.
7. **Sem status `blocked` distinto de `error`.** UI mostra ambos como erro vermelho.
8. **Sem chained_jobs preview.** Quando motor real-time produz `chain_suggestion` (phone → email descoberto), UI não tem onde renderizar.

---

## 2. Nova visão de produto

### 2.1 Reposicionamento

| De | Para |
|---|---|
| "Site com search bar" | **Workspace de investigação** |
| Busca como ato passageiro | **Investigação como entidade primária** (job persistente, dossiê) |
| Resultado como página efêmera | **Caso como artefato durável** com timeline, evidências, exports |
| Painel por categoria de módulo | **Camadas: alvo → fontes → evidências → confiança → risco → relatório** |
| "Find anything on anyone" | "Confirme. Não suponha." (ou similar — ver seção 10) |

### 2.2 Modelo mental novo

```
INVESTIGATION (job persistente)
├── TARGET (com type + normalized value + hash)
├── CONNECTORS (rodam em paralelo, status individual)
│   ├── username/sherlock:github → status, score, evidence[]
│   ├── email/gravatar          → status, score, evidence[]
│   ├── phone/whatsapp_qr       → status, score, evidence[]
│   └── …
├── SIGNALS (evidence raw, agrupado por conector)
├── CONFIDENCE (overall, derivado de quorum + score médio + agreement)
├── RISK (derivado de breach count, recency, stealer logs, exposure)
├── TIMELINE (eventos: connector started, found, blocked, chain suggested…)
├── CHAINED INVESTIGATIONS (filhas)
└── REPORT (PDF/JSON snapshot p/ cliente/cliente final/dossiê interno)
```

### 2.3 Princípios visuais que sustentam

1. **Tudo é evidência.** Nenhum status final aparece sem `Why?` clickável.
2. **Confiança ≠ risco.** Dois indicadores separados, sempre.
3. **Tempo importa.** Cache freshness, source health, last_seen sempre visíveis (mesmo que discretos).
4. **Modularidade.** Componente "connector card" é a unidade. Adicionar conector = registrar no backend, frontend descobre.
5. **Densidade controlada.** Investigador olha 8 h/dia. Sem cyberpunk, sem fadiga.
6. **Hierarquia investigativa.** Investigation > Caso > Busca rápida. Não "busca > save case opcional".

---

## 3. Direção visual principal

Três conceitos comparados. Recomendação final ao fim.

### Conceito A — "Graphite & Ember" (recomendado)

**Personalidade:** Forense profissional. Software de inteligência sério. Não é dark-SaaS, é dark-laboratory.

**Referências:** Maltego CE refresh, i2 Analyst's Notebook moderno, Pinpoint (First Draft), ID Card sistemas governamentais europeus, FT Alphaville night theme, Tweetbot for Mac.

**Paleta:**
```
Surface base       #11141a   (graphite 95) — mais quente que o #060810 atual
Surface recessed   #161a22
Surface elevated   #1d2230
Surface hover      #242a3a
Border subtle      rgba(255,255,255,0.05)
Border default     rgba(255,255,255,0.09)
Border strong      rgba(255,255,255,0.15)

Text primary       #e8ecf3
Text secondary     #9ba3b5
Text tertiary      #5d6478
Text disabled      #353a4a

Accent (Ember)     #c4451d   — vermelho-tijolo profundo, signal "found / primary"
Accent hover       #d75432
Accent muted       rgba(196, 69, 29, 0.14)
Accent border      rgba(196, 69, 29, 0.32)

Confidence high    #6ba368   — verde-musgo (não neon)
Confidence med     #c19443   — mostarda envelhecida
Confidence low     #8b6a5e   — terra
Confidence none    #5d6478   — text-tertiary

Status found       #6ba368
Status not_found   #5d6478
Status likely      #c19443
Status uncertain   #b7884a   — âmbar dessaturado
Status blocked     #8b6a5e   — terra (distingue de error)
Status error       #c4451d   — ember (mesmo que accent, p/ chamar atenção)

Risk crit          #b8332b
Risk high          #c4451d
Risk med           #c19443
Risk low           #5d6478
```

**Por que ember vermelho-tijolo:**
- Amber/laranja-amarelado domina a categoria OSINT pública. Vermelho-tijolo é vizinho mas escapa.
- Vermelho-tijolo evoca "carimbo oficial / dossiê / arquivo" — não cyberpunk.
- Saturação baixa (chroma <60) impede vibração agressiva em telas OLED/IPS modernas.
- Acessível: contraste contra surface base ≥7.5:1 (AAA).

**Tipografia:**
- Display: **`Söhne` (paga) ou `Inter Display` (Google free)** — substitui Space Grotesk. Mais sóbria, menos "Big Tech indie".
- Data: **`IBM Plex Mono`** — manter caráter mas trocar JetBrains (clichê dev). Plex Mono tem ligaduras desligáveis, identidade IBM/análise.
- Body: **`Inter`** — manter, é o padrão certo p/ corpo de texto longo.
- Escala 1.125 (não 1.2 atual) — densidade maior, hierarquia mais sutil:
  `12, 13, 14, 16, 18, 22, 28, 36px` (base 14).
- Pesos: 400 / 500 / 600 / 700. Sem ultralight, sem black.

**Ícones:**
- **Lucide** como única família. Coerência total. Sem emoji. Sem mistura.
- Stroke 1.5 padrão. Stroke 1.25 em 12-14px sizes.
- Ícones nunca decoram; sempre rotulam ação ou tipo.

**Componentes-chave novos:**
- **Connector card** (substitui painel-por-categoria) — pequeno (180×96), grid 3-4 colunas, status colorido na borda esquerda.
- **Evidence rail** — coluna direita expansível com lista signals + weight + detail.
- **Confidence meter** — barra horizontal 0-100 com 4 zonas + label textual.
- **Risk dial** — semicírculo 0-100 com pointer (Bloomberg Terminal-style).
- **Status pill** — sempre vem com ícone + label + tooltip.
- **Timeline rail** vertical com timestamps relativos (`2s ago`, `45s ago`, `1h ago`).
- **Source health chip** — discreto, no header da connector card, dot verde/amarelo/vermelho + uptime % no hover.

**Bordas, sombras, densidade:**
- Radius máximo 6 px (radius-xl). Sem `rounded-full` exceto pills/avatars. Densidade forense.
- Sombras quase inexistentes — elevação por contraste de surface (`#161a22 → #1d2230`), não por blur preto.
- Glow só em estado `running` (pulse sutil 1.2 s) e em `confidence_score ≥90`. Nunca decorativo.
- Spacing base 8 px mantido. Densidades: `compact (gap 4)`, `default (gap 8)`, `relaxed (gap 16)` — usuário escolhe via setting.

**Como evita IA genérica:**
- Sem gradientes coloridos. Sem `bg-gradient-to-br from-purple-500 to-pink-500`.
- Sem blur glassmorphism (já reduzir o atual `--color-surface-glass`).
- Sem floating cards com shadow-xl.
- Sem ilustrações 3D coloridas.
- Sem chatGPT-style messages bubbles. Sem emoji-driven copy.

**Como evita hacker exagero:**
- Sem cursor blink. Sem matrix-text. Sem terminal green.
- Mono usado só onde semanticamente é dado (IDs, hashes, IPs, URLs, timestamps). Body é proporcional.
- Sem `ASCII art` no UI.

**Como diferencia da OathNet:**
- OathNet = amber + dark + busca centralizada hero. Nós = ember + workspace lateral + caso como entidade.
- Voz: OathNet vende "data". Nós vendemos "confirmação" (anti-FP é o produto, não um feature).

---

### Conceito B — "Atlas Paper" (alternativa, light theme premium)

**Personalidade:** Editorial. Pinpoint/Substack/Notion premium. Para usuários que trabalham de dia, em monitor brilhante, e querem fugir do dark-SaaS exausto.

**Paleta light:**
```
Surface base       #f7f4ed   — bege papel reciclado, NÃO branco
Surface elevated   #ffffff
Border subtle      rgba(20, 28, 40, 0.06)
Border default     rgba(20, 28, 40, 0.10)
Text primary       #141c28   — tinta azul-escuro
Text secondary     #4a5468
Accent             #1a3a52   — azul-prussiano (não black, não royal blue)
Accent muted       rgba(26, 58, 82, 0.10)

Risk crit          #962826
Confidence high    #245a3a
Status blocked     #8b6e3c
```

**Prós:** Diferenciação total da categoria. Profissional, "investigador de jornal".
**Contras:** Dark mode obrigatório p/ trabalho noturno; manter dois temas = 1.6× custo CSS. Investigadores OSINT preferem dark majoritariamente.
**Decisão:** Não como tema principal — manter como **opção `theme=light` em v2** após design system maduro.

---

### Conceito C — "Prussian & Bronze"

**Personalidade:** Archive sofisticado. Botas pesadas, biblioteca antiga, instituição.

**Paleta:**
```
Surface base       #0c1e3a   — azul-prussiano profundo
Surface elevated   #142849
Accent             #a37c3f   — bronze antigo
Accent hover       #c1955a
Confidence high    #6b8e6e
Risk crit          #b04848
```

**Prós:** Linda esteticamente. Único.
**Contras:** Azul-prussiano cansa em sessão longa (mais vibração que graphite). Bronze contra azul é alto contraste mas pouco signal-friendly (parece "tema de game antigo" em demos). Muito autoral — risco de "lindo no Dribbble, ruim no dia-a-dia".
**Decisão:** Não.

---

### Comparação final

| Critério | A. Graphite & Ember | B. Atlas Paper | C. Prussian & Bronze |
|---|---|---|---|
| Diferenciação da OathNet | Alta | Total | Alta |
| Profissionalismo percebido | Alta | Alta | Média-alta |
| Fadiga visual sessão longa | Baixa | Média (light) | Média-alta |
| Custo de implementação | Baixo (refator de tokens) | Alto (2 temas) | Médio (rebrand) |
| "Não parece IA" | Sim | Sim | Sim |
| "Não parece cyberpunk" | Sim | Sim | Sim |
| Suporta novos conectores | Sim (modular) | Sim | Sim |
| Risk-friendly (sinais de cor) | Sim | Sim | Médio (bronze ≈ risk_med) |

**Recomendação:** **Conceito A — Graphite & Ember.** Implementar como tema padrão único no MVP visual; Atlas Paper (B) entra como `theme=light` futuro em v2 do redesign.

---

## 4. Arquitetura de telas

### 4.1 Inventário completo

| Tela | Existe hoje | Estado |
|---|---|---|
| Login | Sim | Refatorar visual |
| Register | Não | Não criar agora (admin cria users) |
| Landing pública | Não | **Adiar** — root atual sustenta auth/app. Criar só logged-out sign-in shell curto; marketing page fica fora do MVP visual. |
| Workspace (dashboard principal) | Não — é uma single-page index | **Criar incrementalmente** sob flag visual, sem renomear `index.html` no primeiro corte. |
| Nova investigação | Não isolado — é o hero | **Criar** como `/investigations/new` |
| Investigação em progresso (real-time) | Parcial — `scan-status` | **Preparar componentes agora; tela real espera `/api/v2/search/{id}/events`.** |
| Resultados / Investigação completa | Sim — painéis abaixo do search | **Refazer via adapter legacy primeiro; rota `/investigations/:id` espera job store.** |
| Caso/dossiê salvo | Side panel/localStorage metadata | **Melhorar agora; promover a `/cases/:id` só após backend persistente.** |
| Histórico | `historySection` bottom | **Mover** p/ sidebar persistente |
| Relatórios/exportações | Inline | Página dedicada `/cases/:id/export` |
| Perfil/Settings | Não | **Criar** `/settings` |
| Admin: dashboard | Sim | Refatorar c/ novos widgets real-time |
| Admin: usuários | Sim | Refatorar + plans/quotas tab |
| Admin: planos/quotas | Não | **Criar** |
| Admin: API keys | Não (usuário não tem keys próprias hoje) | **Criar** para v1 |
| Admin: logs/auditoria | Sim | Refatorar tabela |
| Admin: source health | Não | **Shell/empty state agora; dados reais só após `connector_metrics`.** |
| Admin: filas/workers/cache | Não | **Cache stats pode evoluir agora; Jobs/Queue espera `search_jobs`.** |
| Empty / loading / error | Inconsistente | **Padronizar** |
| 404 / 500 / maintenance (`READ_ONLY_MODE`) | Não dedicado | **Criar** |

### 4.2 Layout primário (autenticado)

```
┌─ TopBar (slim 44px) ──────────────────────────────────────────────────────┐
│  ⬡ NEXUSOSINT       [Cmd+K Quick search ▾]   [User ▾]                     │
├──────────────┬───────────────────────────────────────────────────────────┤
│              │                                                            │
│  Workspace   │   ACTIVE INVESTIGATION (or empty workspace)                │
│  ─────────   │                                                            │
│  ⊕ New       │                                                            │
│              │                                                            │
│  CASES (12)  │                                                            │
│   • Case A   │                                                            │
│   • Case B   │                                                            │
│   • Case C   │                                                            │
│              │                                                            │
│  RECENT      │                                                            │
│   • search 1 │                                                            │
│   • search 2 │                                                            │
│              │                                                            │
│  ─────────   │                                                            │
│  ◐ Settings  │                                                            │
│  ◑ Admin*    │                                                            │
└──────────────┴───────────────────────────────────────────────────────────┘
   240 px         flex 1
```

- Sidebar 240 px fixa em desktop ≥1280, drawer overlay em <1280.
- Top bar 44 px, sticky, contém Cmd+K global search (target lookup direto) + user menu.
- Sem hero gigante em nenhuma tela. Espaço é palco da investigação.
- **Quota pill OathNet sai do nav.** Vai p/ Settings > Plan & Quotas (não é primary info p/ user; é admin info).

### 4.3 Wireframes ASCII por tela

#### A) Workspace vazio (primeiro login)

```
┌─ TopBar ──────────────────────────────────────────────────────────────────┐
├──────────────┬───────────────────────────────────────────────────────────┤
│  Sidebar     │                                                            │
│              │           ┌─────────────────────────────────────┐         │
│              │           │  Start an investigation             │         │
│              │           │                                     │         │
│              │           │  ╭───────────────────────────────╮  │         │
│              │           │  │ username · email · phone …    │  │         │
│              │           │  ╰───────────────────────────────╯  │         │
│              │           │                                     │         │
│              │           │  [ Fast ]  [ Deep ]  [ Custom ]     │         │
│              │           │                                     │         │
│              │           │           [ Investigate → ]         │         │
│              │           └─────────────────────────────────────┘         │
│              │                                                            │
│              │     Last 3 closed cases     [View all]                    │
│              │     · case A  · case B  · case C                          │
│              │                                                            │
└──────────────┴───────────────────────────────────────────────────────────┘
```

#### B) Investigation in progress (real-time)

```
┌─ TopBar ──────────────────────────────────────────────────────────────────┐
├──────────────┬───────────────────────────────────────────────────────────┤
│  Sidebar     │ ◀ Back to workspace             Job #a1b2  · 00:12 elapsed │
│              │                                                            │
│              │ TARGET                                                     │
│              │ phone · +55 ⬢⬢⬢⬢⬢⬢⬢⬢ ⓘ (BR · TIM · mobile)              │
│              │                                                            │
│              │ ▰▰▰▰▰▰▰▰▰▰▰▰▰▱▱▱▱▱▱▱  60%   12 of 20 sources              │
│              │                                                            │
│              │ ┌─ CONNECTORS ──────────────────────────────────────────┐ │
│              │ │ ▣ found        ▢ running    ◌ blocked                 │ │
│              │ │ ───── ─────── ───── ─────── ─────── ─────── ─────── │ │
│              │ │ │carrier │whatsapp│telegram│apple_id│truecaller│… │ │
│              │ │ │ ▣ found│▢ run.. │ ▣ found│◌ block │ ✕ error  │  │ │
│              │ │ │ 95     │ 0→100  │ 88     │ —      │ —        │  │ │
│              │ │ │ 4 evid │ 2 sec  │ 3 evid │ rate-l │ timeout  │  │ │
│              │ │ └────────┴────────┴────────┴────────┴──────────┘   │ │
│              │ └─────────────────────────────────────────────────────┘  │
│              │                                                            │
│              │ ┌─ TIMELINE ────────────────┐  ┌─ EVIDENCE FEED ───────┐  │
│              │ │ 00:00 job created         │  │ carrier · country=BR  │  │
│              │ │ 00:01 carrier → found 95  │  │ carrier · type=mobile │  │
│              │ │ 00:03 telegram → found 88 │  │ telegram · t.me/+55…  │  │
│              │ │ 00:05 chain suggested:    │  │   resolved (200)      │  │
│              │ │       email via breach    │  │ telegram · @username  │  │
│              │ │ 00:08 apple_id → blocked  │  │   discovered          │  │
│              │ │ …                         │  │ …                     │  │
│              │ └───────────────────────────┘  └───────────────────────┘  │
│              │                                                            │
│              │ [ Pause ] [ Cancel ] [ Save as Case ]                     │
└──────────────┴───────────────────────────────────────────────────────────┘
```

#### C) Investigation complete (results)

```
┌─ TopBar ──────────────────────────────────────────────────────────────────┐
├──────────────┬───────────────────────────────────────────────────────────┤
│  Sidebar     │ ◀ Back        Job #a1b2  · completed 00:18  · cached 0/12  │
│              │                                                            │
│              │ ┌─ TARGET SUMMARY ─────────────────────────────────────┐  │
│              │ │ phone +55⬢⬢⬢⬢⬢⬢⬢⬢ ⓘ   ↗ chained: 1 email           │  │
│              │ │ ─────────── ───────────────────── ──────────────────│  │
│              │ │   RISK 67  │  CONFIDENCE 82      │  AGREEMENT 5/7    │  │
│              │ │   ▰▰▰▰▰▱   │  ▰▰▰▰▰▰▰▰          │  found by 5 of 7  │  │
│              │ │   high     │  high               │  sources          │  │
│              │ └──────────────────────────────────────────────────────┘  │
│              │                                                            │
│              │ Tabs: [ All ] [ Identity ] [ Breaches ] [ Network ] [ Social ] [ Raw ] │
│              │                                                            │
│              │ ┌─ IDENTITY ────────────────────────────────────────────┐ │
│              │ │ carrier_lookup ▣ found · 95                           │ │
│              │ │   country   Brazil                                    │ │
│              │ │   carrier   TIM S.A.                                  │ │
│              │ │   type      mobile                                    │ │
│              │ │   Evidence ▾                                          │ │
│              │ │                                                       │ │
│              │ │ telegram_resolve ▣ found · 88                         │ │
│              │ │   handle    @username                                 │ │
│              │ │   ↗ open https://t.me/username                        │ │
│              │ │   Evidence ▾ (3 signals)                              │ │
│              │ └──────────────────────────────────────────────────────┘  │
│              │                                                            │
│              │ ┌─ BREACHES ────────────────────────────────────────────┐ │
│              │ │ 12 breaches · 4 unique passwords · oldest 2017        │ │
│              │ │ [ table with filters: dbname, date, fields exposed ]  │ │
│              │ └──────────────────────────────────────────────────────┘  │
│              │                                                            │
│              │ [ Save as Case ]  [ Export ▾ ]  [ Run again ]             │
└──────────────┴───────────────────────────────────────────────────────────┘
```

#### D) Case / dossier

```
┌─ TopBar ──────────────────────────────────────────────────────────────────┐
├──────────────┬───────────────────────────────────────────────────────────┤
│  Sidebar     │ Case · "John Doe phone-led" · created 2026-05-18 by math  │
│              │ ───────────────────────────────────────────────────────────│
│              │ Notes  │  Investigations (3)  │  Targets  │  Export        │
│              │                                                            │
│              │ ┌─ TIMELINE OF INVESTIGATIONS ─────────────────────────┐  │
│              │ │ 1. phone +55⬢⬢⬢⬢⬢⬢⬢⬢   → found  17:12              │  │
│              │ │ 2. email j.d⬢@⬢⬢⬢.com  → likely 17:15 (chained)     │  │
│              │ │ 3. username johndoe…    → uncertain 17:22 (chained) │  │
│              │ └──────────────────────────────────────────────────────┘  │
│              │                                                            │
│              │ [ Run new investigation in this case ]                    │
│              │                                                            │
│              │ NOTES (markdown editor, autosaved)                        │
│              │ ┌──────────────────────────────────────────────────────┐  │
│              │ │ Subject confirmed in TIM carrier database…           │  │
│              │ └──────────────────────────────────────────────────────┘  │
└──────────────┴───────────────────────────────────────────────────────────┘
```

#### E) Source health (admin)

```
┌─ Admin TopBar ────────────────────────────────────────────────────────────┐
├──────────────┬───────────────────────────────────────────────────────────┤
│ Admin Sidebar│ Source Health  · last 24h                                  │
│              │                                                            │
│              │ ┌────────────────────────────────────────────────────────┐ │
│              │ │ Connector       Health  Latency p95  Block%  Error%   │ │
│              │ │ ─────────────── ──────  ───────────  ──────  ──────── │ │
│              │ │ sherlock:github ● 98%   1.2s         0%      2%       │ │
│              │ │ sherlock:tiktok ● 78%   3.1s         18%     4%       │ │
│              │ │ sherlock:linked ◐ 41%   5.8s         57%     2%       │ │
│              │ │ gravatar        ● 99%   0.3s         0%      1%       │ │
│              │ │ carrier_lookup  ● 99%   0.0s         0%      0%       │ │
│              │ │ oathnet:breach  ◐ 87%   1.9s         8%      3%       │ │
│              │ │ lab connectors  ◌ unavailable until compliance gate    │ │
│              │ └────────────────────────────────────────────────────────┘ │
│              │                                                            │
│              │ Click connector for: latency chart, last 100 runs,        │
│              │   baseline check status, rate-limit budget, IP rotation   │
└──────────────┴───────────────────────────────────────────────────────────┘
```

---

## 5. Fluxo ideal de uso

```
1. usuário entra em /
   → não-autenticado: sign-in shell curto (landing pública fica fora do MVP)
   → autenticado: workspace
2. workspace: input central + Fast/Deep/Custom + recent cases
3. usuário cola alvo "+55..."
   → detecção automática (TargetType.PHONE) com pill clicável p/ override
4. seleciona "Fast" (default) — gera ConnectorRequest p/ todos conectores ativos do tipo
5. clica Investigate
   → POST /api/v2/search → 201 {job_id} → navegação SPA p/ /investigations/{id}/live
   → antes do `/api/v2/search`, o mesmo componente roda em modo adapter com `/api/search` legado
6. live view:
   → conectores aparecem como grid (todos com status `pending`)
   → progressivamente cada um vira `running` → `found` / `likely` / `uncertain` / `blocked` / `error` / `not_found`
   → timeline rolando à direita (evidence feed)
   → progress bar topo (X de Y conectores)
   → kbd shortcut: S save-as-case; pause/cancel só depois do backend cooperativo
7. ao terminar:
   → auto-redirect p/ /investigations/{id} (results view)
   → toast "Done · 4 found · 1 blocked · 1 error" com action "Save as case"
8. results view:
   → target summary com Risk + Confidence + Agreement (3 medidores distintos)
   → tabs: All / Identity / Breaches / Network / Social / Raw
   → cada connector card expande p/ mostrar evidence drawer
9. usuário clica "Save as Case"
   → modal: case name, optional folder, optional notes
   → no MVP visual salva apenas metadata local; case persistente espera backend
10. usuário pode "Run new investigation in this case" (chain manual)
    OU clicar em chain_suggestion → nova investigation já vinculada
11. export:
    → PDF (com evidence completa, branded)
    → JSON (raw)
    → CSV (planificado por connector)
    → Link compartilhável (signed URL com TTL — v1)
12. histórico:
    → sempre acessível na sidebar
    → pesquisável por hash do alvo, data, status
```

---

## 6. Interface para real-time OSINT

### 6.1 Estados visuais por entidade

#### Job
| Estado | Cor | Ícone | Onde aparece |
|---|---|---|---|
| `queued` | tertiary | ◌ | live view topo + sidebar |
| `running` | accent (ember) | ▢ (pulsing 1.2s) | live view + sidebar |
| `completed` | confidence-high (green-musgo) | ✓ | results header + sidebar |
| `failed` | risk-crit | ✕ | live view + toast |
| `cancelled` | tertiary | ⊘ | results header + sidebar |

#### Source / Connector
| Estado | Cor | Ícone | Tooltip |
|---|---|---|---|
| `pending` | tertiary | ◌ | "Waiting in queue" |
| `running` | accent | ▢ (pulse) | "Querying source…" |
| `found` | confidence-high | ▣ | "Match confirmed" |
| `likely` | confidence-med | ▤ | "Match likely — confirm via evidence" |
| `uncertain` | confidence-med (border só) | ◇ | "Inconclusive — multiple signals disagree" |
| `not_found` | tertiary | □ | "No match found" |
| `blocked` | status-blocked (terra) | ⊘ | "Source blocked us (rate limit, captcha, auth wall)" |
| `error` | risk-crit | ✕ | "Source failed — see retry options" |

### 6.2 Componentes específicos real-time

**ConnectorCard:**
```
┌──────────────────────────┐
│ █ telegram_resolve   ⓘ   │  ← left border = status color; ⓘ = source health
│                          │
│ ▣ found              88  │  ← status + confidence (mono)
│ 3 signals · 1.2s         │
│                          │
│ ↗ @username              │  ← primary evidence preview
│ Evidence ▾               │  ← clickable drawer
└──────────────────────────┘
```

**ProgressBar (global):**
- Barra slim 2px topo da live view.
- Segmentada: cada conector = um segmento adjacente, cor = status.
- Não percentual fake; reflete real (running fica accent, completed verde, etc.).

**ConfidenceMeter:**
```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0
████████████████████████░░░░░░  82  high
████████████████████████████  100
```
4 zonas (none<30 / low<60 / med<85 / high≥85), label textual sempre.

**RiskDial:**
Semicírculo SVG 0-100. Pointer + label numérico + label categoria. Hover → breakdown ("12 breaches contribute 40 · 4 stealer logs contribute 27").

**EvidenceDrawer (lateral direito):**
- 320 px, slide-in.
- Lista signals do conector ativo: `signal_name · weight · detail`.
- Botão "Raw request" só aparece para admins e só se backend enviar payload sanitizado. Nunca mostrar corpo bruto com PII.

**SourceHealthChip:**
- Dot 6 px verde/amarelo/vermelho.
- Hover: "98% uptime · p95 1.2s · 12 runs/min".
- Antes de `connector_metrics`, mostra "health unavailable" e não finge uptime. Link admin só quando endpoint real existir.

**CacheBadge:**
- Pequeno chip "cached · 4m ago" abaixo do connector card quando `cache_hit=true`.
- Cor: blue muted. Discreto.

**FreshnessLine:**
- Sob cada result: `fetched_at: 17:12:08 UTC · 2 min ago`.

**RetryButton:**
- Aparece em conector `blocked` ou `error` ao hover.
- Tooltip explica retry cost (consome quota, novo IP via Thordata). Só habilitar quando backend tiver retry idempotente.

**LogToggle:**
- Sob a timeline: "Show technical logs ▾".
- Modo simples = só `connector_result` events.
- Modo avançado = só eventos que backend já sanitiza. Não expor proxy URL, target bruto, headers ou body.

### 6.3 Reconexão / partial results
- Live view escuta SSE com `Last-Event-ID` header → reconnect automático. Espera `/api/v2/search/{id}/events`.
- Cada SSE event carrega `seq` → frontend deduplica. No adapter legacy, dedupe é best-effort em memória.
- Se conexão cai >5s: badge "Reconnecting…" no header com countdown.
- Se job concluído enquanto desconectado: ao reconectar, replay rápido + auto-redirect p/ results.

### 6.4 Cancel
- Botão Cancel → modal confirma → DELETE /api/v2/search/{id}.
- Connectors em execução param cooperativamente; job marcado `cancelled`.
- Resultados parciais preservados.
- Esperar backend cooperativo. Não criar botão falso que só esconde UI.

---

## 7. Resultado OSINT ideal

### 7.1 Hierarquia visual de um resultado completo

```
LEVEL 1 — TARGET SUMMARY (acima da dobra)
   ├── Target (hash visible, full value behind "reveal" click + audit log)
   ├── Risk dial (0-100, breakdown on hover)
   ├── Confidence meter (0-100, derived from quorum)
   ├── Agreement count (X of Y sources)
   └── Chain breadcrumb (if chained from parent investigation)

LEVEL 2 — CATEGORY TABS
   [ All ] [ Identity ] [ Breaches ] [ Stealer Logs ] [ Network ] [ Social ] [ Raw ]
   ↑ tabs derivam de categories presentes nos ConnectorResults — não hardcoded

LEVEL 3 — CONNECTOR RESULTS (within tab)
   Each = ConnectorCard expandable
   Sorted by: confidence DESC, then status priority (found > likely > uncertain > blocked > error > not_found)
   "Hidden" not_found collapsed under "12 sources reported not_found ▾"

LEVEL 4 — EVIDENCE DRAWER (lateral)
   Per-connector signals + weights + details

LEVEL 5 — RAW (separate tab)
   JSON pretty-printed, copy-able
```

### 7.2 Separação por categoria — **derivada de connector metadata, não hardcoded**

Cada conector declara `category` no registry. Frontend agrupa dinamicamente. Categorias propostas:
- **Identity** — gravatar, github_email, carrier_lookup, mx_check
- **Social** — sherlock:* + maigret:* + linkedin/x/instagram
- **Communication** — whatsapp_qr, telegram_resolve, discord
- **Account Recovery Signals** — forgot_pwd_* (separado p/ contexto ético)
- **Breaches** — oathnet breach
- **Stealer Logs** — oathnet stealer + victims
- **Network & Domain** — oathnet ip_info, oathnet subdomain, spiderfoot
- **Gaming** — steam, xbox, roblox
- **Google** — ghunt

Categoria nova surge automaticamente se conector declarar — frontend não precisa update.

### 7.3 Estados especiais
- **Empty (0 results found):** ilustração discreta + sugestão de retry com Deep mode + lista de fontes que retornaram `blocked`.
- **All blocked:** banner topo "12 sources blocked us. Possible reasons: rate limit, captcha. Retry with proxy rotation?"
- **Mostly uncertain:** banner "Low confidence overall. Add corroborating target?"
- **High risk:** banner topo (não modal) "Subject has 12 breach exposures including recent. See Breaches tab."

### 7.4 Visualização de relações (chain graph) — v1
- Aba "Graph" opcional quando há ≥2 investigações vinculadas no mesmo caso.
- SVG simples: nodes = targets, edges = chain_suggestions executadas.
- Não Maltego full-graph (overkill); só breadcrumb visual.

---

## 8. Admin panel

**Regra de dependência:** admin pode ganhar polish visual agora, mas páginas com dados operacionais novos só entram quando endpoint backend real existir. Sem mock production-like.

### 8.1 Estrutura proposta

```
Overview
  ├── Dashboard              (KPIs realtime)
  ├── Activity feed          (audit log compact)
Management
  ├── Users                  (CRUD)
  ├── Plans & Quotas         (v2 — backend billing/tiers obrigatório)
  ├── API Keys (user-scoped) (v2 — backend key store obrigatório)
Infrastructure
  ├── Source Health          (pós-connector_metrics)
  ├── Jobs & Queue           (pós-search_jobs)
  ├── Cache                  (Redis stats, invalidate)
  ├── Workers                (TaskOrchestrator status, ceiling, degradation mode)
  ├── Costs                  (OathNet quota usage trend, Thordata bytes, etc.)
Compliance
  ├── Audit Logs             (search log + admin actions)
  ├── Data Retention         (TTL configs, manual purge)
Settings
  ├── Feature Flags          (v2 — backend config/admin audit obrigatório)
  ├── Alerts                 (Slack/email webhooks)
```

### 8.2 Widgets Dashboard
- Searches per hour (sparkline 24h)
- Active jobs (number) — só após `search_jobs`
- Queue depth (number, alert if >N) — só após fila/job store
- Memory pressure (current `degradation_mode`)
- Top 5 users by quota usage
- Top 5 connectors by errors — só após `connector_metrics`
- OathNet quota trend (line, 7d)
- Cache hit rate (line, 7d)

### 8.3 Source Health página
- Espera `connector_metrics`. Antes disso, criar apenas empty state honesto.
- Tabela connector × health × p50/p95/p99 latency × block% × error% × runs/h
- Click connector → detail page:
  - Latency chart (1h, 24h, 7d)
  - Last 100 runs com `status`, `target_hash`, `cache_hit`, `evidence_count`
  - Baseline check: shadow-mode results (false-positive estimado)
  - Rate-limit budget: current per-domain calls remaining
  - IP rotation: Thordata sticky session age, recent rotations
- Botões: pause connector, force baseline re-test, clear cache

### 8.4 Jobs & Queue
- Espera `search_jobs`/cancelamento cooperativo. Antes disso, não mostrar fila falsa.
- Tab Running / Queued / Failed (24h) / Completed (24h)
- Running: live status, elapsed, cancel button (admin override)
- Failed: error reason, retry button, owner, copy job_id
- Queued: TTL, position, cancel

### 8.5 Costs
- OathNet: quota consumed, breakdown por user, projected daily/monthly
- Thordata: bytes/day, alert se cruzar SOFT 500 MB
- Postgres storage: search_jobs + search_events size

### 8.6 Permissions
- Three roles: `viewer` (read-only), `analyst` (investigate), `admin` (full).
- Per-connector enable per-role (v2) exige backend authorization. Frontend apenas renderiza capabilities; nunca decide acesso.

---

## 9. Design system

### 9.1 Tokens (extensão do `tokens.css` atual)

```
# Surfaces — Graphite scale
--surface-0   #11141a
--surface-1   #161a22
--surface-2   #1d2230
--surface-3   #242a3a
--surface-glass  rgba(22,26,34,0.92)

# Borders
--border-1   rgba(255,255,255,0.05)
--border-2   rgba(255,255,255,0.09)
--border-3   rgba(255,255,255,0.15)

# Text
--text-1   #e8ecf3
--text-2   #9ba3b5
--text-3   #5d6478
--text-disabled  #353a4a

# Accent — Ember
--accent          #c4451d
--accent-hover    #d75432
--accent-muted    rgba(196,69,29,0.14)
--accent-border   rgba(196,69,29,0.32)
--accent-glow     rgba(196,69,29,0.18)

# Confidence
--conf-high       #6ba368
--conf-med        #c19443
--conf-low        #8b6a5e
--conf-none       #5d6478

# Status (8-state unificado)
--status-found       #6ba368
--status-likely      #c19443
--status-uncertain   #b7884a
--status-not-found   #5d6478
--status-blocked     #8b6a5e
--status-error       #c4451d

# Risk
--risk-crit  #b8332b
--risk-high  #c4451d
--risk-med   #c19443
--risk-low   #5d6478

# Typography
--font-display  'Inter Display', 'Inter', system-ui, sans-serif
--font-data     'IBM Plex Mono', 'JetBrains Mono', monospace
--font-body     'Inter', system-ui, sans-serif

# Scale (base 14, ratio 1.125)
--text-2xs  0.6875rem   # 11
--text-xs   0.75rem     # 12
--text-sm   0.8125rem   # 13
--text-md   0.875rem    # 14 (body default)
--text-lg   1rem        # 16
--text-xl   1.25rem     # 20
--text-2xl  1.625rem    # 26
--text-3xl  2.25rem     # 36 (only on landing / empty states)

# Spacing (8px base mantido)
--space-1..8  same

# Radius (mais tight)
--radius-xs   2px
--radius-sm   4px
--radius-md   6px
--radius-pill 999px
# Sem radius-xl. Sem cards "rounded".

# Shadows (subtle)
--shadow-1  0 1px 2px rgba(0,0,0,0.4)
--shadow-2  0 2px 6px rgba(0,0,0,0.5)
--shadow-3  0 4px 14px rgba(0,0,0,0.55)
# Sem shadow-glow decorativo. Só usar em :focus-visible.

# Motion (mais rápido — densidade)
--dur-1  90ms
--dur-2  150ms
--dur-3  240ms
--ease-out  cubic-bezier(0.16, 1, 0.3, 1)
```

### 9.2 Componentes (inventário)

| Componente | Variantes | Notes |
|---|---|---|
| Button | primary, secondary, ghost, danger, sm/md/lg, icon-only | Sem `rounded-full`. Border 1px sempre, fill só primary. |
| Input | text, search, with-prefix-icon, with-clear, disabled, error | Sem `rounded-lg`. |
| Select | native em desktop, custom dropdown em mobile | |
| Tabs | line-under (default), pill (only Cmd+K filter) | |
| Pill / Badge | neutral, accent, status (8 variantes), confidence (4) | |
| Card | flat (default), elevated | Sem gradient borders. |
| ConnectorCard | pending, running, found, likely, uncertain, blocked, error, not_found, cached | Composto: status border + title + score + evidence trigger |
| EvidenceItem | positive (+weight), negative (-weight), neutral, warning | List item em drawer |
| ConfidenceMeter | sm, md (default), lg | 4-zone bar |
| RiskDial | sm (chip), md (default semicircle) | SVG |
| StatusPill | 8 variantes + size sm/md | |
| ProgressBar | segmented, linear | |
| Timeline | vertical default, horizontal landing | |
| Toast | info, success, warning, error | bottom-right, max 3 stack |
| Modal | sm, md, lg, fullscreen | center, blur-bg light |
| Drawer | right (default), left (rare) | 320px / 400px / 50% |
| Table | dense (default), comfortable | sticky header, sortable, filter row optional |
| Empty State | illustration + text + CTA | 4 ilustrações: search, results, error, locked |
| Skeleton | line, block, card, table-row | shimmer subtle |
| Tooltip | hover (≤200ms delay), click (sticky) | usa atributo `data-tooltip` |
| Kbd | inline `<kbd>` styled | Cmd+K, ↵, ESC |
| Avatar | letter, image, with-status-dot | radius-pill |
| Tag | clickable, removable | input multi-tag p/ case folders |
| Switch | sm, md | toggle settings, "Show technical logs" |
| Banner | info, warning, critical | full-width topo de view, dismissible |
| Sidebar Nav | item, item-with-badge, section-label | |
| Logo Mark | full, mark-only, mono | |

### 9.3 Risk badge / confidence indicator / source status — sempre 3 distintos

Erro frequente em SaaS OSINT: misturar risco com confiança. Aqui são entidades visualmente diferentes:

- **Risk** = dial 0-100. Único elemento que usa `--risk-*` palette. Aparece 1× no target summary header.
- **Confidence** = meter 0-100 com 4 zonas. Usa `--conf-*` palette. Aparece 1× no target summary + 1× por connector card.
- **Source status** = pill com ícone+label. Usa `--status-*` palette. Aparece em todo connector card.

Nunca usar a mesma cor pra dois.

---

## 10. Conteúdo e copywriting

### 10.1 Voz da marca

**Personalidade:** Calmamente confiante. Forense, não promocional. Especificidade > superlativo. Mostra o trabalho.

**Não:**
- "Find anything on anyone, instantly"
- "AI-powered investigations"
- "Search smarter"
- "Unlimited intelligence at your fingertips"

**Sim:**
- "Confirme. Não suponha."
- "Investigations with evidence — not guesses."
- "Every signal sourced. Every result traceable."

### 10.2 Copy por tela (proposta — pt-BR e en-US, decidir locale default)

**Landing pública** (logged out)
> NexusOSINT
> Plataforma de investigação OSINT focada em evidência.
> Username, email, telefone — múltiplas fontes, score de confiança, trilha auditável.
> [ Entrar ]
> (sem CTA "Try free"; produto é fechado/B2B)

**Login**
> Entre para continuar.
> [ usuário ] [ senha ] [ Entrar ]
> Sem mensagens "Welcome back!". Discreto.

**Workspace vazio (primeira vez)**
> Comece uma investigação.
> Cole um username, email ou telefone.
> Modo Fast roda 5 fontes em <10s. Deep roda todas.

**Workspace vazio (returning)**
> 12 casos · 47 investigações nos últimos 30 dias
> [ Nova investigação ]

**Search input placeholder**
> "username · email · telefone · IP · domínio"
> (sem "instantly", sem "smarter")

**Investigation in progress**
> "Investigando ⬢⬢⬢⬢⬢⬢⬢⬢ · 12 de 20 fontes"
> (sem "Scanning…", sem "AI is working its magic")

**Result · all blocked**
> "Nenhuma fonte conseguiu responder. 14 retornaram bloqueio (rate limit ou captcha). Tente Deep mode (rotaciona IP) ou aguarde 5 min."

**Result · high risk**
> "Alvo aparece em 12 vazamentos · senha exposta mais recente: 2024-03-14."
> (factual; sem "URGENT" ou exclamações)

**Empty state · no cases yet**
> "Nenhum caso salvo. Cases agrupam investigações relacionadas a um alvo ou pessoa."
> [ Saiba mais ] [ Nova investigação ]

**Error · connector failed**
> "telegram_resolve falhou após 8s (timeout). Tente novamente ou pule esta fonte."
> [ Retry ] [ Skip ]

**Admin · source unhealthy**
> "linkedin (sherlock): 57% de bloqueio nas últimas 24h. Possível causa: detecção de bot. Considere desabilitar temporariamente."

**Export**
> "Exportar relatório"
> "PDF · com evidências, branded, ~3 páginas"
> "JSON · raw, todos os signals"
> "CSV · planificado, 1 linha por fonte"

**Source health (admin)**
> "98% saudável · p95 1.2s · 0% bloqueios"
> (números primeiro; explicação no hover)

**Real-time connector status (live view)**
> Pills curtos: "found", "blocked", "error · timeout", "blocked · captcha", "running · 2s"

---

## 11. Responsividade

### Breakpoints
```
xs   <  480   (mobile compacto)
sm   ≥  480   (mobile grande)
md   ≥  768   (tablet)
lg   ≥ 1024   (desktop pequeno)
xl   ≥ 1280   (desktop padrão — sidebar fixa começa aqui)
2xl  ≥ 1536   (desktop wide — evidence drawer pode ficar fixa)
```

### Desktop (lg+) — experiência completa
- Sidebar 240px fixa, evidence drawer 320px on-demand
- Tudo investigation-grade: live view, timeline, evidence side-by-side
- Cmd+K global search
- Keyboard shortcuts: N (new), C (cancel), S (save case), / (focus search), Esc (back)

### Tablet (md, 768-1023)
- Sidebar vira ícones (60px) com tooltips, expande no hover
- Evidence drawer overlay em vez de side-by-side
- Tabs scrolláveis horizontalmente se overflow

### Mobile (xs/sm, <768)
- **Não tentar replicar workspace inteiro.** Foco em consumo.
- Telas mobile prioritárias:
  1. Workspace simples: input + Fast/Deep + último caso aberto
  2. Live view simplificada: progress + 5 últimos events em feed
  3. Result view: target summary + tabs scrolláveis + connector cards stacked
  4. Case list: lista vertical com badge counts
  5. Quick export: PDF/JSON
- **Não disponível em mobile:** evidence drawer (mostra inline), admin panel (block com mensagem "Use desktop"), graph view
- Bottom nav 4 tabs: Workspace · Cases · History · Settings

### Touch
- Min 44×44 px targets
- Hover-only tooltips substituídos por tap-to-reveal
- Swipe right em connector card → reveal "retry / skip" actions

---

## 12. Stack e abordagem técnica

### 12.1 Análise honesta

Trade-off central: **Vanilla JS atual vs React/Next.**

| Critério | Vanilla atual | Migrar React/Next | Reescrever leve em HTMX + Alpine |
|---|---|---|---|
| Velocidade de desenvolvimento de connector cards dinâmicos | Lenta (DOM manual) | Rápida (declarativa) | Média |
| Reuso de componentes do design system | Difícil (template literals) | Trivial (componentes) | Médio (slots) |
| Performance em VPS 4 GB | Excelente (zero bundle) | Boa (Next SSR ou React SPA bundle 80-150 KB) | Excelente |
| Time-to-first-paint | Ótimo (HTML estático) | Bom (SSR) ou regular (SPA) | Ótimo |
| SSE streaming com partial render | Funciona | Funciona (react-use-event-source) | Funciona |
| Custo migração | $0 | Alto: reescrever 11 JS files (~3 648 LOC) + 11 CSS | Médio |
| Atratividade p/ contratar dev futuro | Baixa (vanilla é nicho) | Alta | Média |
| Vendor lock-in framework | Zero | Médio (React/Next ecosystem) | Baixo (HTMX leve) |
| Compatibilidade com motor real-time OSINT (SSE-heavy, dynamic connector cards) | Custo manual alto pra dinâmica | Natural | OK com `hx-sse` |
| Risco de quebrar features existentes durante refator | Alto se reescrever, baixo se incremental | Alto (cutover) | Médio |

**Decisão recomendada — incremental, em 3 estágios:**

1. **Estágio 0 (agora):** **Refatorar Vanilla atual.** Manter HTML/CSS/JS estático. Reescrever só CSS (tokens + componentes novos) + adicionar `static/js/components/` com factories que produzem DOM via template literals tipados (TS opcional via JSDoc). Custo baixo, risco baixo, encaixa hoje.

2. **Estágio 1 (junto com MVP do motor real-time):** Avaliar **Lit (Web Components)** para componentes dinâmicos críticos: `<connector-card>`, `<evidence-drawer>`, `<confidence-meter>`, `<risk-dial>`. Se usar Lit, vendor local pinado ou bundle próprio; **sem CDN** por CSP/hardening. Compatível com vanilla, sem migração big-bang. Componentes reutilizáveis no main e no admin.

3. **Estágio 2 (se/quando demanda):** Avaliar React+Vite se complexidade crescer (graph view, drag-drop case organization, multi-pane workspace). **Não decidir agora.**

**Não recomendado:**
- **shadcn/ui:** depende de React + Tailwind + Radix. Migração big-bang. Estética genérica "shadcn-look" que o usuário pediu pra evitar. Reuso = baixa diferenciação.
- **Tailwind direto:** atrasa adoção do design system (devs pulam tokens, usam utilities ad-hoc). Manter CSS modular com tokens é melhor pra um produto com identidade.
- **Next.js full:** SSR não traz benefício hoje (zero SEO need — produto fechado). Bundle Next = ~85 KB JS antes do app code. Overhead sem retorno.
- **Migrar p/ React Vite agora:** custo de migração 3 648 LOC JS + paralisação de feature dev durante 3-4 semanas.

### 12.2 Bibliotecas que valem
- **Lucide Icons** — SVG sprites, 1 família única, lazy import via `<svg>` direto inline.
- **Lit** (Estágio 1) — web components, 5 KB.
- **Chart.js** — admin charts (já leve, sem rival prático).
- **date-fns** ou **dayjs** — formatação `2 min ago`. 2-7 KB.

### 12.3 Build tool
- Manter sem build tool no Estágio 0 (CSS plain, JS plain).
- Estágio 1: opcional `esbuild` script p/ minify CSS+JS em produção (script Python ou Node 1-liner). Não webpack/vite.

---

## 13. Arquivos a alterar/criar/remover

### 13.1 Criar
```
static/css/
  design-tokens.css          # NOVO master tokens (substitui tokens.css em escopo)
  components/
    button.css
    input.css
    pill.css
    connector-card.css
    confidence-meter.css
    risk-dial.css
    timeline.css
    evidence-drawer.css
    sidebar.css
    topbar.css
    skeleton.css
    empty-state.css
  themes/
    graphite-ember.css       # Conceito A (default)
    atlas-paper.css          # Conceito B (v2, opcional)

static/js/components/        # NOVO — DOM factories (estágio 0) → Lit (estágio 1)
  connector-card.js
  evidence-drawer.js
  confidence-meter.js
  risk-dial.js
  status-pill.js
  timeline.js
  cmd-k.js                   # global quick search
  shortcuts.js               # keyboard shortcuts

static/js/views/             # NOVO — view controllers
  workspace.js
  investigation-live.js
  investigation-results.js
  case-detail.js
  history.js
  settings.js

static/js/admin-views/       # NOVO
  source-health.js
  jobs-queue.js
  costs.js
  api-keys.js
  plans-quotas.js
  feature-flags.js

static/                      # NOVO páginas — criar incrementalmente, não renomear index no primeiro corte
  workspace.html
  investigation-live.html
  investigation-results.html
  case.html
  history.html
  settings.html
  landing.html               # pós-MVP visual; início usa sign-in shell existente
  errors/
    404.html
    500.html
    maintenance.html

static/assets/
  icons/                     # Lucide SVG sprite ou individual
  illustrations/             # empty states (4 SVGs únicos, autorais)
  logo/
    mark.svg
    full.svg
    mark-mono.svg
```

### 13.2 Alterar
```
static/index.html            → manter no primeiro corte; criar shell autenticado sob flag visual antes de qualquer rename
static/admin.html            → mudar p/ shell de admin SPA simples (sidebar + main routes)
static/css/tokens.css        → manter como compat shim → re-exports design-tokens.css
static/css/{panels,cards,components,tables}.css
                             → DESCONTINUAR gradualmente em favor dos componentes novos
static/js/render.js          → quebrar em renderers por categoria (após estágio 1)
static/js/search.js          → renomear p/ legacy-search.js; novo investigation-* assume
static/js/admin.js           → quebrar por section (estágio 1)
```

### 13.3 Remover (após migração estágio 0 + 1 concluída)
```
static/css/panels.css        # substituído por components/
static/css/cards.css         # idem
static/css/components.css    # idem (nome ruim, conflito de namespace)
static/css/security-hardening.css  # avaliar se ainda relevante; integrar nos tokens
```

### 13.4 Ordem segura
1. **Estágio 0 sem quebra:** criar `design-tokens.css` em paralelo, gate por feature flag query string (`?ui=v4`). Velho continua funcionando.
2. **Refatorar UMA tela por sprint** sob feature flag: workspace primeiro (mais valor), depois investigation-live, depois results, depois admin.
3. **Connector card** = primeiro componente novo (essencial p/ motor real-time). Implementar antes do motor via adapter legacy; mock só em demo/test.
4. **Cutover por tela:** quando v4 dessa tela aprovado em staging, remover v3 daquela tela.
5. **Não migrar admin antes do main app.** Admin tem menos uso e é menos crítico.

### 13.5 Mudanças que podem ser feitas **agora** (sem aguardar motor real-time)
- Refator de tokens (Graphite & Ember)
- Sidebar persistente (deslocar histórico p/ lá)
- Hero copy + redesign workspace empty state
- ConnectorCard component (com adapter legacy; mock só em demo/test)
- ConfidenceMeter + RiskDial
- Lucide icons cleanup (substituir todos SVGs custom + emojis)
- Cmd+K
- Empty/error/loading states padronizados
- Admin Source Health shell com empty state honesto ("metrics unavailable until connector_metrics exists")

### 13.6 Mudanças que **devem esperar** o motor real-time
- Live view com SSE replay/reconnect (precisa de `search_events` table)
- Job lifecycle UI (queued/running/etc — precisa `search_jobs`)
- Chain suggestion UI (precisa `chain_suggestion` event no SSE)
- Multi-target chained investigations (precisa `parent_job_id` na DB)
- Evidence drawer com signals do backend (precisa `Evidence[]` chegar ao client — só sherlock_v2 envia hoje)
- Source health agregado real (precisa `connector_metrics` table)
- Jobs & Queue real (precisa `search_jobs` + cancelamento cooperativo)
- Cases/dossiês persistentes (precisa API/server-side storage)

---

## 14. Roadmap

### Fase 0 — Auditoria visual + preparação (1-2 dias)
- Confirma decisão Math sobre direção visual (A/B/C)
- Setup feature flag `?ui=v4` global
- Criar `static/css/design-tokens.css` e `static/css/components/` vazios
- Aprovar paleta + fontes (preview no Figma se quiser ou HTML prototype 1-page)
- Confirmar que `?ui=v4` é flag visual apenas, sem controle de permissão/feature paga.

**Saída:** decisão + skeleton de arquivos.

### Fase 1 — Quick wins sem quebrar nada (3-5 dias)
- Lucide icons substituem emojis + SVGs ad-hoc no main + admin (sem mudar layout)
- Hero copy reescrita ("Confirme. Não suponha.")
- Quota pill sai do nav (vai p/ settings — admin only)
- Histórico ganha "search" e ordenação no painel atual
- Risk badge ganha tooltip explicando breakdown
- Empty states padronizados (4 ilustrações novas)
- Bug pass: padronizar cache-busting `?v=` por sessão única

**Saída:** main + admin com cara consistente, sem refator estrutural.

### Fase 2 — Redesign da experiência principal atual (1-2 semanas)
- Sidebar permanente no main app (workspace)
- Workspace empty state + new-investigation flow
- Topbar nova (Cmd+K, user menu, sem quota)
- Refator CSS: tokens + components/ assumem o trabalho de panels.css/cards.css
- Investigation-results view (substitui results inline atual)
  - Target summary header com 3 medidores (risk + confidence + agreement)
  - Tabs derivadas de categories presentes
  - ConnectorCard como unidade visual
  - Evidence drawer com evidence real quando existir; empty state quando ausente
- Case metadata view (não dossiê persistente ainda)
- History como view dedicada

**Saída:** main app redesenhado, motor antigo ainda alimenta. Zero regressão de feature.

### Fase 3 — Preparar UI para real-time OSINT (paralelo ao MVP do motor — 2 semanas)
- Live view com SSE consumer + reconnect (testado contra novo `/api/v2/search`)
- Connector cards consomem `connector_result` events reais
- Confidence/risk/status pills usam dados reais do `ConnectorResult` schema
- Pause/cancel/save-as-case actions wired
- Evidence drawer recebe `Evidence[]` real

**Saída:** live view real-time funcional contra MVP do motor.

### Fase 4 — Redesign dos resultados OSINT (1 semana)
- Categorização dinâmica por `connector.category`
- Hidden not_found expansível
- Banner conditionals (all blocked, mostly uncertain, high risk)
- Empty state per tab
- Filter row em tabela de breaches

**Saída:** results refinados, polidos.

### Fase 5 — Admin panel completo (2 semanas)
- Sidebar reorganizada (Overview/Management/Infrastructure/Compliance/Settings)
- Dashboard novos widgets que já têm backend (memory pressure/cache/quota/logs)
- Source Health página só após `connector_metrics`
- Jobs & Queue página só após `search_jobs`
- Cache página
- Workers página
- Costs página
- Plans & Quotas (v2, backend/billing primeiro)
- API Keys (v2, backend key store primeiro)
- Feature Flags toggles (v2, backend audit/config primeiro)

**Saída:** admin pro-grade.

### Fase 6 — Integração visual com jobs/workers/conectores real-time (paralelo a v1 do motor — 2 semanas)
- Chain suggestion UI (banner inline + auto-link em case)
- Multi-target case timeline
- Source health histórico real (24h/7d charts)
- Connector marketplace stub (v2)

**Saída:** UI suporta toda capacidade do v1 do motor.

### Fase 7 — Refinamento premium (1-2 semanas)
- Microinterações (sem cyberpunk): focus rings consistentes, transition curves uniformes, ease tuning
- Animações de entrada por seção (≤150ms, ease-out)
- Responsividade tablet + mobile finalizada
- Acessibilidade pass (WCAG 2.2 AA): keyboard nav, ARIA, screen reader sweep
- Performance pass: lazy load components, CSS critical path
- Dark theme refinement + opt-in Atlas Paper (v2)
- Documentação design system (storybook ou MDX simples)

**Saída:** produto premium pronto p/ demo.

**Duração total estimada:** 8-10 semanas calendário (parte em paralelo ao motor).

---

## 15. Critérios de qualidade — gate de aprovação

Checklist usado pra dizer "redesign está bom":

- [ ] Parece produto próprio? Comparar lado-a-lado com OathNet, IntelX, Snusbase — diferenciação visual imediata em <3s de olhar.
- [ ] Parece SaaS premium? Comparar com Linear, Stripe Dashboard, Pinpoint — paridade percebida.
- [ ] Reduz poluição? Single-page → multi-tela hierárquica.
- [ ] Mostra valor do anti-FP? Confidence + Evidence visíveis em todo resultado.
- [ ] Diferencia da OathNet? Vocabulário ("investigação" não "search"), copy, paleta, layout — sim em todos.
- [ ] Não parece gerado por IA? Sem gradientes purple/pink, sem ilustrações 3D, sem chatbot UI.
- [ ] Preparado para real-time? Connector cards, status 8-state, evidence empty state e source-health shell existem; dados reais só quando backend existir.
- [ ] Suporta novos conectores sem redesign? Connector card é genérica + categoria derivada do registry.
- [ ] Evidência/risco/confiança são distinguíveis? 3 cores diferentes, 3 representações diferentes, 3 locais diferentes.
- [ ] Mobile usável p/ consumo (não investigação completa)? Workspace + live + result + cases acessíveis.
- [ ] Acessível? WCAG 2.2 AA mínimo. Contrast ≥4.5:1 corpo, ≥3:1 UI; foco visível; keyboard nav completa.
- [ ] Zero regressão de feature existente após cutover de fase.
- [ ] Zero mock production-like em admin/live/results. Mock apenas em demo/dev/test.
- [ ] Performance: time-to-interactive <2s em 3G simulado p/ workspace.
- [ ] CSS bundle gzipped ≤40 KB (estágio 0/1). JS ≤80 KB (estágio 1 com Lit).
- [ ] Lighthouse: Performance ≥85, Accessibility ≥95, Best Practices ≥95.

---

## 16. O que NÃO fazer

- Gradientes coloridos decorativos (`bg-gradient-to-br from-* to-*`)
- Glassmorphism / heavy blur — manter glass só em modais (8-12 px blur max)
- Floating action buttons grandes
- Ilustrações 3D coloridas / mascotes IA
- Cyberpunk / Matrix / Hacker green / Terminal cursor blinking
- Cursor "█" piscando (remover do scan-status atual)
- Mistura emoji + SVG icons
- Múltiplas famílias de ícones
- shadcn/ui copy-paste
- Tailwind utilities ad-hoc sem tokens
- CDN para runtime UI libs (CSP/hardening; vendor local ou bundle)
- Métricas mockadas em telas admin como se fossem reais
- Botões de cancel/retry que só escondem UI sem backend cooperativo
- Modal centralizado p/ tudo (preferir drawer p/ contexto adjacente)
- Esconder evidências atrás de "Show more" sem destaque — evidence é o produto
- Misturar breach/stealer/social num único feed sem categoria
- Cores de risco usadas pra UI neutra (usar text/border tokens)
- Status `blocked` colorido igual a `error` (são semanticamente distintos)
- UI rígida que assume hoje (5 painéis fixos) — connector card genérica
- Telas que serão refeitas com motor real-time — Live view só faz sentido depois do MVP do motor
- Quebrar /admin existente antes do main estar redesenhado
- Hero copy genérica ("Find anything", "AI-powered", "Smarter searches")
- Quota pill no nav (info de admin, não usuário)
- Sem dark mode (mas tampouco forçar light obrigatório)
- Tipografia ultralight ou black weights (legibilidade ruim, estética IA)
- Animações pesadas (≥350ms ou pulses em loop infinito)
- Cyber-fonts (Orbitron, Audiowide, etc — clichê hacker)

---

## Conceitos visuais — comparação final

| Aspecto | A. Graphite & Ember (recomendado) | B. Atlas Paper | C. Prussian & Bronze |
|---|---|---|---|
| Surface | Graphite 95 quente | Bege papel | Azul-prussiano |
| Accent | Ember vermelho-tijolo | Azul-prussiano | Bronze antigo |
| Sessão longa | Excelente | Boa (light) | Cansa |
| Diferenciação OathNet | Alta | Total | Alta |
| Custo implementação | Baixo | Alto (2 temas) | Médio |
| Compat sinais de cor | Boa | Boa | Confunde com bronze |
| Mood | Forense profissional | Editorial premium | Archive sofisticado |
| Risco "dribbble-only" | Baixo | Baixo | Alto |

**Recomendação final:** Conceito A como tema principal único no MVP visual. Conceito B (Atlas Paper) entra como **opção `theme=light` em v2**.

---

## Como este redesign se adapta ao futuro motor real-time OSINT

O motor descrito em `REAL_TIME_OSINT_PLAN.md` introduz:
- `Connector` ABC com `ConnectorResult` (status 8-state + confidence_score + evidence + raw_url sanitizado)
- `search_jobs` + `search_events` Postgres (job lifecycle persistente)
- SSE com replay/reconnect (eventos: `job_started`, `connector_started`, `connector_result`, `progress`, `summary`, `chain_suggestion`, `done`)
- `connector_metrics` agregado horário
- Quórum + agregação de status com regras anti-FP

**Mapeamento direto:**

| Backend (REAL_TIME_OSINT_PLAN.md) | UI (este plano) |
|---|---|
| `ConnectorRequest/Result` schema | `ConnectorCard` componente — recebe `ConnectorResult` 1:1 |
| `ConnectorStatus` enum (8-state) | `StatusPill` para `pending/running/found/not_found/likely/uncertain/blocked/error` com `--status-*` tokens |
| `confidence_score` 0-100 | `ConfidenceMeter` 4-zone bar |
| `Evidence[]` | `EvidenceDrawer` (lateral right) |
| `search_jobs.status` (queued/running/done/failed/cancelled) | Job state UI (live view + sidebar item state) |
| `search_events` append-only com `seq` | SSE consumer com `Last-Event-ID` reconnect |
| `chain_suggestion` event | Banner inline na live view + auto-link em case timeline |
| `connector_metrics` agregado | Admin Source Health página + Dashboard widgets |
| `connector.category` no registry | Tabs derivadas dinamicamente nos results |
| `cache_hit=true` no `ConnectorResult` | `CacheBadge` na connector card |
| `fetched_at` timestamp | `FreshnessLine` no result |
| `BLOCKED` distinto de `ERROR` | 2 status pills diferentes, cores diferentes |
| Quórum mínimo p/ `found` | Banner "Low confidence — N of M agree" + Agreement count no header |
| Job persistente | Cases page + history + chained_jobs UI |
| `DELETE /api/v2/search/{id}` (cancel) | Cancel button cooperativo na live view |
| `?from_seq=N` replay | Reconnecting banner com countdown |

**Princípios garantidos:**
1. UI **não assume** lista fixa de conectores. Tudo descoberto runtime via `connectors_planned` no `job_started` event.
2. UI **não distingue** username vs email vs phone no layout de live/result — só no detection inicial.
3. UI **mostra evidence sempre** — anti-FP é o produto.
4. UI **reflete graceful degradation** — status `blocked` ≠ `error`, retry/skip/pause como ações primárias.
5. UI **suporta job offline** — fecha aba, reabre amanhã, vê resultado completo (TTL).
6. UI **mostra freshness** — usuário sempre sabe se viu cache ou real-time.
7. UI **escala visualmente** — 5 conectores ou 50 conectores, mesma estrutura (grid responde).

**Garantias de não-quebra:**
- Fase 2 do redesign roda contra `/api/search` v1 (motor antigo) usando ConnectorCard com adapter dos resultados legacy; mock só em demo/test.
- Fase 3 troca o consumer pra `/api/v2/search` quando MVP do motor estiver pronto.
- Endpoint legacy mantém funcionando em paralelo até v1 do motor estabilizado em produção 7 dias.

---

**Fim do plano. Próximo passo:**
1. Math escolhe Conceito A / B / C (sugestão: A — Graphite & Ember).
2. Math aprova fase 0 (preparação) — pode iniciar antes do motor, limitada a tokens/shell/componentes/adapter legacy.
3. Sessão Sonnet abre branch `v4.1/visual-redesign-fase-0` e executa fase 0.
4. Depois de fase 0, fase 1 (quick wins) inicia.
