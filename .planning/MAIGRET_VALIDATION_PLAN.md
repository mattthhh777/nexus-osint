# Plano: Reintroduzir Maigret + Camada de Validação Anti-Falso-Positivo

## Context

### Por que isto agora
Math quer reduzir drasticamente os falsos positivos na busca por username da plataforma NexusOSINT. Pediu plano técnico considerando "Maigret". Verificação repo-wide confirmou:

- **Repo NÃO usa Maigret no runtime.** Foi removido deliberadamente em `4532adb` (2026-05-11), três commits após `8009028` (2026-05-06) que o introduziu.
- **Stack atual de username search:** `modules/sherlock_wrapper.py` (Sherlock-style custom interno, 25 plataformas, Phase 16 já entregou confidence scoring 0-100 + 3-state + Thordata proxy + audit log).
- **Outros OSINT integrados:** Holehe (email), OathNet (phone/breach), SpiderFoot (subprocess).
- **Artefato órfão:** `maigret_repo/` no disco, em `.gitignore` + `.dockerignore`, zero impacto runtime — manter como referência (lista de URLs por site é útil para validators).

### Por que Maigret foi removido (lições para não repetir)
Análise do wrapper deletado (`modules/maigret_wrapper.py` em `4532adb`):

1. **Maigret usa `aiohttp` interno, não `httpx`.** Comentário literal do wrapper: *"aiohttp internals not hookable via Thordata byte counter. Bytes estimated."* → Byte budget Thordata era **estimado** (50KB para CLAIMED, 5KB para outros), não medido. Risco de estouro silencioso.
2. **Sem body cap real.** Maigret lê resposta inteira em memória; viola CLAUDE.md 256KB cap.
3. **Sem hook no rate limiter outbound** do projeto (`OutboundRateLimiter` per-domain). Maigret usa concorrência interna `max_connections=10`, ignora nossa fila.
4. **Cairo build deps** (`687c448`) inflaram Docker para satisfazer `pycairo` (dep transitiva do Maigret para PDF reports). Viola target <250MB.
5. **Scoring binário do Maigret** (`CLAIMED`/`AVAILABLE`/`UNKNOWN`) — mesma classe de FP que motivou Phase 16. `CLAIMED` para SPA = FP.
6. **"Inline event risk"** no título do commit sugere preocupação com falhas do Maigret travarem o event loop FastAPI.

### Decisão arquitetural

**Reintroduzir Maigret SOMENTE como fonte de dados (site database), não como fetcher.**

- Importar `maigret.sites.MaigretDatabase` para carregar lista de 500 sites + URL templates + tags + regex de detecção.
- **Fetch e validação 100% no nosso código** usando `httpx.AsyncClient` existente + `_fetch_with_cap` 256KB + `OutboundRateLimiter` + proxy Thordata sticky.
- Pipeline unificado de validators aplicado a TODOS os hits (Sherlock-curated 25 + Maigret-derived 500).
- Maigret entrega **candidatos** e **regex/markers** por site. Nosso código decide se é match.

Esta abordagem resolve todos os 6 motivos da remoção anterior:
- (1) bytes medidos via nosso fetcher
- (2) body cap real
- (3) rate limiter respeitado
- (4) cairo desnecessário (não usamos `maigret.report`)
- (5) scoring multi-sinal nosso, não binário do Maigret
- (6) sem subprocess Maigret no event loop; só import da DB estática

---

## Estado atual

### Pontos de integração relevantes
| Caminho | Linha | Função |
|---|---|---|
| `modules/sherlock_wrapper.py` | 691 | `search_username()` — entrypoint async |
| `modules/sherlock_wrapper.py` | 93-347 | `PLATFORMS` — 25 sites curados |
| `modules/sherlock_wrapper.py` | 449-500 | `_compute_confidence` — scoring atual (status+text+size) |
| `modules/sherlock_wrapper.py` | 505-526 | `_fetch_with_cap` — streaming 256KB |
| `modules/sherlock_wrapper.py` | 60-85 | `OutboundRateLimiter` — 1 req/s por domínio |
| `api/services/search_service.py` | 311 | Import lazy do wrapper |
| `api/services/search_service.py` | 482-545 | Orquestração no SSE |
| `api/schemas.py` | 84 | `SherlockUsernameRequest` validator |
| `api/config.py` | 105-106 | `SHERLOCK_CONFIRMED_THRESHOLD=70`, `LIKELY=40` |
| `api/budget.py` | — | Estado proxy + bytes |
| `api/orchestrator.py` | 21 | Registry tasks, module name `"sherlock"` |
| `api/main.py` | 113-135 | Healthcheck Thordata |
| `static/js/render.js` | — | Render frontend (CSP-safe pós Phase 16) |
| `maigret_repo/maigret/sites.py` | — | `MaigretDatabase` (referência local) |
| `maigret_repo/maigret/resources/data.json` | — | Site DB (500+ entries com regex) |

