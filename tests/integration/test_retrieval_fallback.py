from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rag.embeddings import deterministic_dense_vector, lexical_sparse_vector
from rag.indexing import index_corpus
from rag.retrieval import NoMatchFound, search

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
COLLECTION = "test_dbpedia_retrieval"


@pytest.fixture()
def indexed_client() -> Any:
    from qdrant_client import QdrantClient

    client = QdrantClient(url="http://localhost:6333")
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    index_corpus(
        data_dir=DATA_DIR,
        collection_name=COLLECTION,
        rebuild=True,
        dense_vector_size=16,
        dense_embedder=lambda text: deterministic_dense_vector(text, size=16),
        sparse_embedder=lexical_sparse_vector,
        client=client,
    )
    yield client
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)


def test_low_confidence_returns_no_match(indexed_client: Any) -> None:
    results = search(
        "random Latin lorem ipsum out of ontology",
        client=indexed_client,
        collection_name=COLLECTION,
        dense_embedder=lambda text: deterministic_dense_vector(text, size=16),
        sparse_embedder=lexical_sparse_vector,
        confidence_threshold=1.0,
    )

    assert results == [NoMatchFound(query="random Latin lorem ipsum out of ontology")]
