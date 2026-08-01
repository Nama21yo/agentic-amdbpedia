from __future__ import annotations

import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUERY_PATH = PROJECT_ROOT / "evaluation" / "test_queries.json"
MANUAL_SCORES_PATH = PROJECT_ROOT / "evaluation" / "human_overrides.csv"


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


def test_manual_relevance_scores_cover_every_query() -> None:
    queries = json.loads(QUERY_PATH.read_text(encoding="utf-8"))
    with MANUAL_SCORES_PATH.open(encoding="utf-8", newline="") as handle:
        scores = list(csv.DictReader(handle))

    assert {row["id"] for row in scores} == {query["id"] for query in queries}
    assert all(1 <= int(row["score"]) <= 5 for row in scores)
    assert all(row["rationale"].strip() for row in scores)
