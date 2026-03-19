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
    except OSError as _log_err:
        print(f"[nexusosint] Could not create log file: {_log_err}")  # sem logger ainda

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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Hide Streamlit chrome ── */
[data-testid="stSidebar"]        { display:none!important; }
[data-testid="collapsedControl"] { display:none!important; }
header[data-testid="stHeader"]   { display:none!important; }
.stMainBlockContainer            { max-width:100%!important; padding:0!important; }
footer                           { display:none!important; }

/* ── Design tokens ── */
:root {
  --bg:      #0b0c14;
  --bg2:     #10111d;
  --bg3:     #16172a;
  --bg4:     #1e2035;
  --border:  rgba(255,255,255,.07);
  --border2: rgba(255,255,255,.12);
  --purple:  #7b68ee;
  --purple2: #6255d3;
  --purple-glow: rgba(123,104,238,.3);
  --accent:  #7b68ee;
  --bg4:     #1e2035;
  --text:    #f0f0f8;
  --text2:   #8a8aaa;
  --text3:   #555575;
  --red:     #ff4f4f;
  --orange:  #ff8c42;
  --green:   #3ecf8e;
  --yellow:  #ffc84a;
  --r:       14px;
  --r-sm:    8px;
}

html, body, [data-testid="stApp"] {
  background: var(--bg)!important;
  color: var(--text)!important;
  font-family: 'Inter', -apple-system, sans-serif!important;
  font-size: 14px;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width:6px; height:6px; }
::-webkit-scrollbar-track { background:var(--bg2); }
::-webkit-scrollbar-thumb { background:var(--bg4); border-radius:3px; }

/* ── Metrics ── */
[data-testid="stMetric"] {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  padding: 16px 20px;
  transition: border-color .2s;
}
[data-testid="stMetric"]:hover { border-color: var(--border2); }
[data-testid="stMetricValue"]  { color: var(--text)!important; font-size:1.6rem!important; font-weight:700!important; letter-spacing:-.02em; }
[data-testid="stMetricLabel"]  { color: var(--text2)!important; font-size:.7rem!important; text-transform:uppercase; letter-spacing:.08em; font-weight:600; }
[data-testid="stMetricDelta"]  { font-size:.72rem!important; }

/* ── DataFrames ── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--border)!important;
  border-radius: var(--r-sm)!important;
  overflow: hidden;
}

/* ── Expanders ── */
[data-testid="stExpander"] {
  background: var(--bg2)!important;
  border: 1px solid var(--border)!important;
  border-radius: var(--r)!important;
  margin: 6px 0!important;
  overflow: hidden;
}
[data-testid="stExpander"]:hover { border-color: var(--border2)!important; }
[data-testid="stExpander"] summary {
  padding: 12px 16px!important;
  font-weight: 600!important;
  font-size: .88rem!important;
  color: var(--text)!important;
}

/* ── Text inputs ── */
.stTextInput input {
  background: var(--bg3)!important;
  border: 1px solid var(--border2)!important;
  border-radius: var(--r-sm)!important;
  color: var(--text)!important;
  font-size: 15px!important;
  padding: 12px 16px!important;
  transition: all .2s;
}
.stTextInput input:focus {
  border-color: var(--purple)!important;
  box-shadow: 0 0 0 3px var(--purple-glow)!important;
  outline: none!important;
}
.stTextInput input::placeholder { color: var(--text3)!important; }

/* ── Buttons ── */
.stButton > button {
  background: var(--bg4)!important;
  border: 1px solid var(--border2)!important;
  color: var(--text2)!important;
  border-radius: var(--r-sm)!important;
  font-size: .82rem!important;
  font-weight: 500!important;
  transition: all .15s!important;
  font-family: inherit!important;
}
.stButton > button:hover {
  border-color: var(--purple)!important;
  color: var(--text)!important;
  background: rgba(123,104,238,.1)!important;
}
.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, var(--purple), var(--purple2))!important;
  border: none!important;
  color: #fff!important;
  font-weight: 600!important;
  box-shadow: 0 4px 20px var(--purple-glow)!important;
}
.stButton > button[kind="primary"]:hover {
  box-shadow: 0 6px 28px var(--purple-glow)!important;
  filter: brightness(1.08)!important;
  color: #fff!important;
}

