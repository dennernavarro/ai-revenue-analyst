"""Project settings, loaded from environment variables / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RA_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")

    model: str = "openrouter:anthropic/claude-haiku-4.5"
    """Resolved by llm.init_model: "openrouter:<vendor>/<model>",
    "anthropic:<model>", "ollama:<model>"... — the vendor is configuration,
    not code."""
