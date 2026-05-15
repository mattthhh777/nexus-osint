# Changelog

## 2026-05-15 - Username validation Phase A

- Refactored Sherlock username search into `modules/username_check/` with a
  compatibility shim at `modules/sherlock_wrapper.py`.
- Behavior unchanged: no new validation/scoring logic and no Maigret runtime use.
- FP-rate impact: not measurable in Phase A; structural-only refactor.
- Manual smoke:
  - Real username `torvalds`: 12 confirmed, 7 likely, 4 not found, 2 errors.
  - Nonexistent username `nexusosint_no_such_user_20260515`: 7 confirmed,
    7 likely, 8 not found, 3 errors.
  - Diff: current false-positive behavior preserved for Phase A; anti-FP work starts
    in later gated phases.
