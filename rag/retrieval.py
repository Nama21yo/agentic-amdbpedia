"""Hybrid retrieval over DBpedia ontology property chunks."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from functools import partial
from typing import Any

from config import Settings
from errors import RetrievalUnavailableError
from logging_config import log_event
from rag.embeddings import (
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    DenseEmbedder,
    SparseEmbedder,
    SparseVector,
    embed_query_dense,
    embed_sparse,
    qdrant_sparse_vector,
)
from rag.indexing import DEFAULT_COLLECTION_NAME, qdrant_client_from_settings

LOGGER = logging.getLogger("dbpedia_mapping_assistant.retrieval")


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


@dataclass
class RetrievalCircuitBreaker:
    """Small in-process circuit breaker for transient Qdrant outages."""

    failure_threshold: int = 3
    reset_after_seconds: float = 30.0
    failures: int = 0
    opened_at: float | None = None

    def allow_request(self, now: float | None = None) -> bool:
        current = now if now is not None else time.monotonic()
        if self.opened_at is None:
            return True
        if current - self.opened_at >= self.reset_after_seconds:
            self.failures = 0
            self.opened_at = None
            return True
        return False

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self, now: float | None = None) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = now if now is not None else time.monotonic()


DEFAULT_CIRCUIT_BREAKER = RetrievalCircuitBreaker()


def encode_query(
    amharic_text: str,
    *,
    dense_embedder: DenseEmbedder = embed_query_dense,
    sparse_embedder: SparseEmbedder = embed_sparse,
) -> tuple[list[float], SparseVector]:
    """Encode a query with the exact same embedders used for indexing."""

    try:
        return dense_embedder(amharic_text), sparse_embedder(amharic_text)
    except Exception as exc:
        raise RetrievalUnavailableError(f"Embedding model unavailable: {exc}") from exc


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
    dense_embedder: DenseEmbedder = embed_query_dense,
    sparse_embedder: SparseEmbedder = embed_sparse,
    settings: Settings | None = None,
    circuit_breaker: RetrievalCircuitBreaker | None = DEFAULT_CIRCUIT_BREAKER,
) -> list[RetrievalResult]:
    """Search Qdrant with native dense+sparse RRF fusion."""

    if not query.strip():
        return [NoMatchFound(query=query, reason="Empty query")]
    if circuit_breaker is not None and not circuit_breaker.allow_request():
        log_event(LOGGER, "retrieval.circuit_open", target_class=target_class)
        return [NoMatchFound(query=query, reason="Retrieval temporarily unavailable")]
    log_event(LOGGER, "retrieval.start", target_class=target_class, limit=limit)

    from qdrant_client import models

    resolved_settings = settings or Settings()
    threshold = (
        confidence_threshold
        if confidence_threshold is not None
        else resolved_settings.retrieval_confidence_threshold
    )
    if dense_embedder is embed_query_dense:
        dense_embedder = partial(
            embed_query_dense,
            model_name=resolved_settings.embedding_model_dense,
            device=resolved_settings.embedding_device,
        )
    if sparse_embedder is embed_sparse:
        sparse_embedder = partial(embed_sparse, model_name=resolved_settings.embedding_model_sparse)
    dense_vector, sparse_vector = encode_query(
        query,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
    )
    resolved_client = client or qdrant_client_from_settings(resolved_settings)
    query_filter = _class_filter(target_class)
    try:
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
    except Exception as exc:
        if circuit_breaker is not None:
            circuit_breaker.record_failure()
        log_event(LOGGER, "retrieval.unavailable", error=exc.__class__.__name__)
        raise RetrievalUnavailableError("Qdrant retrieval is unavailable") from exc
    if circuit_breaker is not None:
        circuit_breaker.record_success()
    scored_points = response.points
    if not scored_points or float(scored_points[0].score) < threshold:
        log_event(LOGGER, "retrieval.no_match", threshold=threshold)
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
    log_event(LOGGER, "retrieval.complete", result_count=len(results))
    return results or [NoMatchFound(query=query)]
