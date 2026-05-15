"""Curated Sherlock-style username platform definitions."""
from __future__ import annotations
PLATFORMS: list[dict] = [
    {
        "name": "GitHub",
        "url": "https://github.com/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "ðŸ™",
        "negative_markers": ["Not Found", "Page not found"],
    },
    {
        "name": "GitLab",
        "url": "https://gitlab.com/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "ðŸ¦Š",
        "negative_markers": ["not found", "404 Page Not Found"],
    },
    {
        "name": "Twitter / X",
        "url": "https://x.com/{username}",
        "claim_type": "text_absent",
        "claim_value": "This account doesn't exist",
        "category": "Social",
        "icon": "ðŸ¦",
        # Audit 2026-05-01: X returns a full React SPA (HTTP 200, ~256KB).
        # The marker "this account doesn't exist" is injected client-side by
        # React and is NOT present in the SSR HTML received by httpx.
        # Cleared negative_markers: no SSR-detectable text distinguishes
        # missing vs existing accounts from the raw HTTP response body.
        "negative_markers": [],
        "reliability": "low",
    },
    {
        "name": "Instagram",
        "url": "https://www.instagram.com/{username}/",
        "claim_type": "text_absent",
        "claim_value": "Sorry, this page",
        "category": "Social",
        "icon": "ðŸ“¸",
        # Audit 2026-05-01: Instagram returns HTTP 200 + full React SPA (~800KB)
        # regardless of account existence. "Sorry, this page isn't available"
        # is rendered client-side only. SSR HTML contains no detectable
        # text difference. Negative markers cleared; platform reliability
        # is LOW without browser execution or residential proxy.
        "negative_markers": [],
        "reliability": "low",
    },
    {
        "name": "TikTok",
        "url": "https://www.tiktok.com/@{username}",
        "claim_type": "text_absent",
        "claim_value": "Couldn't find this account",
        "category": "Social",
        "icon": "ðŸŽµ",
        "negative_markers": ["couldn't find this account", '"statusCode":10221'],
    },
    {
        "name": "Reddit",
        "url": "https://www.reddit.com/user/{username}",
        "claim_type": "text_absent",
        "claim_value": "Sorry, nobody on Reddit",
        "category": "Social",
        "icon": "ðŸ¤–",
        # Audit 2026-05-01: Reddit returns HTTP 200 with a bot-verification
        # challenge page ("Please wait for verification") for automated
        # requests. The marker "sorry, nobody on reddit goes by that name"
        # is NOT present in the challenge page body. Negative markers cleared
        # since the challenge page never contains them; the claim_value
        # "Sorry, nobody on Reddit" also won't be found in the challenge body,
        # so the text_absent claim will score positively even for nonexistent
        # accounts â€” known limitation requiring proxy or API access.
        "negative_markers": [],
        "reliability": "low",
    },
    {
        "name": "LinkedIn",
        "url": "https://www.linkedin.com/in/{username}",
        "claim_type": "text_absent",
        "claim_value": "Page not found",
        "category": "Professional",
        "icon": "ðŸ’¼",
        # Audit 2026-05-01: LinkedIn returns HTTP 999 (proprietary login-wall
        # status code) for all unauthenticated requests. Negative markers are
        # unreachable â€” the response body is a JS redirect to the login page.
        # text_absent claim will not match (body does not contain "Page not
        # found") â†’ score boost applies even for nonexistent accounts.
        # No SSR-detectable markers; platform requires authenticated session.
        "negative_markers": [],
        "reliability": "low",
    },
    {
        "name": "Pinterest",
        "url": "https://www.pinterest.com/{username}/",
        "claim_type": "text_absent",
        "claim_value": "Sorry! We couldn't find that page",
        "category": "Social",
        "icon": "ðŸ“Œ",
        "negative_markers": ["sorry! we couldn't find that page"],
    },
    {
        "name": "YouTube",
        "url": "https://www.youtube.com/@{username}",
        "claim_type": "text_absent",
        "claim_value": "This page isn't available",
        "category": "Video",
        "icon": "â–¶ï¸",
        "negative_markers": ["this page isn't available", "404 not found"],
    },
    {
        "name": "Twitch",
        "url": "https://www.twitch.tv/{username}",
        "claim_type": "text_absent",
        "claim_value": "Sorry. Unless you've got a time machine",
        "category": "Video",
        "icon": "ðŸŽ®",
        "negative_markers": ["sorry. unless you've got a time machine"],
    },
    {
        "name": "Steam",
        "url": "https://steamcommunity.com/id/{username}",
        "claim_type": "text_absent",
        "claim_value": "The specified profile could not be found",
        "category": "Gaming",
        "icon": "ðŸŽ®",
        "negative_markers": ["the specified profile could not be found"],
    },
    {
        "name": "Keybase",
        "url": "https://keybase.io/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "ðŸ”‘",
        "negative_markers": ["not found", "user not found"],
    },
    {
        "name": "HackerNews",
        "url": "https://news.ycombinator.com/user?id={username}",
        "claim_type": "text_present",
        "claim_value": "user?id=",
        "category": "Dev / Tech",
        "icon": "ðŸŸ ",
        "negative_markers": ["no such user", "sorry"],
    },
    {
        "name": "Dev.to",
        "url": "https://dev.to/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "ðŸ‘©â€ðŸ’»",
        "negative_markers": ["page not found", "404 not found"],
    },
    {
        "name": "Medium",
        "url": "https://medium.com/@{username}",
        "claim_type": "text_absent",
        "claim_value": "Page not found",
        "category": "Blogging",
        "icon": "âœï¸",
        "negative_markers": ["page not found"],
    },
    {
        "name": "Mastodon (social.linux.pizza)",
        "url": "https://social.linux.pizza/@{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Social",
        "icon": "ðŸ˜",
        "negative_markers": ["not found", "this resource was not found"],
    },
    {
        "name": "Flickr",
        "url": "https://www.flickr.com/people/{username}/",
        "claim_type": "text_absent",
        "claim_value": "Page Not Found",
        "category": "Photo",
        "icon": "ðŸ“·",
        "negative_markers": ["page not found"],
    },
    {
        "name": "Vimeo",
        "url": "https://vimeo.com/{username}",
        "claim_type": "text_absent",
        "claim_value": "Sorry, we couldn't find that page",
        "category": "Video",
        "icon": "ðŸŽ¬",
        "negative_markers": ["sorry, we couldn't find that page"],
    },
    {
        "name": "SoundCloud",
        "url": "https://soundcloud.com/{username}",
        "claim_type": "text_absent",
        "claim_value": "We can't find that user",
        "category": "Music",
        "icon": "ðŸŽµ",
        "negative_markers": ["we can't find that user"],
    },
    {
        "name": "Spotify",
        "url": "https://open.spotify.com/user/{username}",
        "claim_type": "text_absent",
        "claim_value": "Page not found",
        "category": "Music",
        "icon": "ðŸŽ§",
        "negative_markers": ["page not found", "user not found"],
    },
    {
        "name": "DockerHub",
        "url": "https://hub.docker.com/u/{username}",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "ðŸ³",
        "negative_markers": ["not found", "page not found"],
    },
    {
        "name": "NPM",
        "url": "https://www.npmjs.com/~{username}",
        "claim_type": "text_absent",
        "claim_value": "We're sorry, you've reached a 404",
        "category": "Dev / Tech",
        "icon": "ðŸ“¦",
        "negative_markers": ["we're sorry, you've reached a 404"],
    },
    {
        "name": "PyPI",
        "url": "https://pypi.org/user/{username}/",
        "claim_type": "status_code",
        "claim_value": 200,
        "category": "Dev / Tech",
        "icon": "ðŸ",
        "negative_markers": ["not found", "404: page not found"],
    },
    {
        "name": "Telegram",
        "url": "https://t.me/{username}",
        "claim_type": "text_present",
        "claim_value": "tgme_page_title",
        "category": "Messaging",
        "icon": "âœˆï¸",
        "negative_markers": [],
    },
    {
        "name": "Snapchat",
        "url": "https://www.snapchat.com/add/{username}",
        "claim_type": "text_absent",
        "claim_value": "Sorry, we couldn't find",
        "category": "Social",
        "icon": "ðŸ‘»",
        "negative_markers": ["sorry, we couldn't find"],
    },
]

