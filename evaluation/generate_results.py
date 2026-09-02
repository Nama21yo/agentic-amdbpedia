"""Generate evaluation/results.md from metrics JSON artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRECISION_PATH = PROJECT_ROOT / "evaluation" / "latest_metrics.json"
DEFAULT_RELEVANCE_PATH = PROJECT_ROOT / "evaluation" / "relevance_metrics.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "evaluation" / "results.md"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"status": "missing"}


def generate_results_markdown(
    *,
    precision_path: Path = DEFAULT_PRECISION_PATH,
    relevance_path: Path = DEFAULT_RELEVANCE_PATH,
) -> str:
    precision = load_json(precision_path)
    relevance = load_json(relevance_path)
    lines = [
        "# Evaluation Results",
        "",
        "## Metrics",
        "",
        "| Metric | Value | Queries |",
        "|---|---:|---:|",
        (
            f"| Hits@3 | {precision.get('hits_at_3', 'n/a')} | "
            f"{precision.get('evaluated_queries', 'n/a')} |"
        ),
        (
            f"| Precision@1 | {precision.get('precision_at_1', 'n/a')} | "
            f"{precision.get('evaluated_queries', 'n/a')} |"
        ),
        (
            f"| Mean answer relevance | {relevance.get('mean_relevance', 'n/a')} | "
            f"{relevance.get('evaluated_queries', 'n/a')} |"
        ),
        "",
        (
            f"Answer relevance method: `{relevance.get('review_method', 'unknown')}` "
            f"({relevance.get('manual_reviews', 0)}/"
            f"{relevance.get('evaluated_queries', 'n/a')} manually reviewed)."
        ),
        "",
        "## Retrieval Detail",
        "",
        "| Query ID | Expected | Top Properties | Hit |",
        "|---|---|---|---|",
    ]
    for item in precision.get("breakdown", []):
        top = ", ".join(item.get("top_properties", []))
        lines.append(
            f"| {item['id']} | {item.get('expected_property')} | {top} | {item.get('hit')} |"
        )

    lines.extend(
        [
            "",
            "## Answer Relevance Detail",
            "",
            "| Query ID | Score | Source | Rationale |",
            "|---|---:|---|---|",
        ]
    )
    for item in relevance.get("breakdown", []):
        lines.append(
            f"| {item['id']} | {item.get('score')} | {item.get('source')} | "
            f"{item.get('rationale')} |"
        )

    lines.extend(
        [
            "",
            "## Documented Failure Cases and Mitigations",
            "",
            "1. Acronym Collision Failure: Amharic fields mixed with Latin acronyms such as "
            "`አይካኦ_ኮድ ICAO` can be misranked by semantic-only retrieval. Mitigation: sparse "
            "alias keyword folding plus in-process RRF hybrid search. Proof test: "
            "`tests/integration/test_retrieval_precision.py::test_acronym_collision_sparse_channel_rescues_icao`.",
            "",
            "2. Data-Type Hallucination: LLM-authored XML can invent properties or malformed "
            "syntax. Mitigation: the agent must call deterministic `generate_mapping_syntax`, "
            "which uses `ElementTree`, and the prompt forbids raw XML. Proof tests: "
            "`tests/test_mcp_server.py::test_generate_mapping_syntax_escapes_injection_attempt` "
            "and `tests/test_agent_guardrails.py::test_agent_never_emits_raw_xml_not_from_tool`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_results(
    *,
    precision_path: Path = DEFAULT_PRECISION_PATH,
    relevance_path: Path = DEFAULT_RELEVANCE_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> str:
    markdown = generate_results_markdown(
        precision_path=precision_path, relevance_path=relevance_path
    )
    output_path.write_text(markdown, encoding="utf-8")
    return markdown


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--precision", type=Path, default=DEFAULT_PRECISION_PATH)
    parser.add_argument("--relevance", type=Path, default=DEFAULT_RELEVANCE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()
    print(
        write_results(
            precision_path=args.precision, relevance_path=args.relevance, output_path=args.output
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
