# CODEX HANDOFF — NexusOSINT R0/R1 Execution Pack

**Target executor:** Codex GPT 5.5 xhigh
**Repository:** `C:\Users\vtbit\Documents\nexus_osint` (Windows host) / `/root/nexus-osint` (VPS Linux)
**Source of truth:** this file + `.planning/R0_R1_REVISION.md` + `CLAUDE.md` (project root)
**Date prepared:** 2026-05-18
**Author of handoff:** Opus session
**Operator:** Math (vibe-coding, low-code)

---

## 0. Read order (BLOCKING — do not skip)

Codex must read these in order BEFORE writing any code:

1. `CLAUDE.md` (project root) — filosofia central, regras de ouro, exception handling, padrões obrigatórios
2. `.planning/R0_R1_REVISION.md` — escopo R0/R1, contratos, critérios de aceite (canonical)
3. This file (`.planning/CODEX_HANDOFF.md`) — execution protocol, decisions baked, skeletons
4. `agora/README.MD` — UX baseline (Signal v2)
5. `api/main.py` (just the router registration block, lines 271-277) — pattern for adding `search_v2.router`
6. `api/orchestrator.py` (class `TaskOrchestrator`, lines 59-140) — submit/results API
7. `api/services/search_service.py` (function `_stream_search`, lines 257+) — legacy event shape source
8. `modules/username_check/scoring.py` (function `combine_outcomes`) — legacy 6-state mapping source

**Do not** read entire codebase. Trust this handoff for paths/contracts. Read only files cited above before R0; read files cited per-task during execution.

---

## 1. Decisions baked (G1-G4 from Math, 2026-05-18)

| Gate | Decision | Implication |
|------|----------|-------------|
| **G1** | **hash-only + TTL 7d** | `search_jobs.target_encrypted` stays `NULL` always. `search_events.payload` contains only `target_hash` + sanitized metadata. `expires_at = created_at + INTERVAL '7 days'`. No key management. No ChaCha20Poly1305 module needed. |
| **G2** | **Adiar gravatar** | **Skip R1-10 entirely.** No `modules/connectors/email/gravatar.py`. No MD5 sent to gravatar.com. Email connectors in R1 limited to OathNet adapter only. |
| **G3** | **≥2 conectores independentes** | `search_orchestrator.aggregate()`: `overall_status = "found"` only if ≥2 connectors returned `found`. Single-connector `found` becomes `overall_status = "likely"`. No `hard_positive` short-circuit. |
| **G4** | **Reuse Thordata (1GB/day quota)** | No new proxy provisioning. `carrier_lookup` is offline → zero proxy impact. Future email/phone connectors (R2+) reuse existing `ThordataProxy`. |

**Decisions still OUT of scope (do not touch):**
- HIBP API, Truecaller, forgot-password probes, WhatsApp QR, Telegram resolve, Apple ID probe.
- `connector_metrics` table, Source Health real-data UI.
- Cancel/retry cooperative, chain suggestions, persistent cases in DB, chain graph SVG.
- Lit/Stencil/any frontend framework via CDN.
- Renaming `index.html`, landing public page.

---

## 2. Project context (condensed)

**Product:** NexusOSINT — OSINT investigation workspace. Username + email + phone lookup. Anti-false-positive heavy.

**Stack (immutable):**
- Backend: FastAPI 0.136 + Python 3.12 + asyncpg 0.31 (pool 2-10) + Redis 5.1 + SQLAlchemy 2.0 + Alembic 1.14
- Frontend: Vanilla JS (no framework), Space Grotesk + JetBrains Mono + Inter fonts, dark Amber theme (Meridian tokens)
- Auth: JWT HS256 httpOnly cookie + bcrypt + slowapi rate limit
- Container: Docker multi-stage `python:3.12-slim`, target <250MB
- Deploy: Hetzner VPS `root@87.99.153.11`, domain `nexusosint.uk` via Cloudflare proxy

**Hardware constraints (non-negotiable):**
- VPS: 3 vCPU / 4 GB RAM / 80 GB SSD
- RAM resting: <500 MB | alert: >2000 MB | critical: >85% (~3400 MB)
- Concurrency ceiling: `asyncio.Semaphore(5)` global + `Semaphore(3)` OathNet sub-cap
- Docker image: <250 MB
- Postgres: container privado, sem porta pública, `max_connections=20`, `mem_limit=768 MB`

**Existing infra to REUSE (do not recreate):**
- `api.cache.cache_backend` — RedisCacheBackend with fail-open + InMemoryCacheBackend fallback
- `api.db.db` — `DatabaseManager` with `asyncpg.Pool` (2-10) + `execute()`, `fetch()`, `fetch_stream()` (cursor-based)
- `api.orchestrator.TaskOrchestrator` — `submit(name, coro, is_oathnet=False)` + `async for (name, result) in orch.results()`
- `modules.username_check.runner.search_username` — legacy username runner (do not rewrite, only wrap in adapter)
- `modules.oathnet_client` — legacy OathNet client (wrap in adapter)
- `modules.username_check.rate_limit.OutboundRateLimiter` — token-bucket per domain
- `modules.username_check.proxy.ThordataProxy` — sticky + rotate proxy
- `modules.username_check.audit` — SHA-256 hashed target audit log
- `modules.username_check.scoring.combine_outcomes` — 6-state scoring (mapping to 8-state defined in §5)
- `modules.report_generator` — PDF export (do not touch template; only call from casebook)

---

## 3. Hard rules (CLAUDE.md compressed — violation = block PR)

| Rule | Enforcement |
|------|-------------|
| No `except Exception:` generic | Per-camada exception handling (see CLAUDE.md §"PADRÃO DE EXCEPTION HANDLING"). Endpoints convert to `HTTPException`. Connectors catch specific httpx/asyncio exceptions; let unknowns propagate to TaskGroup. |
| No `target_value` in claro in logs / payloads / `search_events.payload` | Always log `target_hash` (SHA-256[:12]). Sanitize payloads before INSERT. |
| No frontend authorization logic | Backend decides; frontend renders capabilities returned by API. |
| No `.fetchall()` on queries returning >100 rows | Use `db.fetch_stream()` (cursor) for events. |
| No `asyncio.create_task()` fire-and-forget | All tasks via `TaskOrchestrator.submit()` or `TaskGroup`. Existing `tasks.py` pattern OK. |
| No secrets hardcoded | All via `.env`. |
| `likely` never becomes `found` | At any layer. CI test enforces. |
| `blocked` never becomes `not_found` or `error` | At any layer. CI test enforces. |
| `CLAUDE.md` immutable in R0/R1 | Update `docs/CONNECTORS.md` and `.planning/PROJECT.md` instead. |
| `meridian.css` (or `tokens.css`) immutable | New tokens go to `static/css/tokens-graphite.css`. |
| `docker-compose.prod.yml` immutable without approval | If R1-2 requires migration runtime change, document and ask. |
| Outbound rate limit on every connector | Reuse `OutboundRateLimiter`. Profile per-connector via config. |
| Brand Amber/Noir untouched | Graphite & Ember is a new opt-in theme under feature flag, not a replacement. |

---

## 4. Pre-flight (before R0-1) — cleanup working tree

Codex runs ONCE before R0-1, on `master`:

```bash
# 1. Verify state
git status
git branch --show-current   # must be 'master'

# 2. Delete junk
rm -f .tmp_vps_diff.txt

# 3. Move session snapshot
git mv ultima.md .planning/SESSAO_2026-05-18_ultima.md 2>/dev/null || mv ultima.md .planning/SESSAO_2026-05-18_ultima.md

# 4. Stage planning backlog
git add .planning/MAIGRET_VALIDATION_PLAN.md \
        .planning/PROPOSTA_MELHORIAS_API_PERFORMANCE.md \
        .planning/SESSAO_2026-05-12.md \
        .planning/hotfixes/CODEX_REVIEW_OPUS_PLAN.md \
        .planning/SESSAO_2026-05-18_ultima.md \
        .planning/R0_R1_REVISION.md \
        .planning/CODEX_HANDOFF.md \
        tests/e2e/README.md \
        tests/e2e/security-smoke.spec.ts

# 5. Stage deletion that was already marked
git add -u PROPOSTA_MELHORIAS_API_PERFORMANCE.md

# 6. Commit (use HEREDOC for multi-line message)
git commit -m "$(cat <<'EOF'
docs(planning): backlog + R0/R1 revision + Codex handoff

- Move PROPOSTA_MELHORIAS_API_PERFORMANCE.md to .planning/
- Move ultima.md to .planning/SESSAO_2026-05-18_ultima.md
- Add R0_R1_REVISION.md (canonical scope)
- Add CODEX_HANDOFF.md (Codex execution pack)
- Add pre-existing planning artifacts

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"

# 7. Verify clean
git status   # must show: "nothing to commit, working tree clean"
```

