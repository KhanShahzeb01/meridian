"""Full LLM compaction for long /research sessions (Wave 4 rank 13)."""

from .constants import (
    FULL_COMPACT_TOKEN_THRESHOLD,
    FULL_COMPACT_TOOL_COUNT_THRESHOLD,
    MAX_CONSECUTIVE_COMPACTION_FAILURES,
    MIN_TOOL_RESULTS_FOR_COMPACTION,
)
from .messages import (
    apply_compaction_to_messages,
    collect_tool_results_text,
    count_active_tool_messages,
    estimate_messages_tokens,
    should_run_full_compaction,
)
from .run import CompactionResult, compact_tool_results

__all__ = [
    "FULL_COMPACT_TOKEN_THRESHOLD",
    "FULL_COMPACT_TOOL_COUNT_THRESHOLD",
    "MAX_CONSECUTIVE_COMPACTION_FAILURES",
    "MIN_TOOL_RESULTS_FOR_COMPACTION",
    "CompactionResult",
    "apply_compaction_to_messages",
    "collect_tool_results_text",
    "count_active_tool_messages",
    "compact_tool_results",
    "estimate_messages_tokens",
    "should_run_full_compaction",
]
