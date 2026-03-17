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
        "breach_page":      0,        # ← paginação de breaches
        "discord_lookups":  {},       # ← cache discord_id → dados do perfil
        "authenticated":    False,    # ← controle de senha
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
        st.markdown("### 🗂️ Gerenciador de Casos")
        st.markdown("---")

        # ── New investigation form ─────────────────────────────────────
        st.markdown("**Nova Investigação**")
        target = st.text_input(
            "Alvo",
            placeholder="email@example.com ou username",
            key="target_input",
            label_visibility="collapsed",
        )
        col1, col2 = st.columns(2)
        with col1:
            target_type = st.selectbox("Tipo", ["Email", "Username"], label_visibility="collapsed")
        with col2:
            prefer_cli = st.checkbox("CLI Sherlock", value=False, help="Usa o Sherlock oficial via subprocess se instalado")

        if st.button("🔍 Investigar", use_container_width=True):
            if target.strip():
                st.session_state.target = target.strip()
                st.session_state.target_type = target_type
                st.session_state.prefer_cli = prefer_cli
                st.session_state.running = True
                st.rerun()
            else:
                st.warning("Digite um alvo válido.")

        st.markdown("---")

        # ── Case history ───────────────────────────────────────────────
        st.markdown("**Histórico de Casos**")
        if not st.session_state.cases:
            st.caption("_Nenhum caso registrado ainda._")
        else:
            if st.button("🗑️ Limpar Histórico", use_container_width=True):
                st.session_state.cases = []
                CASES_FILE.unlink(missing_ok=True)
                st.rerun()

            for case in st.session_state.cases[:15]:
                label, color = _risk_label(case["risk_score"])
                is_active = case["id"] == st.session_state.active_case_id
                badge = "🔴" if label == "CRÍTICO" else "🟠" if label == "ALTO" else "🟡" if label == "MÉDIO" else "🟢"
                st.markdown(
                    f"""<div class="case-card {'case-card-active' if is_active else ''}">
                        <div class="case-target">{badge} {case['target']}</div>
                        <div class="case-meta">{case['target_type']} · Risk {case['risk_score']} · {case['timestamp'][:16]}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

        st.markdown("---")
        st.caption(f"NexusOSINT {APP_VERSION} · For legal & ethical use only.")


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


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import re

    _init_state()

    # ── Password gate ─────────────────────────────────────────────────────
    if not _check_password():
        return

    _render_header()
    _render_sidebar()

    # Trigger investigation if running flag is set
    if st.session_state.running:
        st.session_state.running = False
        _run_investigation(st.session_state.target, st.session_state.target_type)
        st.rerun()

    oath: Optional[OathnetResult] = st.session_state.oathnet_result
    sherl: Optional[SherlockResult] = st.session_state.sherlock_result

    if not st.session_state.investigation:
        # Welcome screen
        st.markdown(
            """
            <div style="text-align:center; padding: 60px 0 40px;">
                <div style="font-size:4rem;">🔍</div>
                <h2 style="color:#00d4ff; letter-spacing:0.1em;">Bem-vindo ao NexusOSINT</h2>
                <p style="color:#8b949e; max-width:500px; margin:0 auto; line-height:1.7;">
                    Plataforma modular de investigação OSINT para análise de emails e
                    usernames. Use a sidebar para iniciar uma investigação.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.markdown("### 💥 Vazamentos\nConsulta a API Oathnet para verificar se o alvo aparece em bases de dados comprometidas.")
        c2.markdown("### 🌐 Redes Sociais\nVerifica presença pública em 25+ plataformas usando o motor Sherlock.")
        c3.markdown("### 📤 Exportar\nExporte relatórios completos em JSON ou Excel para documentação de casos.")

        # Debug tab only visible when DEBUG=true (local dev)
        if DEBUG_MODE:
            st.markdown("---")
            _tab_debug_pre, = st.tabs(["🛠️ Diagnóstico de Ambiente"])
            with _tab_debug_pre:
                _render_tab_debug(None, None)
        return

    # Tabs — Debug tab only shown in DEBUG mode
    if DEBUG_MODE:
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Resumo", "💥 Vazamentos (Oathnet)", "🌐 Redes Sociais (Sherlock)", "📤 Exportar", "🛠️ Debug"])
        with tab5:
            _render_tab_debug(oath, sherl)
    else:
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Resumo", "💥 Vazamentos (Oathnet)", "🌐 Redes Sociais (Sherlock)", "📤 Exportar"])

    with tab1:
        _render_tab_summary(oath, sherl)
    with tab2:
        _render_tab_oathnet(oath)
    with tab3:
        _render_tab_sherlock(sherl)
    with tab4:
        _render_tab_export(oath, sherl)


if __name__ == "__main__":
    import re
    main()