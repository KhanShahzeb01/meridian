"""Load user research rules from .rallies/RULES.md (additive prompt overlay)."""

from __future__ import annotations

from .paths import ensure_data_dir, rules_path


def load_rules() -> str | None:
    path = rules_path()
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None
    return text


def rules_system_prefix() -> str:
    rules = load_rules()
    if not rules:
        return ""
    return f"## User research rules\n\n{rules}\n\n"


def ensure_default_rules_template() -> None:
    """Create a starter RULES.md if missing (non-destructive)."""
    ensure_data_dir()
    path = rules_path()
    if path.exists():
        return
    path.write_text(
        "# Rallies research rules\n\n"
        "# Add preferences for how the agent should research (one per line or short paragraphs).\n"
        "# Examples:\n"
        "# - Always cite data dates when quoting prices.\n"
        "# - Prefer conservative assumptions in valuation questions.\n"
        "# - Portfolio dollars are literal unless suffixed (k/mn/bn); "
        "position value = shares × price.\n",
        encoding="utf-8",
    )
