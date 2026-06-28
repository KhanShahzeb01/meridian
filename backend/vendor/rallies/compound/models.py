"""Data structures for compound (multi-command) prompts."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedCommand:
    """One slash command occurrence in a user line."""

    name: str
    start: int
    end: int

    @property
    def is_primary_anchor(self) -> bool:
        return self.start == 0


@dataclass
class CompoundContext:
    """Resolved context passed to primary command handlers."""

    sources: list[str] = field(default_factory=list)
    tickers: list[str] = field(default_factory=list)
    tickers_by_source: dict[str, list[str]] = field(default_factory=dict)
    live_data_block: str = ""
    notes: list[str] = field(default_factory=list)

    def format_context_briefing(self) -> str:
        """Structured briefing from all resolved context steps (by source)."""
        if not self.sources and not self.live_data_block.strip() and not self.notes:
            return ""

        parts: list[str] = [
            "Compound command — resolved context "
            f"(execution order: {', '.join(self.sources) or 'none'}). "
            "Use each labeled section only for its role in the user request; "
            "do not treat tickers from one source as if they came from another."
        ]

        ticker_lines: list[str] = []
        for src in self.sources:
            tks = self.tickers_by_source.get(src, [])
            if tks:
                ticker_lines.append(f"- {src}: {', '.join(tks)}")
        if ticker_lines:
            parts.append("Tickers by source:\n" + "\n".join(ticker_lines))

        if self.live_data_block.strip():
            parts.append(self.live_data_block.strip())
        if self.notes:
            parts.append("Resolver notes: " + "; ".join(self.notes))
        return "\n\n".join(parts)

    def augment_query(self, query: str) -> str:
        """Prepend resolved data for research-style primaries."""
        briefing = self.format_context_briefing()
        if not briefing:
            return query
        return f"{briefing}\n\n---\n\nUser request: {query}"


@dataclass(frozen=True)
class ExecutionPlan:
    """Ordered steps: context resolvers first, then primary handler."""

    raw_prompt: str
    primary: ParsedCommand
    context_steps: tuple[ParsedCommand, ...]
    cleaned_primary_prompt: str
    user_intent: str

    def effective_primary_prompt(self, ctx: CompoundContext) -> str:
        """Primary line plus resolved multi-source briefing for the handler."""
        briefing = ctx.format_context_briefing()
        if not briefing:
            return self.cleaned_primary_prompt
        return f"{self.cleaned_primary_prompt}\n\n---\n\n{briefing}"