/* ── Category pills ── */
div.cat-row div[data-testid="stButton"] button {
  border-radius: 999px!important;
  padding: 5px 16px!important;
  font-size: .8rem!important;
  height: auto!important;
  min-height: 0!important;
  letter-spacing: .01em;
}
div.cat-row div[data-testid="stButton"] button[kind="primary"] {
  background: rgba(123,104,238,.15)!important;
  border: 1px solid var(--purple)!important;
  color: #a89af0!important;
  font-weight: 600!important;
  box-shadow: none!important;
}
div.mod-row div[data-testid="stButton"] button {
  border-radius: var(--r-sm)!important;
  padding: 4px 12px!important;
  font-size: .76rem!important;
  height: auto!important;
  min-height: 0!important;
}
div.mod-row div[data-testid="stButton"] button[kind="primary"] {
  background: rgba(123,104,238,.12)!important;
  border: 1px solid var(--purple)!important;
  color: #a89af0!important;
  box-shadow: none!important;
}

/* ── Radio toggle pill ── */
div[data-testid="stRadio"] > div {
  display: inline-flex!important;
  flex-direction: row!important;
  gap: 0!important;
  background: var(--bg4)!important;
  border: 1px solid var(--border2)!important;
  border-radius: 999px!important;
  padding: 3px!important;
}
div[data-testid="stRadio"] label { margin:0!important; cursor:pointer; }
div[data-testid="stRadio"] label > div:first-child { display:none!important; }
div[data-testid="stRadio"] label span {
  display:block!important;
  padding: 6px 20px!important;
  border-radius: 999px!important;
  font-size: .82rem!important;
  font-weight: 500!important;
  color: var(--text2)!important;
  background: transparent!important;
  border: none!important;
  transition: all .15s!important;
}
div[data-testid="stRadio"] label:has(input:checked) span {
  background: var(--purple)!important;
  color: #fff!important;
  font-weight: 600!important;
  box-shadow: 0 2px 8px var(--purple-glow)!important;
  min-width: 90px;
  text-align: center;
}

/* ── Alerts ── */
hr { border-color: var(--border)!important; }
.platform-found {
  display:inline-flex; align-items:center; gap:4px;
  background: rgba(62,207,142,.08); border: 1px solid rgba(62,207,142,.25);
  color: var(--green); border-radius:6px; padding:3px 9px;
  font-size:.74rem; margin:2px; font-weight:500;
}
.alert-success { background:rgba(62,207,142,.07); border:1px solid rgba(62,207,142,.2); border-radius:var(--r-sm); padding:12px 16px; color:var(--green); margin:6px 0; }
.alert-danger  { background:rgba(255,79,79,.07); border:1px solid rgba(255,79,79,.2); border-radius:var(--r-sm); padding:12px 16px; color:var(--red); margin:6px 0; }
.alert-warning { background:rgba(255,140,66,.07); border:1px solid rgba(255,140,66,.2); border-radius:var(--r-sm); padding:12px 16px; color:var(--orange); margin:6px 0; }
.alert-info    { background:rgba(123,104,238,.07); border:1px solid rgba(123,104,238,.2); border-radius:var(--r-sm); padding:12px 16px; color:#a89af0; margin:6px 0; }

/* ── Case / history cards ── */
.case-card {
  background: var(--bg3); border: 1px solid var(--border);
  border-radius: var(--r-sm); padding: 12px 14px; margin: 4px 0;
  cursor: pointer; transition: all .15s;
}
.case-card:hover { border-color: var(--purple); background: var(--bg4); }
.case-target { font-weight: 600; color: var(--text); font-size:.88rem; }
.case-meta   { font-size: .7rem; color: var(--text3); margin-top: 3px; }

/* ══════════════════════════════════════════════
   HUB LAYOUT
══════════════════════════════════════════════ */
.hub-page {
  min-height: 100vh;
  background:
    radial-gradient(ellipse 80% 50% at 50% -10%, rgba(123,104,238,.18), transparent),
    radial-gradient(ellipse 60% 40% at 80% 80%, rgba(100,80,220,.08), transparent),
    var(--bg);
}
.hub-wrap {
  max-width: 680px;
  margin: 0 auto;
  padding: 0 20px 60px;
}
.hub-logo {
  text-align: center;
  padding: 28px 0 20px;
}
.hub-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(123,104,238,.1);
  border: 1px solid rgba(123,104,238,.25);
  border-radius: 999px;
  padding: 5px 14px;
  font-size: .74rem;
  font-weight: 600;
  color: #a89af0;
  letter-spacing: .04em;
  margin-bottom: 18px;
}
.hub-logo h1 {
  font-size: 2rem;
  font-weight: 800;
  color: var(--text);
  letter-spacing: -.03em;
  margin: 0 0 8px;
  line-height: 1.1;
}
.hub-logo p {
  color: var(--text2);
  font-size: .9rem;
  margin: 0;
  font-weight: 400;
}

