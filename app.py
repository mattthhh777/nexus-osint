"""
NexusOSINT — Main Dashboard
Streamlit-powered OSINT investigation dashboard.
"""

from __future__ import annotations

import json
import os
import time
import warnings
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

# Suppress Streamlit deprecation noise in logs
warnings.filterwarnings("ignore", message=".*use_container_width.*")

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from modules.oathnet_client import OathnetClient, OathnetResult, OATHNET_BASE_URL
from modules.sherlock_wrapper import SherlockResult, search_username
from modules.report_generator import generate_html, generate_pdf

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv()

# ── API key: reads from environment / Streamlit secrets ──────────────────────
# In Streamlit Cloud: set via Settings → Secrets (never hardcode here)
# Locally: set in .env file
OATHNET_API_KEY = (
    st.secrets.get("OATHNET_API_KEY", "")          # Streamlit Cloud secrets
    if hasattr(st, "secrets") else ""
) or os.getenv("OATHNET_API_KEY", "")

# ── Debug mode: only visible when DEBUG=true in environment ───────────────────
# Locally you can set DEBUG=true in .env; on Streamlit Cloud leave it unset.
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

CASES_FILE  = Path("cases.json")
APP_VERSION = "1.0.0"

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="NexusOSINT",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Dark-mode theme injection ─────────────────────────────────────────────────

DARK_CSS = """
<style>
    /* ── Global ── */
    :root {
        --bg-primary:    #0d1117;
        --bg-secondary:  #161b22;
        --bg-card:       #1c2128;
        --border:        #30363d;
        --accent-cyan:   #00d4ff;
        --accent-green:  #39d353;
        --accent-red:    #f85149;
        --accent-orange: #f0883e;
        --accent-yellow: #ffd700;
        --text-primary:  #e6edf3;
        --text-muted:    #8b949e;
    }
    html, body, [data-testid="stApp"] {
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
        font-family: 'Consolas', 'Courier New', monospace;
    }
    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background-color: var(--bg-secondary) !important;
        border-right: 1px solid var(--border);
    }
    [data-testid="stSidebar"] * { color: var(--text-primary) !important; }
    /* ── Metric cards ── */
    [data-testid="stMetric"] {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 12px 16px;
    }
    [data-testid="stMetricLabel"] { color: var(--text-muted) !important; font-size: 0.75rem; }
    [data-testid="stMetricValue"] { color: var(--accent-cyan) !important; font-size: 1.6rem; font-weight: 700; }
    /* ── Tabs ── */
    button[data-baseweb="tab"] {
        background: var(--bg-secondary) !important;
        color: var(--text-muted) !important;
        border-bottom: 2px solid transparent !important;
        font-size: 0.85rem;
        letter-spacing: 0.05em;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--accent-cyan) !important;
        border-bottom: 2px solid var(--accent-cyan) !important;
    }
    /* ── DataFrames ── */
    [data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 6px; }
    /* ── Inputs ── */
    .stTextInput input, .stSelectbox select {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        color: var(--text-primary) !important;
        border-radius: 6px !important;
    }
    /* ── Buttons ── */
    .stButton > button {
        background: linear-gradient(135deg, #00d4ff22, #00d4ff11) !important;
        border: 1px solid var(--accent-cyan) !important;
        color: var(--accent-cyan) !important;
        border-radius: 6px !important;
        font-family: 'Consolas', monospace !important;
        letter-spacing: 0.08em;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: var(--accent-cyan) !important;
        color: #000 !important;
    }
    /* ── Dividers / expanders ── */
    hr { border-color: var(--border) !important; }
    [data-testid="stExpander"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
    }
    /* ── Header bar ── */
    .nexus-header {
        background: linear-gradient(90deg, #0d1117 0%, #161b22 100%);
        border-bottom: 1px solid #00d4ff44;
        padding: 12px 0 8px;
        margin-bottom: 20px;
    }
    .nexus-title {
        font-size: 1.8rem;
        font-weight: 900;
        color: #00d4ff;
        letter-spacing: 0.12em;
        text-shadow: 0 0 20px #00d4ff66;
    }
    .nexus-sub { font-size: 0.75rem; color: #8b949e; letter-spacing: 0.15em; }
    /* ── Risk gauge ── */
    .risk-score-wrap {
        display: flex; align-items: center; gap: 12px;
        background: var(--bg-card); border: 1px solid var(--border);
        border-radius: 8px; padding: 16px 20px; margin: 12px 0;
    }
    .risk-circle {
        width: 72px; height: 72px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.4rem; font-weight: 900; border: 3px solid;
        flex-shrink: 0;
    }
    .risk-info { flex: 1; }
    .risk-label { font-size: 0.7rem; color: var(--text-muted); letter-spacing: 0.1em; }
    .risk-verdict { font-size: 1rem; font-weight: 700; }
    /* ── Platform badges ── */
    .platform-found {
        display: inline-block;
        background: #39d35322; border: 1px solid #39d353;
        color: #39d353; border-radius: 4px;
        padding: 2px 8px; font-size: 0.75rem; margin: 2px;
    }
    .platform-notfound {
        display: inline-block;
        background: #8b949e11; border: 1px solid #30363d;
        color: #8b949e; border-radius: 4px;
        padding: 2px 8px; font-size: 0.75rem; margin: 2px;
    }
    /* ── Alert boxes ── */
    .alert-success { background:#39d35315; border:1px solid #39d353; border-radius:6px; padding:10px 14px; color:#39d353; }
    .alert-danger  { background:#f8514915; border:1px solid #f85149; border-radius:6px; padding:10px 14px; color:#f85149; }
    .alert-warning { background:#f0883e15; border:1px solid #f0883e; border-radius:6px; padding:10px 14px; color:#f0883e; }
    .alert-info    { background:#00d4ff15; border:1px solid #00d4ff; border-radius:6px; padding:10px 14px; color:#00d4ff; }
    /* ── Case card ── */
    .case-card {
        background: var(--bg-card); border: 1px solid var(--border);
        border-radius: 6px; padding: 10px 12px; margin: 6px 0;
        cursor: pointer; transition: border-color 0.2s;
    }
    .case-card:hover { border-color: var(--accent-cyan); }
    .case-card-active { border-color: var(--accent-cyan) !important; }
    .case-target { font-weight: 700; color: var(--accent-cyan); font-size: 0.9rem; }
    .case-meta   { font-size: 0.7rem; color: var(--text-muted); }
</style>
"""

st.markdown(DARK_CSS, unsafe_allow_html=True)


# ── Session state bootstrap ───────────────────────────────────────────────────

