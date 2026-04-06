# Phase 07: F6 Stack Modernization - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-06
**Phase:** 07-f6-stack-modernization
**Areas discussed:** Test gate scope, Rollback depth, Tenacity disposition

---

## Pre-discussion Findings

Codebase scan revealed significant work already complete before this phase:
- `PyJWT==2.9.0` already in requirements.txt, `import jwt` already in `api/main.py` — JWT migration done
- `aiohttp`, `requests`, `python-jose` already removed — httpx migration done (Phase 11)
- `tenacity==8.5.0` present but completely unwired (confirmed by STACK.md and codebase scan)
- `tests/test_endpoints.py` exists (untracked) with 2 tests: `test_full_nexus_flow` + `test_unauthorized_access`

---

## Tenacity Disposition

| Option | Description | Selected |
|--------|-------------|----------|
| Remove it | Fewer deps = smaller image, less attack surface. Manual backoff in SpiderFoot already works. | ✓ |
| Keep it | Hedge against future use. Adds ~0.5MB, no runtime cost if unused. | |

**User's choice:** Remove it (Recommended)
**Notes:** No hesitation. Clear preference for lean dependencies.

---

## Rollback Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal — git revert note | One commit per sub-task. Rollback = git revert the merge commit. | |
| Full runbook | pip freeze snapshot, docker tag backup, step-by-step revert commands. | ✓ |

**User's choice:** Full runbook
**Notes:** Matches the full F6 template in CLAUDE.md exactly.

---

## Test Gate Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Extend what exists (Recommended) | Add /health test + JWT roundtrip test. 4 tests total. | ✓ |
| Full integration suite | Auth + scan + health + admin + rate limiting. More work. | |
| Current 2 tests are enough | Run existing 2 on 3.12, if green proceed. | |

**User's choice:** Extend what exists (Recommended)
**Notes:** 4 tests: login, auth guard, /health, JWT roundtrip. Minimal viable gate.

---

## Claude's Discretion

- Whether to pin Python 3.12 to a digest after stabilizing
- mypy/pyright flags during 3.12 compat check
- FIND-16 fix implementation detail (obvious from CONCERNS.md)

## Deferred Ideas

None.
