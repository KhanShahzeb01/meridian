"""Non-invasive hooks from Manager into graph checkpointing."""

from __future__ import annotations

from typing import Any


def maybe_save_turn_checkpoint(
    manager: Any,
    prompt: str,
    conversation: list[dict],
    *,
    answer: str = "",
    simple_ticker: bool = False,
) -> None:
    """
    Persist shadow-graph checkpoint when enabled.

    Never raises — failures are logged dimly and ignored.
    """
    from .flags import graph_checkpoints_enabled, langgraph_available

    if not graph_checkpoints_enabled():
        return
    if not langgraph_available():
        _print_checkpoint_skip(manager, "langgraph not installed (pip install -e '.[agent]')")
        return

    try:
        from .checkpoint_runtime import save_turn_checkpoint

        save_turn_checkpoint(
            manager,
            prompt,
            conversation,
            answer=answer,
            simple_ticker=simple_ticker,
        )
    except Exception as exc:
        _print_checkpoint_skip(manager, f"checkpoint skipped: {exc}")


def _print_checkpoint_skip(manager: Any, message: str) -> None:
    console = getattr(manager, "_graph_console", None)
    if console is None:
        try:
            from .. import console as rallies_console

            console = rallies_console
        except Exception:
            return
    console.print(f"[dim]Graph checkpoint: {message}[/dim]")
