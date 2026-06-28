"""Parallel subagents inside /research (Wave 4 rank 17)."""

from .parallel import run_subagents_parallel
from .runner import run_subagent
from .types import MAX_SUBAGENTS_PER_ROUND, SUBAGENT_TYPES, resolve_subagent_type

__all__ = [
    "MAX_SUBAGENTS_PER_ROUND",
    "SUBAGENT_TYPES",
    "resolve_subagent_type",
    "run_subagent",
    "run_subagents_parallel",
]
