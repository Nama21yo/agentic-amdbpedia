from __future__ import annotations

import io
import json
import logging
from typing import Any

from logging_config import configure_logging, log_event
from mcp_server.server import find_semantic_match_impl
from rag.retrieval import SearchResult


def test_correlation_id_propagates_across_layers() -> None:
    stream = io.StringIO()
    configure_logging(stream=stream, force=True)

    def search_func(_: str, **__: Any) -> list[SearchResult]:
        log_event(logging.getLogger("dbpedia_mapping_assistant.retrieval"), "fake.retrieval")
        return [
            SearchResult(
                property="icaoLocationIdentifier",
                ontology_class="Airport",
                score=0.91,
                payload={"xsd_type": "xsd:string"},
            )
        ]

    response = json.loads(
        find_semantic_match_impl("አይካኦ_ኮድ", target_class="Airport", search_func=search_func)
    )
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    correlation_ids = {record["correlation_id"] for record in records}

    assert response["status"] == "ok"
    assert response["correlation_id"] in correlation_ids
    assert len(correlation_ids) == 1
    assert {record["event"] for record in records} >= {
        "mcp.find_semantic_match.start",
        "fake.retrieval",
        "mcp.find_semantic_match.complete",
    }
