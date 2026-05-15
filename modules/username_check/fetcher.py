"""Capped HTTP fetch helpers for username checks."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import httpx

_SHERLOCK_BODY_CAP = 262_144  # 256KB per response (D-15)


@dataclass(frozen=True)
class FetchResult:
    status_code: int
    headers: dict[str, str]
    body: bytes
    bytes_read: int
    final_url: str
    redirect_chain: list[str]

    def __iter__(self) -> Iterator[object]:
        """Preserve Phase A tuple unpacking contract for existing callers."""
        yield self.status_code
        yield self.headers
        yield self.body
        yield self.bytes_read


async def _fetch_with_cap(
    client: httpx.AsyncClient,
    url: str,
    cap_bytes: int = _SHERLOCK_BODY_CAP,
) -> FetchResult:
    """
    Fetch URL, stopping body read at cap_bytes.
    Returns FetchResult with final URL and redirect chain.
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
        redirect_chain = [str(item.url) for item in resp.history]
        if redirect_chain:
            redirect_chain.append(str(resp.url))
        return FetchResult(
            status_code=resp.status_code,
            headers=headers,
            body=body,
            bytes_read=total,
            final_url=str(resp.url),
            redirect_chain=redirect_chain,
        )

