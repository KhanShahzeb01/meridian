"""Shared types for context resolvers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResolverResult:
    source: str
    tickers: list[str] = field(default_factory=list)
    live_data_block: str = ""
    notes: list[str] = field(default_factory=list)
