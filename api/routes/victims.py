"""Victims API routes: /api/victims/search, manifest, file content."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from api.config import RL_READ_LIMIT
from api.deps import get_current_user
from api.main import limiter
from api.services.admin_service import _validate_id
from modules.oathnet_client import oathnet_client

router = APIRouter()


@router.get("/api/victims/search")
@limiter.limit(RL_READ_LIMIT)
async def victims_search_endpoint(
    request: Request,
    q: str = "",
    page_size: int = 10,
    cursor: str = "",
    email: str = "",
    ip: str = "",
    discord_id: str = "",
    username: str = "",
    user: dict = Depends(get_current_user),
):
    """Search victim profiles (compromised machines)."""
    if oathnet_client is None:
        raise HTTPException(status_code=503, detail="OATHNET_API_KEY not configured")
    filters = {}
    if email:      filters["email"]      = email
    if ip:         filters["ip"]         = ip
    if discord_id: filters["discord_id"] = discord_id
    if username:   filters["username"]   = username
    ok, data = await oathnet_client.victims_search(q, page_size, cursor, "", **filters)
    if not ok:
        raise HTTPException(status_code=400, detail=data.get("error", "Search failed"))
    return data


@router.get("/api/victims/{log_id}/manifest")
@limiter.limit(RL_READ_LIMIT)
async def victims_manifest_endpoint(
    request: Request,
    log_id: str,
    user: dict = Depends(get_current_user),
):
    """Get file tree for a victim log."""
    _validate_id(log_id)
    if oathnet_client is None:
        raise HTTPException(status_code=503, detail="OATHNET_API_KEY not configured")
    ok, data = await oathnet_client.victims_manifest(log_id)
    if not ok:
        raise HTTPException(status_code=404, detail=data.get("error", "Not found"))
    return data


@router.get("/api/victims/{log_id}/files/{file_id}")
@limiter.limit(RL_READ_LIMIT)
async def victims_file_endpoint(
    request: Request,
    log_id: str,
    file_id: str,
    user: dict = Depends(get_current_user),
):
    """Get raw file content from a victim log."""
    _validate_id(log_id)
    _validate_id(file_id)
    if oathnet_client is None:
        raise HTTPException(status_code=503, detail="OATHNET_API_KEY not configured")
    ok, content_text = await oathnet_client.victims_file(log_id, file_id)
    if not ok:
        raise HTTPException(status_code=404, detail=content_text)
    return PlainTextResponse(content_text)
