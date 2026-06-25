from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pytest

from mcp_server.agent import ReasoningStep, ToolRequest, is_injection_attempt, run_mapping_agent
from rag.embeddings import deterministic_dense_vector, lexical_sparse_vector
from rag.retrieval import RetrievalResult, SearchResult, search

pytestmark = pytest.mark.perf


class FakeQueryResponse:
    def __init__(self, points: list[Any]) -> None:
        self.points = points


class FakeScoredPoint:
    def __init__(self, score: float, payload: dict[str, Any]) -> None:
        self.score = score
        self.payload = payload


class FakeQdrantClient:
    def query_points(self, **_: Any) -> FakeQueryResponse:
        return FakeQueryResponse(
            [
                FakeScoredPoint(
                    0.8,
                    {
                        "class": "Airport",
                        "property": "icaoLocationIdentifier",
                        "xsd_type": "xsd:string",
                    },
                )
            ]
        )


class ScriptedGroq:
    def __init__(self) -> None:
        self.index = 0
        self.steps = [
            ReasoningStep(
                tool_call=ToolRequest(
                    "find_semantic_match",
                    {"amharic_property": "አይካኦ_ኮድ", "target_class": "Airport"},
                )
            ),
            ReasoningStep(
                tool_call=ToolRequest(
                    "generate_mapping_syntax",
                    {
                        "domain_class": "Airport",
                        "mappings": [
                            {
                                "templateProperty": "አይካኦ_ኮድ",
                                "ontologyProperty": "icaoLocationIdentifier",
                            }
                        ],
                    },
                )
            ),
            ReasoningStep(content="Done.", final=True),
        ]

    def reason(self, _: list[dict[str, Any]], __: list[dict[str, Any]]) -> ReasoningStep:
        step = self.steps[min(self.index, len(self.steps) - 1)]
        self.index += 1
        return step


def _p95(durations: list[float]) -> float:
    ordered = sorted(durations)
    index = min(len(ordered) - 1, int(len(ordered) * 0.95))
    return ordered[index]


def _assert_budget(
    name: str,
    operation: Callable[[], Any],
    budget_seconds: float,
    benchmark: Any,
) -> None:
    durations: list[float] = []

    def run_once() -> None:
        start = time.perf_counter()
        operation()
        durations.append(time.perf_counter() - start)

    operation()
    benchmark.pedantic(run_once, rounds=5, iterations=1)
    p95 = _p95(durations)
    benchmark.extra_info[f"{name}_p95_seconds"] = p95
    assert p95 < budget_seconds * 2


def test_qdrant_hybrid_query_latency_budget(benchmark: Any) -> None:
    def operation() -> list[RetrievalResult]:
        results = search(
            "አይካኦ_ኮድ ICAO",
            target_class="Airport",
            client=FakeQdrantClient(),
            dense_embedder=lambda text: deterministic_dense_vector(text, size=16),
            sparse_embedder=lexical_sparse_vector,
            confidence_threshold=0.1,
            circuit_breaker=None,
        )
        assert isinstance(results[0], SearchResult)
        return results

    _assert_budget("qdrant_hybrid_query", operation, 0.2, benchmark)


def test_fast_path_classification_latency_budget(benchmark: Any) -> None:
    _assert_budget(
        "fast_path_classification",
        lambda: is_injection_attempt("አይካኦ_ኮድ ለAirport ይፈልጉ"),
        1.0,
        benchmark,
    )


def test_react_happy_path_latency_budget(benchmark: Any) -> None:
    def operation() -> None:
        def runner(request: ToolRequest) -> str:
            if request.name == "find_semantic_match":
                return (
                    '{"status":"ok","matches":[{"property":"icaoLocationIdentifier",'
                    '"class":"Airport"}]}'
                )
            return (
                '<TemplateMapping mapToClass="dbo:Airport">\n'
                "  <PropertyMapping>\n"
                "    <templateProperty>አይካኦ_ኮድ</templateProperty>\n"
                "    <ontologyProperty>icaoLocationIdentifier</ontologyProperty>\n"
                "  </PropertyMapping>\n"
                "</TemplateMapping>"
            )

        response = run_mapping_agent(
            "አይካኦ_ኮድ",
            target_class="Airport",
            groq_client=ScriptedGroq(),
            tool_runner=runner,
        )
        assert response.final_answer == "Done."

    _assert_budget("react_happy_path", operation, 4.0, benchmark)
