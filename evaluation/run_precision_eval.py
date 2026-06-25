"""Run Hits@3 precision evaluation over golden retrieval queries."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rag.retrieval import NoMatchFound, RetrievalResult, SearchResult, search

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUERY_PATH = PROJECT_ROOT / "evaluation" / "test_queries.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "evaluation" / "latest_metrics.json"

SearchFunc = Callable[[str, str | None, int], list[RetrievalResult]]


def load_queries(path: Path = DEFAULT_QUERY_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON array")
    return [item for item in payload if isinstance(item, dict)]


def default_search_func(query: str, target_class: str | None, top_k: int) -> list[RetrievalResult]:
    return search(query, target_class=target_class, limit=top_k)


def run_precision_eval(
    *,
    query_path: Path = DEFAULT_QUERY_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    search_func: SearchFunc = default_search_func,
    top_k: int = 3,
) -> dict[str, Any]:
    queries = [query for query in load_queries(query_path) if not query["is_adversarial"]]
    breakdown: list[dict[str, Any]] = []
    hits = 0

    for item in queries:
        results = search_func(item["query"], item["target_class"], top_k)
        properties = [result.property for result in results if isinstance(result, SearchResult)]
        no_match = any(isinstance(result, NoMatchFound) for result in results)
        hit = item["expected_property"] in properties
        hits += int(hit)
        breakdown.append(
            {
                "id": item["id"],
                "query": item["query"],
                "target_class": item["target_class"],
                "expected_property": item["expected_property"],
                "top_properties": properties,
                "no_match": no_match,
                "hit": hit,
            }
        )

    payload = {
        "status": "ok",
        "metric": "hits_at_3",
        "hits_at_3": hits / len(queries) if queries else 0.0,
        "evaluated_queries": len(queries),
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
    args = parser.parse_args()
    payload = run_precision_eval(query_path=args.queries, output_path=args.output)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
