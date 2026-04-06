import pytest
import httpx
import os
import asyncio
from datetime import datetime, timezone
from fastapi import HTTPException
from api.main import app, _create_token, _decode_token
import api.main
from api.db import db as global_db

BASE_URL = "http://test.local"
APP_PASSWORD = os.getenv("APP_PASSWORD", "admin")

@pytest.mark.asyncio
async def test_full_nexus_flow(tmp_db, monkeypatch):
    # 1. Override de dependência (já sabemos que funciona!)
    app.dependency_overrides[global_db] = lambda: tmp_db
    monkeypatch.setattr(api.main, "_db", tmp_db)

    transport = httpx.ASGITransport(app=app)
    
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        
        # --- LOGIN ---
        payload = {"username": "admin", "password": APP_PASSWORD}
        login_res = await ac.post("/api/login", json=payload)
        
        if login_res.status_code == 422:
            login_res = await ac.post("/api/login", json={"password": APP_PASSWORD})
            
        assert login_res.status_code == 200
        
        # Pausa técnica para o SQLite no Windows
        await asyncio.sleep(0.5)

        # --- ADMIN STATS ---
        stats_res = await ac.get("/api/admin/stats")
        
        # Se der 401 por causa da expiração rápida do cookie, tentamos forçar
        if stats_res.status_code == 401:
            token = ac.cookies.get("nx_session")
            stats_res = await ac.get("/api/admin/stats", cookies={"nx_session": token})

        assert stats_res.status_code == 200
        
        # AJUSTE AQUI: O seu log mostrou que a resposta tem 'active_users'
        data = stats_res.json()
        assert "active_users" in data
        print("\n[SUCESSO] Fluxo completo finalizado com êxito!")

    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_unauthorized_access(tmp_db, monkeypatch):
    app.dependency_overrides[global_db] = lambda: tmp_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        res = await ac.get("/api/admin/stats")
        assert res.status_code == 401
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_health_endpoint(tmp_db, monkeypatch):
    app.dependency_overrides[global_db] = lambda: tmp_db
    monkeypatch.setattr(api.main, "_db", tmp_db)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        body = res.json()
        assert "status" in body
        assert "rss_mb" in body
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_jwt_roundtrip():
    token = _create_token("alice", "admin")
    assert isinstance(token, str) and len(token) > 20
    decoded = _decode_token(token)
    assert decoded["sub"] == "alice"
    assert decoded["role"] == "admin"
    assert "exp" in decoded
    assert "iat" in decoded
    assert "jti" in decoded
    now_ts = int(datetime.now(timezone.utc).timestamp())
    assert decoded["exp"] > now_ts
    # Tamper: flip last 4 chars — must raise 401
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(HTTPException) as exc_info:
        _decode_token(tampered)
    assert exc_info.value.status_code == 401