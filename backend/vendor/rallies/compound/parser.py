"""Find slash commands embedded in a single user line."""

from __future__ import annotations

from .models import ParsedCommand
from .registry import sorted_command_names


def _boundary_ok(text: str, end: int) -> bool:
    """Command token must end at string boundary or before whitespace."""
    return end >= len(text) or text[end] in " \t\n\r"


def find_commands(text: str) -> list[ParsedCommand]:
    """Return all known slash commands in *text*, longest match at each position."""
    stripped = text.lstrip()
    offset = len(text) - len(stripped)
    names = sorted_command_names()
    found: list[ParsedCommand] = []
    seen_spans: set[tuple[int, int]] = set()

    for i in range(len(stripped)):
        if stripped[i] != "/":
            continue
        for name in names:
            end_local = i + len(name)
            if not stripped.startswith(name, i):
                continue
            if not _boundary_ok(stripped, end_local):
                continue
            start = offset + i
            end = offset + end_local
            span = (start, end)
            if span in seen_spans:
                break
            seen_spans.add(span)
            found.append(ParsedCommand(name=name, start=start, end=end))
            break

    found.sort(key=lambda c: c.start)
    return found


def is_compound_prompt(text: str) -> bool:
    """True when line starts with a slash command and has another command later."""
    commands = find_commands(text)
    if len(commands) < 2:
        return False
    if commands[0].start != len(text) - len(text.lstrip()):
        return False
    return True
