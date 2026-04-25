"""Search service: TTL cache, seen-keys accumulator, SSE stream generator, SpiderFoot runner, helpers."""
import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import AsyncGenerator

import aiosqlite
import httpx
from cachetools import TTLCache
from pydantic import ValidationError

from api.config import MAX_BREACH_SERIALIZE, MODULE_TIMEOUTS, SPIDERFOOT_URL
from api.db import db as _db
from api.orchestrator import get_orchestrator
from api.schemas import SearchRequest
from modules.oathnet_client import oathnet_client
from modules.spiderfoot_wrapper import SpiderFootTarget

logger = logging.getLogger("nexusosint.search_service")

# 5-min TTL, max 200 entries — ~2MB max, safe for 1GB VPS
_api_cache: TTLCache = TTLCache(maxsize=200, ttl=300)

# Phase 13 accumulator — grows as real breach scans happen; resets on restart
_seen_breach_extra_keys: set[str] = set()


def _cache_key(endpoint: str, query: str) -> str:
    """Generate normalised cache key for external API responses."""
    return f"{endpoint}:{query.lower().strip()}"


def _get_cached(endpoint: str, query: str):
    """Return cached API response or None if absent / expired."""
    return _api_cache.get(_cache_key(endpoint, query))


def _set_cached(endpoint: str, query: str, data) -> None:
    """Store a successful API response in cache. Never cache None / errors."""
    if data is not None:
        _api_cache[_cache_key(endpoint, query)] = data


async def _save_quota(used: int, left: int, daily_limit: int) -> None:
    """Save current OathNet quota to DB for admin dashboard."""
    await _db.write(
        "INSERT INTO quota_log (ts, used_today, left_today, daily_limit) VALUES (?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), used, left, daily_limit),
    )
    # Keep only last 100 entries — fire-and-forget trim
    await _db.write(
        "DELETE FROM quota_log WHERE rowid NOT IN "
        "(SELECT rowid FROM quota_log ORDER BY ts DESC LIMIT 100)",
    )


