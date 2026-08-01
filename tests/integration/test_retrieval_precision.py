from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from config import Settings
from rag.embeddings import deterministic_dense_vector, lexical_sparse_vector
from rag.indexing import index_corpus
from rag.retrieval import SearchResult, search

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
COLLECTION = "test_dbpedia_retrieval_precision"


@pytest.fixture()
def indexed_client() -> Any:
    from qdrant_client import QdrantClient

    settings = Settings()
    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
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


def top_properties(client: Any, query: str, target_class: str | None = None) -> list[str]:
    results = search(
        query,
        target_class=target_class,
        client=client,
        collection_name=COLLECTION,
        limit=3,
        dense_embedder=lambda text: deterministic_dense_vector(text, size=16),
        sparse_embedder=lexical_sparse_vector,
        confidence_threshold=0.0,
    )
    return [result.property for result in results if isinstance(result, SearchResult)]


def test_hits_at_3_precision(indexed_client: Any) -> None:
    labeled_queries = [
        ("አያታ_ኮድ IATA", "Airport", "iataLocationIdentifier"),
        ("አይካኦ_ኮድ ICAO", "Airport", "icaoLocationIdentifier"),
        ("የመሮጫ_መንገድ_ርዝመት", "Airport", "runwayLength"),
        ("የግድብ_ከፍታ", "Dam", "height"),
        ("የወንዝ_ፍሳሽ", "River", "discharge"),
        ("የመድረክ_ስም", "MusicalArtist", "alias"),
        ("የተማሪዎች_ብዛት", "University", "numberOfStudents"),
        ("ጠቅላላ_ህዝብ", "Settlement", "populationTotal"),
        ("UTC_ልዩነት UTC", "Settlement", "utcOffset"),
        ("የአልጋ_ብዛት", "Hospital", "bedCount"),
    ]
    hits = 0
    for query, target_class, expected_property in labeled_queries:
        if expected_property in top_properties(indexed_client, query, target_class):
            hits += 1

    assert hits / len(labeled_queries) >= 0.8


def test_acronym_collision_sparse_channel_rescues_icao(indexed_client: Any) -> None:
    properties = top_properties(indexed_client, "አይካኦ_ኮድ mixed Latin ICAO", "Airport")

    assert "icaoLocationIdentifier" in properties