### Reutilizáveis (não duplicar)
- `_fetch_with_cap` em `modules/sherlock_wrapper.py:505` → mover para `modules/username_check/fetcher.py`.
- `OutboundRateLimiter` em `modules/sherlock_wrapper.py:63` → `modules/username_check/rate_limit.py` (singleton).
- `_build_sticky_url` / `_build_rotate_url` em `modules/sherlock_wrapper.py:425-444` → `modules/username_check/proxy.py`.
- `_budget.record_usage` em `api/budget.py` → manter; ambas fontes contabilizam aqui.
- `PlatformResult` / `SherlockResult` dataclasses → shim retrocompat; novo schema é Pydantic.
- Negative markers já curados em `PLATFORMS` → migrar para validators site-specific.

### Gaps que causam FPs atuais
1. SPAs (X, Instagram, Reddit, LinkedIn) com `reliability=low` ainda passam para `likely`.
2. Sem captura de `final_url` / `redirect_chain` no fetcher.
3. Sem parser de `<title>`, `<link rel="canonical">`, `og:url`, JSON-LD.
4. Sem **baseline negativa** (fake-username comparison).
5. Negative markers só substring, sem regex multi-idioma.
6. Sem validators específicos extensíveis (lógica hardcoded em `_compute_confidence`).
7. Schema de resposta sem `evidence`, `warnings`, `checked_at`, `redirect_chain`, `url_final`.
8. Sem cache de resultado por username.
9. 25 sites é pouco — Maigret tem 500+.

---

## Arquitetura proposta

```
modules/username_check/                  ← novo subpackage unificado
├── __init__.py                          ← API pública: search_username(uname, opts)
├── runner.py                            ← orquestração; merge Sherlock+Maigret
├── fetcher.py                           ← _fetch_with_cap + redirect_chain
├── rate_limit.py                        ← OutboundRateLimiter singleton
├── proxy.py                             ← sticky / rotate URL builders
├── budget.py                            ← thin re-export de api.budget
├── audit.py                             ← log_decision estruturado
├── cache.py                             ← Redis result cache 5min
├── baseline.py                          ← fake-username fetcher + 1h LRU
├── scoring.py                           ← combine_outcomes → ScoredResult
├── normalize.py                         ← dataclass → Pydantic response
├── sources/
│   ├── __init__.py
│   ├── sherlock_curated.py              ← PLATFORMS (25 atuais)
│   └── maigret_db.py                    ← import maigret.sites.MaigretDatabase
│                                          carrega data.json, gera Platform[]
└── validators/
    ├── __init__.py
    ├── base.py                          ← Validator / Signal / Outcome / Context
    ├── registry.py                      ← maps platform → list[Validator]
    ├── generic_content.py               ← title / canonical / og: / JSON-LD
    ├── url_final.py                     ← redirect / homepage / login / search
    ├── negative_markers.py              ← regex multi-idioma + substring
    ├── baseline_compare.py              ← similarity vs baseline
    └── sites/
        ├── github.py
        ├── instagram.py
        ├── x.py
        ├── linkedin.py
        ├── reddit.py
        └── ...
modules/sherlock_wrapper.py              ← SHIM retrocompat: re-exporta de username_check
                                          mantido até Fase I
```

### Pipeline unificado

```
search_username(uname)
  ├── result_cache.get(uname) → if hit, return
  ├── candidates = sherlock_curated.PLATFORMS + maigret_db.top_500()
  │                (deduplicar por domínio canônico)
  ├── baseline_cache.prefetch(candidates)              # 1h LRU, paralelo
  ├── para cada candidate em paralelo (semaphore 10):
  │    ├── outbound_limiter.acquire(domain)            # 1 req/s/domínio
  │    ├── fetch_result = fetcher.fetch(url)           # 256KB cap, redirect chain
  │    ├── ctx = ValidationContext(fetch_result, baseline, candidate)
  │    ├── validators = registry.for_platform(name)
  │    │      [GenericContent, UrlFinal, NegativeMarkers, BaselineCompare,
  │    │       *site_specific]
  │    ├── outcomes = [v.validate(ctx) for v in validators]
  │    ├── (score, level, evidence) = scoring.combine(outcomes, candidate)
  │    └── normalize → SherlockPlatformResponse
  ├── result_cache.set(uname, results, ttl=300)
  ├── budget.record_usage(total_bytes)
  └── audit.log_decision_batch(results)
```