async def _log_search(
    username: str,
    ip: str,
    query: str,
    query_type: str,
    mode: str,
    modules_run: list[str],
    breach_count: int = 0,
    stealer_count: int = 0,
    social_count: int = 0,
    elapsed_s: float = 0.0,
    success: bool = True,
) -> None:
    """Write a search audit record. Non-blocking — goes through write queue."""
    await _db.write(
        """INSERT INTO searches
           (ts, username, ip, query, query_type, mode, modules_run,
            breach_count, stealer_count, social_count, elapsed_s, success)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            datetime.now(timezone.utc).isoformat(),
            username, ip, query, query_type, mode,
            ",".join(modules_run),
            breach_count, stealer_count, social_count,
            elapsed_s, int(success),
        ),
    )


def detect_type(q: str) -> str:
    q = q.strip()
    if re.match(r"^\d{14,19}$", q):      return "discord_id"
    if re.match(r"^\+\d{7,15}$", q):     return "phone"
    if re.match(r"^[\w.+\-]+@[\w\-]+\.[\w.]{2,}$", q, re.I): return "email"
    if re.match(r"^(\d{1,3}\.){3}\d{1,3}$", q):               return "ip"
    if re.match(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$", q): return "domain"
    if re.match(r"^\d{7,10}$", q):        return "steam_id"
    return "username"


async def with_timeout(coro, module: str, default=None):
    """
    Wrap a coroutine with a per-module timeout.
    Returns (result, timed_out: bool).
    On timeout: returns (default, True) instead of raising.
    """
    timeout_s = MODULE_TIMEOUTS.get(module, 30)
    try:
        result = await asyncio.wait_for(coro, timeout=timeout_s)
        return result, False
    except asyncio.TimeoutError:
        logger.warning("Module '%s' timed out after %ds", module, timeout_s)
        return default, True


def _serialize_breaches(breaches, limit: int = MAX_BREACH_SERIALIZE) -> list[dict]:
    for b in breaches:
        if b.extra_fields:
            _seen_breach_extra_keys.update(b.extra_fields.keys())
    return [{"dbname": b.dbname, "email": b.email, "username": b.username,
             "password": b.password, "ip": b.ip, "country": b.country,
             "date": b.date, "discord_id": b.discord_id, "phone": b.phone,
             "extra": b.extra_fields} for b in breaches[:limit]]

def _serialize_stealers(stealers) -> list[dict]:
    return [{"url": s.url, "username": s.username, "password": s.password,
             "domain": s.domain, "pwned_at": s.pwned_at, "log_id": s.log_id}
            for s in stealers]


async def _stream_search(
    req: SearchRequest,
    username: str,
    client_ip: str,
) -> AsyncGenerator[str, None]:

    def event(data: dict) -> str:
        return f"data: {json.dumps(data, default=str)}\n\n"

    # Phase 10: register this search in the orchestrator so active_count
    # reports non-zero during a running scan. Sentinel stays in the registry
    # until _sentinel_done is set at the end of the search.
    orch = get_orchestrator()
    _sentinel_done: asyncio.Event = asyncio.Event()

    async def _search_sentinel() -> None:
        await _sentinel_done.wait()

    try:
        orch.submit(
            f"search-{id(_sentinel_done)}",
            _search_sentinel(),
            is_oathnet=False,
        )
    except RuntimeError:
        # Ceiling reached (REDUCED mode at capacity) — search continues untracked.
        # CRITICAL mode is already blocked at the /api/search gate.
        logger.warning("Orchestrator ceiling reached — search proceeds untracked (degradation=%s)", orch.degradation_mode.value)

    query    = req.query
    q_type   = detect_type(query)
    is_email = q_type == "email"
    is_user  = q_type == "username"
    is_ip    = q_type == "ip"
    is_disc  = q_type == "discord_id"
    is_dom   = q_type == "domain"
    is_steam = q_type == "steam_id"

    if req.mode == "automated":
        run = {
            "breach": True, "stealer": True,
            "sherlock": is_email or is_user,
            "holehe": is_email, "discord": is_disc,
            "ip_info": is_ip, "subdomain": is_dom,
            "steam": is_steam or is_user,
            "xbox":  is_user,
            "roblox": is_user,
            "ghunt": is_email,
            "discord_roblox": is_disc,
            "victims": is_user or is_email,
            "spiderfoot": False,
        }
    else:
        mods = set(req.modules)
        run = {
            "breach":         "breach"         in mods,
            "stealer":        "stealer"        in mods,
            "sherlock":       "sherlock"       in mods and (is_email or is_user),
            "holehe":         "holehe"         in mods and is_email,
            "discord":        "discord"        in mods,
            "ip_info":        "ip_info"        in mods and is_ip,
            "subdomain":      "subdomain"      in mods and is_dom,
            "steam":          "steam"          in mods,
            "xbox":           "xbox"           in mods,
            "roblox":         "roblox"         in mods,
            "ghunt":          "ghunt"          in mods and is_email,
            "discord_roblox": "discord_roblox" in mods,
            "victims":        "victims"        in mods,
            "spiderfoot":     "spiderfoot"     in mods,
        }

    total    = sum(run.values())
    done_cnt = [0]
    ran: list[str] = []
    # Counters for audit log
    breach_count = stealer_count = social_count = 0

    def progress(label: str) -> str:
        done_cnt[0] += 1
        pct = int(done_cnt[0] / max(total, 1) * 100)
        return event({"type": "progress", "pct": pct, "label": label})

    yield event({
        "type": "start", "query": query,
        "query_type": q_type, "total_modules": total,
        "modules_planned": [k for k, v in run.items() if v],
        "user": username,
    })

    from modules.sherlock_wrapper import search_username

    if oathnet_client is None:
        yield event({"type": "error", "message": "OATHNET_API_KEY not configured"})
        return

    t0 = time.time()

    # ── Breach + Stealer parallel ─────────────────────────────────────────
    if run.get("breach") or run.get("stealer") or run.get("holehe"):
        yield progress("Searching breach databases & stealer logs…")
        ran += ["breach", "stealer"]
        try:
            # Check breach cache first — avoids OathNet API call within 5-min TTL
            cached_breach = _get_cached("breach", query)
            if cached_breach is not None:
                tasks = []
                breach_future = cached_breach
            else:
                tasks = [oathnet_client.search_breach(query)]
                breach_future = None

            stealer_future = None
            if run.get("stealer"):
                cached_stealer = _get_cached("stealer", query)
                if cached_stealer is not None:
                    stealer_future = cached_stealer
                else:
                    tasks.append(oathnet_client.search_stealer_v2(query))

            results_gathered = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []

            # Reconstruct results: cache hits are already resolved, API results from gather
            gather_idx = 0
            if breach_future is not None:
                res = breach_future
            else:
                raw = results_gathered[gather_idx] if gather_idx < len(results_gathered) else None
                res = raw if not isinstance(raw, Exception) else None
                if res is not None:
                    _set_cached("breach", query, res)
                gather_idx += 1

            if run.get("stealer"):
                if stealer_future is not None:
                    sts_result = stealer_future
                else:
                    raw_sts = results_gathered[gather_idx] if gather_idx < len(results_gathered) else None
                    sts_result = raw_sts if not isinstance(raw_sts, Exception) else None
                    if sts_result is not None:
                        _set_cached("stealer", query, sts_result)
                    gather_idx += 1
            else:
                sts_result = None

            if res is None:
                err_detail = str(results_gathered[0]) if results_gathered else "Breach search failed"
                yield event({"type": "module_error", "module": "breach", "error": err_detail})
            else:
                if run.get("stealer") and sts_result is not None:
                    res.stealers       = sts_result.stealers
                    res.stealers_found = sts_result.stealers_found

                if run.get("holehe") and is_email:
                    ran.append("holehe")
                    cached_holehe = _get_cached("holehe", query)
                    if cached_holehe is not None:
                        res.holehe_domains = cached_holehe
                    else:
                        h, timed_out = await with_timeout(
                            oathnet_client.holehe(query), "holehe"
                        )
                        if timed_out:
                            logger.warning("Holehe timed out")
                        elif h:
                            res.holehe_domains = h.holehe_domains
                            _set_cached("holehe", query, h.holehe_domains)

                breaches_data = _serialize_breaches(res.breaches)
                breach_count  = len(breaches_data)
                stealer_count = len(res.stealers)

                discord_ids_from_breach = []
                if req.mode == "automated" and not is_disc:
                    discord_ids_from_breach = list({
                        b["discord_id"] for b in breaches_data
                        if b.get("discord_id") and re.match(r"^\d{14,19}$", str(b["discord_id"]))
                    })

                yield event({
                    "type": "oathnet", "success": res.success,
                    "breach_count": breach_count,
                    "stealer_count": stealer_count,
                    "holehe_count": len(res.holehe_domains),
                    "results_found": res.results_found,
                    "breaches": breaches_data,
                    "stealers": _serialize_stealers(res.stealers),
                    "holehe_domains": res.holehe_domains,
                    "plan": res.meta.plan,
                    "used_today": res.meta.used_today,
                    "left_today": res.meta.left_today,
                    "daily_limit": res.meta.daily_limit,
                    "error": res.error,
                    "discord_ids_found": discord_ids_from_breach,
                })

                if discord_ids_from_breach and req.mode == "automated":
                    for disc_id in discord_ids_from_breach[:3]:
                        yield progress(f"Discord lookup: {disc_id}")
                        ran.append("discord")
                        try:
                            (ok_u, user_data), td1 = await with_timeout(
                                oathnet_client.discord_userinfo(disc_id), "discord_auto", default=(False, None)
                            )
                            (ok_h, raw_hist), td2 = await with_timeout(
                                oathnet_client.discord_username_history(disc_id), "discord_auto", default=(False, None)
                            )
                            yield event({
                                "type": "discord", "query_id": disc_id,
                                "user": user_data if ok_u else None,
                                "history": _parse_discord_history(raw_hist) if ok_h else None,
                            })
                        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                            logger.warning("Auto Discord failed %s: %s", disc_id, exc)

        except (httpx.HTTPError, aiosqlite.Error, ValueError, KeyError, TypeError) as exc:
            logger.error("OathNet failed: %s", exc)
            yield event({"type": "module_error", "module": "oathnet", "error": str(exc)})

    # ── Sherlock ──────────────────────────────────────────────────────────
    if run.get("sherlock"):
        yield progress("Scanning social platforms…")
        ran.append("sherlock")
        try:
            uname = query if is_user else query.split("@")[0]
            sherl, timed_out = await with_timeout(
                search_username(uname, False), "sherlock"
            )
            if timed_out:
                yield event({"type": "module_error", "module": "sherlock",
                             "error": "Sherlock timed out after 60s — partial results unavailable"})
            elif sherl:
                social_count = sherl.found_count
                yield event({
                    "type": "sherlock",
                    "found_count": sherl.found_count,
                    "total_checked": sherl.total_checked,
                    "source": sherl.source,
                    "found": [{"platform": p.platform, "url": p.url,
                               "category": p.category, "icon": p.icon}
                              for p in sherl.found],
                })
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.error("Sherlock failed: %s", exc)
            yield event({"type": "module_error", "module": "sherlock", "error": str(exc)})

    # ── Discord ───────────────────────────────────────────────────────────
    if run.get("discord"):
        yield progress("Looking up Discord profile…")
        ran.append("discord")
        if not is_disc:
            yield event({
                "type": "discord",
                "error": "Discord lookup requires a numeric Discord ID (14-19 digits).",
                "hint": "Use Automated mode — it auto-detects Discord IDs found in breach data.",
                "user": None, "history": None,
            })
        else:
            try:
                cached_disc_user = _get_cached("discord_user", query)
                cached_disc_hist = _get_cached("discord_hist", query)

                if cached_disc_user is not None and cached_disc_hist is not None:
                    yield event({
                        "type": "discord",
                        "user": cached_disc_user,
                        "history": _parse_discord_history(cached_disc_hist),
                        "timeout": False,
                    })
                else:
                    (ok_u, user_data), td1 = await with_timeout(
                        oathnet_client.discord_userinfo(query), "discord", default=(False, None)
                    )
                    (ok_h, raw_hist), td2 = await with_timeout(
                        oathnet_client.discord_username_history(query), "discord", default=(False, None)
                    )
                    if ok_u and user_data is not None:
                        _set_cached("discord_user", query, user_data)
                    if ok_h and raw_hist is not None:
                        _set_cached("discord_hist", query, raw_hist)
                    yield event({
                        "type": "discord",
                        "user": user_data if ok_u else None,
                        "history": _parse_discord_history(raw_hist) if ok_h else None,
                        "timeout": td1,
                    })
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                logger.error("Discord failed: %s", exc)
                yield event({"type": "module_error", "module": "discord", "error": str(exc)})

    # ── IP Info ───────────────────────────────────────────────────────────
    if run.get("ip_info"):
        yield progress("Fetching IP geolocation…")
        ran.append("ip_info")
        try:
            cached_ip = _get_cached("ip_info", query)
            if cached_ip is not None:
                yield event({"type": "ip_info", "ok": True, "data": cached_ip})
            else:
                (ok, data), timed_out = await with_timeout(
                    oathnet_client.ip_info(query), "ip_info"
                )
                if timed_out:
                    yield event({"type": "module_error", "module": "ip_info", "error": "IP lookup timed out"})
                else:
                    if ok and data is not None:
                        _set_cached("ip_info", query, data)
                    yield event({"type": "ip_info", "ok": ok, "data": data if ok else None})
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.error("IP info failed: %s", exc)
            yield event({"type": "module_error", "module": "ip_info", "error": str(exc)})

    # ── Subdomains ────────────────────────────────────────────────────────
    if run.get("subdomain"):
        yield progress("Enumerating subdomains…")
        ran.append("subdomain")
        try:
            (ok, data), timed_out = await with_timeout(
                oathnet_client.extract_subdomains(query), "subdomain"
            )
            if timed_out:
                yield event({"type": "module_error", "module": "subdomains", "error": "Subdomain lookup timed out"})
            else:
                subs = data.get("subdomains", []) if ok else []
                yield event({"type": "subdomains", "ok": ok, "data": subs, "count": len(subs)})
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.error("Subdomains failed: %s", exc)
            yield event({"type": "module_error", "module": "subdomains", "error": str(exc)})

    # ── Steam ─────────────────────────────────────────────────────────────
    if run.get("steam"):
        yield progress("Looking up Steam profile…")
        ran.append("steam")
        try:
            cached_steam = _get_cached("steam", query)
            if cached_steam is not None:
                yield event({"type": "steam", "ok": True, "data": cached_steam})
            else:
                (ok, data), timed_out = await with_timeout(
                    oathnet_client.steam_lookup(query), "steam"
                )
                if timed_out:
                    yield event({"type": "module_error", "module": "steam", "error": "Steam lookup timed out"})
                else:
                    if ok and data is not None:
                        _set_cached("steam", query, data)
                    yield event({"type": "steam", "ok": ok,
                                 "data": data if ok else None,
                                 "error": data.get("error") if not ok else None})
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.error("Steam failed: %s", exc)
            yield event({"type": "module_error", "module": "steam", "error": str(exc)})

    # ── Xbox ──────────────────────────────────────────────────────────────
    if run.get("xbox"):
        yield progress("Looking up Xbox profile…")
        ran.append("xbox")
        try:
            cached_xbox = _get_cached("xbox", query)
            if cached_xbox is not None:
                yield event({"type": "xbox", "ok": True, "data": cached_xbox})
            else:
                (ok, data), timed_out = await with_timeout(
                    oathnet_client.xbox_lookup(query), "xbox"
                )
                if timed_out:
                    yield event({"type": "module_error", "module": "xbox", "error": "Xbox lookup timed out"})
                else:
                    if ok and data is not None:
                        _set_cached("xbox", query, data)
                    logger.info("Xbox lookup ok=%s data_keys=%s", ok, list(data.keys()) if isinstance(data, dict) else type(data).__name__)
                    yield event({"type": "xbox", "ok": ok, "data": data})
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.error("Xbox failed: %s", exc)
            yield event({"type": "module_error", "module": "xbox", "error": str(exc)})

    # ── Roblox ────────────────────────────────────────────────────────────
    if run.get("roblox"):
        yield progress("Looking up Roblox profile…")
        ran.append("roblox")
        try:
            cached_roblox = _get_cached("roblox", query)
            if cached_roblox is not None:
                yield event({"type": "roblox", "ok": True, "data": cached_roblox})
            else:
                (ok, data), timed_out = await with_timeout(
                    oathnet_client.roblox_lookup(username=query), "roblox"
                )
                if timed_out:
                    yield event({"type": "module_error", "module": "roblox", "error": "Roblox lookup timed out"})
                else:
                    if ok and data is not None:
                        _set_cached("roblox", query, data)
                    yield event({"type": "roblox", "ok": ok, "data": data if ok else None})
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.error("Roblox failed: %s", exc)
            yield event({"type": "module_error", "module": "roblox", "error": str(exc)})

    # ── GHunt ─────────────────────────────────────────────────────────────
    if run.get("ghunt"):
        yield progress("Looking up Google account (GHunt)…")
        ran.append("ghunt")
        try:
            (ok, data), timed_out = await with_timeout(
                oathnet_client.ghunt(query), "ghunt"
            )
            if timed_out:
                yield event({"type": "module_error", "module": "ghunt", "error": "GHunt timed out"})
            else:
                yield event({"type": "ghunt", "ok": ok,
                             "data": data if ok else None,
                             "error": data.get("error") if not ok else None})
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.error("GHunt failed: %s", exc)
            yield event({"type": "module_error", "module": "ghunt", "error": str(exc)})


    # ── Victims ──────────────────────────────────────────────────────────
    if run.get("victims"):
        yield progress("Searching compromised machine logs (Victims)…")
        ran.append("victims")
        try:
            # Build filters from query type
            v_filters: dict = {}
            if is_email:     v_filters["email"]      = query
            elif is_ip:      v_filters["ip"]         = query
            elif is_disc:    v_filters["discord_id"] = query
            elif is_user:    v_filters["username"]   = query
            else:            pass  # generic query

            ok, data = await oathnet_client.victims_search(
                query if not v_filters else "",
                10, "", "", **v_filters
            )
            if ok:
                items = data.get("items", [])
                meta  = data.get("meta", {})
                yield event({
                    "type":        "victims",
                    "ok":          True,
                    "items":       items[:10],
                    "total":       meta.get("total", len(items)),
                    "has_more":    meta.get("has_more", False),
                    "next_cursor": data.get("next_cursor", ""),
                })
            else:
                yield event({"type": "victims", "ok": False,
                             "error": data.get("error", ""), "items": []})
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.error("Victims failed: %s", exc)
            yield event({"type": "module_error", "module": "victims", "error": str(exc)})

    # ── Discord → Roblox ─────────────────────────────────────────────────
    if run.get("discord_roblox") and is_disc:
        yield progress("Looking up linked Roblox account…")
        ran.append("discord_roblox")
        try:
            (ok, data), timed_out = await with_timeout(
                oathnet_client.discord_to_roblox(query), "discord_roblox", default=(False, {"error": "timed out"})
            )
            if timed_out:
                logger.warning("Module 'discord_roblox' timed out")
                yield event({"type": "discord_roblox", "ok": False, "data": None, "error": "Discord→Roblox lookup timed out"})
            else:
                logger.info("Discord→Roblox result: ok=%s data=%s", ok, data)
                yield event({"type": "discord_roblox", "ok": ok,
                             "data": data if ok else None,
                             "error": data.get("error") if not ok else None})
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.error("Discord→Roblox failed: %s", exc)
            yield event({"type": "module_error", "module": "discord_roblox", "error": str(exc)})

    # ── SpiderFoot ────────────────────────────────────────────────────────
    if run.get("spiderfoot"):
        # D-11: validate target before dispatching to SpiderFoot
        try:
            SpiderFootTarget(target=query)
        except ValidationError:
            yield event({
                "type": "module_error",
                "module": "spiderfoot",
                "error": "invalid target: must be FQDN or IPv4",
            })
        else:
            yield progress("Starting SpiderFoot scan…")
            ran.append("spiderfoot")
            async for sf_event in _run_spiderfoot(query, req.spiderfoot_mode):
                yield sf_event

    elapsed = round(time.time() - t0, 1)

    # ── Audit log — non-blocking via db write queue (no create_task needed) ──
    await _log_search(
        username=username, ip=client_ip, query=query,
        query_type=q_type, mode=req.mode,
        modules_run=list(set(ran)),
        breach_count=breach_count,
        stealer_count=stealer_count,
        social_count=social_count,
        elapsed_s=elapsed,
    )

    # Phase 10: release sentinel so orchestrator deregisters this search
    _sentinel_done.set()

    yield event({
        "type": "done",
        "elapsed_s": elapsed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "modules_run": list(set(ran)),
    })


async def _run_spiderfoot(target: str, scan_mode: str) -> AsyncGenerator[str, None]:
    def event(data: dict) -> str:
        return f"data: {json.dumps(data, default=str)}\n\n"
    try:
        async with httpx.AsyncClient(timeout=600) as http:
            try:
                ping = await http.get(f"{SPIDERFOOT_URL}/api/v1/ping", timeout=5)
                if ping.status_code != 200:
                    yield event({"type": "spiderfoot", "available": False,
                                 "error": "SpiderFoot not responding"})
                    return
            except httpx.HTTPError:
                yield event({"type": "spiderfoot", "available": False,
                             "error": f"Cannot reach SpiderFoot at {SPIDERFOOT_URL}"})
                return

            scan_resp = await http.post(f"{SPIDERFOOT_URL}/api/v1/startscan", data={
                "scanname":   f"nexus_{target}_{int(time.time())}",
                "scantarget": target,
                "usecase":    scan_mode,
                "modulelist": "", "typelist": "",
            })
            if scan_resp.status_code != 200:
                yield event({"type": "spiderfoot", "available": True,
                             "error": f"Failed to start: {scan_resp.text[:200]}"})
                return

            scan_id = scan_resp.json().get("id", "")
            yield event({"type": "spiderfoot_started", "scan_id": scan_id})

            poll_interval = 5.0   # start at 5s
            max_interval  = 30.0  # cap at 30s
            max_elapsed   = 600.0 # 10 min total timeout (same as before: 120 * 5s)
            elapsed       = 0.0

            while elapsed < max_elapsed:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                try:
                    sr = await http.get(f"{SPIDERFOOT_URL}/api/v1/scanstatus/{scan_id}")
                    if sr.status_code != 200:
                        poll_interval = min(poll_interval * 2, max_interval)
                        continue
                    sc = sr.json().get("status", "")
                    yield event({"type": "spiderfoot_progress", "status": sc})
                    if sc in ("FINISHED", "ABORTED", "ERROR"):
                        break
                    # Backoff: double interval each successful poll, cap at 30s
                    poll_interval = min(poll_interval * 2, max_interval)
                except httpx.HTTPError:
                    poll_interval = min(poll_interval * 2, max_interval)
                    continue

            rr = await http.get(f"{SPIDERFOOT_URL}/api/v1/scaneventresults/{scan_id}")
            if rr.status_code == 200:
                RELEVANT = {"EMAILADDR","USERNAME","SOCIAL_MEDIA","ACCOUNT_EXTERNAL_OWNED",
                            "PHONE_NUMBER","IP_ADDRESS","DOMAIN_NAME","LEAKSITE_URL",
                            "PASSWORD_COMPROMISED","DATA_HAS_BEEN_PWNED","DARKNET_MENTION_URL",
                            "MALICIOUS_IPADDR","MALICIOUS_EMAILADDR","GEOINFO"}
                filtered = [{"type": r[4], "data": r[1], "source": r[3]}
                            for r in rr.json() if len(r) >= 5 and r[4] in RELEVANT]
                yield event({"type": "spiderfoot", "available": True,
                             "scan_id": scan_id, "results": filtered[:500],
                             "total": len(filtered)})
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        logger.error("SpiderFoot failed: %s", exc)
        yield event({"type": "spiderfoot", "available": False, "error": str(exc)})


def _parse_discord_history(raw: dict) -> dict | None:
    if not raw:
        return None
    history_raw = raw.get("history", [])
    if not history_raw:
        return None
    return {"usernames": [
        {"username": (e.get("name", [None])[0] if isinstance(e.get("name"), list) else e.get("name")),
         "timestamp": (e.get("time", [None])[0] if isinstance(e.get("time"), list) else e.get("time"))}
        for e in history_raw
    ]}
