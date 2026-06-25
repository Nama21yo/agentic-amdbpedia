"""Hybrid retrieval over DBpedia ontology property chunks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import Settings
from rag.embeddings import (
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    DenseEmbedder,
    SparseEmbedder,
    SparseVector,
    embed_dense,
    embed_sparse,
    qdrant_sparse_vector,
)
from rag.indexing import DEFAULT_COLLECTION_NAME, qdrant_client_from_settings


@dataclass(frozen=True)
class SearchResult:
    property: str
    ontology_class: str
    score: float
    payload: dict[str, Any]


@dataclass(frozen=True)
class NoMatchFound:
    query: str
    reason: str = "No Match Found"


RetrievalResult = SearchResult | NoMatchFound


def encode_query(
    amharic_text: str,
    *,
    dense_embedder: DenseEmbedder = embed_dense,
    sparse_embedder: SparseEmbedder = embed_sparse,
) -> tuple[list[float], SparseVector]:
    """Encode a query with the exact same embedders used for indexing."""

    return dense_embedder(amharic_text), sparse_embedder(amharic_text)


def _class_filter(target_class: str | None) -> Any | None:
    if not target_class:
        return None

    from qdrant_client import models

    return models.Filter(
        must=[
            models.FieldCondition(
                key="class",
                match=models.MatchValue(value=target_class),
            )
        ]
    )


def _payload_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def search(
    query: str,
    *,
    target_class: str | None = None,
    limit: int = 3,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    confidence_threshold: float | None = None,
    client: Any | None = None,
    dense_embedder: DenseEmbedder = embed_dense,
    sparse_embedder: SparseEmbedder = embed_sparse,
    settings: Settings | None = None,
) -> list[RetrievalResult]:
    """Search Qdrant with native dense+sparse RRF fusion."""

    if not query.strip():
        return [NoMatchFound(query=query, reason="Empty query")]

    from qdrant_client import models

    resolved_settings = settings
    threshold = (
        confidence_threshold
        if confidence_threshold is not None
        else (resolved_settings or Settings()).retrieval_confidence_threshold
    )
    dense_vector, sparse_vector = encode_query(
        query,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
    )
    resolved_client = client or qdrant_client_from_settings(resolved_settings)
    query_filter = _class_filter(target_class)
    response = resolved_client.query_points(
        collection_name=collection_name,
        prefetch=[
            models.Prefetch(
                query=dense_vector,
                using=DENSE_VECTOR_NAME,
                filter=query_filter,
                limit=max(limit, 10),
            ),
            models.Prefetch(
                query=qdrant_sparse_vector(sparse_vector),
                using=SPARSE_VECTOR_NAME,
                filter=query_filter,
                limit=max(limit, 10),
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
        with_payload=True,
    )
    scored_points = response.points
    if not scored_points or float(scored_points[0].score) < threshold:
        return [NoMatchFound(query=query)]

    results: list[RetrievalResult] = []
    for point in scored_points:
        payload = point.payload or {}
        if not isinstance(payload, dict):
            continue
        results.append(
            SearchResult(
                property=_payload_string(payload, "property"),
                ontology_class=_payload_string(payload, "class"),
                score=float(point.score),
                payload=payload,
            )
        )
    return results or [NoMatchFound(query=query)]