**If `git status` shows ANY uncommitted changes after step 7 → halt and ask Math.**

Then create R0 branch:

```bash
git checkout -b v4.1/r0-contract-shim
```

---

## 5. R0 — Contract shim (7 tasks)

### R0-1 — `modules/connectors/base.py` (schemas + enums)

**Files to create:**
- `modules/connectors/__init__.py` (empty)
- `modules/connectors/base.py` (content below — EXACT)
- `tests/unit/connectors/__init__.py` (empty)
- `tests/unit/connectors/test_base.py`

**`modules/connectors/base.py` content (canonical — do not modify shape):**

```python
"""Connector contract shared by all OSINT sources.

This module defines the canonical schemas. Status enum is 8-state.
`likely` and `blocked` are first-class and MUST NOT collapse into other states
at any layer (backend, adapter, frontend). See .planning/R0_R1_REVISION.md.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TargetType(str, Enum):
    USERNAME = "username"
    EMAIL = "email"
    PHONE = "phone"


class ConnectorStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    FOUND = "found"
    LIKELY = "likely"
    NOT_FOUND = "not_found"
    UNCERTAIN = "uncertain"
    BLOCKED = "blocked"
    ERROR = "error"


ConfidenceLevel = Literal["high", "medium", "low", "none"]


def derive_confidence_level(score: int) -> ConfidenceLevel:
    if score >= 85:
        return "high"
    if score >= 60:
        return "medium"
    if score >= 30:
        return "low"
    return "none"


class Evidence(BaseModel):
    signal: str
    weight: int = Field(ge=-100, le=100)
    detail: str = ""


class ConnectorRequest(BaseModel):
    target_type: TargetType
    target_value: str
    target_hash: str
    timeout_s: int = 15
    job_id: UUID


class ConnectorResult(BaseModel):
    connector: str
    target_type: TargetType
    status: ConnectorStatus
    confidence_score: int = Field(ge=0, le=100)
    confidence_level: ConfidenceLevel
    evidence: list[Evidence] = []
    warnings: list[str] = []
    raw_url: str | None = None
    data: dict = {}
    fetched_at: datetime
    cache_hit: bool = False
    elapsed_ms: int = Field(ge=0)
```

**`tests/unit/connectors/test_base.py` content (minimum coverage):**

```python
"""Tests for ConnectorResult schema and derive_confidence_level."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from modules.connectors.base import (
    ConfidenceLevel,
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    Evidence,
    TargetType,
    derive_confidence_level,
)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100, "high"),
        (85, "high"),
        (84, "medium"),
        (60, "medium"),
        (59, "low"),
        (30, "low"),
        (29, "none"),
        (0, "none"),
    ],
)
def test_derive_confidence_level(score: int, expected: ConfidenceLevel) -> None:
    assert derive_confidence_level(score) == expected


def test_connector_status_has_eight_states() -> None:
    expected = {
        "pending", "running", "found", "not_found",
        "likely", "uncertain", "blocked", "error",
    }
    assert {s.value for s in ConnectorStatus} == expected


def test_likely_is_distinct_from_found() -> None:
    assert ConnectorStatus.LIKELY != ConnectorStatus.FOUND
    assert ConnectorStatus.LIKELY.value == "likely"


def test_blocked_is_distinct_from_error_and_not_found() -> None:
    assert ConnectorStatus.BLOCKED != ConnectorStatus.ERROR
    assert ConnectorStatus.BLOCKED != ConnectorStatus.NOT_FOUND


def test_connector_result_valid_construction() -> None:
    result = ConnectorResult(
        connector="sherlock:github",
        target_type=TargetType.USERNAME,
        status=ConnectorStatus.FOUND,
        confidence_score=92,
        confidence_level="high",
        evidence=[Evidence(signal="profile_match", weight=80, detail="200 OK")],
        fetched_at=datetime.now(timezone.utc),
        elapsed_ms=345,
    )
    assert result.connector == "sherlock:github"
    assert result.confidence_score == 92


def test_connector_request_requires_job_id() -> None:
    req = ConnectorRequest(
        target_type=TargetType.PHONE,
        target_value="+5511999999999",
        target_hash="a1b2c3d4e5f6",
        job_id=uuid4(),
    )
    assert req.timeout_s == 15  # default


def test_evidence_weight_bounds() -> None:
    with pytest.raises(ValueError):
        Evidence(signal="bad", weight=150)
    with pytest.raises(ValueError):
        Evidence(signal="bad", weight=-200)


def test_confidence_score_bounds() -> None:
    with pytest.raises(ValueError):
        ConnectorResult(
            connector="x",
            target_type=TargetType.USERNAME,
            status=ConnectorStatus.FOUND,
            confidence_score=150,
            confidence_level="high",
            fetched_at=datetime.now(timezone.utc),
            elapsed_ms=0,
        )
```

**Run:**
```bash
pytest tests/unit/connectors/test_base.py -v
```

**Acceptance:** all 7+ tests green. Import `from modules.connectors.base import ConnectorResult` works.

**Commit:**
```
feat(connectors): add ConnectorResult schema with 8-state status

R0-1 of v4.1/r0-contract-shim. Defines Pydantic v2 contract shared by
all OSINT connectors. Status enum is 8-state (pending/running/found/
not_found/likely/uncertain/blocked/error). Helpers for confidence_level
derivation. CI enforces likely/blocked distinctness.

Refs .planning/R0_R1_REVISION.md
```

---

### R0-2 — Tokens Graphite & Ember sob flag visual

**Files to create:**
- `static/css/tokens-graphite.css`
- `static/css/connectors.css`
- `static/js/theme-flag.js`

**`static/css/tokens-graphite.css`** — copy palette from `agora/VISUAL_REDESIGN_PLAN.md` §9.1 (lines 827-899). Wrap all variables in `:root.nx-v2 { ... }` selector so they only apply when `<html>` has class `nx-v2`.

**`static/js/theme-flag.js`:**

```javascript
// Graphite & Ember theme flag — opt-in only, default OFF.
// Activates via ?theme=graphite query param OR cookie `ui_theme=graphite`.
// When active, adds class `nx-v2` to <html> and loads tokens-graphite.css.

(function () {
  'use strict';

  function getParam(name) {
    var match = new RegExp('[?&]' + name + '=([^&]+)').exec(window.location.search);
    return match ? decodeURIComponent(match[1]) : null;
  }

  function getCookie(name) {
    var match = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]+)'));
    return match ? decodeURIComponent(match[2]) : null;
  }

  var fromParam = getParam('theme');
  var fromCookie = getCookie('ui_theme');
  var active = fromParam === 'graphite' || fromCookie === 'graphite';

  if (active) {
    document.documentElement.classList.add('nx-v2');
    if (fromParam === 'graphite' && fromCookie !== 'graphite') {
      var expires = new Date();
      expires.setDate(expires.getDate() + 30);
      document.cookie = 'ui_theme=graphite; expires=' + expires.toUTCString() + '; path=/; SameSite=Lax';
    }
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/tokens-graphite.css?v=20260518';
    document.head.appendChild(link);

    var connectorsCss = document.createElement('link');
    connectorsCss.rel = 'stylesheet';
    connectorsCss.href = '/static/css/connectors.css?v=20260518';
    document.head.appendChild(connectorsCss);
  }

  window.NX_V2 = active;
})();
```

**Edit `static/index.html` and `static/admin.html`:** add `<script src="/static/js/theme-flag.js?v=20260518"></script>` as FIRST script in `<head>` (before any other JS). No other changes in this task.

