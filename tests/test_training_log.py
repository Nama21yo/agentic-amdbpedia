from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag.training_log import (
    TrainingExample,
    TrainingLogError,
    log_decision,
    read_examples,
    to_dspy_example,
)


def test_log_decision_writes_one_jsonl_row(tmp_path: Path) -> None:
    log_path = tmp_path / "training_examples.jsonl"

    log_decision(
        "Airport's ICAO code",
        ["icaoLocationIdentifier", "iataLocationIdentifier"],
        model_predicted="icaoLocationIdentifier",
        human_confirmed="icaoLocationIdentifier",
        run_id="run-1",
        log_path=log_path,
    )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["premise"] == "Airport's ICAO code"
    assert row["candidates"] == "icaoLocationIdentifier; iataLocationIdentifier"
    assert row["property_class"] == "icaoLocationIdentifier"
    assert row["was_correction"] is False
    assert row["run_id"] == "run-1"


def test_log_decision_flags_a_real_human_correction(tmp_path: Path) -> None:
    log_path = tmp_path / "training_examples.jsonl"

    example = log_decision(
        "Airport's IATA code",
        ["icaoLocationIdentifier", "iataLocationIdentifier"],
        model_predicted="icaoLocationIdentifier",
        human_confirmed="iataLocationIdentifier",
        log_path=log_path,
    )

    assert example.was_correction is True
    assert example.model_predicted == "icaoLocationIdentifier"
    assert example.property_class == "iataLocationIdentifier"


def test_log_decision_generates_a_run_id_when_not_given(tmp_path: Path) -> None:
    log_path = tmp_path / "training_examples.jsonl"

    example = log_decision(
        "premise", ["a"], model_predicted="a", human_confirmed="a", log_path=log_path
    )

    assert example.run_id  # non-empty, generated


def test_log_decision_appends_across_multiple_calls(tmp_path: Path) -> None:
    log_path = tmp_path / "training_examples.jsonl"

    log_decision("p1", ["a"], model_predicted="a", human_confirmed="a", log_path=log_path)
    log_decision("p2", ["b"], model_predicted="a", human_confirmed="b", log_path=log_path)

    examples = read_examples(log_path)
    assert [e.premise for e in examples] == ["p1", "p2"]


def test_log_decision_creates_parent_directories(tmp_path: Path) -> None:
    log_path = tmp_path / "nested" / "dir" / "training_examples.jsonl"

    log_decision("p", ["a"], model_predicted="a", human_confirmed="a", log_path=log_path)

    assert log_path.is_file()


def test_log_decision_rejects_empty_premise(tmp_path: Path) -> None:
    with pytest.raises(TrainingLogError, match="premise"):
        log_decision(
            "   ", ["a"], model_predicted="a", human_confirmed="a", log_path=tmp_path / "x.jsonl"
        )


def test_log_decision_rejects_empty_human_confirmed(tmp_path: Path) -> None:
    with pytest.raises(TrainingLogError, match="human_confirmed"):
        log_decision(
            "p", ["a"], model_predicted="a", human_confirmed="  ", log_path=tmp_path / "x.jsonl"
        )


def test_read_examples_returns_empty_list_for_missing_file(tmp_path: Path) -> None:
    assert read_examples(tmp_path / "does-not-exist.jsonl") == []


def test_read_examples_skips_malformed_lines_without_failing(tmp_path: Path) -> None:
    log_path = tmp_path / "training_examples.jsonl"
    log_decision("good row", ["a"], model_predicted="a", human_confirmed="a", log_path=log_path)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("not json at all\n")
        handle.write("\n")  # blank line, also skipped
        handle.write(json.dumps({"unexpected": "shape"}) + "\n")  # valid JSON, wrong fields

    examples = read_examples(log_path)

    assert len(examples) == 1
    assert examples[0].premise == "good row"


def test_to_dspy_example_round_trips_with_correct_field_names() -> None:
    example = TrainingExample(
        premise="Airport's ICAO code",
        candidates="icaoLocationIdentifier; iataLocationIdentifier",
        property_class="icaoLocationIdentifier",
        model_predicted="icaoLocationIdentifier",
        was_correction=False,
        run_id="run-1",
        decided_at="2026-01-01T00:00:00+00:00",
    )

    dspy_example = to_dspy_example(example)

    # Matches LLMIntegration/llm_raranker.py::load_data's own dspy.Example
    # construction exactly: same three field names, same input marking.
    assert dspy_example.premise == "Airport's ICAO code"
    assert dspy_example.candidates == "icaoLocationIdentifier; iataLocationIdentifier"
    assert dspy_example.property_class == "icaoLocationIdentifier"
    assert set(dspy_example.inputs().keys()) == {"premise", "candidates"}
