from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.refresh_wiki_cache import (
    DEFAULT_EXPORT_BATCH_SIZE,
    WikiFetchError,
    export_titles,
    list_namespace_titles,
    refresh_mappings,
    refresh_ontology,
)

MEDIAWIKI_NS = "http://www.mediawiki.org/xml/export-0.11/"


def _allpages_response(titles: list[str], *, apcontinue: str | None = None) -> bytes:
    payload: dict[str, Any] = {
        "batchcomplete": "",
        "query": {
            "allpages": [{"pageid": i, "ns": 390, "title": title} for i, title in enumerate(titles)]
        },
    }
    if apcontinue:
        payload["continue"] = {"apcontinue": apcontinue, "continue": "-||"}
    return json.dumps(payload).encode("utf-8")


def _export_response(titles: list[str]) -> bytes:
    # Mirrors the real live response shape (verified against mappings.dbpedia.org
    # directly), trimmed to the fields rag/ontology.py's parsers actually read.
    pages = "".join(
        f"<page><title>{title}</title><ns>390</ns><id>{i}</id>"
        f"<revision><id>{100 + i}</id><timestamp>2026-01-01T00:00:00Z</timestamp>"
        f'<text bytes="10" xml:space="preserve">'
        f"{{{{TemplateMapping | mapToClass = Type | mappings = "
        f"{{{{PropertyMapping | templateProperty = field{i} | ontologyProperty = prop{i} }}}} }}}}"
        f"</text></revision></page>"
        for i, title in enumerate(titles)
    )
    return f'<mediawiki xmlns="{MEDIAWIKI_NS}">{pages}</mediawiki>'.encode()


class FakeFetcher:
    """Records every call and serves scripted responses in order, mirroring
    the shape of real allpages/export request/response pairs."""

    def __init__(self, responses: list[bytes]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str, params: dict[str, str]) -> bytes:
        self.calls.append((url, dict(params)))
        if not self.responses:
            raise AssertionError("FakeFetcher ran out of scripted responses")
        return self.responses.pop(0)


class FailingFetcher:
    def __call__(self, url: str, params: dict[str, str]) -> bytes:
        raise WikiFetchError("simulated network failure")


def test_list_namespace_titles_single_page() -> None:
    fetcher = FakeFetcher([_allpages_response(["Mapping am:Citation", "Mapping am:Flag"])])

    titles = list_namespace_titles("https://example.test", 390, fetch=fetcher)

    assert titles == ["Mapping am:Citation", "Mapping am:Flag"]
    assert len(fetcher.calls) == 1
    assert fetcher.calls[0][1]["apnamespace"] == "390"


def test_list_namespace_titles_follows_apcontinue_pagination() -> None:
    fetcher = FakeFetcher(
        [
            _allpages_response(["Page A", "Page B"], apcontinue="Page C"),
            _allpages_response(["Page C"]),
        ]
    )

    titles = list_namespace_titles("https://example.test", 200, fetch=fetcher)

    assert titles == ["Page A", "Page B", "Page C"]
    assert len(fetcher.calls) == 2
    assert "apcontinue" not in fetcher.calls[0][1]
    assert fetcher.calls[1][1]["apcontinue"] == "Page C"


def test_list_namespace_titles_raises_on_api_error_payload() -> None:
    error_body = json.dumps({"error": {"code": "toomanyvalues", "info": "too many"}}).encode()
    fetcher = FakeFetcher([error_body])

    with pytest.raises(WikiFetchError, match="toomanyvalues"):
        list_namespace_titles("https://example.test", 390, fetch=fetcher)


def test_list_namespace_titles_raises_on_transport_failure() -> None:
    with pytest.raises(WikiFetchError, match="simulated network failure"):
        list_namespace_titles("https://example.test", 390, fetch=FailingFetcher())


def test_export_titles_batches_under_the_live_api_limit() -> None:
    titles = [f"Mapping am:Page{i}" for i in range(DEFAULT_EXPORT_BATCH_SIZE + 5)]
    fetcher = FakeFetcher(
        [
            _export_response(titles[:DEFAULT_EXPORT_BATCH_SIZE]),
            _export_response(titles[DEFAULT_EXPORT_BATCH_SIZE:]),
        ]
    )

    pages = export_titles("https://example.test", titles, fetch=fetcher)

    assert len(pages) == len(titles)
    assert len(fetcher.calls) == 2
    assert fetcher.calls[0][1]["titles"].count("|") == DEFAULT_EXPORT_BATCH_SIZE - 1


def test_export_titles_raises_on_malformed_xml() -> None:
    fetcher = FakeFetcher([b"not xml at all"])

    with pytest.raises(WikiFetchError, match="Could not export batch"):
        export_titles("https://example.test", ["Mapping am:Citation"], fetch=fetcher)


def test_refresh_mappings_writes_the_merged_export(tmp_path: Path) -> None:
    destination = tmp_path / "mapping_am.xml"
    titles = ["Mapping am:Citation", "Mapping am:Flag"]
    fetcher = FakeFetcher([_allpages_response(titles), _export_response(titles)])

    count = refresh_mappings(
        base_url="https://example.test", destination=destination, fetch=fetcher
    )

    assert count == 2
    assert destination.is_file()
    written = destination.read_text(encoding="utf-8")
    assert "Mapping am:Citation" in written
    assert "Mapping am:Flag" in written


def test_refresh_mappings_round_trips_through_the_real_parser(tmp_path: Path) -> None:
    from rag.ontology import AmharicMappingIndex

    destination = tmp_path / "mapping_am.xml"
    titles = ["Mapping am:Citation"]
    fetcher = FakeFetcher([_allpages_response(titles), _export_response(titles)])

    refresh_mappings(base_url="https://example.test", destination=destination, fetch=fetcher)
    index = AmharicMappingIndex.from_mapping_xml(destination)

    assert index.lookup("field0") is not None
    assert index.lookup("field0").ontology_property == "prop0"  # type: ignore[union-attr]


def test_refresh_ontology_leaves_existing_cache_untouched_on_failure(tmp_path: Path) -> None:
    destination = tmp_path / "ontology.xml"
    destination.write_text(
        "<mediawiki><page>previous good cache</page></mediawiki>", encoding="utf-8"
    )
    before = destination.read_bytes()

    count = refresh_ontology(
        base_url="https://example.test", destination=destination, fetch=FailingFetcher()
    )

    assert count == 0
    assert destination.read_bytes() == before


def test_refresh_mappings_leaves_no_file_behind_on_first_ever_failure(tmp_path: Path) -> None:
    destination = tmp_path / "mapping_am.xml"

    count = refresh_mappings(
        base_url="https://example.test", destination=destination, fetch=FailingFetcher()
    )

    assert count == 0
    assert not destination.exists()


def test_refresh_ontology_pulls_both_class_and_property_namespaces(tmp_path: Path) -> None:
    destination = tmp_path / "ontology.xml"
    class_titles = ["OntologyClass:Airport"]
    property_titles = ["OntologyProperty:length"]
    fetcher = FakeFetcher(
        [
            _allpages_response(class_titles),
            _allpages_response(property_titles),
            _export_response(class_titles + property_titles),
        ]
    )

    count = refresh_ontology(
        base_url="https://example.test", destination=destination, fetch=fetcher
    )

    assert count == 2
    namespaces_requested = [
        call[1]["apnamespace"] for call in fetcher.calls if "apnamespace" in call[1]
    ]
    assert namespaces_requested == ["200", "202"]
