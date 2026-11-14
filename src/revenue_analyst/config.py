"""Project settings, loaded from environment variables / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RA_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")

    state_dir: Path = Path(".state")
    """Local runtime state (e.g. the SQLite conversation checkpoints)."""

    frontend_dist: Path = Path("frontend/dist")
    """Built web UI; when the folder exists, the API serves it at /ui."""

    model: str = "openrouter:openai/gpt-4o-mini"
    """Resolved by llm.init_model: "openrouter:<vendor>/<model>",
    "anthropic:<model>", "ollama:<model>"... — the vendor is configuration,
    not code."""
