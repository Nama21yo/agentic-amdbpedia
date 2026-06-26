"""Shared dense and sparse embedding helpers."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
DEFAULT_DENSE_MODEL = "intfloat/multilingual-e5-small"
DEFAULT_SPARSE_MODEL = "Qdrant/bm25"
DEFAULT_DENSE_VECTOR_SIZE = 384
DEFAULT_EMBEDDING_DEVICE = "cpu"
E5_MODEL_MARKERS = ("e5-small", "e5-base", "e5-large", "multilingual-e5")
SENTENCE_TRANSFORMER_DENSE_MODELS = (DEFAULT_DENSE_MODEL, "BAAI/bge-m3")
TOKEN_RE = re.compile(r"[\w\u1200-\u137f]+", re.UNICODE)


@dataclass(frozen=True)
class SparseVector:
    """Sparse vector representation independent of a Qdrant import."""

    indices: list[int]
    values: list[float]


DenseEmbedder = Callable[[str], list[float]]
SparseEmbedder = Callable[[str], SparseVector]
DenseInputType = Literal["query", "passage"]


def lexical_sparse_vector(text: str, *, buckets: int = 65536) -> SparseVector:
    """Create a deterministic sparse vector that preserves exact lexical tokens.

    This fallback is intentionally simple and local. Production calls use
    FastEmbed's configured sparse model by default; tests use this function to
    avoid network/model downloads while still exercising sparse retrieval.
    """

    weights: dict[int, float] = {}
    for token in TOKEN_RE.findall(text.casefold()):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest, "big") % buckets
        weights[index] = weights.get(index, 0.0) + 1.0

    return SparseVector(
        indices=sorted(weights), values=[weights[index] for index in sorted(weights)]
    )


def deterministic_dense_vector(text: str, *, size: int = 16) -> list[float]:
    """Create a deterministic dense vector for tests and offline demos."""

    vector = [0.0] * size
    for token in TOKEN_RE.findall(text.casefold()):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
        index = int.from_bytes(digest[:4], "big") % size
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def _uses_e5_prefixes(model_name: str) -> bool:
    normalized_name = model_name.casefold()
    return any(marker in normalized_name for marker in E5_MODEL_MARKERS)


def dense_embedding_text(
    text: str,
    *,
    model_name: str = DEFAULT_DENSE_MODEL,
    input_type: DenseInputType = "passage",
) -> str:
    """Apply model-specific dense embedding formatting."""

    if not _uses_e5_prefixes(model_name):
        return text

    stripped = text.lstrip()
    if stripped.startswith(("query:", "passage:")):
        return text
    return f"{input_type}: {text}"


@lru_cache(maxsize=4)
def _dense_model(model_name: str, device: str) -> Any:
    if model_name in SENTENCE_TRANSFORMER_DENSE_MODELS:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(model_name, device=device)

    from fastembed import TextEmbedding

    return TextEmbedding(model_name=model_name, lazy_load=True)


@lru_cache(maxsize=4)
def _sparse_model(model_name: str) -> Any:
    from fastembed.sparse import SparseTextEmbedding

    return SparseTextEmbedding(model_name=model_name, lazy_load=True)


def _embed_dense(
    text: str,
    *,
    model_name: str = DEFAULT_DENSE_MODEL,
    input_type: DenseInputType = "passage",
    device: str | None = None,
) -> list[float]:
    """Embed text with the configured dense model."""

    formatted_text = dense_embedding_text(text, model_name=model_name, input_type=input_type)
    resolved_device = device or os.environ.get("EMBEDDING_DEVICE", DEFAULT_EMBEDDING_DEVICE)
    model = _dense_model(model_name, resolved_device)
    if hasattr(model, "encode"):
        embedding = model.encode(formatted_text, normalize_embeddings=True)
        return [float(value) for value in embedding.tolist()]
    embedding = next(model.query_embed([formatted_text]))
    return [float(value) for value in embedding.tolist()]


def embed_dense(
    text: str,
    model_name: str = DEFAULT_DENSE_MODEL,
    device: str | None = None,
) -> list[float]:
    """Embed an ontology corpus chunk for dense retrieval."""

    return _embed_dense(text, model_name=model_name, input_type="passage", device=device)


def embed_query_dense(
    text: str,
    model_name: str = DEFAULT_DENSE_MODEL,
    device: str | None = None,
) -> list[float]:
    """Embed a user query for dense retrieval."""

    return _embed_dense(text, model_name=model_name, input_type="query", device=device)


def embed_sparse(text: str, model_name: str = DEFAULT_SPARSE_MODEL) -> SparseVector:
    """Embed text with FastEmbed's sparse model."""

    embedding = next(_sparse_model(model_name).query_embed([text]))
    return SparseVector(
        indices=[int(index) for index in embedding.indices.tolist()],
        values=[float(value) for value in embedding.values.tolist()],
    )


def qdrant_sparse_vector(vector: SparseVector) -> Any:
    from qdrant_client import models

    return models.SparseVector(indices=vector.indices, values=vector.values)
