# Coding Conventions

**Analysis Date:** 2026-03-25

## Naming Patterns

**Python Files:**
- Module files use `snake_case`: `oathnet_client.py`, `sherlock_wrapper.py`, `report_generator.py`, `spiderfoot_wrapper.py`
- Private helpers prefix with `_`: `_load_users`, `_save_users`, `_safe_hash`, `_safe_verify`, `_init_audit_db`, `_log_search`, `_stream_search`, `_serialize_breaches`
- Constants and config in `UPPER_SNAKE_CASE`: `OATHNET_BASE_URL`, `JWT_SECRET`, `MODULE_TIMEOUTS`, `DATA_DIR`, `AUDIT_DB`
- Dataclasses use `PascalCase`: `BreachRecord`, `StealerRecord`, `OathnetResult`, `OathnetMeta`, `SherlockResult`, `PlatformResult`
- Pydantic models use `PascalCase`: `LoginRequest`, `SearchRequest`

**JavaScript Files:**
- Files use `camelCase.js`: `auth.js`, `cases.js`, `export.js`, `history.js`, `panels.js`, `render.js`, `search.js`, `state.js`, `utils.js`
- Functions use `camelCase`: `startSearch`, `handleEvent`, `renderResults`, `buildCatChips`, `toggleMod`, `showToast`, `detectType`
- Module-level state variables use `camelCase`: `authToken`, `authUser`, `currentResult`, `selectedMods`, `activeCat`
- Constants use `UPPER_SNAKE_CASE`: `CATEGORIES`, `MOD_LABELS`, `TYPE_LABELS`, `BREACH_PAGE_SIZE`
- localStorage keys use `nx_` prefix: `nx_token`, `nx_user`, `nx_history`, `nx_cases`

**CSS Classes:**
- BEM-flavored kebab-case: `.discord-card`, `.discord-card-inner`, `.discord-avatar`, `.search-container`, `.search-input`, `.nav-logo-mark`
- State modifiers are bare class additions: `.active`, `.visible`, `.done`, `.error`, `.online`, `.copied`, `.saved`
- Panel/section IDs use `camelCase`: `casesPanel`, `scanModules`, `sfOptions`, `modChips`, `catChips`

## Code Style

**Python Formatting:**
- No formatter config found (no `pyproject.toml`, `.flake8`, `setup.cfg`). Style is manually consistent.
- 4-space indentation throughout
- Trailing inline alignment for constants and short multi-assignments using spaces:
  ```python
  SPIDERFOOT_URL  = os.getenv("SPIDERFOOT_URL", "http://spiderfoot:5001")
  APP_PASSWORD    = os.getenv("APP_PASSWORD", "")
  LOG_LEVEL       = os.getenv("LOG_LEVEL", "WARNING")
  ```
- Max line length approximately 100–120 characters in practice (not enforced)
- Section headers use `# ── Section Name ──────────...` style banners consistently

**JavaScript Formatting:**
- 2-space indentation throughout
- Single quotes for strings: `'nx_token'`, `'auto'`, `'passive'`
- Template literals for HTML generation
- Arrow functions for simple callbacks: `e => { ... }`, `c => c.classList.remove('active')`
- Section headers use `// ══════════════...` banners at file level and `// ── subsection ──` inline

**CSS Formatting:**
- 2-space indentation
- Section banners: `/* ══════════... */` at top of each file
- Values use `var(--token)` for all design tokens from `tokens.css`
- Inline values only for one-off colors not in the token system

## Import Organization

**Python Order:**
1. `from __future__ import annotations` (modules using forward refs)
2. Standard library imports (alphabetical within group)
3. Third-party imports
4. Local imports (deferred inside functions where possible — e.g., `from modules.oathnet_client import OathnetClient` inside `_stream_search`)

Example from `api/main.py`:
```python
import asyncio
import hashlib
import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional, Union

import aiosqlite
import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
```

**JavaScript — No module system.** All JS files are loaded via `<script>` tags. State is shared through globally scoped `let` variables declared at file top. No `import`/`export` syntax used anywhere.

## Error Handling

**Python — Backend:**
- Route handlers use `HTTPException` with explicit `status_code` and `detail` string:
  ```python
  raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
  raise HTTPException(status_code=429, detail="Rate limit exceeded. Max 20 searches/minute.")
  ```
- Module-level helper functions swallow exceptions and return safe defaults with a `logger.warning` or `logger.error` call:
  ```python
  except Exception as exc:
      logger.warning("Quota save failed: %s", exc)
  ```
- SSE stream handlers catch per-module exceptions and yield `module_error` events rather than crashing the stream:
  ```python
  except Exception as exc:
      logger.error("Sherlock failed: %s", exc)
      yield event({"type": "module_error", "module": "sherlock", "error": str(exc)})
  ```