**Acceptance:**
- Visit `/?theme=graphite` → `<html class="nx-v2">` + tokens loaded → cookie set
- Visit `/` after → cookie still active → tokens loaded
- Clear cookie + visit `/` → no `nx-v2` class, original visual identical (regression zero)

**Commit:**
```
feat(ui): add Graphite & Ember tokens behind opt-in flag

R0-2. New theme `nx-v2` loads only via ?theme=graphite query param
or cookie ui_theme=graphite. Existing tokens (Meridian/Amber) untouched.
Default off — zero regression for current users.
```

---

### R0-3 — Componentes UI base (vanilla JS)

**Files to create:**
- `static/js/components/status-pill.js`
- `static/js/components/connector-card.js`
- `static/js/components/confidence-meter.js`
- `static/js/components/evidence-drawer.js`
- `static/dev/components-preview.html` (storybook)

**Pattern:** each component is a factory function `createXxx(opts) → HTMLElement`. No classes, no Lit, no CDN. Use template strings + `document.createElement`.

**Skeleton `static/js/components/status-pill.js`:**

```javascript
// StatusPill — renders 8-state ConnectorStatus as a chip with icon + label.
// Usage: var pill = createStatusPill({ status: 'found', label: 'Found' });
//        container.appendChild(pill);

(function (global) {
  'use strict';

  var STATUS_META = {
    pending:   { icon: '◌', label: 'Pending',   color: 'var(--text-3)' },
    running:   { icon: '▢', label: 'Running',   color: 'var(--accent)' },
    found:     { icon: '▣', label: 'Found',     color: 'var(--status-found)' },
    likely:    { icon: '▤', label: 'Likely',    color: 'var(--status-likely)' },
    uncertain: { icon: '◇', label: 'Uncertain', color: 'var(--status-uncertain)' },
    not_found: { icon: '□', label: 'Not found', color: 'var(--status-not-found)' },
    blocked:   { icon: '⊘', label: 'Blocked',   color: 'var(--status-blocked)' },
    error:     { icon: '✕', label: 'Error',     color: 'var(--status-error)' }
  };

  function createStatusPill(opts) {
    var status = opts.status || 'pending';
    var meta = STATUS_META[status];
    if (!meta) throw new Error('Invalid status: ' + status);

    var el = document.createElement('span');
    el.className = 'nx-v2 nx-status-pill nx-status-pill--' + status;
    el.setAttribute('role', 'status');
    el.setAttribute('aria-label', meta.label);
    el.setAttribute('data-status', status);
    el.style.color = meta.color;
    el.innerHTML = '<span class="nx-status-pill__icon" aria-hidden="true">' +
                   meta.icon + '</span><span class="nx-status-pill__label">' +
                   (opts.label || meta.label) + '</span>';

    if (opts.tooltip) {
      el.setAttribute('title', opts.tooltip);
    }
    return el;
  }

  global.createStatusPill = createStatusPill;
})(window);
```

**Skeleton `static/js/components/connector-card.js`** — render `ConnectorResult`-shaped object. States: empty (no data), loading (status=running, pulse), loaded (with data). Keyboard accessible: tabindex=0, Enter opens evidence drawer.

**Skeleton `static/js/components/confidence-meter.js`** — horizontal bar 0-100, 4 zones (none<30 / low<60 / med<85 / high≥85), text label always present.

**Skeleton `static/js/components/evidence-drawer.js`** — slide-in right panel 320px, lists `evidence[]` with `signal · weight · detail`. Empty state: "No evidence available yet."

**`static/dev/components-preview.html`** — single page that imports all components + tokens-graphite.css with `nx-v2` class on `<html>`. Renders each component in all 8 states + empty/loading. Goal: dev/QA can see all states visually without running search.

**Acceptance:**
- Open `/static/dev/components-preview.html?theme=graphite` → see grid of 8 status pills + connector cards in all states + confidence meter at scores [0, 29, 30, 59, 60, 84, 85, 100] + evidence drawer empty/populated
- Tab through cards with keyboard → focus visible → Enter opens evidence drawer
- No console errors

**Commit:**
```
feat(ui): add R0 base components (StatusPill, ConnectorCard, ConfidenceMeter, EvidenceDrawer)

R0-3. Vanilla JS factories — no framework, no CDN. All states keyboard
accessible. Storybook at /static/dev/components-preview.html.
```

---

### R0-4 — Legacy adapter (client-side translation)

**File to create:** `static/js/legacy-adapter.js`
**File to patch (minimal):** `static/js/render.js` — call adapter when `window.NX_V2 === true`.

**Adapter contract** (per `.planning/R0_R1_REVISION.md` §1.3):

```javascript
// legacy-adapter.js — translates /api/search SSE events into ConnectorResult shape.
// Pure client-side, no backend change.

(function (global) {
  'use strict';

  // CANONICAL MAPPING — see .planning/R0_R1_REVISION.md §1.3 table.
  var SHERLOCK_STATUS_MAP = {
    confirmed:       'found',
    likely:          'likely',         // MUST stay 'likely'. Never 'found'.
    unconfirmed:     'uncertain',
    not_found:       'not_found',
    auth_blocked:    'blocked',
    cf_challenge:    'blocked',
    login_required:  'blocked',
    error:           'error',
    timeout:         'error',
    invalid:         'error'
  };

  function deriveConfidenceLevel(score) {
    if (score >= 85) return 'high';
    if (score >= 60) return 'medium';
    if (score >= 30) return 'low';
    return 'none';
  }

  function adaptSherlockResult(legacy) {
    var status = SHERLOCK_STATUS_MAP[legacy.validation_status] || 'uncertain';
    var score = typeof legacy.confidence_score === 'number' ? legacy.confidence_score : 0;
    return {
      connector: 'sherlock:' + (legacy.platform || legacy.site || 'unknown'),
      target_type: 'username',
      status: status,
      confidence_score: score,
      confidence_level: deriveConfidenceLevel(score),
      evidence: (legacy.evidence || []).map(function (e) {
        return { signal: e.signal, weight: e.weight, detail: e.detail || '' };
      }),
      warnings: legacy.warnings || [],
      raw_url: legacy.url || null,
      data: { platform: legacy.platform || legacy.site },
      fetched_at: new Date().toISOString(),
      cache_hit: !!legacy.cache_hit,
      elapsed_ms: legacy.elapsed_ms || 0
    };
  }

  function adaptOathnetBreach(legacy) {
    var count = (legacy.records || []).length;
    return {
      connector: 'oathnet:breach',
      target_type: legacy.target_type || 'email',
      status: count > 0 ? 'found' : 'not_found',
      confidence_score: count > 0 ? Math.min(100, 50 + count * 5) : 0,
      confidence_level: count > 0 ? 'high' : 'none',
      evidence: [{ signal: 'breach_records', weight: count > 0 ? 80 : 0, detail: count + ' records' }],
      warnings: [],
      raw_url: null,
      data: { record_count: count },
      fetched_at: new Date().toISOString(),
      cache_hit: !!legacy.cache_hit,
      elapsed_ms: legacy.elapsed_ms || 0
    };
  }

  // Add similar adapters for: oathnet:stealer, oathnet:ip, spiderfoot:*

  function adaptLegacyEvent(eventData) {
    if (!eventData || !eventData.type) return null;

    switch (eventData.type) {
      case 'sherlock_result':
        return adaptSherlockResult(eventData);
      case 'breach':
        return adaptOathnetBreach(eventData);
      // ... add cases for stealer, ip_info, spiderfoot
      default:
        return null;
    }
  }

  global.adaptLegacyEvent = adaptLegacyEvent;
})(window);
```

**Patch `static/js/render.js`:** find the SSE event handler. When `window.NX_V2 === true`, call `adaptLegacyEvent(data)` and render via `createConnectorCard()` from R0-3 instead of legacy panel renderer. When `NX_V2` is false, run original code untouched.

**Acceptance:**
- Search username with `?theme=graphite` → each sherlock platform appears as `ConnectorCard` with status pill
- `likely` results show mustard pill, **never** green
- `cf_challenge` results show terra pill (`blocked`), **never** red (`error`)
- Flag off → original UI untouched, regression zero
- Console has no errors

