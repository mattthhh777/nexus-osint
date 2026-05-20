# R2 — Post-R1 Visual Delta

**Status:** R2-0 planning artifact. No code touched.
**Branch:** `r2/signal-ui-foundation`
**Base canonical:** `agora/VISUAL_REDESIGN_PLAN.md` (Conceito A — Graphite & Ember).
**Date:** 2026-05-20.
**Author:** sessão Opus.

This document re-grounds `VISUAL_REDESIGN_PLAN.md` against the state shipped by
R1 (job store, connector contract, opt-in v2 search, SSE replay). It does **not**
introduce new backend, schema, or auth behavior. It does not start
implementation. R2-1 has not begun.

The React mockup "Nexus Redesign Mockup" referenced by Math is treated as a
**visual brief**, not a stack target. Frontend stays vanilla HTML/CSS/JS.

---

## 0. R1 baseline — what already exists

Reading the working tree confirms R1 already shipped most of the "Stage 0"
infrastructure the visual plan called for:

| Artifact | Path | Purpose |
|---|---|---|
| Graphite theme flag | `static/js/theme-flag.js` | `?theme=graphite` → adds `nx-v2` class, loads tokens + connectors css |
| Graphite tokens | `static/css/tokens-graphite.css` | Scoped to `:root.nx-v2` |
| Connector CSS | `static/css/connectors.css` | `.nx-v2` scoped components |
| Status pill | `static/js/components/status-pill.js` | 8-state pill |
| Confidence meter | `static/js/components/confidence-meter.js` | 0-100 + level |
| Evidence drawer | `static/js/components/evidence-drawer.js` | Lateral panel |
| Connector card | `static/js/components/connector-card.js` | ConnectorResult-shaped |
| Legacy adapter | `static/js/legacy-adapter.js` | Maps legacy SSE → ConnectorResult 8-state |
| V2 search bridge | `static/js/v2-search.js` | POST `/api/v2/search`, opt-in via `?engine=v2` |
| Job replay | `static/js/job-replay.js` | SSE consumer with `from_seq` reconnect |

Live frontend (`static/index.html`) still renders the **legacy** hero + five
hardcoded panels (Breach, Stealer, Social, Email, Extras) regardless of flag.
The graphite path is loaded but the layout does not yet use the new components
as primary surface. R2 closes that gap.

---

## 1. What of `VISUAL_REDESIGN_PLAN.md` stays valid

Carried forward unchanged:

- **Conceito A — Graphite & Ember** as the only theme for R2 (Atlas Paper
  remains deferred).
- **Three distinct indicators**: risk dial, confidence meter, source status —
  separate palettes, separate elements.
- **8-state status semantics** (`pending/running/found/likely/not_found/uncertain/blocked/error`).
  Already enforced backend-side via `modules/connectors/base.py` and adapter.
- **Connector card as unit of presentation**, with category derived from
  metadata, not hardcoded.
- **Evidence-first principle**: nothing positive without evidence drawer reach.
- **Density forensic**, radius ≤ 6px (except pills), no glassmorphism, no
  gradients, no cyber clichés.
- **Lucide as single icon family** — still not adopted; emoji icons (📁, 📋)
  remain in `index.html` and must be cleaned before R2 ships.
- **Voice**: "Confirme. Não suponha." already adopted in `index.html` hero —
  keep.
- **Section 16 "O que NÃO fazer"** stays canonical.
- **Section 9 token definitions** match `tokens-graphite.css` 1:1.
- **Section 13.5 "mudanças que podem ser feitas agora"** — most of these are
  R1-done. R2 uses them as building blocks, not new work.

---

## 2. What changed because R1 already shipped

Re-baselining the original plan:

