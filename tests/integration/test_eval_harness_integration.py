from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evaluation.run_precision_eval import run_precision_eval
from evaluation.run_relevance_eval import JudgeResult, run_relevance_eval
from mcp_server.agent import AgentResponse, TraceEvent
from rag.retrieval import RetrievalResult, SearchResult

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUERY_PATH = PROJECT_ROOT / "evaluation" / "test_queries.json"


def test_precision_harness_writes_valid_metrics_file(tmp_path: Path) -> None:
    output = tmp_path / "latest_metrics.json"

    def search_func(query: str, target_class: str | None, _top_k: int) -> list[RetrievalResult]:
        queries = json.loads(QUERY_PATH.read_text(encoding="utf-8"))
        expected = next(item["expected_property"] for item in queries if item["query"] == query)
        return [
            SearchResult(
                property=str(expected),
                ontology_class=str(target_class),
                score=1.0,
                payload={},
            )
        ]

    payload = run_precision_eval(
        query_path=QUERY_PATH,
        output_path=output,
        search_func=search_func,
    )

    assert output.exists()
    assert payload["hits_at_3"] == 1.0
    assert payload["precision_at_1"] == 1.0
    assert all(item["top_1_correct"] for item in payload["breakdown"])
    assert len(payload["breakdown"]) == 8


def test_precision_at_1_distinguishes_top_rank_from_hits_at_3(tmp_path: Path) -> None:
    output = tmp_path / "latest_metrics.json"

    def search_func(query: str, target_class: str | None, _top_k: int) -> list[RetrievalResult]:
        queries = json.loads(QUERY_PATH.read_text(encoding="utf-8"))
        expected = next(item["expected_property"] for item in queries if item["query"] == query)
        return [
            SearchResult(
                property="wrongTopResult",
                ontology_class=str(target_class),
                score=1.0,
                payload={},
            ),
            SearchResult(
                property=str(expected),
                ontology_class=str(target_class),
                score=0.9,
                payload={},
            ),
        ]

    payload = run_precision_eval(
        query_path=QUERY_PATH,
        output_path=output,
        search_func=search_func,
    )

    assert payload["hits_at_3"] == 1.0
    assert payload["precision_at_1"] == 0.0


def test_relevance_harness_produces_score_per_query(tmp_path: Path) -> None:
    output = tmp_path / "relevance_metrics.json"
    overrides = tmp_path / "human_overrides.csv"
    overrides.write_text(
        "id,score,rationale\nartist_birth_name,4,manual correction\n", encoding="utf-8"
    )

    def agent_func(query: dict[str, Any]) -> AgentResponse:
        if query["is_adversarial"]:
            answer = "Rejected: prompt-injection attempt detected."
        else:
            answer = f"Grounded property: {query['expected_property']} <TemplateMapping />"
        return AgentResponse(final_answer=answer, trace=[TraceEvent("test")])

    def judge_func(_query: dict[str, Any], _answer: str) -> JudgeResult:
        return JudgeResult(score=5, rationale="deterministic judge")

    payload = run_relevance_eval(
        query_path=QUERY_PATH,
        output_path=output,
        overrides_path=overrides,
        agent_func=agent_func,
        judge_func=judge_func,
    )

    assert output.exists()
    assert payload["evaluated_queries"] == 10
    assert all(1 <= item["score"] <= 5 for item in payload["breakdown"])
    assert any(item["source"] == "human_override" for item in payload["breakdown"])
