"""Runtime context for research graph nodes (not checkpointed)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ResearchGraphContext:
    """Holds non-serializable research runtime objects."""

    loop: Any
    memory: dict[str, Any] | None = None
    entities: dict[str, Any] | None = None
    input_state: dict[str, str] | None = None

    @classmethod
    def from_loop(cls, loop: Any) -> ResearchGraphContext:
        return cls(loop=loop)

    def memory_dict(self) -> dict[str, Any]:
        return dict(self.memory or {})

    def entities_dict(self) -> dict[str, Any]:
        return dict(self.entities or {})