| Original assumption | R1 reality | R2 consequence |
|---|---|---|
| Flag named `?ui=v4` | Implemented as `?theme=graphite` (cookie sticky 30d) | R2 introduces a **second** flag `?ui=signal` for layout/page-structure changes; theme flag stays orthogonal |
| "Build connector card later" | Already in `static/js/components/connector-card.js` and consumed by `v2-search.js` live grid | R2 reuses it, does not rebuild |
| "Adapter visual para legacy" | `legacy-adapter.js` already maps legacy → ConnectorResult 8-state | R2 wires it into the signal layout |
| "SSE replay/reconnect espera motor real-time" | `job-replay.js` + `/api/v2/search/{id}/events?from_seq` already work | R2 can render real live results behind `?engine=v2&ui=signal` |
| "Estágio 0 = só refator de tokens" | Tokens already shipped, opt-in | R2 starts at the original Stage 1 (layout + components) without breaking Stage 0 |
| "Cases persistentes esperam backend" | Still localStorage; no `cases` table | R2 keeps localStorage; visual treatment honest about it |
| Search target_value persisted | G1 = hash-only + 7d TTL; v2 frontend does **not** write raw targets to history | R2 history view must respect this for v2 entries |
| Job lifecycle UI | `search_jobs.status` exists; cooperative cancel does NOT | R2 shows job state read-only; no cancel button until backend cooperates |
| Connector metrics UI | `connector_metrics` table does NOT exist | R2 admin Source Health stays the same empty-state shell as the canonical plan demands |
| Single-source `found` | G3 demotes to `likely` on backend | R2 layout must show `likely` distinct from `found` — never the same green |
| `TargetType.IP` | Not introduced in R1 by G2/G4 constraints | R2 does NOT add IP target type; placeholder still says "username · email · phone" only for v2 path |
| Gravatar | G2 — deferred | R2 must not display Gravatar avatars or hash email to gravatar.com |

---

## 3. What can now be implemented with real data

All of these have a real R1 endpoint or schema to bind against:

- **`POST /api/v2/search`** — returns `{job_id, sse_url}` for `username|email|phone`.
- **`GET /api/v2/search/{job_id}`** — job snapshot with `connectors_planned`,
  `connectors_run`, `overall_status`, `overall_confidence`, `target_hash`,
  `target_type`, `status`.
- **`GET /api/v2/search/{job_id}/events?from_seq=N`** — replay SSE stream.
  Event types: `job_started`, `connector_started`, `connector_result`,
  `summary`, `job_done`, `job_failed`, `heartbeat`.
- **`ConnectorResult`** fields available on the wire today:
  `connector`, `status` (8-state), `confidence_score` 0-100, `confidence_level`,
  `cache_hit`, `elapsed_ms`, `fetched_at`, `target_hash`.
- **Job snapshot** for replay on reload (`v2-search.js#loadSnapshot`).
- **`search_events`** append-only with `seq` ordering for deterministic replay.
- **Connectors confirmed**: `sherlock:<platform>` (approved list), `oathnet:breach`,
  `oathnet:stealer`, `oathnet:victims`, `carrier_lookup` (offline phone).

What R2 may render from real data:

1. **Target dossier header** — `target_hash` short, `target_type` icon, job id,
   elapsed, `overall_status`, `overall_confidence` (3 distinct indicators).
2. **Signal layers grid** — one card per planned connector, lifecycle pending →
   running → terminal status with confidence + cache + elapsed.
3. **Live progress** — `X of Y` from `connectors_run.length / connectors_planned.length`.
4. **Job snapshot rehydration** after refresh.
5. **SSE replay banner** when `job-replay.js` reports `reconnecting`.

What R2 may **not** render even though it looks tempting:

- **Evidence list per connector** — `ConnectorResult.evidence` is currently an
  empty array in the v2 payload (`v2-search.js#connectorResultFromPayload`
  sets `evidence: []`). The drawer must therefore render an empty state, not a
  fake list. Backend emission of `evidence[]` is post-R2.
- **Raw URL** — never displayed; payload has `raw_url=null`.
- **Per-connector elapsed history / latency chart** — no aggregate metrics
  table exists.

---

## 4. What R2 still must NOT implement

Hard "do not touch" list. Each item is gated on a backend/runtime artifact that
does not exist after R1:

- **Source Health real data** — `connector_metrics` table absent. Admin source
  health remains a shell with the literal empty-state message defined by the
  canonical plan. No mocked latency, no mocked uptime, no fake `block%`.
- **Admin Jobs Queue** — no admin endpoint for listing/cancelling jobs other
  than owner snapshot. Page does not exist in R2.
- **DB-backed cases / chain graph / case timeline** — cases stay localStorage.
  No `cases` table in R2 schema. Multi-target case timeline is therefore off.
- **Cooperative cancel/retry on live jobs** — `DELETE /api/v2/search/{id}` not
  implemented; no per-connector retry. R2 must not show a cancel button that
  only hides the UI.
