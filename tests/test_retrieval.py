from __future__ import annotations

from typing import Any

import pytest

from rag.embeddings import SparseVector, deterministic_dense_vector, lexical_sparse_vector
from rag.retrieval import NoMatchFound, SearchResult, encode_query, search


class FakeQueryResponse:
    def __init__(self, points: list[Any]) -> None:
        self.points = points


class FakeScoredPoint:
    def __init__(self, score: float, payload: dict[str, Any]) -> None:
        self.score = score
        self.payload = payload


class FakeClient:
    def __init__(self) -> None:
        self.prefetch: list[Any] = []
        self.query: Any = None

    def query_points(self, **kwargs: Any) -> FakeQueryResponse:
        self.prefetch = kwargs["prefetch"]
        self.query = kwargs["query"]
        return FakeQueryResponse(
            [
                FakeScoredPoint(
                    0.8,
                    {
                        "class": "Airport",
                        "property": "icaoLocationIdentifier",
                        "xsd_type": "xsd:string",
                    },
                )
            ]
        )


def test_encode_query_uses_supplied_shared_embedders() -> None:
    calls: list[str] = []

    def dense(text: str) -> list[float]:
        calls.append(f"dense:{text}")
        return [1.0, 0.0]

    def sparse(text: str) -> SparseVector:
        calls.append(f"sparse:{text}")
        return SparseVector(indices=[1], values=[1.0])

    dense_vector, sparse_vector = encode_query(
        "አይካኦ_ኮድ", dense_embedder=dense, sparse_embedder=sparse
    )

    assert dense_vector == [1.0, 0.0]
    assert sparse_vector == SparseVector(indices=[1], values=[1.0])
    assert calls == ["dense:አይካኦ_ኮድ", "sparse:አይካኦ_ኮድ"]


def test_search_uses_qdrant_native_rrf_prefetch() -> None:
    client = FakeClient()

    results = search(
        "አይካኦ_ኮድ ICAO",
        target_class="Airport",
        client=client,
        dense_embedder=lambda text: deterministic_dense_vector(text, size=16),
        sparse_embedder=lexical_sparse_vector,
        confidence_threshold=0.1,
    )

    assert isinstance(results[0], SearchResult)
    assert results[0].property == "icaoLocationIdentifier"
    assert len(client.prefetch) == 2
    assert {prefetch.using for prefetch in client.prefetch} == {"dense", "sparse"}
    assert client.query.__class__.__name__ == "FusionQuery"
    assert str(client.query.fusion).lower().endswith("rrf")


def test_search_with_custom_embedders_does_not_require_groq_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    results = search(
        "አይካኦ_ኮድ ICAO",
        target_class="Airport",
        client=FakeClient(),
        dense_embedder=lambda text: deterministic_dense_vector(text, size=16),
        sparse_embedder=lexical_sparse_vector,
        confidence_threshold=0.1,
    )

    assert isinstance(results[0], SearchResult)
    assert results[0].property == "icaoLocationIdentifier"


def test_search_low_score_returns_no_match() -> None:
    class LowScoreClient(FakeClient):
        def query_points(self, **kwargs: Any) -> FakeQueryResponse:
            self.prefetch = kwargs["prefetch"]
            self.query = kwargs["query"]
            return FakeQueryResponse(
                [FakeScoredPoint(0.01, {"class": "Airport", "property": "alias"})]
            )

    results = search(
        "nonsense",
        client=LowScoreClient(),
        dense_embedder=lambda text: deterministic_dense_vector(text, size=16),
        sparse_embedder=lexical_sparse_vector,
        confidence_threshold=0.5,
    )

    assert results == [NoMatchFound(query="nonsense")]
