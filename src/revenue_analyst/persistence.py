"""Conversation persistence: LangGraph checkpointers used by the CLI and API."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


def sqlite_checkpointer(state_dir: Path) -> SqliteSaver:
    """A file-backed checkpointer: conversations survive process restarts."""
    state_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(state_dir / "checkpoints.sqlite", check_same_thread=False)
    return SqliteSaver(conn)
