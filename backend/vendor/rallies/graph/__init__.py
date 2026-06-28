"""
LangGraph foundation for rallies (Phase 0–5).

Optional flags: RALLIES_GRAPH_CHECKPOINTS, RALLIES_GRAPH_RESEARCH, RALLIES_GRAPH_MEMORY,
RALLIES_GRAPH_PLANNER.
Default rallies behavior is unchanged when flags are off.
"""

from .bridge import (
    entities_from_resolution,
    state_from_conversation,
    state_from_manager,
    state_from_turn,
)
from .checkpoint import (
    checkpoint_db_path,
    rallies_checkpoints_dir,
    state_debug_dir,
    thread_checkpoint_config,
)
from .checkpoint_runtime import (
    load_checkpoint_rallies_state,
    load_shadow_graph_values,
    save_turn_checkpoint,
)
from .context import build_llm_context, build_planner_messages, prefetch_compare_message
from .defaults import create_empty_state, default_thread_max_tokens
from .flags import (
    graph_checkpoints_enabled,
    graph_memory_enabled,
    graph_planner_enabled,
    graph_research_enabled,
    langgraph_available,
    planner_memory_digest_enabled,
    turn_pair_memory_enabled,
)
from .memory import (
    SESSION_MEMORY_MARKER,
    append_turn_pair,
    load_turn_pairs,
    memory_digest,
    memory_digest_from_slice,
    pairs_to_thread_messages,
)
from .reducers import (
    DEFAULT_TOOL_RESULT_CAP,
    append_messages,
    append_plan,
    append_tool_result,
    merge_market_snapshots,
    set_market_snapshot,
)
from .serializers import state_from_dict, state_from_json, state_to_dict, state_to_json
from .state import RalliesState

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "run_planned_prompt": (".planner", "run_planned_prompt"),
    "run_research_for_command": (".research.dispatch", "run_research_for_command"),
    "run_research_graph": (".research.runner", "run_research_graph"),
}


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        import importlib

        module_path, attr = _LAZY_EXPORTS[name]
        module = importlib.import_module(module_path, __name__)
        return getattr(module, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DEFAULT_TOOL_RESULT_CAP",
    "RalliesState",
    "append_messages",
    "append_plan",
    "append_tool_result",
    "build_llm_context",
    "build_planner_messages",
    "checkpoint_db_path",
    "create_empty_state",
    "default_thread_max_tokens",
    "entities_from_resolution",
    "SESSION_MEMORY_MARKER",
    "graph_checkpoints_enabled",
    "graph_memory_enabled",
    "graph_planner_enabled",
    "graph_research_enabled",
    "langgraph_available",
    "append_turn_pair",
    "load_turn_pairs",
    "pairs_to_thread_messages",
    "planner_memory_digest_enabled",
    "turn_pair_memory_enabled",
    "run_planned_prompt",
    "memory_digest",
    "memory_digest_from_slice",
    "run_research_for_command",
    "run_research_graph",
    "load_checkpoint_rallies_state",
    "load_shadow_graph_values",
    "merge_market_snapshots",
    "prefetch_compare_message",
    "rallies_checkpoints_dir",
    "save_turn_checkpoint",
    "set_market_snapshot",
    "state_debug_dir",
    "state_from_conversation",
    "state_from_dict",
    "state_from_json",
    "state_from_manager",
    "state_from_turn",
    "state_to_dict",
    "state_to_json",
    "thread_checkpoint_config",
]
