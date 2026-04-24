---
hotfix: 2026-04-23-security-high
branch: hotfix/v4.1-security-2026-04-23
status: DEPLOYED
deployed_at: 2026-04-24T03:05:18Z
deployed_by: Claude (Opus session)
source: codex security review.md (2026-04-23 10:42)
supersedes: none
tags: [security, hotfix, cloudflare, docker, ufw, pyjwt, cve]
---

# Hotfix — 3 HIGH-severity Security Findings

Executado fora do escopo da Phase 15 (refactor-main-py-layers) porque as
vulnerabilidades eram exploráveis em produção no VPS 146.190.142.50. CLAUDE.md
regra 4 ("Claude implementa defesas proativamente") autoriza essa ação sem
gate de planejamento prévio.

## Findings Corrigidos

### HIGH #1 — Porta 8000 pública (Docker-UFW bypass)

**Commit:** `23af34b` — `docker-compose.yml`

**Problema:**
- `docker-compose.yml` publicava `ports: "8000:8000"` no host.
- UFW tinha `DENY IN 8000` configurado — mas **UFW é ineficaz contra Docker**
  porque a regra DNAT do Docker em `PREROUTING` redireciona o pacote para o
  container antes de tocar no `INPUT` chain onde o UFW opera.
- Evidência coletada via SSH:
  - `iptables -t nat -L DOCKER` mostrou `DNAT tcp dpt:8000 to:172.18.0.2:8000`
  - `DOCKER-USER` chain vazia (impressão digital clássica de bypass)
  - `ss -tlnp` mostrou `docker-proxy` em `0.0.0.0:8000`

**Fix:** substituído `ports: "8000:8000"` por `expose: "8000"`. Nginx já
alcançava o backend via DNS interno (`http://nexus:8000` na rede `internal`),
então não há mudança funcional — apenas fecha a porta de bypass.

**Validação pós-deploy:**
- `curl http://146.190.142.50:8000/health` externo → `ECONNREFUSED`
- `ss -tlnp | grep :8000` no VPS → vazio (docker-proxy não sobe)
- `curl http://localhost:8000/health` dentro do VPS → falha (esperado)

---

### HIGH #2 — Rate limit quebrado atrás de proxy

**Commit:** `6eaddff` — `docker-compose.yml` + `nginx.conf`

**Problema:**
- Uvicorn rodava sem `--proxy-headers`, então `request.client.host` recebia o
  IP do container nginx (`172.19.0.x`), não o IP real do cliente.
- Nginx não tinha `real_ip_header` configurado, então mesmo o `X-Real-IP` que
  ele setava era o IP da Cloudflare (não do cliente final).
- Consequência: `slowapi` agrupava TODOS os requests pré-auth no mesmo
  bucket (IP do container nginx). Qualquer atacante conseguia bloquear
  `/api/login` para todos os usuários simultaneamente.
- Usuários autenticados eram poupados porque `_rate_key` usa JWT sub.

**Fix em duas camadas:**

1. `nginx.conf` — adicionadas 22 linhas `set_real_ip_from` (IPv4+IPv6
   Cloudflare canônicos de cloudflare.com/ips-v4 e /ips-v6) + `real_ip_header
   CF-Connecting-IP` + `real_ip_recursive on`, colocadas ANTES das zonas
   `limit_req_zone` para que as próprias zonas nginx já usem o IP real.

2. `docker-compose.yml` — adicionadas flags `--proxy-headers
   --forwarded-allow-ips=172.16.0.0/12` ao comando uvicorn. `172.16.0.0/12`
   cobre o range 172.16-172.31 usado por bridges Docker por padrão.

**Validação pós-deploy:**
- Logs pré-reload (03:00:56): IP Cloudflare `104.23.197.237` no `$remote_addr`
- Logs pós-reload (03:04:08): IP real UptimeRobot `178.156.189.249` no
  `$remote_addr` (fora da faixa CF — confirma substituição)

---

### HIGH #3 — PyJWT CVE (GHSA-752w-5fwx-jx9f)

