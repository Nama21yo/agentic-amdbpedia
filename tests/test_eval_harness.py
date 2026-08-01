from __future__ import annotations

import json
from pathlib import Path

from evaluation.generate_results import generate_results_markdown, write_results


def test_results_md_generation_is_deterministic(tmp_path: Path) -> None:
    precision = tmp_path / "precision.json"
    relevance = tmp_path / "relevance.json"
    output = tmp_path / "results.md"
    precision.write_text(
        json.dumps(
            {
                "status": "ok",
                "hits_at_3": 1.0,
                "evaluated_queries": 1,
                "breakdown": [
                    {
                        "id": "airport_icao",
                        "expected_property": "icaoLocationIdentifier",
                        "top_properties": ["icaoLocationIdentifier"],
                        "hit": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    relevance.write_text(
        json.dumps(
            {
                "status": "ok",
                "review_method": "manual_1_to_5",
                "manual_reviews": 1,
                "mean_relevance": 5.0,
                "evaluated_queries": 1,
                "breakdown": [
                    {
                        "id": "airport_icao",
                        "score": 5,
                        "source": "human_override",
                        "rationale": "correct",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    first = write_results(precision_path=precision, relevance_path=relevance, output_path=output)
    second = generate_results_markdown(precision_path=precision, relevance_path=relevance)

    assert first == second == output.read_text(encoding="utf-8")
    assert "manual_1_to_5` (1/1 manually reviewed)" in first
    assert "Acronym Collision Failure" in first
    assert "Data-Type Hallucination" in first
