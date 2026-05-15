# Changelog

## 2026-05-15 - Username validation Phase D

- Added negative baseline fetch/cache with 1h LRU by `(platform, hour_bucket)`.
- Added `USERNAME_CHECK_BASELINE_ENABLED`, default `false`.
- Added `BaselineCompareValidator` with body normalization, baseline similarity,
  hard-negative indistinguishable responses, and warning-only baseline failures.
- Runner appends baseline outcome only when the flag is enabled; SSE output remains unchanged.
- FP-rate impact: not enforced in default config; baseline signals are gated off by default.
- Manual smoke with default flag off:
  - Real username `torvalds`: 12 confirmed, 7 likely, 4 not found, 2 errors.
  - Nonexistent username `nexusosint_no_such_user_20260515`: 7 confirmed,
    7 likely, 8 not found, 3 errors.
  - Diff: default runtime behavior preserved.

## 2026-05-15 - Username validation Phase C

- Added validator interface and generic validators:
  - `GenericContentValidator` for title, canonical, `og:url`, JSON-LD, and body-size signals.
  - `UrlFinalValidator` for final URL and redirect classifications.
  - `NegativeMarkersValidator` for platform markers and common multi-language negative markers.
- Runner now attaches internal `_outcomes` to `PlatformResult`; API/SSE output remains unchanged.
- Added 21 validator tests: 6+ per validator, registry error isolation, runner outcome attachment.
- FP-rate impact: not enforced yet; Phase C collects validation signals only.
- Manual smoke:
  - Real username `torvalds`: 13 confirmed, 7 likely, 3 not found, 2 errors.
  - Nonexistent username `nexusosint_no_such_user_20260515`: 7 confirmed,
    7 likely, 8 not found, 3 errors.
  - Diff: no intentional scoring change; real-user count varied by one due live external responses.

## 2026-05-15 - Username validation Phase B

- Added `FetchResult` to capped username fetches, including `final_url` and
  `redirect_chain`.
- Preserved Phase A tuple-unpack compatibility for existing runner behavior.
- Added redirect test for `301 -> 200`.
- FP-rate impact: not measurable in Phase B; response metadata capture only.
- Manual smoke:
  - Real username `torvalds`: 12 confirmed, 7 likely, 4 not found, 2 errors.
  - Nonexistent username `nexusosint_no_such_user_20260515`: 7 confirmed,
    7 likely, 8 not found, 3 errors.
  - Diff: current false-positive behavior preserved; validators consume
    redirect metadata starting in later gated phases.

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
