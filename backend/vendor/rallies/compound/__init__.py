"""Compound slash commands: multiple quick commands in one line, ordered execution."""

from .executor import try_handle_compound_command
from .help import show_compound_help
from .parser import find_commands, is_compound_prompt

__all__ = [
    "try_handle_compound_command",
    "show_compound_help",
    "find_commands",
    "is_compound_prompt",
]
