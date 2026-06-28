"""SqliteSaver factory and cached checkpointer access."""

from __future__ import annotations

import sqlite3
from typing import Any

from .checkpoint import checkpoint_db_path
from .flags import langgraph_available

_checkpointer: Any | None = None
_connection: sqlite3.Connection | None = None


def _require_langgraph_sqlite():
    from langgraph.checkpoint.sqlite import SqliteSaver

    return SqliteSaver


def get_sqlite_connection() -> sqlite3.Connection:
    """Shared SQLite connection for checkpoint reads/writes."""
    global _connection
    if _connection is None:
        db_path = checkpoint_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(str(db_path), check_same_thread=False)
    return _connection


def get_checkpointer():
    """Lazy SqliteSaver singleton."""
    global _checkpointer
    if not langgraph_available():
        raise ImportError(
            "langgraph is not installed. Install with: pip install -e '.[agent]'"
        )
    if _checkpointer is None:
        SqliteSaver = _require_langgraph_sqlite()
        _checkpointer = SqliteSaver(get_sqlite_connection())
    return _checkpointer


def reset_checkpointer_cache() -> None:
    """Test helper — close and clear cached connection/checkpointer."""
    global _checkpointer, _connection
    if _connection is not None:
        _connection.close()
    _checkpointer = None
    _connection = None