### Scoring 5 níveis (substitui 3 atuais)

| Level | Score | Critério |
|---|---|---|
| `confirmed` | ≥85 | ≥1 hard_positive OU 3+ sinais positivos + baseline diferente |
| `likely` | 60-84 | 2 sinais positivos + baseline diferente, sem hard_negative |
| `uncertain` | 30-59 | 1 sinal positivo OU baseline indistinguível |
| `likely_false_positive` | 10-29 | claim "passa" mas baseline retorna mesma página p/ fake |
| `not_found` | 0-9 | hard_negative OU 0 sinais OU negative marker explícito |
| `invalid` | — | erro técnico (timeout, cf_challenge, proxy_unavailable, http_error) |

`reliability=low` aplica multiplicador 0.5 → SPAs nunca atingem `confirmed` sem hard_positive.

### Sinais (todos retornados em `evidence[]`)

| Sinal | Peso | Hard? |
|---|---|---|
| Status code esperado match | +20 | — |
| Final URL contém username | +25 | — |
| Final URL == expected | +15 | — |
| Redirect → homepage | -50 | hard_neg |
| Redirect → login | 0 + warning | — |
| Redirect → search | -30 | — |
| Redirect → outro perfil shape | -50 | hard_neg |
| `<title>` contém username | +15 | — |
| `<title>` contém 404/not found | -50 | hard_neg |
| `<link canonical>` contém username | +20 | — |
| `og:url` contém username | +15 | — |
| JSON-LD `@id`/`identifier`/`alternateName` == username | +25 | — |
| JSON-LD `mainEntity.name` == username | +15 | — |
| Body ≥3KB | +5 | — |
| Body ≤500B | -20 | — |
| Body ≈ baseline (sim ≥0.92) | -60 | hard_neg se status=200 |
| Body ≠ baseline (sim ≤0.50) | +20 | — |
| Negative marker (regex/substring multi-idioma) | -100 | hard_neg |
| Positive marker site-specific (e.g. GitHub bio class) | +30 | hard_pos se único |
| Cloudflare challenge | 0 + error | — |

### Schema de resposta (Pydantic em `api/schemas.py`)

```python
class SherlockEvidence(BaseModel):
    signal: str
    weight: int
    detail: str = ""

class SherlockPlatformResponse(BaseModel):
    source: Literal["sherlock", "maigret"]
    username: str
    platform: str
    category: str
    icon: str
    url_original: str
    url_final: str
    redirect_chain: list[str] = []
    http_status: int | None = None
    fetch_status: Literal["ok", "timeout", "connection_error",
                          "proxy_unavailable", "cf_challenge",
                          "http_error", "invalid"]
    validation_status: Literal["confirmed", "likely", "uncertain",
                               "likely_false_positive", "not_found", "invalid"]
    confidence_score: int
    confidence_level: str
    evidence: list[SherlockEvidence] = []
    warnings: list[str] = []
    error: str | None = None
    checked_at: datetime
    reliability: Literal["normal", "low"] = "normal"
    baseline_used: bool = False
```

---

## Fases executáveis (Codex executa uma por vez)

### Fase A — Refactor estrutural (zero mudança comportamental)
**Objetivo:** extrair `sherlock_wrapper.py` em `modules/username_check/` sem alterar lógica.

**Editar/Mover:**
- `modules/sherlock_wrapper.py` → shim que re-exporta de `modules/username_check`
- Criar `modules/username_check/{__init__,runner,fetcher,rate_limit,proxy,budget}.py`
- `modules/username_check/sources/sherlock_curated.py` ← `PLATFORMS` movido cru

**Critério:** `pytest tests/ -q` exit 0; imports antigos continuam válidos; SSE byte-a-byte idêntico.

**Reverter:** `git revert` único commit.

---

### Fase B — Fetcher captura `final_url` + `redirect_chain`
**Editar:** `modules/username_check/fetcher.py`

```python
@dataclass
class FetchResult:
    status_code: int
    headers: dict
    body: bytes
    bytes_read: int
    final_url: str
    redirect_chain: list[str]
```

**Critério:** teste novo (301→200 mock); testes Phase 16 adaptados.

---

### Fase C — Validator interface + 3 validators genéricos
**Criar:**
- `modules/username_check/validators/base.py`
- `modules/username_check/validators/generic_content.py`
- `modules/username_check/validators/url_final.py`
- `modules/username_check/validators/negative_markers.py`
- `modules/username_check/validators/registry.py`

**Editar:** `runner.py` anexa `_outcomes` interno no `PlatformResult` (não exposto na API ainda).