**Commit:** `d4f9936` — `requirements.txt`

**Problema:**
- `PyJWT==2.9.0` pinado.
- GHSA-752w-5fwx-jx9f (publicado 2026-03-12, severidade HIGH): PyJWT < 2.12.0
  aceita extensões `crit` desconhecidas no header JWT, violando RFC 7515
  §4.1.11. Receptores devem rejeitar JWTs com entradas `crit` que não
  entendem.
- Impacto no NexusOSINT: JWT é usado como cookie de sessão (`nx_session`).
  Qualquer advisory no parser da camada de auth é tratado como HIGH por
  política, independentemente de bypass direto nos nossos call sites.

**Fix:** `PyJWT==2.9.0` → `PyJWT==2.12.1`.

**Compatibilidade verificada:**
- Ambos os call sites (`api/main.py:240, 244, 372, 376`) usam assinaturas
  padrão `jwt.encode(payload, key, algorithm=)` e `jwt.decode(token, key,
  algorithms=[])`.
- Classes de exceção (`InvalidTokenError`, `ExpiredSignatureError`) inalteradas
  entre 2.9.0 e 2.12.1.
- Suite de testes: 61/61 verdes (baseline Phase 15 inalterado).

---

## Rollback

Se deploy apresentar regressão:

```bash
# 1. Restaurar imagem anterior
ssh root@146.190.142.50 "docker tag nexus-osint-nexus:pre-hotfix-20260423-backup nexus-osint-nexus:latest"

# 2. Restaurar docker-compose.yml + nginx.conf + requirements.txt do git
git revert d4f9936 6eaddff 23af34b
scp docker-compose.yml nginx.conf requirements.txt root@146.190.142.50:/root/nexus-osint/

# 3. Recriar com imagem antiga
ssh root@146.190.142.50 "cd /root/nexus-osint && docker compose up -d --force-recreate nexus && docker exec nexus-nginx nginx -s reload"
```

Imagens de backup preservadas no VPS:
- `nexus-osint:pre-hotfix-20260423-backup` (image id `0ec1bc7ebbbb`)
- `nexus-osint-nexus:pre-hotfix-20260423-backup`

## Sequência de Commits

```
d4f9936 fix(security): upgrade PyJWT 2.9.0 → 2.12.1 (GHSA-752w-5fwx-jx9f)
6eaddff fix(security): restore real client IP through Cloudflare+nginx+uvicorn (HIGH #2)
23af34b fix(security): remove public bind of port 8000 — close Docker-UFW bypass (HIGH #1)
```

Branch: `hotfix/v4.1-security-2026-04-23` (não merged em master ainda — aguardando
decisão do operador).

## Findings NÃO Corrigidos Neste Hotfix

O review original identificou outros findings MED/LOW que ficaram fora deste
hotfix por serem não-exploráveis imediatamente ou exigirem mudança maior:

| # | Finding | Severity | Deferral |
|---|---------|----------|----------|
| MED 3 | Logout fire-and-forget (`_db.write` em vez de `_db.write_await`) | MED | Phase 16 ou janela futura |
| MED 4 | `verify=False` no Sherlock wrapper | MED | Phase 16 |
| MED 5 | /health público com telemetria detalhada | MED | Phase 16 |
| MED 6b | Image tags flutuantes (sem digest pin) | LOW-MED | Phase 16 |
| LOW 7a | JWT error oracle em detail de 401 | LOW | Batch futuro |
| LOW 7b | Admin `str(exc)` em 500 | LOW | Batch futuro |
| LOW 7c | Log de `sql=%r params=%r` no DB worker | MED (reclassificado) | Phase 16 |

## Continuidade com Phase 15

Este hotfix **não bloqueia** Phase 15 Plan 02 (deps.py extraction). Branch
hotfix é independente de `v4.1/f15-refactor-main-py-layers` (que ainda não foi
criada). Quando hotfix for merged em master, Phase 15 deve rebase sobre master
atualizado antes de continuar.
