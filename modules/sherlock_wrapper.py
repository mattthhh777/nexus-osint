"""
NexusOSINT — Sherlock Wrapper
Checks username presence across 25+ social platforms.
Strategy: async HTTP HEAD/GET checks with per-site claim detection.
Falls back to subprocess Sherlock if installed.
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
import requests

logger = logging.getLogger(__name__)

# ── Platform definitions ──────────────────────────────────────────────────────
# Each entry: (name, url_template, claim_type, claim_value)
# claim_type: "status_code" | "text_present" | "text_absent"

PLATFORMS: list[dict] = [
    {
        "name": "GitHub",
        "url": "https://github.com/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "🐙",
    },
    {
        "name": "GitLab",
        "url": "https://gitlab.com/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "🦊",
    },
    {
        "name": "Twitter / X",
        "url": "https://x.com/{username}",
        "claim_type": "text_absent",
        "claim_value": "This account doesn't exist",
        "category": "Social",
        "icon": "🐦",
    },
    {
        "name": "Instagram",
        "url": "https://www.instagram.com/{username}/",
        "claim_type": "text_absent",
        "claim_value": "Sorry, this page",
        "category": "Social",
        "icon": "📸",
    },
    {
        "name": "TikTok",
        "url": "https://www.tiktok.com/@{username}",
        "claim_type": "text_absent",
        "claim_value": "Couldn't find this account",
        "category": "Social",
        "icon": "🎵",
    },
    {
        "name": "Reddit",
        "url": "https://www.reddit.com/user/{username}",
        "claim_type": "text_absent",
        "claim_value": "Sorry, nobody on Reddit",
        "category": "Social",
        "icon": "🤖",
    },
    {
        "name": "LinkedIn",
        "url": "https://www.linkedin.com/in/{username}",
        "claim_type": "text_absent",
        "claim_value": "Page not found",
        "category": "Professional",
        "icon": "💼",
    },
    {
        "name": "Pinterest",
        "url": "https://www.pinterest.com/{username}/",
        "claim_type": "text_absent",
        "claim_value": "Sorry! We couldn't find that page",
        "category": "Social",
        "icon": "📌",
    },
    {
        "name": "YouTube",
        "url": "https://www.youtube.com/@{username}",
        "claim_type": "text_absent",
        "claim_value": "This page isn't available",
        "category": "Video",
        "icon": "▶️",
    },
    {
        "name": "Twitch",
        "url": "https://www.twitch.tv/{username}",
        "claim_type": "text_absent",
        "claim_value": "Sorry. Unless you've got a time machine",
        "category": "Video",
        "icon": "🎮",
    },
    {
        "name": "Steam",
        "url": "https://steamcommunity.com/id/{username}",
        "claim_type": "text_absent",
        "claim_value": "The specified profile could not be found",
        "category": "Gaming",
        "icon": "🎮",
    },
    {
        "name": "Keybase",
        "url": "https://keybase.io/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "🔑",
    },
    {
        "name": "HackerNews",
        "url": "https://news.ycombinator.com/user?id={username}",
        "claim_type": "text_present",
        "claim_value": "user?id=",
        "category": "Dev / Tech",
        "icon": "🟠",
    },
    {
        "name": "Dev.to",
        "url": "https://dev.to/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "👩‍💻",
    },
    {
        "name": "Medium",
        "url": "https://medium.com/@{username}",
        "claim_type": "text_absent",
        "claim_value": "Page not found",
        "category": "Blogging",
        "icon": "✍️",
    },
    {
        "name": "Mastodon (social.linux.pizza)",
        "url": "https://social.linux.pizza/@{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Social",
        "icon": "🐘",
    },
    {
        "name": "Flickr",
        "url": "https://www.flickr.com/people/{username}/",
        "claim_type": "text_absent",
        "claim_value": "Page Not Found",
        "category": "Photo",
        "icon": "📷",
    },
    {
        "name": "Vimeo",
        "url": "https://vimeo.com/{username}",
        "claim_type": "text_absent",
        "claim_value": "Sorry, we couldn't find that page",
        "category": "Video",
        "icon": "🎬",
    },
    {
        "name": "SoundCloud",
        "url": "https://soundcloud.com/{username}",
        "claim_type": "text_absent",
        "claim_value": "We can't find that user",
        "category": "Music",
        "icon": "🎵",
    },
    {
        "name": "Spotify",
        "url": "https://open.spotify.com/user/{username}",
        "claim_type": "text_absent",
        "claim_value": "Page not found",
        "category": "Music",
        "icon": "🎧",
    },
    {
        "name": "DockerHub",
        "url": "https://hub.docker.com/u/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "🐳",
    },
    {
        "name": "NPM",
        "url": "https://www.npmjs.com/~{username}",
        "claim_type": "text_absent",
        "claim_value": "We're sorry, you've reached a 404",
        "category": "Dev / Tech",
        "icon": "📦",
    },
    {
        "name": "PyPI",
        "url": "https://pypi.org/user/{username}/",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "🐍",
    },
    {
        "name": "Telegram",
        "url": "https://t.me/{username}",
        "claim_type": "text_present",
        "claim_value": "tgme_page_title",
        "category": "Messaging",
        "icon": "✈️",
    },
    {
        "name": "Snapchat",
        "url": "https://www.snapchat.com/add/{username}",
        "claim_type": "text_absent",
        "claim_value": "Sorry, we couldn't find",
        "category": "Social",
        "icon": "👻",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

CONNECT_TIMEOUT = aiohttp.ClientTimeout(total=10, connect=5)


# ── Result model ──────────────────────────────────────────────────────────────

@dataclass
class PlatformResult:
    platform: str = ""
    url: str = ""
    found: bool = False
    category: str = ""
    icon: str = ""
    error: Optional[str] = None


@dataclass
class SherlockResult:
    username: str = ""
    success: bool = False
    found: list[PlatformResult] = field(default_factory=list)
    not_found: list[PlatformResult] = field(default_factory=list)
    errors: list[PlatformResult] = field(default_factory=list)
    error: str = ""
    source: str = "internal"  # "internal" | "sherlock_cli"

    @property
    def found_count(self) -> int:
        return len(self.found)

    @property
    def total_checked(self) -> int:
        return len(self.found) + len(self.not_found) + len(self.errors)

    @property
    def risk_score(self) -> int:
        """Simple risk contribution from social presence."""
        return min(self.found_count * 4, 60)


# ── Async engine ──────────────────────────────────────────────────────────────

async def _check_platform(session: aiohttp.ClientSession, username: str, platform: dict) -> PlatformResult:
    url = platform["url"].format(username=username)
    result = PlatformResult(
        platform=platform["name"],
        url=url,
        category=platform.get("category", ""),
        icon=platform.get("icon", ""),
    )
    try:
        async with session.get(url, timeout=CONNECT_TIMEOUT, allow_redirects=True, ssl=False) as resp:
            claim_type = platform["claim_type"]
            claim_value = platform["claim_value"]

            if claim_type == "status_code":
                result.found = (resp.status == int(claim_value))

            elif claim_type in ("text_present", "text_absent"):
                # Read a limited amount of HTML to avoid large payloads
                body = await resp.text(errors="ignore")
                body_lower = body.lower()
                text_lower = str(claim_value).lower()
                if claim_type == "text_present":
                    result.found = text_lower in body_lower
                else:
                    result.found = text_lower not in body_lower and resp.status == 200

    except asyncio.TimeoutError:
        result.error = "timeout"
    except aiohttp.ClientSSLError:
        result.error = "ssl_error"
    except aiohttp.ClientConnectorError:
        result.error = "connection_error"
    except Exception as exc:
        result.error = str(exc)[:80]

    return result


async def _run_async_checks(username: str) -> list[PlatformResult]:
    connector = aiohttp.TCPConnector(ssl=False, limit=15)
    async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:
        tasks = [_check_platform(session, username, p) for p in PLATFORMS]
        return await asyncio.gather(*tasks)


# ── Sherlock CLI integration ──────────────────────────────────────────────────

def _try_sherlock_cli(username: str) -> Optional[SherlockResult]:
    """Attempt to run the official Sherlock CLI if it's on PATH."""
    try:
        proc = subprocess.run(
            ["sherlock", username, "--print-found", "--no-color", "--timeout", "10"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode not in (0, 1):
            return None

        found: list[PlatformResult] = []
        url_pattern = re.compile(r"\[+\] (https?://\S+)")
        for line in proc.stdout.splitlines():
            m = url_pattern.search(line)
            if m:
                url = m.group(1)
                name = url.split("/")[2].replace("www.", "").split(".")[0].capitalize()
                found.append(PlatformResult(platform=name, url=url, found=True, category="Social"))

        result = SherlockResult(
            username=username,
            success=True,
            found=found,
            source="sherlock_cli",
        )
        return result
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def search_username(username: str, prefer_cli: bool = False) -> SherlockResult:
    """
    Main entry point.
    - If prefer_cli=True: tries Sherlock CLI first.
      Falls back to internal async engine if CLI is not found OR returns 0 results.
    - Always runs internal async engine if CLI is unavailable/finds nothing.
    """
    username = username.strip().lstrip("@")

    if prefer_cli:
        cli_result = _try_sherlock_cli(username)
        # Only accept CLI result if it actually found something
        if cli_result and cli_result.found_count > 0:
            return cli_result
        # CLI returned 0 or failed → fall through to internal engine

    # Run async checks in a fresh event loop (Streamlit-safe)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        platform_results = loop.run_until_complete(_run_async_checks(username))
    finally:
        loop.close()

    result = SherlockResult(username=username, success=True, source="internal")
    for pr in platform_results:
        if pr.error:
            result.errors.append(pr)
        elif pr.found:
            result.found.append(pr)
        else:
            result.not_found.append(pr)

    return result