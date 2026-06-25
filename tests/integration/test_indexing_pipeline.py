from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rag.embeddings import deterministic_dense_vector, lexical_sparse_vector
from rag.indexing import create_collection, index_corpus

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
COLLECTION = "test_dbpedia_indexing"


@pytest.fixture()
def qdrant_client() -> Any:
    from qdrant_client import QdrantClient

    client = QdrantClient(url="http://localhost:6333")
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    yield client
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)


def index_test_corpus(client: Any, *, rebuild: bool = False) -> int:
    return index_corpus(
        data_dir=DATA_DIR,
        collection_name=COLLECTION,
        rebuild=rebuild,
        dense_vector_size=16,
        dense_embedder=lambda text: deterministic_dense_vector(text, size=16),
        sparse_embedder=lexical_sparse_vector,
        client=client,
    )


def test_idempotent_upsert(qdrant_client: Any) -> None:
    first_count = index_test_corpus(qdrant_client, rebuild=True)
    second_count = index_test_corpus(qdrant_client)

    collection = qdrant_client.get_collection(COLLECTION)

    assert first_count == second_count == 36
    assert collection.points_count == 36


def test_payload_filter_index_exists(qdrant_client: Any) -> None:
    create_collection(qdrant_client, COLLECTION, dense_vector_size=16, recreate=True)

    schema = qdrant_client.get_collection(COLLECTION).payload_schema

    assert "class" in schema


def test_point_count_matches_chunk_count(qdrant_client: Any) -> None:
    count = index_test_corpus(qdrant_client, rebuild=True)

    collection = qdrant_client.get_collection(COLLECTION)

    assert collection.points_count == count
