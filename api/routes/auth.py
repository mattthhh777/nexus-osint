"""Auth routes: legacy ping, login, /me, logout."""
import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from api.config import APP_PASSWORD, JWT_EXPIRE_HOURS, RL_LOGIN_LIMIT, RL_READ_LIMIT
from api.db import DatabaseManager
from api.deps import _decode_token, get_current_user, get_db
from api.limiter import limiter
from api.schemas import LoginRequest
from api.services.auth_service import _create_token, _load_users, _revoke_token, _verify_user

router = APIRouter()


@router.post("/api/auth")
@limiter.limit(RL_LOGIN_LIMIT)
async def auth_legacy(request: Request):
    """Legacy endpoint kept for frontend compatibility."""
    if not APP_PASSWORD and not _load_users():
        return {"ok": True}
    return {"ok": False, "requires_login": True}


@router.post("/api/login")
@limiter.limit(RL_LOGIN_LIMIT)
async def login(request: Request, body: LoginRequest):
    """JWT login. Defines the HttpOnly nx_session cookie."""
    user = _verify_user(body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = _create_token(user["username"], user["role"])
    max_age_s = JWT_EXPIRE_HOURS * 3600
    is_prod = os.getenv("ENV", "dev").lower() == "prod"

    response = JSONResponse(content={
        "ok": True,
        "token_type": "cookie",
        "expires_in": max_age_s,
        "username": user["username"],
        "role": user["role"],
    })
    response.set_cookie(
        key="nx_session",
        value=token,
        httponly=True,
        secure=is_prod,
        samesite="strict",
        max_age=max_age_s,
        path="/",
    )
    return response


@router.get("/api/me")
@limiter.limit(RL_READ_LIMIT)
async def me(request: Request, user: dict = Depends(get_current_user)):
    """Returns current user info."""
    return {"username": user["sub"], "role": user.get("role", "user")}


@router.post("/api/logout")
@limiter.limit(RL_READ_LIMIT)
async def logout(
    request: Request,
    response: Response,
    db: DatabaseManager = Depends(get_db),
):
    """Terminate session: revoke JWT and delete nx_session cookie."""
    token = request.cookies.get("nx_session")
    if token:
        try:
            payload = _decode_token(token)
            await _revoke_token(payload.get("jti"), payload.get("exp"), db=db)
        except HTTPException:
            pass
    response.delete_cookie("nx_session", path="/")
    return {"ok": True}
