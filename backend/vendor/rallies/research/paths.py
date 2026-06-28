"""Paths for rallies research / observability artifacts (.rallies/)."""

from __future__ import annotations

import os
from pathlib import Path


def rallies_data_dir() -> Path:
    """
    Canonical rallies data root (memory, history, checkpoints, scratchpad).

    Always ~/.rallies unless RALLIES_DATA_DIR is set. Using a single path avoids
    session memory landing in ./.rallies when cwd is the project repo and in
    ~/.rallies when cwd is $HOME.
    """
    override = os.getenv("RALLIES_DATA_DIR", "").strip()
    if override:
        path = Path(override).expanduser()
    else:
        path = Path.home() / ".rallies"
    path.mkdir(parents=True, exist_ok=True)
    return path


def session_memory_dir() -> Path:
    """One JSON file per CLI session: human/ai message pairs for LLM context."""
    path = rallies_data_dir() / "memory"
    path.mkdir(parents=True, exist_ok=True)
    return path


def scratchpad_dir() -> Path:
    path = rallies_data_dir() / "scratchpad"
    path.mkdir(parents=True, exist_ok=True)
    return path


def rules_path() -> Path:
    return rallies_data_dir() / "RULES.md"


def soul_path() -> Path:
    return rallies_data_dir() / "SOUL.md"


def tool_results_dir() -> Path:
    path = rallies_data_dir() / "tool-results"
    path.mkdir(parents=True, exist_ok=True)
    return path


def memos_dir() -> Path:
    path = rallies_data_dir() / "memos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def web_fetch_cache_dir() -> Path:
    path = rallies_data_dir() / "web-fetch-cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def project_skills_dir() -> Path:
    path = rallies_data_dir() / "skills"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_data_dir() -> Path:
    path = rallies_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path
