"""Central fast router — skip slow rallies pipeline when a fast path exists."""

from __future__ import annotations

from typing import Any, Callable, Optional

from rallies.advanced.personas import list_personas_by_category
from rallies.helpers import handle_command, show_help

from services.command_format import format_command_markdown
from services.fast_ask import run_fast_ask

# Commands that need full rallies (multi-LLM, heavy yfinance, SEC, etc.)
HEAVY_PREFIXES = (
    "/consensus",
    "/research",
    "/screen",
    "/debate",
    "/bundle",
    "/dcf",
    "/options",
    "/chart",
    "/analysis",
    "/optimize",
    "/filing",
    "/sec ",
    "/sec\t",
    "/insider",
    "/holdings",
    "/sector ",
    "/index ",
    "/searchsec",
    "/hedgefund",
    "/fetch ",
    "/skill",
    "/rules",
    "/soul",
    "/example",
    "/history",
    "/export",
    "/resume",
    "/compact",
    "/key",
    "/tickers",
    "/watch",
    "/portfolio",
    "/alert",
    "/alerts",
    "/earnings ",  # per-ticker still uses yfinance in rallies
)

INSTANT_COMMANDS = frozenset({"/clear", "/help", "/personas"})


def is_heavy_command(routed: str) -> bool:
    rl = routed.strip().lower()
    parts = rl.split()
    if parts and parts[0] == "/memo" and any(x in parts for x in ("--full", "-f")):
        return True
    if rl == "/sec":
        return True
    return any(rl.startswith(p) for p in HEAVY_PREFIXES)


def is_data_fast_command(routed: str) -> bool:
    """Pure data fetch — one API call, no LLM."""
    rl = routed.strip().lower()
    if rl in ("/vix", "/macro", "/earnings"):
        return True
    for prefix in ("/quote ", "/news ", "/financials ", "/peers ", "/vix "):
        if rl.startswith(prefix):
            return True
    return False


def is_instant_command(routed: str) -> bool:
    rl = routed.strip().lower()
    return rl in INSTANT_COMMANDS or rl.startswith("/personas ")


def is_fast_ask(routed: str) -> bool:
    parts = routed.strip().split(maxsplit=2)
    return len(parts) >= 3 and parts[0].lower() == "/ask"


def try_instant(
    routed: str,
    conversation: list,
    console: Any,
    *,
    personas_formatter: Callable[[], str],
) -> Optional[str]:
    rl = routed.strip().lower()
    if rl == "/clear":
        conversation.clear()
        return "Conversation cleared."
    if rl == "/personas" or rl.startswith("/personas "):
        return personas_formatter()
    if rl == "/help":
        show_help(console)
        return console.get_output() or "Type `/help` for commands."
    return None


def format_personas_markdown() -> str:
    grouped = list_personas_by_category()
    lines = ["## Personas", ""]
    for category, personas in grouped.items():
        lines.append(f"### {category}")
        lines.append("")
        for p in personas:
            name = p.get("name", p.get("key", ""))
            key = p.get("key", "")
            quote = p.get("quote", "")
            lines.append(f"- **{name}** (`{key}`) — _{quote}_")
        lines.append("")
    lines.append("Use `/ask PERSONA your question` to chat with a persona.")
    return "\n".join(lines)


def try_data_fast(
    routed: str,
    manager: Any,
    cmd_type: str,
) -> Optional[str]:
    if not is_data_fast_command(routed):
        return None
    return format_command_markdown(cmd_type, routed, manager)


def try_fast_ask_path(
    routed: str,
    conversation: list,
    manager: Any,
) -> Optional[str]:
    if not is_fast_ask(routed):
        return None
    return run_fast_ask(routed, conversation, manager)


def run_slow_command(
    routed: str,
    conversation: list,
    manager: Any,
    console: Any,
) -> bool:
    """Full rallies handler — only for heavy / stateful commands."""
    return bool(
        handle_command(routed, conversation, manager.agent, console, manager=manager)
    )