- Rate limiter uses fail-closed on DB errors: `return False  # fail closed — prevent abuse if DB unavailable`
- External API calls in `OathnetClient` use `(bool, dict)` return tuples — never raise:
  ```python
  def _get(self, endpoint, params=None) -> tuple[bool, dict]:
      ...
      except requests.exceptions.ConnectionError as exc:
          return False, {"error": f"Cannot reach OathNet API..."}
  ```
- Per-module timeouts via `with_timeout()` wrapper — returns `(default, timed_out: bool)` rather than raising:
  ```python
  result, timed_out = await with_timeout(asyncio.to_thread(client.holehe, query), "holehe")
  ```

**JavaScript — Frontend:**
- `apiFetch()` centralizes 401 handling: clears token, forces re-login, throws
- All `fetch` calls are wrapped in `try/catch`; errors shown via `showToast()`
- Empty `catch(e) {}` is used for non-critical flows (e.g., `checkAuth` probe requests)
- SSE event parsing uses silent `try/catch` per line: `try { evt = JSON.parse(...) } catch(e) {}`

## Logging

**Framework:** Python `logging` module (`logging.getLogger("nexusosint")`)

**Level Configuration:** Set via `LOG_LEVEL` env var, defaults to `WARNING` in production

**Patterns:**
- Use `%s` format args, never f-strings in logger calls: `logger.warning("Quota save failed: %s", exc)`
- `logger.info` for startup events
- `logger.warning` for recoverable failures (timeouts, DB errors, API errors)
- `logger.error` for unexpected exceptions in business logic
- JavaScript has no structured logging — user-visible errors go to `showToast()`; debug info is silent

## Comments

**Python:**
- Module docstrings at file top with version info and key design decisions (all modules use this)
- Inline comments for non-obvious logic: `# fail closed — prevent abuse if DB unavailable`
- Section banners `# ── Section Name ───...` replace large block comments — used consistently throughout `main.py`
- Function docstrings on public/dependency functions: `"""Dependency: validates JWT and returns user payload."""`
- Portuguese comments appear in `spiderfoot_wrapper.py` and `report_generator.py` (localization inconsistency)

**JavaScript:**
- Section banners `// ══════════ SECTION NAME ══════════` at file top
- Subsection banners `// ── subsection ──` inline
- Inline comments for non-obvious logic: `// Token expired — force re-login`
- No JSDoc usage anywhere

**CSS:**
- Section banners `/* ══════════ SECTION ══════════ */`
- Inline comments for version notes: `/* Nav: refined glassmorphism (enhanced v3.1) */`

## Function Design

**Python:**
- Private helpers prefixed with `_`, kept small and single-purpose
- Async functions used for all I/O; sync functions for pure computation
- Dataclass-based return types preferred over raw dicts in modules (`OathnetResult`, `SherlockResult`)
- Route handlers are thin — delegate to private generator/helper functions
- `_stream_search` is the largest function (~400 lines) — a known complexity issue

**JavaScript:**
- Functions are imperative and DOM-manipulating, typically 5–30 lines
- Global state (`currentResult`, `history`, `cases`, `selectedMods`) is mutated directly
- Event handler functions follow `verbNoun` naming: `startSearch`, `saveCase`, `deleteCase`, `toggleMod`, `loadCase`
- HTML generation uses template literal strings, not DOM API: `` ` <div class="${cls}">${content}</div>` ``

## Module Design

**Python:**
- Each module in `modules/` is a self-contained class or function set with its own dataclasses
- No barrel `__init__.py` re-exports — imports are direct: `from modules.oathnet_client import OathnetClient`
- `api/main.py` imports modules inline inside `_stream_search` to avoid circular import issues

**JavaScript:**
- No module system — global namespace only
- Each `.js` file groups related functions under a section banner
- Cross-file calls are direct function calls (e.g., `render.js` calls `riskLabel()` from `utils.js`)
- Shared state lives in `state.js` (global `let` vars) and `auth.js` (`authToken`, `authUser`)

## CSS Design Tokens

**Token file:** `static/css/tokens.css` — all design values defined as CSS custom properties on `:root`

**Token namespacing:**
- Semantic tokens: `--color-bg-base`, `--color-accent`, `--color-critical`, `--color-text-primary`
- Legacy aliases retained for backward compat: `--bg`, `--amber`, `--red`, `--text`, `--mono`
- Always prefer semantic token names in new code; legacy aliases still used in existing CSS

**Token categories:** surfaces, borders, accent (amber), severity (critical/high/medium/low), semantic (success/info), text, typography, spacing (base-8 scale), radius, shadows, transitions, z-index

---

*Convention analysis: 2026-03-25*
