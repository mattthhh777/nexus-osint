"""Capped HTTP fetch helpers for username checks."""
from __future__ import annotations

import httpx

_SHERLOCK_BODY_CAP = 262_144  # 256KB per response (D-15)


async def _fetch_with_cap(
    client: httpx.AsyncClient,
    url: str,
    cap_bytes: int = _SHERLOCK_BODY_CAP,
) -> tuple[int, dict, bytes, int]:
    """
    Fetch URL, stopping body read at cap_bytes.
    Returns (status_code, response_headers, body_bytes, actual_bytes_read).
    Headers captured BEFORE body iteration (Cloudflare cf-mitigated detection â€” Pitfall 5).
    Real cap, not resp.text slice (Pitfall 4 fix).
    """
    async with client.stream("GET", url) as resp:
        headers = dict(resp.headers)
        chunks: list[bytes] = []
        total = 0
        async for chunk in resp.aiter_bytes(chunk_size=8192):
            chunks.append(chunk)
            total += len(chunk)
            if total >= cap_bytes:
                break
        body = b"".join(chunks)
        return resp.status_code, headers, body, total

