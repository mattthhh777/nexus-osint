"""
modules/spiderfoot_wrapper.py
==============================
Wrapper para integração do SpiderFoot no NexusOSINT.

IMPORTANTE — Diferenças vs Sherlock:
  Sherlock   → 25 plataformas, ~10 segundos, funciona no Streamlit Cloud
  SpiderFoot → 200+ módulos, 5-30 minutos, requer instalação LOCAL

  Este wrapper NÃO funciona no Streamlit Cloud.
  Funciona em:
    ✅ Docker local (docker-compose)
    ✅ VPS com SpiderFoot instalado
    ✅ Máquina local com spiderfoot clonado

Como instalar o SpiderFoot localmente:
  git clone https://github.com/smicallef/spiderfoot.git /opt/spiderfoot
  cd /opt/spiderfoot && pip install -r requirements.txt

  Ou no Docker, adicione ao Dockerfile:
    RUN git clone https://github.com/smicallef/spiderfoot.git /opt/spiderfoot && \
        pip install -r /opt/spiderfoot/requirements.txt

Como funciona a integração:
  1. Roda SpiderFoot em modo CLI: python3 sf.py -s TARGET -u passive -o json -q
  2. Captura o JSON de saída
  3. Filtra os event types mais relevantes para OSINT
  4. Retorna SpiderFootResult estruturado

Modo "passive" (-u passive) = sem tocar diretamente no alvo.
Mais rápido e menos intrusivo que o modo "all".
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, field_validator

logger = logging.getLogger("nexusosint.spiderfoot")

# Onde o SpiderFoot está instalado — pode ser sobrescrito por env var
SPIDERFOOT_PATH = os.getenv(
    "SPIDERFOOT_PATH",
    "/opt/spiderfoot",   # padrão no Docker
)

# Event types mais úteis para OSINT de pessoas/usernames/emails
# Lista completa: python3 sf.py -T
RELEVANT_EVENTS = {
    # Identidade e contas
    "EMAILADDR":           "📧 Email Address",
    "USERNAME":            "👤 Username",
    "ACCOUNT_EXTERNAL_OWNED": "🌐 Conta em Plataforma",
    "SOCIAL_MEDIA":        "📱 Social Media",
    "PHONE_NUMBER":        "📱 Telefone",
    "HUMAN_NAME":          "👤 Nome Real",
    # Infraestrutura / domínios
    "DOMAIN_NAME":         "🔗 Domínio",
    "INTERNET_NAME":       "🌐 Host na Internet",
    "IP_ADDRESS":          "📍 IP Address",
    "LINKED_URL_INTERNAL": "🔗 URL Interna",
    "LINKED_URL_EXTERNAL": "🔗 URL Externa",
    # Segurança / vazamentos
    "LEAKSITE_CONTENT":    "💥 Conteúdo em Site de Leak",
    "LEAKSITE_URL":        "💥 URL de Site de Leak",
    "PASSWORD_COMPROMISED":"🔑 Senha Comprometida",
    "HASH_COMPROMISED":    "🔑 Hash Comprometida",
    "DATA_HAS_BEEN_PWNED": "⚠️ Dado Comprometido",
    "DARKNET_MENTION_URL": "🕵️ Menção na Darknet",
    # Rede e infra
    "NETBLOCK_OWNER":      "🏢 Dono do Bloco de Rede",
    "BGP_AS_OWNER":        "🏢 ASN Owner",
    "SSL_CERTIFICATE_ISSUED": "🔒 Certificado SSL",
    "GEOINFO":             "📍 Geolocalização",
    # Reputação
    "MALICIOUS_IPADDR":    "🚨 IP Malicioso",
    "MALICIOUS_EMAILADDR": "🚨 Email Malicioso",
    "BLACKLISTED_IPADDR":  "🚫 IP Bloqueado",
    "AFFILIATE_EMAILADDR": "🔗 Email Afiliado",
    "AFFILIATE_IPADDR":    "🔗 IP Afiliado",
    "RAW_RIR_DATA":        "📋 Dados RIR",
}

# Quanto tempo esperar por um scan (segundos)
# passive = mais rápido, all = mais completo mas muito mais lento
SCAN_TIMEOUT = int(os.getenv("SPIDERFOOT_TIMEOUT", "300"))  # 5 minutos padrão


# ── Input validation ──────────────────────────────────────────────────────────
# D-11: SpiderFoot target must be a valid FQDN or bare IPv4 address.
# Reject CIDR, IPv6, URL schemes, path traversal, unicode non-ASCII, and empty strings.

_FQDN_RE = re.compile(
    r"^(?=.{1,253}$)"
    r"(?!-)[A-Za-z0-9-]{1,63}(?<!-)"
    r"(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*"
    r"\.[A-Za-z]{2,63}$"
)
_IPV4_RE = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d?\d)$"
)


class SpiderFootTarget(BaseModel):
    """Pydantic v2 model — validates SpiderFoot scan target.

    Accepts:
      - Valid FQDN  (e.g. "example.com", "sub.example.co.uk")
      - Valid IPv4  (e.g. "192.168.1.1")

    Rejects everything else: IPv6, CIDR, URLs, path traversal,
    non-ASCII unicode, and empty strings.
    """

    target: str

    @field_validator("target")
    @classmethod
    def _validate_target(cls, v: str) -> str:
        v = (v or "").strip()
        if not v or len(v) > 253:
            raise ValueError("invalid target: must be FQDN or IPv4")
        if _IPV4_RE.match(v) or _FQDN_RE.match(v):
            return v
        raise ValueError("invalid target: must be FQDN or IPv4")


# ── Modelos de dados ──────────────────────────────────────────────────────────

@dataclass
class SpiderFootEvent:
    """Um evento/resultado individual do SpiderFoot."""
    event_type:  str = ""
    event_label: str = ""   # label amigável (ex: "Email Address")
    data:        str = ""   # o dado em si (ex: "user@email.com")
    source:      str = ""   # de onde veio (ex: "sfp_haveibeen")
    confidence:  int = 100  # 0-100


@dataclass
class SpiderFootResult:
    """
    Resultado completo de um scan SpiderFoot.

    Atributos:
        target       — o alvo escaneado
        success      — True se o scan rodou
        available    — True se o SpiderFoot está instalado
        events       — lista de todos os eventos relevantes encontrados
        by_type      — eventos agrupados por tipo {event_type: [events]}
        scan_mode    — "passive", "footprint", "investigate" ou "all"
        elapsed_s    — tempo que o scan levou
        error        — mensagem de erro se falhou
    """
    target:    str  = ""
    success:   bool = False
    available: bool = False   # False = SpiderFoot não está instalado
    events:    list[SpiderFootEvent] = field(default_factory=list)
    by_type:   dict[str, list[SpiderFootEvent]] = field(default_factory=dict)
    scan_mode: str  = "passive"
    elapsed_s: float = 0.0
    error:     str  = ""

    @property
    def found_count(self) -> int:
        return len(self.events)

    @property
    def has_leaked_data(self) -> bool:
        """True se encontrou senhas ou dados comprometidos."""
        leak_types = {"PASSWORD_COMPROMISED", "HASH_COMPROMISED",
                      "DATA_HAS_BEEN_PWNED", "LEAKSITE_CONTENT"}
        return any(e.event_type in leak_types for e in self.events)

    @property
    def has_darknet(self) -> bool:
        """True se encontrou menções na darknet."""
        return any(e.event_type == "DARKNET_MENTION_URL" for e in self.events)

    @property
    def risk_contribution(self) -> int:
        """Contribuição para o risk score (0-40)."""
        score = 0
        score += min(self.events_of("PASSWORD_COMPROMISED")  * 15, 20)
        score += min(self.events_of("DATA_HAS_BEEN_PWNED")   * 10, 15)
        score += min(self.events_of("DARKNET_MENTION_URL")   * 5,  10)
        score += min(self.events_of("MALICIOUS_IPADDR")      * 3,   5)
        return min(score, 40)

    def events_of(self, event_type: str) -> int:
        """Conta eventos de um tipo específico."""
        return len(self.by_type.get(event_type, []))

    def top_findings(self, n: int = 10) -> list[SpiderFootEvent]:
        """Retorna os N achados mais relevantes."""
        # Prioridade: leaked data > darknet > malicious > social > rest
        priority = {
            "PASSWORD_COMPROMISED": 0,
            "HASH_COMPROMISED": 0,
            "DATA_HAS_BEEN_PWNED": 1,
            "LEAKSITE_CONTENT": 1,
            "DARKNET_MENTION_URL": 2,
            "MALICIOUS_IPADDR": 3,
            "MALICIOUS_EMAILADDR": 3,
            "SOCIAL_MEDIA": 4,
            "ACCOUNT_EXTERNAL_OWNED": 4,
            "EMAILADDR": 5,
        }
        sorted_events = sorted(
            self.events,
            key=lambda e: priority.get(e.event_type, 9)
        )
        return sorted_events[:n]


# ── Verificação de instalação ─────────────────────────────────────────────────

def is_spiderfoot_available() -> bool:
    """Verifica se o SpiderFoot está instalado e acessível."""
    sf_script = Path(SPIDERFOOT_PATH) / "sf.py"

    if sf_script.exists():
        logger.debug("SpiderFoot found at %s", SPIDERFOOT_PATH)
        return True

    # Tenta também como comando no PATH
    try:
        result = subprocess.run(
            ["spiderfoot", "--help"],
            capture_output=True, timeout=5,
        )
        return result.returncode in (0, 1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_spiderfoot_version() -> str:
    """Retorna a versão do SpiderFoot instalada."""
    sf_script = Path(SPIDERFOOT_PATH) / "sf.py"
    try:
        cmd = ["python3", str(sf_script), "-V"] if sf_script.exists() else ["spiderfoot", "-V"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        # Output: "SpiderFoot 4.0.0: Open Source Intelligence Automation."
        for line in (result.stdout + result.stderr).splitlines():
            if "SpiderFoot" in line:
                return line.strip()
    except Exception:
        pass
    return "unknown"


# ── Scan principal ────────────────────────────────────────────────────────────

def run_spiderfoot_scan(
    target: str,
    scan_mode: str = "passive",
    timeout: int = SCAN_TIMEOUT,
    max_events: int = 500,
) -> SpiderFootResult:
    """
    Executa um scan SpiderFoot em modo CLI e retorna os resultados.

    Parâmetros:
      target     — o que buscar (email, IP, domínio, nome, username)
      scan_mode  — "passive" (padrão), "footprint", "investigate" ou "all"
                   passive    = só fontes públicas, sem tocar no alvo (~2-5min)
                   footprint  = mapeamento básico (~5-10min)
                   investigate= investigação completa (~10-30min)
                   all        = todos os módulos, muito lento
      timeout    — máximo de segundos para esperar (padrão: 300 = 5min)
      max_events — máximo de eventos para retornar (evita sobrecarga)

    Retorna:
      SpiderFootResult com todos os achados

    Uso:
      result = run_spiderfoot_scan("user@email.com", scan_mode="passive")
      if result.available and result.success:
          for event in result.top_findings():
              print(event.event_label, ":", event.data)
    """
    import time

    result = SpiderFootResult(target=target, scan_mode=scan_mode)
    t_start = time.time()

    # ── Passo 1: verifica se está instalado ───────────────────────────────
    if not is_spiderfoot_available():
        result.error = (
            "SpiderFoot não está instalado. "
            "Para usar: git clone https://github.com/smicallef/spiderfoot.git /opt/spiderfoot "
            "&& pip install -r /opt/spiderfoot/requirements.txt"
        )
        logger.warning("SpiderFoot not available: %s", result.error)
        return result

    result.available = True

    # ── Passo 2: monta o comando ──────────────────────────────────────────
    sf_script = Path(SPIDERFOOT_PATH) / "sf.py"
    cmd_base  = ["python3", str(sf_script)] if sf_script.exists() else ["spiderfoot"]

    # Monta os event types que queremos (-t filtra a saída)
    relevant_types = ",".join(RELEVANT_EVENTS.keys())

    cmd = cmd_base + [
        "-s", target,           # target
        "-u", scan_mode,        # use case: passive/footprint/investigate/all
        "-t", relevant_types,   # só esses event types
        "-o", "json",           # output em JSON
        "-q",                   # silencia logs internos
        "-f",                   # filtra só os tipos pedidos em -t
    ]

    logger.info(
        "Starting SpiderFoot scan | target='%s' mode=%s timeout=%ds",
        target, scan_mode, timeout
    )

    # ── Passo 3: executa o scan em processo separado ──────────────────────
    # IMPORTANTE: SpiderFoot usa um banco SQLite temporário por scan.
    # Usamos um diretório temp para não sujar o diretório de trabalho.
    with tempfile.TemporaryDirectory(prefix="nexusosint_sf_") as tmpdir:
        env = {**os.environ, "HOME": tmpdir}  # SpiderFoot escreve no HOME

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
                env=env,
            )

            elapsed = time.time() - t_start
            result.elapsed_s = round(elapsed, 1)

            if proc.returncode not in (0, 1):
                result.error = (
                    f"SpiderFoot retornou código {proc.returncode}. "
                    f"stderr: {proc.stderr[:200]}"
                )
                logger.error("SpiderFoot scan failed: %s", result.error)
                return result

            # ── Passo 4: parse do JSON ─────────────────────────────────────
            raw_output = proc.stdout.strip()
            if not raw_output:
                result.success = True  # scan rodou mas não achou nada
                logger.info("SpiderFoot returned no results for '%s'", target)
                return result

            result = _parse_output(raw_output, result, max_events)

        except subprocess.TimeoutExpired:
            result.error = (
                f"Scan cancelado após {timeout}s. "
                f"Use scan_mode='passive' para scans mais rápidos."
            )
            logger.warning("SpiderFoot scan timed out for '%s'", target)

        except FileNotFoundError:
            result.available = False
            result.error = "python3 ou sf.py não encontrado."
            logger.error("SpiderFoot executable not found")

        except Exception as exc:
            result.error = f"Erro inesperado: {exc}"
            logger.error("SpiderFoot scan exception: %s", exc, exc_info=True)

    result.elapsed_s = round(time.time() - t_start, 1)
    return result


def _parse_output(
    raw: str,
    result: SpiderFootResult,
    max_events: int,
) -> SpiderFootResult:
    """
    Faz parse do JSON de saída do SpiderFoot.

    O SpiderFoot produz um array JSON com objetos assim:
    [
      {
        "type": "EMAILADDR",
        "data": "user@example.com",
        "module": "sfp_haveibeen",
        "confidence": 100,
        ...
      },
      ...
    ]
    """
    try:
        # SpiderFoot às vezes adiciona linhas de log antes do JSON
        # Encontra o início do array JSON
        json_start = raw.find("[")
        json_end   = raw.rfind("]") + 1
        if json_start == -1 or json_end == 0:
            result.success = True  # sem resultados
            return result

        json_data = json.loads(raw[json_start:json_end])

    except json.JSONDecodeError as exc:
        result.error = f"Erro ao parsear JSON do SpiderFoot: {exc}"
        logger.warning("JSON parse error: %s", exc)
        result.success = True  # considera sucesso parcial
        return result

    # Processa cada evento
    seen = set()  # deduplicação
    for item in json_data[:max_events * 2]:  # lê mais para ter margem de dedup
        if not isinstance(item, dict):
            continue

        event_type = item.get("type", "")
        data       = str(item.get("data", "")).strip()

        # Filtra só event types relevantes
        if event_type not in RELEVANT_EVENTS:
            continue

        # Deduplicação por tipo+dado
        key = f"{event_type}:{data[:100]}"
        if key in seen:
            continue
        seen.add(key)

        event = SpiderFootEvent(
            event_type  = event_type,
            event_label = RELEVANT_EVENTS.get(event_type, event_type),
            data        = data[:500],  # limita tamanho
            source      = item.get("module", ""),
            confidence  = int(item.get("confidence", 100)),
        )
        result.events.append(event)

        # Agrupa por tipo
        if event_type not in result.by_type:
            result.by_type[event_type] = []
        result.by_type[event_type].append(event)

        if len(result.events) >= max_events:
            break

    result.success = True
    logger.info(
        "SpiderFoot parsed %d events for '%s' in %.1fs",
        len(result.events), result.target, result.elapsed_s
    )
    return result


# ── Renderização no Streamlit ─────────────────────────────────────────────────

def render_spiderfoot_results(result: SpiderFootResult) -> None:
    """
    Renderiza os resultados do SpiderFoot no Streamlit.
    Chame isso no _render_results() do app.py quando result.available=True.

    Uso no app.py:
        from modules.spiderfoot_wrapper import render_spiderfoot_results
        sf_result = st.session_state.get("spiderfoot_result")
        if sf_result:
            render_spiderfoot_results(sf_result)
    """
    import streamlit as st
    import pandas as pd

    if not result.available:
        st.markdown(
            '<div class="alert-warning">'
            '⚠️ <b>SpiderFoot não instalado.</b> '
            'Funciona apenas no Docker local / VPS. '
            '<a href="https://github.com/smicallef/spiderfoot" target="_blank">Ver instalação →</a>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    if not result.success:
        st.markdown(
            f'<div class="alert-danger">❌ Scan SpiderFoot falhou: {result.error}</div>',
            unsafe_allow_html=True,
        )
        return

    n = result.found_count
    label = f"🕷️ SpiderFoot — {n} achados em {result.elapsed_s}s ({result.scan_mode} mode)"

    with st.expander(label, expanded=n > 0):
        if n == 0:
            st.markdown(
                '<div class="alert-success">✅ Nenhum dado encontrado pelo SpiderFoot.</div>',
                unsafe_allow_html=True,
            )
            return

        # Alertas de alto risco no topo
        if result.has_leaked_data:
            st.markdown(
                '<div class="alert-danger">🔑 <b>Dados comprometidos encontrados!</b> '
                'Senhas ou hashes vazados detectados.</div>',
                unsafe_allow_html=True,
            )
        if result.has_darknet:
            st.markdown(
                '<div class="alert-warning">🕵️ <b>Menção na darknet detectada.</b></div>',
                unsafe_allow_html=True,
            )

        # Métricas por categoria
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total",        n)
        col2.metric("🔑 Leaked",    result.events_of("PASSWORD_COMPROMISED") +
                                    result.events_of("DATA_HAS_BEEN_PWNED"))
        col3.metric("🌐 Social",    result.events_of("SOCIAL_MEDIA") +
                                    result.events_of("ACCOUNT_EXTERNAL_OWNED"))
        col4.metric("🕵️ Darknet",   result.events_of("DARKNET_MENTION_URL"))

        # Top achados
        st.markdown("**🎯 Principais Achados**")
        top = result.top_findings(15)
        df = pd.DataFrame([{
            "Tipo":       e.event_label,
            "Dado":       e.data[:80],
            "Fonte":      e.source,
            "Confiança":  f"{e.confidence}%",
        } for e in top])
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Por categoria
        if len(result.by_type) > 1:
            st.markdown("**📊 Por Categoria**")
            cat_df = pd.DataFrame([{
                "Categoria": RELEVANT_EVENTS.get(t, t),
                "Quantidade": len(events),
            } for t, events in sorted(
                result.by_type.items(),
                key=lambda x: len(x[1]), reverse=True
            )])
            st.dataframe(cat_df, use_container_width=True, hide_index=True)

        # Texto para copiar
        lines = [f"=== SPIDERFOOT SCAN ===",
                 f"Target:  {result.target}",
                 f"Mode:    {result.scan_mode}",
                 f"Found:   {n} events",
                 f"Time:    {result.elapsed_s}s", ""]
        for e in result.events:
            lines.append(f"{e.event_label:<30} {e.data}")
        lines.append("\n=== END ===")

        with st.expander("📋 Copiar texto formatado"):
            st.text_area(
                "Ctrl+A → Ctrl+C:",
                value="\n".join(lines),
                height=200,
                key="sf_copy_txt",
                label_visibility="collapsed",
            )