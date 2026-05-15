"""Thordata proxy URL helpers for username checks."""
from __future__ import annotations

import re
import urllib.parse

# â”€â”€ Sticky session â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# NOTE: Thordata sesstime unit is MINUTES (Thordata docs, confirmed 2026-04-29).
# CONTEXT.md D-03 specifies "sesstime-60" intending 60 SECONDS. Implementing as
# sesstime-2 (2 minutes = 120 seconds) to match D-03's stated intent of covering
# full Sherlock search (~30s) plus 1x retry margin. See 16-RESEARCH.md Pitfall 2.
_STICKY_SESSTIME_MINUTES = 2


def _masked_proxy_log(proxy_url: str | None) -> str:
    """Return 'host:port' only â€” never user:pass in logs (D-H5)."""
    if not proxy_url:
        return "unset"
    parsed = urllib.parse.urlparse(proxy_url)
    return f"{parsed.hostname}:{parsed.port}"


def _build_sticky_url(base_proxy_url: str, sessid: str) -> str:
    """
    Inject sticky session sessid + sesstime into Thordata proxy username.

    Input:  http://td-customer-USER:PASS@t.pr.thordata.net:9999
    Output: http://td-customer-USER-sessid-abc123ef-sesstime-2:PASS@host:9999

    sesstime=2 = 2 minutes (Thordata unit is MINUTES, minimum 1 minute).
    sessid stripped to alphanumeric-only for URL safety.
    """
    parsed = urllib.parse.urlparse(base_proxy_url)
    safe_sessid = re.sub(r"[^A-Za-z0-9]", "", sessid)[:16]
    new_username = f"{parsed.username}-sessid-{safe_sessid}-sesstime-{_STICKY_SESSTIME_MINUTES}"
    new_netloc = f"{new_username}:{parsed.password}@{parsed.hostname}:{parsed.port}"
    return urllib.parse.urlunparse(parsed._replace(netloc=new_netloc))


def _build_rotate_url(base_proxy_url: str, sessid: str) -> str:
    """Forced IP rotation â€” different sessid = different IP pool assignment (D-06)."""
    return _build_sticky_url(base_proxy_url, sessid + "r")

