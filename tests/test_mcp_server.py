from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from mcp_server.server import (
    MappingEntry,
    MappingPayload,
    StartupError,
    find_semantic_match_impl,
    generate_mapping_syntax_impl,
    get_benchmarks_impl,
    validate_startup,
)
from rag.retrieval import NoMatchFound, SearchResult


def test_startup_fails_loudly_without_groq_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    # Settings() also reads the project's own (gitignored, real-secret) .env
    # file relative to CWD; chdir somewhere without one so a missing
    # GROQ_API_KEY actually stays missing for this test.
    monkeypatch.chdir(tmp_path)

    with pytest.raises(StartupError, match="Missing or invalid server configuration"):
        validate_startup()


def test_startup_succeeds_with_valid_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_placeholder")

    validate_startup()  # must not raise


def test_startup_checks_can_be_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    validate_startup(skip_checks=True)  # must not raise despite missing config


def test_find_semantic_match_rejects_empty_input() -> None:
    called = False

    def search_func(*_: Any, **__: Any) -> list[Any]:
        nonlocal called
        called = True
        return []

    payload = json.loads(find_semantic_match_impl("   ", search_func=search_func))

    assert payload["status"] == "error"
    assert payload["error_type"] == "validation"
    assert called is False


def test_find_semantic_match_handles_retrieval_outage() -> None:
    def search_func(*_: Any, **__: Any) -> list[Any]:
        raise TimeoutError("embedding model timeout")

    payload = json.loads(find_semantic_match_impl("አይካኦ_ኮድ", search_func=search_func))

    assert payload["status"] == "error"
    assert payload["error_type"] == "retrieval_unavailable"


def test_find_semantic_match_happy_path() -> None:
    def search_func(*_: Any, **__: Any) -> list[Any]:
        return [
            SearchResult(
                property="icaoLocationIdentifier",
                ontology_class="Airport",
                score=0.9,
                payload={"xsd_type": "xsd:string"},
            )
        ]

    payload = json.loads(
        find_semantic_match_impl("አይካኦ_ኮድ", target_class="Airport", search_func=search_func)
    )

    assert payload["status"] == "ok"
    assert payload["matches"][0]["property"] == "icaoLocationIdentifier"


def test_find_semantic_match_no_match() -> None:
    payload = json.loads(
        find_semantic_match_impl(
            "nonsense", search_func=lambda *_args, **_kw: [NoMatchFound("nonsense")]
        )
    )

    assert payload["status"] == "no_match"
    assert payload["matches"] == []
    assert payload["correlation_id"]


def test_generate_mapping_syntax_escapes_injection_attempt() -> None:
    xml = generate_mapping_syntax_impl(
        MappingPayload(
            domain_class="Airport",
            mappings=[
                MappingEntry(
                    templateProperty='"><script>',
                    ontologyProperty="icaoLocationIdentifier",
                )
            ],
        )
    )

    root = ET.fromstring(xml)

    template_property = root.find("./PropertyMapping/templateProperty")
    assert template_property is not None
    assert template_property.text == '"><script>'
    assert len(root.findall(".//script")) == 0


def test_generate_mapping_syntax_rejects_invalid_class_name() -> None:
    with pytest.raises(ValidationError):
        MappingPayload(
            domain_class="airport class",
            mappings=[MappingEntry(templateProperty="x", ontologyProperty="y")],
        )


def test_generate_mapping_syntax_snapshot() -> None:
    xml = generate_mapping_syntax_impl(
        MappingPayload(
            domain_class="Airport",
            mappings=[
                MappingEntry(
                    templateProperty="አይካኦ_ኮድ",
                    ontologyProperty="icaoLocationIdentifier",
                )
            ],
        )
    )

    assert xml == (
        '<TemplateMapping mapToClass="dbo:Airport">\n'
        "  <PropertyMapping>\n"
        "    <templateProperty>አይካኦ_ኮድ</templateProperty>\n"
        "    <ontologyProperty>icaoLocationIdentifier</ontologyProperty>\n"
        "  </PropertyMapping>\n"
        "</TemplateMapping>"
    )


@given(
    template_property=st.text(
        alphabet=st.characters(blacklist_categories=("Cc", "Cs")), min_size=1, max_size=40
    ),
    ontology_property=st.text(
        alphabet=st.characters(blacklist_categories=("Cc", "Cs")), min_size=1, max_size=40
    ),
)
@settings(max_examples=50)
def test_generate_mapping_syntax_always_produces_parseable_xml(
    template_property: str, ontology_property: str
) -> None:
    xml = generate_mapping_syntax_impl(
        MappingPayload(
            domain_class="Airport",
            mappings=[
                MappingEntry(
                    templateProperty=template_property,
                    ontologyProperty=ontology_property,
                )
            ],
        )
    )

    ET.fromstring(xml)


def test_benchmarks_resource_no_data_state(tmp_path: Path) -> None:
    payload = json.loads(get_benchmarks_impl(tmp_path / "missing.json"))

    assert payload == {"status": "no_evaluation_run_yet"}


def test_benchmarks_resource_reflects_latest_eval_run(tmp_path: Path) -> None:
    metrics = tmp_path / "latest_metrics.json"
    metrics.write_text('{"status":"ok","hits_at_3":0.9}', encoding="utf-8")

    assert json.loads(get_benchmarks_impl(metrics)) == {"status": "ok", "hits_at_3": 0.9}


def test_no_dynamic_code_execution_in_tool_layer() -> None:
    server_dir = Path(__file__).resolve().parents[1] / "mcp_server"
    source = "\n".join(path.read_text(encoding="utf-8") for path in server_dir.glob("*.py"))

    assert re.search(r"\b(eval|exec)\s*\(", source) is None
