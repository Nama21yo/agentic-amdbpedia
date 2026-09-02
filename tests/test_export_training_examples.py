from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from rag.training_log import TrainingExample, log_decision
from scripts.export_training_examples import dedupe, export_training_examples


def _example(**overrides: object) -> TrainingExample:
    base = dict(
        premise="premise",
        candidates="a; b",
        property_class="a",
        model_predicted="a",
        was_correction=False,
        run_id="run-1",
        decided_at="2026-01-01T00:00:00+00:00",
    )
    base.update(overrides)
    return TrainingExample(**base)  # type: ignore[arg-type]


def test_dedupe_drops_repeated_decisions_keeping_the_first() -> None:
    first = _example(run_id="run-1", decided_at="2026-01-01T00:00:00+00:00")
    duplicate = _example(run_id="run-2", decided_at="2026-01-02T00:00:00+00:00")

    result = dedupe([first, duplicate])

    assert result == [first]


def test_dedupe_keeps_genuinely_different_decisions() -> None:
    a = _example(premise="premise A")
    b = _example(premise="premise B")

    assert dedupe([a, b]) == [a, b]


def test_dedupe_treats_different_model_predictions_as_distinct() -> None:
    a = _example(model_predicted="a")
    b = _example(model_predicted="b", property_class="b")

    assert dedupe([a, b]) == [a, b]


def test_export_writes_a_date_named_snapshot(tmp_path: Path) -> None:
    log_path = tmp_path / "training_examples.jsonl"
    export_dir = tmp_path / "training_exports"
    log_decision("p1", ["a", "b"], model_predicted="a", human_confirmed="a", log_path=log_path)

    destination = export_training_examples(
        log_path=log_path, export_dir=export_dir, snapshot_date=date(2026, 3, 14)
    )

    assert destination == export_dir / "2026-03-14.jsonl"
    assert destination.is_file()


def test_export_dedupes_before_writing(tmp_path: Path) -> None:
    log_path = tmp_path / "training_examples.jsonl"
    export_dir = tmp_path / "training_exports"
    log_decision("p1", ["a"], model_predicted="a", human_confirmed="a", log_path=log_path)
    log_decision("p1", ["a"], model_predicted="a", human_confirmed="a", log_path=log_path)
    log_decision("p2", ["a"], model_predicted="a", human_confirmed="a", log_path=log_path)

    destination = export_training_examples(log_path=log_path, export_dir=export_dir)

    lines = destination.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_export_handles_a_missing_log_by_writing_an_empty_file(tmp_path: Path) -> None:
    destination = export_training_examples(
        log_path=tmp_path / "does-not-exist.jsonl", export_dir=tmp_path / "training_exports"
    )

    assert destination.is_file()
    assert destination.read_text(encoding="utf-8") == ""


def test_export_output_is_valid_jsonl_matching_training_example_fields(tmp_path: Path) -> None:
    log_path = tmp_path / "training_examples.jsonl"
    export_dir = tmp_path / "training_exports"
    log_decision("p1", ["a", "b"], model_predicted="a", human_confirmed="b", log_path=log_path)

    destination = export_training_examples(log_path=log_path, export_dir=export_dir)

    rows = [json.loads(line) for line in destination.read_text(encoding="utf-8").splitlines()]
    assert rows == [
        {
            "premise": "p1",
            "candidates": "a; b",
            "property_class": "b",
            "model_predicted": "a",
            "was_correction": True,
            "run_id": rows[0]["run_id"],
            "decided_at": rows[0]["decided_at"],
        }
    ]


def test_export_output_loads_cleanly_via_datasets_load_dataset(tmp_path: Path) -> None:
    """The stated 13.2 acceptance criterion, exercised for real."""

    from datasets import load_dataset

    log_path = tmp_path / "training_examples.jsonl"
    export_dir = tmp_path / "training_exports"
    log_decision(
        "Airport's ICAO code",
        ["icaoLocationIdentifier", "iataLocationIdentifier"],
        model_predicted="icaoLocationIdentifier",
        human_confirmed="icaoLocationIdentifier",
        log_path=log_path,
    )
    log_decision(
        "Dam's opening date",
        ["openingDate"],
        model_predicted="foundingDate",
        human_confirmed="openingDate",
        log_path=log_path,
    )

    destination = export_training_examples(log_path=log_path, export_dir=export_dir)
    dataset = load_dataset("json", data_files=str(destination), split="train")

    assert len(dataset) == 2
    assert set(dataset.column_names) == {
        "premise",
        "candidates",
        "property_class",
        "model_predicted",
        "was_correction",
        "run_id",
        "decided_at",
    }
    assert dataset[0]["premise"] == "Airport's ICAO code"
    assert dataset[1]["was_correction"] is True
