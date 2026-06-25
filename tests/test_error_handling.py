from __future__ import annotations

import json
from typing import Any

import pytest

from errors import LLMUnavailableError, RetrievalUnavailableError
from mcp_server.agent import GroqClient, GroqUnavailableError
from mcp_server.server import find_semantic_match_impl
from rag.embeddings import lexical_sparse_vector
from rag.retrieval import NoMatchFound, RetrievalCircuitBreaker, encode_query, search


class RetryableGroqFailure(Exception):
    status_code = 429


class AlwaysFailingCompletions:
    def create(self, **_: Any) -> str:
        raise RetryableGroqFailure("rate limited")


class AlwaysFailingGroqSdk:
    def __init__(self) -> None:
        completion = AlwaysFailingCompletions()
        self.chat = type("Chat", (), {"completions": completion})()


class FakeSettings:
    groq_api_key = "gsk_test_placeholder"
    groq_model_fast = "llama-3.1-8b-instant"
    groq_model_reasoning = "llama-3.3-70b-versatile"


def test_mcp_boundary_maps_qdrant_down_to_client_safe_error() -> None:
    def search_func(_: str, **__: Any) -> list[Any]:
        raise OSError("connection refused with stack-ish detail")

    payload = json.loads(find_semantic_match_impl("አይካኦ_ኮድ", search_func=search_func))

    assert payload["status"] == "error"
    assert payload["error_type"] == "retrieval_unavailable"
    assert payload["message"] == "Retrieval service is unavailable"


def test_embedding_model_failure_raises_retrieval_unavailable() -> None:
    def broken_dense(_: str) -> list[float]:
        raise RuntimeError("model files missing")

    with pytest.raises(RetrievalUnavailableError, match="Embedding model unavailable"):
        encode_query("አይካኦ_ኮድ", dense_embedder=broken_dense, sparse_embedder=lexical_sparse_vector)


def test_groq_down_raises_llm_unavailable_taxonomy() -> None:
    client = GroqClient(
        settings=FakeSettings(),
        client=AlwaysFailingGroqSdk(),
        sleep=lambda _: None,
        max_attempts=1,
    )

    with pytest.raises(GroqUnavailableError) as exc_info:
        client.classify("አይካኦ_ኮድ")

    assert isinstance(exc_info.value, LLMUnavailableError)
    assert exc_info.value.error_type == "llm_unavailable"


def test_retrieval_circuit_breaker_degrades_after_failure() -> None:
    class BrokenClient:
        def query_points(self, **_: Any) -> None:
            raise OSError("qdrant down")

    breaker = RetrievalCircuitBreaker(failure_threshold=1, reset_after_seconds=60)
    with pytest.raises(RetrievalUnavailableError):
        search(
            "አይካኦ_ኮድ",
            client=BrokenClient(),
            dense_embedder=lambda _: [0.0] * 16,
            sparse_embedder=lexical_sparse_vector,
            circuit_breaker=breaker,
        )

    degraded = search(
        "አይካኦ_ኮድ",
        client=BrokenClient(),
        dense_embedder=lambda _: [0.0] * 16,
        sparse_embedder=lexical_sparse_vector,
        circuit_breaker=breaker,
    )
    assert degraded == [NoMatchFound(query="አይካኦ_ኮድ", reason="Retrieval temporarily unavailable")]
