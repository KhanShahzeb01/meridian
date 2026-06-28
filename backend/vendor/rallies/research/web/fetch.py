"""Fetch a public URL and return markdown (Wave 2 rank 5)."""

from __future__ import annotations

import logging
from typing import Any

import requests

from .cache import read_cached_fetch, write_cached_fetch
from .html_text import html_to_markdown, truncate_text
from .url_policy import validate_fetch_url

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_MAX_CHARS = 80_000
USER_AGENT = "Rallies-CLI/1.0 (research; +https://rallies.ai)"


def http_get(url: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[str, str | None]:
    """Returns (body_text, content_type)."""
    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json,text/plain,*/*"},
        allow_redirects=True,
    )
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    response.encoding = response.encoding or "utf-8"
    return response.text, content_type


def body_to_markdown(body: str, content_type: str | None) -> tuple[str, str | None]:
    ctype = (content_type or "").lower()
    if "html" in ctype or "<html" in body[:2000].lower():
        return html_to_markdown(body)
    return body.strip(), None


def fetch_url(
    url: str,
    *,
    use_cache: bool = True,
    max_chars: int = DEFAULT_MAX_CHARS,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """
    Fetch URL → markdown. On cache hit returns cached payload with cached=True.
    Raises ValueError for bad URLs; requests.HTTPError for HTTP failures.
    """
    normalized = validate_fetch_url(url)
    if use_cache:
        cached = read_cached_fetch(normalized)
        if cached:
            cached["cached"] = True
            return cached

    raw, content_type = http_get(normalized, timeout=timeout)
    markdown, title = body_to_markdown(raw, content_type)
    markdown, truncated = truncate_text(markdown, max_chars)
    payload: dict[str, Any] = {
        "url": normalized,
        "title": title,
        "markdown": markdown,
        "truncated": truncated,
        "cached": False,
        "content_type": content_type,
    }
    write_cached_fetch(normalized, payload)
    return payload
