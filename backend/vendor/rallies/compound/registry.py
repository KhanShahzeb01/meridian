"""Command roles and matching order for compound prompts."""

from __future__ import annotations

from enum import Enum

# Longest-first matching (subset of cli.SLASH_COMMANDS + portfolio/watchlist variants).
COMMAND_NAMES: tuple[str, ...] = tuple(
    sorted(
        {
            "/watchlist add",
            "/watchlist remove",
            "/watchlist",
            "/portfolio add",
            "/portfolio remove",
            "/portfolio",
            "/research-log",
            "/financials",
            "/searchsec",
            "/hedgefund",
            "/consensus",
            "/earnings",
            "/holdings",
            "/insider",
            "/optimize",
            "/analysis",
            "/personas",
            "/research",
            "/debate",
            "/example",
            "/compact",
            "/compound_help",
            "/history",
            "/export",
            "/resume",
            "/options",
            "/sector",
            "/alerts",
            "/screen",
            "/bundle",
            "/filing",
            "/macro",
            "/chart",
            "/fetch",
            "/index",
            "/skill",
            "/rules",
            "/quote",
            "/clear",
            "/soul",
            "/memo",
            "/help",
            "/exit",
            "/quit",
            "/vix",
            "/sec",
            "/dcf",
            "/key",
            "/ask",
            "/news",
            "/peers",
            "/alert",
        },
        key=len,
        reverse=True,
    )
)


class CommandRole(str, Enum):
    PRIMARY = "primary"
    CONTEXT = "context"
    SYSTEM = "system"


PRIMARY_COMMANDS: frozenset[str] = frozenset(
    {
        "/ask",
        "/debate",
        "/consensus",
        "/research",
        "/memo",
        "/screen",
        "/dcf",
        "/optimize",
        "/options",
        "/analysis",
        "/chart",
        "/filing",
        "/bundle",
        "/fetch",
        "/skill",
    }
)

CONTEXT_COMMANDS: frozenset[str] = frozenset(
    {
        "/watchlist",
        "/portfolio",
        "/quote",
        "/financials",
        "/earnings",
        "/news",
        "/peers",
        "/insider",
        "/holdings",
        "/sec",
        "/sector",
        "/index",
        "/macro",
        "/vix",
        "/screen",
        "/bundle",
    }
)

SYSTEM_COMMANDS: frozenset[str] = frozenset(
    {
        "/help",
        "/exit",
        "/quit",
        "/clear",
        "/history",
        "/export",
        "/resume",
        "/key",
        "/compact",
        "/compound_help",
        "/example",
        "/personas",
        "/rules",
        "/soul",
        "/research-log",
        "/alerts",
        "/alert",
        "/watchlist add",
        "/watchlist remove",
        "/portfolio add",
        "/portfolio remove",
    }
)

CONTEXT_PRIORITY: dict[str, int] = {
    "/watchlist": 10,
    "/portfolio": 20,
    "/screen": 30,
    "/quote": 40,
    "/financials": 50,
    "/earnings": 55,
    "/news": 60,
    "/peers": 65,
    "/insider": 70,
    "/holdings": 75,
    "/sec": 80,
    "/sector": 85,
    "/index": 90,
    "/macro": 95,
    "/vix": 100,
    "/bundle": 110,
}


def sorted_command_names() -> list[str]:
    return sorted(set(COMMAND_NAMES), key=len, reverse=True)


def role_for_command(name: str) -> CommandRole:
    if name in SYSTEM_COMMANDS:
        return CommandRole.SYSTEM
    if name in CONTEXT_COMMANDS:
        return CommandRole.CONTEXT
    if name in PRIMARY_COMMANDS:
        return CommandRole.PRIMARY
    return CommandRole.CONTEXT
