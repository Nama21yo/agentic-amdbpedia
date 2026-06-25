"""Run answer relevance evaluation with LLM-judge compatible hooks."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp_server.agent import AgentResponse, GroqClient, run_mapping_agent

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUERY_PATH = PROJECT_ROOT / "evaluation" / "test_queries.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "evaluation" / "relevance_metrics.json"
DEFAULT_OVERRIDES_PATH = PROJECT_ROOT / "evaluation" / "human_overrides.csv"


@dataclass(frozen=True)
class JudgeResult:
    score: int
    rationale: str


AgentFunc = Callable[[dict[str, Any]], AgentResponse]
JudgeFunc = Callable[[dict[str, Any], str], JudgeResult]


def load_queries(path: Path = DEFAULT_QUERY_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON array")
    return [item for item in payload if isinstance(item, dict)]


def load_human_overrides(path: Path = DEFAULT_OVERRIDES_PATH) -> dict[str, JudgeResult]:
    if not path.exists():
        return {}
    overrides: dict[str, JudgeResult] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            query_id = row.get("id", "").strip()
            if not query_id or not row.get("score"):
                continue
            overrides[query_id] = JudgeResult(
                score=int(row["score"]),
                rationale=row.get("rationale", "human override").strip() or "human override",
            )
    return overrides


def heuristic_judge(query: dict[str, Any], answer: str) -> JudgeResult:
    expected = query["expected_property"]
    if query["is_adversarial"] and ("Rejected:" in answer or "No confident" in answer):
        return JudgeResult(score=5, rationale="Correct refusal for adversarial or no-match query.")
    if isinstance(expected, str) and expected in answer:
        return JudgeResult(score=5, rationale="Answer contains the expected grounded property.")
    if "<TemplateMapping" in answer and isinstance(expected, str):
        return JudgeResult(
            score=4, rationale="Answer used XML mapping output but omitted the property name."
        )
    return JudgeResult(score=2, rationale="Answer did not clearly match the relevance anchor.")


def default_agent_func(query: dict[str, Any]) -> AgentResponse:
    return run_mapping_agent(
        query["query"],
        target_class=query["target_class"],
        groq_client=GroqClient(),
    )


class GroqRelevanceJudge:
    """LLM-judge wrapper with a strict 1-5 rubric."""

    def __init__(self, groq_client: GroqClient | None = None) -> None:
        self.groq_client = groq_client or GroqClient()

    def __call__(self, query: dict[str, Any], answer: str) -> JudgeResult:
        prompt = (
            "Score answer relevance from 1 to 5 as JSON with keys score and rationale. "
            "5 means the answer identifies the expected property and uses/mentions "
            "deterministic XML; "
            "1 means hallucinated or wrong. "
            f"Expected anchor: {query['expected_relevance_anchor']}\nAnswer: {answer}"
        )
        response = self.groq_client._create_with_retry(  # noqa: SLF001
            model=self.groq_client.settings.groq_model_reasoning,
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            payload = json.loads(response.choices[0].message.content or "{}")
            score = int(payload["score"])
            rationale = str(payload["rationale"])
        except (AttributeError, IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return heuristic_judge(query, answer)
        return JudgeResult(score=max(1, min(5, score)), rationale=rationale)


def run_relevance_eval(
    *,
    query_path: Path = DEFAULT_QUERY_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    overrides_path: Path = DEFAULT_OVERRIDES_PATH,
    agent_func: AgentFunc = default_agent_func,
    judge_func: JudgeFunc = heuristic_judge,
) -> dict[str, Any]:
    overrides = load_human_overrides(overrides_path)
    breakdown: list[dict[str, Any]] = []

    for query in load_queries(query_path):
        agent_response = agent_func(query)
        if query["id"] in overrides:
            judge = overrides[query["id"]]
            source = "human_override"
        else:
            judge = judge_func(query, agent_response.final_answer)
            source = "judge"
        breakdown.append(
            {
                "id": query["id"],
                "query": query["query"],
                "score": judge.score,
                "rationale": judge.rationale,
                "source": source,
                "answer": agent_response.final_answer,
                "expected_relevance_anchor": query["expected_relevance_anchor"],
            }
        )

    mean_score = sum(item["score"] for item in breakdown) / len(breakdown) if breakdown else 0.0
    payload = {
        "status": "ok",
        "metric": "answer_relevance_1_to_5",
        "mean_relevance": mean_score,
        "evaluated_queries": len(breakdown),
        "breakdown": breakdown,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERY_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES_PATH)
    args = parser.parse_args()
    payload = run_relevance_eval(
        query_path=args.queries,
        output_path=args.output,
        overrides_path=args.overrides,
        agent_func=default_agent_func,
        judge_func=GroqRelevanceJudge(),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
