"""Runtime configuration for the mapping assistant."""

from __future__ import annotations

from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_RETRIEVAL_CONFIDENCE_THRESHOLD = 0.35
# A local SQLite file by default -- zero-config for local dev; the real
# docker-compose Postgres service is opt-in via DATABASE_URL (refs 14.1).
DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./data/review_queue.db"


class Settings(BaseSettings):
    """Environment-backed application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def __init__(self, **values: Any) -> None:
        super().__init__(**values)

    groq_api_key: str = Field(alias="GROQ_API_KEY")
    groq_model_fast: str = Field(default="llama-3.1-8b-instant", alias="GROQ_MODEL_FAST")
    groq_model_reasoning: str = Field(
        default="llama-3.3-70b-versatile", alias="GROQ_MODEL_REASONING"
    )
    retrieval_confidence_threshold: float = Field(
        default=DEFAULT_RETRIEVAL_CONFIDENCE_THRESHOLD,
        ge=0.0,
        le=1.0,
        alias="RETRIEVAL_CONFIDENCE_THRESHOLD",
    )
    database_url: str = Field(default=DEFAULT_DATABASE_URL, alias="DATABASE_URL")
