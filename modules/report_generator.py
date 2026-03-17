"""
NexusOSINT — Report Generator
Produces two export formats:
  1. HTML  — dark-mode, OathNet-style (collapsibles, copy buttons, glow)
  2. PDF   — clean light, OSINT-Industries-style (cover, ToC, modules, timeline)
"""

from __future__ import annotations

import io
import textwrap
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .oathnet_client import OathnetResult
    from .sherlock_wrapper import SherlockResult

APP_VERSION = "1.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
# ── HTML REPORT ────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def _e(s: str) -> str:
    """HTML-escape a string."""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def generate_html(
    target: str,
    target_type: str,
    oath: Optional["OathnetResult"],
    sherl: Optional["SherlockResult"],
    risk_score: int,
    timestamp: str,
) -> str:

    now_str = timestamp or datetime.now().isoformat()

    # ── Risk colour ───────────────────────────────────────────────────────────
    if risk_score >= 75:
        risk_color, risk_label = "#f85149", "CRÍTICO"
    elif risk_score >= 50:
        risk_color, risk_label = "#f0883e", "ALTO"
    elif risk_score >= 25:
        risk_color, risk_label = "#ffd700", "MÉDIO"
    else:
        risk_color, risk_label = "#39d353", "BAIXO"

    # ── Build ToC entries ─────────────────────────────────────────────────────
    toc_items = []
    sections  = []

    # ── Section: Overview ─────────────────────────────────────────────────────
    breach_n  = oath.breach_count  if oath else 0
    stealer_n = oath.stealer_count if oath else 0
    holehe_n  = len(oath.holehe_domains) if oath else 0
    social_n  = sherl.found_count if sherl else 0
    toc_items.append('<li><a href="#overview">Visão Geral</a></li>')
    sections.append(f"""
<section id="overview" class="card">
  <h2 class="card-title">Visão Geral da Investigação</h2>
  <div class="grid stats">
    <div class="stat"><div class="stat-label">Alvo</div><div class="stat-value">{_e(target)}</div></div>
    <div class="stat"><div class="stat-label">Tipo</div><div class="stat-value">{_e(target_type)}</div></div>
    <div class="stat"><div class="stat-label">Risk Score</div>
      <div class="stat-value" style="color:{risk_color}">{risk_score} <span style="font-size:14px">{risk_label}</span></div>
    </div>
    <div class="stat"><div class="stat-label">Gerado em</div><div class="stat-value" style="font-size:13px">{_e(now_str[:19].replace("T"," "))}</div></div>
  </div>
  <div class="grid stats" style="margin-top:12px">
    <div class="stat"><div class="stat-label">💥 Vazamentos</div><div class="stat-value">{breach_n}</div></div>
    <div class="stat"><div class="stat-label">🦠 Stealer Logs</div><div class="stat-value">{stealer_n}</div></div>
    <div class="stat"><div class="stat-label">📧 Serviços (Holehe)</div><div class="stat-value">{holehe_n}</div></div>
    <div class="stat"><div class="stat-label">🌐 Redes Sociais</div><div class="stat-value">{social_n}</div></div>
  </div>
</section>""")

    # ── Section: Breach logs ──────────────────────────────────────────────────
    if oath and oath.breaches:
        toc_items.append(f'<li><a href="#breaches">Vazamentos ({breach_n})</a></li>')
        rows = ""
        for i, b in enumerate(oath.breaches, 1):
            fields = [
                ("dbname",   b.dbname),
                ("email",    b.email),
                ("username", b.username),
                ("password", b.password),
                ("ip",       b.ip),
                ("country",  b.country),
                ("date",     b.date[:10] if b.date else ""),
            ]
            kv_rows = "".join(
                f'<tr><th>{_e(k)}</th><td><button class="copy-btn" data-copy="{_e(v)}">Copy</button>{_e(v)}</td></tr>'
                for k, v in fields if v
            )
            rows += f"""
<details class="details anchor" id="breach-{i}">
  <summary><span class="badge">#{i}</span> {_e(b.dbname or "unknown")}</summary>
  <table class="kv"><tbody>{kv_rows}</tbody></table>
</details>"""
        sections.append(f"""
<section id="breaches" class="card page-break">
  <h2 class="card-title">💥 Vazamentos de Dados ({breach_n})</h2>
  <div class="list">{rows}</div>
</section>""")

    # ── Section: Stealer logs ─────────────────────────────────────────────────
    if oath and oath.stealers:
        toc_items.append(f'<li><a href="#stealers">Stealer Logs ({stealer_n})</a></li>')
        rows = ""
        for i, s in enumerate(oath.stealers, 1):
            domain_str = ", ".join(s.domain[:3]) if s.domain else ""
            email_str  = ", ".join(s.email[:3]) if s.email else ""
            fields = [
                ("url",      s.url),
                ("username", s.username),
                ("password", s.password),
                ("domain",   domain_str),
                ("email",    email_str),
                ("pwned_at", s.pwned_at[:10] if s.pwned_at else ""),
                ("log_id",   s.log_id),
            ]
            kv_rows = "".join(
                f'<tr><th>{_e(k)}</th><td><button class="copy-btn" data-copy="{_e(v)}">Copy</button>{_e(v)}</td></tr>'
                for k, v in fields if v
            )
            rows += f"""
<details class="details anchor" id="stealer-{i}">
  <summary><span class="badge badge-red">#{i}</span> {_e(s.url[:60] if s.url else "unknown")}</summary>
  <table class="kv"><tbody>{kv_rows}</tbody></table>
</details>"""
        sections.append(f"""
<section id="stealers" class="card page-break">
  <h2 class="card-title">🦠 Stealer Logs — Credenciais Roubadas por Malware ({stealer_n})</h2>
  <div class="alert-banner">⚠️ Credenciais encontradas em dumps de infostealer. Um dispositivo associado a este alvo foi comprometido.</div>
  <div class="list">{rows}</div>
</section>""")

    # ── Section: Holehe ───────────────────────────────────────────────────────
    if oath and oath.holehe_domains:
        toc_items.append(f'<li><a href="#holehe">Serviços ({holehe_n})</a></li>')
        chips = "".join(
            f'<span class="chip"><span class="chip-dot"></span>{_e(d)}</span>'
            for d in oath.holehe_domains
        )
        sections.append(f"""
<section id="holehe" class="card">
  <h2 class="card-title">📧 Serviços com Conta Cadastrada — Holehe ({holehe_n})</h2>
  <div class="chips" style="margin-top:10px">{chips}</div>
</section>""")

    # ── Section: Social (Sherlock) ────────────────────────────────────────────
    if sherl and sherl.found:
        toc_items.append(f'<li><a href="#social">Redes Sociais ({social_n})</a></li>')
        from collections import Counter
        cats = Counter(p.category for p in sherl.found)
        cat_rows = "".join(
            f"<tr><td>{_e(cat)}</td><td><strong>{cnt}</strong></td></tr>"
            for cat, cnt in cats.most_common()
        )
        platform_rows = "".join(
            f'<tr>'
            f'<td>{_e(p.icon)} {_e(p.platform)}</td>'
            f'<td><a href="{_e(p.url)}" target="_blank" rel="noopener" style="color:#a78bfa">{_e(p.url[:60])}</a></td>'
            f'<td><span class="tag">{_e(p.category)}</span></td>'
            f'</tr>'
            for p in sherl.found
        )
        motor = sherl.source if sherl else "internal"
        sections.append(f"""
<section id="social" class="card page-break">
  <h2 class="card-title">🌐 Presença em Redes Sociais — Sherlock ({social_n} encontradas)</h2>
  <p class="meta" style="margin:0 0 12px 0">Motor: <code>{_e(motor)}</code> · Plataformas verificadas: {sherl.total_checked if sherl else 0}</p>
  <div class="grid" style="grid-template-columns:1fr 2fr;gap:16px">
    <div>
      <h3 style="font-size:14px;color:#a78bfa;margin:0 0 8px 0">Por Categoria</h3>
      <table class="table"><thead><tr><th>Categoria</th><th>Perfis</th></tr></thead>
      <tbody>{cat_rows}</tbody></table>
    </div>
    <div>
      <h3 style="font-size:14px;color:#a78bfa;margin:0 0 8px 0">Perfis Encontrados</h3>
      <table class="table"><thead><tr><th>Plataforma</th><th>URL</th><th>Categoria</th></tr></thead>
      <tbody>{platform_rows}</tbody></table>
    </div>
  </div>
</section>""")

    # ── Oathnet quota info ────────────────────────────────────────────────────
    if oath and oath.meta.plan:
        m = oath.meta
        toc_items.append('<li><a href="#quota">Quota da API</a></li>')
        sections.append(f"""
<section id="quota" class="card">
  <h2 class="card-title">📊 Informações da Conta OathNet</h2>
  <div class="grid stats">
    <div class="stat"><div class="stat-label">Plano</div><div class="stat-value">{_e(m.plan)}</div></div>
    <div class="stat"><div class="stat-label">Usados Hoje</div><div class="stat-value">{m.used_today}</div></div>
    <div class="stat"><div class="stat-label">Restantes</div><div class="stat-value">{m.left_today}</div></div>
    <div class="stat"><div class="stat-label">Limite Diário</div><div class="stat-value">{"∞" if m.is_unlimited else m.daily_limit}</div></div>
  </div>
</section>""")

    toc_html     = "\n".join(toc_items)
    sections_html = "\n".join(sections)

    return f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>NexusOSINT Report • {_e(target)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{{
  --background:#0a0a0a;--foreground:#f5f5f5;--muted:#262626;
  --muted-foreground:#a3a3a3;--card:rgba(16,16,16,.75);
  --border:rgba(139,92,246,.25);--purple:#8B5CF6;--purple-400:#A78BFA;
  --purple-600:#7C3AED;--blue:#4cc9f0;--indigo:#4361ee;--violet:#3a0ca3;
  --glow:rgba(139,92,246,0.25);--red:#f85149;--orange:#f0883e;--green:#39d353;
}}
*{{box-sizing:border-box}}
html,body{{height:100%;margin:0}}
body{{
  font-family:"Inter",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto;
  color:var(--foreground);
  background:radial-gradient(1200px 800px at 10% -10%,rgba(67,97,238,.15),transparent),
             radial-gradient(1000px 600px at 90% 10%,rgba(76,201,240,.10),transparent),#0b0b0f;
}}
header.site{{
  position:sticky;top:0;z-index:10;
  backdrop-filter:saturate(140%) blur(10px);
  background:rgba(0,0,0,.45);border-bottom:1px solid var(--border);
}}
.wrap{{max-width:1280px;margin:0 auto;padding:20px 24px}}
.title{{display:flex;align-items:center;gap:10px;font-weight:700;font-size:20px;color:#e9e9ff}}
.meta{{color:var(--muted-foreground);font-size:13px;margin-top:3px}}
code{{font-family:"JetBrains Mono",monospace;font-size:12px;background:rgba(255,255,255,.06);
      padding:2px 6px;border-radius:4px;border:1px solid var(--border)}}
.grid{{display:grid;gap:16px}}
.layout{{grid-template-columns:280px 1fr}}
@media(max-width:768px){{.layout{{grid-template-columns:1fr}}}}
nav{{position:sticky;top:76px;align-self:start}}
nav .toc{{list-style:none;padding:0;margin:0}}
nav .toc li{{margin:6px 0}}
nav .toc a{{color:var(--purple-400);text-decoration:none;font-size:14px;transition:color .15s}}
nav .toc a:hover{{color:#fff}}
.card{{
  background:var(--card);border:1px solid var(--border);border-radius:12px;
  box-shadow:0 10px 25px rgba(0,0,0,.25),0 0 0 1px rgba(255,255,255,.02) inset,0 0 40px var(--glow);
  padding:20px;
}}
.card-title{{margin:0 0 14px 0;font-size:17px;color:#e9e9ff;font-weight:600}}
.stats{{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media(max-width:600px){{.stats{{grid-template-columns:repeat(2,1fr)}}}}
.stat{{background:rgba(255,255,255,.02);border:1px solid var(--border);border-radius:10px;padding:14px 16px}}
.stat-label{{font-size:11px;color:var(--muted-foreground);text-transform:uppercase;letter-spacing:.05em}}
.stat-value{{font-size:20px;font-weight:700;margin-top:4px}}
.list{{display:flex;flex-direction:column;gap:8px}}
.details{{border:1px solid var(--border);border-radius:10px;padding:0;background:rgba(0,0,0,.3);overflow:hidden}}
.details summary{{
  cursor:pointer;list-style:none;outline:none;padding:10px 14px;
  background:rgba(255,255,255,.02);transition:background .15s;
  display:flex;align-items:center;gap:8px;
}}
.details[open]>summary{{background:rgba(139,92,246,.1);border-bottom:1px solid var(--border)}}
.details summary::-webkit-details-marker{{display:none}}
.details>div{{padding:12px 14px}}
.badge{{
  display:inline-block;background:rgba(139,92,246,.25);
  border:1px solid var(--border);padding:2px 8px;border-radius:999px;
  font-size:11px;color:#cfc8ff;font-family:"JetBrains Mono",monospace;
}}
.badge-red{{background:rgba(248,81,73,.2);border-color:rgba(248,81,73,.4);color:#fca5a5}}
.tag{{
  display:inline-block;background:rgba(167,139,250,.12);
  border:1px solid var(--border);padding:2px 8px;border-radius:6px;
  font-size:11px;color:#c4b5fd;
}}
.kv{{width:100%;border-collapse:collapse;font-size:13px}}
.kv th,.kv td{{border:1px solid rgba(255,255,255,.06);padding:7px 10px;text-align:left;vertical-align:top}}
.kv th{{width:22%;color:#d7d7ff;background:rgba(255,255,255,.03);font-weight:500;
        font-size:11px;text-transform:uppercase;letter-spacing:.05em}}
.table{{width:100%;border-collapse:collapse;font-size:13px}}
.table th,.table td{{border:1px solid rgba(255,255,255,.06);padding:8px 10px;text-align:left}}
.table th{{background:rgba(255,255,255,.03);color:#a78bfa;font-size:11px;text-transform:uppercase;letter-spacing:.05em}}
.table tr:hover td{{background:rgba(255,255,255,.02)}}
.chips{{display:flex;flex-wrap:wrap;gap:8px}}
.chip{{
  display:inline-flex;align-items:center;gap:7px;padding:6px 12px;
  border-radius:999px;border:1px solid var(--border);
  background:rgba(255,255,255,.03);color:#e9e9ff;font-size:13px;
}}
.chip-dot{{width:8px;height:8px;border-radius:50%;background:var(--green);flex-shrink:0}}
.alert-banner{{
  background:rgba(248,81,73,.1);border:1px solid rgba(248,81,73,.35);
  border-radius:8px;padding:10px 14px;color:#fca5a5;font-size:13px;margin-bottom:14px;
}}
.cover{{
  display:grid;place-items:center;min-height:50vh;
  border:1px solid var(--border);border-radius:12px;overflow:hidden;
  background:linear-gradient(135deg,var(--violet),var(--indigo),var(--blue));
}}
.cover .inner{{
  background:rgba(0,0,0,.5);padding:44px 56px;border-radius:16px;
  border:1px solid rgba(255,255,255,.12);text-align:center;max-width:600px;
}}
.cover .brand{{font-size:30px;font-weight:800;letter-spacing:.06em;color:#fff}}
.cover .subtitle{{margin-top:8px;color:#c0c0ff;font-size:15px}}
.cover .pills{{display:flex;gap:10px;justify-content:center;margin-top:18px;flex-wrap:wrap}}
.cover .pill{{
  background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);
  padding:5px 14px;border-radius:999px;font-size:13px;color:#fff;
}}
.risk-pill{{
  display:inline-flex;align-items:center;gap:8px;
  background:rgba(0,0,0,.4);border:2px solid {risk_color};
  border-radius:999px;padding:6px 18px;font-size:20px;font-weight:800;
  color:{risk_color};margin-top:14px;
}}
.page-break{{page-break-before:always}}
footer.site{{color:var(--muted-foreground);text-align:center;padding:28px 0;font-size:13px;
              border-top:1px solid var(--border);margin-top:32px}}
.btn-top{{
  position:fixed;right:22px;bottom:22px;
  background:var(--purple-600);color:#fff;border:none;
  border-radius:999px;padding:10px 16px;font-weight:600;cursor:pointer;
  box-shadow:0 8px 20px rgba(124,58,237,.4);font-size:14px;
  transition:transform .15s;
}}
.btn-top:hover{{transform:scale(1.05)}}
.copy-btn{{
  float:right;font-size:11px;color:#cfc8ff;
  border:1px solid var(--border);background:rgba(255,255,255,.03);
  padding:2px 7px;border-radius:7px;cursor:pointer;margin-left:8px;
  transition:all .15s;font-family:"JetBrains Mono",monospace;
}}
.copy-btn:hover{{background:rgba(255,255,255,.08);border-color:rgba(167,139,250,.5)}}
.copy-btn.copied{{background:rgba(57,211,83,.15);border-color:rgba(57,211,83,.4);color:#bbf7d0}}
.anchor{{scroll-margin-top:88px}}
@media print{{
  header.site,.btn-top{{display:none!important}}
  .layout{{grid-template-columns:1fr}}
  body{{background:#fff;color:#000}}
  .card{{box-shadow:none;border:1px solid #ddd;background:#fff}}
  .cover{{background:linear-gradient(135deg,#6d28d9,#4338ca,#0ea5e9)}}
}}
</style>
</head>
<body>
<header class="site">
  <div class="wrap">
    <div class="title">⬡ NexusOSINT • Relatório de Investigação</div>
    <div class="meta">v{APP_VERSION} · Gerado em {_e(now_str[:19].replace("T"," "))} · Alvo: <strong>{_e(target)}</strong></div>
  </div>
</header>

<main class="wrap grid layout">
  <aside>
    <nav class="card">
      <h2 class="card-title" style="font-size:14px;margin-bottom:10px">📋 Índice</h2>
      <ol class="toc">{toc_html}</ol>
    </nav>
  </aside>

  <section class="grid" style="gap:18px">
    <!-- Cover -->
    <section class="cover">
      <div class="inner">
        <div class="brand">⬡ NEXUSOSINT</div>
        <div class="subtitle">Plataforma de Investigação OSINT</div>
        <div class="pills">
          <span class="pill">🎯 {_e(target)}</span>
          <span class="pill">📋 {_e(target_type)}</span>
          <span class="pill">📅 {_e(now_str[:10])}</span>
        </div>
        <div class="risk-pill">{risk_score} — {risk_label}</div>
      </div>
    </section>

    {sections_html}
  </section>
</main>

<footer class="site">
  NexusOSINT v{APP_VERSION} · Relatório gerado em {_e(now_str)} · For legal &amp; ethical use only.
</footer>

<button class="btn-top" onclick="window.scrollTo({{top:0,behavior:'smooth'}})">▲ Topo</button>

<script>
document.addEventListener('click', function(e) {{
  var t = e.target;
  if (!t || !t.classList || !t.classList.contains('copy-btn')) return;
  e.preventDefault();
  var val = t.getAttribute('data-copy') || '';
  if (!val) return;
  function flash() {{
    t.classList.add('copied'); t.textContent = '✓ Copiado';
    setTimeout(function() {{ t.classList.remove('copied'); t.textContent = 'Copy'; }}, 1400);
  }}
  if (navigator.clipboard && navigator.clipboard.writeText) {{
    navigator.clipboard.writeText(val).then(flash).catch(function() {{
      var ta = document.createElement('textarea');
      ta.value = val; document.body.appendChild(ta); ta.select();
      document.execCommand('copy'); document.body.removeChild(ta); flash();
    }});
  }} else {{
    var ta = document.createElement('textarea');
    ta.value = val; document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta); flash();
  }}
}});
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# ── PDF REPORT (OSINT Industries style) ───────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def generate_pdf(
    target: str,
    target_type: str,
    oath: Optional["OathnetResult"],
    sherl: Optional["SherlockResult"],
    risk_score: int,
    timestamp: str,
) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak, KeepTogether,
    )
    from reportlab.platypus.flowables import BalancedColumns
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2.2*cm, bottomMargin=2.2*cm,
        title=f"NexusOSINT — {target}",
        author="NexusOSINT",
    )

    # ── Palette ───────────────────────────────────────────────────────────────
    C_DARK   = colors.HexColor("#0d1117")
    C_ACCENT = colors.HexColor("#00d4ff")
    C_PURPLE = colors.HexColor("#7c3aed")
    C_GREEN  = colors.HexColor("#39d353")
    C_RED    = colors.HexColor("#f85149")
    C_ORANGE = colors.HexColor("#f0883e")
    C_GOLD   = colors.HexColor("#ffd700")
    C_GRAY   = colors.HexColor("#8b949e")
    C_LIGHT  = colors.HexColor("#f0f0f0")
    C_WHITE  = colors.white
    C_BORDER = colors.HexColor("#d0d0d0")

    if risk_score >= 75:
        risk_color = C_RED
    elif risk_score >= 50:
        risk_color = C_ORANGE
    elif risk_score >= 25:
        risk_color = C_GOLD
    else:
        risk_color = C_GREEN

    # ── Styles ────────────────────────────────────────────────────────────────
    base = getSampleStyleSheet()

    def sty(name, parent="Normal", **kw):
        s = ParagraphStyle(name, parent=base[parent], **kw)
        return s

    S_TITLE    = sty("nx_title",    fontSize=26, fontName="Helvetica-Bold",
                     textColor=C_WHITE, alignment=TA_CENTER, spaceAfter=4)
    S_SUBTITLE = sty("nx_sub",      fontSize=13, fontName="Helvetica",
                     textColor=colors.HexColor("#c0c0ff"), alignment=TA_CENTER, spaceAfter=2)
    S_SMALL    = sty("nx_small",    fontSize=9,  fontName="Helvetica",
                     textColor=C_GRAY, alignment=TA_CENTER, spaceAfter=2)
    S_H1       = sty("nx_h1",       fontSize=15, fontName="Helvetica-Bold",
                     textColor=C_DARK, spaceBefore=14, spaceAfter=6,
                     borderPad=4, borderWidth=0)
    S_H2       = sty("nx_h2",       fontSize=12, fontName="Helvetica-Bold",
                     textColor=C_PURPLE, spaceBefore=10, spaceAfter=4)
    S_BODY     = sty("nx_body",     fontSize=9,  fontName="Helvetica",
                     textColor=C_DARK, spaceAfter=3, leading=13)
    S_LABEL    = sty("nx_label",    fontSize=8,  fontName="Helvetica-Bold",
                     textColor=C_GRAY, spaceAfter=1)
    S_CODE     = sty("nx_code",     fontSize=8,  fontName="Courier",
                     textColor=C_DARK, backColor=C_LIGHT,
                     borderWidth=0.5, borderColor=C_BORDER, borderPad=3,
                     spaceAfter=4)
    S_TOC      = sty("nx_toc",      fontSize=10, fontName="Helvetica",
                     textColor=C_DARK, spaceAfter=4, leftIndent=12)
    S_WARN     = sty("nx_warn",     fontSize=9,  fontName="Helvetica",
                     textColor=C_RED, backColor=colors.HexColor("#fff0f0"),
                     borderWidth=0.5, borderColor=C_RED, borderPad=5,
                     spaceAfter=6)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def hr():
        return HRFlowable(width="100%", thickness=0.5, color=C_BORDER, spaceAfter=6, spaceBefore=2)

    def kv_table(rows: list[tuple[str, str]], col_widths=(4*cm, 12*cm)) -> Table:
        data = [[Paragraph(f"<b>{k}</b>", S_LABEL), Paragraph(str(v)[:300], S_BODY)]
                for k, v in rows if v]
        if not data:
            return Spacer(1, 0)
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (0,-1), C_LIGHT),
            ("GRID",        (0,0), (-1,-1), 0.3, C_BORDER),
            ("VALIGN",      (0,0), (-1,-1), "TOP"),
            ("TOPPADDING",  (0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
        ]))
        return t

    def section_header(text: str, color=C_ACCENT) -> list:
        return [
            Spacer(1, 0.3*cm),
            Table([[Paragraph(text, sty(f"hdr_{text[:10]}", fontSize=13,
                                        fontName="Helvetica-Bold", textColor=C_WHITE))]],
                   colWidths=["100%"]),
            Spacer(1, 0.1*cm),
        ]

    def banner_table(text: str, bg_color=C_DARK, text_color=C_WHITE) -> Table:
        style = sty(f"banner_{text[:6]}", fontSize=13, fontName="Helvetica-Bold",
                    textColor=text_color, alignment=TA_LEFT)
        t = Table([[Paragraph(text, style)]], colWidths=["100%"])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), bg_color),
            ("TOPPADDING",  (0,0), (-1,-1), 8),
            ("BOTTOMPADDING",(0,0),(-1,-1), 8),
            ("LEFTPADDING", (0,0), (-1,-1), 12),
            ("ROUNDEDCORNERS", [4]),
        ]))
        return t

    def stats_row(stats: list[tuple[str, str]]) -> Table:
        """Horizontal stat cards in a single row."""
        header_row = [Paragraph(lbl, S_LABEL) for lbl, _ in stats]
        value_row  = [Paragraph(val, sty(f"sv{i}", fontSize=18, fontName="Helvetica-Bold",
                                          textColor=C_PURPLE)) for i, (_, val) in enumerate(stats)]
        n = len(stats)
        w = 16.6 * cm / n
        t = Table([header_row, value_row], colWidths=[w]*n)
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), C_LIGHT),
            ("GRID",          (0,0), (-1,-1), 0.3, C_BORDER),
            ("ALIGN",         (0,0), (-1,-1), "CENTER"),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        return t

    now_str = timestamp or datetime.now().isoformat()
    story   = []

    # ══════════════════════════════════════════════════════════════════════════
    # COVER PAGE
    # ══════════════════════════════════════════════════════════════════════════
    cover_data = [[
        Paragraph("⬡ NEXUSOSINT", S_TITLE),
    ]]
    cover_bg = Table(
        [[Paragraph("⬡ NexusOSINT", S_TITLE),],
         [Paragraph("Plataforma de Investigação OSINT", S_SUBTITLE)],
         [Spacer(1, 0.4*cm)],
         [Paragraph(f"Alvo: {target}", sty("cv_target", fontSize=14, fontName="Helvetica-Bold",
                                            textColor=C_WHITE, alignment=TA_CENTER))],
         [Paragraph(f"Tipo: {target_type} · {now_str[:10]}", S_SMALL)],
         [Spacer(1, 0.5*cm)],
         [Table([[Paragraph(f"RISK SCORE: {risk_score}",
                             sty("cv_risk", fontSize=16, fontName="Helvetica-Bold",
                                 textColor=risk_color, alignment=TA_CENTER))]],
                colWidths=["100%"],
                style=[("BACKGROUND",(0,0),(-1,-1), colors.HexColor("#0a0a0a")),
                       ("TOPPADDING",(0,0),(-1,-1), 10),
                       ("BOTTOMPADDING",(0,0),(-1,-1), 10)])],
        ],
        colWidths=["100%"],
    )
    cover_bg.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#1a0a3e")),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING",    (0,0), (-1,-1), 28),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("LEFTPADDING",   (0,0), (-1,-1), 30),
        ("RIGHTPADDING",  (0,0), (-1,-1), 30),
    ]))
    story.append(cover_bg)
    story.append(Spacer(1, 1*cm))

    # ── Table of Contents ─────────────────────────────────────────────────────
    story.append(Paragraph("Índice", S_H1))
    story.append(hr())
    toc_entries = [
        ("1", "Visão Geral"),
        ("2", f"Vazamentos de Dados — {oath.breach_count if oath else 0} registros"),
        ("3", f"Stealer Logs — {oath.stealer_count if oath else 0} entradas"),
        ("4", f"Serviços (Holehe) — {len(oath.holehe_domains) if oath else 0} serviços"),
        ("5", f"Presença Social (Sherlock) — {sherl.found_count if sherl else 0} plataformas"),
        ("6", "Timeline de Eventos"),
    ]
    for num, title in toc_entries:
        story.append(Paragraph(f"  {num}.  {title}", S_TOC))
    story.append(Spacer(1, 0.5*cm))

    # ══════════════════════════════════════════════════════════════════════════
    # 1 — OVERVIEW
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(banner_table("1. Visão Geral"))
    story.append(Spacer(1, 0.3*cm))
    story.append(stats_row([
        ("Vazamentos",     str(oath.breach_count  if oath else 0)),
        ("Stealer Logs",   str(oath.stealer_count if oath else 0)),
        ("Holehe",         str(len(oath.holehe_domains) if oath else 0)),
        ("Redes Sociais",  str(sherl.found_count  if sherl else 0)),
    ]))
    story.append(Spacer(1, 0.4*cm))
    story.append(kv_table([
        ("Alvo",        target),
        ("Tipo",        target_type),
        ("Investigado", now_str[:19].replace("T", " ")),
        ("Risk Score",  f"{risk_score} — {'CRÍTICO' if risk_score>=75 else 'ALTO' if risk_score>=50 else 'MÉDIO' if risk_score>=25 else 'BAIXO'}"),
        ("Ferramenta",  f"NexusOSINT v{APP_VERSION}"),
    ]))

    # ══════════════════════════════════════════════════════════════════════════
    # 2 — BREACH RECORDS
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(banner_table("2. Vazamentos de Dados"))
    story.append(Spacer(1, 0.3*cm))

    if oath and oath.breaches:
        story.append(Paragraph(f"Total encontrado no banco de breaches: <b>{oath.results_found}</b> registros", S_BODY))
        story.append(Spacer(1, 0.2*cm))
        hdrs = ["#", "DB / Fonte", "Email", "Username", "País", "Data"]
        rows_data = [hdrs] + [
            [str(i), b.dbname[:20], b.email[:28], b.username[:20], b.country[:4], b.date[:10]]
            for i, b in enumerate(oath.breaches, 1)
        ]
        col_ws = [0.6*cm, 3*cm, 5*cm, 3.5*cm, 1.5*cm, 2.5*cm]
        t = Table(rows_data, colWidths=col_ws, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), C_DARK),
            ("TEXTCOLOR",     (0,0), (-1,0), C_ACCENT),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 8),
            ("GRID",          (0,0), (-1,-1), 0.3, C_BORDER),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_WHITE, C_LIGHT]),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("✅ Nenhum vazamento encontrado para este alvo.", S_BODY))

    # ══════════════════════════════════════════════════════════════════════════
    # 3 — STEALER LOGS
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(banner_table("3. Stealer Logs — Credenciais Roubadas por Malware"))
    story.append(Spacer(1, 0.3*cm))

    if oath and oath.stealers:
        story.append(Paragraph(
            "⚠️  Credenciais encontradas em dumps de infostealer. Um dispositivo associado a este alvo foi comprometido.",
            S_WARN,
        ))
        hdrs = ["#", "URL", "Username", "Domínio", "Data"]
        rows_data = [hdrs] + [
            [str(i), (s.url[:35] or "—"), (s.username[:22] or "—"),
             (", ".join(s.domain[:1]) or "—")[:20], (s.pwned_at[:10] or "—")]
            for i, s in enumerate(oath.stealers, 1)
        ]
        col_ws = [0.6*cm, 5.5*cm, 3.5*cm, 3.5*cm, 2.5*cm]
        t = Table(rows_data, colWidths=col_ws, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), colors.HexColor("#3d0000")),
            ("TEXTCOLOR",     (0,0), (-1,0), C_RED),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 8),
            ("GRID",          (0,0), (-1,-1), 0.3, C_BORDER),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_WHITE, colors.HexColor("#fff8f8")]),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("✅ Nenhum stealer log encontrado.", S_BODY))

    # ══════════════════════════════════════════════════════════════════════════
    # 4 — HOLEHE
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(banner_table("4. Serviços com Conta Cadastrada — Holehe"))
    story.append(Spacer(1, 0.3*cm))

    if oath and oath.holehe_domains:
        n = len(oath.holehe_domains)
        story.append(Paragraph(f"<b>{n}</b> serviço(s) confirmado(s) para este email:", S_BODY))
        story.append(Spacer(1, 0.2*cm))
        # Grid: 3 columns
        col_per_row = 3
        domain_rows = []
        row = []
        for i, d in enumerate(oath.holehe_domains):
            row.append(Paragraph(f"✓  {d}", S_BODY))
            if len(row) == col_per_row:
                domain_rows.append(row)
                row = []
        if row:
            while len(row) < col_per_row:
                row.append(Paragraph("", S_BODY))
            domain_rows.append(row)
        cw = 16.6*cm / col_per_row
        t = Table(domain_rows, colWidths=[cw]*col_per_row)
        t.setStyle(TableStyle([
            ("GRID",          (0,0), (-1,-1), 0.3, C_BORDER),
            ("ROWBACKGROUNDS",(0,0), (-1,-1), [C_WHITE, C_LIGHT]),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("Nenhum serviço detectado via Holehe.", S_BODY))

    # ══════════════════════════════════════════════════════════════════════════
    # 5 — SOCIAL (SHERLOCK)
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(banner_table("5. Presença em Redes Sociais — Sherlock"))
    story.append(Spacer(1, 0.3*cm))

    if sherl and sherl.found:
        story.append(Paragraph(
            f"<b>{sherl.found_count}</b> perfis encontrados em <b>{sherl.total_checked}</b> plataformas verificadas (motor: {sherl.source})",
            S_BODY,
        ))
        story.append(Spacer(1, 0.2*cm))
        hdrs = ["Plataforma", "URL", "Categoria"]
        rows_data = [hdrs] + [
            [p.platform, p.url[:50], p.category]
            for p in sherl.found
        ]
        col_ws = [4*cm, 8.6*cm, 4*cm]
        t = Table(rows_data, colWidths=col_ws, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), C_DARK),
            ("TEXTCOLOR",     (0,0), (-1,0), C_ACCENT),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 8),
            ("GRID",          (0,0), (-1,-1), 0.3, C_BORDER),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_WHITE, C_LIGHT]),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("Nenhum perfil público encontrado nas plataformas verificadas.", S_BODY))

    # ══════════════════════════════════════════════════════════════════════════
    # 6 — TIMELINE
    # ══════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(banner_table("6. Timeline de Eventos"))
    story.append(Spacer(1, 0.3*cm))

    events = []
    if oath:
        for b in oath.breaches:
            if b.date:
                events.append((b.date[:10], "💥 Vazamento", f"Encontrado em {b.dbname}"))
        for s in oath.stealers:
            if s.pwned_at:
                events.append((s.pwned_at[:10], "🦠 Stealer", f"Credential capturada: {s.url[:40]}"))
    if sherl:
        for p in sherl.found:
            events.append((now_str[:10], "🌐 Social", f"Perfil encontrado: {p.platform}"))

    events.sort(key=lambda x: x[0], reverse=True)

    if events:
        hdrs = ["Data", "Tipo", "Descrição"]
        rows_data = [hdrs] + [[e[0], e[1], e[2]] for e in events[:40]]
        col_ws = [2.5*cm, 3.5*cm, 10.6*cm]
        t = Table(rows_data, colWidths=col_ws, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), C_DARK),
            ("TEXTCOLOR",     (0,0), (-1,0), C_ACCENT),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 8),
            ("GRID",          (0,0), (-1,-1), 0.3, C_BORDER),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_WHITE, C_LIGHT]),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("Nenhum evento com data disponível.", S_BODY))

    # ── Footer on every page ──────────────────────────────────────────────────
    def add_page_number(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(C_GRAY)
        canvas.drawString(2*cm, 1.2*cm, f"NexusOSINT v{APP_VERSION} · {now_str[:10]} · Alvo: {target}")
        canvas.drawRightString(19.5*cm, 1.2*cm, f"Página {document.page}")
        canvas.setStrokeColor(C_BORDER)
        canvas.setLineWidth(0.3)
        canvas.line(2*cm, 1.6*cm, 19.5*cm, 1.6*cm)
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    buf.seek(0)
    return buf.read()