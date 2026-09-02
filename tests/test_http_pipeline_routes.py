from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.applications import Starlette
from starlette.testclient import TestClient

from mcp_server.http_app import create_app
from rag.predict import PredictionResult
from rag.retrieval import NoMatchFound, SearchResult

BRIDGE_WIKITEXT = "{{Infobox bridge | ርዝመት = 1,700 ሜትር}}"


def _in_memory_app(**kwargs: Any) -> Starlette:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    return create_app(engine=engine, **kwargs)


def _fake_predict_property(amharic_property: str, **kwargs: object) -> object:
    if amharic_property != "ርዝመት":
        return NoMatchFound(query=amharic_property)
    return PredictionResult(
        property="length",
        used_llm=False,
        candidates=["length"],
        top_retrieval_result=SearchResult(
            property="length", ontology_class="Bridge", score=1.0, payload={}
        ),
    )


def _parse_sse_events(body: str) -> list[dict[str, object]]:
    events = []
    for chunk in body.split("\n\n"):
        data_line = next((line for line in chunk.splitlines() if line.startswith("data:")), None)
        if data_line is None:
            continue
        events.append(json.loads(data_line[len("data:") :].strip()))
    return events


def test_preview_streams_one_event_per_node_and_a_final_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("mcp_server.pipeline.predict_property", _fake_predict_property)
    app = _in_memory_app()

    with (
        TestClient(app) as client,
        client.stream(
            "POST", "/v1/preview", json={"infobox": BRIDGE_WIKITEXT, "target_class": "Bridge"}
        ) as response,
    ):
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    events = _parse_sse_events(body)

    node_names = [event["node"] for event in events]
    assert node_names == [
        "extract_infobox_fields",
        "predict_properties",
        "format_mapping_syntax",
        "persist_review_item",
        "result",
    ]
    result_event = events[-1]
    assert result_event["mappings"] == [
        {"templateProperty": "ርዝመት", "ontologyProperty": "length", "confidence": 1.0}
    ]
    for step_event in events[:-1]:
        assert step_event["status"] == "done"
        assert "detail" in step_event
        assert "timestamp" in step_event


def test_preview_rejects_a_request_with_no_infobox_field() -> None:
    app = _in_memory_app()

    with TestClient(app) as client:
        response = client.post("/v1/preview", json={})

        assert response.status_code == 400
        assert response.json()["error_type"] == "validation"


def test_preview_defaults_to_thing_when_no_target_class_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    async def spy_stream(
        infobox: str, *, domain_class: str, session: object, **kwargs: object
    ) -> AsyncIterator[dict[str, Any]]:
        captured["domain_class"] = domain_class
        yield {"node": "result", "mappings": []}

    monkeypatch.setattr("mcp_server.http_app.stream_mapping_pipeline", spy_stream)
    app = _in_memory_app()

    with (
        TestClient(app) as client,
        client.stream("POST", "/v1/preview", json={"infobox": BRIDGE_WIKITEXT}) as response,
    ):
        list(response.iter_text())

    assert captured["domain_class"] == "Thing"


def test_find_semantic_match_route_matches_the_mcp_tool_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_search(query: str, *, target_class: str | None = None, limit: int = 3) -> list[object]:
        return [SearchResult(property="length", ontology_class="Bridge", score=1.0, payload={})]

    app = _in_memory_app(search_func=fake_search)

    with TestClient(app) as client:
        response = client.post(
            "/v1/find-semantic-match", json={"amharic_property": "ርዝመት", "target_class": "Bridge"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        body = response.json()
        assert body["status"] == "ok"
        assert body["matches"][0]["property"] == "length"


def test_find_semantic_match_route_reports_no_match_honestly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_search(query: str, *, target_class: str | None = None, limit: int = 3) -> list[object]:
        return [NoMatchFound(query=query)]

    app = _in_memory_app(search_func=fake_search)

    with TestClient(app) as client:
        response = client.post("/v1/find-semantic-match", json={"amharic_property": "ያልታወቀ"})

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "no_match"
        assert body["matches"] == []


def test_find_semantic_match_route_rejects_missing_amharic_property() -> None:
    app = _in_memory_app()

    with TestClient(app) as client:
        response = client.post("/v1/find-semantic-match", json={})

        assert response.status_code == 400
        assert response.json()["error_type"] == "validation"
