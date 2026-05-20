# Connectors Contract - NexusOSINT

**Status:** R1 safe MVP implemented through R1-12 documentation closeout.
**Source of truth:** `modules/connectors/base.py`.
**Runtime paths:** legacy `/api/search` remains active and not deprecated; v2
search is opt-in through `/api/v2/search` and frontend `?engine=v2`.

This document defines the shared connector contract for engineers and LLM
operators. R1 adds the job store, safe connector adapters, v2 search API, opt-in
frontend replay, and hourly TTL cleanup. It does not create Source Health,
admin Jobs Queue, real connector metrics UI, DB-backed cases, or production-like
fake metrics.

## 1. Schema

Canonical Pydantic v2 definitions live in `modules/connectors/base.py`:

- `TargetType`: `username`, `email`, `phone`
- `ConnectorStatus`: `pending`, `running`, `found`, `not_found`, `likely`, `uncertain`, `blocked`, `error`
- `ConfidenceLevel`: `high`, `medium`, `low`, `none`
- `Evidence`: `signal`, `weight` from `-100` to `100`, `detail`
- `ConnectorRequest`: `target_type`, `target_value`, `target_hash`, `timeout_s`, `job_id`
- `ConnectorResult`: connector output contract consumed by v2 backend and UI

`target_value` exists in the request contract for runtime execution only. It
must not be written to logs, persisted events, cache payloads, or client-visible
job payloads.

## 2. Status Semantics

These eight states are immutable. Do not collapse them across backend, adapter,
tests, or UI.

| Status | Meaning | UI treatment |
| --- | --- | --- |
| `pending` | Planned, not started | tertiary text |
| `running` | In flight lifecycle state | amber/accent loading affordance |
| `found` | Confirmed match. Overall `found` needs quorum. | high-confidence green |
| `likely` | Positive signal without quorum | medium-confidence, never green |
| `not_found` | Negative result confirmed | tertiary text |
| `uncertain` | Signals disagree or confidence is insufficient | restrained border |
| `blocked` | Source blocked access: captcha, auth wall, anti-bot, rate limit | blocked tone, not red |
| `error` | Source failed: timeout, network, parser, unexpected module failure | error red |

Hard rules:

- `likely` must not become `found`.
- `blocked` must not become `not_found`.
- `blocked` must not become `error`.
- A single source must not set overall search status to `found`; quorum is two or more independent connectors.

## 3. Confidence Derivation

`derive_confidence_level(score)` in `modules/connectors/base.py` is canonical:

```text
score >= 85 -> high
score >= 60 -> medium
score >= 30 -> low
score <  30 -> none
```

Scores are integer bounded from `0` to `100`.

## 4. R1 Connectors

Implemented connectors:

- `sherlock:<platform>` wraps the existing username runner for approved
  platforms and maps legacy scoring into the 8-state contract.
- `oathnet:breach` wraps OathNet breach search and stores only counts/safe
  metadata in connector data and events.
- `oathnet:stealer` wraps OathNet stealer search and stores only counts/safe
  metadata in connector data and events.
- `oathnet:victims` wraps OathNet victims search for approved target types and
  stores only counts/safe metadata.
- `carrier_lookup` is offline phone metadata. It never returns `found`; maximum
  positive status is `likely`.

Deferred connectors/features:

- Gravatar is deferred by G2. R1-10 was intentionally skipped. No
  `modules/connectors/email/gravatar.py`, no Gravatar HTTP call, and no MD5/email
  hash sent to an external avatar service.
- `oathnet:ip` / `ip_info` is deferred until `TargetType.IP` exists. R1 must not
  introduce `TargetType.IP`.
- Sensitive probes remain out of scope: HIBP, Truecaller, forgot-password
  probes, WhatsApp QR, Telegram resolve, Apple ID probe, and similar account
  existence checks.

## 5. R1 Runtime

Legacy search:

- `/api/search` remains active and is not deprecated.
- Existing public behavior stays intact unless the user explicitly opts into v2.

V2 search:

- `POST /api/v2/search` creates a hash-only job and returns `job_id` plus
  `sse_url`.
- `GET /api/v2/search/{job_id}` returns a job snapshot.
- `GET /api/v2/search/{job_id}/events?from_seq=N` streams replayable SSE events.
- Frontend v2 is opt-in via `?engine=v2`; flag off keeps `/api/search`.
- SSE replay uses `from_seq` for reconnect/resume.

Job lifecycle:

- `search_jobs.expires_at` defaults to seven days after creation.
- `api.tasks` runs hourly cleanup for expired jobs; events cascade by FK.
- Logs from cleanup contain only aggregate counts or generic status.

## 6. G1-G4 Decisions

| Gate | Decision | R1 result |
| --- | --- | --- |
| G1 | hash-only + TTL 7d | `search_events.payload` stores `target_hash` plus sanitized metadata only; TTL cleanup added in R1-11 |
| G2 | defer Gravatar | R1-10 skipped; no Gravatar connector or external MD5/email lookup |
| G3 | >=2 independent connectors for `found` | `search_orchestrator` demotes single-source `found` to `likely` |
| G4 | reuse Thordata quota | no new proxy provisioning; `carrier_lookup` is offline |

## 7. Privacy and Retention

- No clear `target_value` in DB event payloads, cache payloads, logs, or
  client-visible job payloads.
- `search_jobs.target_encrypted` remains `NULL` in the G1 model.
- `search_jobs.owner_key_hash` is a privacy-preserving owner identifier aligned
  with current JSON auth. It is intentionally not a FK until DB-backed users
  exist.
- Delete requests can be satisfied by TTL expiry or a future explicit job delete
  endpoint if approved.
- Frontend v2 does not write raw target values to history/localStorage.

## 8. Not Implemented In R1

- Source Health real-data UI and `connector_metrics` table.
- Admin Jobs Queue / complete job management UI.
- DB-backed persistent cases or chain graph.
- Cooperative cancel/retry for running jobs.
- Public v2 rollout or legacy `/api/search` deprecation.
- Merge, deploy, or production flag enablement.

## 9. Operator Checklist

Before changing adapter, connector, or UI status behavior:

- Re-run connector unit tests.
- Smoke v2 off and confirm legacy `/api/search` still works.
- Smoke `?engine=v2` and confirm connector cards preserve all eight states.
- Confirm `likely` is visually distinct from `found`.
- Confirm anti-bot, auth wall, and rate-limit conditions render as `blocked`,
  not `error` or `not_found`.
