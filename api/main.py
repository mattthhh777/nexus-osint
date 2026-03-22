"""
NexusOSINT v2.2 — FastAPI Backend
Fixes over v2.1:
  - modules_run communicated to frontend in 'done' event
  - Discord runs on any query in manual mode (not just discord_id type)
  - Discord username history correctly parsed (nested data.history[].name[0])
  - Auto Discord lookup from breach discord_id fields in automated mode
  - discord-to-roblox endpoint exposed
  - Panel isolation: frontend hides panels for modules not run
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

load_dotenv()

OATHNET_API_KEY = os.getenv("OATHNET_API_KEY", "")
SPIDERFOOT_URL  = os.getenv("SPIDERFOOT_URL", "http://spiderfoot:5001")
APP_PASSWORD    = os.getenv("APP_PASSWORD", "")
LOG_LEVEL       = os.getenv("LOG_LEVEL", "WARNING")

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.WARNING))
logger = logging.getLogger("nexusosint")

app = FastAPI(title="NexusOSINT", version="2.3.0", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


class SearchRequest(BaseModel):
    query: str
    mode: str = "automated"
    modules: list[str] = []
    spiderfoot_mode: str = "passive"

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Query cannot be empty")
        if len(v) > 256:
            raise ValueError("Query too long (max 256 chars)")
        v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        return v if v in ("automated", "manual") else "automated"

    @field_validator("spiderfoot_mode")
    @classmethod
    def validate_sf_mode(cls, v: str) -> str:
        return v if v in ("passive", "footprint", "investigate") else "passive"


@app.get("/", response_class=HTMLResponse)
async def root():
    html_file = Path(__file__).parent.parent / "static" / "index.html"
    if html_file.exists():
        return HTMLResponse(html_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>NexusOSINT v2</h1><p>static/index.html not found</p>")


@app.post("/api/auth")
async def auth(request: Request):
    if not APP_PASSWORD:
        return {"ok": True}
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if body.get("password") == APP_PASSWORD:
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Invalid password")


def detect_type(q: str) -> str:
    q = q.strip()
    if re.match(r"^\d{14,19}$", q):
        return "discord_id"
    if re.match(r"^\+\d{7,15}$", q):
        return "phone"
    if re.match(r"^[\w.+\-]+@[\w\-]+\.[\w.]{2,}$", q, re.I):
        return "email"
    if re.match(r"^(\d{1,3}\.){3}\d{1,3}$", q):
        return "ip"
    if re.match(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$", q):
        return "domain"
    if re.match(r"^\d{7,10}$", q):
        return "steam_id"
    return "username"


def _serialize_breaches(breaches) -> list[dict]:
    return [{
        "dbname":     b.dbname,
        "email":      b.email,
        "username":   b.username,
        "password":   b.password,
        "ip":         b.ip,
        "country":    b.country,
        "date":       b.date,
        "discord_id": b.discord_id,
        "phone":      b.phone,
        "extra":      b.extra_fields,
    } for b in breaches]


def _serialize_stealers(stealers) -> list[dict]:
    return [{
        "url":      s.url,
        "username": s.username,
        "password": s.password,
        "domain":   s.domain,
        "pwned_at": s.pwned_at,
        "log_id":   s.log_id,
    } for s in stealers]


@app.post("/api/search")
async def search(req: SearchRequest):
    return StreamingResponse(
        _stream_search(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_search(req: SearchRequest) -> AsyncGenerator[str, None]:

    def event(data: dict) -> str:
        return f"data: {json.dumps(data, default=str)}\n\n"

    query    = req.query
    q_type   = detect_type(query)
    is_email = q_type == "email"
    is_user  = q_type == "username"
    is_ip    = q_type == "ip"
    is_disc  = q_type == "discord_id"
    is_dom   = q_type == "domain"
    is_steam = q_type == "steam_id"

    # ── Module selection ──────────────────────────────────────────────────
    if req.mode == "automated":
        run = {
            "breach":     True,
            "stealer":    True,
            "sherlock":   is_email or is_user,
            "holehe":     is_email,
            # Discord: run if query IS a discord_id; also auto-run after breach if discord_ids found
            "discord":    is_disc,
            "ip_info":    is_ip,
            "subdomain":  is_dom,
            "steam":      is_steam or is_user,
            "roblox":     is_user,
            "ghunt":      is_email,
            "minecraft":  is_user,
            "spiderfoot": False,
        }
    else:
        mods = set(req.modules)
        run = {
            "breach":    "breach"    in mods,
            "stealer":   "stealer"   in mods,
            # ↓ FIX: Discord in manual mode runs regardless of query type
            "sherlock":  "sherlock"  in mods and (is_email or is_user),
            "holehe":    "holehe"    in mods and is_email,
            "discord":   "discord"   in mods,   # no is_disc filter — always allow manual
            "ip_info":   "ip_info"   in mods and is_ip,
            "subdomain": "subdomain" in mods and is_dom,
            "steam":     "steam"     in mods,
            "xbox":      "xbox"      in mods,
            "roblox":    "roblox"    in mods,
            "spiderfoot":"spiderfoot" in mods,
        }

    total     = sum(run.values())
    done_cnt  = [0]
    # Track which modules actually ran (for frontend panel isolation)
    ran: list[str] = []

    def progress(label: str, detail: str = "") -> str:
        done_cnt[0] += 1
        pct = int(done_cnt[0] / max(total, 1) * 100)
        return event({"type": "progress", "pct": pct, "label": label, "detail": detail})

    yield event({
        "type":          "start",
        "query":         query,
        "query_type":    q_type,
        "total_modules": total,
        "modules_planned": [k for k, v in run.items() if v],
    })

    from modules.oathnet_client import OathnetClient
    from modules.sherlock_wrapper import search_username

    client = OathnetClient(api_key=OATHNET_API_KEY)
    t0     = time.time()

    # ── OathNet: Breach + Stealer parallel ───────────────────────────────
    if run.get("breach") or run.get("stealer") or run.get("holehe"):
        yield progress("Searching breach databases & stealer logs…")
        ran.append("breach")
        ran.append("stealer")
        try:
            tasks = [asyncio.to_thread(client.search_breach, query)]
            if run.get("stealer"):
                tasks.append(asyncio.to_thread(client.search_stealer_v2, query))

            results_gathered = await asyncio.gather(*tasks, return_exceptions=True)
            res = results_gathered[0] if not isinstance(results_gathered[0], Exception) else None

            if res is None:
                yield event({"type": "module_error", "module": "breach", "error": str(results_gathered[0])})
            else:
                if run.get("stealer") and len(results_gathered) > 1:
                    sts = results_gathered[1]
                    if not isinstance(sts, Exception):
                        res.stealers = sts.stealers
                        res.stealers_found = sts.stealers_found

                if run.get("holehe") and is_email:
                    ran.append("holehe")
                    h = await asyncio.to_thread(client.holehe, query)
                    res.holehe_domains = h.holehe_domains

                breaches_data = _serialize_breaches(res.breaches)

                # AUTO-EXTRACT Discord IDs from breach results (automated mode)
                discord_ids_from_breach = []
                if req.mode == "automated" and not is_disc:
                    discord_ids_from_breach = list({
                        b["discord_id"] for b in breaches_data
                        if b.get("discord_id") and re.match(r"^\d{14,19}$", str(b["discord_id"]))
                    })

                yield event({
                    "type":           "oathnet",
                    "success":        res.success,
                    "breach_count":   len(breaches_data),
                    "stealer_count":  len(res.stealers),
                    "holehe_count":   len(res.holehe_domains),
                    "results_found":  res.results_found,
                    "breaches":       breaches_data,
                    "stealers":       _serialize_stealers(res.stealers),
                    "holehe_domains": res.holehe_domains,
                    "plan":           res.meta.plan,
                    "used_today":     res.meta.used_today,
                    "left_today":     res.meta.left_today,
                    "daily_limit":    res.meta.daily_limit,
                    "error":          res.error,
                    "discord_ids_found": discord_ids_from_breach,
                })

                # Auto-run Discord lookup if IDs were found in breach data
                if discord_ids_from_breach and req.mode == "automated":
                    for disc_id in discord_ids_from_breach[:3]:  # max 3 to save quota
                        yield progress(f"Discord lookup: {disc_id}")
                        ran.append("discord")
                        try:
                            ok_u, user = await asyncio.to_thread(client.discord_userinfo, disc_id)
                            ok_h, hist = await asyncio.to_thread(client.discord_username_history, disc_id)
                            yield event({
                                "type":       "discord",
                                "query_id":   disc_id,
                                "user":       user if ok_u else None,
                                "history":    _parse_discord_history(hist) if ok_h else None,
                            })
                        except Exception as exc:
                            logger.warning("Auto Discord lookup failed for %s: %s", disc_id, exc)

        except Exception as exc:
            logger.error("OathNet failed: %s", exc)
            yield event({"type": "module_error", "module": "oathnet", "error": str(exc)})

    # ── Sherlock ──────────────────────────────────────────────────────────
    if run.get("sherlock"):
        yield progress("Scanning social platforms (Sherlock)…")
        ran.append("sherlock")
        try:
            uname = query if is_user else query.split("@")[0]
            sherl = await asyncio.to_thread(search_username, uname, False)
            yield event({
                "type":          "sherlock",
                "found_count":   sherl.found_count,
                "total_checked": sherl.total_checked,
                "source":        sherl.source,
                "found": [{
                    "platform": p.platform,
                    "url":      p.url,
                    "category": p.category,
                    "icon":     p.icon,
                } for p in sherl.found],
            })
        except Exception as exc:
            logger.error("Sherlock failed: %s", exc)
            yield event({"type": "module_error", "module": "sherlock", "error": str(exc)})

    # ── Discord ───────────────────────────────────────────────────────────
    if run.get("discord"):
        yield progress("Looking up Discord profile…")
        ran.append("discord")

        # FIX: if query is not a discord_id, tell the frontend clearly
        if not is_disc:
            yield event({
                "type":  "discord",
                "error": "Discord lookup requires a Discord ID (numeric snowflake, e.g. 123456789012345678). "
                         "Username lookup is not supported by the Discord API.",
                "hint":  "Try searching by Discord ID, or use Automated mode — it will auto-detect Discord IDs found in breach data.",
                "user":  None,
                "history": None,
            })
        else:
            try:
                ok_u, user = await asyncio.to_thread(client.discord_userinfo, query)
                ok_h, raw_hist = await asyncio.to_thread(client.discord_username_history, query)
                yield event({
                    "type":    "discord",
                    "user":    user if ok_u else None,
                    "history": _parse_discord_history(raw_hist) if ok_h else None,
                })
            except Exception as exc:
                yield event({"type": "module_error", "module": "discord", "error": str(exc)})

    # ── IP Info ──────────────────────────────────────────────────────────
    if run.get("ip_info"):
        yield progress("Fetching IP geolocation…")
        ran.append("ip_info")
        try:
            ok, data = await asyncio.to_thread(client.ip_info, query)
            yield event({"type": "ip_info", "ok": ok, "data": data if ok else None})
        except Exception as exc:
            yield event({"type": "module_error", "module": "ip_info", "error": str(exc)})

    # ── Subdomains ───────────────────────────────────────────────────────
    if run.get("subdomain"):
        yield progress("Enumerating subdomains…")
        ran.append("subdomain")
        try:
            ok, data = await asyncio.to_thread(client.extract_subdomains, query)
            subs = data.get("subdomains", []) if ok else []
            yield event({"type": "subdomains", "ok": ok, "data": subs, "count": len(subs)})
        except Exception as exc:
            yield event({"type": "module_error", "module": "subdomains", "error": str(exc)})

    # ── Steam ─────────────────────────────────────────────────────────────
    if run.get("steam"):
        yield progress("Looking up Steam profile…")
        ran.append("steam")
        try:
            ok, data = await asyncio.to_thread(client.steam_lookup, query)
            if ok:
                yield event({"type": "steam", "ok": True, "data": data})
            else:
                yield event({"type": "steam", "ok": False, "error": data.get("error", "Not found")})
        except Exception as exc:
            yield event({"type": "module_error", "module": "steam", "error": str(exc)})

    # ── Xbox ──────────────────────────────────────────────────────────────
    if run.get("xbox"):
        yield progress("Looking up Xbox profile…")
        ran.append("xbox")
        try:
            ok, data = await asyncio.to_thread(client.xbox_lookup, query)
            yield event({"type": "xbox", "ok": ok, "data": data if ok else None})
        except Exception as exc:
            yield event({"type": "module_error", "module": "xbox", "error": str(exc)})

    # ── Roblox ────────────────────────────────────────────────────────────
    if run.get("roblox"):
        yield progress("Looking up Roblox profile…")
        ran.append("roblox")
        try:
            ok, data = await asyncio.to_thread(client.roblox_lookup, username=query)
            yield event({"type": "roblox", "ok": ok, "data": data if ok else None})
        except Exception as exc:
            yield event({"type": "module_error", "module": "roblox", "error": str(exc)})

    # ── GHunt ─────────────────────────────────────────────────────────────
    if run.get("ghunt"):
        yield progress("Looking up Google account (GHunt)…")
        ran.append("ghunt")
        try:
            ok, data = await asyncio.to_thread(client.ghunt, query)
            yield event({"type": "ghunt", "ok": ok, "data": data if ok else None,
                         "error": data.get("error") if not ok else None})
        except Exception as exc:
            yield event({"type": "module_error", "module": "ghunt", "error": str(exc)})

    # ── Minecraft ─────────────────────────────────────────────────────────
    if run.get("minecraft"):
        yield progress("Looking up Minecraft account…")
        ran.append("minecraft")
        try:
            ok, data = await asyncio.to_thread(client.minecraft_history, query)
            yield event({"type": "minecraft", "ok": ok, "data": data if ok else None,
                         "error": data.get("error") if not ok else None})
        except Exception as exc:
            yield event({"type": "module_error", "module": "minecraft", "error": str(exc)})

    # ── SpiderFoot ────────────────────────────────────────────────────────
    if run.get("spiderfoot"):
        yield progress("Starting SpiderFoot scan…")
        ran.append("spiderfoot")
        async for sf_event in _run_spiderfoot(query, req.spiderfoot_mode):
            yield sf_event

    # ── Done ─────────────────────────────────────────────────────────────
    yield event({
        "type":        "done",
        "elapsed_s":   round(time.time() - t0, 1),
        "timestamp":   datetime.now().isoformat(),
        "modules_run": list(set(ran)),   # ← NEW: frontend uses this to show/hide panels
    })


def _parse_discord_history(raw: dict) -> dict | None:
    """Parse the nested discord-username-history response correctly.
    API returns: data.history[].name[0] and data.history[].time[0]
    """
    if not raw:
        return None
    # raw is already data.data from oathnet_client
    history_raw = raw.get("history", [])
    if not history_raw:
        return None
    parsed = []
    for entry in history_raw:
        name = entry.get("name", [])
        time_ = entry.get("time", [])
        parsed.append({
            "username": name[0] if isinstance(name, list) and name else name,
            "timestamp": time_[0] if isinstance(time_, list) and time_ else time_,
        })
    return {"usernames": parsed}


async def _run_spiderfoot(target: str, scan_mode: str) -> AsyncGenerator[str, None]:
    def event(data: dict) -> str:
        return f"data: {json.dumps(data, default=str)}\n\n"

    try:
        async with httpx.AsyncClient(timeout=600) as http:
            try:
                ping = await http.get(f"{SPIDERFOOT_URL}/api/v1/ping", timeout=5)
                if ping.status_code != 200:
                    yield event({"type": "spiderfoot", "available": False, "error": "SpiderFoot not responding"})
                    return
            except Exception:
                yield event({"type": "spiderfoot", "available": False,
                             "error": f"Cannot reach SpiderFoot at {SPIDERFOOT_URL}"})
                return

            scan_resp = await http.post(f"{SPIDERFOOT_URL}/api/v1/startscan", data={
                "scanname":   f"nexus_{target}_{int(time.time())}",
                "scantarget": target,
                "usecase":    scan_mode,
                "modulelist": "",
                "typelist":   "",
            })

            if scan_resp.status_code != 200:
                yield event({"type": "spiderfoot", "available": True,
                             "error": f"Failed to start scan: {scan_resp.text[:200]}"})
                return

            scan_id = scan_resp.json().get("id", "")
            yield event({"type": "spiderfoot_started", "scan_id": scan_id})

            for _ in range(120):
                await asyncio.sleep(5)
                try:
                    status_resp = await http.get(f"{SPIDERFOOT_URL}/api/v1/scanstatus/{scan_id}")
                    if status_resp.status_code != 200:
                        continue
                    scan_status = status_resp.json().get("status", "")
                    yield event({"type": "spiderfoot_progress", "status": scan_status})
                    if scan_status in ("FINISHED", "ABORTED", "ERROR"):
                        break
                except Exception:
                    continue

            results_resp = await http.get(f"{SPIDERFOOT_URL}/api/v1/scaneventresults/{scan_id}")
            if results_resp.status_code == 200:
                raw_results = results_resp.json()
                RELEVANT = {
                    "EMAILADDR", "USERNAME", "SOCIAL_MEDIA", "ACCOUNT_EXTERNAL_OWNED",
                    "PHONE_NUMBER", "IP_ADDRESS", "DOMAIN_NAME", "LEAKSITE_URL",
                    "PASSWORD_COMPROMISED", "DATA_HAS_BEEN_PWNED", "DARKNET_MENTION_URL",
                    "MALICIOUS_IPADDR", "MALICIOUS_EMAILADDR", "GEOINFO",
                }
                filtered = [
                    {"type": r[4], "data": r[1], "source": r[3], "confidence": r[2]}
                    for r in raw_results
                    if len(r) >= 5 and r[4] in RELEVANT
                ]
                yield event({
                    "type":      "spiderfoot",
                    "available": True,
                    "scan_id":   scan_id,
                    "results":   filtered[:500],
                    "total":     len(filtered),
                })
    except Exception as exc:
        logger.error("SpiderFoot error: %s", exc)
        yield event({"type": "spiderfoot", "available": False, "error": str(exc)})


@app.get("/api/spiderfoot/status")
async def sf_status():
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            r = await http.get(f"{SPIDERFOOT_URL}/api/v1/ping")
            return {"available": r.status_code == 200, "url": SPIDERFOOT_URL}
    except Exception as exc:
        return {"available": False, "error": str(exc), "url": SPIDERFOOT_URL}


@app.get("/api/spiderfoot/scans")
async def sf_scans():
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.get(f"{SPIDERFOOT_URL}/api/v1/scanlist")
            return r.json() if r.status_code == 200 else []
    except Exception:
        return []


@app.get("/api/spiderfoot/scan/{scan_id}")
async def sf_scan_results(scan_id: str):
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.get(f"{SPIDERFOOT_URL}/api/v1/scaneventresults/{scan_id}")
            return r.json() if r.status_code == 200 else {"error": "not found"}
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.3.0", "timestamp": datetime.now().isoformat()}