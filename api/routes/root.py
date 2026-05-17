"""Root + admin-panel HTML pages."""
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from api.deps import get_optional_admin_user

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
@router.head("/")
async def root():
    html_file = Path(__file__).parent.parent.parent / "static" / "index.html"
    if html_file.exists():
        return HTMLResponse(html_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>NexusOSINT v3</h1>")


@router.get("/admin", response_class=HTMLResponse)
async def admin_panel(maybe_admin: dict | None = Depends(get_optional_admin_user)):
    """Admin panel is served only to a valid admin cookie session."""
    if maybe_admin is not None:
        admin_file = Path(__file__).parent.parent.parent / "static" / "admin.html"
        if admin_file.exists():
            return HTMLResponse(admin_file.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Admin panel not found</h1>", status_code=404)

    return RedirectResponse("/", status_code=303)
