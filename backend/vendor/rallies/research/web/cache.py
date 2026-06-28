"""Disk cache for web_fetch responses."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from ..paths import web_fetch_cache_dir

DEFAULT_TTL_SECONDS = 3600


def cache_key_for_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]


def cache_path_for_url(url: str) -> Path:
    return web_fetch_cache_dir() / f"{cache_key_for_url(url)}.json"


def read_cached_fetch(url: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> dict[str, Any] | None:
    path = cache_path_for_url(url)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    fetched_at = payload.get("fetched_at", 0)
    if time.time() - float(fetched_at) > ttl_seconds:
        return None
    return payload


def write_cached_fetch(url: str, payload: dict[str, Any]) -> Path:
    path = cache_path_for_url(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**payload, "url": url, "fetched_at": time.time()}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path