- **`TargetType.IP`** — G2/G4 deferred. R2 does not add `?engine=v2` IP support,
  does not render IP-specific UI, does not change the placeholder to imply IP
  support on the v2 path.
- **Gravatar** — G2 deferred. R2 must not display Gravatar avatars, must not
  hash email client-side and request `gravatar.com/avatar/<hash>`, and must
  not add `static/js/components/gravatar.js` or similar.
- **Sensitive probes** — HIBP, Truecaller, WhatsApp QR, Telegram resolve,
  Apple ID, forgot-password probes. None of these appear as UI affordances,
  not even as placeholder cards.
- **Real-time Source Health charts** — Chart.js dashboards over
  `connector_metrics` are out.
- **Cases dossier persistence** — Notes editor that pretends to persist
  server-side. Save-as-case stays localStorage-only with a visible "stored
  locally" hint.
- **Legacy `/api/search` deprecation** — `/api/search` stays active, R2 does
  not gate it, does not warn users, does not collect "migrate now" telemetry.
- **`?engine=v2` as default** — R2 keeps opt-in via query string only. No
  cookie sticky for engine flag (theme cookie stays; engine flag does not).
- **Replacing the whole frontend / React migration** — vanilla stack
  preserved. No bundler, no Lit yet, no Vite. The React mockup is a brief.
- **Auth/backend/DB changes** — R2 is frontend-only. No FastAPI route, no
  Alembic migration, no `modules/` Python edit.
- **Deploy / VPS cleanup** — no scp, no `docker compose up` against
  production, no certbot, no nginx edit. R2-0..R2-5 ship behind flag.

---

## 5. Translating the React mockup into static-frontend terms

Math's "Nexus Redesign Mockup" canvas uses React component names. R2 keeps
HTML/CSS/JS. Mapping below is normative for R2.

| Mockup name | R2 implementation | Notes |
|---|---|---|
| `<TargetDossier />` | `<header class="nx-signal__dossier">` populated by `v2-search.js` from snapshot | Renders `target_hash` short (last 8 chars), `target_type`, `job_id`, elapsed, 3 indicators (risk dial slot stays empty pending backend) |
| `<SignalLayers />` | `<section class="nx-signal__layers">` grid of `createConnectorCard()` instances, one per planned connector | Card already exists. R2 only adds the layout wrapper + lifecycle ordering (running > found > likely > uncertain > blocked > error > not_found > pending) |
| `<EvidenceQueue />` | `<aside class="nx-signal__evidence">` driven by `createEvidenceDrawer` | Empty state until backend emits `evidence[]` |
| `<ModuleOutput />` | Per-connector expanded body inside connector card | Uses `meta` slots already in `connector-card.js` |
| `<RecentCases />` | `<section class="nx-signal__cases">` reading `localStorage[nexus_cases]` | Honest label "stored locally · not server-side" |
| `<RiskPills />` | `<div class="nx-signal__risk-pills">` of `status-pill` instances for filter chips | Filters in-page; do not call backend |
| `<ChainSuggestion />` | **NOT** implemented in R2 — no backend `chain_suggestion` event | — |
| `<SourceHealthChart />` | **NOT** implemented in R2 — no `connector_metrics` | — |

Wire format constraint: any DOM element added by R2 is scoped to
`.nx-v2.nx-signal` so that turning either flag off restores the current
production UI exactly.

---

## 6. R2 phase breakdown

Five small, independently revertible phases. Each phase is its own PR-equivalent
commit on `r2/signal-ui-foundation` (or a child branch named
`r2/<phase>-<slug>`). No phase merges into `master` without smoke and
explicit Math approval.

### R2-1 — Signal UI foundation behind `?ui=signal`

**Goal:** introduce the second flag and the empty layout shell scoped to
`.nx-v2.nx-signal`. Zero functional change unless both `?theme=graphite` and
`?ui=signal` are set.

Deliverables:
- New flag wiring in `static/js/theme-flag.js` (or new `static/js/ui-flag.js`)
  that adds `nx-signal` class to `<html>` when `?ui=signal` is present, with
  a cookie of name `ui_layout` distinct from `ui_theme`. Both flags must be
  active to enable the new layout.
