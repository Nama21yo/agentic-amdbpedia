from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_readme_required_sections_and_domain_language() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    required_fragments = [
        "## Domain",
        "## Architecture",
        "## Current Milestone",
        "cross-lingual semantic web engineering",
        "Amharic Wikipedia",
        "English DBpedia ontology",
        "Retrieval-augmented generation is required",
        "MCP tools are required",
        "deterministic",
    ]
    missing = [fragment for fragment in required_fragments if fragment not in readme]
    assert missing == []
