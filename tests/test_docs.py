from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_readme_required_sections_and_domain_language() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    required_fragments = [
        "## Domain",
        "## Architecture",
        "## Requirements Traceability",
        "## Future Work",
        "cross-lingual semantic web engineering",
        "Amharic Wikipedia",
        "English DBpedia ontology",
        "Retrieval-augmented generation is required",
        "MCP tools are required",
        "deterministic",
    ]
    missing = [fragment for fragment in required_fragments if fragment not in readme]
    assert missing == []


def test_demo_transcripts_cover_required_paths() -> None:
    demo = (PROJECT_ROOT / "examples" / "demo.md").read_text(encoding="utf-8")
    required_fragments = [
        "Successful Airport Mapping",
        "Low-Confidence No-Match Refusal",
        "Prompt-Injection Guardrail",
        "find_semantic_match",
        "generate_mapping_syntax",
        "Rejected: prompt-injection attempt detected.",
    ]
    missing = [fragment for fragment in required_fragments if fragment not in demo]
    assert missing == []


def test_traceability_matrix_entries_reference_existing_tests() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    references = re.findall(r"`(tests/[^`]+::test_[^`]+)`", readme)

    assert references
    for reference in references:
        path_text, test_name = reference.split("::", 1)
        path = PROJECT_ROOT / path_text
        assert path.exists(), reference
        source = path.read_text(encoding="utf-8")
        assert f"def {test_name}" in source or f"async def {test_name}" in source, reference
