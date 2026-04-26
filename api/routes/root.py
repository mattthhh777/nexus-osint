"""Root + admin-panel HTML pages."""
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from api.deps import _decode_token

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
@router.head("/")
async def root():
    html_file = Path(__file__).parent.parent.parent / "static" / "index.html"
    if html_file.exists():
        return HTMLResponse(html_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>NexusOSINT v3</h1>")


@router.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    """Admin panel — auth server-side via cookie nx_session (VULN-03)."""
    token = request.cookies.get("nx_session")

    if token:
        try:
            payload = _decode_token(token)
            if payload.get("role") == "admin":
                admin_file = Path(__file__).parent.parent.parent / "static" / "admin.html"
                if admin_file.exists():
                    return HTMLResponse(admin_file.read_text(encoding="utf-8"))
                return HTMLResponse("<h1>Admin panel not found</h1>", status_code=404)
        except HTTPException:
            pass  # token inválido/expirado → cai no fallback abaixo

    # Sem cookie válido: bridge page que lê localStorage e chama auth-gate
    return HTMLResponse("""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>NexusOSINT Admin</title>
<style>
  body{background:#0a0a0f;display:flex;align-items:center;
       justify-content:center;height:100vh;margin:0;
       font-family:monospace;color:#666;font-size:.85rem}
</style>
</head>
<body><span>Authenticating…</span>
<script>
(async () => {
  const t = localStorage.getItem('nx_token');
  if (!t) { location.replace('/'); return; }
  try {
    const r = await fetch('/api/admin/auth-gate', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + t }
    });
    if (r.ok) { location.replace('/admin'); }
    else       { location.replace('/'); }
  } catch { location.replace('/'); }
})();
</script>
</body></html>""")
