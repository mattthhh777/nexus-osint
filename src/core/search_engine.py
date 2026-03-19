"""
src/core/search_engine.py
=========================
Motor de busca unificado do NexusOSINT.

Por que esse arquivo existe?
  O app.py original tinha a lógica de busca escrita em 2 lugares:
    - _render_tool_fullsearch() — linha ~1288
    - _run_hub_search()         — linha ~2128
  
  Qualquer bug precisava ser corrigido em 2 lugares, e as lógicas
  ficavam divergindo com o tempo. Este arquivo é o ponto único
  de entrada para TODAS as buscas.

Como usar no app.py:
  from src.core.search_engine import run_search, SearchConfig, detect_query_type

  q_type = detect_query_type("bictoftw")         # → "username"
  config = SearchConfig.auto(q_type)              # todos os módulos relevantes
  results = run_search("bictoftw", config, key)   # executa tudo
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional

# Configurar logging estruturado
# (os logs aparecem nos logs do Streamlit Cloud e no terminal local)
logger = logging.getLogger("nexusosint.search")

QueryType = Literal["email", "ip", "discord_id", "domain", "username", "phone"]


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DE BUSCA
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SearchConfig:
    """
    Define QUAIS módulos rodar em uma busca.
    
    Pense nela como um "pedido de busca":
      config = SearchConfig(run_breach=True, run_sherlock=True)
    
    Ou deixe ela decidir automaticamente pelo tipo do query:
      config = SearchConfig.auto("username")  # → ativa breach + stealer + sherlock + gaming
      config = SearchConfig.auto("email")     # → ativa breach + stealer + holehe + ghunt
    """
    run_breach:    bool = True
    run_stealer:   bool = True
    run_sherlock:  bool = False
    run_spiderfoot:bool = False   # requer instalação local — não funciona no Streamlit Cloud
    run_discord:   bool = False
    run_steam:     bool = False
    run_xbox:      bool = False
    run_roblox:    bool = False
    run_holehe:    bool = False
    run_ghunt:     bool = False
    run_ip:        bool = False
    run_subdomain: bool = False

    @classmethod
    def auto(cls, query_type: QueryType) -> "SearchConfig":
        """
        Modo Automated: decide automaticamente o que faz sentido rodar
        baseado no tipo de dado que o usuário digitou.
        
        Exemplos:
          "bictoftw"          → breach + stealer + sherlock + steam + xbox + roblox
          "user@gmail.com"    → breach + stealer + sherlock + holehe + ghunt
          "192.168.0.1"       → breach + stealer + ip_info
          "352826996163739666"→ breach + stealer + discord
          "example.com"       → breach + stealer + subdomain
        """
        is_email    = query_type == "email"
        is_username = query_type == "username"
        is_discord  = query_type == "discord_id"
        is_ip       = query_type == "ip"
        is_domain   = query_type == "domain"

        return cls(
            run_breach    = True,
            run_stealer   = True,
            run_sherlock  = is_email or is_username,
            run_discord   = is_discord,
            run_steam     = is_username,
            run_xbox      = is_username,
            run_roblox    = is_username,
            run_holehe    = is_email,
            run_ghunt     = is_email,
            run_ip        = is_ip,
            run_subdomain  = is_domain,
            run_spiderfoot = False,  # desabilitado por padrão — scan lento, habilite manualmente
        )

    @classmethod
    def from_manual_selection(
        cls,
        selected_modules: set[str],
        query_type: QueryType,
    ) -> "SearchConfig":
        """
        Modo Manual: respeita exatamente os módulos que o usuário selecionou
        na interface, mas ainda valida compatibilidade com o tipo de dado.
        
        Exemplo: se o usuário selecionou "holehe" mas digitou um IP,
        o holehe NÃO roda (holehe só funciona com email).
        """
        is_email    = query_type == "email"
        is_username = query_type == "username"
        is_discord  = query_type == "discord_id"
        is_ip       = query_type == "ip"
        is_domain   = query_type == "domain"

        return cls(
            run_breach    = "breaches"  in selected_modules,
            run_stealer   = "stealer"   in selected_modules,
            run_sherlock  = "sherlock"  in selected_modules and (is_email or is_username),
            run_discord   = "discord"   in selected_modules and is_discord,
            run_steam     = "steam"     in selected_modules and is_username,
            run_xbox      = "xbox"      in selected_modules and is_username,
            run_roblox    = "roblox"    in selected_modules and is_username,
            run_holehe    = "holehe"    in selected_modules and is_email,
            run_ghunt     = "ghunt"     in selected_modules and is_email,
            run_ip        = "ip_info"   in selected_modules and is_ip,
            run_subdomain  = "subdomain" in selected_modules and is_domain,
            run_spiderfoot = "spiderfoot" in selected_modules,
        )

    @property
    def total_modules(self) -> int:
        """Quantos módulos vão rodar — usado para calcular o progresso."""
        return sum([
            self.run_breach, self.run_stealer, self.run_sherlock,
            self.run_discord, self.run_steam, self.run_xbox, self.run_roblox,
            self.run_holehe, self.run_ghunt, self.run_ip, self.run_subdomain,
            self.run_spiderfoot,
        ])

    def module_labels(self) -> list[str]:
        """Retorna lista de nomes dos módulos que vão rodar — para exibir na UI."""
        mapping = {
            "run_breach":    "🔓 Breaches",
            "run_stealer":   "🦠 Stealer Logs",
            "run_sherlock":  "🌐 Sherlock",
            "run_discord":   "🎮 Discord",
            "run_steam":     "🎮 Steam",
            "run_xbox":      "🕹️ Xbox",
            "run_roblox":    "🧱 Roblox",
            "run_holehe":    "📧 Holehe",
            "run_ghunt":     "🔍 GHunt",
            "run_ip":        "📍 IP Info",
            "run_subdomain":  "🔗 Subdomínios",
            "run_spiderfoot": "🕷️ SpiderFoot",
        }
        return [label for attr, label in mapping.items() if getattr(self, attr)]


# ══════════════════════════════════════════════════════════════════════════════
# RESULTADO DA BUSCA
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SearchResults:
    """
    Contém todos os resultados de uma busca, de todos os módulos.
    
    Uso:
        results.oath_result   → dados de breach/stealer/holehe da OathNet
        results.sherl_result  → dados do Sherlock (redes sociais)
        results.extras        → dados extras: discord, gaming, ip, subdomains
        results.errors        → dict com erros por módulo: {"steam": "não encontrado"}
        results.risk_score    → pontuação 0-100 calculada automaticamente
        results.elapsed_s     → tempo total da busca em segundos
    """
    query:        str
    query_type:   QueryType
    oath_result:  Optional[object] = None   # OathnetResult
    sherl_result: Optional[object] = None   # SherlockResult
    sf_result:    Optional[object] = None   # SpiderFootResult
    extras:       dict = field(default_factory=dict)
    errors:       dict[str, str] = field(default_factory=dict)
    elapsed_s:    float = 0.0
    config:       Optional[SearchConfig] = None

    @property
    def risk_score(self) -> int:
        """
        Calcula o risk score combinando todos os módulos.
        Fórmula:
          Breach:  cada registro = +15 pts (máx 45)
          Stealer: cada registro = +20 pts (máx 40)
          Holehe:  cada serviço  = +3 pts  (máx 15)
          Total máximo: 100
        """
        score = 0
        if self.oath_result:
            score += self.oath_result.risk_score
        if self.sherl_result:
            score += self.sherl_result.risk_score
        if self.sf_result and hasattr(self.sf_result, "risk_contribution"):
            score += self.sf_result.risk_contribution
        return min(score, 100)

    @property
    def has_results(self) -> bool:
        """True se encontrou qualquer coisa."""
        if self.oath_result:
            o = self.oath_result
            if o.breach_count > 0 or o.stealer_count > 0 or len(o.holehe_domains) > 0:
                return True
        if self.sherl_result and self.sherl_result.found_count > 0:
            return True
        return any(
            v.get("ok") and v.get("data")
            for v in self.extras.values()
            if isinstance(v, dict)
        )

    def summary(self) -> dict[str, int]:
        """Retorna contagens resumidas para os metric cards."""
        return {
            "breaches":  self.oath_result.breach_count if self.oath_result else 0,
            "stealers":  self.oath_result.stealer_count if self.oath_result else 0,
            "holehe":    len(self.oath_result.holehe_domains) if self.oath_result else 0,
            "social":    self.sherl_result.found_count if self.sherl_result else 0,
        }


# ══════════════════════════════════════════════════════════════════════════════
# DETECÇÃO DE TIPO (mesma lógica do validators.py, mais leve)
# ══════════════════════════════════════════════════════════════════════════════

def detect_query_type(query: str) -> QueryType:
    """
    Detecta o tipo do query para o search engine.
    Use validators.validate_query() na UI (faz sanitização completa).
    Esta função é usada internamente quando o tipo já foi validado.
    """
    q = query.strip()
    if re.match(r'^\d{14,19}$', q):
        return "discord_id"
    if re.match(r'^\+\d{7,15}$', q):
        return "phone"
    if re.match(r'^[\w.+\-]+@[\w\-]+\.[\w.]{2,}$', q, re.IGNORECASE):
        return "email"
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', q):
        return "ip"
    if re.match(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$', q):
        return "domain"
    return "username"


# ══════════════════════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL — ponto único de entrada para buscas
# ══════════════════════════════════════════════════════════════════════════════

def run_search(
    query: str,
    config: SearchConfig,
    api_key: str,
    on_progress: Optional[Callable[[int, str], None]] = None,
) -> SearchResults:
    """
    Executa todos os módulos de busca configurados em `config`.
    
    Esta função SUBSTITUI completamente:
      - _render_tool_fullsearch() do app.py (linha ~1288)
      - _run_hub_search() do app.py (linha ~2128)
    
    Parâmetros:
      query        — o que buscar ("bictoftw", "user@email.com", etc.)
      config       — quais módulos rodar (use SearchConfig.auto() ou .from_manual_selection())
      api_key      — chave da OathNet
      on_progress  — callback opcional: on_progress(50, "Sherlock...") atualiza a UI
    
    Retorna:
      SearchResults com todos os dados, erros e métricas
    
    Exemplo de uso:
      from src.core.search_engine import run_search, SearchConfig, detect_query_type
      
      q_type = detect_query_type("bictoftw")
      config = SearchConfig.auto(q_type)
      
      progress = st.progress(0)
      results = run_search(
          "bictoftw",
          config,
          api_key=OATHNET_API_KEY,
          on_progress=lambda pct, lbl: progress.progress(pct, text=lbl)
      )
    """
    # Importações aqui dentro para não criar dependência circular
    # e para que o arquivo possa ser testado sem Streamlit
    from modules.oathnet_client import OathnetClient
    from modules.sherlock_wrapper import search_username

    t_start = time.time()
    q_type  = detect_query_type(query)
    results = SearchResults(query=query, query_type=q_type, config=config)
    client  = OathnetClient(api_key=api_key)

    if config.total_modules == 0:
        results.errors["config"] = "Nenhum módulo selecionado para este tipo de dado."
        return results

    # Contagem para calcular % de progresso
    done    = [0]

    def _step(label: str) -> None:
        """Avança a barra de progresso e atualiza o label."""
        done[0] += 1
        if on_progress:
            pct = min(int(done[0] / config.total_modules * 100), 99)
            on_progress(pct, label)
        logger.debug("[%s/%s] %s", done[0], config.total_modules, label)

    # ── Módulo 1+2+3: Breach + Stealer + Holehe ───────────────────────────
    # Fazemos juntos para usar o mesmo cliente e poupar tempo de conexão
    if config.run_breach or config.run_stealer or config.run_holehe:
        _step("🔓 Vazamentos (Breach DB)…")
        try:
            res = client.search_breach(query)

            if config.run_stealer:
                _step("🦠 Stealer Logs…")
                sts = client.search_stealer_v2(query)
                res.stealers       = sts.stealers
                res.stealers_found = sts.stealers_found

            if config.run_holehe and q_type == "email":
                _step("📧 Holehe (serviços cadastrados)…")
                h = client.holehe(query)
                res.holehe_domains = h.holehe_domains

            results.oath_result = res

        except Exception as exc:
            # LOGGING ESTRUTURADO — substitui os "except: pass" do app.py original
            # Agora o erro aparece nos logs DO Streamlit Cloud e no terminal local
            logger.error(
                "OathNet search failed | query='%s' type=%s | error: %s",
                query, q_type, exc,
                exc_info=True,  # inclui o stack trace completo no log
            )
            results.errors["oathnet"] = str(exc)

    # ── Módulo 4: Sherlock (redes sociais) ────────────────────────────────
    if config.run_sherlock:
        _step("🌐 Sherlock (25+ plataformas)…")
        try:
            # Para email: usa a parte antes do @ como username
            uname = query if q_type == "username" else query.split("@")[0]
            results.sherl_result = search_username(uname, prefer_cli=False)

        except Exception as exc:
            logger.error("Sherlock failed | query='%s' | error: %s", query, exc, exc_info=True)
            results.errors["sherlock"] = str(exc)

    # ── Módulo 5: SpiderFoot (scan OSINT completo — apenas local) ─────────
    # NOTA: SpiderFoot não funciona no Streamlit Cloud.
    # Só roda se: 1) config.run_spiderfoot=True  2) SpiderFoot instalado
    if config.run_spiderfoot:
        _step("🕷️ SpiderFoot (scan completo)…")
        try:
            from modules.spiderfoot_wrapper import run_spiderfoot_scan, is_spiderfoot_available
            if is_spiderfoot_available():
                results.sf_result = run_spiderfoot_scan(
                    query,
                    scan_mode="passive",  # rápido e não-intrusivo
                    timeout=int(os.getenv("SPIDERFOOT_TIMEOUT", "300")),
                )
            else:
                logger.info("SpiderFoot not installed, skipping")
                results.sf_result = None
        except Exception as exc:
            logger.error("SpiderFoot failed | query='%s' | %s", query, exc, exc_info=True)
            results.errors["spiderfoot"] = str(exc)

    # ── Módulos extras (Discord, Gaming, IP, Subdomain) ───────────────────
    _run_extra_modules(client, query, q_type, config, results, _step)

    # ── Finalização ───────────────────────────────────────────────────────
    results.elapsed_s = round(time.time() - t_start, 1)

    if on_progress:
        on_progress(100, "✅ Busca concluída!")

    logger.info(
        "Search complete | query='%s' type=%s risk=%d elapsed=%.1fs errors=%s",
        query, q_type, results.risk_score, results.elapsed_s,
        list(results.errors.keys()) if results.errors else "none",
    )

    return results


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULOS EXTRAS — separados para manter run_search() legível
# ══════════════════════════════════════════════════════════════════════════════

def _run_extra_modules(  # noqa

    client: object,
    query: str,
    q_type: QueryType,
    config: SearchConfig,
    results: SearchResults,
    step: Callable[[str], None],
) -> None:
    """
    Executa os módulos extras (GHunt, Discord, Gaming, IP, Subdomínios).
    Cada um tem seu próprio try/except para que um erro não cancele os outros.
    """

    # GHunt (informações da conta Google — só para email)
    if config.run_ghunt and q_type == "email":
        step("🔍 GHunt (conta Google)…")
        try:
            ok, data = client._get("service/ghunt", params={"email": query})
            results.extras["ghunt"] = {
                "ok": ok,
                "data": data.get("data", data) if ok else None,
                "error": "" if ok else data.get("error", "GHunt falhou"),
            }
        except Exception as exc:
            logger.warning("GHunt failed | query='%s' | %s", query, exc)
            results.extras["ghunt"] = {"ok": False, "data": None, "error": str(exc)}

    # Discord (perfil + histórico de usernames)
    if config.run_discord and q_type == "discord_id":
        step("🎮 Discord (perfil + histórico)…")
        try:
            ok_u, user = client.discord_userinfo(query)
            ok_h, hist = client.discord_username_history(query)
            results.extras["discord"] = {
                "user":    {"ok": ok_u, "data": user if ok_u else None},
                "history": {"ok": ok_h, "data": hist if ok_h else None},
            }
        except Exception as exc:
            logger.warning("Discord lookup failed | id='%s' | %s", query, exc)
            results.extras["discord"] = {"user": {"ok": False}, "history": {"ok": False}}

    # Plataformas de gaming — Steam, Xbox, Roblox
    gaming_modules = [
        ("steam",  config.run_steam,  lambda q: client.steam_lookup(q),               "🎮 Steam…"),
        ("xbox",   config.run_xbox,   lambda q: client.xbox_lookup(q),                "🕹️ Xbox…"),
        ("roblox", config.run_roblox, lambda q: client.roblox_lookup(username=q),     "🧱 Roblox…"),
    ]

    for key, should_run, method, label in gaming_modules:
        if not should_run:
            continue
        step(label)
        try:
            ok, data = method(query)
            results.extras[key] = {
                "ok":    ok,
                "data":  data if ok else None,
                "error": "" if ok else data.get("error", f"{key} não encontrado"),
            }
        except Exception as exc:
            logger.warning("%s lookup failed | query='%s' | %s", key, query, exc)
            results.extras[key] = {"ok": False, "data": None, "error": str(exc)}

    # IP Info (geolocalização e rede)
    if config.run_ip and q_type == "ip":
        step("📍 IP Info (geolocalização)…")
        try:
            ok, data = client.ip_info(query)
            results.extras["ip_info"] = {
                "ok":   ok,
                "data": data if ok else None,
                "error": "" if ok else data.get("error", "IP lookup falhou"),
            }
        except Exception as exc:
            logger.warning("IP info failed | ip='%s' | %s", query, exc)
            results.extras["ip_info"] = {"ok": False, "data": None, "error": str(exc)}

    # Subdomínios (só para domains)
    if config.run_subdomain and q_type == "domain":
        step("🔗 Subdomínios…")
        try:
            ok, data = client.extract_subdomains(query)
            subs = data.get("subdomains", []) if ok else []
            results.extras["subdomains"] = {
                "ok":    ok,
                "data":  subs,
                "count": len(subs),
                "error": "" if ok else data.get("error", "Subdomain lookup falhou"),
            }
        except Exception as exc:
            logger.warning("Subdomain lookup failed | domain='%s' | %s", query, exc)
            results.extras["subdomains"] = {"ok": False, "data": [], "count": 0, "error": str(exc)}


# ══════════════════════════════════════════════════════════════════════════════
# CACHE LAYER — economiza sua cota da OathNet
# ══════════════════════════════════════════════════════════════════════════════

def make_cached_runner(api_key: str):
    """
    Retorna uma versão cacheada de run_search.
    
    Por que cache?
      Você tem 100 lookups/dia no plano Starter.
      Sem cache: buscar "bictoftw" 3x = 3 lookups gastos.
      Com cache:  buscar "bictoftw" 3x = 1 lookup (os outros 2 usam cache).
    
    O cache dura 2 horas por padrão.
    Isso significa: se você buscar o mesmo alvo de manhã e de tarde,
    a busca da tarde usa cache. Se buscar amanhã, usa um novo lookup.
    
    Como usar no app.py:
        from src.core.search_engine import make_cached_runner
        
        # Cria a função cacheada uma vez (o @st.cache_data fica nela)
        cached_search = make_cached_runner(OATHNET_API_KEY)
        
        # Usa normalmente — o cache é automático
        results = cached_search("bictoftw", config_json)
    
    IMPORTANTE: st.cache_data não aceita objetos complexos como parâmetros,
    por isso config é passado como JSON string.
    """
    import json
    import streamlit as st
    from datetime import timedelta

    @st.cache_data(
        ttl=timedelta(hours=2),      # cache válido por 2 horas
        show_spinner=False,           # o spinner é gerenciado pelo app.py
        hash_funcs={},                # sem funções de hash customizadas
    )
    def _cached_run(query: str, config_json: str) -> dict:
        """
        Versão cacheada do run_search.
        Retorna um dict (serializável) em vez de SearchResults
        porque st.cache_data precisa serializar o resultado.
        """
        config_data = json.loads(config_json)
        config = SearchConfig(**config_data)

        # Sem callback de progresso no cache (não temos acesso ao st.progress aqui)
        results = run_search(query, config, api_key, on_progress=None)

        # Serializa o resultado para o cache
        return {
            "query":       results.query,
            "query_type":  results.query_type,
            "elapsed_s":   results.elapsed_s,
            "risk_score":  results.risk_score,
            "errors":      results.errors,
            "oath_result": results.oath_result,
            "sherl_result":results.sherl_result,
            "extras":      results.extras,
        }

    def run_with_cache(query: str, config: SearchConfig) -> SearchResults:
        """Wrapper que serializa config e chama a função cacheada."""
        config_json = json.dumps({
            k: v for k, v in config.__dict__.items()
            if not k.startswith("_")
        })
        raw = _cached_run(query, config_json)

        # Reconstrói o SearchResults a partir do dict cacheado
        r = SearchResults(
            query        = raw["query"],
            query_type   = raw["query_type"],
            oath_result  = raw["oath_result"],
            sherl_result = raw["sherl_result"],
            extras       = raw["extras"],
            errors       = raw["errors"],
            elapsed_s    = raw["elapsed_s"],
        )
        return r

    return run_with_cache