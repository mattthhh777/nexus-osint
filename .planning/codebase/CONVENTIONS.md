# Coding Conventions

**Analysis Date:** 2026-04-19

## Naming Patterns

**Files:**
- Python modules: `snake_case.py` (e.g., `oathnet_client.py`, `spiderfoot_wrapper.py`)
- JavaScript modules: `camelCase.js` (e.g., `searchHistory.js`, `renderUtils.js`)
- Private modules in Python: prefix with underscore (e.g., `_bcrypt_lib` for internal imports)
- Test files: `test_*.py` or `*_test.py` pattern

**Functions:**
- Python async/sync: `snake_case` (e.g., `async def startup()`, `def _validate_jwt_secret()`)
- JavaScript: `camelCase` (e.g., `startSearch()`, `setMode()`, `buildCatChips()`)
- Private/internal Python functions: prefix with underscore (e.g., `_create_token()`, `_decode_token()`)
- Private/internal JavaScript: underscore prefix or inline closures (e.g., `_table_exists()`, nested helpers in larger functions)

**Variables:**
- Python: `snake_case` (e.g., `max_concurrent`, `current_oathnet`, `db_path`)
- JavaScript: `camelCase` (e.g., `authUser`, `selectedMods`, `currentResult`)
- Constants (both languages): `UPPER_SNAKE_CASE` (e.g., `GLOBAL_CONCURRENCY_LIMIT`, `JWT_EXPIRE_HOURS`, `TYPE_LABELS`)

**Types/Classes:**
- Python dataclasses: `PascalCase` (e.g., `BreachRecord`, `OathnetResult`, `DatabaseManager`)
- Python Pydantic models: `PascalCase` (e.g., `SearchRequest`)
- Python enums: `PascalCase` (e.g., `DegradationMode`)
- JavaScript: no class-based code in this codebase (module-scoped functions + object literals)

## Code Style

**Formatting:**
- Python: PEP 8 style, implicit via linting (no explicit formatter tool configured, but patterns suggest standard)
- JavaScript: 2-space indentation, no semicolons (observed in existing code)
- Line length: Python modules typically stay under 120 chars; JavaScript varies but generally concise

**Linting:**
- No explicit `.eslintrc` or `.prettierrc` in codebase
- Python exception handling enforces specific patterns (see "Error Handling" section)
- JavaScript validation happens via manual type-checking in utility functions (e.g., `typeof url !== 'string'`)

## Import Organization

**Order (Python):**
1. `from __future__ import annotations` (always first if present)
2. Standard library imports (`asyncio`, `logging`, `os`, etc.)
3. Third-party imports (`httpx`, `pydantic`, `fastapi`, etc.)
4. Local imports (`from api.db import db`, `from modules.oathnet_client import oathnet_client`)
5. Exception handling imports grouped near top (e.g., JWT exceptions in `api/main.py` lines 37-41)

**Observed Pattern (from `api/main.py`):**
```python
from __future__ import annotations  # if PEP 563 deferred evaluation needed

import asyncio
import hashlib
import json
import logging
# ... more stdlib ...

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
# ... more third-party ...

from api.db import db as _db
from api.orchestrator import get_orchestrator, DegradationMode
from modules.oathnet_client import oathnet_client
```

**Path Aliases:**
- No explicit `pathlib` aliases configured in `pyproject.toml` or `setup.cfg`
- Module imports use relative paths from project root (e.g., `from api.db import db`)

## Error Handling

**Pattern (from CLAUDE.md — strictly enforced):**

**In FastAPI endpoints (HTTPException required):**
```python
# ✅ CORRECT
@router.get("/scan/{target}")
async def run_scan(target: str):
    try:
        result = await orchestrator.run(target)
        return result
    except ValueError as e:
        # Input validation failed — 400
        raise HTTPException(status_code=400, detail=str(e))
    except asyncio.TimeoutError:
        # Timeout — 504
        logger.warning("Scan timeout | target_hash={}", hash(target))
        raise HTTPException(status_code=504, detail="Scan timed out")
    except aiosqlite.Error as e:
        # DB error — 503
        logger.error("DB error: {}", type(e).__name__)
        raise HTTPException(status_code=503, detail="Database unavailable")
    except Exception as e:
        # Unexpected — 500, log fully, never expose details
        logger.exception("Unhandled error in scan endpoint")
        raise HTTPException(status_code=500, detail="Internal error")
```

**In async agents (let TaskGroup handle cancellation):**
```python
# ✅ CORRECT — inside _guarded() in api/orchestrator.py
async def _guarded(...) -> None:
    try:
        # agent work here
    except asyncio.CancelledError:
        # Task was cancelled by orchestrator
        logger.info("Module '%s' was cancelled", name)
    except Exception as exc:
        # Module failed — push to result queue, don't raise
        logger.warning("Module '%s' failed: %s", name, type(exc).__name__)
        await self._result_queue.put((name, exc))
```

**Errors NOT to catch (let them propagate):**
- `asyncio.CancelledError` in TaskGroup contexts (mark explicitly if caught: `noqa: BLE001`)
- Generic `except Exception` outside of documented guard functions (marked with `noqa: BLE001` + comment)
- Errors in background loops (watchdog) use `logger.exception()` to log but continue

**Observable enforcement in codebase:**
- `api/watchdog.py:123` — catch-all in background loop marked `# noqa: BLE001 — documented background-loop guard`
- `api/orchestrator.py:249` — module error handler in `_guarded()` marked `# noqa: BLE001` with explanatory comment
- All endpoint handlers convert to HTTPException with specific status codes

## Logging

**Framework:** Python standard `logging` module (no loguru, no structlog)

