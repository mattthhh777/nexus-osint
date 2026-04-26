"""SpiderFoot integration routes: /api/spiderfoot/status."""
import httpx
from fastapi import APIRouter, Depends, Request

from api.config import RL_READ_LIMIT, SPIDERFOOT_URL
from api.deps import get_current_user
from api.main import limiter

router = APIRouter()


@router.get("/api/spiderfoot/status")
@limiter.limit(RL_READ_LIMIT)
async def sf_status(request: Request, _: dict = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            r = await http.get(f"{SPIDERFOOT_URL}/api/v1/ping")
            return {"available": r.status_code == 200, "url": SPIDERFOOT_URL}
    except httpx.HTTPError as exc:
        return {"available": False, "error": str(exc), "url": SPIDERFOOT_URL}
