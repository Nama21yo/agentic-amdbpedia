from __future__ import annotations

from rag.embeddings import (
    DEFAULT_DENSE_MODEL,
    DEFAULT_DENSE_VECTOR_SIZE,
    DEFAULT_EMBEDDING_DEVICE,
    dense_embedding_text,
)


def test_default_dense_model_is_e5_small() -> None:
    assert DEFAULT_DENSE_MODEL == "intfloat/multilingual-e5-small"
    assert DEFAULT_DENSE_VECTOR_SIZE == 384
    assert DEFAULT_EMBEDDING_DEVICE == "cpu"


def test_e5_dense_text_uses_query_and_passage_prefixes() -> None:
    assert dense_embedding_text("አያታ ኮድ", input_type="query") == "query: አያታ ኮድ"
    assert (
        dense_embedding_text("Class: Airport | Property: iataLocationIdentifier")
        == "passage: Class: Airport | Property: iataLocationIdentifier"
    )


def test_dense_text_does_not_double_prefix() -> None:
    assert dense_embedding_text("query: አያታ ኮድ", input_type="query") == "query: አያታ ኮድ"


def test_non_e5_dense_text_is_unmodified() -> None:
    assert (
        dense_embedding_text(
            "Class: Airport",
            model_name="BAAI/bge-m3",
            input_type="passage",
        )
        == "Class: Airport"
    )
