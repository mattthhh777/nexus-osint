# Connectors Contract - NexusOSINT

**Status:** R0 contract shim. Backend connectors arrive in R1.
**Source of truth:** `modules/connectors/base.py`.
**Compatibility:** `/api/search` remains the current public search endpoint in R0.

This document defines the shared contract for engineers and LLM operators. R0
adds schema, opt-in UI components, and a safe legacy adapter only. It does not
create Source Health, a real Jobs Queue, persistent cases, production-like fake
metrics, or a Signal v2 backend.

## 1. Schema

Canonical Pydantic v2 definitions live in `modules/connectors/base.py`:

- `TargetType`: `username`, `email`, `phone`
- `ConnectorStatus`: `pending`, `running`, `found`, `not_found`, `likely`, `uncertain`, `blocked`, `error`
- `ConfidenceLevel`: `high`, `medium`, `low`, `none`
- `Evidence`: `signal`, `weight` from `-100` to `100`, `detail`
- `ConnectorRequest`: `target_type`, `target_value`, `target_hash`, `timeout_s`, `job_id`
- `ConnectorResult`: connector output contract consumed by the R0 UI adapter

`target_value` exists in the request contract for runtime execution only. It
must not be written to logs, persisted events, or client-visible job payloads.

## 2. Status Semantics

These eight states are immutable. Do not collapse them across backend, adapter,
tests, or UI.

| Status | Meaning | UI treatment in Graphite & Ember |
| --- | --- | --- |
| `pending` | Planned, not started | tertiary text |
| `running` | In flight lifecycle state | ember accent with loading affordance |
| `found` | Confirmed match. Overall `found` needs quorum in R1. | high-confidence green |
| `likely` | Positive signal without quorum | medium-confidence mustard, never green |
| `not_found` | Negative result confirmed | tertiary text |
| `uncertain` | Signals disagree or confidence is insufficient | medium treatment with restrained border |
| `blocked` | Source blocked access: captcha, auth wall, anti-bot, rate limit | blocked/earth tone, not red |
| `error` | Source failed: timeout, network, parser, unexpected module failure | error red |

Hard rules:

- `likely` must not become `found`.
- `blocked` must not become `not_found`.
- `blocked` must not become `error`.
- A single source must not set overall search status to `found`; R1 quorum is two or more independent connectors.

## 3. Confidence Derivation

`derive_confidence_level(score)` in `modules/connectors/base.py` is canonical:

```text
score >= 85 -> high
score >= 60 -> medium
score >= 30 -> low
score <  30 -> none
```

Scores are integer bounded from `0` to `100`.

## 4. Legacy to 8-State Mapping

R0-4 maps current `/api/search` SSE events into `ConnectorResult` shaped data
in the browser when `window.NX_V2` is enabled. This is an adapter only. With
`nx-v2` off, the legacy render path remains the public behavior.

| Legacy signal | Connector name | Status |
| --- | --- | --- |
| `sherlock.validation_status=confirmed` or `found` | `sherlock:<platform>` | `found` |
| `sherlock.validation_status=likely` | `sherlock:<platform>` | `likely` |
| `sherlock.validation_status=unconfirmed` or `uncertain` | `sherlock:<platform>` | `uncertain` |
| `sherlock.validation_status=likely_false_positive` or `not_found` | `sherlock:<platform>` | `not_found` |
| `sherlock.validation_status=auth_blocked` | `sherlock:<platform>` | `blocked` |
| `sherlock.fetch_status=cf_challenge`, `login_required`, or `redirect_to_login` | `sherlock:<platform>` | `blocked` |
| `sherlock.validation_status=error`, timeout, HTTP error, connection error, proxy unavailable, or invalid input | `sherlock:<platform>` | `error` unless fetch status is blocked |
| OathNet breach count greater than zero | `oathnet:breach` | `found` |
| OathNet breach count equals zero | `oathnet:breach` | `not_found` |
| OathNet stealer count greater than zero | `oathnet:stealer` | `found` |
| OathNet stealer count equals zero | `oathnet:stealer` | `not_found` |
| OathNet Holehe count greater than zero | `oathnet:holehe` | `found` |
| OathNet IP metadata returned | `oathnet:ip` | `found` |
| OathNet IP metadata missing | `oathnet:ip` | `not_found` |
| SpiderFoot available with events | `spiderfoot:scan` | `likely` |
| SpiderFoot available with no events | `spiderfoot:scan` | `not_found` |
| SpiderFoot unavailable | `spiderfoot:scan` | `error` |
| Legacy `module_error` | `<module>:error` | `error` |

## 5. R0 Scope

R0 is a contract shim:

- `modules/connectors/base.py` defines the contract.
- Graphite & Ember tokens stay behind `?theme=graphite` or `ui_theme=graphite`.
- Connector UI components are opt-in/dev-safe.
- Legacy search events can be adapted in memory with `nx-v2` on.
- `/api/search` is not deprecated.
- No public search behavior changes with `nx-v2` off.

R0 does not create real backend connector jobs, source health metrics, durable
case entities, or production-like mocked metrics.

## 6. R1 Scope

R1 is the safe MVP after R0 approval:

- `sherlock_adapter`
- `oathnet_adapter`
- `carrier_lookup`
- `/api/v2/search`
- hash-only event payloads
- seven-day TTL for jobs/events
- overall `found` only when at least two independent connectors agree

R1-10 Gravatar is skipped. Thordata is reused under its 1GB/day quota.

Any R1 source-specific anti-bot or rate-limit signal must normalize to
`blocked` before it reaches UI code. It must not render as `not_found` or
`error`.

## 7. Privacy and Retention

Decision G1 is hash-only plus TTL seven days:

- `search_events.payload` stores `target_hash` and sanitized metadata only.
- No clear `target_value` in DB event payloads, logs, or client-visible job payloads.
- `search_jobs.expires_at` is `created_at + 7 days`.
- Cleanup purges expired jobs; event rows cascade.
- Delete requests can be satisfied by TTL expiry or an explicit job delete endpoint if added in R1.

## 8. Operator Checklist

Before changing adapter, connector, or UI status behavior:

- Re-run connector unit tests.
- Smoke `nx-v2` off and confirm legacy rendering still works.
- Smoke `nx-v2` on and confirm connector cards preserve all eight states.
- Confirm `likely` is visually distinct from `found`.
- Confirm `cf_challenge`, anti-bot, and rate-limit conditions render as `blocked`, not `error`.
