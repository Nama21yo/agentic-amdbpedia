from __future__ import annotations

import pytest

from rag.retrieval import RetrievalIndex, SearchResult, build_index, search

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def index() -> RetrievalIndex:
    # Built once for the whole module: real embeddings over the real ~2,948
    # -property corpus are expensive enough that re-embedding per query
    # would make this suite impractically slow.
    return build_index()


def top_properties(index: RetrievalIndex, query: str, target_class: str | None = None) -> list[str]:
    results = search(
        query, target_class=target_class, index=index, limit=3, confidence_threshold=0.0
    )
    return [result.property for result in results if isinstance(result, SearchResult)]


def test_hits_at_3_precision(index: RetrievalIndex) -> None:
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
        if expected_property in top_properties(index, query, target_class):
            hits += 1

    assert hits / len(labeled_queries) >= 0.8


def test_acronym_collision_sparse_channel_rescues_icao(index: RetrievalIndex) -> None:
    properties = top_properties(index, "አይካኦ_ኮድ mixed Latin ICAO", "Airport")

    assert "icaoLocationIdentifier" in properties
