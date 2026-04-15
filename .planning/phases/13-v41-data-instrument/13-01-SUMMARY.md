---
phase: 13-v41-data-instrument
plan: 01
status: COMPLETE
completed: "2026-04-15"
files_modified:
  - api/main.py
tests: 62 passed, 0 failed
---

# Phase 13 Summary — Data Instrumentation

## What Was Built

**Backend: in-memory key accumulator + admin diagnostic endpoint**

`api/main.py` changes:
1. `_seen_breach_extra_keys: set[str] = set()` — module-level accumulator (lines ~754)
2. `_serialize_breaches()` modified to call `_seen_breach_extra_keys.update(b.extra_fields.keys())` before serialization — zero overhead when extra_fields is empty
3. `GET /api/admin/breach-extra-keys` — admin-only endpoint (Depends(get_admin_user) + RL_ADMIN_LIMIT) returning sorted key list + count + usage note

## Architecture Decision

In-memory set chosen over new SQLite table because:
- extra_fields never persisted to DB — only lives during scan
- Container lifetime is enough to sample real OathNet responses  
- Zero migration risk, zero new DB table, zero write-queue pressure
- Resets on restart: acceptable — admin runs a few queries, reads endpoint, builds whitelist

## Security

- Only key names stored — never values (no PII/password leakage possible)
- Admin-only gate (403 for non-admin users)
- CPython GIL makes `set.update()` safe without explicit lock (no data race)

## How to Use

1. Deploy to VPS (scp + docker restart nexus)
2. Run 1-2 real email queries via search
3. Call `GET /api/admin/breach-extra-keys` with admin auth
4. Use returned key list to build Phase 14 whitelist in render.js

## Phase 14 Input

Whitelist candidates to check (common OathNet field names):
```js
// Update after running real queries and checking /api/admin/breach-extra-keys
const BREACH_EXTRA_WHITELIST = [
    'full_name', 'name', 'first_name', 'last_name',
    'cpf', 'cpf_cnpj',
    'date_birth', 'birthdate', 'birth_date', 'dob',
    'gender', 'sex',
    'age',
    'address', 'city', 'state', 'zip', 'postal_code',
];
```

## Tests

62/62 passed. No regressions. No new `except Exception` introduced.