**Commit:**
```
feat(ui): client-side legacy adapter mapping /api/search to 8-state

R0-4. Translates sherlock/oathnet/spiderfoot events into ConnectorResult
shape when nx-v2 flag is active. Canonical mapping documented in
.planning/R0_R1_REVISION.md §1.3. `likely` and `blocked` preserved.
```

---

### R0-5 — Cleanup copy + nav (remove OathNet quota from nav)

**Files to edit:** `static/index.html`, `static/admin.html`

**Changes:**
1. Replace hero copy "Find anything on anyone, instantly." with "Confirme. Não suponha." (or whatever Math approves — ask if not specified)
2. Remove OathNet quota pill from main nav. Quota stays visible only in `/admin` (already exists there)
3. Verify with grep that no remaining occurrences:

```bash
grep -rn "Find anything on anyone" static/
grep -rn "OathNet" static/index.html  # should not match in nav block
```

**Acceptance:**
- Visual diff on `/` (logged in) → hero copy changed, nav quota gone
- `/admin` → quota still visible
- No broken layout (quota element removal doesn't shift other elements)

**Commit:**
```
chore(ui): remove "Find anything on anyone" copy and OathNet quota from nav

R0-5. Per R0/R1 revision: hero copy reframed for investigation-first
positioning. OathNet quota moves to /admin only (admin info, not user info).
```

---

### R0-6 — Documentation

**Files to create:**
- `docs/CONNECTORS.md`
- Append to `.planning/PROJECT.md` (do NOT create if missing — verify first; if missing, halt)

**`docs/CONNECTORS.md` content (skeleton):**

```markdown
# Connectors Contract — NexusOSINT

**Status:** R0 (contract shim) — backend connectors arrive in R1.
**Source of truth:** `modules/connectors/base.py`.

## 1. Schema

See `modules/connectors/base.py` for the canonical Pydantic v2 definitions:
- `TargetType` — username | email | phone
- `ConnectorStatus` — 8-state (pending/running/found/not_found/likely/uncertain/blocked/error)
- `Evidence` — signal + weight (-100..100) + detail
- `ConnectorRequest` — input contract
- `ConnectorResult` — output contract

## 2. Status semantics (IMMUTABLE)

| Status | Meaning | UI color (Graphite & Ember) |
|--------|---------|------------------------------|
| `pending` | Planned, not started | text-3 (tertiary) |
| `running` | In flight (lifecycle) | accent (ember) with pulse |
| `found` | Match confirmed by quorum (≥2 connectors agree) | conf-high (musgo green) |
| `likely` | Positive signal without quorum | conf-med (mostarda) — NEVER green |
| `not_found` | Negative confirmed | text-3 |
| `uncertain` | Signals disagree | conf-med with border only |
| `blocked` | Source blocked us (rate limit, captcha, auth wall) | status-blocked (terra) — NOT red |
| `error` | Source failed (timeout, network, parse) | status-error (ember red) |

**Hard rules:**
- `likely` MUST NOT collapse to `found` at any layer.
- `blocked` MUST NOT collapse to `not_found` or `error` at any layer.

## 3. Confidence derivation

```
score >= 85 → "high"
score >= 60 → "medium"
score >= 30 → "low"
score <  30 → "none"
```

## 4. Legacy → 8-state mapping (R0-4 client adapter)

| Legacy event field | Connector name | Status derived |
|--------------------|----------------|----------------|
| `sherlock.validation_status=confirmed` | `sherlock:<platform>` | `found` |
| `sherlock.validation_status=likely` | `sherlock:<platform>` | `likely` |
| `sherlock.validation_status=unconfirmed` | `sherlock:<platform>` | `uncertain` |
| `sherlock.validation_status=not_found` | `sherlock:<platform>` | `not_found` |
| `sherlock.validation_status=auth_blocked` or `cf_challenge` | `sherlock:<platform>` | `blocked` |
| `sherlock.validation_status=error` or `timeout` | `sherlock:<platform>` | `error` |
| oathnet breach record (≥1) | `oathnet:breach` | `found` |
| oathnet breach record (0) | `oathnet:breach` | `not_found` |
| oathnet stealer | `oathnet:stealer` | same as breach |
| spiderfoot event | `spiderfoot:<event_type>` | `likely` |

## 5. R0/R1 scope

See `.planning/R0_R1_REVISION.md` for full task list.

R0 (contract shim): schema only, no backend connectors yet.
R1 (safe MVP): sherlock_adapter + oathnet_adapter + carrier_lookup. Decisions G1-G4 baked.

## 6. Privacy & retention (G1 = hash-only + TTL 7d)

- `search_events.payload` contains only `target_hash` (SHA-256[:12]) + sanitized metadata.
- No `target_value` in claro anywhere (DB, logs, payloads).
- `search_jobs.expires_at = created_at + INTERVAL '7 days'`.
- Job cleanup loop purges expired rows (R1-11). Events cascade via `ON DELETE CASCADE`.
- LGPD: hash-only is irreversible — user delete request fulfilled by waiting for TTL or `DELETE /api/v2/search/{job_id}` (R1-8 if added).
```

**Append to `.planning/PROJECT.md`:**

```markdown
## 2026-05-18 — R0/R1 decisions baked

- G1 = hash-only + TTL 7d for search_events.payload
- G2 = adiar gravatar (skip R1-10)
- G3 = >=2 conectores independentes for overall_status='found'
- G4 = reuse Thordata (1GB/day quota)

Execution branch series:
- R0: `v4.1/r0-contract-shim` -> 7 tasks -> contract shim, no engine change
- R1: `v4.1/r1-safe-mvp` -> 11 tasks (R1-10 skipped) -> safe MVP with /api/v2/search

See `.planning/R0_R1_REVISION.md` and `.planning/CODEX_HANDOFF.md`.
```

**Acceptance:** both files exist, Math reads and approves.

**Commit:**
```
docs(connectors): add CONNECTORS.md and update PROJECT.md with G1-G4

R0-6. Canonical contract reference for engineers + LLM operators.
Records decisions baked for R1 execution.
```

---

### R0-7 — Casebook metadata (localStorage) + export PDF wired

**File to edit:** `static/js/cases.js` (exists per `static/js/` listing).

**Changes:**
1. When saving a case to `localStorage`, include these fields:
   ```javascript
   {
     id: <uuid>,
     name: <user-provided>,
     created_at: <ISO timestamp>,
     updated_at: <ISO timestamp>,
     target_hash: <SHA-256[:12] of target_value, computed client-side via SubtleCrypto>,
     target_type: 'username' | 'email' | 'phone',
     summary_snapshot: {
       overall_status: <8-state>,
       overall_confidence: <0-100>,
       found_count: <int>,
       likely_count: <int>,
       not_found_count: <int>,
       blocked_count: <int>,
       error_count: <int>
     },
     // legacy fields preserved for back-compat
   }
   ```
2. List view: sort by `updated_at` desc, each item shows StatusPill (from R0-3) + counts.
3. "Export PDF" button: calls existing PDF endpoint (verify in `api/routes/` — search for `/report/pdf` or similar). Add footer to PDF: "NexusOSINT · case_id · generated_at".

**SubtleCrypto hash helper:**
```javascript
async function sha256Hex12(str) {
  var enc = new TextEncoder();
  var buf = await crypto.subtle.digest('SHA-256', enc.encode(str));
  return Array.from(new Uint8Array(buf))
    .map(function (b) { return b.toString(16).padStart(2, '0'); })
    .join('')
    .slice(0, 12);
}
```

**Acceptance:**
- Save case → reopen → metadata visible (created_at, target_hash, summary)
- Cases list shows StatusPill per case
- Export PDF button works (returns valid PDF), footer includes case_id
- `localStorage` quota check: warn if approaching 5MB (don't fail silently)

**Commit:**
```
feat(cases): enrich case metadata + wire PDF export with case footer

R0-7. localStorage cases now include created_at/updated_at/target_hash/
summary_snapshot. List sorted by updated_at desc with StatusPill.
PDF export adds case_id footer. Persistent case entity deferred to R3+.
```

---

### R0 wrap-up

After R0-1 to R0-7 committed on `v4.1/r0-contract-shim`:

```bash
# Verify all acceptance
pytest tests/unit/connectors/test_base.py -v
# Manual: open / with ?theme=graphite, search a username, verify cards render correctly
# Manual: open /static/dev/components-preview.html?theme=graphite
# Manual: save a case, reopen, export PDF

# Push branch
git push -u origin v4.1/r0-contract-shim

# Open PR
gh pr create --title "R0 contract shim — ConnectorResult schema + Graphite & Ember opt-in" --body "$(cat <<'EOF'
## Summary
- ConnectorResult Pydantic v2 schema with 8-state ConnectorStatus
- Graphite & Ember tokens under opt-in flag (?theme=graphite / cookie ui_theme)
- R0 base UI components (StatusPill, ConnectorCard, ConfidenceMeter, EvidenceDrawer)
- Client-side legacy adapter translating /api/search events to ConnectorResult shape
- Cleanup: hero copy reframed, OathNet quota removed from nav
- docs/CONNECTORS.md canonical reference
- Casebook localStorage metadata enriched + PDF export wired

## Test plan
- [x] pytest tests/unit/connectors/test_base.py (8+ tests green)
- [x] Visit / without ?theme=graphite → original visual identical (regression zero)
- [x] Visit /?theme=graphite → cards render via legacy adapter, likely stays likely, blocked stays blocked
- [x] /static/dev/components-preview.html?theme=graphite → all 8 states visible
- [x] Save case, reopen, export PDF — footer includes case_id
- [x] No console errors

## Scope deferred
See `.planning/R0_R1_REVISION.md` §6 for items intentionally out of R0/R1.

Generated with Claude Code
EOF
)"
```

**Math reviews PR → merge → deploy → smoke prod → R0 done.**

---

## 6. R1 — Safe MVP (11 tasks; R1-10 skipped per G2)

Open R1 branch only after R0 merged + deployed + smoke verified:

```bash
git checkout master
git pull
git checkout -b v4.1/r1-safe-mvp
```

### R1-1 — `modules/connectors/runner.py`

**File to create:** `modules/connectors/runner.py`

**Contract:**

```python
"""Connector runner — applies timeout, rate limit, cache, audit log
around any Connector instance."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Protocol

import httpx
from loguru import logger

from api.cache import cache_backend
from modules.connectors.base import (
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    TargetType,
)
from modules.username_check.rate_limit import OutboundRateLimiter

_limiter = OutboundRateLimiter(calls_per_second=2.0)


class Connector(Protocol):
    name: str
    target_types: tuple[TargetType, ...]
    default_timeout_s: int
    rate_limit_cps: float

    async def run(self, req: ConnectorRequest, http: httpx.AsyncClient) -> ConnectorResult: ...


async def run_connector(
    connector: Connector,
    req: ConnectorRequest,
    http: httpx.AsyncClient,
    *,
    cache_ttl_s: int = 300,
) -> ConnectorResult:
    """Execute a connector with full hardening:
    - cache lookup (Redis fail-open)
    - outbound rate limit per connector name
    - timeout enforcement (asyncio.wait_for)
    - audit log with target_hash (never target_value)
    - exception → ConnectorResult with status=ERROR/BLOCKED (never raise)
    """
    cache_key = f"connector:{connector.name}:{req.target_type.value}:{req.target_hash}"

    cached = await cache_backend.get(cache_key)
    if cached:
        try:
            result = ConnectorResult.model_validate_json(cached)
            result.cache_hit = True
            logger.info(
                "connector cache hit | connector={} target_hash={}",
                connector.name, req.target_hash,
            )
            return result
        except (ValueError, TypeError):
            logger.warning("connector cache parse failure | connector={}", connector.name)

    await _limiter.acquire(connector.name)

    started = time.monotonic()
    try:
        result = await asyncio.wait_for(
            connector.run(req, http),
            timeout=connector.default_timeout_s,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "connector timeout | connector={} target_hash={} timeout_s={}",
            connector.name, req.target_hash, connector.default_timeout_s,
        )
        return _error_result(connector, req, ConnectorStatus.ERROR, "timeout", started)
    except httpx.HTTPStatusError as e:
        status = (
            ConnectorStatus.BLOCKED
            if e.response.status_code in (401, 403, 429)
            else ConnectorStatus.ERROR
        )
        logger.warning(
            "connector http {} | connector={} target_hash={}",
            e.response.status_code, connector.name, req.target_hash,
        )
        return _error_result(connector, req, status, f"http_{e.response.status_code}", started)
    except (httpx.TimeoutException, httpx.NetworkError) as e:
        logger.warning(
            "connector network error | connector={} target_hash={} type={}",
            connector.name, req.target_hash, type(e).__name__,
        )
        return _error_result(connector, req, ConnectorStatus.ERROR, type(e).__name__, started)

    if result.elapsed_ms == 0:
        result.elapsed_ms = int((time.monotonic() - started) * 1000)

    if result.status in (ConnectorStatus.FOUND, ConnectorStatus.LIKELY,
                        ConnectorStatus.NOT_FOUND, ConnectorStatus.UNCERTAIN):
        try:
            await cache_backend.set(cache_key, result.model_dump_json(), ttl=cache_ttl_s)
        except (ConnectionError, TimeoutError):
            logger.warning("connector cache set failure | connector={}", connector.name)

    return result


def _error_result(
    connector: Connector,
    req: ConnectorRequest,
    status: ConnectorStatus,
    reason: str,
    started: float,
) -> ConnectorResult:
    return ConnectorResult(
        connector=connector.name,
        target_type=req.target_type,
        status=status,
        confidence_score=0,
        confidence_level="none",
        evidence=[],
        warnings=[reason],
        fetched_at=datetime.now(timezone.utc),
        cache_hit=False,
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )
```

**Tests:** `tests/unit/connectors/test_runner.py` — mock connector that:
- Returns FOUND → cached → second call returns `cache_hit=True`
- Raises `asyncio.TimeoutError` → result has `status=ERROR`, `warnings=['timeout']`
- Raises `httpx.HTTPStatusError(429)` → `status=BLOCKED`
- Raises `httpx.HTTPStatusError(500)` → `status=ERROR`

**Acceptance:** all tests green. Coverage of `run_connector` ≥90%.

**Commit:** `feat(connectors): add runner with timeout/rate-limit/cache/audit hardening`

---

### R1-2 — Alembic migration (search_jobs + search_events, G1 hash-only)

**File to create:** `migrations/versions/0004_real_time_osint_jobs.py`

**Migration body:**

```python
"""real-time OSINT job store -- hash-only payload + TTL 7d (G1)

Revision ID: 0004_real_time_osint_jobs
Revises: 0003_indexes_constraints
Create Date: 2026-05-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_real_time_osint_jobs"
down_revision = "0003_indexes_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_type", sa.Text, nullable=False),
        sa.Column("target_hash", sa.Text, nullable=False),
        sa.Column("target_encrypted", sa.LargeBinary, nullable=True),  # G1=a -> stays NULL
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("overall_status", sa.Text, nullable=True),
        sa.Column("overall_confidence", sa.Integer, nullable=True),
        sa.Column("connectors_planned", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("connectors_run", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("elapsed_ms", sa.Integer, nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("ix_search_jobs_user_id_created_at", "search_jobs", ["user_id", "created_at"])
    op.create_index("ix_search_jobs_expires_at", "search_jobs", ["expires_at"])
    op.create_index("ix_search_jobs_target_hash", "search_jobs", ["target_hash"])

    op.create_table(
        "search_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("search_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("emitted_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("job_id", "seq", name="uq_search_events_job_seq"),
    )
    op.create_index("ix_search_events_job_id_seq", "search_events", ["job_id", "seq"])


def downgrade() -> None:
    op.drop_index("ix_search_events_job_id_seq", table_name="search_events")
    op.drop_table("search_events")
    op.drop_index("ix_search_jobs_target_hash", table_name="search_jobs")
    op.drop_index("ix_search_jobs_expires_at", table_name="search_jobs")
    op.drop_index("ix_search_jobs_user_id_created_at", table_name="search_jobs")
    op.drop_table("search_jobs")
```

**Verify revision id matches `down_revision` of next migration if any.** Check `migrations/versions/` for actual filename of `0003_indexes_constraints` and adjust `down_revision` to its `revision` constant.

**Run locally:**
```bash
docker compose up -d postgres
alembic upgrade head
docker compose exec postgres psql -U nexus -d nexusosint_test -c "\d search_jobs"
docker compose exec postgres psql -U nexus -d nexusosint_test -c "\d search_events"
alembic downgrade -1
alembic upgrade head
```

**Acceptance:** `alembic upgrade head` and `alembic downgrade -1` both succeed. Tables present after upgrade, absent after downgrade.

**Commit:** `feat(db): add search_jobs + search_events tables (G1 hash-only TTL 7d)`

---

### R1-3 — `api/services/job_store.py`

**File to create:** `api/services/job_store.py`

**Contract methods:**

```python
"""Job store CRUD using asyncpg.Pool. Replay uses fetch_stream (cursor),
never fetch_all on events table (could be 1000s of rows per job)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from uuid import UUID, uuid4

from api.db import db as _db
from modules.connectors.base import ConnectorStatus, TargetType

# G1: TTL 7 days (hash-only)
JOB_TTL = timedelta(days=7)


async def create_job(
    *,
    user_id: int,
    target_type: TargetType,
    target_hash: str,
    connectors_planned: list[str],
) -> UUID:
    """Insert a queued job, return its UUID."""
    job_id = uuid4()
    now = datetime.now(timezone.utc)
    expires_at = now + JOB_TTL
    await _db.execute(
        """
        INSERT INTO search_jobs
            (id, user_id, target_type, target_hash, status,
             connectors_planned, created_at, expires_at)
        VALUES ($1, $2, $3, $4, 'queued', $5, $6, $7)
        """,
        job_id, user_id, target_type.value, target_hash,
        connectors_planned, now, expires_at,
    )
    return job_id


async def mark_running(job_id: UUID) -> None:
    await _db.execute(
        "UPDATE search_jobs SET status='running', started_at=NOW() WHERE id=$1",
        job_id,
    )


async def mark_done(
    job_id: UUID,
    *,
    overall_status: ConnectorStatus,
    overall_confidence: int,
    connectors_run: list[str],
    elapsed_ms: int,
) -> None:
    await _db.execute(
        """
        UPDATE search_jobs SET status='done', overall_status=$1, overall_confidence=$2,
            connectors_run=$3, finished_at=NOW(), elapsed_ms=$4
        WHERE id=$5
        """,
        overall_status.value, overall_confidence, connectors_run, elapsed_ms, job_id,
    )


async def mark_failed(job_id: UUID, *, reason: str) -> None:
    await _db.execute(
        "UPDATE search_jobs SET status='failed', finished_at=NOW() WHERE id=$1",
        job_id,
    )


async def get_job(job_id: UUID) -> dict | None:
    row = await _db.fetchrow(
        "SELECT * FROM search_jobs WHERE id=$1", job_id,
    )
    return dict(row) if row else None


async def append_event(job_id: UUID, seq: int, event_type: str, payload: dict) -> None:
    """Insert one event. Caller computes seq monotonic per job.
    payload MUST be sanitized (no target_value in claro) before this call."""
    import json
    await _db.execute(
        """
        INSERT INTO search_events (job_id, seq, event_type, payload)
        VALUES ($1, $2, $3, $4::jsonb)
        """,
        job_id, seq, event_type, json.dumps(payload),
    )


async def stream_events(
    job_id: UUID, *, from_seq: int = 0,
) -> AsyncGenerator[dict, None]:
    """Replay events for SSE. Uses cursor — never fetch_all."""
    async for row in _db.fetch_stream(
        "SELECT seq, event_type, payload, emitted_at FROM search_events "
        "WHERE job_id = $1 AND seq > $2 ORDER BY seq ASC",
        job_id, from_seq,
    ):
        yield {
            "seq": row["seq"],
            "event_type": row["event_type"],
            "payload": row["payload"],
            "emitted_at": row["emitted_at"],
        }


async def purge_expired() -> int:
    """Delete expired jobs; events cascade via FK ON DELETE CASCADE.
    Returns number of jobs deleted."""
    now = datetime.now(timezone.utc)
    result = await _db.execute(
        "DELETE FROM search_jobs WHERE expires_at < $1", now,
    )
    return int(result.split()[-1]) if result else 0
```

**Note:** verify `_db.fetch_stream` and `_db.fetchrow` exist in `api/db.py`. If not present, halt and ask Math whether to add or use `_db.fetch` (with row cap warning).

**Tests:** `tests/integration/test_job_store.py` — uses Postgres test fixture, creates job, inserts 50 events, replays with `from_seq=10` → expects 40 rows in order.

**Commit:** `feat(jobs): add job_store with create/append/stream/purge`

---

### R1-4 — `modules/connectors/username/sherlock_adapter.py`

**Files to create:**
- `modules/connectors/username/__init__.py` (empty)
- `modules/connectors/username/sherlock_adapter.py`
- `tests/unit/connectors/username/__init__.py` (empty)
- `tests/unit/connectors/username/test_sherlock_adapter.py`

**Contract:**

```python
"""Adapter: wraps existing modules.username_check.runner.search_username
and translates ScoredResult (6-state) into ConnectorResult (8-state).

CANONICAL MAPPING (mirrors client-side adapter in static/js/legacy-adapter.js):
    confirmed             -> FOUND
    likely                -> LIKELY      (MUST NOT collapse to FOUND)
    uncertain             -> UNCERTAIN
    likely_false_positive -> NOT_FOUND
    not_found             -> NOT_FOUND
    invalid (auth/login)  -> BLOCKED
    invalid (fetch_error) -> ERROR
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from modules.connectors.base import (
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    Evidence,
    TargetType,
    derive_confidence_level,
)
from modules.username_check.runner import search_username as _legacy_run
from modules.username_check.scoring import ScoredResult


_STATUS_MAP: dict[str, ConnectorStatus] = {
    "confirmed":             ConnectorStatus.FOUND,
    "likely":                ConnectorStatus.LIKELY,
    "uncertain":             ConnectorStatus.UNCERTAIN,
    "likely_false_positive": ConnectorStatus.NOT_FOUND,
    "not_found":             ConnectorStatus.NOT_FOUND,
}


def _map_invalid(scored: ScoredResult) -> ConnectorStatus:
    warns = set(scored.warnings)
    blocked_signals = {"bot_check", "login_required", "redirect_to_login"}
    if warns & blocked_signals or any(
        e.signal.startswith("linkedin_auth") for e in scored.evidence
    ):
        return ConnectorStatus.BLOCKED
    return ConnectorStatus.ERROR


def map_scored_to_connector_status(scored: ScoredResult) -> ConnectorStatus:
    """Pure function — tested in isolation."""
    if scored.validation_status == "invalid":
        return _map_invalid(scored)
    return _STATUS_MAP.get(scored.validation_status, ConnectorStatus.UNCERTAIN)


class SherlockAdapter:
    target_types = (TargetType.USERNAME,)
    default_timeout_s = 30
    rate_limit_cps = 2.0

    def __init__(self, platform: str) -> None:
        self._platform = platform
        self.name = f"sherlock:{platform}"

    async def run(
        self,
        req: ConnectorRequest,
        http: httpx.AsyncClient,
    ) -> ConnectorResult:
        # Delegate to legacy runner. Adjust the shape extraction below
        # to match the actual return value of search_username().
        raw_results = await _legacy_run(req.target_value, sites=[self._platform])
        platform_data = raw_results.get(self._platform)
        if not platform_data:
            return ConnectorResult(
                connector=self.name,
                target_type=TargetType.USERNAME,
                status=ConnectorStatus.NOT_FOUND,
                confidence_score=0,
                confidence_level="none",
                evidence=[],
                warnings=["no_data_for_platform"],
                fetched_at=datetime.now(timezone.utc),
                elapsed_ms=0,
            )

        scored: ScoredResult = platform_data["scored"]  # ADJUST per legacy shape
        status = map_scored_to_connector_status(scored)
        return ConnectorResult(
            connector=self.name,
            target_type=TargetType.USERNAME,
            status=status,
            confidence_score=scored.confidence_score,
            confidence_level=derive_confidence_level(scored.confidence_score),
            evidence=[
                Evidence(signal=e.signal, weight=e.weight, detail=e.detail or "")
                for e in scored.evidence
            ],
            warnings=scored.warnings,
            raw_url=platform_data.get("url"),
            data={"platform": self._platform},
            fetched_at=datetime.now(timezone.utc),
            cache_hit=False,
            elapsed_ms=platform_data.get("elapsed_ms", 0),
        )
```

**Note:** the exact shape of `_legacy_run(...)` return value depends on `modules.username_check.runner.search_username` — Codex MUST read that function signature first. Adjust the `platform_data` extraction to match actual API. If shape is unclear, halt and ask Math.

**Tests:** unit tests for `map_scored_to_connector_status` covering all 6 legacy statuses + the two `invalid` sub-cases. Integration test mocks `_legacy_run` to return fixed dict and asserts `ConnectorResult` shape.

**Commit:** `feat(connectors): add sherlock_adapter mapping 6-state scoring to 8-state ConnectorResult`

---

### R1-5 — `modules/connectors/oathnet_adapter.py`

Same pattern as R1-4 but wraps `modules.oathnet_client`. Emit one `ConnectorResult` per OathNet feature consumed (breach, stealer, ip_info, victims). Sanitize: never include raw `target_value` in `data` dict; use record counts + summary fields only.

**Commit:** `feat(connectors): add oathnet_adapter for breach/stealer/ip_info/victims`

---

### R1-6 — `modules/connectors/phone/carrier_lookup.py`

**Add to `requirements.txt`:** `phonenumbers==9.0.10` (or latest 9.0.x stable as of execution date — pin major.minor)

**Connector:**

```python
"""Offline phone carrier lookup via phonenumbers lib.
Status maximum is LIKELY — knowing carrier never proves account existence."""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
import phonenumbers
from phonenumbers import carrier, geocoder, NumberParseException

from modules.connectors.base import (
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    Evidence,
    TargetType,
    derive_confidence_level,
)


class CarrierLookup:
    name = "carrier_lookup"
    target_types = (TargetType.PHONE,)
    default_timeout_s = 5
    rate_limit_cps = 100.0

    async def run(
        self,
        req: ConnectorRequest,
        http: httpx.AsyncClient,
    ) -> ConnectorResult:
        try:
            parsed = phonenumbers.parse(req.target_value, None)
        except NumberParseException:
            return self._not_found(req, reason="parse_failure")

        if not phonenumbers.is_valid_number(parsed):
            return self._not_found(req, reason="invalid_number")

        carrier_name = carrier.name_for_number(parsed, "en")
        country = geocoder.description_for_number(parsed, "en")
        line_type = self._line_type(parsed)

        evidence = []
        score = 0
        if carrier_name:
            evidence.append(Evidence(signal="carrier_known", weight=40, detail=carrier_name))
            score += 40
        if country:
            evidence.append(Evidence(signal="country_known", weight=20, detail=country))
            score += 20
        if line_type:
            evidence.append(Evidence(signal="line_type_known", weight=15, detail=line_type))
            score += 15

        status = ConnectorStatus.LIKELY if score > 0 else ConnectorStatus.NOT_FOUND
        capped_score = min(score, 75)

        return ConnectorResult(
            connector=self.name,
            target_type=TargetType.PHONE,
            status=status,
            confidence_score=capped_score,
            confidence_level=derive_confidence_level(capped_score),
            evidence=evidence,
            warnings=[],
            data={
                "carrier": carrier_name,
                "country": country,
                "line_type": line_type,
            },
            fetched_at=datetime.now(timezone.utc),
            cache_hit=False,
            elapsed_ms=0,
        )

    def _not_found(self, req: ConnectorRequest, *, reason: str) -> ConnectorResult:
        return ConnectorResult(
            connector=self.name,
            target_type=TargetType.PHONE,
            status=ConnectorStatus.NOT_FOUND,
            confidence_score=0,
            confidence_level="none",
            evidence=[],
            warnings=[reason],
            fetched_at=datetime.now(timezone.utc),
            elapsed_ms=0,
        )

    @staticmethod
    def _line_type(parsed) -> str:
        t = phonenumbers.number_type(parsed)
        mapping = {
            phonenumbers.PhoneNumberType.MOBILE: "mobile",
            phonenumbers.PhoneNumberType.FIXED_LINE: "fixed_line",
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "fixed_or_mobile",
            phonenumbers.PhoneNumberType.VOIP: "voip",
        }
        return mapping.get(t, "unknown")
```

**Tests:** `tests/unit/connectors/phone/test_carrier_lookup.py` — BR mobile (`+5511987654321`), US landline (`+12125551234`), invalid (`+123`), empty string. ZERO network calls — pure offline. Status MAX is LIKELY in all valid cases.

**Verify Docker image size after install:**
```bash
docker compose build nexus
docker images nexus
```
Must stay <250MB. If breached, halt and ask Math.

**Commit:** `feat(connectors): add offline carrier_lookup via phonenumbers (status max=LIKELY)`

---

### R1-7 — `api/services/search_orchestrator.py`

Aggregates connector results applying G3 quorum rule.

**Core aggregation function:**

```python
def aggregate_overall_status(
    results: list[ConnectorResult],
) -> tuple[ConnectorStatus, int, float]:
    """Apply G3: overall_status='found' only if >=2 connectors agree on FOUND.
    Returns (overall_status, overall_confidence, agreement_ratio)."""
    found_results = [r for r in results if r.status == ConnectorStatus.FOUND]
    likely_results = [r for r in results if r.status == ConnectorStatus.LIKELY]
    not_found_results = [r for r in results if r.status == ConnectorStatus.NOT_FOUND]
    blocked_results = [r for r in results if r.status == ConnectorStatus.BLOCKED]
    error_results = [r for r in results if r.status == ConnectorStatus.ERROR]
    uncertain_results = [r for r in results if r.status == ConnectorStatus.UNCERTAIN]

    total_decisive = (
        len(found_results) + len(likely_results)
        + len(not_found_results) + len(uncertain_results)
    )

    if len(found_results) >= 2:
        overall = ConnectorStatus.FOUND
        confidence = int(sum(r.confidence_score for r in found_results) / len(found_results))
    elif len(found_results) == 1:
        # Single FOUND -> demote to LIKELY (anti-FP per G3)
        overall = ConnectorStatus.LIKELY
        confidence = min(found_results[0].confidence_score, 70)
    elif len(likely_results) >= 1:
        overall = ConnectorStatus.LIKELY
        confidence = int(sum(r.confidence_score for r in likely_results) / len(likely_results))
    elif len(not_found_results) > 0 and (len(blocked_results) + len(error_results)) > 0:
        overall = ConnectorStatus.UNCERTAIN
        confidence = 0
    elif len(results) > 0 and len(blocked_results) == len(results):
        overall = ConnectorStatus.BLOCKED
        confidence = 0
    elif len(results) > 0 and len(error_results) == len(results):
        overall = ConnectorStatus.ERROR
        confidence = 0
    elif len(results) > 0 and len(not_found_results) == len(results):
        overall = ConnectorStatus.NOT_FOUND
        confidence = 0
    else:
        overall = ConnectorStatus.UNCERTAIN
        confidence = 0

    agreement_ratio = (len(found_results) + len(likely_results)) / max(total_decisive, 1)
    return overall, confidence, agreement_ratio
```

**Tests:** `tests/unit/test_search_orchestrator.py` — 8 scenarios:
1. 3 FOUND → overall FOUND
2. 2 FOUND + 1 NOT_FOUND → overall FOUND
3. 1 FOUND + 2 LIKELY → overall LIKELY (single FOUND demoted)
4. 0 FOUND + 3 LIKELY → overall LIKELY
5. 1 FOUND + 1 NOT_FOUND + 1 BLOCKED → overall UNCERTAIN (demoted + disagreement)
6. 3 BLOCKED → overall BLOCKED
7. 3 ERROR → overall ERROR
8. 3 NOT_FOUND → overall NOT_FOUND

**Commit:** `feat(orchestrator): add search_orchestrator with G3 quorum aggregation`

---

### R1-8 — `api/routes/search_v2.py`

**Endpoints:**
- `POST /api/v2/search` → validate input, detect target_type, create job, enqueue, return `201 {job_id, sse_url}`
- `GET /api/v2/search/{job_id}` → return job snapshot (status, overall_status, summary)
- `GET /api/v2/search/{job_id}/events?from_seq=N` → SSE stream of replayed + live events

**Auth:** `Depends(get_current_user)` — REJECT cross-user access (`job.user_id != current_user.id` → 403).

**Sanitization rule:** every `payload` written to `search_events` via `job_store.append_event()` MUST go through `_sanitize_payload()` which strips any `target_value` field.

**Register router in `api/main.py`** after line 277:
```python
from api.routes import search_v2 as _search_v2_routes
app.include_router(_search_v2_routes.router)
```

**Cross-user test (security-critical):** integration test asserts user B cannot read user A's job events → 403.

**Commit:** `feat(api): add /api/v2/search with SSE replay (auth-scoped, sanitized payload)`

---

### R1-9 — Frontend `static/js/v2-search.js`

Wired to `/api/v2/search` behind flag `?engine=v2`. Reuses R0-3 components. **No fake cancel button.**

Use `EventSource` API for SSE. On reconnect, send `?from_seq=<last_seq>` to resume from where dropped.

**Commit:** `feat(ui): add v2 search engine consumer behind ?engine=v2 flag`

---

### R1-10 — SKIPPED per G2 decision

Do not create `modules/connectors/email/gravatar.py`. Note this in commit log of R1-12.

---

### R1-11 — Job cleanup loop

Extend `api/tasks.py`. Follow existing pattern of `blacklist_purge_loop`. Run every 1h. Calls `job_store.purge_expired()`.

**Commit:** `feat(jobs): add job cleanup loop (TTL 7d per G1)`

---

### R1-12 — Documentation update

Update `docs/CONNECTORS.md` and `.planning/PROJECT.md` with:
- R1 connectors list (sherlock_adapter, oathnet_adapter, carrier_lookup; gravatar deferred per G2)
- Final G1-G4 implementation notes
- API v2 endpoint reference

**Commit:** `docs(connectors): update for R1 implementation (G2 gravatar deferred)`

---

### R1 wrap-up

```bash
pytest --tb=short -q

docker compose build nexus
docker images nexus  # must be <250MB

docker compose up -d
# wait 30s for app to settle
docker stats --no-stream nexus  # must be <500MB resting

git push -u origin v4.1/r1-safe-mvp
gh pr create --title "R1 safe MVP -- /api/v2/search + job store + adapters" --body "..."
```

After merge: deploy to VPS via SCP+rebuild (see `CLAUDE.md` "DEPLOY — VPS PRODUCTION"). Monitor 7 days with flag off. Then enable for subset of users.

---

## 7. Commit conventions

Format: Conventional Commits. Trailer required.

```
<type>(<scope>): <subject 50 chars max>

<body — wrap 72 chars, explain WHY not WHAT>

Refs .planning/R0_R1_REVISION.md

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

**Types:** `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`.
**Scope examples:** `connectors`, `ui`, `db`, `jobs`, `api`, `cases`.

**One commit per task** (R0-1, R0-2, ..., R1-11). Do not batch.

---

## 8. When to HALT and ask Math

Halt immediately and ask in PR comment / chat, if:

1. Any pre-existing file's signature differs from what this handoff describes.
2. Migration `alembic upgrade head` fails on staging or VPS.
3. Docker image breaches 250MB.
4. Any test that was previously green turns red.
5. A connector returns status `FOUND` from single source aggregator (anti-FP regression — STOP and audit).
6. `likely` appears as `found` in any UI state.
7. `blocked` appears as `not_found` or `error` in any UI state.
8. `CLAUDE.md`, `meridian.css`/`tokens.css`, `docker-compose.prod.yml`, or `.env` files need editing.
9. Search returns `target_value` in any log line or `search_events.payload`.
10. Cross-user job access doesn't return 403 (security regression).
11. Any task's acceptance criterion cannot be met without scope creep.

**Do not silently expand scope.** "Continuar" advances the next task in the listed order; it does not authorize new tasks beyond R0-7 / R1-12 (excluding R1-10).

---

## 9. Quick reference

**Run tests:**
```bash
pytest tests/unit/connectors/ -v                    # R0-1 + R1 unit
pytest tests/integration/test_job_store.py -v       # R1-3
pytest tests/integration/test_search_v2_api.py -v   # R1-8
pytest tests/e2e/realtime-search.spec.ts            # R1 E2E (Playwright)
pytest --tb=short -q                                # full suite
```

**Run app locally:**
```bash
docker compose up -d postgres redis
uvicorn api.main:app --reload --port 8000
# Visit http://localhost:8000/?theme=graphite
```

**Alembic:**
```bash
alembic upgrade head
alembic downgrade -1
alembic current
```

**Deploy (after merge to master, per CLAUDE.md):**
```bash
scp -r api/ static/ modules/ migrations/ requirements.txt root@87.99.153.11:/root/nexus-osint/
ssh root@87.99.153.11 "cd /root/nexus-osint && docker compose up -d --build"
ssh root@87.99.153.11 "docker logs nexus_osint-nexus-1 --tail 50"
```

**Branch protocol:**
- One branch per phase: `v4.1/r0-contract-shim`, then `v4.1/r1-safe-mvp`
- One commit per task
- PR opens only when ALL tasks in phase complete + acceptance verified
- Merge to master only after Math approves PR
- Deploy only after merge

---

## 10. File map (R0/R1 deltas)

```
NEW FILES (R0):
  modules/connectors/__init__.py
  modules/connectors/base.py
  tests/unit/connectors/__init__.py
  tests/unit/connectors/test_base.py
  static/css/tokens-graphite.css
  static/css/connectors.css
  static/js/theme-flag.js
  static/js/components/status-pill.js
  static/js/components/connector-card.js
  static/js/components/confidence-meter.js
  static/js/components/evidence-drawer.js
  static/js/legacy-adapter.js
  static/dev/components-preview.html
  docs/CONNECTORS.md

EDITED FILES (R0):
  static/index.html              # add theme-flag.js script, change hero copy, remove quota
  static/admin.html              # add theme-flag.js script
  static/js/render.js            # call legacy adapter when NX_V2 true
  static/js/cases.js             # enrich metadata, wire PDF export
  .planning/PROJECT.md           # append G1-G4 decisions

NEW FILES (R1):
  modules/connectors/runner.py
  modules/connectors/username/__init__.py
  modules/connectors/username/sherlock_adapter.py
  modules/connectors/oathnet_adapter.py
  modules/connectors/phone/__init__.py
  modules/connectors/phone/carrier_lookup.py
  api/services/job_store.py
  api/services/search_orchestrator.py
  api/routes/search_v2.py
  static/js/v2-search.js
  static/js/job-replay.js
  migrations/versions/0004_real_time_osint_jobs.py
  tests/unit/connectors/test_runner.py
  tests/unit/connectors/username/__init__.py
  tests/unit/connectors/username/test_sherlock_adapter.py
  tests/unit/connectors/phone/__init__.py
  tests/unit/connectors/phone/test_carrier_lookup.py
  tests/unit/test_search_orchestrator.py
  tests/integration/test_job_store.py
  tests/integration/test_search_v2_api.py
  tests/e2e/realtime-search.spec.ts

EDITED FILES (R1):
  api/main.py                    # register search_v2 router
  api/tasks.py                   # add job cleanup loop
  requirements.txt               # +phonenumbers==9.0.10
  docs/CONNECTORS.md             # update with R1 connectors
  .planning/PROJECT.md           # final G1-G4 notes

UNTOUCHED (CLAUDE.md protected):
  CLAUDE.md
  .env / .env.production
  static/css/meridian.css        # (verify exact name; may be tokens.css)
  docker-compose.prod.yml
```

---

**End of handoff.** Codex starts with §4 (pre-flight), then R0-1. Halt criteria in §8 are absolute.
