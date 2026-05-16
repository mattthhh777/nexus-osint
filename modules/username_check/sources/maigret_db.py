"""Maigret site database adapter.

Only site metadata is used. Runtime fetching, rate limiting, proxy handling,
body caps, validation, and scoring stay in NexusOSINT code.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

logger = logging.getLogger("nexusosint.sherlock")

try:
    from maigret.sites import MaigretDatabase
except ImportError:
    MaigretDatabase = None

_PACKAGED_DATA_PATH = Path(__file__).resolve().parent / "data" / "maigret_data.json"
_LOCAL_DATA_PATH = (
    Path(__file__).resolve().parents[3]
    / "maigret_repo"
    / "maigret"
    / "resources"
    / "data.json"
)

_LOW_RELIABILITY_NAMES = {
    "instagram",
    "linkedin",
    "reddit",
    "twitter",
    "x",
}

_CATEGORY_BY_TAG = {
    "blog": "Blogging",
    "business": "Professional",
    "coding": "Dev / Tech",
    "dev": "Dev / Tech",
    "gaming": "Gaming",
    "music": "Music",
    "photo": "Photo",
    "social": "Social",
    "video": "Video",
}


def _first(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _expand_url(url: str, site: Any) -> str:
    url_main = str(_get(site, "url_main", "urlMain", "") or "")
    url_subpath = str(_get(site, "url_subpath", "urlSubpath", "") or "")
    return (
        url.replace("{urlMain}", url_main.rstrip("/"))
        .replace("{urlSubpath}", url_subpath.strip("/"))
    )


def _get(site: Any, snake_name: str, camel_name: str, default: Any = None) -> Any:
    if isinstance(site, dict):
        return site.get(camel_name, default)
    return getattr(site, snake_name, default)


def _category(tags: list[str]) -> str:
    for tag in tags:
        category = _CATEGORY_BY_TAG.get(tag.lower())
        if category:
            return category
    return "Social"


def _host_key(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").removeprefix("www.").lower()


def _reliability(name: str, tags: list[str], protection: list[str]) -> str:
    lowered = name.lower()
    if lowered in _LOW_RELIABILITY_NAMES or protection:
        return "low"
    if "social" in {tag.lower() for tag in tags} and lowered in _LOW_RELIABILITY_NAMES:
        return "low"
    return "normal"


def _adapt_site(name: str, site: Any) -> dict | None:
    if bool(_get(site, "disabled", "disabled", False)):
        return None
    if str(_get(site, "type", "type", "username")) != "username":
        return None

    method = str(_get(site, "request_method", "requestMethod", "") or "GET").upper()
    if method not in {"", "GET", "HEAD"}:
        return None

    url = _expand_url(str(_get(site, "url", "url", "") or ""), site)
    if not url.startswith(("http://", "https://")) or "{username}" not in url:
        return None

    tags = _as_list(_get(site, "tags", "tags", []))
    protection = _as_list(_get(site, "protection", "protection", []))
    presence = _as_list(_get(site, "presense_strs", "presenseStrs", []))
    absence = _as_list(_get(site, "absence_strs", "absenceStrs", []))
    errors = _get(site, "errors", "errors", {}) or {}
    error_markers = list(errors.keys()) if isinstance(errors, dict) else []

    if presence:
        claim_type = "text_present"
        claim_value = _first(presence)
    elif absence:
        claim_type = "text_absent"
        claim_value = _first(absence)
    else:
        claim_type = "status_code"
        claim_value = 200

    return {
        "name": f"Maigret: {name}",
        "url": url,
        "claim_type": claim_type,
        "claim_value": claim_value,
        "category": _category(tags),
        "icon": "",
        "negative_markers": [*absence, *error_markers],
        "reliability": _reliability(name, tags, protection),
        "source": "maigret",
        "maigret_tags": tags,
        "maigret_domain": _host_key(url),
    }


def _load_raw_json() -> dict:
    if MaigretDatabase is not None:
        for package, path_parts in (
            ("maigret.resources", ("data.json",)),
            ("maigret", ("resources", "data.json")),
        ):
            try:
                data_path = resources.files(package).joinpath(*path_parts)
                return json.loads(data_path.read_text(encoding="utf-8"))
            except (ModuleNotFoundError, FileNotFoundError, OSError, ValueError):
                continue

    for path in (_PACKAGED_DATA_PATH, _LOCAL_DATA_PATH):
        try:
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            continue
    raise FileNotFoundError("Maigret data.json not found")


def _load_via_maigret_database(data: dict) -> list[tuple[str, Any]]:
    if MaigretDatabase is None:
        return []
    database = MaigretDatabase().load_from_json(data)
    ranked = database.ranked_sites_dict(top=10_000, disabled=False, id_type="username")
    return list(ranked.items())


def _load_raw_sites(data: dict) -> list[tuple[str, dict]]:
    sites = data.get("sites", {})
    if not isinstance(sites, dict):
        return []

    def rank(item: tuple[str, dict]) -> tuple[int, str]:
        name, site = item
        raw_rank = site.get("alexaRank", 2_147_483_647)
        if not isinstance(raw_rank, int):
            raw_rank = 2_147_483_647
        return raw_rank, name

    return sorted(sites.items(), key=rank)


@lru_cache(maxsize=1)
def _load_all_sites() -> tuple[dict, ...]:
    try:
        data = _load_raw_json()
        raw_sites = _load_via_maigret_database(data) or _load_raw_sites(data)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        logger.warning("Maigret DB load failed: %s", type(exc).__name__)
        return ()

    adapted: list[dict] = []
    seen_domains: set[str] = set()
    for name, site in raw_sites:
        candidate = _adapt_site(name, site)
        if candidate is None:
            continue
        domain = str(candidate.get("maigret_domain", ""))
        if domain and domain in seen_domains:
            continue
        adapted.append(candidate)
        seen_domains.add(domain)
    return tuple(adapted)


def load_top_n_sites(n: int = 500) -> list[dict]:
    if n <= 0:
        return []
    return [dict(site) for site in _load_all_sites()[:n]]


def get_loaded_site_count(n: int = 500) -> int:
    return len(load_top_n_sites(n))