**Critério:** ≥6 testes/validator; cobertura ≥90%; SSE output inalterado.

**Riscos:** regex match em `<script>`/comments. Mitigação: skip `<script>...</script>`, cap parse 100KB. Sem BeautifulSoup.

---

### Fase D — Baseline fetcher + `BaselineCompare`
**Criar:**
- `modules/username_check/baseline.py` (fake-user gen + LRU 1h por `(platform, hour_bucket)`)
- `modules/username_check/validators/baseline_compare.py`

**Body normalization:**
```python
_VOLATILE = re.compile(
    r'(csrf[_-]?token|nonce|timestamp|build[_-]?id|request[_-]?id|trace[_-]?id|'
    r'data-id="\d+"|/static/[a-f0-9]{8,}|\d{10,})', re.I)
```

**Flag:** `USERNAME_CHECK_BASELINE_ENABLED` env, default `false` na merge, `true` após Fase E estabilizar.

**Critério:** cache hit em 2ª busca <1h; site mock 200-para-tudo → `hard_negative`; baseline fail → warning, validação continua.

**Riscos:** 2× tráfego na 1ª busca/hora. Mitigação: semáforo separado cap 8; baseline só para top-50 sites.

---

### Fase E — Novo scoring + 5 níveis + normalize + SSE dual emission
**Criar:**
- `modules/username_check/scoring.py`
- `modules/username_check/normalize.py`

**Editar:**
- `runner.py` usa novo scoring
- `api/schemas.py` adiciona `SherlockPlatformResponse`, `SherlockUsernameResponse`, `SherlockEvidence`
- `api/services/search_service.py:482-545` emite dois eventos SSE:
  - `{"type":"sherlock", ...}` legacy (1 release)
  - `{"type":"sherlock_v2", ...}` novo

**Flag:** `SHERLOCK_VALIDATION_V2=true|false` env.

**Critério:** toda resposta tem `evidence ≥1` OU `error ≠ null`; `confirmed` exige hard_positive OU 3+ sinais; `reliability=low` nunca `confirmed` sem hard_positive; bench p50 ≤ 1.3× baseline.

---

### Fase F — Maigret como fonte de dados (NÃO fetcher)
**Objetivo:** carregar `MaigretDatabase` para expandir candidatos 25 → 500. Fetch sempre via httpx próprio.

**Criar:** `modules/username_check/sources/maigret_db.py`
- `from maigret.sites import MaigretDatabase` apenas
- `load_top_n_sites(n=500) → list[CandidatePlatform]`
- Adapter `MaigretSite` → schema interno (url_template, claim regex, tags, category)
- **CRÍTICO:** NÃO importar `maigret.search`, `maigret.report`, `maigret.checking`

**Editar:**
- `runner.py` — `candidates = sherlock_curated + maigret_db.top_n(500)`, dedup por domínio canônico
- `requirements.txt` — `maigret` instalado com `pip install maigret --no-deps`; deps manuais curadas: `aiohttp`, `lxml`, `socid_extractor`, `mock`, `python-Wappalyzer`, `aiodns` (confirmar lista exata em teste local)
- `Dockerfile` — sem `cairo`/`pycairo`; install Maigret no estágio builder com `--no-deps`
- `api/config.py` — `MAIGRET_TOP_N=500`, `MAIGRET_ENABLED=true`

**Critério:**
- Docker image ≤ 270MB (relaxado documentadamente de 250)
- `/health` expõe `maigret_sites_loaded: 500`
- Busca de username conhecido retorna ≥1 `confirmed` adicional vindo de Maigret-derived
- Bench p95 ≤ 60s (timeout config `sherlock: 120s` cobre)
- Bytes Thordata medidos reais

**Riscos (lições da remoção anterior):**
- Docker bloat → `--no-deps` + lista curada; documentar diff.
- Conflito `aiohttp` versão → pinear.
- `MaigretDatabase` API muda → pinear versão `maigret==X.Y.Z`; CI carrega DB.

**Reverter:** `MAIGRET_ENABLED=false`.

---

### Fase G — Validators site-specific (FP-rate alto primeiro)
**Ordem:**
1. `instagram.py` — força `uncertain` sem proxy; com proxy parse og:/JSON-LD
2. `x.py` — força `uncertain` sem proxy; avaliar Nitter/syndication
3. `linkedin.py` — status 999 → `invalid` warning `login_required`
4. `reddit.py` — challenge → `invalid` warning `bot_check`
5. `github.py` — bio class + avatar URL → hard_positive
6. `tiktok.py`, `youtube.py`, `medium.py` — incremental