/* Search card */
.hub-card {
  background: rgba(16,17,29,.7);
  border: 1px solid var(--border2);
  border-radius: 18px;
  padding: 20px 24px;
  backdrop-filter: blur(20px);
  box-shadow:
    0 0 0 1px rgba(255,255,255,.03) inset,
    0 20px 60px rgba(0,0,0,.5),
    0 0 80px rgba(123,104,238,.05);
  margin-bottom: 20px;
}

/* Section dividers for results */
.results-page { max-width: 100%; padding: 0 20px 60px; }

.report-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 20px 0 16px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 20px;
}
.report-title { font-size: 1.4rem; font-weight: 800; color: var(--text); letter-spacing: -.02em; }
.report-sub   { color: var(--text2); font-size: .85rem; margin-top: 2px; }
.risk-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  border-radius: 999px;
  font-size: .82rem;
  font-weight: 700;
  letter-spacing: .02em;
}

/* Section cards (breach, stealer, social) */
.section-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: var(--r);
  overflow: hidden;
  margin: 8px 0;
  transition: border-color .2s;
}
.section-card:hover { border-color: var(--border2); }
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  background: var(--bg3);
  border-bottom: 1px solid var(--border);
  cursor: pointer;
}
.section-title { font-weight: 600; font-size: .9rem; color: var(--text); }
.section-count {
  background: rgba(123,104,238,.12);
  border: 1px solid rgba(123,104,238,.2);
  color: #a89af0;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: .74rem;
  font-weight: 700;
}

/* Stat row inline */
.stat-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
  margin: 12px 0;
}
.stat-cell {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  padding: 14px 16px;
  text-align: center;
}
.stat-value { font-size: 1.6rem; font-weight: 700; color: var(--text); letter-spacing: -.02em; }
.stat-label { font-size: .68rem; color: var(--text2); text-transform: uppercase; letter-spacing: .07em; font-weight: 600; margin-top: 3px; }
.stat-delta { font-size: .7rem; margin-top: 4px; }

/* History section */
.history-title {
  font-size: .7rem;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: var(--text3);
  font-weight: 700;
  margin: 28px 0 8px;
}

