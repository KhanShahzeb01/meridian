"""Rich tool progress for research mode (Wave 3 rank 14)."""

from __future__ import annotations

from typing import Callable


class ResearchProgress:
    """Emit user-visible status while the research loop runs tools."""

    def __init__(self, console=None, callback: Callable[[str], None] | None = None) -> None:
        self._console = console
        self._callback = callback

    def _emit(self, message: str) -> None:
        if self._callback:
            self._callback(message)
        elif self._console is not None:
            self._console.print(f"[bright_black]{message}[/bright_black]")

    def iteration(self, n: int, max_iterations: int) -> None:
        self._emit(f"Research round {n}/{max_iterations}…")

    def thinking(self, text: str) -> None:
        preview = (text or "").strip().replace("\n", " ")[:120]
        if preview:
            self._emit(f"Thinking: {preview}")

    def tool_start(self, name: str, args: dict | None = None) -> None:
        detail = ""
        if args:
            ticker = args.get("ticker")
            intent = args.get("intent") or args.get("section") or args.get("url")
            if ticker and intent:
                detail = f" ({ticker}: {intent})"
            elif ticker:
                detail = f" ({ticker})"
            elif intent:
                detail = f" ({intent})"
        self._emit(f"⏺ Tool {name}{detail}…")

    def tool_done(self, name: str, chars: int) -> None:
        self._emit(f"✓ {name} ({chars:,} chars)")

    def microcompact(self, cleared: int, tokens_saved: int) -> None:
        if cleared:
            self._emit(
                f"Microcompact: cleared {cleared} old tool result(s) "
                f"(~{max(1, tokens_saved // 1000)}K tokens)"
            )

    def compaction(self, pre_tokens: int, post_tokens: int, *, success: bool) -> None:
        if success:
            self._emit(
                f"Full compaction: ~{pre_tokens // 1000}K → ~{post_tokens // 1000}K tokens"
            )
        else:
            self._emit("Full compaction failed — continuing with microcompact only")

    def subagent_start(self, description: str) -> None:
        self._emit(f"Subagent: {description}…")

    def subagent_done(self, description: str) -> None:
        self._emit(f"✓ Subagent {description}")

    def subagent_round(self, agent_type: str, n: int, max_n: int) -> None:
        self._emit(f"Subagent ({agent_type}) round {n}/{max_n}")

    def done(self, tool_count: int, iterations: int) -> None:
        self._emit(f"Research complete — {tool_count} tool call(s) in {iterations} round(s)")