**Critério por site:** ≥3 testes (real, inexistente, edge case).

---

### Fase H — Cache resultado + logs estruturados + métricas + UI v2
**Criar:** `modules/username_check/cache.py` (Redis 5min TTL; key = `sha256(username|VALIDATOR_VERSION)`)

**Editar:**
- `audit.py` populado com `log_decision`
- `api/routes/health.py` — `username_searches_total`, `baseline_cache_hits`, `validation_v2_pct`, `maigret_sites_loaded`, `confirmed_per_search_avg`
- `static/js/render.js` — exibe `evidence`, `confidence_level`, `warnings`; filtro p/ esconder `uncertain`/`likely_false_positive`

**Critério:** 2ª busca em 5min <50ms; E2E UI Amber/Noir renderiza nível + evidências.

---

### Fase I — Remoção legacy
**Pré-condição:** telemetria H mostra v2 estável ≥3 dias, FP-rate <1/5 do baseline.

**Dropar:** SSE `type:"sherlock"` legacy, `_compute_confidence` antigo, shim `sherlock_wrapper.py`.

---

## Métricas de sucesso

Antes (gate de Fase E — coletar amostragem manual 100 buscas):
- FP-rate: `___%`
- Confirmed-rate em SPAs: `___%`
- Latência p50: `___ms`
- Docker image: `___MB`

Após Fase I:
- FP-rate ≤ 1/5 do baseline
- `confirmed` em SPAs só com hard_positive
- Latência p50 ≤ 1.3× baseline
- Cobertura `modules/username_check/` ≥85%
- Docker image ≤ 270MB

---

## Testes obrigatórios

| Cenário | Fase |
|---|---|
| Username real GitHub conhecido | C, G |
| Username inexistente GitHub | C, G |
| Site mock retorna 200 para qualquer user | D |
| Redirect 200→homepage | C |
| Redirect 200→login | C |
| Redirect 200→search | C |
| Redirect 200→outro perfil | C |
| `<title>404</title>` page | C |
| `<link canonical>` aponta username real | C |
| JSON-LD com `@id` username | C |
| `httpx.ConnectError` rede | A |
| `httpx.TimeoutException` | A |
| `cf-mitigated: challenge` | A |
| Mesmo username 2× <5min cache hit | H |
| `reliability=low` não vira `confirmed` sem hard_positive | E |
| Baseline indistinguível → `likely_false_positive` | D |
| Username unicode sanitizado | A |
| HTML malformado sem crash | C |
| JSON-LD inválido ignorado | C |
| Sinais conflitantes → `uncertain` | E |
| Validator lança exceção isolada | C |
| Maigret DB load fail → fallback Sherlock-only | F |
| Maigret-derived site sem validator-specific usa genéricos | F |
| Docker build com `maigret --no-deps` resolve | F |

---

## Arquivos críticos a modificar

| Path | Fase | Tipo |
|---|---|---|
| `modules/sherlock_wrapper.py` | A | shim retrocompat |
| `modules/username_check/` (subpackage completo) | A-H | novo |
| `api/services/search_service.py` | E | dual-emit SSE |
| `api/schemas.py` | E | adicionar response models |
| `api/config.py` | E, F | flags e thresholds |
| `api/routes/health.py` | F, H | métricas |
| `api/budget.py` | F | confirmar accounting Maigret-derived |
| `requirements.txt` | F | `maigret` + deps mínimas |
| `Dockerfile` | F | `--no-deps` + deps manuais |
| `static/js/render.js` | H | UI evidence + level filter |
| `tests/fixtures/username_check/**` | C-H | HTML samples |

---

## Verificação end-to-end

### Após cada fase
```powershell
pytest tests/ -q --tb=short                  # exit 0
docker compose build nexus                   # ok
docker compose up -d
# request manual SSE com username real + inexistente
```

### Gates específicos
- **Fase F:** `docker images nexus --format "{{.Size}}"` ≤ 270MB
- **Fase E:** bench `scripts/bench_username_search.py` reporta p50 ≤ 1.3× baseline
- **Fase H:** `/health` retorna `maigret_sites_loaded`, `validation_v2_pct`, `baseline_cache_hits`
- **Fase I:** grep `_compute_confidence` = 0; grep `type":"sherlock"` legacy = 0

### Fora do escopo
- Headless browser (Playwright/Selenium)
- Scrape agressivo
- Tocar `oathnet_client.py`, `spiderfoot_wrapper.py`, `meridian.css`
- Reintroduzir `pycairo`/`cairo`
- Substituir Sherlock por Maigret — decisão: lado a lado, validators unificados

---

