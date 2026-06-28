"""Mutable runtime context for planner graph invocation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlannerGraphContext:
    manager: Any
    prompt: str
    workspace: list[dict[str, Any]]
    thread: list[dict[str, Any]]
    rallies_state: dict[str, Any]
    max_rounds: int
    max_steps_per_round: int
    memory_enabled: bool = False
    step_results: dict[str, str] = field(default_factory=dict)

    def manager_agent(self) -> Any:
        return self.manager.agent

    def history_session(self) -> dict[str, Any]:
        return self.manager.history_session

    def memory_dict(self) -> dict[str, Any]:
        memory = self.rallies_state.get("memory")
        if not isinstance(memory, dict):
            memory = {}
            self.rallies_state["memory"] = memory
        return memory
