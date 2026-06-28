"""Named portfolio identifiers and command parsing."""

from __future__ import annotations

import re

DEFAULT_PORTFOLIO = "default"

RESERVED_SUBCOMMANDS = frozenset(
    {
        "list",
        "add",
        "remove",
        "portfolios",
        "create",
        "delete",
        "rename",
        "help",
        "portfolio",
    }
)

_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def normalize_portfolio_name(name: str) -> str:
    """Lowercase, underscores; must match [a-z][a-z0-9_-]*."""
    raw = str(name).strip().lower().replace(" ", "_")
    if not raw or not _NAME_RE.match(raw):
        raise ValueError(
            "Portfolio name must start with a letter and use only letters, "
            "numbers, underscores, and hyphens (e.g. portfolio_2025)."
        )
    if raw in RESERVED_SUBCOMMANDS:
        raise ValueError(f"'{raw}' is reserved; choose another portfolio name.")
    return raw


def is_likely_portfolio_name(token: str) -> bool:
    if not token or token.lower() in RESERVED_SUBCOMMANDS:
        return False
    try:
        normalize_portfolio_name(token)
        return True
    except ValueError:
        return False


def extract_portfolio_name_after_command(
    text: str,
    command_end: int,
    known_names: set[str] | None = None,
) -> tuple[str, str | None]:
    """
    Portfolio name token immediately after `/portfolio` in a compound line.

    Returns (name, optional_note). Unknown names fall back to default.
    """
    from .list_context import resolve_named_list_after_command

    rest = text[command_end:].lstrip()
    if not rest:
        return DEFAULT_PORTFOLIO, None
    token = rest.split()[0]
    if token.lower() in RESERVED_SUBCOMMANDS:
        return DEFAULT_PORTFOLIO, None
    return resolve_named_list_after_command(
        token,
        default=DEFAULT_PORTFOLIO,
        known_names=known_names,
        normalize=normalize_portfolio_name,
        is_likely=is_likely_portfolio_name,
        prefix_hint="portfolio_",
    )


def extract_portfolio_name_from_text(text: str) -> str:
    """First named portfolio after any `/portfolio` (optimize, single-command hints)."""
    for match in re.finditer(r"/portfolio\b", text, re.IGNORECASE):
        name, _ = extract_portfolio_name_after_command(text, match.end())
        if name != DEFAULT_PORTFOLIO:
            return name
    return DEFAULT_PORTFOLIO


def parse_portfolio_prompt(prompt: str) -> tuple[str, str, str]:
    """
    Parse `/portfolio [NAME] [list|add|remove|...] [args]`.

    Returns (portfolio_name, subcommand, remainder_args).
    """
    parts = prompt.strip().split()
    if not parts or parts[0].lower() != "/portfolio":
        return DEFAULT_PORTFOLIO, "list", ""

    rest = parts[1:]
    if not rest:
        return DEFAULT_PORTFOLIO, "list", ""

    first = rest[0]
    first_low = first.lower()

    if first_low in RESERVED_SUBCOMMANDS:
        sub = first_low
        args = " ".join(rest[1:]) if len(rest) > 1 else ""
        return DEFAULT_PORTFOLIO, sub, args

    if len(rest) >= 2 and rest[1].lower() in ("add", "remove"):
        name = normalize_portfolio_name(first)
        sub = rest[1].lower()
        args = " ".join(rest[2:]) if len(rest) > 2 else ""
        return name, sub, args

    if is_likely_portfolio_name(first):
        return normalize_portfolio_name(first), "list", ""

    return DEFAULT_PORTFOLIO, first_low, " ".join(rest[1:])