- `static/css/signal-layout.css` — grid skeleton (dossier / layers / evidence /
  cases) using existing graphite tokens. No new color tokens.
- `static/js/views/signal-shell.js` — initializes the shell, hides legacy
  hero/panels DOM when `nx-signal` is active.
- Empty-state copy honestly stating "no investigation active".

Allowed files: `static/css/signal-layout.css` (new), `static/js/ui-flag.js`
(new) **or** edits to `static/js/theme-flag.js`, `static/js/views/signal-shell.js`
(new), `static/index.html` (script tag + stylesheet tag additions only — no
DOM restructure of existing nodes).

Forbidden files: any `api/`, `modules/`, `alembic/`, `docker-compose*.yml`,
`nginx.conf`, `Dockerfile`, `tokens-graphite.css`, `tokens.css`,
`security-hardening.css`, R1 component JS files in `static/js/components/`.

Tests:
- Manual: load `/` with no flag → identical to today (DOM snapshot diff = 0).
- Manual: load `/?theme=graphite` → identical to today's graphite (no `nx-signal`
  side effect).
- Manual: load `/?theme=graphite&ui=signal` → empty shell visible, legacy hero
  hidden.
- Smoke: `nexus_smoke.mjs` still passes (auth + legacy + v2 + engine isolation +
  no localStorage leakage).

Rollback: `git revert <R2-1 commit>` restores index.html + removes new files.

### R2-2 — Adapt v2 results into signal layout

**Goal:** when `?engine=v2&theme=graphite&ui=signal` is active, render the
already-functional v2 search flow inside the new shell instead of the legacy
panels. Legacy `/api/search` path stays untouched.

Deliverables:
- `static/js/views/signal-investigation.js` — subscribes to `v2-search.js`
  state, renders dossier header + layers grid using existing
  `createConnectorCard`.
- Replace `v2-search.js#renderV2LiveConnectorResults` injection point with a
  callable hook so signal view receives the same `currentResult` snapshot
  (no behavioral change to `v2-search.js`; only adds an event/callback).
- Lifecycle ordering implemented in JS; CSS already gives status border.

Allowed files: `static/js/views/signal-investigation.js` (new),
`static/css/signal-layout.css` (additions), `static/js/v2-search.js` (one new
optional callback, NO change to network payload or SSE handling),
`static/index.html` (script tag only).

Forbidden files: `static/js/components/*.js` (R1 components stay frozen),
`static/js/job-replay.js`, `static/js/legacy-adapter.js`, `static/js/search.js`,
`static/js/render.js` and any backend path.

Tests:
- Manual: `/?theme=graphite&ui=signal&engine=v2` + investigate `allz` → live
  signal layout shows connector cards transitioning pending → running →
  terminal status using real `/api/v2/search` events.
- Manual: `/?engine=v2` (no signal) → legacy `scanStatus` UI still works as
  today.
- Manual: `/?theme=graphite&ui=signal` (no engine=v2) → signal shell visible
  but says "v2 engine off"; no v2 network calls.
- Smoke: `nexus_smoke.mjs` still passes.

Rollback: revert R2-2 commit; R2-1 shell remains as empty state.

### R2-3 — Evidence queue + drawer with honest empty state

**Goal:** wire `createEvidenceDrawer` into the signal layout. Since backend
`evidence[]` is empty for v2, the drawer must render an empty state explicitly.
This phase prevents the foot-gun of faking evidence later.

Deliverables:
- Drawer slot in `signal-layout.css`.
- Click on a connector card opens the drawer with that connector's
  `ConnectorResult` (status, confidence, cache, elapsed, target_hash). Evidence
  list area shows "Evidence pipeline not yet shipped — connector reported X
  signals server-side but client-visible evidence is gated on a future
  release." for v2 results.
- For legacy-adapted results (when engine=off but signal=on is allowed later),
  evidence comes from the adapter and renders normally — but R2-3 keeps signal
  layout v2-only to avoid surface creep.

Allowed files: `static/js/views/signal-investigation.js` (extend),
`static/css/signal-layout.css` (extend), `static/js/components/evidence-drawer.js`
(NO change — used as-is via existing API).

Forbidden files: backend, schema, any R1 component file body change, anything
that would make the empty state look like real evidence.

Tests:
- Manual: open any connector card → drawer opens, empty-evidence message is
  literal and quotable.
