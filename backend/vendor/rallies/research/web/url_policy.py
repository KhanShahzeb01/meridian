"""URL validation for web_fetch (blocks obvious non-http targets)."""

from __future__ import annotations

from urllib.parse import urlparse


def normalize_url(url: str) -> str:
    text = url.strip()
    if not text:
        raise ValueError("URL is empty")
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    return text


def validate_fetch_url(url: str) -> str:
    normalized = normalize_url(url)
    parsed = urlparse(normalized)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported scheme: {parsed.scheme}")
    if not parsed.netloc:
        raise ValueError("URL has no host")
    host = parsed.hostname or ""
    if host in ("localhost", "127.0.0.1", "0.0.0.0") or host.endswith(".local"):
        raise ValueError(f"Blocked host: {host}")
    return normalized
