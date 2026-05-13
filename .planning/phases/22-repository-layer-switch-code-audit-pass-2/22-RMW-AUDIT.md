# Phase 22 Read-Modify-Write Audit

## Scope

Runtime DB paths under `api/` after the asyncpg switch.

## Query

`rg -n "SELECT .*UPDATE|UPDATE .*SELECT|UPDATE |SELECT .*FOR UPDATE" api -g "*.py"`

## Result

No matches.

## Conclusion

No runtime read-modify-write update sequence was found in the current codebase.
Phase 22 therefore has no `SELECT then UPDATE` site to convert to
`UPDATE col = col + 1` or `SELECT FOR UPDATE`.

The only write patterns in runtime DB paths are:

- `INSERT INTO quota_log ...`
- retention trim: `DELETE FROM quota_log WHERE id NOT IN (SELECT id ... LIMIT 100)`
- `INSERT INTO searches ...`
- `INSERT INTO token_blacklist ... ON CONFLICT (jti) DO NOTHING`
- expired-token cleanup: `DELETE FROM token_blacklist WHERE exp < $1`

These do not perform a lost-update-prone read-modify-write cycle.
