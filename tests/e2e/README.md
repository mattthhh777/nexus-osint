# NexusOSINT E2E Security Tests

These tests run against `https://nexusosint.uk` by default and require a test
account. Do not hardcode credentials in the repo.

PowerShell:

```powershell
$env:NEXUS_TEST_USER = "codex"
$env:NEXUS_TEST_PASS = "<test password>"
npm install
npm run test:e2e
```

Optional:

```powershell
$env:NEXUS_BASE_URL = "https://nexusosint.uk"
npm run test:e2e:auth
npm run test:e2e:security
```

Scope:

- UI login, dashboard visibility, logout.
- Private route auth checks.
- User-vs-admin authorization checks with the non-admin test user.
- Security headers and CORS smoke checks.
- Benign validation failures only. No brute force, DoS, destructive payloads, or
  third-party target testing.

The security smoke suite sends at most five `/api/auth` probes for rate-limit
behavior. If the site is already rate-limited from prior manual testing, wait
for `Retry-After` before rerunning.
