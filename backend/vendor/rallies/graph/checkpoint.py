"""Checkpoint path helpers for LangGraph SqliteSaver integration."""

from __future__ import annotations

import os
from pathlib import Path

from ..research.paths import rallies_data_dir


def rallies_checkpoints_dir() -> Path:
    """Directory for LangGraph checkpoint databases."""
    path = rallies_data_dir() / "checkpoints"
    path.mkdir(parents=True, exist_ok=True)
    return path


def checkpoint_db_path(*, filename: str = "rallies.db") -> Path:
    """Default SQLite checkpoint file path."""
    override = os.getenv("RALLIES_CHECKPOINT_DB", "").strip()
    if override:
        return Path(override).expanduser()
    return rallies_checkpoints_dir() / filename


def thread_checkpoint_config(session_id: str) -> dict[str, dict[str, str]]:
    """LangGraph configurable thread_id for a rallies history session."""
    return {"configurable": {"thread_id": session_id}}


def state_debug_dir() -> Path:
    """Optional shadow-state dumps (Phase 1+)."""
    path = rallies_data_dir() / "state-debug"
    path.mkdir(parents=True, exist_ok=True)
    return path
