"""Named watchlist identifiers and command parsing."""

from __future__ import annotations

import re

DEFAULT_WATCHLIST = "default"

RESERVED_SUBCOMMANDS = frozenset(
    {
        "list",
        "add",
        "remove",
        "watchlists",
        "create",
        "delete",
        "rename",
        "help",
        "watchlist",
        "watch",
    }
)

_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def normalize_watchlist_name(name: str) -> str:
    """Lowercase, underscores; must match [a-z][a-z0-9_-]*."""
    raw = str(name).strip().lower().replace(" ", "_")
    if not raw or not _NAME_RE.match(raw):
        raise ValueError(
            "Watchlist name must start with a letter and use only letters, "
            "numbers, underscores, and hyphens (e.g. watchlist_khan)."
        )
    if raw in RESERVED_SUBCOMMANDS:
        raise ValueError(f"'{raw}' is reserved; choose another watchlist name.")
    return raw


def is_likely_watchlist_name(token: str) -> bool:
    if not token or token.lower() in RESERVED_SUBCOMMANDS:
        return False
    try:
        normalize_watchlist_name(token)
        return True
    except ValueError:
        return False


def extract_watchlist_name_after_command(
    text: str,
    command_end: int,
    known_names: set[str] | None = None,
) -> tuple[str, str | None]:
    """
    Watchlist name immediately after `/watchlist` in a compound line.

    Returns (name, optional_note). Unknown names fall back to default.
    """
    from .list_context import resolve_named_list_after_command

    rest = text[command_end:].lstrip()
    if not rest:
        return DEFAULT_WATCHLIST, None
    token = rest.split()[0]
    if token.lower() in RESERVED_SUBCOMMANDS:
        return DEFAULT_WATCHLIST, None
    return resolve_named_list_after_command(
        token,
        default=DEFAULT_WATCHLIST,
        known_names=known_names,
        normalize=normalize_watchlist_name,
        is_likely=is_likely_watchlist_name,
        prefix_hint="watchlist_",
    )


def extract_watchlist_name_from_text(text: str) -> str:
    """First named watchlist after any `/watchlist` (optimize, single-command hints)."""
    for match in re.finditer(r"/watchlist\b", text, re.IGNORECASE):
        name, _ = extract_watchlist_name_after_command(text, match.end())
        if name != DEFAULT_WATCHLIST:
            return name
    return DEFAULT_WATCHLIST


def parse_watchlist_prompt(prompt: str) -> tuple[str, str, str]:
    """
    Parse `/watchlist [NAME] [add|remove|list|...] [args]`.

    Shorthand: `/watchlist watchlist_khan MU` → add MU to watchlist_khan.

    Returns (watchlist_name, subcommand, remainder_args).
    """
    parts = prompt.strip().split()
    if not parts or parts[0].lower() not in ("/watchlist", "/watch"):
        return DEFAULT_WATCHLIST, "list", ""

    rest = parts[1:]
    if not rest:
        return DEFAULT_WATCHLIST, "list", ""

    first = rest[0]
    first_low = first.lower()

    if first_low in RESERVED_SUBCOMMANDS:
        sub = first_low
        args = " ".join(rest[1:]) if len(rest) > 1 else ""
        return DEFAULT_WATCHLIST, sub, args

    if is_likely_watchlist_name(first):
        name = normalize_watchlist_name(first)
        if len(rest) >= 2:
            second_low = rest[1].lower()
            if second_low in ("add", "remove"):
                args = " ".join(rest[2:]) if len(rest) > 2 else ""
                return name, second_low, args
            # Shorthand: /watchlist watchlist_khan MU AAPL
            return name, "add", " ".join(rest[1:])
        return name, "list", ""

    return DEFAULT_WATCHLIST, first_low if first_low in ("add", "remove") else "list", " ".join(rest[1:])
