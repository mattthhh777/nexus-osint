"""
app.py — NexusOSINT
====================
Ponto de entrada principal. APENAS 2 responsabilidades:
  1. Configurar a página Streamlit
  2. Chamar main()

Tudo mais fica nos módulos src/.

ANTES: app.py tinha 2.581 linhas fazendo tudo.
AGORA: app.py tem ~80 linhas — é só o "cabo de força".
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

# ── Configurar logging ANTES de qualquer import ───────────────────────────────
# Isso garante que todos os módulos (search_engine, validators, etc.)
# já encontrem o logger configurado quando forem importados.
def _setup_logging() -> None:
    """Configura logging para console + arquivo rotativo."""
    Path("logs").mkdir(exist_ok=True)
    root = logging.getLogger("nexusosint")
    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Console (aparece nos logs do Streamlit Cloud)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.WARNING)   # só warnings+ no console
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # Arquivo rotativo (5 MB, 5 backups = ~25 MB máximo)
    try:
        fh = logging.handlers.RotatingFileHandler(
            "logs/nexusosint.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        fh.setLevel(logging.INFO)   # tudo no arquivo
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass  # Streamlit Cloud pode não ter filesystem writável — sem problema

_setup_logging()

import streamlit as st
from dotenv import load_dotenv

# ── Carrega variáveis do .env ANTES de qualquer import que use config ─────────
load_dotenv()

# ── Configuração de página ────────────────────────────────────────────────────
# DEVE ser a primeira chamada st.* — antes de qualquer outro st.
st.set_page_config(
    page_title  = "NexusOSINT",
    page_icon   = "🔍",
    layout      = "wide",
    initial_sidebar_state = "collapsed",
)

# ── Imports dos módulos internos (depois do set_page_config) ──────────────────
from modules.oathnet_client import OathnetClient, OathnetResult, OATHNET_BASE_URL
from modules.sherlock_wrapper import SherlockResult, search_username
from modules.report_generator import generate_html, generate_pdf
from typing import Optional
from src.core.search_engine import (
    SearchConfig,
    SearchResults,
    detect_query_type,
    run_search,
    make_cached_runner,
)
from src.core.quota_guardian import QuotaGuardian
from src.utils.validators import validate_query, get_display_label

# ── Constantes globais ────────────────────────────────────────────────────────

# API Key: lê do Streamlit Secrets (produção) ou .env (local)
# NUNCA hardcode aqui — se você ver uma chave real aqui, remova imediatamente
OATHNET_API_KEY: str = (
    st.secrets.get("OATHNET_API_KEY", "") if hasattr(st, "secrets") else ""
) or os.getenv("OATHNET_API_KEY", "")

DEBUG_MODE:  bool = os.getenv("DEBUG", "false").lower() == "true"
APP_VERSION: str  = "2.0.0"
CASES_FILE:  Path = Path("cases.json")

# Cache de busca — criado uma vez, reutilizado em todas as execuções do Streamlit
# O cache economiza sua cota OathNet (100/dia no plano Starter)
_cached_search = make_cached_runner(OATHNET_API_KEY) if OATHNET_API_KEY else None

import pandas as pd
import json
import re


# ── CSS/Theme ─────────────────────────────────────────────────────────────────
# Importar de um arquivo separado mantém o app.py limpo

_DARK_CSS = """

