from __future__ import annotations

import pytest

from errors import RetrievalUnavailableError
from rag.embeddings import (
    DEFAULT_DENSE_MODEL,
    DEFAULT_EMBEDDING_DEVICE,
    DEFAULT_SPARSE_MODEL,
    SparseVector,
    dense_vector_size,
    embed_dense,
    embed_query_dense,
    embed_sparse,
    lexical_sparse_vector,
)


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_default_dense_model_is_the_amharic_property_retriever() -> None:
    assert DEFAULT_DENSE_MODEL == "dice-research/amharic-property-retriever-afro-xlmr-base"
    assert DEFAULT_EMBEDDING_DEVICE == "cpu"


def test_default_sparse_model_is_bm25() -> None:
    assert DEFAULT_SPARSE_MODEL == "Qdrant/bm25"


def test_lexical_sparse_vector_is_deterministic_and_order_independent() -> None:
    first = lexical_sparse_vector("ርዝመት length")
    second = lexical_sparse_vector("length ርዝመት")

    assert isinstance(first, SparseVector)
    assert sorted(zip(first.indices, first.values, strict=True)) == sorted(
        zip(second.indices, second.values, strict=True)
    )


def test_lexical_sparse_vector_distinguishes_unrelated_text() -> None:
    length_vector = lexical_sparse_vector("length")
    unrelated_vector = lexical_sparse_vector("volcano eruption")

    assert set(length_vector.indices).isdisjoint(unrelated_vector.indices)


@pytest.mark.integration
def test_dense_embeddings_are_l2_normalized_and_have_a_real_dimension() -> None:
    vector = embed_dense("ርዝመት")
    size = dense_vector_size()

    assert len(vector) == size
    assert size > 1  # a real transformer embedding, not a placeholder scalar
    assert sum(value * value for value in vector) == pytest.approx(1.0, abs=1e-4)


@pytest.mark.integration
def test_dense_embeddings_are_deterministic_for_the_same_text() -> None:
    first = embed_dense("የተወለደበት ቦታ")
    second = embed_dense("የተወለደበት ቦታ")

    assert first == second


@pytest.mark.integration
def test_queries_and_passages_use_the_same_dense_vector_space() -> None:
    text = "ርዝመት"
    assert embed_query_dense(text) == embed_dense(text)


@pytest.mark.integration
def test_semantically_related_terms_score_higher_than_unrelated_ones() -> None:
    """Acceptance criterion for 10.2: an Amharic term and its English translation
    should be closer in embedding space than two unrelated concepts."""

    length_am = embed_dense("ርዝመት")  # Amharic for "length"
    length_en = embed_dense("length")
    unrelated_en = embed_dense("volcano eruption schedule")

    related_score = _cosine(length_am, length_en)
    unrelated_score = _cosine(length_am, unrelated_en)

    assert related_score > unrelated_score


@pytest.mark.integration
def test_unknown_dense_model_raises_retrieval_unavailable_error() -> None:
    with pytest.raises(RetrievalUnavailableError):
        embed_dense("length", model_name="this-model-does-not-exist/afro-xlmr-fake")


@pytest.mark.integration
def test_embed_sparse_uses_bm25_and_returns_matching_indices() -> None:
    vector = embed_sparse("length")

    assert isinstance(vector, SparseVector)
    assert vector.indices
    assert len(vector.indices) == len(vector.values)
