"""
Bundled + user-extensible ticker catalog for $-prefixed symbols and tab completion.

User overrides: ~/.rallies/tickers.json
  {
    "add": [{"symbol": "FOO", "name": "Optional label"}],
    "remove": ["SPY"]
  }
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

DOLLAR_TICKER_RE = re.compile(r"\$([A-Za-z]{1,6}(?:\.[A-Z])?(?:-[A-Z])?)\b")
_TICKER_TOKEN_RE = re.compile(r"^[A-Za-z]{1,6}(?:[.-][A-Za-z]{1,2})?$")

POPULAR_SYMBOLS = (
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "SPY",
    "QQQ",
    "BRK-B",
    "JPM",
    "V",
)

USER_TICKERS_FILENAME = "tickers.json"


def user_tickers_path() -> Path:
    path = Path.home() / ".rallies"
    path.mkdir(parents=True, exist_ok=True)
    return path / USER_TICKERS_FILENAME


def _default_user_config() -> dict[str, Any]:
    return {"add": [], "remove": []}


def load_user_config(*, create: bool = False) -> dict[str, Any]:
    path = user_tickers_path()
    if not path.exists():
        if create:
            path.write_text(
                json.dumps(
                    {
                        **_default_user_config(),
                        "_comment": "add: extra symbols; remove: hide bundled symbols",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return _default_user_config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _default_user_config()
    if not isinstance(data, dict):
        return _default_user_config()
    add = data.get("add") if isinstance(data.get("add"), list) else []
    remove = data.get("remove") if isinstance(data.get("remove"), list) else []
    return {"add": add, "remove": remove}


def save_user_config(config: dict[str, Any]) -> Path:
    path = user_tickers_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "add": config.get("add") or [],
        "remove": config.get("remove") or [],
        "_comment": "add: extra symbols; remove: hide bundled symbols",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _load_builtin_catalog() -> list[dict[str, str]]:
    try:
        raw = resources.files("rallies.data").joinpath("tickers_builtin.json").read_text(
            encoding="utf-8"
        )
        data = json.loads(raw)
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        return [{"symbol": s, "name": "", "exchange": ""} for s in POPULAR_SYMBOLS]
    if not isinstance(data, list):
        return []
    out: list[dict[str, str]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("symbol") or "").strip().upper()
        if not sym:
            continue
        out.append(
            {
                "symbol": sym,
                "name": str(row.get("name") or "").strip(),
                "exchange": str(row.get("exchange") or "").strip(),
            }
        )
    return out


def _normalize_entry(symbol: str, name: str = "", exchange: str = "") -> dict[str, str]:
    sym = symbol.strip().upper()
    return {"symbol": sym, "name": (name or "").strip(), "exchange": (exchange or "").strip()}


@lru_cache(maxsize=1)
def get_ticker_catalog() -> tuple[dict[str, str], ...]:
    """Merged builtin + user add, minus user remove. Cached until process exit."""
    by_symbol: dict[str, dict[str, str]] = {
        row["symbol"]: dict(row) for row in _load_builtin_catalog()
    }
    user = load_user_config()
    for sym in user.get("remove") or []:
        by_symbol.pop(str(sym).strip().upper(), None)
    for item in user.get("add") or []:
        if isinstance(item, str):
            entry = _normalize_entry(item)
        elif isinstance(item, dict):
            entry = _normalize_entry(
                str(item.get("symbol") or ""),
                str(item.get("name") or ""),
                str(item.get("exchange") or ""),
            )
        else:
            continue
        if entry["symbol"]:
            by_symbol[entry["symbol"]] = entry
    return tuple(sorted(by_symbol.values(), key=lambda r: r["symbol"]))


def invalidate_ticker_catalog_cache() -> None:
    get_ticker_catalog.cache_clear()


def get_symbol_set() -> frozenset[str]:
    return frozenset(row["symbol"] for row in get_ticker_catalog())


def filter_ticker_catalog(prefix: str = "") -> list[dict[str, str]]:
    """All catalog symbols, optionally filtered by symbol prefix (for /tickers list)."""
    catalog = get_ticker_catalog()
    p = (prefix or "").strip().upper()
    if not p:
        return list(catalog)
    return [row for row in catalog if row["symbol"].startswith(p)]


def suggest_tickers(prefix: str, *, limit: int = 25) -> list[dict[str, str]]:
    """Prefix match for tab completion after $."""
    p = (prefix or "").strip().upper()
    catalog = get_ticker_catalog()
    if not p:
        popular = {s: None for s in POPULAR_SYMBOLS}
        hits = [row for row in catalog if row["symbol"] in popular]
        if len(hits) < limit:
            seen = {r["symbol"] for r in hits}
            for row in catalog:
                if row["symbol"] not in seen:
                    hits.append(row)
                if len(hits) >= limit:
                    break
        return hits[:limit]
    return [row for row in catalog if row["symbol"].startswith(p)][:limit]


def normalize_ticker_token(token: str) -> str | None:
    """Strip $ and commas; return uppercase symbol or None."""
    raw = (token or "").strip().upper().lstrip("$").rstrip(",")
    if not raw or raw.startswith("/"):
        return None
    if _TICKER_TOKEN_RE.fullmatch(raw):
        return raw
    return None


def normalize_ticker_tokens(text: str) -> list[str]:
    """Split whitespace/comma list and normalize each token (for slash command args)."""
    if not text or not str(text).strip():
        return []
    parts = re.split(r"[\s,]+", str(text).strip())
    out: list[str] = []
    for part in parts:
        sym = normalize_ticker_token(part)
        if sym and sym not in out:
            out.append(sym)
    return out


def extract_dollar_tickers(text: str) -> list[str]:
    """All $SYMBOL tokens in text, in order."""
    if not text:
        return []
    found: list[str] = []
    for match in DOLLAR_TICKER_RE.finditer(text):
        sym = match.group(1).upper()
        if sym not in found:
            found.append(sym)
    return found


def user_add_ticker(symbol: str, name: str = "", exchange: str = "") -> dict[str, str]:
    sym = normalize_ticker_token(symbol)
    if not sym:
        raise ValueError(f"Invalid ticker symbol: {symbol!r}")
    config = load_user_config(create=True)
    remove = {str(s).strip().upper() for s in config.get("remove") or []}
    remove.discard(sym)
    config["remove"] = sorted(remove)
    add_list: list[Any] = list(config.get("add") or [])
    entry = _normalize_entry(sym, name, exchange)
    add_list = [e for e in add_list if not (isinstance(e, dict) and str(e.get("symbol", "")).upper() == sym)]
    add_list.append(entry)
    config["add"] = add_list
    save_user_config(config)
    invalidate_ticker_catalog_cache()
    return entry


def user_remove_ticker(symbol: str, *, from_add_only: bool = False) -> bool:
    sym = normalize_ticker_token(symbol)
    if not sym:
        raise ValueError(f"Invalid ticker symbol: {symbol!r}")
    config = load_user_config(create=True)
    changed = False
    add_list = config.get("add") or []
    new_add = []
    for item in add_list:
        if isinstance(item, dict) and str(item.get("symbol", "")).upper() == sym:
            changed = True
            continue
        if isinstance(item, str) and item.upper() == sym:
            changed = True
            continue
        new_add.append(item)
    config["add"] = new_add
    if not from_add_only:
        remove = {str(s).strip().upper() for s in config.get("remove") or []}
        if sym not in remove:
            remove.add(sym)
            changed = True
        config["remove"] = sorted(remove)
    save_user_config(config)
    invalidate_ticker_catalog_cache()
    return changed


def catalog_stats() -> dict[str, int]:
    user = load_user_config()
    catalog = get_ticker_catalog()
    return {
        "total": len(catalog),
        "builtin": len(_load_builtin_catalog()),
        "user_add": len(user.get("add") or []),
        "user_remove": len(user.get("remove") or []),
    }