- Manual: keyboard `Escape` closes drawer; focus restored to card.
- Smoke: legacy still passes.

Rollback: revert R2-3 commit; layers grid remains clickable but no-op.

### R2-4 — Recent cases / history visual without DB-backed cases

**Goal:** render the "recent cases" slot using **only** `localStorage` data.
Visual treatment must make persistence boundary obvious ("stored locally on
this device").

Deliverables:
- `static/js/views/signal-cases.js` — reads existing case keys from
  `localStorage` (same keys `cases.js` already uses) and renders cards in the
  signal layout.
- Honest footer per card: stored timestamp + "Local only · clears when you
  clear browser data".
- No new persistence call. No POST. No `/api/cases`.
- For `?engine=v2` runs, history continues to NOT write raw target values to
  localStorage (R1 invariant). The signal cases section therefore shows hash
  short + target_type for v2-origin cases.

Allowed files: `static/js/views/signal-cases.js` (new),
`static/css/signal-layout.css` (extend), `static/js/views/signal-shell.js`
(extend to mount the section).

Forbidden files: `static/js/cases.js` (do not change persistence behavior),
backend, schema.

Tests:
- Manual: save case from legacy flow → appears in signal cases section after
  reload with `?theme=graphite&ui=signal`.
- Manual: clear localStorage → empty state with "Nenhum caso salvo. Cases
  agrupam investigações relacionadas a um alvo ou pessoa." literal copy.
- Smoke: legacy still passes.

Rollback: revert R2-4 commit; cases stay accessible via legacy slide-in panel.

### R2-5 — Polish + honest admin placeholders

**Goal:** close R2 with cosmetic polish and the **honest** admin placeholders
the canonical plan demanded — no mock metrics.

Deliverables:
- Lucide icon sweep limited to the signal layout (`.nx-v2.nx-signal` scope).
  Replace inline emoji 📁/📋/📋 with Lucide-equivalent inline SVG paths only
  inside signal layout containers. Legacy DOM keeps emoji until a future
  cleanup phase.
- `static/admin.html` — add a Source Health card (when `?ui=signal` cookie set
  on the admin domain) that **literally** says "Source health metrics
  unavailable until `connector_metrics` is shipped." Same for Jobs Queue.
  Cards are non-interactive.
- Cmd+K, keyboard shortcuts, focus rings — only if budget allows; otherwise
  defer.

Allowed files: `static/css/signal-layout.css` (extend),
`static/js/views/signal-admin.js` (new, only mounts the empty cards),
`static/admin.html` (additions only, no removal).

Forbidden files: any data fetch in admin that does not already exist; any
backend stat endpoint; `static/js/admin.js` (no behavioral change to existing
admin features).

Tests:
- Manual: `/admin?theme=graphite&ui=signal` → empty placeholder cards visible
  with literal copy; existing admin features unchanged.
- Smoke: legacy + v2 smoke unchanged.

Rollback: revert R2-5 commit.

---

## 7. File allow/deny matrix per phase

| Phase | Allowed new | Allowed edits | Strictly forbidden |
|---|---|---|---|
| R2-0 | `.planning/R2_POST_R1_VISUAL_DELTA.md` | — | Everything else |
| R2-1 | `static/css/signal-layout.css`, `static/js/ui-flag.js` (or extend theme-flag), `static/js/views/signal-shell.js` | `static/index.html` (script/link tags only) | `static/js/components/*`, `tokens*.css`, all backend, all schema |
| R2-2 | `static/js/views/signal-investigation.js` | `static/css/signal-layout.css`, `static/js/v2-search.js` (one callback only), `static/index.html` (tag only) | `static/js/components/*`, `job-replay.js`, `legacy-adapter.js`, backend |
| R2-3 | — | `static/js/views/signal-investigation.js`, `static/css/signal-layout.css` | `static/js/components/evidence-drawer.js` body, backend |
| R2-4 | `static/js/views/signal-cases.js` | `static/css/signal-layout.css`, `static/js/views/signal-shell.js` | `static/js/cases.js`, backend, schema |
| R2-5 | `static/js/views/signal-admin.js` | `static/css/signal-layout.css`, `static/admin.html` | `static/js/admin.js`, backend, stats endpoints |

---

## 8. Tests per phase

Common to every phase:
- `nexus_smoke.mjs` against local stack — must remain 8/8 PASS.
- Manual DOM diff for `/` with no flags vs. master — must be empty.
- No new console errors on `/?theme=graphite` without `ui=signal`.

Per-phase specifics already listed in §6.

A v2-engine browser smoke (Playwright manual via MCP) is appropriate for R2-2,
R2-3, R2-4, R2-5: load `?theme=graphite&ui=signal&engine=v2`, run a `username`
search, observe connector cards lifecycle.

---

## 9. Rollback strategy

R2 ships **only** behind two flags (`theme=graphite` cookie + `ui=signal`
query/cookie). Default visitor sees zero change.

- **Per-phase revert:** `git revert <phase commit>` on
  `r2/signal-ui-foundation`. No deploy required because nothing is on master.
- **Hard kill:** delete the `ui_layout` cookie or strip the `ui=signal` query
  param. Layout falls back to the live (legacy or graphite) UI.
- **Theme kill:** clearing `ui_theme` cookie hides everything graphite, by R1
  contract. `nx-signal` styles are scoped under `.nx-v2.nx-signal` so they
  disappear with the theme.
- **Database safety:** R2 touches no DB. No migration to roll back.
- **Deploy safety:** R2 phases stay on `r2/signal-ui-foundation` until Math
  approves merge to master and explicit deploy.

---

## 10. What NOT to do during R2

These actions are out of scope **and** must be refused even if convenient:

- Do not edit `api/`, `modules/`, `alembic/`, `tests/` for product changes.
- Do not edit `docker-compose*.yml`, `Dockerfile`, `entrypoint.sh`,
  `nginx.conf`, certbot config.
- Do not edit `static/css/tokens.css`, `static/css/tokens-graphite.css`,
  `static/css/security-hardening.css`.
- Do not touch `static/admin.html` outside R2-5, and even then only additive.
- Do not change `static/js/components/*.js` bodies. Their public API is the
  R2 contract; new behavior goes into `static/js/views/`.
- Do not migrate `static/js/search.js` or `render.js` to the signal layout —
  signal layout is v2-only.
- Do not promote `?engine=v2` to default.
- Do not introduce React, Vite, Lit, Tailwind, shadcn/ui, Web Components,
  bundlers, or any runtime dependency CDN.
- Do not introduce a new color, font, radius, or shadow token.
- Do not write raw `target_value` to `localStorage`, `sessionStorage`, query
  params, history entries, or DOM `data-*` attributes anywhere on the v2 path.
- Do not display real or simulated Gravatar avatars.
- Do not introduce `TargetType.IP` UI affordances on the v2 path.
- Do not add Source Health, Jobs Queue, or chain graph visualizations with
  data that does not exist server-side.
- Do not add cancel, retry, pause buttons for live jobs.
- Do not auto-redirect anyone to the signal layout.
- Do not deploy to the VPS.
- Do not "clean up" the legacy OathNet quota pill, hero copy, or panels in R2.
  Those changes belong to a later cleanup branch, after R2 ships behind flags
  and Math evaluates rollover.
- Do not start R2-1 work in this commit. R2-0 is documentation only.

---

## Appendix A — Open questions for Math (non-blocking for R2-0)

1. Should `?ui=signal` flip both theme + layout at once, or stay strictly
   additive (require `?theme=graphite` too)? Default chosen here: **additive**
   to keep flag composition explicit and rollback cheap.
2. Where does the React mockup live? If a snapshot URL or file exists, R2-1
   benefits from pinning it as the reference image. If only canvas-only, R2-1
   proceeds from the ASCII wireframes in `VISUAL_REDESIGN_PLAN.md` §4.3 B/C.
3. Locale for the signal UI strings: `VISUAL_REDESIGN_PLAN.md` mixes pt-BR and
   en-US. R2 defaults to **pt-BR** for visible copy and keeps technical
   placeholders (status names) in lowercase English to match `ConnectorStatus`
   wire values.
4. Is `?engine=v2&ui=signal` the only allowed combination, or should
   `?ui=signal` without `?engine=v2` show the legacy data through
   `legacy-adapter.js`? Default chosen: **v2-only** for R2 to keep scope
   small. Legacy adoption of signal layout can be its own future phase.

These are **deferrable**: R2-0 commits without answering them.
