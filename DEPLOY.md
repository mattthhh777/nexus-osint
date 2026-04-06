# NexusOSINT Deployment & Rollback Runbook

**Scope:** Python 3.11 -> 3.12 upgrade (Phase 07, F6 Stack Modernization)
**Owner:** Math
**Last updated:** 2026-04-06

---

## Pre-Upgrade Snapshot (MANDATORY — run before Plan 03)

Run these commands on the VPS (and locally for dev parity) BEFORE any Dockerfile change:

```bash
# 1. Freeze current dependency versions
pip freeze > requirements.lock.pre-python312.txt

# 2. Tag the current production image
docker tag nexus:latest nexus:pre-py312-backup

# 3. Copy SQLite data volume (belt + suspenders)
docker run --rm -v nexus_data:/data -v $(pwd):/backup alpine \
    tar czf /backup/nexus_data.pre-py312.tar.gz -C /data .

# 4. Record current container memory baseline
docker stats --no-stream nexus > stats.pre-py312.txt
```

Commit requirements.lock.pre-python312.txt to the branch (NOT to main).

---

## Upgrade Procedure (executed in Plan 03)

1. Verify all 4 endpoint tests green: `python -m pytest tests/test_endpoints.py -q`
2. Edit `Dockerfile`: both stages `FROM python:3.11-slim` -> `FROM python:3.12-slim`
3. Rebuild: `docker compose build --no-cache nexus`
4. Verify image size < 250MB: `docker images nexus:latest --format "{{.Size}}"`
5. Run tests inside new image: `docker compose run --rm nexus python -m pytest tests/ -q`
6. Deploy: `docker compose up -d nexus`
7. Smoke test: `curl -f https://nexusosint.uk/health`
8. Watch memory 10 min: `docker stats nexus` — RSS must remain < 400MB

---

## Rollback Procedure (if upgrade fails at ANY step)

Execute immediately on failure detection:

```bash
# 1. Stop broken container
docker compose stop nexus

# 2. Restore the pre-upgrade image tag
docker tag nexus:pre-py312-backup nexus:latest

# 3. Restart with the backup image
docker compose up -d nexus

# 4. Verify service healthy
curl -f https://nexusosint.uk/health

# 5. (Optional) Restore data volume if corruption suspected
docker compose down
docker volume rm nexus_data
docker volume create nexus_data
docker run --rm -v nexus_data:/data -v $(pwd):/backup alpine \
    tar xzf /backup/nexus_data.pre-py312.tar.gz -C /data
docker compose up -d

# 6. Reinstall pinned dependencies (dev machine)
pip install -r requirements.lock.pre-python312.txt
```

---

## Rollback Triggers

Abort the upgrade and execute rollback if ANY of these occur:

- Test suite fails under 3.12 (`pytest` non-zero exit)
- Docker image > 250MB after rebuild
- /health returns non-200 for > 30s after deploy
- RSS > 400MB in resting state (10 min window)
- Any deprecation warning from Python 3.12 in application logs
- User-reported auth failures (JWT library incompatibility)

---

## Post-Upgrade Cleanup (only after 48h stable)

```bash
# Remove backup tag once upgrade is confirmed stable
docker rmi nexus:pre-py312-backup
# Keep requirements.lock.pre-python312.txt in git history — do not delete
```

---

## Known Risks

- `PyJWT==2.9.0` already installed; no jose migration during this phase.
- `httpx==0.27.2` already sole HTTP client (Phase 11).
- `tenacity` removal (Plan 02) is independent but ships in same branch — rollback restores it.
- FIND-16 fix (Plan 02) is isolated to oathnet_client.py 429 handling.

---

## Pre-Requisites (General)

- VPS: 1vCPU / 1GB RAM / 25GB SSD (Ubuntu 24.04)
- Docker + Docker Compose installed
- 2GB swap active:
  ```bash
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  ```
- Domain pointing to VPS IP

## Environment Variables (.env)

```
OATHNET_API_KEY=<OathNet API key>
JWT_SECRET=<long random string>
APP_PASSWORD=<app password>
ALLOWED_ORIGINS=https://nexusosint.uk
```

## Initial Deploy

```bash
cd /root/nexus-osint
docker compose up -d --build
docker compose logs -f nexus
```

## Post-Deploy Verification

- Health check: `curl -s https://nexusosint.uk/health | python3 -m json.tool`
- RSS must be < 200MB at rest
- `rss_mb`, `cache_entries`, and `version` must appear in JSON response
- After 10 searches, RSS must remain < 250MB

## Routine Update (zero-downtime)

```bash
docker compose pull
docker compose up -d --build nexus
docker compose logs -f nexus
```
