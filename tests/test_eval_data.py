from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUERY_PATH = PROJECT_ROOT / "evaluation" / "test_queries.json"


def test_query_set_schema_and_count() -> None:
    queries = json.loads(QUERY_PATH.read_text(encoding="utf-8"))

    assert len(queries) == 10
    required = {
        "id",
        "query",
        "target_class",
        "expected_property",
        "expected_relevance_anchor",
        "is_adversarial",
    }
    for query in queries:
        assert required <= set(query)
        assert isinstance(query["id"], str) and query["id"]
        assert isinstance(query["query"], str) and query["query"]
        assert isinstance(query["expected_relevance_anchor"], str)
        assert isinstance(query["is_adversarial"], bool)

    classes = {query["target_class"] for query in queries if not query["is_adversarial"]}
    assert {"Airport", "Dam", "MusicalArtist"} <= classes
    assert any(query["id"] == "airport_icao" for query in queries)
    assert any(query["id"] == "out_of_domain" and query["is_adversarial"] for query in queries)
    assert any(query["id"] == "injection_attempt" and query["is_adversarial"] for query in queries)
