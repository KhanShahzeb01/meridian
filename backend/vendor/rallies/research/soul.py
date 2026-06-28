"""Load optional tone overlay from .rallies/SOUL.md (Wave 2 rank 12)."""

from __future__ import annotations

from .paths import ensure_data_dir, soul_path


def load_soul() -> str | None:
    path = soul_path()
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def soul_system_prefix() -> str:
    soul = load_soul()
    if not soul:
        return ""
    return f"## Tone and voice (SOUL)\n\n{soul}\n\n"


def ensure_default_soul_template() -> None:
    ensure_data_dir()
    path = soul_path()
    if path.exists():
        return
    path.write_text(
        "# Rallies SOUL (optional)\n\n"
        "# Describe how answers should sound — tone, brevity, skepticism, humor, etc.\n"
        "# Examples:\n"
        "# - Be direct and skeptical of hype; cite numbers.\n"
        "# - Write like a buy-side analyst memo, not marketing copy.\n",
        encoding="utf-8",
    )
