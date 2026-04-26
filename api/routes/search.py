"""Search routes: /api/search (SSE), /api/search/more-breaches, /api/admin/breach-extra-keys."""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.config import RL_ADMIN_LIMIT, RL_SEARCH_LIMIT
from api.db import DatabaseManager
from api.deps import get_admin_user, get_client_ip, get_current_user, get_db, get_orchestrator_dep
from api.main import limiter
from api.orchestrator import DegradationMode, TaskOrchestrator
from api.schemas import SearchRequest
from api.services.search_service import (
    _seen_breach_extra_keys,
    _serialize_breaches,
    _stream_search,
)
from modules.oathnet_client import oathnet_client

router = APIRouter()


@router.post("/api/search")
@limiter.limit(RL_SEARCH_LIMIT)
async def search(
    request: Request,
    req: SearchRequest,
    user: dict = Depends(get_current_user),
    db: DatabaseManager = Depends(get_db),
    orch: TaskOrchestrator = Depends(get_orchestrator_dep),
):
    """Protected SSE search endpoint. Rate limited by slowapi (RL_SEARCH_LIMIT, per user)."""
    if orch.degradation_mode == DegradationMode.CRITICAL:
        raise HTTPException(
            status_code=503,
            detail="System under memory pressure — new scans temporarily rejected",
            headers={"Retry-After": "120"},
        )
    client_ip = get_client_ip(request)
    return StreamingResponse(
        _stream_search(req, user["sub"], client_ip, db=db, orch=orch),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/search/more-breaches")
@limiter.limit(RL_SEARCH_LIMIT)
async def more_breaches(
    request: Request,
    body: dict,
    user: dict = Depends(get_current_user),
):
    """Fetch next page of breach results using OathNet cursor."""
    query  = body.get("query", "").strip()
    cursor = body.get("cursor", "")
    if not query or not cursor:
        raise HTTPException(status_code=400, detail="query and cursor required")
    if len(query) > 256:
        raise HTTPException(status_code=400, detail="Query too long")
    if oathnet_client is None:
        raise HTTPException(status_code=503, detail="OATHNET_API_KEY not configured")
    try:
        result = await oathnet_client.search_breach(query, cursor)
        if not result.success:
            raise HTTPException(status_code=502, detail=result.error or "Breach search failed")
        breaches_data = _serialize_breaches(result.breaches)
        return {
            "breaches":      breaches_data,
            "breach_count":  len(breaches_data),
            "results_found": result.results_found,
            "next_cursor":   result.next_cursor,
            "has_more":      bool(result.next_cursor),
        }
    except HTTPException:
        raise
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="OathNet API unreachable")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="OathNet API timed out")


@router.get("/api/admin/breach-extra-keys")
@limiter.limit(RL_ADMIN_LIMIT)
async def breach_extra_keys(request: Request, _: dict = Depends(get_admin_user)):
    """Phase 13 diagnostic: return key names seen in breach extra_fields since process start.

    Accumulates across all real OathNet scans run while the container is up.
    Only key names are exposed — never field values (no PII leak risk).
    Resets on container restart. Run a few real queries before calling this.
    """
    return {
        "keys": sorted(_seen_breach_extra_keys),
        "count": len(_seen_breach_extra_keys),
        "note": (
            "In-memory accumulator — resets on container restart. "
            "Run at least one real breach query before checking."
        ),
    }
