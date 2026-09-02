"""Runtime configuration for the mapping assistant."""

from __future__ import annotations

from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from rag.embeddings import DEFAULT_DENSE_MODEL as DEFAULT_DENSE_MODEL
from rag.embeddings import DEFAULT_EMBEDDING_DEVICE as DEFAULT_EMBEDDING_DEVICE
from rag.embeddings import DEFAULT_SPARSE_MODEL as DEFAULT_SPARSE_MODEL

# Re-exported from rag.embeddings so there is a single source of truth for
# which embedding model is the real, currently-active default (refs 10.2).
DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_RETRIEVAL_CONFIDENCE_THRESHOLD = 0.35


class Settings(BaseSettings):
    """Environment-backed application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def __init__(self, **values: Any) -> None:
        super().__init__(**values)

    groq_api_key: str = Field(alias="GROQ_API_KEY")
    qdrant_url: str = Field(default=DEFAULT_QDRANT_URL, alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")
    embedding_model_dense: str = Field(default=DEFAULT_DENSE_MODEL, alias="EMBEDDING_MODEL_DENSE")
    embedding_model_sparse: str = Field(
        default=DEFAULT_SPARSE_MODEL, alias="EMBEDDING_MODEL_SPARSE"
    )
    embedding_device: str = Field(default=DEFAULT_EMBEDDING_DEVICE, alias="EMBEDDING_DEVICE")
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
