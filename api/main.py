"""
NexusOSINT v2 — FastAPI Backend
Replaces Streamlit entirely. Runs on VPS with SpiderFoot as sidecar.
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
from typing import AsyncGenerator, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────
OATHNET_API_KEY  = os.getenv("OATHNET_API_KEY", "")
SPIDERFOOT_URL   = os.getenv("SPIDERFOOT_URL", "http://spiderfoot:5001")
APP_PASSWORD     = os.getenv("APP_PASSWORD", "")
LOG_LEVEL        = os.getenv("LOG_LEVEL", "WARNING")

logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger("nexusosint")

app = FastAPI(title="NexusOSINT", version="2.0.0", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Serve static files (the frontend)
static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


# ── Models ─────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    mode: str = "automated"           # "automated" | "manual"
    modules: list[str] = []           # for manual mode
    spiderfoot_mode: str = "passive"  # "passive" | "footprint" | "investigate"


# ── Root — serve the SPA ────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    html_file = Path(__file__).parent.parent / "static" / "index.html"
    if html_file.exists():
        return HTMLResponse(html_file.read_text())
    return HTMLResponse("<h1>NexusOSINT v2</h1><p>static/index.html not found</p>")


# ── Auth ────────────────────────────────────────────────────────────────────

@app.post("/api/auth")
async def auth(request: Request):
    if not APP_PASSWORD:
        return {"ok": True}
    body = await request.json()
    if body.get("password") == APP_PASSWORD:
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Invalid password")


# ── Query type detection ─────────────────────────────────────────────────────

def detect_type(q: str) -> str:
    q = q.strip()
    if re.match(r'^\d{14,19}$', q):               return "discord_id"
    if re.match(r'^\+\d{7,15}$', q):              return "phone"
    if re.match(r'^[\w.+\-]+@[\w\-]+\.[\w.]{2,}$', q, re.I): return "email"
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', q):  return "ip"
    if re.match(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$', q): return "domain"
    return "username"


# ── Main search endpoint (SSE streaming) ────────────────────────────────────

@app.post("/api/search")
async def search(req: SearchRequest):
    """
    Streams search results as Server-Sent Events (SSE).
    Each event: data: {"type": "progress"|"result"|"done"|"error", ...}
    """
    return StreamingResponse(
        _stream_search(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx: disable buffering
        },
    )


async def _stream_search(req: SearchRequest) -> AsyncGenerator[str, None]:
    """Generator that yields SSE events as search progresses."""

    def event(data: dict) -> str:
        return f"data: {json.dumps(data, default=str)}\n\n"

    query    = req.query.strip()
    q_type   = detect_type(query)
    is_email = q_type == "email"
    is_user  = q_type == "username"
    is_ip    = q_type == "ip"
    is_disc  = q_type == "discord_id"
    is_dom   = q_type == "domain"

    # Decide which modules to run
    if req.mode == "automated":
        run = {
            "breach":     True,
            "stealer":    True,
            "sherlock":   is_email or is_user,
            "holehe":     is_email,
            "discord":    is_disc,
            "ip_info":    is_ip,
            "subdomain":  is_dom,
            "spiderfoot": False,  # always manual for spiderfoot
        }
    else:
        mods = set(req.modules)
        run = {
            "breach":     "breach"    in mods,
            "stealer":    "stealer"   in mods,
            "sherlock":   "sherlock"  in mods and (is_email or is_user),
            "holehe":     "holehe"    in mods and is_email,
            "discord":    "discord"   in mods and is_disc,
            "ip_info":    "ip_info"   in mods and is_ip,
            "subdomain":  "subdomain" in mods and is_dom,
            "spiderfoot": "spiderfoot" in mods,
        }

    total = sum(run.values())
    done  = [0]

    def progress(label: str, detail: str = ""):
        done[0] += 1
        pct = int(done[0] / max(total, 1) * 100)
        return event({"type": "progress", "pct": pct, "label": label, "detail": detail})

    yield event({"type": "start", "query": query, "query_type": q_type, "total_modules": total})

    # Import modules lazily to avoid import errors at startup
    from modules.oathnet_client import OathnetClient
    from modules.sherlock_wrapper import search_username

    client = OathnetClient(api_key=OATHNET_API_KEY)
    t0 = time.time()

    # ── OathNet: Breach ──────────────────────────────────────────────────
    if run["breach"] or run["stealer"] or run["holehe"]:
        yield progress("Searching breach databases…")
        try:
            res = await asyncio.to_thread(client.search_breach, query)

            if run["stealer"]:
                yield progress("Scanning stealer logs…")
                sts = await asyncio.to_thread(client.search_stealer_v2, query)
                res.stealers = sts.stealers
                res.stealers_found = sts.stealers_found

            if run["holehe"] and is_email:
                yield progress("Checking email registrations (Holehe)…")
                h = await asyncio.to_thread(client.holehe, query)
                res.holehe_domains = h.holehe_domains

            # Serialize breaches
            breaches_data = [{
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
            } for b in res.breaches]

            stealers_data = [{
                "url":      s.url,
                "username": s.username,
                "password": s.password,
                "domain":   s.domain,
                "pwned_at": s.pwned_at,
                "log_id":   s.log_id,
            } for s in res.stealers]

            yield event({
                "type":           "oathnet",
                "success":        res.success,
                "breach_count":   len(breaches_data),
                "stealer_count":  len(stealers_data),
                "holehe_count":   len(res.holehe_domains),
                "results_found":  res.results_found,
                "breaches":       breaches_data,
                "stealers":       stealers_data,
                "holehe_domains": res.holehe_domains,
                "plan":           res.meta.plan,
                "used_today":     res.meta.used_today,
                "left_today":     res.meta.left_today,
                "daily_limit":    res.meta.daily_limit,
                "error":          res.error,
            })
        except Exception as exc:
            logger.error("OathNet failed: %s", exc)
            yield event({"type": "module_error", "module": "oathnet", "error": str(exc)})

    # ── Sherlock ─────────────────────────────────────────────────────────
    if run["sherlock"]:
        yield progress("Scanning social platforms (Sherlock)…")
        try:
            uname = query if is_user else query.split("@")[0]
            sherl = await asyncio.to_thread(search_username, uname, False)
            yield event({
                "type":        "sherlock",
                "found_count": sherl.found_count,
                "total_checked": sherl.total_checked,
                "source":      sherl.source,
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

    # ── Discord ──────────────────────────────────────────────────────────
    if run["discord"]:
        yield progress("Looking up Discord profile…")
        try:
            ok_u, user = await asyncio.to_thread(client.discord_userinfo, query)
            ok_h, hist = await asyncio.to_thread(client.discord_username_history, query)
            yield event({
                "type":    "discord",
                "user":    user if ok_u else None,
                "history": hist if ok_h else None,
            })
        except Exception as exc:
            yield event({"type": "module_error", "module": "discord", "error": str(exc)})

    # ── IP Info ──────────────────────────────────────────────────────────
    if run["ip_info"]:
        yield progress("Fetching IP geolocation & network info…")
        try:
            ok, data = await asyncio.to_thread(client.ip_info, query)
            yield event({"type": "ip_info", "ok": ok, "data": data if ok else None})
        except Exception as exc:
            yield event({"type": "module_error", "module": "ip_info", "error": str(exc)})

    # ── Subdomains ───────────────────────────────────────────────────────
    if run["subdomain"]:
        yield progress("Enumerating subdomains…")
        try:
            ok, data = await asyncio.to_thread(client.extract_subdomains, query)
            subs = data.get("subdomains", []) if ok else []
            yield event({"type": "subdomains", "ok": ok, "data": subs, "count": len(subs)})
        except Exception as exc:
            yield event({"type": "module_error", "module": "subdomains", "error": str(exc)})

    # ── SpiderFoot ───────────────────────────────────────────────────────
    if run["spiderfoot"]:
        yield progress("Starting SpiderFoot scan (this may take a few minutes)…")
        async for sf_event in _run_spiderfoot(query, req.spiderfoot_mode):
            yield sf_event

    # ── Done ─────────────────────────────────────────────────────────────
    yield event({
        "type":      "done",
        "elapsed_s": round(time.time() - t0, 1),
        "timestamp": datetime.now().isoformat(),
    })


# ── SpiderFoot integration ───────────────────────────────────────────────────

async def _run_spiderfoot(target: str, scan_mode: str) -> AsyncGenerator[str, None]:
    """Calls SpiderFoot REST API and streams progress."""

    def event(data: dict) -> str:
        return f"data: {json.dumps(data, default=str)}\n\n"

    try:
        async with httpx.AsyncClient(timeout=600) as http:
            # Check if SpiderFoot is available
            try:
                ping = await http.get(f"{SPIDERFOOT_URL}/api/v1/ping", timeout=5)
                if ping.status_code != 200:
                    yield event({"type": "spiderfoot", "available": False,
                                 "error": "SpiderFoot not responding"})
                    return
            except Exception:
                yield event({"type": "spiderfoot", "available": False,
                             "error": f"Cannot reach SpiderFoot at {SPIDERFOOT_URL}"})
                return

            # Create scan
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

            # Poll for completion
            for _ in range(120):  # max 10 minutes
                await asyncio.sleep(5)
                status_resp = await http.get(f"{SPIDERFOOT_URL}/api/v1/scanstatus/{scan_id}")
                if status_resp.status_code != 200:
                    continue

                status = status_resp.json()
                scan_status = status.get("status", "")
                yield event({"type": "spiderfoot_progress", "status": scan_status})

                if scan_status in ("FINISHED", "ABORTED", "ERROR"):
                    break

            # Get results
            results_resp = await http.get(f"{SPIDERFOOT_URL}/api/v1/scaneventresults/{scan_id}")
            if results_resp.status_code == 200:
                raw_results = results_resp.json()

                # Filter relevant event types
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


# ── SpiderFoot proxy endpoints ───────────────────────────────────────────────

@app.get("/api/spiderfoot/status")
async def sf_status():
    """Check if SpiderFoot is available."""
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            r = await http.get(f"{SPIDERFOOT_URL}/api/v1/ping")
            version_r = await http.get(f"{SPIDERFOOT_URL}/api/v1/version")
            return {
                "available": r.status_code == 200,
                "version": version_r.json() if version_r.status_code == 200 else None,
                "url": SPIDERFOOT_URL,
            }
    except Exception as exc:
        return {"available": False, "error": str(exc), "url": SPIDERFOOT_URL}


@app.get("/api/spiderfoot/scans")
async def sf_scans():
    """List recent SpiderFoot scans."""
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.get(f"{SPIDERFOOT_URL}/api/v1/scanlist")
            return r.json() if r.status_code == 200 else []
    except Exception:
        return []


@app.get("/api/spiderfoot/scan/{scan_id}")
async def sf_scan_results(scan_id: str):
    """Get results of a specific scan."""
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.get(f"{SPIDERFOOT_URL}/api/v1/scaneventresults/{scan_id}")
            return r.json() if r.status_code == 200 else {"error": "not found"}
    except Exception as exc:
        return {"error": str(exc)}


# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "timestamp": datetime.now().isoformat()}