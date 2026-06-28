"""Run free-text planner flow via LangGraph."""

from __future__ import annotations

from typing import Any

from ..bridge import state_from_manager
from ..defaults import empty_memory_state
from ..flags import graph_checkpoints_enabled, planner_memory_digest_enabled
from ..serializers import state_to_dict
from .config import build_planner_invoke_config
from .context import PlannerGraphContext
from .graph_build import get_planner_graph
from .messages import prepend_memory_digest_to_workspace
from .state import PlannerGraphState


def _session_id_from_manager(manager: Any) -> str | None:
    history = getattr(manager, "history_session", None)
    if not isinstance(history, dict):
        return None
    session_id = str(history.get("id") or "").strip()
    return session_id or None


def build_initial_planner_state(manager: Any) -> PlannerGraphState:
    return PlannerGraphState(
        round=0,
        max_rounds=int(manager.max_planner_rounds),
        max_steps_per_round=int(manager.max_steps_per_round),
        plan=[],
        status="plan",
        answer=None,
        last_node="start",
    )


def build_planner_context(
    manager: Any,
    prompt: str,
    workspace: list,
    thread: list,
) -> PlannerGraphContext:
    rallies_state = state_to_dict(state_from_manager(manager, prompt, thread, route="planner"))
    memory = rallies_state.get("memory")
    if not isinstance(memory, dict):
        rallies_state["memory"] = empty_memory_state()
    memory_enabled = planner_memory_digest_enabled()
    if memory_enabled:
        workspace[:] = prepend_memory_digest_to_workspace(workspace, rallies_state)
    return PlannerGraphContext(
        manager=manager,
        prompt=prompt,
        workspace=workspace,
        thread=thread,
        rallies_state=rallies_state,
        max_rounds=int(manager.max_planner_rounds),
        max_steps_per_round=int(manager.max_steps_per_round),
        memory_enabled=memory_enabled,
    )


def extract_answer_from_final_state(final: PlannerGraphState) -> str:
    answer = final.get("answer")
    return str(answer) if answer is not None else ""


def _show_planning_spinner() -> None:
    from rich.live import Live
    from rich.spinner import Spinner

    from rallies import console

    console.print()
    spinner = Spinner("dots", text="[bright_magenta]Planning (graph)...[/bright_magenta]")
    with Live(spinner, console=console, refresh_per_second=10):
        pass


def run_planner_graph(
    manager: Any,
    prompt: str,
    workspace: list,
    thread: list,
) -> str:
    """Execute planner orchestration through LangGraph nodes."""
    _show_planning_spinner()
    graph = get_planner_graph(use_checkpoint=graph_checkpoints_enabled())
    ctx = build_planner_context(manager, prompt, workspace, thread)
    initial = build_initial_planner_state(manager)
    config = build_planner_invoke_config(
        session_id=_session_id_from_manager(manager),
        ctx=ctx,
        use_checkpoint=graph_checkpoints_enabled(),
    )
    final = graph.invoke(initial, config)
    return extract_answer_from_final_state(final)