/* Export row */
.export-btn-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
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
    CATEGORIES = {
        "Data Leaks":         {"icon": "🛡️", "modules": {"breaches": ("🔓","Breaches"), "stealer": ("📋","Stealer Logs")}},
        "Social & Gaming":    {"icon": "🎮", "modules": {"sherlock": ("🌐","Sherlock"), "discord": ("💬","Discord"), "steam": ("🎮","Steam"), "xbox": ("🕹️","Xbox"), "roblox": ("🧱","Roblox")}},
        "Email Intelligence": {"icon": "📧", "modules": {"holehe": ("📨","Holehe"), "ghunt": ("🔍","GHunt")}},
        "Network":            {"icon": "🌐", "modules": {"ip_info": ("📍","IP Info"), "subdomain": ("🔗","Subdomínios")}},
        "SpiderFoot":         {"icon": "🕷️", "modules": {"spiderfoot": ("🕷️","SpiderFoot")}},
    }

    # ── Logo ────────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="hub-wrap">'
        '<div class="hub-logo">'
        '<div class="hub-badge">⬡ NEXUSOSINT</div>'
        '<h1>Investigate any data,<br>instantly.</h1>'
        '<p>Run targeted lookups across breaches, social profiles, gaming accounts,<br>'
        'emails and network infrastructure — all in one place.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Card único: quota + input + toggle + categorias ─────────────────────
    st.markdown('<div class="hub-card">', unsafe_allow_html=True)

    # Quota widget
    QuotaGuardian.load().render_widget()

    # Input + botão Search
    c1, c2 = st.columns([6, 1])
    with c1:
        raw_query = st.text_input(
            "Buscar",
            placeholder="username · email · IP · Discord ID · domínio…",
            key="hub_query_input",
            label_visibility="collapsed",
        )
    with c2:
        search_clicked = st.button("Search →", key="hub_search_btn",
                                   type="primary", use_container_width=True)

    # Toggle Automated / Manual
    mode = st.radio("", ["Automated", "Manual"],
                    horizontal=True, key="hub_mode", label_visibility="collapsed")

    # ── Manual: categorias e módulos dentro do card ─────────────────────────
    active_cat  = st.session_state.get("hub_active_cat", "Data Leaks")
    active_mods = st.session_state.get("hub_active_mods", {"breaches", "stealer"})

    if mode == "Manual":
        st.markdown(
            '<div style="height:1px;background:var(--border);margin:12px -24px;"></div>'
            '<div style="color:var(--text3);font-size:.7rem;text-transform:uppercase;'
            'letter-spacing:.1em;font-weight:700;margin-bottom:8px">Categoria</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="cat-row">', unsafe_allow_html=True)
        cat_cols = st.columns(len(CATEGORIES))
        for i, (cat_name, cat_data) in enumerate(CATEGORIES.items()):
            with cat_cols[i]:
                if st.button(
                    f"{cat_data['icon']} {cat_name}",
                    key=f"hub_cat_{cat_name}",
                    type="primary" if cat_name == active_cat else "secondary",
                    use_container_width=True,
                ):
                    st.session_state.hub_active_cat  = cat_name
                    st.session_state.hub_active_mods = set(cat_data["modules"].keys())
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        cat_modules = CATEGORIES[active_cat]["modules"]
        st.markdown(
            '<div style="color:var(--text3);font-size:.7rem;text-transform:uppercase;'
            'letter-spacing:.1em;font-weight:700;margin:10px 0 6px">Módulos</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="mod-row">', unsafe_allow_html=True)
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

    st.markdown('</div>', unsafe_allow_html=True)  # hub-card

    # ── Executar busca ──────────────────────────────────────────────────────
    if search_clicked and raw_query.strip():
        _execute_search(raw_query, active_cat, active_mods, mode)

    # ── Histórico ───────────────────────────────────────────────────────────
    if st.session_state.cases:
        st.markdown('<p class="history-title">Buscas Recentes</p>', unsafe_allow_html=True)
        ch, cc = st.columns([5, 1])
        with cc:
            if st.button("Limpar", key="clear_hist"):
                st.session_state.cases = []
                CASES_FILE.unlink(missing_ok=True)
                st.rerun()
        gcols = st.columns(4)
        for i, case in enumerate(st.session_state.cases[:8]):
            lbl, color = _risk_label(case["risk_score"])
            with gcols[i % 4]:
                st.markdown(
                    f'<div class="case-card">'
                    f'<div class="case-target">{case["target"]}</div>'
                    f'<div class="case-meta" style="margin-top:4px">'
                    f'<span style="color:{color};font-weight:600">{lbl}</span>'
                    f' · {case["risk_score"]} · {case["timestamp"][:16]}'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

    st.markdown('</div>', unsafe_allow_html=True)  # hub-wrap



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

    # ── Passo 2.5: verificar cota ANTES de buscar ────────────────────────
    # SpiderFoot não usa OathNet — só verifica cota se há módulos OathNet
    needs_oathnet = any([
        config.run_breach, config.run_stealer, config.run_holehe,
        config.run_ghunt, config.run_ip, config.run_discord,
        config.run_steam, config.run_xbox, config.run_roblox, config.run_subdomain,
    ])

    if needs_oathnet:
        if not OATHNET_API_KEY:
            st.error("❌ OATHNET_API_KEY não configurada. Configure em Settings → Secrets.")
            return
        guardian = QuotaGuardian.load()
        can_run, quota_msg = guardian.can_run(config)
        if not can_run:
            st.error(quota_msg)
            return
        elif quota_msg:
            st.warning(quota_msg)
        cost = guardian.estimate_cost(config)
        guardian.record_usage(cost)
    else:
        guardian = None  # SpiderFoot only — sem cota OathNet

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
    try:
        results = _cached_search(query, config) if (_cached_search and needs_oathnet) else _fallback_search(query, config)
    except Exception as exc:
        logging.getLogger("nexusosint").error("Search execution failed: %s", exc, exc_info=True)
        st.error(f"❌ Erro durante a busca: {exc}")
        return

    # Limpa os elementos de progresso
    progress_bar.empty()
    status_area.empty()

    # ── Passo 5: salvar e exibir resultados ───────────────────────────────
    st.session_state.search_results   = results
    st.session_state.spiderfoot_result = results.sf_result
    st.session_state.investigation    = {
        "target":      query,
        "target_type": category,
        "timestamp":   __import__("datetime").datetime.now().isoformat(),
    }

    # Sincroniza cota com os dados REAIS da API (só se usou OathNet)
    if guardian and results.oath_result and results.oath_result.meta:
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
    import pandas as pd
    import re as _re

    inv     = st.session_state.investigation or {}
    query   = inv.get("target", results.query)
    risk    = results.risk_score
    rl, rc  = _risk_label(risk)
    oath    = results.oath_result
    sherl   = results.sherl_result
    extra   = results.extras
    summary = results.summary()
    inv_ts  = inv.get("timestamp", "")
    ts_safe = inv_ts[:10] if inv_ts else ""
    q_safe  = _re.sub(r"[^a-zA-Z0-9_\-@.]", "_", query)

    # ── Search Report header ───────────────────────────────────────────────
    st.markdown(
        f'<div class="results-page">'
        f'<div class="report-header">'
        f'<div>'
        f'  <div class="report-title">Search Report</div>'
        f'  <div class="report-sub">Information found for <b style="color:var(--text)">{query}</b>'
        f'  · {results.elapsed_s}s</div>'
        f'</div>'
        f'<span class="risk-badge" style="background:{rc}18;border:1px solid {rc}55;color:{rc}">'
        f'  {risk} — {rl}'
        f'</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Stat row (OathNet style — sem expander, direto) ────────────────────
    n_breach  = summary["breaches"]
    n_stealer = summary["stealers"]
    n_social  = summary["social"]
    n_holehe  = summary["holehe"]
    n_total   = n_breach + n_stealer + n_social + n_holehe

    def _delta_color(val: int, inverse: bool = False) -> str:
        if val == 0: return "var(--green)"
        return "var(--red)" if not inverse else "var(--orange)"

    st.markdown(f"""
    <div class="stat-row">
      <div class="stat-cell">
        <div class="stat-value">{n_total}</div>
        <div class="stat-label">Total Found</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value" style="color:{'var(--red)' if n_breach>10 else 'var(--orange)' if n_breach>0 else 'var(--green)'}">{n_breach}</div>
        <div class="stat-label">Security Breaches</div>
        <div class="stat-delta" style="color:{'var(--red)' if n_breach>10 else 'var(--orange)' if n_breach>0 else 'var(--green)'}">
          {'⚠ Alto risco' if n_breach>10 else '⚠ Atenção' if n_breach>0 else '✓ Limpo'}
        </div>
      </div>
      <div class="stat-cell">
        <div class="stat-value" style="color:{'var(--red)' if n_stealer>0 else 'var(--green)'}">{n_stealer}</div>
        <div class="stat-label">Stolen Info</div>
        <div class="stat-delta" style="color:{'var(--red)' if n_stealer>0 else 'var(--green)'}">
          {'🚨 Comprometido' if n_stealer>0 else '✓ Limpo'}
        </div>
      </div>
      <div class="stat-cell">
        <div class="stat-value">{n_social}</div>
        <div class="stat-label">Social Profiles</div>
        <div class="stat-delta" style="color:var(--text2)">{sherl.total_checked if sherl else 0} checked</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value">{n_holehe}</div>
        <div class="stat-label">Email Services</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Quota info + erros inline (sem expander extra)
    if oath and oath.meta.plan:
        st.caption(f"🔑 {oath.meta.plan.upper()} · {oath.meta.used_today}/{oath.meta.daily_limit} lookups usados · {oath.meta.left_today} restantes")
    if results.errors:
        errs = " · ".join(f"**{m}**: {e[:40]}" for m, e in results.errors.items())
        st.markdown(f'<div class="alert-warning" style="font-size:.78rem">⚠ {errs}</div>', unsafe_allow_html=True)

    # ── Export inline (sem "gerar primeiro") ─────────────────────────────
    with st.expander("📤 Export Report", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("⚙️ Generate HTML", key="exp_html"):
                with st.spinner("Generating…"):
                    try:
                        h = generate_html(query, inv.get("target_type",""), oath, sherl, risk, inv_ts or "").encode()
                        st.session_state["_html_cache"] = h
                    except Exception as e:
                        st.error(str(e))
            if st.session_state.get("_html_cache"):
                st.download_button("⬇️ HTML", data=st.session_state["_html_cache"],
                                   file_name=f"nexus_{q_safe}_{ts_safe}.html",
                                   mime="text/html", use_container_width=True)
        with col2:
            if st.button("⚙️ Generate PDF", key="exp_pdf"):
                with st.spinner("Generating…"):
                    try:
                        p = generate_pdf(query, inv.get("target_type",""), oath, sherl, risk, inv_ts or "")
                        st.session_state["_pdf_cache"] = p
                    except Exception as e:
                        st.error(str(e))
            if st.session_state.get("_pdf_cache"):
                st.download_button("⬇️ PDF", data=st.session_state["_pdf_cache"],
                                   file_name=f"nexus_{q_safe}_{ts_safe}.pdf",
                                   mime="application/pdf", use_container_width=True)
        with col3:
            st.download_button("⬇️ JSON", data=_build_json_export(results, inv),
                               file_name=f"nexus_{q_safe}_{ts_safe}.json",
                               mime="application/json", use_container_width=True)

    # ── Data Breaches ──────────────────────────────────────────────────────
    if oath and oath.breaches:
        _render_breach_section(oath, inv_ts)
    elif oath and oath.success and not oath.breaches:
        st.markdown('<div class="alert-success">✓ No breaches found for this target.</div>', unsafe_allow_html=True)

    # ── Stealer Logs ───────────────────────────────────────────────────────
    if oath and oath.stealers:
        _render_stealer_section(oath, inv_ts)

    # ── Social (Sherlock) ──────────────────────────────────────────────────
    if sherl and sherl.found:
        _render_social_section(sherl, inv_ts)

    # ── Email / Holehe ─────────────────────────────────────────────────────
    if oath and oath.holehe_domains:
        _render_holehe_section(oath, inv_ts)

    # ── Extras (IP, Discord, Gaming, Subdomains) ───────────────────────────
    _render_extras(extra, query)

    # ── SpiderFoot ────────────────────────────────────────────────────────
    sf = results.sf_result
    if sf is not None:
        from modules.spiderfoot_wrapper import render_spiderfoot_results
        render_spiderfoot_results(sf)

    # ── Raw JSON ───────────────────────────────────────────────────────────
    with st.expander("🔬 Raw API Response"):
        st.json(oath.raw_response if oath and oath.raw_response else {"_note": "no raw data"})

    st.markdown('</div>', unsafe_allow_html=True)  # results-page


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
    _inject_css()
    _init_state()

    try:
        if st.query_params.get("debug") == "owner":
            _render_owner_debug()
            return
    except Exception as _qp_err:
        logging.getLogger("nexusosint").debug("query_params check failed: %s", _qp_err)

    if not _check_password():
        return

    st.markdown('<div class="hub-page">', unsafe_allow_html=True)
    _render_hub()

    results: Optional[SearchResults] = st.session_state.get("search_results")
    if results is not None:
        _render_results(results)

    st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()