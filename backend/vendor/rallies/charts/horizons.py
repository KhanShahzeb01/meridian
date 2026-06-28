"""Time horizons for valuation charts (YTD, 1y–10y, max)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

DEFAULT_HORIZONS = ("ytd", "1y", "5y", "10y", "max")

HORIZON_ALIASES = {
    "ytd": "ytd",
    "1y": "1y",
    "1yr": "1y",
    "5y": "5y",
    "5yr": "5y",
    "10y": "10y",
    "10yr": "10y",
    "max": "max",
    "all": "max",
    "alltime": "max",
}


@dataclass(frozen=True)
class Horizon:
    key: str
    label: str
    start: pd.Timestamp | None  # None = max available


def normalize_horizon(token: str) -> str | None:
    return HORIZON_ALIASES.get(token.lower().strip())


def parse_horizons(tokens: list[str]) -> list[Horizon]:
    keys: list[str] = []
    for t in tokens:
        h = normalize_horizon(t)
        if h and h not in keys:
            keys.append(h)
    if not keys:
        keys = list(DEFAULT_HORIZONS)
    return [horizon_for_key(k) for k in keys]


def horizon_for_key(key: str) -> Horizon:
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    labels = {
        "ytd": "Year to date",
        "1y": "1 year",
        "5y": "5 years",
        "10y": "10 years",
        "max": "All available history",
    }
    if key == "ytd":
        start = pd.Timestamp(datetime(now.year, 1, 1))
        return Horizon(key, labels[key], start)
    if key == "1y":
        return Horizon(key, labels[key], now - pd.DateOffset(years=1))
    if key == "5y":
        return Horizon(key, labels[key], now - pd.DateOffset(years=5))
    if key == "10y":
        return Horizon(key, labels[key], now - pd.DateOffset(years=10))
    return Horizon(key, labels[key], None)
