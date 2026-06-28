"""Central token budget policy for model context, output, and thread memory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# openai/gpt-oss-120b on OpenRouter — 131,072 token context window.
DEFAULT_MODEL_CONTEXT_TOKENS = 131_072

# Never consume the full window; leave headroom for provider counting quirks.
DEFAULT_SAFETY_MARGIN_RATIO = 0.10

# System + developer prompts on planner/answer calls.
DEFAULT_OVERHEAD_TOKENS = 12_000

# Per-turn workspace: plan steps, summaries, prefetched blocks (not stored in thread).
DEFAULT_WORKSPACE_RESERVE_TOKENS = 28_000

# Output budgets — consensus summaries are the largest routine responses.
DEFAULT_OUTPUT_BUDGETS: dict[str, int] = {
    "planner": 2_500,
    "action": 2_500,
    "summary": 1_200,
    "compact": 3_000,
    "answer": 8_000,
    "analysis": 8_000,
    "debate": 8_000,
    "consensus": 12_000,
    "consensus_summary": 14_000,
    "research": 6_000,
    "memo": 10_000,
}


@dataclass(frozen=True)
class TokenBudgetPolicy:
    """How rallies splits the model context window across input and output."""

    model_context_tokens: int
    safety_margin_ratio: float
    overhead_tokens: int
    workspace_reserve_tokens: int
    max_output_tokens: int
    max_thread_tokens: int
    output_budgets: dict[str, int]

    @property
    def usable_context_tokens(self) -> int:
        margin = max(0.0, min(0.5, self.safety_margin_ratio))
        return int(self.model_context_tokens * (1.0 - margin))

    @property
    def max_input_tokens(self) -> int:
        """Upper bound for a single request's input side (thread + workspace + overhead)."""
        return max(
            4_000,
            self.usable_context_tokens - self.max_output_tokens,
        )

    def output_budget_for(self, task_type: str | None) -> int:
        if task_type and task_type in self.output_budgets:
            return int(self.output_budgets[task_type])
        return int(self.output_budgets.get("answer", 8_000))

    def thread_utilization(self, thread_tokens: int) -> float:
        if self.max_thread_tokens <= 0:
            return 0.0
        return min(1.0, thread_tokens / self.max_thread_tokens)

    @classmethod
    def from_provider_config(cls, config: dict[str, Any] | None) -> TokenBudgetPolicy:
        config = config or {}
        memory = config.get("memory") or {}
        token_budgets = dict(DEFAULT_OUTPUT_BUDGETS)
        token_budgets.update(config.get("token_budgets") or {})

        model_context = int(
            memory.get("model_context_tokens", DEFAULT_MODEL_CONTEXT_TOKENS)
        )
        safety_ratio = float(
            memory.get("safety_margin_ratio", DEFAULT_SAFETY_MARGIN_RATIO)
        )
        overhead = int(memory.get("overhead_tokens", DEFAULT_OVERHEAD_TOKENS))
        workspace = int(
            memory.get("workspace_reserve_tokens", DEFAULT_WORKSPACE_RESERVE_TOKENS)
        )

        max_output = max(int(v) for v in token_budgets.values())

        usable = int(model_context * (1.0 - max(0.0, min(0.5, safety_ratio))))
        computed_thread = usable - max_output - overhead - workspace
        configured_thread = memory.get("max_thread_tokens")
        if configured_thread is not None:
            max_thread = min(int(configured_thread), computed_thread)
        else:
            max_thread = computed_thread

        max_thread = max(8_000, max_thread)

        return cls(
            model_context_tokens=model_context,
            safety_margin_ratio=safety_ratio,
            overhead_tokens=overhead,
            workspace_reserve_tokens=workspace,
            max_output_tokens=max_output,
            max_thread_tokens=max_thread,
            output_budgets=token_budgets,
        )


def default_thread_token_budget() -> int:
    """Thread cap when no provider config is loaded."""
    return TokenBudgetPolicy.from_provider_config({}).max_thread_tokens