def _init_state():
    defaults = {
        "investigation":    None,
        "oathnet_result":   None,
        "sherlock_result":  None,
        "cases":            _load_cases(),
        "active_case_id":   None,
        "running":          False,
        "target":           "",
        "target_type":      "Email",
        "prefer_cli":       False,
        "debug_log":        [],
        "breach_page":      0,
        "discord_lookups":  {},
        "authenticated":    False,
        # ── Ferramentas standalone ────────────────────────────────────────
        "tool_ip_result":       None,
        "tool_discord_result":  None,
        "tool_gaming_result":   None,
        "tool_subdomain_result":None,
        "tool_filesearch_result":None,
        "tool_fullsearch_result":None,
        "sidebar_active_tool":   "full",
        "fs_sidebar_run_query":  None,
        "tool_ip_prefill":       None,
        "tool_discord_prefill":  None,
        "tool_gaming_prefill":   None,
        "tool_subdomain_prefill":None,
        # ── Hub state ─────────────────────────────────────────────────────
        "hub_active_cat":    "Data Leaks",
        "hub_active_mods":   {"breaches", "stealer"},
        "hub_extra":         {},   # resultados extras (discord, gaming, ip, etc.)
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v



# ── Password gate ─────────────────────────────────────────────────────────────

def _check_password() -> bool:
    """
    Returns True if the user is authenticated.
    If APP_PASSWORD is not set in secrets/env, auth is disabled (open access).
    """
    app_password = ""
    if hasattr(st, "secrets"):
        app_password = st.secrets.get("APP_PASSWORD", "")
    if not app_password:
        app_password = os.getenv("APP_PASSWORD", "")

    # No password configured → open access
    if not app_password:
        return True

    if st.session_state.authenticated:
        return True

    # Show login screen
    st.markdown(
        """
        <div style="max-width:400px;margin:80px auto;text-align:center">
          <div style="font-size:3rem">⬡</div>
          <h2 style="color:#00d4ff;letter-spacing:.1em">NEXUSOSINT</h2>
          <p style="color:#8b949e">Acesso restrito. Digite a senha para continuar.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col = st.columns([1, 2, 1])[1]
    with col:
        pwd = st.text_input("🔑 Senha", type="password", label_visibility="collapsed",
                            placeholder="Digite a senha de acesso...")
        if st.button("Entrar", use_container_width=True):
            if pwd == app_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Senha incorreta.")
    return False


# ── Discord inline lookup ─────────────────────────────────────────────────────

def _render_discord_card(discord_id: str):
    """Fetch and display a Discord profile inline, with result caching."""
    if not discord_id:
        return

    cache = st.session_state.discord_lookups

    if discord_id not in cache:
        client = OathnetClient(api_key=OATHNET_API_KEY)
        ok, data = client.discord_userinfo(discord_id)
        cache[discord_id] = data if ok else {"error": data.get("error", "Lookup failed")}

    info = cache[discord_id]

    if "error" in info:
        st.caption(f"⚠️ Discord lookup falhou: {info['error']}")
        return

    avatar = info.get("avatar_url", "")
    uname  = info.get("username", "—")
    gname  = info.get("global_name", "")
    created = info.get("creation_date", "")
    badges  = info.get("badges", [])

    cols = st.columns([1, 4])
    with cols[0]:
        if avatar:
            st.image(avatar, width=56)
        else:
            st.markdown('<div style="width:56px;height:56px;background:#30363d;border-radius:50%"></div>',
                        unsafe_allow_html=True)
    with cols[1]:
        st.markdown(
            f'**{gname or uname}** `@{uname}`  \n'
            f'<span style="color:#8b949e;font-size:12px">ID: {discord_id}'
            f'{" · " + created[:10] if created else ""}'
            f'{" · 🏅 " + ", ".join(badges) if badges else ""}</span>',
            unsafe_allow_html=True,
        )




def _load_cases() -> list[dict]:
    if CASES_FILE.exists():
        try:
            return json.loads(CASES_FILE.read_text())
        except Exception:
            return []
    return []


def _save_cases():
    CASES_FILE.write_text(json.dumps(st.session_state.cases, indent=2, default=str))


def _add_case(target: str, target_type: str, oath: OathnetResult, sherl: SherlockResult):
    case_id = f"{target}_{int(time.time())}"
    case = {
        "id": case_id,
        "target": target,
        "target_type": target_type,
        "timestamp": datetime.now().isoformat(),
        "risk_score": _compute_risk(oath, sherl),
        "breach_count": oath.breach_count if oath else 0,
        "social_count": sherl.found_count if sherl else 0,
        "oathnet_success": oath.success if oath else False,
        "sherlock_success": sherl.success if sherl else False,
    }
    st.session_state.cases.insert(0, case)
    st.session_state.active_case_id = case_id
    _save_cases()
    return case_id


# ── Risk scoring ──────────────────────────────────────────────────────────────

def _compute_risk(oath: Optional[OathnetResult], sherl: Optional[SherlockResult]) -> int:
    score = 0
    if oath:
        score += oath.risk_score
    if sherl:
        score += sherl.risk_score
    return min(score, 100)


def _risk_label(score: int) -> tuple[str, str]:
    """Returns (label, hex_color)."""
    if score >= 75:
        return "CRÍTICO", "#f85149"
    if score >= 50:
        return "ALTO", "#f0883e"
    if score >= 25:
        return "MÉDIO", "#ffd700"
    return "BAIXO", "#39d353"


# ── Investigation runner ──────────────────────────────────────────────────────

def _log(level: str, module: str, msg: str, detail: str = ""):
    """Append an entry to the in-session debug log."""
    st.session_state.debug_log.append({
        "ts": datetime.now().strftime("%H:%M:%S.%f")[:-3],
        "level": level.upper(),
        "module": module,
        "msg": msg,
        "detail": detail,
    })


def _run_investigation(target: str, target_type: str):
    import traceback

    if not OATHNET_API_KEY:
        st.error("❌ OATHNET_API_KEY não configurada. Contate o administrador.")
        return

    # Reset debug log for each new investigation
    st.session_state.debug_log = []
    _log("INFO", "SYSTEM", f"Investigação iniciada", f"alvo={target}  tipo={target_type}  api_key={'SET' if OATHNET_API_KEY else 'MISSING'}")

    client = OathnetClient(api_key=OATHNET_API_KEY)

    # ── Oathnet ──────────────────────────────────────────────────────────────
    with st.status("🌐 Consultando Oathnet (vazamentos)...", expanded=True) as s:
        t0 = time.time()
        try:
            _log("INFO", "OATHNET", f"Chamando {'search_email' if target_type == 'Email' else 'search_username'}", f"base_url={OATHNET_BASE_URL}")
            if target_type == "Email":
                oath_result = client.search_email(target)
            else:
                oath_result = client.search_username(target)
            elapsed = round(time.time() - t0, 2)
            if oath_result.success:
                _log("OK", "OATHNET", f"Sucesso em {elapsed}s", f"breaches={oath_result.breach_count}  pastes={oath_result.paste_count}  domains={len(oath_result.domains)}")
                s.update(label=f"✅ Oathnet concluído ({elapsed}s)", state="complete")
            else:
                _log("WARN", "OATHNET", f"API retornou sem sucesso em {elapsed}s", oath_result.error)
                s.update(label=f"⚠️ Oathnet: {oath_result.error}", state="error")
        except Exception as exc:
            oath_result = None
            tb = traceback.format_exc()
            _log("ERROR", "OATHNET", f"Exceção: {exc}", tb)
            s.update(label=f"❌ Oathnet falhou: {exc}", state="error")

    # ── Sherlock ─────────────────────────────────────────────────────────────
    with st.status("🔍 Verificando redes sociais (Sherlock)...", expanded=True) as s:
        t0 = time.time()
        try:
            _log("INFO", "SHERLOCK", "Iniciando verificação async de plataformas", f"prefer_cli={st.session_state.prefer_cli}  platforms=25")
            sherl_result = search_username(target, prefer_cli=st.session_state.prefer_cli)
            elapsed = round(time.time() - t0, 2)
            _log("OK", "SHERLOCK", f"Concluído em {elapsed}s via {sherl_result.source}",
                 f"found={sherl_result.found_count}  not_found={len(sherl_result.not_found)}  errors={len(sherl_result.errors)}")
            if sherl_result.errors:
                for e in sherl_result.errors[:5]:
                    _log("WARN", "SHERLOCK", f"Timeout/erro em {e.platform}", e.error or "")
            s.update(label=f"✅ Sherlock concluído — {sherl_result.found_count} encontradas ({elapsed}s)", state="complete")
        except Exception as exc:
            sherl_result = None
            tb = traceback.format_exc()
            _log("ERROR", "SHERLOCK", f"Exceção: {exc}", tb)
            s.update(label=f"❌ Sherlock falhou: {exc}", state="error")

    st.session_state.oathnet_result = oath_result
    st.session_state.sherlock_result = sherl_result
    st.session_state.investigation = {
        "target": target,
        "target_type": target_type,
        "timestamp": datetime.now().isoformat(),
    }

    _log("INFO", "SYSTEM", "Investigação finalizada", f"oathnet_ok={oath_result is not None}  sherlock_ok={sherl_result is not None}")

    if oath_result or sherl_result:
        _add_case(target, target_type, oath_result, sherl_result)


# ── Export helpers ────────────────────────────────────────────────────────────

def _build_export_json() -> str:
    inv = st.session_state.investigation or {}
    oath: Optional[OathnetResult] = st.session_state.oathnet_result
    sherl: Optional[SherlockResult] = st.session_state.sherlock_result

    payload: dict = {
        "meta": {
            "tool": "NexusOSINT",
            "version": APP_VERSION,
            "exported_at": datetime.now().isoformat(),
        },
        "investigation": inv,
        "risk_score": _compute_risk(oath, sherl),
    }

    if oath:
        payload["oathnet"] = {
            "success":        oath.success,
            "breach_count":   oath.breach_count,
            "stealer_count":  oath.stealer_count,
            "holehe_count":   len(oath.holehe_domains),
            "results_found":  oath.results_found,
            "session_id":     oath.session_id,
            "error":          oath.error,
            "breaches": [
                {
                    "dbname":   b.dbname,
                    "email":    b.email,
                    "username": b.username,
                    "password": b.password,
                    "ip":       b.ip,
                    "domain":   b.domain,
                    "country":  b.country,
                    "date":     b.date,
                }
                for b in oath.breaches
            ],
            "stealers": [
                {
                    "url":      s.url,
                    "username": s.username,
                    "password": s.password,
                    "domain":   s.domain,
                    "log_id":   s.log_id,
                    "pwned_at": s.pwned_at,
                }
                for s in oath.stealers
            ],
            "holehe_domains": oath.holehe_domains,
        }

    if sherl:
        payload["sherlock"] = {
            "success": sherl.success,
            "source": sherl.source,
            "found_count": sherl.found_count,
            "found": [
                {"platform": p.platform, "url": p.url, "category": p.category}
                for p in sherl.found
            ],
            "errors": [{"platform": p.platform, "error": p.error} for p in sherl.errors],
        }

    return json.dumps(payload, indent=2, default=str)


def _build_export_excel() -> bytes:
    oath: Optional[OathnetResult] = st.session_state.oathnet_result
    sherl: Optional[SherlockResult] = st.session_state.sherlock_result

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:  # type: ignore
        wb = writer.book
        fmt_header = wb.add_format({"bold": True, "bg_color": "#0d1117", "font_color": "#00d4ff", "border": 1})
        fmt_cell = wb.add_format({"bg_color": "#161b22", "font_color": "#e6edf3", "border": 1})

        # Sheet: Breaches
        if oath and oath.breaches:
            df_breach = pd.DataFrame([{
                "DB / Fonte": b.dbname,
                "Email":      b.email,
                "Username":   b.username,
                "Senha":      b.password,
                "IP":         b.ip,
                "País":       b.country,
                "Data":       b.date[:10] if b.date else "",
            } for b in oath.breaches])
            df_breach.to_excel(writer, index=False, sheet_name="Vazamentos")
            ws = writer.sheets["Vazamentos"]
            for col_num, val in enumerate(df_breach.columns):
                ws.write(0, col_num, val, fmt_header)
                ws.set_column(col_num, col_num, 22, fmt_cell)

        # Sheet: Stealers
        if oath and oath.stealers:
            df_steal = pd.DataFrame([{
                "URL":      s.url,
                "Username": s.username,
                "Senha":    s.password,
                "Domínio":  ", ".join(s.domain[:2]) if s.domain else "",
                "Data":     s.pwned_at[:10] if s.pwned_at else "",
                "Log ID":   s.log_id,
            } for s in oath.stealers])
            df_steal.to_excel(writer, index=False, sheet_name="Stealer Logs")
            ws = writer.sheets["Stealer Logs"]
            for col_num, val in enumerate(df_steal.columns):
                ws.write(0, col_num, val, fmt_header)
                ws.set_column(col_num, col_num, 28, fmt_cell)

        # Sheet: Social
        if sherl and sherl.found:
            df_social = pd.DataFrame(
                [
                    {"Plataforma": p.platform, "URL": p.url, "Categoria": p.category}
                    for p in sherl.found
                ]
            )
            df_social.to_excel(writer, index=False, sheet_name="Redes Sociais")
            ws = writer.sheets["Redes Sociais"]
            for col_num, val in enumerate(df_social.columns):
                ws.write(0, col_num, val, fmt_header)
                ws.set_column(col_num, col_num, 30, fmt_cell)

        # Sheet: Summary
        inv = st.session_state.investigation or {}
        df_summary = pd.DataFrame([
            {"Campo": "Alvo",           "Valor": inv.get("target", "")},
            {"Campo": "Tipo",           "Valor": inv.get("target_type", "")},
            {"Campo": "Investigado em", "Valor": inv.get("timestamp", "")},
            {"Campo": "Risk Score",     "Valor": _compute_risk(oath, sherl)},
            {"Campo": "Vazamentos",     "Valor": oath.breach_count  if oath else 0},
            {"Campo": "Stealer Logs",   "Valor": oath.stealer_count if oath else 0},
            {"Campo": "Holehe Serviços","Valor": len(oath.holehe_domains) if oath else 0},
            {"Campo": "Redes Sociais",  "Valor": sherl.found_count  if sherl else 0},
        ])
        df_summary.to_excel(writer, index=False, sheet_name="Resumo")

    buf.seek(0)
    return buf.read()


# ── UI Sections ───────────────────────────────────────────────────────────────

def _render_header():
    st.markdown(
        """
        <div class="nexus-header">
            <div class="nexus-title">⬡ NEXUSOSINT</div>
            <div class="nexus-sub">INTELLIGENCE GATHERING PLATFORM · v{v}</div>
        </div>
        """.format(v=APP_VERSION),
        unsafe_allow_html=True,
    )


def _render_sidebar():
    with st.sidebar:
        st.markdown(
            '<div style="text-align:center;padding:10px 0 6px">'
            '<span style="color:#00d4ff;font-size:1.4rem;font-weight:900;letter-spacing:.12em">⬡ NEXUSOSINT</span><br>'
            f'<span style="color:#8b949e;font-size:.7rem">v{APP_VERSION} · Legal & ethical use only</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")

        # ── Navegação rápida para abas ─────────────────────────────────────
        st.markdown("**📂 Resultados**")
        st.caption("Clique após uma busca para ver os detalhes.")
        for label in ["📊 Resumo", "💥 Vazamentos", "🌐 Redes Sociais", "📤 Exportar"]:
            st.markdown(f'<div style="padding:4px 8px;color:#8b949e;font-size:.8rem">{label}</div>', unsafe_allow_html=True)

        st.markdown("---")

        # ── Histórico ──────────────────────────────────────────────────────
        st.markdown("**📋 Histórico de Casos**")
        if not st.session_state.cases:
            st.caption("_Nenhuma busca ainda._")
        else:
            if st.button("🗑️ Limpar histórico", use_container_width=True, key="clear_history"):
                st.session_state.cases = []
                CASES_FILE.unlink(missing_ok=True)
                st.rerun()
            for case in st.session_state.cases[:12]:
                label_r, _ = _risk_label(case["risk_score"])
                badge = "🔴" if label_r == "CRÍTICO" else "🟠" if label_r == "ALTO" else "🟡" if label_r == "MÉDIO" else "🟢"
                st.markdown(
                    f'<div class="case-card">'
                    f'<div class="case-target">{badge} {case["target"]}</div>'
                    f'<div class="case-meta">{case["target_type"]} · Risk {case["risk_score"]} · {case["timestamp"][:16]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("---")
        st.caption("OathNet API · Sherlock Engine")


def _render_tab_summary(oath: Optional[OathnetResult], sherl: Optional[SherlockResult]):
    inv = st.session_state.investigation or {}
    risk = _compute_risk(oath, sherl)
    label, color = _risk_label(risk)

    # Risk gauge
    st.markdown(
        f"""<div class="risk-score-wrap">
            <div class="risk-circle" style="border-color:{color}; color:{color};">{risk}</div>
            <div class="risk-info">
                <div class="risk-label">PONTUAÇÃO DE RISCO</div>
                <div class="risk-verdict" style="color:{color};">{label}</div>
                <div class="risk-label">Alvo: {inv.get('target','')} ({inv.get('target_type','')})</div>
                <div class="risk-label">Investigado: {inv.get('timestamp','')[:19].replace('T',' ')}</div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Metrics row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("💥 Vazamentos", oath.breach_count if oath else "—")
    with c2:
        st.metric("🦠 Stealer Logs", oath.stealer_count if oath else "—")
    with c3:
        st.metric("🌐 Redes Sociais", sherl.found_count if sherl else "—")
    with c4:
        st.metric("📧 Serviços Holehe", len(oath.holehe_domains) if oath else "—")

    st.markdown("---")

    # Quick status
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Status Oathnet**")
        if not oath:
            st.markdown('<div class="alert-danger">❌ Módulo não executado</div>', unsafe_allow_html=True)
        elif oath.success:
            st.markdown(f'<div class="alert-success">✅ {oath.breach_count} vazamento(s) encontrado(s)</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="alert-warning">⚠️ {oath.error or "Nenhum dado retornado"}</div>', unsafe_allow_html=True)

    with col_b:
        st.markdown("**Status Sherlock**")
        if not sherl:
            st.markdown('<div class="alert-danger">❌ Módulo não executado</div>', unsafe_allow_html=True)
        elif sherl.success:
            st.markdown(f'<div class="alert-success">✅ {sherl.found_count}/{sherl.total_checked} plataformas confirmadas (via {sherl.source})</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="alert-warning">⚠️ {sherl.error or "Nenhum dado retornado"}</div>', unsafe_allow_html=True)

    # Top breaches preview
    if oath and oath.breaches:
        st.markdown("---")
        st.markdown("**Últimos Vazamentos Detectados**")
        has_discord = any(b.discord_id for b in oath.breaches[:5])
        rows = []
        for b in oath.breaches[:5]:
            row = {"DB / Fonte": b.dbname, "Email": b.email, "Username": b.username}
            if has_discord:
                row["Discord ID"] = b.discord_id
            row["Senha"] = ("*" * min(len(b.password), 8)) if b.password else "—"
            row["País"]  = b.country
            row["Data"]  = b.date[:10] if b.date else "—"
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_tab_oathnet(oath: Optional[OathnetResult]):
    if not oath:
        st.markdown('<div class="alert-info">ℹ️ Nenhuma investigação ativa. Use a sidebar para iniciar.</div>', unsafe_allow_html=True)
        return

    if not oath.success:
        st.markdown(f'<div class="alert-danger">❌ Erro na API OathNet: {oath.error}</div>', unsafe_allow_html=True)
        st.markdown("""
        **Checklist de diagnóstico:**
        - Verifique a aba 🛠️ Debug → botão **Testar Conexão Oathnet**
        - A URL correta é `https://oathnet.org/api` (não `api.oathnet.org`)
        - O header correto é `x-api-key` (não `Authorization: Bearer`)
        - Endpoint correto: `GET /service/search-breach?q=...`
        """)
        return

    st.markdown(f"**Alvo:** `{oath.query}` ({oath.query_type})")

    # Quota info
    if oath.meta.plan:
        st.markdown(
            f'<div class="alert-info">📊 Plano: <b>{oath.meta.plan}</b> · '
            f'Lookups: <b>{oath.meta.used_today}</b> usados, <b>{oath.meta.left_today}</b> restantes hoje</div>',
            unsafe_allow_html=True,
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💥 Vazamentos", oath.breach_count)
    c2.metric("🦠 Stealer Logs", oath.stealer_count)
    c3.metric("📧 Serviços (Holehe)", len(oath.holehe_domains))
    c4.metric("📈 Total encontrado", oath.results_found)

    # ── Breach records ────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("💥 Registros de Vazamento (Breach DB)")
    if not oath.breaches:
        st.markdown('<div class="alert-success">✅ Nenhum vazamento encontrado para este alvo.</div>', unsafe_allow_html=True)
    else:
        # ── Pagination ────────────────────────────────────────────────────
        PAGE_SIZE = 10
        total     = len(oath.breaches)
        max_page  = max(0, (total - 1) // PAGE_SIZE)
        if st.session_state.breach_page > max_page:
            st.session_state.breach_page = 0

        page_start = st.session_state.breach_page * PAGE_SIZE
        page_end   = min(page_start + PAGE_SIZE, total)
        page_slice = oath.breaches[page_start:page_end]

        st.caption(f"Mostrando {page_start + 1}–{page_end} de {total} registros"
                   + (f" (total encontrado na API: {oath.results_found})" if oath.results_found > total else ""))

        # ── Build table rows ──────────────────────────────────────────────
        has_discord = any(b.discord_id for b in page_slice)
        has_phone   = any(b.phone      for b in page_slice)
        has_pass    = any(b.password   for b in page_slice)

        rows = []
        for b in page_slice:
            row = {"DB / Fonte": b.dbname, "Email": b.email, "Username": b.username}
            if has_discord:
                row["Discord ID"] = b.discord_id
            if has_phone:
                row["Telefone"] = b.phone
            if has_pass:
                row["Senha"] = b.password[:30] + "..." if len(b.password) > 30 else b.password
            row["IP"]   = b.ip
            row["País"] = b.country
            row["Data"] = b.date[:10] if b.date else ""
            for k, v in b.extra_fields.items():
                row[k] = str(v)[:40]
            rows.append(row)

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # ── Page controls ─────────────────────────────────────────────────
        if max_page > 0:
            pcol1, pcol2, pcol3 = st.columns([1, 3, 1])
            with pcol1:
                if st.button("◀ Anterior", disabled=st.session_state.breach_page == 0,
                             use_container_width=True):
                    st.session_state.breach_page -= 1
                    st.rerun()
            with pcol2:
                st.markdown(
                    f'<p style="text-align:center;color:#8b949e;margin:6px 0">Página '
                    f'<b>{st.session_state.breach_page + 1}</b> de <b>{max_page + 1}</b></p>',
                    unsafe_allow_html=True,
                )
            with pcol3:
                if st.button("Próxima ▶", disabled=st.session_state.breach_page >= max_page,
                             use_container_width=True):
                    st.session_state.breach_page += 1
                    st.rerun()

        # ── Discord auto-lookup ───────────────────────────────────────────
        discord_ids = list({b.discord_id for b in oath.breaches if b.discord_id})
        if discord_ids:
            st.markdown("---")
            st.subheader("🎮 Perfis Discord Detectados")
            st.caption(f"{len(discord_ids)} Discord ID(s) encontrado(s) nos vazamentos. Clique para carregar os perfis.")
            for did in discord_ids[:5]:  # max 5 para não esgotar cota
                with st.expander(f"Discord ID: {did}"):
                    _render_discord_card(did)

    # ── Stealer logs ──────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🦠 Stealer Logs (Credenciais Roubadas por Malware)")
    if not oath.stealers:
        st.markdown('<div class="alert-success">✅ Nenhum stealer log encontrado.</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="alert-danger">⚠️ Credenciais encontradas em logs de malware infostealer. '
            'Isso indica que um dispositivo foi comprometido.</div>',
            unsafe_allow_html=True,
        )
        df_st = pd.DataFrame([{
            "URL":      s.url[:60],
            "Username": s.username,
            "Senha":    s.password[:30] + "..." if len(s.password) > 30 else s.password,
            "Domínio":  ", ".join(s.domain[:2]) if s.domain else "",
            "Data":     s.pwned_at[:10] if s.pwned_at else "",
            "Log ID":   s.log_id[:20] + "..." if len(s.log_id) > 20 else s.log_id,
        } for s in oath.stealers])
        st.dataframe(df_st, use_container_width=True, hide_index=True)

    # ── Holehe ────────────────────────────────────────────────────────────
    if oath.holehe_domains:
        st.markdown("---")
        st.subheader("📧 Serviços com Conta Cadastrada (Holehe)")
        badges = "".join(
            f'<span class="platform-found">📌 {d}</span>'
            for d in oath.holehe_domains
        )
        st.markdown(badges, unsafe_allow_html=True)
        st.markdown("")
        st.dataframe(pd.DataFrame({"Serviço": oath.holehe_domains}), use_container_width=True, hide_index=True)

    # ── Raw JSON ──────────────────────────────────────────────────────────
    with st.expander("🔬 Resposta Raw da API (JSON)"):
        st.json(oath.raw_response if oath.raw_response else {"_note": "Sem dados brutos"})


def _render_tab_sherlock(sherl: Optional[SherlockResult]):
    if not sherl:
        st.markdown('<div class="alert-info">ℹ️ Nenhuma investigação ativa. Use a sidebar para iniciar.</div>', unsafe_allow_html=True)
        return

    if not sherl.success:
        st.markdown(f'<div class="alert-danger">❌ Erro no Sherlock: {sherl.error}</div>', unsafe_allow_html=True)
        return

    st.markdown(f"**Username pesquisado:** `{sherl.username}` · **Motor:** `{sherl.source}`")
    c1, c2, c3 = st.columns(3)
    c1.metric("✅ Encontrado", sherl.found_count)
    c2.metric("❌ Não encontrado", len(sherl.not_found))
    c3.metric("⚠️ Erros/Timeout", len(sherl.errors))

    # Platforms found
    st.markdown("---")
    st.subheader("✅ Perfis Encontrados")
    if not sherl.found:
        st.markdown('<div class="alert-success">Nenhum perfil público encontrado nas plataformas verificadas.</div>', unsafe_allow_html=True)
    else:
        # Badge cloud
        badges = "".join(
            f'<a href="{p.url}" target="_blank" style="text-decoration:none;">'
            f'<span class="platform-found">{p.icon} {p.platform}</span></a>'
            for p in sherl.found
        )
        st.markdown(badges, unsafe_allow_html=True)
        st.markdown("")

        # Table
        df = pd.DataFrame(
            [{"Plataforma": p.platform, "URL": p.url, "Categoria": p.category}
             for p in sherl.found]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Category breakdown
    if sherl.found:
        st.markdown("---")
        st.subheader("📊 Presença por Categoria")
        from collections import Counter
        cats = Counter(p.category for p in sherl.found)
        df_cat = pd.DataFrame(
            [{"Categoria": cat, "Perfis": count} for cat, count in cats.most_common()]
        )
        st.dataframe(df_cat, use_container_width=True, hide_index=True)

    # Not found
    with st.expander(f"❌ Plataformas sem perfil encontrado ({len(sherl.not_found)})"):
        badges_nf = "".join(
            f'<span class="platform-notfound">{p.icon} {p.platform}</span>'
            for p in sherl.not_found
        )
        st.markdown(badges_nf if badges_nf else "_Nenhuma_", unsafe_allow_html=True)

    # Errors
    if sherl.errors:
        with st.expander(f"⚠️ Erros / Timeouts ({len(sherl.errors)})"):
            df_err = pd.DataFrame(
                [{"Plataforma": p.platform, "Erro": p.error} for p in sherl.errors]
            )
            st.dataframe(df_err, use_container_width=True, hide_index=True)


def _render_tab_export(oath: Optional[OathnetResult], sherl: Optional[SherlockResult]):
    import re
    if not st.session_state.investigation:
        st.markdown('<div class="alert-info">ℹ️ Nenhuma investigação ativa para exportar.</div>', unsafe_allow_html=True)
        return

    inv        = st.session_state.investigation
    ts         = inv.get("timestamp", datetime.now().isoformat())
    target     = inv.get("target", "target")
    ttype      = inv.get("target_type", "")
    risk       = _compute_risk(oath, sherl)
    ts_safe    = ts[:10]
    target_safe = re.sub(r"[^a-zA-Z0-9_\-@.]", "_", target)

    st.markdown("### 📤 Exportar Relatório")
    st.markdown(f"**Alvo:** `{target}` · **Tipo:** `{ttype}` · **Risk Score:** `{risk}`")
    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    # ── HTML report ───────────────────────────────────────────────────────────
    with col1:
        st.markdown("**🌐 Relatório HTML**")
        st.caption("Dark-mode interativo com copy buttons, collapsibles e seções linkadas. Abre direto no navegador.")
        if st.button("⚙️ Gerar HTML", use_container_width=True, key="gen_html"):
            with st.spinner("Gerando HTML..."):
                try:
                    html_bytes = generate_html(
                        target=target, target_type=ttype,
                        oath=oath, sherl=sherl,
                        risk_score=risk, timestamp=ts,
                    ).encode("utf-8")
                    st.session_state["_html_cache"] = html_bytes
                    st.success("✅ HTML pronto!")
                except Exception as exc:
                    st.error(f"Erro: {exc}")
        if st.session_state.get("_html_cache"):
            st.download_button(
                label="⬇️ Baixar HTML",
                data=st.session_state["_html_cache"],
                file_name=f"nexusosint_{target_safe}_{ts_safe}.html",
                mime="text/html",
                use_container_width=True,
            )

    # ── PDF report ────────────────────────────────────────────────────────────
    with col2:
        st.markdown("**📄 Relatório PDF**")
        st.caption("Estilo OSINT Industries — capa, índice, tabelas, timeline. Profissional para documentação.")
        if st.button("⚙️ Gerar PDF", use_container_width=True, key="gen_pdf"):
            with st.spinner("Gerando PDF com ReportLab..."):
                try:
                    pdf_bytes = generate_pdf(
                        target=target, target_type=ttype,
                        oath=oath, sherl=sherl,
                        risk_score=risk, timestamp=ts,
                    )
                    st.session_state["_pdf_cache"] = pdf_bytes
                    st.success("✅ PDF pronto!")
                except Exception as exc:
                    st.error(f"Erro ao gerar PDF: {exc}")
        if st.session_state.get("_pdf_cache"):
            st.download_button(
                label="⬇️ Baixar PDF",
                data=st.session_state["_pdf_cache"],
                file_name=f"nexusosint_{target_safe}_{ts_safe}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    # ── JSON raw ──────────────────────────────────────────────────────────────
    with col3:
        st.markdown("**📦 JSON + Excel**")
        st.caption("Dados brutos estruturados para integração com outras ferramentas.")
        json_data  = _build_export_json()
        excel_data = _build_export_excel()
        st.download_button(
            label="⬇️ Baixar JSON",
            data=json_data,
            file_name=f"nexusosint_{target_safe}_{ts_safe}.json",
            mime="application/json",
            use_container_width=True,
        )
        st.download_button(
            label="⬇️ Baixar Excel",
            data=excel_data,
            file_name=f"nexusosint_{target_safe}_{ts_safe}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    # ── HTML preview ──────────────────────────────────────────────────────────
    if st.session_state.get("_html_cache"):
        st.markdown("---")
        st.markdown("**👁️ Preview HTML** (iframe — comportamento pode variar por navegador)")
        html_b64 = __import__("base64").b64encode(st.session_state["_html_cache"]).decode()
        st.markdown(
            f'<iframe src="data:text/html;base64,{html_b64}" '
            f'width="100%" height="600" style="border:1px solid #30363d;border-radius:8px"></iframe>',
            unsafe_allow_html=True,
        )

    # ── JSON preview ──────────────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("📋 Preview JSON"):
        st.code(_build_export_json(), language="json")




# ── Debug / Diagnostics tab ───────────────────────────────────────────────────

def _render_tab_debug(oath: Optional[OathnetResult], sherl: Optional[SherlockResult]):
    import platform as _platform
    import sys

    st.markdown("### 🛠️ Painel de Diagnóstico")
    st.caption("Informações técnicas completas para debugging. Não compartilhe capturas com a API Key visível.")

    # ── API Key / connectivity check ──────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 🔑 Configuração da API")

    col1, col2 = st.columns([2, 1])
    with col1:
        key_display = OATHNET_API_KEY[:8] + "..." + OATHNET_API_KEY[-4:] if OATHNET_API_KEY else "❌ NÃO DEFINIDA"
        st.code(f"OATHNET_API_KEY = {key_display}\nBASE_URL        = {OATHNET_BASE_URL}", language="bash")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔌 Testar Conexão Oathnet", use_container_width=True):
            with st.spinner("Testando..."):
                try:
                    client = OathnetClient(api_key=OATHNET_API_KEY)
                    ok, msg = client.validate_key()
                    if ok:
                        st.markdown(f'<div class="alert-success">✅ {msg}</div>', unsafe_allow_html=True)
                        _log("OK", "DIAG", "validate_key OK", msg)
                    else:
                        st.markdown(f'<div class="alert-danger">❌ {msg}</div>', unsafe_allow_html=True)
                        _log("WARN", "DIAG", "validate_key FAIL", msg)
                except Exception as exc:
                    st.markdown(f'<div class="alert-danger">❌ Exceção: {exc}</div>', unsafe_allow_html=True)
                    _log("ERROR", "DIAG", f"validate_key exception: {exc}", "")

        if st.button("🌐 Ping raw HTTP", use_container_width=True):
            import requests as _req
            with st.spinner("Pingando..."):
                try:
                    r = _req.get(
                        OATHNET_BASE_URL,
                        headers={"Authorization": f"Bearer {OATHNET_API_KEY}", "User-Agent": "NexusOSINT/1.0"},
                        timeout=8,
                    )
                    st.markdown(f'<div class="alert-info">HTTP {r.status_code} · {len(r.content)} bytes · {r.elapsed.total_seconds():.2f}s</div>', unsafe_allow_html=True)
                    _log("INFO", "DIAG", f"Raw ping → HTTP {r.status_code}", f"bytes={len(r.content)}")
                    with st.expander("Response Headers"):
                        st.json(dict(r.headers))
                    with st.expander("Response Body (primeiros 2000 chars)"):
                        st.code(r.text[:2000])
                except Exception as exc:
                    st.markdown(f'<div class="alert-danger">❌ {exc}</div>', unsafe_allow_html=True)
                    _log("ERROR", "DIAG", f"Raw ping exception: {exc}", "")

    # ── Oathnet raw response ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 💥 Oathnet — Resposta Bruta")
    if not oath:
        st.markdown('<div class="alert-warning">⚠️ Nenhuma resposta Oathnet disponível. Execute uma investigação primeiro.</div>', unsafe_allow_html=True)
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("success", str(oath.success))
        c2.metric("breach_count", oath.breach_count)
        c3.metric("stealer_count", oath.stealer_count)
        with st.expander("📦 raw_response (JSON completo)", expanded=not oath.success):
            st.json(oath.raw_response if oath.raw_response else {"_note": "API retornou vazio ou falhou"})
        if oath.error:
            st.markdown(f'<div class="alert-danger">❌ Mensagem de erro: <code>{oath.error}</code></div>', unsafe_allow_html=True)
            st.markdown("**Possíveis causas:**")
            causes = {
                "Cannot reach Oathnet API": "O container não tem acesso externo à internet, ou a URL base está errada. Verifique `docker run` com `--network host` ou a configuração de rede do Compose.",
                "Invalid or expired API key": "A chave da API está incorreta ou revogada. Verifique no painel da Oathnet.",
                "Rate limit exceeded": "Muitas requisições. Aguarde alguns segundos.",
                "timed out": "O servidor da Oathnet está lento ou inacessível. Tente novamente.",
            }
            matched = False
            for pattern, cause in causes.items():
                if pattern.lower() in oath.error.lower():
                    st.warning(f"➜ {cause}")
                    matched = True
            if not matched:
                st.info("Consulte a aba Debug Log abaixo para o traceback completo.")

    # ── Sherlock raw results ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 🌐 Sherlock — Resultado Completo")
    if not sherl:
        st.markdown('<div class="alert-warning">⚠️ Nenhum resultado Sherlock. Execute uma investigação primeiro.</div>', unsafe_allow_html=True)
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("fonte", sherl.source)
        c2.metric("encontrado", sherl.found_count)
        c3.metric("não encontrado", len(sherl.not_found))
        c4.metric("erros/timeout", len(sherl.errors))

        if sherl.errors:
            st.markdown("**⚠️ Plataformas com erro (timeout ou SSL):**")
            df_err = pd.DataFrame(
                [{"Plataforma": p.platform, "URL": p.url, "Erro": p.error} for p in sherl.errors]
            )
            st.dataframe(df_err, use_container_width=True, hide_index=True)

        with st.expander("✅ Todas as plataformas encontradas"):
            if sherl.found:
                st.dataframe(
                    pd.DataFrame([{"Plataforma": p.platform, "URL": p.url, "Categoria": p.category} for p in sherl.found]),
                    use_container_width=True, hide_index=True,
                )
            else:
                st.caption("Nenhuma.")

    # ── Session state viewer ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 🧠 Session State Completo")
    # Note: not using st.expander here to avoid nesting issues
    safe_state = {
        k: v for k, v in st.session_state.items()
        if k not in ("oathnet_result", "sherlock_result")
    }
    st.json(safe_state, expanded=False)

    # ── Debug log ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📋 Debug Log (última investigação)")

    level_colors = {"OK": "#39d353", "INFO": "#00d4ff", "WARN": "#f0883e", "ERROR": "#f85149"}
    logs = st.session_state.debug_log

    if not logs:
        st.markdown('<div class="alert-info">ℹ️ Nenhum log disponível. Execute uma investigação para gerar logs.</div>', unsafe_allow_html=True)
    else:
        col_filter, col_clear = st.columns([3, 1])
        with col_filter:
            show_levels = st.multiselect(
                "Filtrar por nível",
                ["OK", "INFO", "WARN", "ERROR"],
                default=["OK", "INFO", "WARN", "ERROR"],
                label_visibility="collapsed",
            )
        with col_clear:
            if st.button("🗑️ Limpar log", use_container_width=True):
                st.session_state.debug_log = []
                st.rerun()

        filtered = [e for e in logs if e["level"] in show_levels]

        # Render as styled log lines
        lines = []
        for e in filtered:
            color = level_colors.get(e["level"], "#e6edf3")
            detail_html = f"<br><span style='color:#8b949e;font-size:0.75rem;white-space:pre-wrap;'>{e['detail'][:400]}</span>" if e["detail"] else ""
            lines.append(
                f'<div style="border-bottom:1px solid #30363d;padding:5px 0;">'
                f'<span style="color:#8b949e;">{e["ts"]}</span> '
                f'<span style="color:{color};font-weight:700;min-width:50px;display:inline-block;">[{e["level"]}]</span> '
                f'<span style="color:#00d4ff;">[{e["module"]}]</span> '
                f'<span style="color:#e6edf3;">{e["msg"]}</span>'
                f'{detail_html}'
                f'</div>'
            )
        st.markdown(
            f'<div style="background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:12px 16px;'
            f'font-family:Consolas,monospace;font-size:0.8rem;max-height:420px;overflow-y:auto;">'
            + "\n".join(lines) +
            "</div>",
            unsafe_allow_html=True,
        )

        # Export log as text
        log_text = "\n".join(
            f"[{e['ts']}] [{e['level']}] [{e['module']}] {e['msg']}" +
            (f"\n  {e['detail']}" if e["detail"] else "")
            for e in logs
        )
        st.download_button(
            "⬇️ Exportar log (.txt)",
            data=log_text,
            file_name=f"nexusosint_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
        )

    # ── Environment info ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ⚙️ Ambiente")
    with st.expander("Python / OS / Pacotes"):
        env_info = {
            "python_version": sys.version,
            "platform": _platform.platform(),
            "streamlit_version": st.__version__,
            "oathnet_base_url": OATHNET_BASE_URL,
            "api_key_set": bool(OATHNET_API_KEY),
            "api_key_length": len(OATHNET_API_KEY) if OATHNET_API_KEY else 0,
            "cases_file": str(CASES_FILE.resolve()),
            "cases_count": len(st.session_state.cases),
        }
        st.json(env_info)



# ══════════════════════════════════════════════════════════════════════════════
# ── FERRAMENTAS STANDALONE ────────────────────────────────────────────────────
# Cada ferramenta funciona de forma independente, sem precisar de investigação
# ══════════════════════════════════════════════════════════════════════════════

def _tool_input(label: str, placeholder: str, key: str) -> str:
    """Campo de input estilizado para as ferramentas."""
    return st.text_input(label, placeholder=placeholder, key=key,
                         label_visibility="collapsed")


def _render_tab_tools():
    """Aba principal de Ferramentas com sub-abas."""
    st.markdown("### 🛠️ Ferramentas OSINT")
    st.caption("Ferramentas independentes — funcionam sem precisar de uma investigação ativa.")

    tool_tabs = st.tabs([
        "🔍 Full Search",
        "🌐 IP Info",
        "🎮 Discord",
        "🕹️ Gaming",
        "🔗 Subdomínios",
        "📁 File Search",
    ])

    with tool_tabs[0]:
        _render_tool_fullsearch()
    with tool_tabs[1]:
        _render_tool_ip()
    with tool_tabs[2]:
        _render_tool_discord()
    with tool_tabs[3]:
        _render_tool_gaming()
    with tool_tabs[4]:
        _render_tool_subdomain()
    with tool_tabs[5]:
        _render_tool_filesearch()


# ── Full Search ───────────────────────────────────────────────────────────────

def _render_tool_fullsearch():
    st.markdown("#### 🔍 Full Search — Pesquisa Completa")
    st.markdown(
        '<div class="alert-info">ℹ️ Insira qualquer dado (email, username, IP, Discord ID, domínio, telefone…) '
        'e o sistema executa <b>todos os módulos relevantes</b> automaticamente.</div>',
        unsafe_allow_html=True,
    )

    # Pega valor que veio da sidebar (busca rápida)
    autorun_query = st.session_state.pop("_fs_autorun", None)

    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("Query",
                              value=autorun_query or "",
                              placeholder="email, username, IP, Discord ID, domínio...",
                              key="fs_query", label_visibility="collapsed")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run = st.button("🔍 Buscar Tudo", use_container_width=True, key="fs_run")

    # Roda automaticamente se veio da sidebar
    if (run or autorun_query) and query.strip():
        client = OathnetClient(api_key=OATHNET_API_KEY)
        results = {}

        # Detecta tipo para mostrar quais módulos vão rodar
        import re as _re
        is_email_q   = "@" in query
        is_ip_q      = bool(_re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", query))
        is_discord_q = bool(_re.match(r"^\d{14,19}$", query))
        is_domain_q  = "." in query and not is_ip_q and not is_email_q

        st.markdown("---")
        progress = st.progress(0, text="Iniciando busca...")

        modules_total = 0
        modules_done  = 0

        def step(label: str):
            nonlocal modules_done
            modules_done += 1
            pct = int((modules_done / max(modules_total, 1)) * 100)
            progress.progress(min(pct, 100), text=f"🔄 {label}...")

        # ── Conta quantos módulos rodarão ──────────────────────────────────
        is_username_q = not is_email_q and not is_ip_q and not is_discord_q and not is_domain_q
        module_list = ["Breach", "Stealer"]
        if is_email_q:    module_list += ["Holehe", "GHunt"]
        if is_ip_q:       module_list += ["IP Info"]
        if is_discord_q:  module_list += ["Discord User", "Discord History"]
        if is_domain_q:   module_list += ["Subdomínios"]
        if is_username_q: module_list += ["Steam", "Xbox", "Roblox"]
        modules_total = len(module_list)

        # ── Breach ─────────────────────────────────────────────────────────
        step("Vazamentos (Breach DB)")
        try:
            res = client.search_breach(query)
            results["breach"] = {"success": res.success, "data": res.breaches,
                                  "count": res.results_found, "error": res.error}
        except Exception as e:
            results["breach"] = {"success": False, "error": str(e)}

        # ── Stealer ────────────────────────────────────────────────────────
        step("Stealer Logs")
        try:
            res = client.search_stealer_v2(query)
            results["stealer"] = {"success": res.success, "data": res.stealers,
                                   "count": res.stealers_found, "error": res.error}
        except Exception as e:
            results["stealer"] = {"success": False, "error": str(e)}

        # ── Email-specific ─────────────────────────────────────────────────
        if is_email_q:
            step("Holehe")
            try:
                res = client.holehe(query)
                results["holehe"] = {"success": res.success, "data": res.holehe_domains,
                                     "count": len(res.holehe_domains), "error": res.error}
            except Exception as e:
                results["holehe"] = {"success": False, "error": str(e)}

            step("GHunt (Google)")
            try:
                ok, data = client._get("service/ghunt", params={"email": query})
                results["ghunt"] = {"success": ok, "data": data.get("data", data) if ok else None,
                                     "error": "" if ok else data.get("error", "")}
            except Exception as e:
                results["ghunt"] = {"success": False, "error": str(e)}

        # ── IP ─────────────────────────────────────────────────────────────
        if is_ip_q:
            step("IP Info")
            try:
                ok, data = client.ip_info(query)
                results["ip_info"] = {"success": ok, "data": data if ok else None,
                                       "error": "" if ok else data.get("error", "")}
            except Exception as e:
                results["ip_info"] = {"success": False, "error": str(e)}

        # ── Discord ────────────────────────────────────────────────────────
        if is_discord_q:
            step("Discord Userinfo")
            try:
                ok, data = client.discord_userinfo(query)
                results["discord"] = {"success": ok, "data": data if ok else None,
                                       "error": "" if ok else data.get("error", "")}
            except Exception as e:
                results["discord"] = {"success": False, "error": str(e)}

            step("Discord History")
            try:
                ok, data = client.discord_username_history(query)
                results["discord_history"] = {"success": ok, "data": data if ok else None,
                                               "error": "" if ok else data.get("error", "")}
            except Exception as e:
                results["discord_history"] = {"success": False, "error": str(e)}

        # ── Domain ─────────────────────────────────────────────────────────
        if is_domain_q:
            step("Subdomínios")
            try:
                ok, data = client.extract_subdomains(query)
                subs = data.get("subdomains", []) if ok else []
                results["subdomains"] = {"success": ok, "data": subs,
                                          "count": len(subs), "error": "" if ok else data.get("error", "")}
            except Exception as e:
                results["subdomains"] = {"success": False, "error": str(e)}

        # ── Gaming — só roda para username (não email, IP, Discord, domínio) ──
        is_username_q = not is_email_q and not is_ip_q and not is_discord_q and not is_domain_q
        if is_username_q:
            for platform, method in [("steam", client.steam_lookup),
                                      ("xbox",  client.xbox_lookup),
                                      ("roblox", lambda u: client.roblox_lookup(username=u))]:
                step(platform.capitalize())
                try:
                    ok, data = method(query)
                    results[platform] = {"success": ok, "data": data if ok else None,
                                          "error": "" if ok else data.get("error", "")}
                except Exception as e:
                    results[platform] = {"success": False, "error": str(e)}

        progress.progress(100, text="✅ Concluído!")
        st.session_state.tool_fullsearch_result = {"query": query, "results": results}

    # ── Exibe resultados ───────────────────────────────────────────────────
    fs = st.session_state.tool_fullsearch_result
    if not fs:
        return

    query   = fs["query"]
    results = fs["results"]

    # Calcula risk score
    risk = 0
    risk += min((results.get("breach", {}).get("count") or 0) * 15, 45)
    risk += min(len(results.get("stealer", {}).get("data") or []) * 20, 40)
    risk += min(len(results.get("holehe", {}).get("data") or []) * 3, 15)
    risk = min(risk, 100)
    if risk >= 75:   rc, rl = "#f85149", "CRÍTICO"
    elif risk >= 50: rc, rl = "#f0883e", "ALTO"
    elif risk >= 25: rc, rl = "#ffd700", "MÉDIO"
    else:            rc, rl = "#39d353", "BAIXO"

    # Painel de resumo
    found_modules = [k for k, v in results.items() if v.get("success") and (v.get("count") or v.get("data"))]
    failed_modules = [k for k, v in results.items() if not v.get("success")]

    cols = st.columns(4)
    cols[0].metric("🎯 Alvo", query[:20])
    cols[1].metric("Risk Score", f"{risk} — {rl}")
    cols[2].metric("✅ Módulos OK", len(found_modules))
    cols[3].metric("❌ Falhas", len(failed_modules))

    # Resultados por módulo
    if results.get("breach", {}).get("success") and results["breach"].get("data"):
        st.markdown("---")
        st.markdown("##### 💥 Vazamentos")
        breaches = results["breach"]["data"]
        has_discord = any(b.discord_id for b in breaches)
        rows = []
        for b in breaches[:10]:
            row = {"DB": b.dbname, "Email": b.email, "Username": b.username}
            if has_discord: row["Discord ID"] = b.discord_id
            row["País"] = b.country
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if results.get("stealer", {}).get("success") and results["stealer"].get("data"):
        st.markdown("---")
        st.markdown("##### 🦠 Stealer Logs")
        st.markdown('<div class="alert-danger">⚠️ Credenciais em logs de malware encontradas</div>', unsafe_allow_html=True)
        stealers = results["stealer"]["data"]
        st.dataframe(pd.DataFrame([{
            "URL": s.url[:50], "Username": s.username, "Domínio": ", ".join(s.domain[:1]) or "—"
        } for s in stealers[:10]]), use_container_width=True, hide_index=True)

    if results.get("holehe", {}).get("success") and results["holehe"].get("data"):
        st.markdown("---")
        st.markdown("##### 📧 Serviços com Conta (Holehe)")
        badges = "".join(f'<span class="platform-found">✓ {d}</span>' for d in results["holehe"]["data"])
        st.markdown(badges, unsafe_allow_html=True)

    if results.get("ip_info", {}).get("success"):
        st.markdown("---")
        st.markdown("##### 🌐 IP Info")
        d = results["ip_info"]["data"] or {}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("País", d.get("country", "—"))
        c2.metric("Cidade", d.get("city", "—"))
        c3.metric("ISP", (d.get("isp") or "—")[:20])
        c4.metric("Proxy/VPN", "⚠ Sim" if d.get("proxy") else "Não")

    if results.get("discord", {}).get("success") and results["discord"].get("data"):
        st.markdown("---")
        st.markdown("##### 🎮 Discord")
        d = results["discord"]["data"]
        st.markdown(f"**{d.get('global_name') or d.get('username', '—')}** · `@{d.get('username','—')}` · ID: `{d.get('id','—')}`")
        if d.get("avatar_url"):
            st.image(d["avatar_url"], width=64)

    for plat in ["steam", "xbox", "roblox"]:
        if results.get(plat, {}).get("success") and results[plat].get("data"):
            st.markdown("---")
            d = results[plat]["data"]
            st.markdown(f"##### {'🎮' if plat=='steam' else '🕹️' if plat=='xbox' else '🧱'} {plat.capitalize()}: **{d.get('username','—')}**")

    if results.get("subdomains", {}).get("success"):
        subs = results["subdomains"].get("data") or []
        if subs:
            st.markdown("---")
            st.markdown(f"##### 🔗 Subdomínios ({len(subs)} encontrados)")
            st.dataframe(pd.DataFrame({"Subdomínio": subs[:20]}), use_container_width=True, hide_index=True)

    # Módulos com falha
    if failed_modules:
        with st.expander(f"⚠️ Módulos sem resultado ({len(failed_modules)})"):
            for m in failed_modules:
                err = results[m].get("error", "sem dados")
                st.markdown(f"- **{m}**: `{err[:60]}`")


# ── IP Info ───────────────────────────────────────────────────────────────────

def _render_tool_ip():
    st.markdown("#### 🌐 IP Info — Geolocalização e Rede")
    st.caption("Retorna país, cidade, ISP, organização, fuso horário e detecta Proxy/VPN/Hosting.")

    # Pega prefill da sidebar se vier de busca específica
    prefill = st.session_state.pop("tool_ip_prefill", None) or {}
    default_val = prefill.get("query", "")

    col1, col2 = st.columns([3, 1])
    with col1:
        ip = st.text_input("IP", value=default_val,
                           placeholder="ex: 174.235.65.156", key="tool_ip_input",
                           label_visibility="collapsed")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run = st.button("🔍 Consultar", use_container_width=True, key="ip_run")

    # Auto-run se veio da sidebar com valor preenchido
    if (run or default_val) and ip.strip():
        with st.spinner("Consultando..."):
            client = OathnetClient(api_key=OATHNET_API_KEY)
            ok, data = client.ip_info(ip.strip())
            st.session_state.tool_ip_result = {"ok": ok, "data": data, "ip": ip.strip()}

    res = st.session_state.tool_ip_result
    if not res:
        return
    if not res["ok"]:
        st.markdown(f'<div class="alert-danger">❌ {res["data"].get("error","Falhou")}</div>', unsafe_allow_html=True)
        return

    d = res["data"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🌍 País",     f"{d.get('country','—')} ({d.get('countryCode','—')})")
    c2.metric("🏙️ Cidade",  d.get("city", "—"))
    c3.metric("📡 ISP",     (d.get("isp") or "—")[:22])
    c4.metric("🔒 Proxy/VPN", "⚠️ Sim" if d.get("proxy") else "Não")

    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Detalhes de Rede**")
        for k, v in [("Organização", d.get("org")), ("AS", d.get("as")),
                     ("Reverse DNS", d.get("reverse")), ("Fuso Horário", d.get("timezone"))]:
            if v:
                st.markdown(f"**{k}:** `{v}`")
    with col_b:
        st.markdown("**Flags de Segurança**")
        flags = [
            ("📱 Mobile",   d.get("mobile")),
            ("🔒 Proxy/VPN", d.get("proxy")),
            ("🖥️ Hosting",  d.get("hosting")),
        ]
        for label, val in flags:
            color = "#f0883e" if val else "#39d353"
            st.markdown(f'<span style="color:{color}">{"⚠️" if val else "✅"} {label}: {"Sim" if val else "Não"}</span>', unsafe_allow_html=True)

        if d.get("lat") and d.get("lon"):
            st.markdown(f"**📍 Coords:** `{d.get('lat')}, {d.get('lon')}`")


# ── Discord ───────────────────────────────────────────────────────────────────

def _render_tool_discord():
    st.markdown("#### 🎮 Discord Lookup")
    st.caption("Busca perfil público, histórico de usernames e conta Roblox vinculada pelo Discord ID (snowflake).")

    prefill = st.session_state.pop("tool_discord_prefill", None) or {}
    default_val = prefill.get("query", "")

    col1, col2 = st.columns([3, 1])
    with col1:
        did = st.text_input("Discord ID", value=default_val,
                            placeholder="ex: 352826996163739666  (somente números)",
                            key="tool_discord_input", label_visibility="collapsed")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run = st.button("🔍 Buscar", use_container_width=True, key="discord_run")

    if (run or default_val) and did.strip():
        import re as _re
        if not _re.match(r"^\d{14,19}$", did.strip()):
            st.markdown('<div class="alert-warning">⚠️ Discord ID deve conter 14–19 dígitos numéricos.</div>', unsafe_allow_html=True)
        else:
            with st.spinner("Consultando Discord..."):
                client = OathnetClient(api_key=OATHNET_API_KEY)
                ok_u, user    = client.discord_userinfo(did.strip())
                ok_h, history = client.discord_username_history(did.strip())
                ok_r, roblox  = client.discord_to_roblox(did.strip())
                st.session_state.tool_discord_result = {
                    "did": did.strip(),
                    "user": {"ok": ok_u, "data": user},
                    "history": {"ok": ok_h, "data": history},
                    "roblox": {"ok": ok_r, "data": roblox},
                }

    res = st.session_state.tool_discord_result
    if not res:
        return

    # Perfil
    st.markdown("---")
    st.markdown("##### 👤 Perfil")
    if res["user"]["ok"]:
        d = res["user"]["data"]
        col_a, col_b = st.columns([1, 4])
        with col_a:
            if d.get("avatar_url"):
                st.image(d["avatar_url"], width=72)
        with col_b:
            st.markdown(f"**{d.get('global_name') or d.get('username','—')}** · `@{d.get('username','—')}`")
            st.caption(f"ID: `{d.get('id','—')}` · Criado em: `{d.get('creation_date','—')}`")
            if d.get("badges"):
                st.markdown("🏅 " + " · ".join(d["badges"]))
    else:
        st.markdown(f'<div class="alert-warning">⚠️ {res["user"]["data"].get("error","Não encontrado")}</div>', unsafe_allow_html=True)

    # Histórico de usernames
    st.markdown("##### 📋 Histórico de Usernames")
    if res["history"]["ok"]:
        h = res["history"]["data"]
        entries = h.get("history", [])
        if entries:
            rows = []
            for e in entries:
                name = e.get("name", ["—"]); name = name[0] if isinstance(name, list) else name
                ts   = e.get("time",  ["—"]); ts   = ts[0][:19]  if isinstance(ts,   list) else str(ts)[:19]
                rows.append({"Username": name, "Data": ts})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption("Nenhum histórico disponível.")
    else:
        st.caption(f"Histórico indisponível: {res['history']['data'].get('error','')}")

    # Roblox vinculado
    st.markdown("##### 🧱 Conta Roblox Vinculada")
    if res["roblox"]["ok"] and res["roblox"]["data"].get("roblox_id"):
        d = res["roblox"]["data"]
        st.markdown(f"**Roblox ID:** `{d.get('roblox_id','—')}` · **Username:** `{d.get('name','—')}` · **Display:** `{d.get('displayName','—')}`")
        if d.get("avatar"):
            st.image(d["avatar"], width=64)
    else:
        st.caption("Nenhuma conta Roblox vinculada encontrada.")


# ── Gaming ────────────────────────────────────────────────────────────────────

def _render_tool_gaming():
    st.markdown("#### 🕹️ Gaming — Steam / Xbox / Roblox")
    st.caption("Busca perfis em plataformas de gaming pelo username ou ID.")

    prefill   = st.session_state.pop("tool_gaming_prefill", None) or {}
    pf_query  = prefill.get("query", "")
    pf_tipo   = prefill.get("tipo", "")

    # Se veio da sidebar com tipo específico, pre-seleciona a plataforma
    default_platform = {"Steam": "Steam", "Xbox": "Xbox", "Roblox": "Roblox"}.get(pf_tipo, "Steam")
    platform = st.radio("Plataforma", ["Steam", "Xbox", "Roblox"],
                        horizontal=True, key="gaming_platform",
                        index=["Steam","Xbox","Roblox"].index(default_platform))

    if platform == "Steam":
        placeholder = "Steam64 ID ou custom URL  (ex: 76561199443618616)"
    elif platform == "Xbox":
        placeholder = "Gamertag  (ex: ethan)"
    else:
        placeholder = "Username  (ex: chris)"

    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("ID / Username", value=pf_query,
                              placeholder=placeholder, key="tool_gaming_input",
                              label_visibility="collapsed")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run = st.button("🔍 Buscar", use_container_width=True, key="gaming_run")

    if (run or pf_query) and query.strip():
        with st.spinner(f"Consultando {platform}..."):
            client = OathnetClient(api_key=OATHNET_API_KEY)
            if platform == "Steam":
                ok, data = client.steam_lookup(query.strip())
            elif platform == "Xbox":
                ok, data = client.xbox_lookup(query.strip())
            else:
                ok, data = client.roblox_lookup(username=query.strip())
            st.session_state.tool_gaming_result = {
                "platform": platform, "query": query.strip(), "ok": ok, "data": data
            }

    res = st.session_state.tool_gaming_result
    if not res:
        return

    st.markdown("---")
    if not res["ok"]:
        st.markdown(f'<div class="alert-danger">❌ {res["data"].get("error","Perfil não encontrado")}</div>', unsafe_allow_html=True)
        return

    d = res["data"]
    plat = res["platform"]

    col_a, col_b = st.columns([1, 4])
    with col_a:
        if d.get("avatar"):
            st.image(d["avatar"], width=80)
    with col_b:
        st.markdown(f"### {d.get('username','—')}")
        if plat == "Steam":
            raw = d.get("raw_data", {})
            vis = {1:"🔒 Privado", 2:"👥 Amigos", 3:"🌐 Público"}.get(raw.get("communityvisibilitystate",0),"—")
            st.caption(f"Steam ID: `{d.get('id','—')}` · {vis}")
            if raw.get("profileurl"):
                st.markdown(f"[🔗 Ver perfil]({raw['profileurl']})")
        elif plat == "Xbox":
            meta = (d.get("meta") or {}).get("meta") or {}
            sc = d.get("scraper_data") or {}
            st.caption(f"XUID: `{(d.get('meta') or {}).get('id','—')}` · Tier: `{meta.get('accounttier','—')}` · Gamerscore: `{meta.get('gamerscore','—')}`")
            if sc.get("games_played"):
                st.metric("Jogos", sc["games_played"])
        else:
            st.caption(f"ID: `{d.get('user_id') or d.get('User ID','—')}` · Criado em: `{d.get('Join Date','—')[:10]}`")
            old = d.get("Old Usernames")
            if old and old != "None":
                st.caption(f"Usernames anteriores: {old}")


# ── Subdomínios ───────────────────────────────────────────────────────────────

def _render_tool_subdomain():
    st.markdown("#### 🔗 Enumeração de Subdomínios")
    st.caption("Descobre subdomínios conhecidos de um domínio usando os dados da OathNet.")

    prefill = st.session_state.pop("tool_subdomain_prefill", None) or {}
    default_val = prefill.get("query", "")

    col1, col2 = st.columns([3, 1])
    with col1:
        domain = st.text_input("Domínio", value=default_val,
                               placeholder="ex: example.com", key="tool_sub_input",
                               label_visibility="collapsed")
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run = st.button("🔍 Enumerar", use_container_width=True, key="sub_run")

    if (run or default_val) and domain.strip():
        with st.spinner("Buscando subdomínios..."):
            client = OathnetClient(api_key=OATHNET_API_KEY)
            ok, data = client.extract_subdomains(domain.strip())
            subs = data.get("subdomains", []) if ok else []
            st.session_state.tool_subdomain_result = {
                "domain": domain.strip(), "ok": ok,
                "data": subs, "error": "" if ok else data.get("error", "Falhou")
            }

    res = st.session_state.tool_subdomain_result
    if not res:
        return

    st.markdown("---")
    if not res["ok"]:
        st.markdown(f'<div class="alert-danger">❌ {res["error"]}</div>', unsafe_allow_html=True)
        return

    subs = res["data"]
    st.metric("Subdomínios encontrados", len(subs))
    if subs:
        # Mostrar em duas colunas
        col1, col2 = st.columns(2)
        mid = len(subs) // 2
        with col1:
            st.dataframe(pd.DataFrame({"Subdomínio": subs[:mid]}),
                         use_container_width=True, hide_index=True)
        with col2:
            st.dataframe(pd.DataFrame({"Subdomínio": subs[mid:]}),
                         use_container_width=True, hide_index=True)

        # Download
        st.download_button(
            "⬇️ Baixar lista (.txt)",
            data="\n".join(subs),
            file_name=f"subdomains_{res['domain']}.txt",
            mime="text/plain",
        )
    else:
        st.markdown('<div class="alert-success">✅ Nenhum subdomínio encontrado.</div>', unsafe_allow_html=True)


# ── File Search ───────────────────────────────────────────────────────────────

def _render_tool_filesearch():
    st.markdown("#### 📁 File Search — Busca em Arquivos de Vítimas")
    st.markdown('<div class="alert-warning">⚠️ Esta ferramenta busca dentro de arquivos capturados de máquinas comprometidas. Use com responsabilidade.</div>', unsafe_allow_html=True)
    st.markdown("")

    col1, col2 = st.columns([2, 1])
    with col1:
        expr = _tool_input("Expressão", "ex: password, @gmail.com, .*secret.*", "tool_fs_expr")
    with col2:
        mode = st.selectbox("Modo", ["literal", "wildcard", "regex"], key="tool_fs_mode", label_visibility="collapsed")

    run = st.button("🔍 Buscar em Arquivos", use_container_width=True, key="filesearch_run")

    if run and expr.strip():
        with st.spinner("Criando job de busca... pode levar até 30s."):
            import time as _time
            client  = OathnetClient(api_key=OATHNET_API_KEY)
            payload = {
                "expression":      expr.strip(),
                "search_mode":     mode,
                "include_matches": True,
                "case_sensitive":  False,
                "context_lines":   1,
            }
            ok, data = client._post("service/v2/file-search", payload)
            if not ok:
                st.session_state.tool_filesearch_result = {"ok": False, "error": data.get("error","Job creation failed")}
            else:
                job_id = (data.get("data") or data).get("job_id", "")
                result = None
                for _ in range(15):
                    _time.sleep(2)
                    ok2, jdata = client._get(f"service/v2/file-search/{job_id}")
                    if ok2:
                        status = (jdata.get("data") or jdata).get("status","")
                        if status in ("completed","canceled"):
                            result = jdata.get("data") or jdata
                            break
                st.session_state.tool_filesearch_result = {
                    "ok": result is not None,
                    "data": result,
                    "error": "Timeout" if result is None else "",
                }

    res = st.session_state.tool_filesearch_result
    if not res:
        return

    st.markdown("---")
    if not res["ok"]:
        st.markdown(f'<div class="alert-danger">❌ {res.get("error","Falhou")}</div>', unsafe_allow_html=True)
        return

    data    = res["data"] or {}
    matches = data.get("matches", [])
    summary = data.get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📄 Arquivos escaneados", summary.get("files_scanned","—"))
    c2.metric("✅ Arquivos com match",  summary.get("files_matched","—"))
    c3.metric("🔍 Total de matches",   summary.get("matches","—"))
    c4.metric("📊 Bytes escaneados",   summary.get("bytes_scanned","—"))

    if matches:
        st.markdown("**Matches encontrados:**")
        rows = []
        for m in matches[:50]:
            rows.append({
                "Arquivo":   m.get("file_name","—"),
                "Log ID":    (m.get("log_id") or "")[:20],
                "Linha":     m.get("line_number","—"),
                "Match":     (m.get("match_text") or "")[:80],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.markdown('<div class="alert-success">✅ Nenhum match encontrado.</div>', unsafe_allow_html=True)


# ── Owner debug panel ─────────────────────────────────────────────────────────

def _render_owner_debug():
    """
    Painel de debug visível APENAS para o dono do app.
    Acesse via: https://seuapp.streamlit.app/?debug=owner
    """
    import platform as _platform
    import sys

    st.markdown("## 🔧 Owner Debug Panel")
    st.caption("Visível apenas via `?debug=owner` na URL — não aparece para outros usuários.")
    st.markdown("---")

    # ── Status da API ──────────────────────────────────────────────────────
    st.markdown("### 🔑 API Status")
    key_display = OATHNET_API_KEY[:8] + "..." + OATHNET_API_KEY[-4:] if OATHNET_API_KEY else "❌ NÃO DEFINIDA"
    st.code(f"OATHNET_API_KEY = {key_display}\nBASE_URL        = {OATHNET_BASE_URL}", language="bash")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔌 Testar Conexão OathNet", key="dbg_test_conn"):
            with st.spinner("Testando..."):
                try:
                    client = OathnetClient(api_key=OATHNET_API_KEY)
                    ok, msg = client.validate_key()
                    st.success(f"✅ {msg}") if ok else st.error(f"❌ {msg}")
                except Exception as exc:
                    st.error(f"❌ Exceção: {exc}")
    with col2:
        if st.button("📡 Ping HTTP Raw", key="dbg_ping"):
            import requests as _req
            try:
                r = _req.get(OATHNET_BASE_URL, headers={"x-api-key": OATHNET_API_KEY}, timeout=8)
                st.info(f"HTTP {r.status_code} · {len(r.content)} bytes · {r.elapsed.total_seconds():.2f}s")
                with st.expander("Response Body"):
                    st.code(r.text[:2000])
            except Exception as exc:
                st.error(f"❌ {exc}")

    st.markdown("---")

    # ── Debug log ──────────────────────────────────────────────────────────
    st.markdown("### 📋 Log da Última Investigação")
    logs = st.session_state.get("debug_log", [])
    level_colors = {"OK": "#39d353", "INFO": "#00d4ff", "WARN": "#f0883e", "ERROR": "#f85149"}

    if not logs:
        st.info("Nenhum log. Execute uma investigação primeiro.")
    else:
        col_f, col_c = st.columns([3, 1])
        with col_f:
            show = st.multiselect("Níveis", ["OK","INFO","WARN","ERROR"],
                                  default=["OK","INFO","WARN","ERROR"], key="dbg_levels")
        with col_c:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗑️ Limpar", key="dbg_clear"):
                st.session_state.debug_log = []
                st.rerun()

        filtered = [e for e in logs if e["level"] in show]
        lines = []
        for e in filtered:
            color  = level_colors.get(e["level"], "#e6edf3")
            detail = (f"<br><span style='color:#8b949e;font-size:.75rem;white-space:pre-wrap'>"
                      f"{e['detail'][:500]}</span>") if e.get("detail") else ""
            lines.append(
                f'<div style="border-bottom:1px solid #30363d;padding:5px 0">'
                f'<span style="color:#8b949e">{e["ts"]}</span> '
                f'<span style="color:{color};font-weight:700">[{e["level"]}]</span> '
                f'<span style="color:#00d4ff">[{e["module"]}]</span> '
                f'<span style="color:#e6edf3">{e["msg"]}</span>{detail}</div>'
            )
        st.markdown(
            '<div style="background:#0d1117;border:1px solid #30363d;border-radius:6px;'
            'padding:12px;font-family:monospace;font-size:.8rem;max-height:400px;overflow-y:auto">'
            + "\n".join(lines) + "</div>", unsafe_allow_html=True,
        )
        log_txt = "\n".join(
            f"[{e['ts']}][{e['level']}][{e['module']}] {e['msg']}" +
            (f"\n  {e['detail']}" if e.get("detail") else "")
            for e in logs
        )
        st.download_button("⬇️ Exportar log .txt", data=log_txt,
                           file_name=f"nexus_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                           key="dbg_download")

    st.markdown("---")

    # ── OathNet raw response ───────────────────────────────────────────────
    oath = st.session_state.get("oathnet_result")
    if oath:
        st.markdown("### 💥 OathNet Raw Response")
        c1, c2, c3 = st.columns(3)
        c1.metric("success",       str(oath.success))
        c2.metric("breach_count",  oath.breach_count)
        c3.metric("stealer_count", oath.stealer_count)
        if oath.error:
            st.error(f"Erro: {oath.error}")
        with st.expander("raw_response JSON"):
            st.json(oath.raw_response or {})
        st.markdown("---")

    # ── Session state ──────────────────────────────────────────────────────
    st.markdown("### 🧠 Session State")
    safe = {k: v for k, v in st.session_state.items()
            if k not in ("oathnet_result","sherlock_result","tool_fullsearch_result")}
    st.json(safe, expanded=False)
    st.markdown("---")

    # ── Ambiente ───────────────────────────────────────────────────────────
    st.markdown("### ⚙️ Ambiente")
    st.json({
        "python":      sys.version,
        "platform":    _platform.platform(),
        "streamlit":   st.__version__,
        "api_key_set": bool(OATHNET_API_KEY),
        "debug_mode":  DEBUG_MODE,
        "base_url":    OATHNET_BASE_URL,
    })


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import re

    _init_state()

    # ── Owner debug panel via URL param ?debug=owner ──────────────────────
    try:
        if st.query_params.get("debug") == "owner":
            _render_header()
            _render_owner_debug()
            return
    except Exception:
        pass

    if not _check_password():
        return

    _render_header()
    _render_sidebar()

    oath: Optional[OathnetResult]   = st.session_state.oathnet_result
    sherl: Optional[SherlockResult] = st.session_state.sherlock_result

    # ── Abas sempre visíveis ──────────────────────────────────────────────
    tab_labels = ["🔍 Buscar", "📊 Resultados", "💥 Vazamentos",
                  "🌐 Redes Sociais", "🛠️ Ferramentas", "📤 Exportar"]
    if DEBUG_MODE:
        tab_labels.append("🔧 Debug")

    tabs = st.tabs(tab_labels)

    with tabs[0]:
        # Hub de busca sempre visível na primeira aba
        _render_welcome()

    with tabs[1]:
        if not st.session_state.investigation:
            st.markdown('<div class="alert-info">ℹ️ Faça uma busca na aba <b>🔍 Buscar</b> para ver os resultados aqui.</div>', unsafe_allow_html=True)
        else:
            _render_tab_summary(oath, sherl)
            _render_hub_extras()

    with tabs[2]:
        _render_tab_oathnet(oath)

    with tabs[3]:
        _render_tab_sherlock(sherl)

    with tabs[4]:
        _render_tab_tools()

    with tabs[5]:
        _render_tab_export(oath, sherl)

    if DEBUG_MODE:
        with tabs[6]:
            _render_tab_debug(oath, sherl)


def _render_hub_extras():
    """Exibe resultados extras do hub (Discord, Gaming, IP, etc.) abaixo do resumo."""
    extra = st.session_state.get("hub_extra", {})
    if not extra:
        return

    if extra.get("ip_info", {}).get("ok"):
        st.markdown("---")
        st.subheader("🌐 IP Info")
        d = extra["ip_info"]["data"] or {}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("País",     f"{d.get('country','—')} ({d.get('countryCode','—')})")
        c2.metric("Cidade",   d.get("city","—"))
        c3.metric("ISP",      (d.get("isp") or "—")[:22])
        c4.metric("Proxy/VPN","⚠️ Sim" if d.get("proxy") else "Não")

    if extra.get("discord", {}).get("user", {}).get("ok"):
        st.markdown("---")
        st.subheader("🎮 Discord")
        d = extra["discord"]["user"]["data"] or {}
        col_a, col_b = st.columns([1,4])
        with col_a:
            if d.get("avatar_url"): st.image(d["avatar_url"], width=64)
        with col_b:
            st.markdown(f"**{d.get('global_name') or d.get('username','—')}** `@{d.get('username','—')}`")
            st.caption(f"ID: `{d.get('id','—')}` · Criado: `{d.get('creation_date','—')}`")
        hist = extra["discord"].get("history", {})
        if hist.get("ok") and hist.get("data", {}).get("history"):
            rows = []
            for e in hist["data"]["history"]:
                name = e.get("name",["—"]); name = name[0] if isinstance(name, list) else name
                ts   = e.get("time",["—"]); ts = ts[0][:19] if isinstance(ts, list) else str(ts)[:19]
                rows.append({"Username": name, "Data": ts})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    for plat, icon in [("steam","🎮"),("xbox","🕹️"),("roblox","🧱")]:
        pdata = extra.get(plat, {})
        if pdata.get("ok") and pdata.get("data"):
            st.markdown("---")
            d = pdata["data"]
            col_a, col_b = st.columns([1,4])
            with col_a:
                if d.get("avatar"): st.image(d["avatar"], width=64)
            with col_b:
                st.subheader(f"{icon} {plat.capitalize()}: {d.get('username','—')}")

    if extra.get("subdomains", {}).get("ok"):
        subs = extra["subdomains"].get("data",[])
        if subs:
            st.markdown("---")
            st.subheader(f"🔗 Subdomínios ({len(subs)})")
            st.dataframe(pd.DataFrame({"Subdomínio": subs[:30]}), use_container_width=True, hide_index=True)

    if extra.get("ghunt", {}).get("ok"):
        st.markdown("---")
        st.subheader("🔍 Google (GHunt)")
        g = extra["ghunt"].get("data") or {}
        profile = g.get("data", {}).get("profile") or g
        if isinstance(profile, dict):
            for k, v in profile.items():
                if v: st.markdown(f"**{k}:** `{v}`")


def _render_welcome():
    """
    Hub de pesquisa central estilo OathNet.
    Barra de busca + categorias + módulos selecionáveis.
    """
    import re as _re

    # ── CSS extra para o hub ───────────────────────────────────────────────
    st.markdown("""
    <style>
    .hub-wrap {
        max-width: 820px; margin: 32px auto 0; padding: 0 8px;
    }
    .hub-search-box {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 14px;
        padding: 20px 24px 18px;
        margin-bottom: 18px;
        box-shadow: 0 8px 32px rgba(0,0,0,.4), 0 0 0 1px rgba(255,255,255,.03) inset;
        transition: border-color .2s;
    }
    .hub-search-box:hover { border-color: #00d4ff44; }
    .hub-cat-row {
        display: flex; gap: 8px; flex-wrap: wrap;
        margin: 12px 0 6px;
    }
    .hub-cat {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 6px 14px; border-radius: 999px; cursor: pointer;
        border: 1px solid #30363d; background: rgba(255,255,255,.03);
        color: #8b949e; font-size: .83rem; transition: all .15s;
        user-select: none;
    }
    .hub-cat:hover { border-color: #00d4ff66; color: #e6edf3; }
    .hub-cat.active { background: rgba(0,212,255,.12); border-color: #00d4ff; color: #00d4ff; font-weight: 600; }
    .hub-mod-row {
        display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 2px;
    }
    .hub-mod {
        display: inline-flex; align-items: center; gap: 5px;
        padding: 5px 12px; border-radius: 8px; cursor: pointer;
        border: 1px solid #30363d; background: rgba(255,255,255,.02);
        color: #8b949e; font-size: .78rem; transition: all .15s;
        user-select: none;
    }
    .hub-mod:hover { border-color: #8b949e; color: #e6edf3; }
    .hub-mod.active { background: rgba(139,92,246,.15); border-color: #7c3aed; color: #c4b5fd; }
    .hub-footer {
        display: flex; align-items: center; gap: 18px;
        margin-top: 14px; color: #8b949e; font-size: .78rem;
    }
    .hub-footer span { display:flex; align-items:center; gap:5px; }
    .hub-stats {
        display: grid; grid-template-columns: repeat(3,1fr); gap: 12px;
        margin: 20px 0 0;
    }
    .hub-stat {
        background: #161b22; border: 1px solid #30363d; border-radius: 10px;
        padding: 14px 16px; text-align: center;
    }
    .hub-stat-n { font-size: 1.4rem; font-weight: 800; color: #00d4ff; }
    .hub-stat-l { font-size: .72rem; color: #8b949e; margin-top: 2px; }
    </style>
    """, unsafe_allow_html=True)

    # ── Título ─────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="text-align:center;padding:8px 0 20px">'
        '<span style="font-size:2.2rem;font-weight:900;color:#e6edf3;letter-spacing:.06em">⬡ NexusOSINT</span><br>'
        '<span style="color:#8b949e;font-size:.9rem">Plataforma de investigação OSINT · Powered by OathNet + Sherlock</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Categorias e módulos disponíveis ───────────────────────────────────
    CATEGORIES = {
        "Data Leaks": {
            "icon": "🛡️",
            "color": "#f85149",
            "modules": {
                "breaches":  ("🔓", "Breaches",    "Banco de dados vazados"),
                "stealer":   ("📋", "Stealer Logs", "Credenciais de malware"),
            }
        },
        "Social & Gaming": {
            "icon": "🎮",
            "color": "#a78bfa",
            "modules": {
                "sherlock":  ("🌐", "Sherlock",    "25+ redes sociais"),
                "discord":   ("💬", "Discord",     "Perfil + histórico"),
                "steam":     ("🎮", "Steam",       "Perfil Steam"),
                "xbox":      ("🕹️", "Xbox",        "Perfil Xbox"),
                "roblox":    ("🧱", "Roblox",      "Perfil Roblox"),
            }
        },
        "Email Intelligence": {
            "icon": "📧",
            "color": "#39d353",
            "modules": {
                "holehe":    ("📨", "Holehe",      "Serviços cadastrados"),
                "ghunt":     ("🔍", "GHunt",       "Conta Google"),
            }
        },
        "Network": {
            "icon": "🌐",
            "color": "#00d4ff",
            "modules": {
                "ip_info":   ("📍", "IP Info",     "Geolocalização e rede"),
                "subdomain": ("🔗", "Subdomínios", "Enumeração de subdomínios"),
            }
        },
    }

    # ── Session state para hub ─────────────────────────────────────────────
    if "hub_active_cat" not in st.session_state:
        st.session_state.hub_active_cat = "Data Leaks"
    if "hub_active_mods" not in st.session_state:
        # Por padrão, todos os módulos da categoria ativa marcados
        st.session_state.hub_active_mods = set(CATEGORIES["Data Leaks"]["modules"].keys())
    if "hub_query" not in st.session_state:
        st.session_state.hub_query = ""

    st.markdown('<div class="hub-wrap">', unsafe_allow_html=True)

    # ── Barra de busca ─────────────────────────────────────────────────────
    st.markdown('<div class="hub-search-box">', unsafe_allow_html=True)

    col_input, col_btn = st.columns([5, 1])
    with col_input:
        query = st.text_input(
            "query",
            placeholder="e.g. username: winterfox · email · IP · Discord ID · domínio",
            key="hub_query_input",
            label_visibility="collapsed",
        )
    with col_btn:
        search_clicked = st.button("Search →", use_container_width=True, key="hub_search_btn",
                                   type="primary")

    # ── Toggle Automated / Manual ──────────────────────────────────────────
    col_mode, col_info = st.columns([2, 5])
    with col_mode:
        mode = st.radio("Modo", ["Automated", "Manual"], horizontal=True,
                        key="hub_mode", label_visibility="collapsed")
    with col_info:
        st.markdown(
            '<div style="display:flex;gap:18px;align-items:center;padding-top:6px;color:#8b949e;font-size:.78rem">'
            '<span>📦 Bulk Search</span><span>🛡 Secure Search</span><span>📊 15+ Sources</span>'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── Categoria pills ────────────────────────────────────────────────────
    st.markdown('<div class="hub-cat-row">', unsafe_allow_html=True)
    cat_cols = st.columns(len(CATEGORIES))
    for i, (cat_name, cat_data) in enumerate(CATEGORIES.items()):
        with cat_cols[i]:
            is_active = st.session_state.hub_active_cat == cat_name
            if st.button(
                f"{cat_data['icon']} {cat_name}",
                key=f"hub_cat_{cat_name}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.hub_active_cat = cat_name
                # Seleciona todos os módulos da nova categoria
                st.session_state.hub_active_mods = set(cat_data["modules"].keys())
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Módulo chips (sub-seleção dentro da categoria) ─────────────────────
    active_cat   = st.session_state.hub_active_cat
    active_mods  = st.session_state.hub_active_mods
    cat_modules  = CATEGORIES[active_cat]["modules"]

    # Em modo Manual: mostra chips individuais para selecionar/desselecionar
    if mode == "Manual":
        mod_cols = st.columns(len(cat_modules))
        for i, (mod_key, (icon, label, desc)) in enumerate(cat_modules.items()):
            with mod_cols[i]:
                is_sel = mod_key in active_mods
                if st.button(
                    f"{icon} {label}",
                    key=f"hub_mod_{mod_key}",
                    use_container_width=True,
                    type="primary" if is_sel else "secondary",
                    help=desc,
                ):
                    mods = set(active_mods)
                    if mod_key in mods:
                        mods.discard(mod_key)
                    else:
                        mods.add(mod_key)
                    st.session_state.hub_active_mods = mods
                    st.rerun()
    else:
        # Automated: mostra apenas quais módulos vão rodar (não selecionável)
        chips_html = "".join(
            f'<span style="display:inline-flex;align-items:center;gap:5px;padding:5px 12px;'
            f'border-radius:8px;border:1px solid #30363d;background:rgba(0,212,255,.08);'
            f'color:#00d4ff;font-size:.78rem;margin:2px">{icon} {label}</span>'
            for mod_key, (icon, label, _) in cat_modules.items()
        )
        st.markdown(f'<div style="margin:8px 0">{chips_html}</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)  # hub-search-box

    # ── Executar busca ─────────────────────────────────────────────────────
    if search_clicked and query.strip():
        _run_hub_search(query.strip(), active_cat, active_mods, mode)

    st.markdown('</div>', unsafe_allow_html=True)  # hub-wrap


def _run_hub_search(query: str, category: str, selected_mods: set, mode: str):
    """
    Executa os módulos selecionados e armazena resultado no session_state
    para exibição nas abas.
    """
    import re as _re
    client = OathnetClient(api_key=OATHNET_API_KEY)

    # Detecta tipo automaticamente
    is_email_q   = "@" in query
    is_ip_q      = bool(_re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", query))
    is_discord_q = bool(_re.match(r"^\d{14,19}$", query))
    is_domain_q  = ("." in query and not is_ip_q and not is_email_q
                    and not query.replace(".","").isdigit())
    is_username_q = not is_email_q and not is_ip_q and not is_discord_q and not is_domain_q

    # Monta lista de módulos a rodar
    # Automated → roda tudo que faz sentido para o tipo detectado (ignora categoria)
    # Manual → só os módulos selecionados da categoria ativa
    if mode == "Automated":
        run_breach   = True
        run_stealer  = True
        run_sherlock = is_email_q or is_username_q   # ← sempre para nomes/usernames
        run_discord  = is_discord_q
        run_steam    = is_username_q
        run_xbox     = is_username_q
        run_roblox   = is_username_q
        run_holehe   = is_email_q
        run_ghunt    = is_email_q
        run_ip       = is_ip_q
        run_subdomain= is_domain_q
    else:
        # Manual: só os módulos que o usuário selecionou
        run_breach   = "breaches"  in selected_mods
        run_stealer  = "stealer"   in selected_mods
        run_sherlock = "sherlock"  in selected_mods and (is_email_q or is_username_q)
        run_discord  = "discord"   in selected_mods and (is_discord_q or is_username_q)
        run_steam    = "steam"     in selected_mods and is_username_q
        run_xbox     = "xbox"      in selected_mods and is_username_q
        run_roblox   = "roblox"    in selected_mods and is_username_q
        run_holehe   = "holehe"    in selected_mods and is_email_q
        run_ghunt    = "ghunt"     in selected_mods and is_email_q
        run_ip       = "ip_info"   in selected_mods and is_ip_q
        run_subdomain= "subdomain" in selected_mods and is_domain_q

    total_mods = sum([run_breach, run_stealer, run_sherlock, run_discord,
                      run_steam, run_xbox, run_roblox, run_holehe, run_ghunt,
                      run_ip, run_subdomain])

    if total_mods == 0:
        st.warning("⚠️ Nenhum módulo compatível com este tipo de dado para a categoria selecionada. "
                   "Tente outra categoria ou o Full Search.")
        return

    progress = st.progress(0, text="Iniciando...")
    done = [0]

    def step(label: str):
        done[0] += 1
        progress.progress(min(int(done[0] / total_mods * 100), 100), text=f"🔄 {label}...")

    # Resultados que alimentam as abas normais
    oath_result  = None
    sherl_result = None
    extra        = {}  # resultados extras (discord, gaming, ip, etc.)

    # ── Breach ──────────────────────────────────────────────────────────
    if run_breach or run_stealer:
        step("Vazamentos")
        try:
            res = client.search_breach(query)
            if run_stealer:
                step("Stealer logs")
                sts = client.search_stealer_v2(query)
                res.stealers       = sts.stealers
                res.stealers_found = sts.stealers_found
            if run_holehe and is_email_q:
                step("Holehe")
                h = client.holehe(query)
                res.holehe_domains = h.holehe_domains
            oath_result = res
        except Exception as e:
            st.error(f"Erro OathNet: {e}")

    # ── Sherlock ─────────────────────────────────────────────────────────
    if run_sherlock:
        step("Sherlock (redes sociais)")
        try:
            sherl_result = search_username(
                query if is_username_q else query.split("@")[0],
                prefer_cli=False,
            )
        except Exception as e:
            st.error(f"Erro Sherlock: {e}")

    # ── GHunt ─────────────────────────────────────────────────────────────
    if run_ghunt and is_email_q:
        step("GHunt")
        try:
            ok, data = client._get("service/ghunt", params={"email": query})
            extra["ghunt"] = {"ok": ok, "data": data.get("data", data) if ok else None}
        except Exception:
            pass

    # ── Discord ───────────────────────────────────────────────────────────
    if run_discord and is_discord_q:
        step("Discord")
        try:
            ok_u, user = client.discord_userinfo(query)
            ok_h, hist = client.discord_username_history(query)
            extra["discord"] = {"user": {"ok": ok_u, "data": user if ok_u else None},
                                 "history": {"ok": ok_h, "data": hist if ok_h else None}}
        except Exception:
            pass

    # ── Gaming ────────────────────────────────────────────────────────────
    for key, flag, method in [
        ("steam",  run_steam,  lambda q: client.steam_lookup(q)),
        ("xbox",   run_xbox,   lambda q: client.xbox_lookup(q)),
        ("roblox", run_roblox, lambda q: client.roblox_lookup(username=q)),
    ]:
        if flag:
            step(key.capitalize())
            try:
                ok, data = method(query)
                extra[key] = {"ok": ok, "data": data if ok else None,
                               "error": "" if ok else data.get("error","")}
            except Exception:
                pass

    # ── IP Info ───────────────────────────────────────────────────────────
    if run_ip:
        step("IP Info")
        try:
            ok, data = client.ip_info(query)
            extra["ip_info"] = {"ok": ok, "data": data if ok else None}
        except Exception:
            pass

    # ── Subdomains ────────────────────────────────────────────────────────
    if run_subdomain:
        step("Subdomínios")
        try:
            ok, data = client.extract_subdomains(query)
            extra["subdomains"] = {"ok": ok, "data": data.get("subdomains",[]) if ok else []}
        except Exception:
            pass

    progress.progress(100, text="✅ Concluído!")

    # Salva nos resultados da investigação
    st.session_state.oathnet_result  = oath_result
    st.session_state.sherlock_result = sherl_result
    st.session_state.hub_extra       = extra
    st.session_state.investigation   = {
        "target":      query,
        "target_type": "Auto",
        "timestamp":   datetime.now().isoformat(),
        "category":    category,
        "modules":     list(selected_mods),
    }

    if oath_result or sherl_result:
        _add_case(query, category, oath_result, sherl_result)

    st.rerun()


if __name__ == "__main__":
    import re
    main()