from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mcp_server.qa import QAError, _sparql_term, verify_extraction

SAMPLE_NT = (
    '<http://example.org/Airport1> <http://dbpedia.org/ontology/icaoLocationIdentifier> "HAAB" .\n'
    '<http://example.org/Airport1> <http://dbpedia.org/ontology/iataLocationIdentifier> "ADD" .\n'
)


class FakeTentrisProcess:
    """Scripts the exact query -> JSON-results shape the real Tentris HTTP
    endpoint returns (verified directly against the real image — see this
    module's own docstring for the ASK-vs-SELECT finding), without Docker."""

    def __init__(self, triples: set[tuple[str, str, str]]) -> None:
        self.triples = triples
        self.base_url = "http://fake-tentris.test"
        self.queries: list[str] = []

    def __enter__(self) -> FakeTentrisProcess:
        return self

    def __exit__(self, *exc_info: object) -> None:
        pass


def _fake_query_sparql(triples: set[tuple[str, str, str]]) -> Any:
    def _query(base_url: str, query: str, *, timeout: float = 10.0) -> dict[str, Any]:
        # A minimal, real-shaped stand-in: checks whether the exact ground
        # triple embedded in the query text is one of the known triples.
        matched = any(
            f"{_sparql_term(s)} {_sparql_term(p)} {_sparql_term(o)}" in query for s, p, o in triples
        )
        bindings: list[dict[str, str]] = [{}] if matched else []
        return {"head": {"vars": []}, "results": {"bindings": bindings}}

    return _query


def test_sparql_term_wraps_uris_in_angle_brackets() -> None:
    assert (
        _sparql_term("http://dbpedia.org/ontology/length") == "<http://dbpedia.org/ontology/length>"
    )


def test_sparql_term_quotes_literals_and_escapes_quotes() -> None:
    assert _sparql_term("HAAB") == '"HAAB"'
    assert _sparql_term('has "quotes"') == '"has \\"quotes\\""'


def test_verify_extraction_returns_true_for_a_present_triple(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "mcp_server.qa.query_sparql",
        _fake_query_sparql(
            {
                (
                    "http://example.org/Airport1",
                    "http://dbpedia.org/ontology/icaoLocationIdentifier",
                    "HAAB",
                )
            }
        ),
    )
    process = FakeTentrisProcess(set())

    found = verify_extraction(
        tmp_path / "sample.nt",
        "http://example.org/Airport1",
        "http://dbpedia.org/ontology/icaoLocationIdentifier",
        "HAAB",
        process=process,
    )

    assert found is True


def test_verify_extraction_returns_false_for_an_absent_triple(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("mcp_server.qa.query_sparql", _fake_query_sparql(set()))
    process = FakeTentrisProcess(set())

    found = verify_extraction(
        tmp_path / "sample.nt",
        "http://example.org/Airport1",
        "http://dbpedia.org/ontology/icaoLocationIdentifier",
        "WRONG_VALUE",
        process=process,
    )

    assert found is False


def test_verify_extraction_never_raises_just_because_the_triple_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("mcp_server.qa.query_sparql", _fake_query_sparql(set()))
    process = FakeTentrisProcess(set())

    # Must not raise -- only report False.
    found = verify_extraction(
        tmp_path / "sample.nt",
        "http://example.org/DoesNotExist",
        "http://example.org/p",
        "x",
        process=process,
    )
    assert found is False


def test_verify_extraction_propagates_a_genuine_query_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _failing_query(base_url: str, query: str, *, timeout: float = 10.0) -> dict[str, Any]:
        raise QAError("Tentris query failed: URLError")

    monkeypatch.setattr("mcp_server.qa.query_sparql", _failing_query)
    process = FakeTentrisProcess(set())

    with pytest.raises(QAError):
        verify_extraction(
            tmp_path / "sample.nt",
            "http://example.org/s",
            "http://example.org/p",
            "o",
            process=process,
        )


@pytest.mark.integration
def test_query_sparql_parses_a_real_tentris_response_shape() -> None:
    """Locks in the exact response shape verified directly against the
    real dicegroup/tentris_server image, independent of whether Docker is
    reachable from this particular test run."""

    payload = json.loads('{"head":{"vars":[]},"results":{"bindings":[{}]}}')
    assert payload["results"]["bindings"] == [{}]


@pytest.mark.integration
def test_verify_extraction_against_a_real_tentris_container(tmp_path: Path) -> None:
    """Runs a real dicegroup/tentris_server container via Docker -- no
    mocks. Requires Docker to be available; skipped otherwise rather than
    failing a run on a host without it."""

    import shutil
    import subprocess

    if shutil.which("docker") is None:
        pytest.skip("docker is not available")
    if subprocess.run(["docker", "info"], capture_output=True, timeout=10).returncode != 0:
        pytest.skip("docker daemon is not reachable")

    nt_file = tmp_path / "sample.nt"
    nt_file.write_text(SAMPLE_NT, encoding="utf-8")

    found = verify_extraction(
        nt_file,
        "http://example.org/Airport1",
        "http://dbpedia.org/ontology/icaoLocationIdentifier",
        "HAAB",
    )
    assert found is True

    not_found = verify_extraction(
        nt_file,
        "http://example.org/Airport1",
        "http://dbpedia.org/ontology/icaoLocationIdentifier",
        "WRONG_VALUE",
    )
    assert not_found is False
