# NexusOSINT Security Review

Date: 2026-05-17

## Executive Summary

Non-destructive security review performed against the local NexusOSINT codebase
and the authorized production domain `https://nexusosint.uk`.

No critical issue was confirmed. Three findings remain:

- High: production static assets under `/css/*` and `/js/*` return `403` with
  `Content-Type: text/html`, so browsers refuse to load CSS/JS and the dashboard
  cannot initialize.
- Medium: `/admin` page gate decodes JWT role directly and does not enforce the
  same blacklist/session-state checks used by API auth.
- Low: `/api/spiderfoot/status` exposes an internal service URL and raw network
  error details to any authenticated user.

Positive controls confirmed: protected API routes reject anonymous requests,
normal test user cannot access admin APIs, login cookie is `HttpOnly`, `Secure`,
and `SameSite=strict`, logout revokes the JWT, core security headers are present,
basic rate limiting is active, and benign invalid inputs fail closed without 500.

## Scope Tested

- Domain: `https://nexusosint.uk`
- Local repository: `C:\Users\vtbit\Documents\nexus_osint`
- Test user: non-admin account from the authorized prompt. Password was not
  written to committed files.
- Out of scope: third-party APIs, subdomains outside `nexusosint.uk`, brute force,
  DoS, destructive payloads, mass enumeration, database dumps, and real account
  access.

## Architecture Reviewed

- FastAPI app and middleware: `api/main.py`
- Auth dependencies and token blacklist: `api/deps.py`
- Login/logout routes: `api/routes/auth.py`
- Admin gate and root pages: `api/routes/root.py`
- Admin APIs: `api/routes/admin.py`
- Search APIs: `api/routes/search.py`
- Victims APIs: `api/routes/victims.py`
- SpiderFoot status API: `api/routes/spiderfoot.py`
- Input schemas: `api/schemas.py`
- Nginx security headers and rate limits: `nginx.conf`
- Docker and deployment config: `Dockerfile`, `docker-compose.yml`
- Frontend auth storage: `static/js/auth.js`, `static/js/admin.js`

## Environment and Commands Used

Commands were run with low volume and only against the authorized domain.
Credential value is intentionally redacted.

```powershell
curl.exe -4 -I https://nexusosint.uk/
curl.exe -4 -i https://nexusosint.uk/api/me
curl.exe -4 -i -H "Content-Type: application/json" https://nexusosint.uk/api/login --data '{"username":"codex","password":"<redacted>"}'
curl.exe -4 -b .tmp_nexus_cookies.txt https://nexusosint.uk/api/me
curl.exe -4 -b .tmp_nexus_cookies.txt https://nexusosint.uk/api/admin/stats
curl.exe -4 -b .tmp_nexus_cookies.txt -X POST https://nexusosint.uk/api/logout
curl.exe -4 -X OPTIONS https://nexusosint.uk/api/me -H "Origin: https://evil.example" -H "Access-Control-Request-Method: GET"
curl.exe -4 -I "https://nexusosint.uk/js/state.js?v=202604170002"
curl.exe -4 -I "https://nexusosint.uk/css/components.css?v=202604180200"
```

Playwright tests added:

```powershell
npm install
$env:NEXUS_TEST_USER = "codex"
$env:NEXUS_TEST_PASS = "<test password>"
npm run test:e2e
```

Observed Playwright result after adding tests: 7 passed, 1 failed. The failing
test is the dashboard/auth UI test and is treated as evidence for the static
asset production bug below.

## Findings

### Critical

None confirmed.

### High

#### Production static CSS/JS return 403 HTML, breaking dashboard initialization

Severity: High

Evidence:

HTTP probes:

```text
GET /js/state.js?v=202604170002 -> 403 Forbidden
Content-Type: text/html

GET /css/components.css?v=202604180200 -> 403 Forbidden
Content-Type: text/html
```

Playwright browser console:

```text
Refused to execute script from 'https://nexusosint.uk/js/state.js?v=202604170002'
because its MIME type ('text/html') is not executable.

Refused to apply style from 'https://nexusosint.uk/css/components.css?v=202604180200'
because its MIME type ('text/html') is not a supported stylesheet MIME type.
```

The E2E auth test logged in through the backend API and confirmed `/api/me`
returned 200, but the dashboard stayed hidden because frontend scripts never
loaded.

Related code/config:

- `static/index.html` references `/css/*.css` and `/js/*.js`.
- `nginx.conf:122-147` serves `/css/` and `/js/` from
  `/etc/nginx/static/...`.
- `docker-compose.yml:145-147` mounts `./static:/etc/nginx/static:ro`.

Impact:

Authenticated users can receive a valid session but the production dashboard
does not initialize in a real browser. This blocks normal use of the app and can
hide auth/session bugs because frontend code is not executing.

Safe reproduction:

1. GET `https://nexusosint.uk/` and inspect browser console.
2. HEAD `https://nexusosint.uk/js/state.js?v=202604170002`.
3. HEAD `https://nexusosint.uk/css/components.css?v=202604180200`.
4. Observe 403 HTML for assets and MIME blocking in browser.

Recommended fix:

