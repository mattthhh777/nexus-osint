"""Generic HTML/content validators for username profile pages."""
from __future__ import annotations

import html
import json
import re

from modules.username_check.validators.base import (
    Signal,
    ValidationContext,
    ValidationOutcome,
)

_PARSE_CAP = 100_000
_SCRIPT_OR_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
_COMMENTS = re.compile(r"<!--.*?-->", re.S)
_TITLE = re.compile(r"<title\b[^>]*>(.*?)</title>", re.I | re.S)
_CANONICAL = re.compile(
    r"<link\b(?=[^>]*\brel=[\"'][^\"']*\bcanonical\b[^\"']*[\"'])(?=[^>]*\bhref=[\"']([^\"']+)[\"'])[^>]*>",
    re.I | re.S,
)
_OG_URL = re.compile(
    r"<meta\b(?=[^>]*\bproperty=[\"']og:url[\"'])(?=[^>]*\bcontent=[\"']([^\"']+)[\"'])[^>]*>",
    re.I | re.S,
)
_JSON_LD = re.compile(
    r"<script\b(?=[^>]*\btype=[\"']application/ld\+json[\"'])[^>]*>(.*?)</script>",
    re.I | re.S,
)
_NEGATIVE_TITLE = re.compile(r"\b(404|not found|page not found|user not found|account not found)\b", re.I)


def _clean_visible_html(body: str) -> str:
    body = body[:_PARSE_CAP]
    body = _SCRIPT_OR_STYLE.sub("", body)
    return _COMMENTS.sub("", body)


def _first_match(pattern: re.Pattern[str], body: str) -> str:
    match = pattern.search(body)
    if not match:
        return ""
    return html.unescape(match.group(1)).strip()


def _walk_json(value: object) -> list[object]:
    items = [value]
    if isinstance(value, dict):
        for child in value.values():
            items.extend(_walk_json(child))
    elif isinstance(value, list):
        for child in value:
            items.extend(_walk_json(child))
    return items


def _jsonld_has_username(raw: str, username: str) -> bool:
    try:
        parsed = json.loads(html.unescape(raw).strip())
    except json.JSONDecodeError:
        return False
    username_lower = username.lower()
    interesting_keys = {"@id", "identifier", "alternateName", "name"}
    for node in _walk_json(parsed):
        if not isinstance(node, dict):
            continue
        for key in interesting_keys:
            value = node.get(key)
            if isinstance(value, str) and username_lower in value.lower():
                return True
    return False


class GenericContentValidator:
    name = "generic_content"

    def validate(self, ctx: ValidationContext) -> ValidationOutcome:
        body = _clean_visible_html(ctx.body_text)
        username = ctx.username.lower()
        signals: list[Signal] = []
        warnings: list[str] = []

        title = _first_match(_TITLE, body)
        if title:
            title_lower = title.lower()
            if username in title_lower:
                signals.append(Signal("title_contains_username", 15, "title"))
            if _NEGATIVE_TITLE.search(title):
                signals.append(
                    Signal(
                        "title_negative_marker",
                        -50,
                        "title",
                        hard_negative=True,
                    )
                )

        canonical = _first_match(_CANONICAL, body)
        if canonical and username in canonical.lower():
            signals.append(Signal("canonical_contains_username", 20, "canonical"))

        og_url = _first_match(_OG_URL, body)
        if og_url and username in og_url.lower():
            signals.append(Signal("og_url_contains_username", 15, "og:url"))

        for raw_jsonld in _JSON_LD.findall(ctx.body_text[:_PARSE_CAP]):
            if _jsonld_has_username(raw_jsonld, ctx.username):
                signals.append(Signal("jsonld_contains_username", 25, "json-ld"))
                break
            if raw_jsonld.strip():
                warnings.append("jsonld_no_username_match")

        if ctx.fetch_result.bytes_read >= 3_072:
            signals.append(Signal("body_size_large", 5, ">=3KB"))
        elif ctx.fetch_result.bytes_read <= 500:
            signals.append(Signal("body_size_small", -20, "<=500B"))

        return ValidationOutcome(self.name, signals, warnings)