**Configuration:**
- Configured in `api/main.py:120-121`: `logging.basicConfig()` + module-level logger
- Logger per module: `logger = logging.getLogger(__name__)`
- Log level from env: `LOG_LEVEL` env var (default: `WARNING`)

**Patterns:**

**Info level (startup/shutdown):**
```python
logger.info("DatabaseManager started — WAL mode active, writer task running")
logger.info("NexusOSINT v3.0 started — %d allowed origins, tracemalloc active", len(origins))
```

**Warning level (recoverable issues):**
```python
logger.warning("DatabaseManager.startup() called more than once — ignoring")
logger.warning("DB write queue at %d/1000 — approaching capacity", qsize)
logger.warning("Module '%s' failed: %s", name, type(exc).__name__)
```

**Error level (failed operations, always include reason):**
```python
logger.error("DB write error — sql=%r params=%r error=%s", sql, params, exc)
logger.error("DB write queue full (maxsize=1000) — dropping write: sql=%r", sql)
```

**Exception level (with traceback):**
```python
logger.exception("Unhandled error in scan endpoint")  # includes traceback
```

**Never log:**
- User data directly (hash instead: `logger.warning("... target_hash={}", hash(target))`)
- Raw passwords or API keys
- Full query strings from untrusted sources (summarize instead)

**JavaScript logging:**
- Uses native `console.warn()` / `console.error()` sparingly
- Example: `console.warn('[NexusOSINT] URL bloqueada (protocolo inválido):', url.slice(0, 80));` (in `utils.js`)
- No structured logging in frontend; warnings are security/validation related only

## Comments

**When to Comment:**
- Module docstrings: Always (see `api/db.py:1-20`, `api/orchestrator.py:1-31`)
- Function docstrings: For public APIs and complex logic
- Inline comments: For non-obvious decisions (e.g., semaphore acquisition order to prevent deadlock)
- Section separators: ASCII dividers for major subsections (e.g., `# ── Lifecycle ─────────────────────`)

**JSDoc/TSDoc:**
- Not used (Python docstrings are standard, JavaScript is untyped vanilla)
- Docstring format: reStructuredText style (not Google/NumPy style)

**Example (from `api/db.py`):**
```python
"""
Manages a single persistent SQLite connection with WAL mode and
serialized writes via asyncio.Queue.
"""

def __init__(self, db_path: Optional[Path] = None) -> None:
    """Initialize the database manager.
    
    Args:
        db_path: path to SQLite file
    """
```

## Function Design

**Size:** Typical range 20-80 lines; larger functions break into helpers
- Example: `api/orchestrator.py` `_run_module()` is ~25 lines
- Example: `api/main.py` `_stream_search()` is ~200 lines (largest, includes inline helper)

**Parameters:** Type hints always present in Python
```python
async def run_scan(self, target: str, timeout_s: int = 30) -> OathnetResult:
```

**Return Values:** 
- Functions return typed values (dataclasses, dict, or None)
- Example: `async def read_one(...) -> Optional[aiosqlite.Row]`
- Example: `def risk_score(self) -> int`

**Async/await:**
- All I/O bound operations use `async def`
- Pure logic functions stay synchronous
- Example: `async def startup()` (I/O), `def detect_type(q)` (pure logic)

## Module Design

**Exports:**
- No explicit `__all__` in most modules; public APIs implied by docstrings
- Singletons exposed: `oathnet_client` (module-level instance in `modules/oathnet_client.py`), `get_orchestrator()` (function in `api/orchestrator.py`)
- Private internals: prefix with underscore (e.g., `_db`, `_oathnet_sem`)

**Barrel Files:**
- Not used in this codebase (each module explicitly imported by name)
- Example: `from api.db import db` (not `from api import db`)

## JavaScript-Specific Patterns

**Event Handling:**
- DOM event handlers use data attributes: `data-action="select-cat"`, `data-name="..."` (seen in `search.js`)
- Handler naming: `on<Action>` or just action name (e.g., `selectCat()`, `toggleMod()`)
- Event delegation via `querySelectorAll()` + `forEach()` loops

**State Management:**
- Global variables at module scope (e.g., `let authUser = null;`, `let mode = 'auto';`)
- No explicit state library; DOM is single source of truth for UI state
- Derived state via utility functions (e.g., `detectType()` computes query type from string)

**Error Handling (Frontend):**
```javascript
try {
    const evt = JSON.parse(line.slice(6));
    handleEvent(evt);
} catch(e) {}  // Silent on parse errors (malformed SSE lines)
```
- Most errors are logged to toast notifications via `showToast()`
- Network errors trigger redirect to auth screen (in `auth.js`)

**HTML Escaping:**
- Required in all user-facing output
- Utility functions: `esc()` for text content, `escAttr()` for attributes, `sanitizeUrl()` for hrefs
- Example: `` `data-name="${esc(name)}"` `` in template literals

**Fetch Patterns:**
- Uses `apiFetch()` wrapper (defined in `auth.js`) which:
  - Sets `credentials: 'include'` for httpOnly cookies
  - Handles 401 by clearing session and showing auth screen
  - Adds standard headers via `authHeaders()`

## Type Hints

**Usage (Python):**
- All function parameters and return types annotated
- Example: `async def read_one(self, sql: str, params: tuple = ()) -> Optional[aiosqlite.Row]:`
- Generic types via `typing` module: `list[BreachRecord]`, `dict[str, Any]`, `Optional[str]`
- `from __future__ import annotations` used for forward references

**Not enforced for:**
- Local variables (inferred from assignment)
- Lambda functions (rarely used)

---

*Convention analysis: 2026-04-19*
