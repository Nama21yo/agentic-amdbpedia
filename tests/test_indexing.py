from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rag.embeddings import SparseVector, deterministic_dense_vector, lexical_sparse_vector
from rag.indexing import (
    DEFAULT_COLLECTION_NAME,
    build_points,
    chunk_corpus,
    create_collection,
    index_corpus,
    qdrant_client_from_settings,
)
from scripts.validate_corpus import parse_property_documents

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


class FakeClient:
    def __init__(self) -> None:
        self.exists = False
        self.deleted: list[str] = []
        self.created: list[str] = []
        self.indexes: list[tuple[str, str]] = []
        self.upserts: list[tuple[str, list[Any]]] = []

    def collection_exists(self, collection_name: str) -> bool:
        return self.exists

    def delete_collection(self, collection_name: str) -> None:
        self.deleted.append(collection_name)
        self.exists = False

    def create_collection(self, collection_name: str, **_: Any) -> None:
        self.created.append(collection_name)
        self.exists = True

    def create_payload_index(
        self, collection_name: str, field_name: str, field_schema: Any
    ) -> None:
        self.indexes.append((collection_name, field_name))

    def upsert(self, collection_name: str, points: list[Any], wait: bool) -> None:
        self.upserts.append((collection_name, points))


def test_chunk_count_matches_corpus() -> None:
    expected = sum(len(parse_property_documents(path)) for path in sorted(DATA_DIR.glob("*.md")))

    chunks = chunk_corpus(DATA_DIR)

    assert len(chunks) == expected == 36


def test_chunk_id_determinism() -> None:
    first = [chunk.chunk_id for chunk in chunk_corpus(DATA_DIR)]
    second = [chunk.chunk_id for chunk in chunk_corpus(DATA_DIR)]

    assert first == second


def test_chunk_text_format() -> None:
    chunk = next(
        chunk for chunk in chunk_corpus(DATA_DIR) if chunk.payload["property"] == "runwayLength"
    )

    assert chunk.text == (
        "Class: Airport | Property: runwayLength | Type: xsd:double | "
        "Description: Length of an airport runway, typically normalized into metres in "
        "DBpedia data."
    )
    assert chunk.payload["amharic_aliases"] == [
        "የመሮጫ_መንገድ_ርዝመት",
        "ራንዌይ_ርዝመት",
    ]


def test_build_points_folds_aliases_into_sparse_text() -> None:
    captured_sparse_texts: list[str] = []

    def sparse_embedder(text: str) -> SparseVector:
        captured_sparse_texts.append(text)
        return lexical_sparse_vector(text)

    chunks = [
        chunk
        for chunk in chunk_corpus(DATA_DIR)
        if chunk.payload["property"] == "icaoLocationIdentifier"
    ]
    points = build_points(
        chunks,
        dense_embedder=lambda text: deterministic_dense_vector(text, size=16),
        sparse_embedder=sparse_embedder,
    )

    assert len(points) == 1
    assert "አይካኦ_ኮድ" in captured_sparse_texts[0]
    assert "ICAO" in captured_sparse_texts[0]


def test_create_collection_creates_payload_index() -> None:
    client = FakeClient()

    create_collection(client, DEFAULT_COLLECTION_NAME, dense_vector_size=16)

    assert client.created == [DEFAULT_COLLECTION_NAME]
    assert client.indexes == [(DEFAULT_COLLECTION_NAME, "class")]


def test_create_collection_rebuild_deletes_existing_collection() -> None:
    client = FakeClient()
    client.exists = True

    create_collection(client, DEFAULT_COLLECTION_NAME, dense_vector_size=16, recreate=True)

    assert client.deleted == [DEFAULT_COLLECTION_NAME]
    assert client.created == [DEFAULT_COLLECTION_NAME]


def test_index_corpus_upserts_once_per_chunk() -> None:
    client = FakeClient()

    count = index_corpus(
        data_dir=DATA_DIR,
        client=client,
        dense_vector_size=16,
        dense_embedder=lambda text: deterministic_dense_vector(text, size=16),
        sparse_embedder=lexical_sparse_vector,
    )

    assert count == 36
    assert len(client.upserts) == 1
    assert len(client.upserts[0][1]) == 36


def test_indexing_qdrant_client_does_not_require_groq_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")

    client = qdrant_client_from_settings()

    assert client is not None