<style>
    [data-testid="stSidebar"]        { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    .stMainBlockContainer            { max-width: 100% !important; padding: 0 2rem !important; }
    :root {
        --bg:      #0d1117; --bg2: #161b22; --bg3: #1c2128;
        --border:  #30363d; --cyan: #00d4ff; --green: #39d353;
        --red:     #f85149; --orange: #f0883e; --yellow: #ffd700;
        --text:    #e6edf3; --muted: #8b949e;
    }
    html, body, [data-testid="stApp"] {
        background-color: var(--bg) !important;
        color: var(--text) !important;
        font-family: 'Consolas', 'Courier New', monospace;
    }
    [data-testid="stMetric"] {
        background: var(--bg3); border: 1px solid var(--border);
        border-radius: 8px; padding: 12px 16px;
    }
    [data-testid="stMetricValue"]  { color: var(--cyan)  !important; font-size: 1.6rem; font-weight: 700; }
    [data-testid="stMetricLabel"]  { color: var(--muted) !important; font-size: 0.75rem; }
    [data-testid="stMetricDelta"]  { font-size: 0.75rem !important; }
    [data-testid="stDataFrame"]    { border: 1px solid var(--border); border-radius: 6px; }
    [data-testid="stExpander"]     { background: var(--bg3) !important; border: 1px solid var(--border) !important; border-radius: 6px !important; }
    .stTextInput input             { background: var(--bg3) !important; border: 1px solid var(--border) !important; color: var(--text) !important; border-radius: 6px !important; }
    .stButton > button             { background: linear-gradient(135deg, #00d4ff22, #00d4ff11) !important; border: 1px solid var(--cyan) !important; color: var(--cyan) !important; border-radius: 6px !important; transition: all 0.2s; }
    .stButton > button:hover       { background: var(--cyan) !important; color: #000 !important; }
    hr                             { border-color: var(--border) !important; }
    .platform-found  { display: inline-block; background: #39d35322; border: 1px solid #39d353; color: #39d353; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; margin: 2px; }
    .alert-success   { background:#39d35315; border:1px solid #39d353; border-radius:6px; padding:10px 14px; color:#39d353; margin:6px 0; }
    .alert-danger    { background:#f8514915; border:1px solid #f85149; border-radius:6px; padding:10px 14px; color:#f85149; margin:6px 0; }
    .alert-warning   { background:#f0883e15; border:1px solid #f0883e; border-radius:6px; padding:10px 14px; color:#f0883e; margin:6px 0; }
    .alert-info      { background:#00d4ff15; border:1px solid #00d4ff; border-radius:6px; padding:10px 14px; color:#00d4ff; margin:6px 0; }
    .case-card       { background: var(--bg3); border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px; margin: 6px 0; }
    .case-card:hover { border-color: var(--cyan); }
    .case-target     { font-weight: 700; color: var(--cyan); font-size: 0.9rem; }
    .case-meta       { font-size: 0.7rem; color: var(--muted); }
    div.cat-row div[data-testid="stButton"] button { border-radius: 999px !important; padding: 4px 14px !important; font-size: .78rem !important; min-height: 0 !important; height: 32px !important; }
    div.mod-row div[data-testid="stButton"] button { border-radius: 8px !important; padding: 4px 12px !important; font-size: .76rem !important; height: 30px !important; }
    div[data-testid="stRadio"] > div { flex-direction: row !important; gap: 16px !important; }
    .hub h1          { text-align: center; font-size: 1.8rem; font-weight: 900; color: var(--text); letter-spacing: .04em; margin: 24px 0 4px; }
    .hub-sub         { text-align: center; color: var(--muted); font-size: .84rem; margin: 0 0 22px; }
    .hub-meta        { display: flex; gap: 16px; color: var(--muted); font-size: .74rem; margin-top: 4px; flex-wrap: wrap; }
</style>
"""


# ── Gerenciamento de state ────────────────────────────────────────────────────

def _init_state() -> None:
    """
    Inicializa o session_state com valores padrão.
    Centralizado aqui para ter uma visão clara de TUDO que usamos.
    """
    defaults: dict = {
        # Resultados da última busca
        "investigation":    None,
        "search_results":   None,   # SearchResults object

        # Estado da UI do hub de busca
        "hub_active_cat":   "Data Leaks",
        "hub_active_mods":  {"breaches", "stealer"},

        # Histórico de casos
        "cases":            _load_cases(),
        "active_case_id":   None,

        # Busca específica / flags
        "breach_page":      0,
        "authenticated":    False,
    }

    for key, default_val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_val


def _load_cases() -> list[dict]:
    """Carrega histórico de casos do arquivo JSON."""
    if CASES_FILE.exists():
        try:
            return json.loads(CASES_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logging.getLogger("nexusosint").warning("Could not load cases.json: %s", exc)
    return []


def _save_case(query: str, category: str, results: SearchResults) -> str:
    """Salva um caso no histórico e retorna o ID."""
    import json, time

    case_id = f"{query}_{int(time.time())}"
    case = {
        "id":         case_id,
        "target":     query,
        "target_type":category,
        "timestamp":  __import__("datetime").datetime.now().isoformat(),
        "risk_score": results.risk_score,
        "breach_count": results.oath_result.breach_count if results.oath_result else 0,
        "social_count": results.sherl_result.found_count if results.sherl_result else 0,
    }
    st.session_state.cases.insert(0, case)
    # Limita a 50 casos para não crescer infinitamente
    st.session_state.cases = st.session_state.cases[:50]
    st.session_state.active_case_id = case_id

    try:
        CASES_FILE.write_text(
            json.dumps(st.session_state.cases, indent=2, default=str),
            encoding="utf-8",
        )
    except OSError as exc:
        logging.getLogger("nexusosint").warning("Could not save cases: %s", exc)

    return case_id


# ── Helpers de risco ──────────────────────────────────────────────────────────

def _risk_label(score: int) -> tuple[str, str]:
    """Retorna (label, cor_hex) para um risk score."""
    if score >= 75: return "CRÍTICO", "#f85149"
    if score >= 50: return "ALTO",    "#f0883e"
    if score >= 25: return "MÉDIO",   "#ffd700"
    return "BAIXO", "#39d353"


# ── Password gate ─────────────────────────────────────────────────────────────

def _check_password() -> bool:
    """
    Retorna True se o usuário pode acessar o app.
    Se APP_PASSWORD não está configurada, acesso é livre.
    """
    pwd_required = (
        st.secrets.get("APP_PASSWORD", "") if hasattr(st, "secrets") else ""
    ) or os.getenv("APP_PASSWORD", "")

    if not pwd_required or st.session_state.authenticated:
        return True

    # Tela de login
    st.markdown(
        """<div style="max-width:400px;margin:80px auto;text-align:center">
          <div style="font-size:3rem">⬡</div>
          <h2 style="color:#00d4ff">NEXUSOSINT</h2>
          <p style="color:#8b949e">Acesso restrito.</p>
        </div>""",
        unsafe_allow_html=True,
    )
    col = st.columns([1, 2, 1])[1]
    with col:
        pwd = st.text_input("Senha", type="password", label_visibility="collapsed",
                            placeholder="Digite a senha…")
        if st.button("Entrar", use_container_width=True):
            if pwd == pwd_required:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Senha incorreta.")
    return False


# ══════════════════════════════════════════════════════════════════════════════
# HUB DE BUSCA
# ══════════════════════════════════════════════════════════════════════════════

def _render_hub() -> None:
    """
    Tela principal de busca — o hub.
    Agora usa validate_query() para sanitizar inputs e
    SearchConfig para configurar os módulos.
    """
    CATEGORIES = {
        "Data Leaks":         {"icon": "🛡️", "modules": {"breaches": ("🔓","Breaches"), "stealer": ("📋","Stealer Logs")}},
        "Social & Gaming":    {"icon": "🎮", "modules": {"sherlock": ("🌐","Sherlock"), "discord": ("💬","Discord"), "steam": ("🎮","Steam"), "xbox": ("🕹️","Xbox"), "roblox": ("🧱","Roblox")}},
        "Email Intelligence": {"icon": "📧", "modules": {"holehe": ("📨","Holehe"), "ghunt": ("🔍","GHunt")}},
        "Network":            {"icon": "🌐", "modules": {"ip_info": ("📍","IP Info"), "subdomain": ("🔗","Subdomínios")}},
    }

    st.markdown('<div class="hub">', unsafe_allow_html=True)
    st.markdown('<h1>⬡ NexusOSINT</h1><p class="hub-sub">Plataforma de investigação OSINT · OathNet + Sherlock</p>', unsafe_allow_html=True)

    # Widget de quota — mostra uso da API em tempo real
    QuotaGuardian.load().render_widget()

    # ── Barra de busca ──────────────────────────────────────────────────────
    c1, c2 = st.columns([5, 1])
    with c1:
        raw_query = st.text_input(
            "Buscar",
            placeholder="username · email · IP · Discord ID · domínio…",
            key="hub_query_input",
            label_visibility="collapsed",
        )
    with c2:
        search_clicked = st.button("Search →", key="hub_search_btn", type="primary", use_container_width=True)

    # ── Modo + info ─────────────────────────────────────────────────────────
    cm, ci = st.columns([2, 5])
    with cm:
        mode = st.radio("Modo", ["Automated", "Manual"], horizontal=True,
                        key="hub_mode", label_visibility="collapsed")
    with ci:
        st.markdown('<div class="hub-meta"><span>📦 Bulk</span><span>🛡 Secure</span><span>📊 15+ Sources</span></div>',
                    unsafe_allow_html=True)

    # ── Categorias ──────────────────────────────────────────────────────────
    active_cat  = st.session_state.get("hub_active_cat", "Data Leaks")
    active_mods = st.session_state.get("hub_active_mods", {"breaches", "stealer"})

    st.markdown('<div class="cat-row" style="margin-top:8px">', unsafe_allow_html=True)
    cat_cols = st.columns(len(CATEGORIES))
    for i, (cat_name, cat_data) in enumerate(CATEGORIES.items()):
        with cat_cols[i]:
            if st.button(f"{cat_data['icon']} {cat_name}", key=f"hub_cat_{cat_name}",
                         type="primary" if cat_name == active_cat else "secondary",
                         use_container_width=True):
                st.session_state.hub_active_cat  = cat_name
                st.session_state.hub_active_mods = set(cat_data["modules"].keys())
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Módulos da categoria ────────────────────────────────────────────────
    cat_modules = CATEGORIES[active_cat]["modules"]
    if mode == "Manual":
        st.markdown('<div class="mod-row" style="margin-top:4px">', unsafe_allow_html=True)
        mod_cols = st.columns(min(len(cat_modules), 6))
        for i, (mk, (icon, lbl)) in enumerate(cat_modules.items()):
            with mod_cols[i]:
                sel = mk in active_mods
                if st.button(f"{icon} {lbl}", key=f"hub_mod_{mk}",
                             type="primary" if sel else "secondary"):
                    mods = set(active_mods)
                    mods.discard(mk) if mk in mods else mods.add(mk)
                    st.session_state.hub_active_mods = mods
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        mods_str = "  ·  ".join(f"{icon} {lbl}" for _, (icon, lbl) in cat_modules.items())
        st.caption(f"Módulos: {mods_str}")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Executar busca ──────────────────────────────────────────────────────
    if search_clicked and raw_query.strip():
        _execute_search(raw_query, active_cat, active_mods, mode)

    # ── Histórico ───────────────────────────────────────────────────────────
    if st.session_state.cases:
        st.markdown("---")
        ch, cc = st.columns([5, 1])
        with ch:
            st.markdown("**📋 Buscas Recentes**")
        with cc:
            if st.button("🗑️ Limpar", key="clear_hist"):
                st.session_state.cases = []
                CASES_FILE.unlink(missing_ok=True)
                st.rerun()
        gcols = st.columns(4)
        for i, case in enumerate(st.session_state.cases[:8]):
            lbl, _ = _risk_label(case["risk_score"])
            badge = "🔴" if lbl=="CRÍTICO" else "🟠" if lbl=="ALTO" else "🟡" if lbl=="MÉDIO" else "🟢"
            with gcols[i % 4]:
                st.markdown(
                    f'<div class="case-card">'
                    f'<div class="case-target">{badge} {case["target"]}</div>'
                    f'<div class="case-meta">{case["target_type"]} · Risk {case["risk_score"]} · {case["timestamp"][:16]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


def _execute_search(
    raw_query: str,
    category: str,
    selected_mods: set[str],
    mode: str,
) -> None:
    """
    Valida o input, monta a config e executa a busca.
    Usa o search_engine.py para toda a lógica — app.py não faz requests diretos.
    """
    # ── Passo 1: validar e sanitizar o input ─────────────────────────────
    validation = validate_query(raw_query)
    if not validation.valid:
        st.error(f"❌ {validation.error}")
        return

    query    = validation.cleaned
    q_type   = validation.query_type
    type_lbl = get_display_label(q_type)

    # ── Passo 2: mostrar o que vai rodar ─────────────────────────────────
    if mode == "Automated":
        config = SearchConfig.auto(q_type)
    else:
        config = SearchConfig.from_manual_selection(selected_mods, q_type)

    if config.total_modules == 0:
        st.warning(f"⚠️ Nenhum módulo é compatível com {type_lbl}. Tente outra categoria ou Automated.")
        return

    # ── Passo 3: feedback visual de progresso com etapas ─────────────────
    # MELHORIA UX: mostra cada módulo que está sendo executado
    st.markdown(f"**Buscando:** `{query}` ({type_lbl}) · {config.total_modules} módulos")

    # ── Passo 2.5: verificar cota ANTES de buscar ─────────────────────────
    guardian = QuotaGuardian.load()
    can_run, quota_msg = guardian.can_run(config)

    if not can_run:
        st.error(quota_msg)
        return
    elif quota_msg:
        st.warning(quota_msg)

    cost = guardian.estimate_cost(config)
    guardian.record_usage(cost)   # registra localmente (API vai confirmar depois)

    progress_bar = st.progress(0, text="Iniciando…")
    status_area  = st.empty()   # área que atualiza o módulo atual

    module_history: list[str] = []   # para mostrar o que já rodou

    def on_progress(pct: int, label: str) -> None:
        progress_bar.progress(pct, text=label)
        module_history.append(label)
        # Mostra os últimos 3 módulos em execução
        recent = " → ".join(module_history[-3:])
        status_area.caption(f"⏱ {recent}")

    # ── Passo 4: executar busca ───────────────────────────────────────────
    if not OATHNET_API_KEY:
        st.error("❌ OATHNET_API_KEY não configurada.")
        return

    try:
        results = _cached_search(query, config) if _cached_search else _fallback_search(query, config)
    except Exception as exc:
        logging.getLogger("nexusosint").error("Search execution failed: %s", exc, exc_info=True)
        st.error(f"❌ Erro durante a busca: {exc}")
        return

    # Limpa os elementos de progresso
    progress_bar.empty()
    status_area.empty()

    # ── Passo 5: salvar e exibir resultados ───────────────────────────────
    st.session_state.search_results = results
    st.session_state.investigation  = {
        "target":      query,
        "target_type": category,
        "timestamp":   __import__("datetime").datetime.now().isoformat(),
    }

    # Sincroniza cota com os dados REAIS da API (mais preciso que o contador local)
    if results.oath_result and results.oath_result.meta:
        guardian.sync_from_api(results.oath_result.meta)
        guardian.save()

    # Salva no histórico se encontrou algo
    if results.has_results:
        _save_case(query, category, results)

    st.rerun()


def _fallback_search(query: str, config: SearchConfig) -> SearchResults:
    """
    Busca sem cache — usada quando _cached_search não está disponível
    (ex: OATHNET_API_KEY não configurada ainda, mas queremos testar a UI).
    """
    from src.core.search_engine import run_search
    return run_search(query, config, OATHNET_API_KEY, on_progress=None)


# ══════════════════════════════════════════════════════════════════════════════
# PÁGINA DE RESULTADOS
# ══════════════════════════════════════════════════════════════════════════════

def _render_results(results: SearchResults) -> None:
    """
    Exibe os resultados inline na mesma página.
    Cada seção é um st.expander colapsável.
    """
    inv     = st.session_state.investigation or {}
    query   = inv.get("target", results.query)
    risk    = results.risk_score
    rl, rc  = _risk_label(risk)
    oath    = results.oath_result
    sherl   = results.sherl_result
    extra   = results.extras
    summary = results.summary()
    inv_ts  = inv.get("timestamp", "")

    # ── Header do relatório ────────────────────────────────────────────────
    st.markdown(f"""
    <div style="margin:8px 0 16px;padding-bottom:12px;border-bottom:1px solid #30363d">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
        <div>
          <span style="font-size:1.35rem;font-weight:800;color:#e6edf3">Search Report</span>
          <span style="color:#8b949e;font-size:.85rem;margin-left:10px">
            Information found for <b style="color:#e6edf3">"{query}"</b>
            · {results.elapsed_s}s
          </span>
        </div>
        <span style="background:{rc}20;border:1px solid {rc};color:{rc};
              padding:4px 12px;border-radius:6px;font-size:.8rem;font-weight:700">
          Risk {risk} — {rl}
        </span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Metric cards COM DELTA (melhoria enterprise) ───────────────────────
    # Delta mostra o significado do número, não só o número em si
    with st.expander("📋 Search Summary", expanded=True):
        c1, c2, c3, c4, c5 = st.columns(5)

        # Cada metric card tem um "delta" que explica o nível de risco
        # ANTES: st.metric("Breaches", 95)  ← sem contexto
        # AGORA: st.metric("Breaches", 95, delta="⚠ Alto risco") ← com contexto
        c1.metric("Total", sum(summary.values()))
        c2.metric(
            "🔓 Breaches", summary["breaches"],
            delta = "⚠ Alto risco" if summary["breaches"] > 10 else ("OK" if summary["breaches"] == 0 else "Atenção"),
            delta_color = "inverse" if summary["breaches"] > 10 else "normal",
        )
        c3.metric(
            "🦠 Stealer", summary["stealers"],
            delta = "🚨 Dispositivo comprometido" if summary["stealers"] > 0 else "Limpo",
            delta_color = "inverse" if summary["stealers"] > 0 else "normal",
        )
        c4.metric(
            "🌐 Social", summary["social"],
            delta = f"em {sherl.total_checked if sherl else 0} plataformas",
        )
        c5.metric("📧 Holehe", summary["holehe"])

        if oath and oath.meta.plan:
            st.caption(
                f"🔑 Plano: {oath.meta.plan} · "
                f"{oath.meta.used_today} lookups usados · "
                f"{oath.meta.left_today} restantes"
            )

        # Erros de módulos (se houver) — visível mas não assustador
        if results.errors:
            with st.expander(f"⚠️ {len(results.errors)} módulo(s) com falha"):
                for mod, err in results.errors.items():
                    st.caption(f"**{mod}**: {err[:100]}")

    # ── Exportar ───────────────────────────────────────────────────────────
    with st.expander("📤 Exportar Relatório"):
        ts      = inv_ts or __import__("datetime").datetime.now().isoformat()
        ts_safe = ts[:10]
        q_safe  = re.sub(r"[^a-zA-Z0-9_\-@.]", "_", query)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**🌐 HTML (dark-mode)**")
            if st.button("⚙️ Gerar HTML", key="exp_html"):
                with st.spinner("Gerando…"):
                    try:
                        html_bytes = generate_html(
                            query, inv.get("target_type",""),
                            oath, sherl, risk, ts
                        ).encode()
                        st.session_state["_html_cache"] = html_bytes
                        st.success("✅ Pronto!")
                    except Exception as e:
                        st.error(str(e))
            if st.session_state.get("_html_cache"):
                st.download_button("⬇️ Baixar HTML", data=st.session_state["_html_cache"],
                                   file_name=f"nexus_{q_safe}_{ts_safe}.html",
                                   mime="text/html", use_container_width=True)

        with col2:
            st.markdown("**📄 PDF (profissional)**")
            if st.button("⚙️ Gerar PDF", key="exp_pdf"):
                with st.spinner("Gerando…"):
                    try:
                        pdf = generate_pdf(query, inv.get("target_type",""), oath, sherl, risk, ts)
                        st.session_state["_pdf_cache"] = pdf
                        st.success("✅ Pronto!")
                    except Exception as e:
                        st.error(str(e))
            if st.session_state.get("_pdf_cache"):
                st.download_button("⬇️ Baixar PDF", data=st.session_state["_pdf_cache"],
                                   file_name=f"nexus_{q_safe}_{ts_safe}.pdf",
                                   mime="application/pdf", use_container_width=True)

        with col3:
            st.markdown("**📦 JSON / Excel**")
            # JSON direto (sem "gerar" — melhoria UX)
            st.download_button(
                "⬇️ Baixar JSON",
                data=_build_json_export(results, inv),
                file_name=f"nexus_{q_safe}_{ts_safe}.json",
                mime="application/json", use_container_width=True,
            )

    # ── Data Breaches ──────────────────────────────────────────────────────
    if oath and oath.breaches:
        _render_breach_section(oath, inv_ts)
    elif oath and oath.success:
        st.markdown('<div class="alert-success">✅ Nenhum breach encontrado.</div>', unsafe_allow_html=True)

    # ── Stealer Logs ───────────────────────────────────────────────────────
    if oath and oath.stealers:
        _render_stealer_section(oath, inv_ts)

    # ── Redes Sociais (Sherlock) ───────────────────────────────────────────
    if sherl and sherl.found:
        _render_social_section(sherl, inv_ts)

    # ── Email / Holehe ─────────────────────────────────────────────────────
    if oath and oath.holehe_domains:
        _render_holehe_section(oath, inv_ts)

    # ── Extras ─────────────────────────────────────────────────────────────
    _render_extras(extra, query)

    # ── Raw JSON ───────────────────────────────────────────────────────────
    with st.expander("🔬 Raw API Response"):
        st.json(oath.raw_response if oath and oath.raw_response else {"_note": "sem dados brutos"})


# ── Seções de resultado (cada uma separada para legibilidade) ─────────────────

def _render_breach_section(oath: OathnetResult, inv_ts: str) -> None:
    import pandas as pd
    n = oath.breach_count
    with st.expander(f"🔓 Data Breaches — {n} encontrados", expanded=True):
        PAGE = 10
        total  = len(oath.breaches)
        max_pg = max(0, (total - 1) // PAGE)
        pg     = st.session_state.get("breach_page", 0)
        if pg > max_pg: pg = 0
        slc    = oath.breaches[pg*PAGE : pg*PAGE+PAGE]

        has_discord = any(b.discord_id for b in slc)
        has_pass    = any(b.password   for b in slc)

        rows = []
        for b in slc:
            row = {"DB": b.dbname, "Email": b.email, "Username": b.username}
            if has_discord: row["Discord ID"] = b.discord_id
            if has_pass:    row["Senha"] = b.password[:25] + "…" if len(b.password) > 25 else b.password
            row["País"] = b.country
            row["Data"] = b.date[:10] if b.date else ""
            for k, v in b.extra_fields.items():
                if v: row[k] = str(v)[:30]
            rows.append(row)

        st.caption(f"Mostrando {pg*PAGE+1}–{min(pg*PAGE+PAGE, total)} de {total}")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if max_pg > 0:
            pc1, pc2, pc3 = st.columns([1, 3, 1])
            with pc1:
                if st.button("◀", key="pg_prev", disabled=pg==0):
                    st.session_state.breach_page = pg - 1
                    st.rerun()
            with pc2:
                st.caption(f"Página {pg+1} de {max_pg+1}")
            with pc3:
                if st.button("▶", key="pg_next", disabled=pg>=max_pg):
                    st.session_state.breach_page = pg + 1
                    st.rerun()

        # Texto formatado para copiar
        lines = []
        for b in oath.breaches:
            lines += ["=== INTELLIGENCE ===", f"Found via     NexusOSINT",
                      f"Date:         {inv_ts}", f"Database:     {b.dbname}", f"Source:       Security Breach"]
            if b.email:      lines.append(f"Email:        {b.email}")
            if b.username:   lines.append(f"Username:     {b.username}")
            if b.password:   lines.append(f"Password:     {b.password}")
            if b.ip:         lines.append(f"IP:           {b.ip}")
            if b.country:    lines.append(f"Country:      {b.country}")
            if b.discord_id: lines.append(f"Discord ID:   {b.discord_id}")
            for k, v in b.extra_fields.items():
                if v: lines.append(f"{k:<13} {v}")
            lines.append("=== END ===\n")
        with st.expander("📋 Copiar texto formatado"):
            st.text_area("Ctrl+A → Ctrl+C:", value="\n".join(lines),
                         height=200, key="breach_copy", label_visibility="collapsed")


def _render_stealer_section(oath: OathnetResult, inv_ts: str) -> None:
    import pandas as pd
    n = oath.stealer_count
    with st.expander(f"⚠️ Stolen Information — {n} credenciais de malware", expanded=True):
        st.markdown('<div class="alert-danger">Um dispositivo associado pode estar comprometido.</div>',
                    unsafe_allow_html=True)
        df = pd.DataFrame([{
            "URL":      (s.url or "")[:55],
            "Username": s.username,
            "Domínio":  ", ".join((s.domain or [])[:2]) or "—",
            "Data":     (s.pwned_at or "")[:10],
        } for s in oath.stealers])
        st.dataframe(df, use_container_width=True, hide_index=True)

        lines = []
        for s in oath.stealers:
            lines += ["=== STEALER LOG ===", f"Found via     NexusOSINT",
                      f"Date:         {inv_ts}", f"Log ID:       {s.log_id}", f"URL:          {s.url}"]
            if s.username: lines.append(f"Username:     {s.username}")
            if s.password: lines.append(f"Password:     {s.password}")
            if s.domain:   lines.append(f"Domain:       {', '.join(s.domain[:3])}")
            lines.append("=== END ===\n")
        with st.expander("📋 Copiar texto formatado"):
            st.text_area("Ctrl+A → Ctrl+C:", value="\n".join(lines),
                         height=200, key="stealer_copy", label_visibility="collapsed")


def _render_social_section(sherl: SherlockResult, inv_ts: str) -> None:
    import pandas as pd
    n = sherl.found_count
    with st.expander(f"🌐 Redes Sociais — {n} perfis encontrados", expanded=True):
        badges = "".join(
            f'<a href="{p.url}" target="_blank" style="text-decoration:none">'
            f'<span class="platform-found">{p.icon} {p.platform}</span></a>'
            for p in sherl.found
        )
        st.markdown(badges, unsafe_allow_html=True)
        st.markdown("")
        df = pd.DataFrame([{"Plataforma": p.platform, "URL": p.url, "Categoria": p.category}
                           for p in sherl.found])
        st.dataframe(df, use_container_width=True, hide_index=True)

        lines = ["=== SOCIAL PROFILES ===", f"Found via     NexusOSINT",
                 f"Date:         {inv_ts}", f"Total:        {n}", ""]
        for p in sherl.found:
            lines += [f"Platform:     {p.platform}", f"URL:          {p.url}",
                      f"Category:     {p.category}", ""]
        lines.append("=== END ===")
        with st.expander("📋 Copiar texto formatado"):
            st.text_area("Ctrl+A → Ctrl+C:", value="\n".join(lines),
                         height=200, key="social_copy", label_visibility="collapsed")


def _render_holehe_section(oath: OathnetResult, inv_ts: str) -> None:
    n = len(oath.holehe_domains)
    with st.expander(f"📧 Email Intelligence — {n} serviços detectados"):
        badges = "".join(f'<span class="platform-found">📌 {d}</span>' for d in oath.holehe_domains)
        st.markdown(badges, unsafe_allow_html=True)
        lines = ["=== EMAIL INTELLIGENCE ===", f"Found via     NexusOSINT",
                 f"Date:         {inv_ts}", f"Total:        {n}", ""]
        for d in oath.holehe_domains:
            lines.append(f"Service:      {d}")
        lines.append("\n=== END ===")
        with st.expander("📋 Copiar texto formatado"):
            st.text_area("Ctrl+A → Ctrl+C:", value="\n".join(lines),
                         height=150, key="holehe_copy", label_visibility="collapsed")


def _render_extras(extra: dict, query: str) -> None:
    """Renderiza resultados extras (IP, Discord, Gaming, Subdomínios)."""
    import pandas as pd

    if extra.get("ip_info", {}).get("ok"):
        with st.expander("🌐 Network — IP Info"):
            d = extra["ip_info"]["data"] or {}
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("País",      f"{d.get('country','—')} ({d.get('countryCode','—')})")
            c2.metric("Cidade",    d.get("city", "—"))
            c3.metric("ISP",       (d.get("isp") or "—")[:22])
            c4.metric("Proxy/VPN", "⚠️ Sim" if d.get("proxy") else "Não")

    if extra.get("discord", {}).get("user", {}).get("ok"):
        with st.expander("🎮 Discord Profile"):
            d = extra["discord"]["user"]["data"] or {}
            ca, cb = st.columns([1, 4])
            with ca:
                if d.get("avatar_url"):
                    st.image(d["avatar_url"], width=64)
            with cb:
                st.markdown(f"**{d.get('global_name') or d.get('username','—')}** `@{d.get('username','—')}`")
                st.caption(f"ID: `{d.get('id','—')}` · Criado: `{d.get('creation_date','—')}`")

    for plat, icon in [("steam","🎮"), ("xbox","🕹️"), ("roblox","🧱")]:
        p = extra.get(plat, {})
        if p.get("ok") and p.get("data"):
            with st.expander(f"{icon} {plat.capitalize()}"):
                d = p["data"]
                ca, cb = st.columns([1, 4])
                with ca:
                    if d.get("avatar"):
                        st.image(d["avatar"], width=64)
                with cb:
                    st.markdown(f"**{d.get('username','—')}**")

    if extra.get("subdomains", {}).get("ok"):
        subs = extra["subdomains"].get("data", [])
        if subs:
            with st.expander(f"🔗 Subdomínios ({len(subs)})"):
                c1, c2 = st.columns([5, 1])
                with c2:
                    st.download_button("⬇️ .txt", data="\n".join(subs),
                                       file_name=f"subs_{query}.txt", mime="text/plain")
                st.dataframe(pd.DataFrame({"Subdomínio": subs[:50]}),
                             use_container_width=True, hide_index=True)


def _build_json_export(results: SearchResults, inv: dict) -> str:
    """Gera o JSON de export diretamente do SearchResults."""
    import json
    from datetime import datetime

    payload = {
        "meta": {
            "tool": "NexusOSINT", "version": APP_VERSION,
            "exported_at": datetime.now().isoformat(),
        },
        "investigation": inv,
        "risk_score":    results.risk_score,
        "summary":       results.summary(),
    }

    oath = results.oath_result
    if oath:
        payload["breaches"] = [
            {"dbname": b.dbname, "email": b.email, "username": b.username,
             "password": b.password, "ip": b.ip, "country": b.country, "date": b.date}
            for b in oath.breaches
        ]
        payload["stealers"] = [
            {"url": s.url, "username": s.username, "domain": s.domain, "pwned_at": s.pwned_at}
            for s in oath.stealers
        ]
        payload["holehe_domains"] = oath.holehe_domains

    sherl = results.sherl_result
    if sherl:
        payload["social_profiles"] = [
            {"platform": p.platform, "url": p.url, "category": p.category}
            for p in sherl.found
        ]

    return json.dumps(payload, indent=2, default=str)


# ══════════════════════════════════════════════════════════════════════════════
# OWNER DEBUG (URL: ?debug=owner)
# ══════════════════════════════════════════════════════════════════════════════

def _render_owner_debug() -> None:
    """
    Painel de diagnóstico visível APENAS via ?debug=owner na URL.
    Outros usuários nunca veem isso.
    """
    import platform as _platform
    import sys

    st.markdown("## 🔧 Owner Debug Panel")
    st.caption("Acesse via `?debug=owner` na URL.")
    st.markdown("---")

    key_display = OATHNET_API_KEY[:8] + "..." + OATHNET_API_KEY[-4:] if OATHNET_API_KEY else "❌ NÃO DEFINIDA"
    st.code(f"OATHNET_API_KEY = {key_display}\nBASE_URL = {OATHNET_BASE_URL}\nAPP_VERSION = {APP_VERSION}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔌 Testar Conexão OathNet", key="dbg_conn"):
            try:
                client = OathnetClient(api_key=OATHNET_API_KEY)
                ok, msg = client.validate_key()
                st.success(f"✅ {msg}") if ok else st.error(f"❌ {msg}")
            except Exception as e:
                st.error(f"❌ {e}")
    with col2:
        if st.button("📡 Ping Raw", key="dbg_ping"):
            import requests
            try:
                r = requests.get(OATHNET_BASE_URL, headers={"x-api-key": OATHNET_API_KEY}, timeout=8)
                st.info(f"HTTP {r.status_code} · {len(r.content)} bytes · {r.elapsed.total_seconds():.2f}s")
            except Exception as e:
                st.error(f"❌ {e}")

    st.markdown("---")
    st.markdown("**Session State**")
    safe = {k: v for k, v in st.session_state.items()
            if k not in ("oath_result", "sherl_result", "search_results")}
    st.json(safe, expanded=False)

    st.markdown("**Ambiente**")
    st.json({"python": sys.version, "platform": _platform.platform(),
             "streamlit": st.__version__, "api_key_ok": bool(OATHNET_API_KEY)})


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def _inject_css() -> None:
    """Injeta o CSS dark-mode uma única vez."""
    st.markdown(_DARK_CSS, unsafe_allow_html=True)


def main() -> None:
    """
    Ponto de entrada principal — apenas 3 responsabilidades:
      1. Inicializar estado
      2. Verificar acesso
      3. Renderizar a página certa
    """
    _inject_css()
    _init_state()

    # Owner debug via URL param
    try:
        if st.query_params.get("debug") == "owner":
            _render_owner_debug()
            return
    except Exception:
        pass

    # Password gate
    if not _check_password():
        return

    # Hub de busca (sempre visível no topo)
    _render_hub()

    # Resultados (aparecem logo abaixo quando há uma busca ativa)
    results: Optional[SearchResults] = st.session_state.get("search_results")
    if results is not None:
        _render_results(results)


if __name__ == "__main__":
    main()