Do not change CSP to work around this. Fix static serving/deploy:

- On VPS, verify `./static` exists relative to the active `docker-compose.yml`
  directory and is mounted into `nexus-nginx`.
- Verify files exist inside nginx container:
  `docker exec nexus-nginx ls -la /etc/nginx/static/js /etc/nginx/static/css`.
- Keep `alias /etc/nginx/static/js/` and `alias /etc/nginx/static/css/` only if
  the volume mount is correct; otherwise serve static through FastAPI or mount
  the actual deployed static path.
- Ensure JS responses use `Content-Type: application/javascript` and CSS uses
  `Content-Type: text/css`.

### Medium

#### `/admin` page gate bypasses centralized session checks

Severity: Medium

Evidence:

- Code in `api/routes/root.py` reads `nx_session`, calls `_decode_token()`, then
  trusts `payload.get("role") == "admin"` before serving `admin.html`.
- The route does not call `get_current_user()` or `_check_blacklist()`.
- Logout test confirmed `/api/logout -> 200`, then `/api/me -> 401 Token revoked`.
  A revoked admin token could still satisfy the current `/admin` HTML gate if its
  JWT role is `admin`.
- Related code: `api/routes/root.py:24-37`, `api/deps.py:178-205`.

Impact:

API calls remain protected by `get_admin_user()`, so this does not directly grant
admin API access. It still creates inconsistent logout behavior and lets a
revoked/stale admin token load the admin shell HTML.

Safe reproduction:

1. Log in with an admin test account.
2. Save only a redacted copy of the session cookie in a local temp file.
3. POST `/api/logout`.
4. Request `/api/me` with the same cookie and confirm `401`.
5. Request `/admin` with the same cookie. Current code path would serve the page
   if the decoded role is `admin`.

Recommended fix:

Use the same backend auth dependency as the APIs. Replace direct `_decode_token`
logic with `get_current_user()` plus role check, or a reusable dependency that
enforces blacklist, user active state, password rotation timestamp, and admin
role before serving `admin.html`.

### Low

#### `/api/spiderfoot/status` exposes internal service details

Severity: Low

Evidence:

Authenticated non-admin user received:

```json
{
  "available": false,
  "error": "[Errno -3] Temporary failure in name resolution",
  "url": "http://spiderfoot:5001"
}
```

Related code: `api/routes/spiderfoot.py:12-20`.

Impact:

Exposes internal container hostname, port, and raw network failure class. This is
useful reconnaissance for an attacker with any valid account.

Safe reproduction:

1. Log in as non-admin test user.
2. GET `/api/spiderfoot/status`.
3. Observe `url` and `error` fields.

Recommended fix:

For non-admin users return only stable public state, for example:

```json
{ "available": false }
```

Log raw exception details server-side. If operational diagnostics are needed,
gate them behind `get_admin_user()`.

### Info

#### Secrets posture

Evidence:

- `.env` exists locally but is not tracked by git.
- `.env.example` is tracked.
- Static scan found env variable names and placeholders, not live secret values.

Impact:

No direct leak confirmed. Local `.env` remains sensitive and should never be
printed, copied to reports, or committed.

Recommended fix:

Keep `.env` ignored. Add pre-commit secret scanning if not already enforced.

#### Security controls confirmed

Evidence:

- `/api/me`, `/api/admin/*`, `/health/memory`, `/api/search`,
  `/api/victims/search`, and `/api/spiderfoot/status` returned `401` when
  unauthenticated.
- Normal test user received `403` for admin APIs and `/health/memory`.
- Login response set `nx_session` with `HttpOnly`, `Secure`, `SameSite=strict`,
  and `Max-Age=86400`.
- Logout returned `200`, then `/api/me` returned `401 Token revoked`.
- Root response included CSP, HSTS, `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, and `Permissions-Policy`.
- `/api/auth` low-volume rate test returned `429` with `retry_after` during
  manual probing after the allowed threshold.
- `/api/search` with a one-character query returned `422`, and
  `/api/search/more-breaches` with empty fields returned `400`.

## Checklist

- [x] Read Docker, Nginx, backend, frontend, auth middleware, and sensitive routes.
- [x] Verified login with test account.
- [x] Verified authenticated `/api/me`.
- [x] Verified logout revokes session for API access.
- [x] Verified anonymous private API blocks.
- [x] Verified normal user cannot access admin APIs.
- [x] Checked cookie flags.
- [x] Checked localStorage/sessionStorage auth posture in code.
- [x] Checked security headers.
- [x] Checked CORS posture.
- [x] Checked docs/openapi exposure.
- [x] Checked production static asset delivery.
- [x] Checked benign validation failures.
- [x] Checked low-volume rate limiting.
- [x] Checked repo for obvious tracked secrets.
- [x] Added Playwright E2E security tests.

## Next Steps

1. Fix `/admin` to use centralized auth/session checks.
2. Redact `/api/spiderfoot/status` for non-admin users.
3. Fix production static asset delivery, then rerun `npm run test:e2e`.
4. Add the E2E suite to CI after confirming Playwright browser install on the
   runner.
5. Add secret scanning to pre-commit/CI if not already present.
