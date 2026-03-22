"""
NexusOSINT — OathNet API Client  v2.0
Based on official OpenAPI spec at https://docs.oathnet.org/openapi.yaml

Corrections vs previous version:
  ❌ OLD base URL : https://api.oathnet.org/v1
  ✅ NEW base URL : https://oathnet.org/api

  ❌ OLD auth     : Authorization: Bearer <key>
  ✅ NEW auth     : x-api-key: <key>

  ❌ OLD endpoints: /breach/email, /breach/username  (don't exist)
  ✅ NEW endpoints: /service/search-breach?q=<query>
                    /service/v2/stealer/search?q=<query>
                    /service/search/init  (session management)
                    /service/holehe, ip-info, steam, xbox, discord-*, roblox-*
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

OATHNET_BASE_URL = "https://oathnet.org/api"
DEFAULT_TIMEOUT  = 20


@dataclass
class BreachRecord:
    dbname:      str       = ""
    email:       str       = ""
    username:    str       = ""
    password:    str       = ""
    ip:          str       = ""
    domain:      str       = ""
    date:        str       = ""
    country:     str       = ""
    discord_id:  str       = ""   # ← novo: captura discordid da API
    phone:       str       = ""   # ← novo: captura phone/phone_number
    data_types:  list[str] = field(default_factory=list)
    extra_fields: dict     = field(default_factory=dict)  # ← todos os campos extras
    raw:         dict      = field(default_factory=dict)


@dataclass
class StealerRecord:
    log:      str       = ""
    url:      str       = ""
    domain:   list[str] = field(default_factory=list)
    username: str       = ""
    password: str       = ""
    email:    list[str] = field(default_factory=list)
    log_id:   str       = ""
    pwned_at: str       = ""
    raw:      dict      = field(default_factory=dict)


@dataclass
class OathnetMeta:
    plan:         str   = ""
    used_today:   int   = 0
    left_today:   int   = 0
    daily_limit:  int   = 0
    is_unlimited: bool  = False
    duration_ms:  float = 0.0


@dataclass
class OathnetResult:
    success:         bool                = False
    query:           str                 = ""
    query_type:      str                 = ""
    breaches:        list[BreachRecord]  = field(default_factory=list)
    results_found:   int                 = 0
    next_cursor:     str                 = ""
    stealers:        list[StealerRecord] = field(default_factory=list)
    stealers_found:  int                 = 0
    holehe_domains:  list[str]           = field(default_factory=list)
    ip_info:         dict                = field(default_factory=dict)
    session_id:      str                 = ""
    meta:            OathnetMeta         = field(default_factory=OathnetMeta)
    error:           str                 = ""
    raw_response:    dict                = field(default_factory=dict)

    @property
    def breach_count(self) -> int:
        return len(self.breaches)

    @property
    def stealer_count(self) -> int:
        return len(self.stealers)

    @property
    def paste_count(self) -> int:
        return 0

    @property
    def domains(self) -> list[str]:
        return self.holehe_domains

    @property
    def risk_score(self) -> int:
        score  = self.breach_count  * 15
        score += self.stealer_count * 20
        score += len(self.holehe_domains) * 3
        return min(score, 100)


class OathnetClient:
    """
    Wrapper around the OathNet v2 REST API.
    Auth   : x-api-key header
    Base   : https://oathnet.org/api
    """

    def __init__(self, api_key: str, base_url: str = OATHNET_BASE_URL, timeout: int = DEFAULT_TIMEOUT):
        if not api_key:
            raise ValueError("OathNet API key cannot be empty.")
        self.api_key  = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout
        self.session  = requests.Session()
        self.session.headers.update({
            "x-api-key":    self.api_key,
            "Accept":       "application/json",
            "Content-Type": "application/json",
            "User-Agent":   "NexusOSINT/2.0",
        })

    def _get(self, endpoint: str, params: dict | None = None) -> tuple[bool, dict]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            return self._handle(resp, url)
        except requests.exceptions.ConnectionError as exc:
            return False, {"error": f"Cannot reach OathNet API ({self.base_url}). Network error: {exc}"}
        except requests.exceptions.Timeout:
            return False, {"error": f"Request timed out after {self.timeout}s — {url}"}
        except requests.exceptions.RequestException as exc:
            return False, {"error": f"HTTP error: {exc}"}

    def _post(self, endpoint: str, payload: dict) -> tuple[bool, dict]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            return self._handle(resp, url)
        except requests.exceptions.ConnectionError as exc:
            return False, {"error": f"Cannot reach OathNet API: {exc}"}
        except requests.exceptions.Timeout:
            return False, {"error": f"Request timed out after {self.timeout}s"}
        except requests.exceptions.RequestException as exc:
            return False, {"error": f"HTTP error: {exc}"}

    @staticmethod
    def _handle(resp: requests.Response, url: str) -> tuple[bool, dict]:
        status = resp.status_code
        try:
            body = resp.json()
        except ValueError:
            body = {"error": f"Non-JSON response (HTTP {status}): {resp.text[:300]}"}

        if status == 401:
            return False, {"error": "Invalid or expired API key (HTTP 401). Check your x-api-key."}
        if status == 403:
            return False, {"error": "Forbidden (HTTP 403) — quota exceeded or Cloudflare block."}
        if status == 404:
            if isinstance(body, dict) and not body.get("success", True):
                return False, {"error": body.get("message", "Not found."), "body": body}
            return False, {"error": f"Endpoint not found: {url} (HTTP 404)."}
        if status == 429:
            return False, {"error": "Rate limit exceeded (HTTP 429). Wait and retry."}
        if status >= 500:
            return False, {"error": f"OathNet server error (HTTP {status})."}

        if isinstance(body, dict) and body.get("success") is False:
            msg = body.get("message") or (body.get("errors") or {}).get("error", "API returned success=false")
            return False, {"error": msg, "body": body}

        return True, body

    @staticmethod
    def _parse_meta(data: dict) -> OathnetMeta:
        m       = OathnetMeta()
        raw     = data.get("_meta") or {}
        user    = raw.get("user", {})
        lookups = raw.get("lookups", {})
        perf    = raw.get("performance", {})
        m.plan         = user.get("plan", "")
        m.used_today   = lookups.get("used_today", 0)
        m.left_today   = lookups.get("left_today", 0)
        m.daily_limit  = lookups.get("daily_limit", 0)
        m.is_unlimited = lookups.get("is_unlimited", False)
        m.duration_ms  = perf.get("duration_ms", 0.0)
        return m

    # ── Session ───────────────────────────────────────────────────────────

    def init_session(self, query: str) -> Optional[str]:
        ok, data = self._post("service/search/init", {"query": query})
        if not ok:
            logger.warning("Session init failed: %s", data.get("error"))
            return None
        return data.get("data", {}).get("session", {}).get("id")

    # ── Breach search ─────────────────────────────────────────────────────

    def search_breach(self, query: str, cursor: str = "", session_id: str = "") -> OathnetResult:
        result = OathnetResult(query=query, query_type="breach")
        params: dict = {"q": query}
        if cursor:
            params["cursor"] = cursor
        if session_id:
            params["search_id"] = session_id

        ok, data = self._get("service/search-breach", params=params)
        if not ok:
            result.error = data.get("error", "Breach search failed.")
            return result

        result.success      = True
        result.raw_response = data
        payload             = data.get("data", data)
        result.results_found = payload.get("results_found", 0)
        result.next_cursor   = payload.get("nextCursorMark") or payload.get("next_cursor_mark", "")
        result.meta          = self._parse_meta(payload)

        # Known fields that are handled explicitly
        KNOWN_FIELDS = {"dbname", "email", "username", "password", "ip", "domain",
                        "date", "created_at", "country", "discordid", "discord_id",
                        "phone", "phone_number", "id", "_version_", "_meta"}

        for item in payload.get("results", []):
            if not isinstance(item, dict):
                continue
            u   = item.get("username", "")
            e   = item.get("email", "")
            c   = item.get("country", "")
            did = item.get("discordid") or item.get("discord_id", "")
            ph  = item.get("phone") or item.get("phone_number", "")

            # Capture any fields not explicitly handled as extra_fields
            extra = {
                k: (v[0] if isinstance(v, list) and v else v)
                for k, v in item.items()
                if k not in KNOWN_FIELDS and v not in (None, "", [], {})
            }

            result.breaches.append(BreachRecord(
                dbname       = item.get("dbname", ""),
                email        = (e[0] if isinstance(e, list) else e) or "",
                username     = (u[0] if isinstance(u, list) else u) or "",
                password     = item.get("password", ""),
                ip           = item.get("ip", ""),
                domain       = item.get("domain", ""),
                date         = item.get("date") or item.get("created_at", ""),
                country      = (c[0] if isinstance(c, list) else c) or "",
                discord_id   = str(did) if did else "",
                phone        = str(ph)  if ph  else "",
                extra_fields = extra,
                raw          = item,
            ))
        return result

    # ── Stealer v2 ────────────────────────────────────────────────────────

    def search_stealer_v2(self, query: str, cursor: str = "", session_id: str = "", page_size: int = 25) -> OathnetResult:
        result = OathnetResult(query=query, query_type="stealer")
        params: dict = {"q": query, "page_size": page_size}
        if cursor:
            params["cursor"] = cursor
        if session_id:
            params["search_id"] = session_id

        ok, data = self._get("service/v2/stealer/search", params=params)
        if not ok:
            result.error = data.get("error", "Stealer search failed.")
            return result

        result.success        = True
        result.raw_response   = data
        payload               = data.get("data", data)
        v2_meta               = payload.get("meta", {})
        result.stealers_found = v2_meta.get("total", 0)
        result.next_cursor    = payload.get("next_cursor", "")
        result.meta           = self._parse_meta(payload)

        for item in payload.get("items", []):
            result.stealers.append(StealerRecord(
                log      = item.get("log", ""),
                url      = item.get("url", ""),
                domain   = item.get("domain", []),
                username = item.get("username", ""),
                password = item.get("password", ""),
                email    = item.get("email", []),
                log_id   = item.get("log_id", ""),
                pwned_at = item.get("pwned_at", ""),
                raw      = item,
            ))
        return result

    # ── Holehe ────────────────────────────────────────────────────────────

    def holehe(self, email: str, session_id: str = "") -> OathnetResult:
        result = OathnetResult(query=email, query_type="holehe")
        params: dict = {"email": email}
        if session_id:
            params["search_id"] = session_id
        ok, data = self._get("service/holehe", params=params)
        if not ok:
            result.error = data.get("error", "Holehe failed.")
            return result
        result.success        = True
        result.raw_response   = data
        payload               = data.get("data", data)
        result.holehe_domains = payload.get("domains", [])
        result.meta           = self._parse_meta(payload)
        return result

    # ── OSINT helpers ─────────────────────────────────────────────────────

    def ip_info(self, ip: str, session_id: str = "") -> tuple[bool, dict]:
        params: dict = {"ip": ip}
        if session_id:
            params["search_id"] = session_id
        ok, data = self._get("service/ip-info", params=params)
        return (True, data.get("data", data)) if ok else (False, {"error": data.get("error", "")})

    def steam_lookup(self, steam_id: str, session_id: str = "") -> tuple[bool, dict]:
        params: dict = {"steam_id": steam_id}
        if session_id:
            params["search_id"] = session_id
        ok, data = self._get("service/steam", params=params)
        return (True, data.get("data", data)) if ok else (False, {"error": data.get("error", "")})

    def xbox_lookup(self, xbl_id: str, session_id: str = "") -> tuple[bool, dict]:
        params: dict = {"xbl_id": xbl_id}
        if session_id:
            params["search_id"] = session_id
        ok, data = self._get("service/xbox", params=params)
        return (True, data.get("data", data)) if ok else (False, {"error": data.get("error", "")})

    def roblox_lookup(self, username: str = "", user_id: str = "", session_id: str = "") -> tuple[bool, dict]:
        params: dict = {}
        if username:
            params["username"] = username
        elif user_id:
            params["user_id"] = user_id
        if session_id:
            params["search_id"] = session_id
        ok, data = self._get("service/roblox-userinfo", params=params)
        return (True, data.get("data", data)) if ok else (False, {"error": data.get("error", "")})

    def discord_userinfo(self, discord_id: str, session_id: str = "") -> tuple[bool, dict]:
        params: dict = {"discord_id": discord_id}
        if session_id:
            params["search_id"] = session_id
        ok, data = self._get("service/discord-userinfo", params=params)
        return (True, data.get("data", data)) if ok else (False, {"error": data.get("error", "")})

    def discord_username_history(self, discord_id: str, session_id: str = "") -> tuple[bool, dict]:
        params: dict = {"discord_id": discord_id}
        if session_id:
            params["search_id"] = session_id
        ok, data = self._get("service/discord-username-history", params=params)
        return (True, data.get("data", data)) if ok else (False, {"error": data.get("error", "")})

    def extract_subdomains(self, domain: str, is_alive: bool = False, session_id: str = "") -> tuple[bool, dict]:
        params: dict = {"domain": domain, "is_alive": is_alive}
        if session_id:
            params["search_id"] = session_id
        ok, data = self._get("service/extract-subdomain", params=params)
        return (True, data.get("data", data)) if ok else (False, {"error": data.get("error", "")})

    # ── Convenience wrappers (kept for app.py compatibility) ──────────────

    def search_email(self, email: str) -> OathnetResult:
        session_id     = self.init_session(email) or ""
        breach         = self.search_breach(email, session_id=session_id)
        stealer        = self.search_stealer_v2(email, session_id=session_id)
        holehe_r       = self.holehe(email, session_id=session_id)
        breach.stealers       = stealer.stealers
        breach.stealers_found = stealer.stealers_found
        breach.holehe_domains = holehe_r.holehe_domains
        breach.session_id     = session_id
        breach.query_type     = "email"
        if not breach.success and (stealer.success or holehe_r.success):
            breach.success = True
        return breach

    def search_username(self, username: str) -> OathnetResult:
        session_id     = self.init_session(username) or ""
        breach         = self.search_breach(username, session_id=session_id)
        stealer        = self.search_stealer_v2(username, session_id=session_id)
        breach.stealers       = stealer.stealers
        breach.stealers_found = stealer.stealers_found
        breach.session_id     = session_id
        breach.query_type     = "username"
        if not breach.success and stealer.success:
            breach.success = True
        return breach

    def validate_key(self) -> tuple[bool, str]:
        ok, data = self._post("service/search/init", {"query": "nexusosint_keycheck"})
        if ok:
            plan = data.get("data", {}).get("user", {}).get("plan", "unknown")
            return True, f"Chave válida. Plano: {plan}"
        err = data.get("error", "")
        if "401" in err or "invalid" in err.lower():
            return False, f"Chave inválida: {err}"
        return False, err
    # ── GHunt (Google Account OSINT) ─────────────────────────────────────

    def ghunt(self, email: str, session_id: str = "") -> tuple[bool, dict]:
        """
        Google account OSINT via GHunt.
        Returns profile info: name, picture, Gaia ID, Maps reviews, last seen, etc.
        Note: May fail if upstream OSID detection fails — handle gracefully.
        """
        params: dict = {"email": email}
        if session_id:
            params["search_id"] = session_id
        ok, data = self._get("service/ghunt", params=params)
        if not ok:
            return False, {"error": data.get("error", "GHunt lookup failed.")}
        payload = data.get("data", data)
        return True, payload

    # ── Minecraft Username History ────────────────────────────────────────

    def minecraft_history(self, username: str, session_id: str = "") -> tuple[bool, dict]:
        """
        Minecraft username history via Mojang API proxy.
        Returns: uuid, current username, history list [{username, changed_at}].
        Note: Endpoint may be temporarily unavailable (503).
        """
        params: dict = {"username": username}
        if session_id:
            params["search_id"] = session_id
        ok, data = self._get("service/mc-history", params=params)
        if not ok:
            return False, {"error": data.get("error", "Minecraft lookup failed.")}
        payload = data.get("data", data)
        return True, payload