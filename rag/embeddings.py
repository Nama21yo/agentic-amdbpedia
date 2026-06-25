"""Shared dense and sparse embedding helpers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
DEFAULT_DENSE_MODEL = "BAAI/bge-m3"
DEFAULT_SPARSE_MODEL = "Qdrant/bm25"
DEFAULT_DENSE_VECTOR_SIZE = 1024
TOKEN_RE = re.compile(r"[\w\u1200-\u137f]+", re.UNICODE)


@dataclass(frozen=True)
class SparseVector:
    """Sparse vector representation independent of a Qdrant import."""

    indices: list[int]
    values: list[float]


DenseEmbedder = Callable[[str], list[float]]
SparseEmbedder = Callable[[str], SparseVector]


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


@lru_cache(maxsize=4)
def _dense_model(model_name: str) -> Any:
    if model_name == DEFAULT_DENSE_MODEL:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(model_name)

    from fastembed import TextEmbedding

    return TextEmbedding(model_name=model_name, lazy_load=True)


@lru_cache(maxsize=4)
def _sparse_model(model_name: str) -> Any:
    from fastembed.sparse import SparseTextEmbedding

    return SparseTextEmbedding(model_name=model_name, lazy_load=True)


def embed_dense(text: str, model_name: str = DEFAULT_DENSE_MODEL) -> list[float]:
    """Embed text with the configured dense model."""

    model = _dense_model(model_name)
    if hasattr(model, "encode"):
        embedding = model.encode(text, normalize_embeddings=True)
        return [float(value) for value in embedding.tolist()]
    embedding = next(model.query_embed([text]))
    return [float(value) for value in embedding.tolist()]


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
