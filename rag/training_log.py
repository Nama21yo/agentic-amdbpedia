"""Append-only training-example log.

Every terminal human review decision (approve, reject, correct) is logged
as one JSONL row shaped exactly like `LLMIntegration/llm_raranker.py`'s
`load_data()` already constructs its `dspy.Example`s — `premise`,
`candidates` ("; "-joined), `property_class` — plus `model_predicted`,
`was_correction`, `run_id`, and `decided_at` so real model-vs-human
disagreements are captured for later fine-tuning (refs implementation.md
13.1). A local JSONL file for now (`data/training_examples.jsonl`), not
Postgres — this has to work before M14's review queue exists at all.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from logging_config import log_event

if TYPE_CHECKING:
    import dspy

LOGGER = logging.getLogger("dbpedia_mapping_assistant.training_log")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_PATH = PROJECT_ROOT / "data" / "training_examples.jsonl"
CANDIDATE_SEPARATOR = "; "  # matches LLMIntegration/llm_raranker.py::load_data exactly


class TrainingLogError(ValueError):
    """Raised when a logged row can't be reconstructed as a TrainingExample."""


@dataclass(frozen=True)
class TrainingExample:
    """One row. `premise`/`candidates`/`property_class` match the field
    names `dspy.Example(...).with_inputs("premise", "candidates")` expects
    exactly; the rest is provenance for training-data curation."""

    premise: str
    candidates: str
    property_class: str
    model_predicted: str
    was_correction: bool
    run_id: str
    decided_at: str  # ISO 8601 UTC


def log_decision(
    premise: str,
    candidates: list[str],
    *,
    model_predicted: str,
    human_confirmed: str,
    run_id: str | None = None,
    log_path: Path = DEFAULT_LOG_PATH,
) -> TrainingExample:
    """Append one terminal review decision to the training log.

    `candidates` is the retriever/predictor's own ordered candidate list —
    exactly what was actually shown to the reviewer — joined with the same
    "; " separator LLMIntegration's `load_data()` uses, so a logged row
    round-trips into a `dspy.Example` with no reformatting.
    """

    if not premise.strip():
        raise TrainingLogError("premise must not be empty")
    if not human_confirmed.strip():
        raise TrainingLogError("human_confirmed must not be empty")

    example = TrainingExample(
        premise=premise,
        candidates=CANDIDATE_SEPARATOR.join(candidates),
        property_class=human_confirmed,
        model_predicted=model_predicted,
        was_correction=model_predicted != human_confirmed,
        run_id=run_id or str(uuid.uuid4()),
        decided_at=datetime.now(UTC).isoformat(),
    )

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(example), ensure_ascii=False) + "\n")

    log_event(
        LOGGER,
        "training_log.decision_logged",
        was_correction=example.was_correction,
        run_id=example.run_id,
    )
    return example


def read_examples(log_path: Path = DEFAULT_LOG_PATH) -> list[TrainingExample]:
    """Read every logged example. A malformed line is skipped and logged,
    not fatal — one bad row must never block reading the rest of an
    append-only log written by many separate processes over time."""

    if not log_path.is_file():
        return []

    examples: list[TrainingExample] = []
    for line_number, raw_line in enumerate(
        log_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line:
            continue
        try:
            row: Any = json.loads(line)
            examples.append(TrainingExample(**row))
        except (json.JSONDecodeError, TypeError) as exc:
            log_event(
                LOGGER, "training_log.skip_malformed_row", line_number=line_number, error=str(exc)
            )

    return examples


def to_dspy_example(example: TrainingExample) -> dspy.Example:
    """Construct the exact `dspy.Example(...).with_inputs("premise",
    "candidates")` shape `LLMIntegration/llm_raranker.py::load_data` uses,
    so a logged correction round-trips into DSPy training data unchanged."""

    import dspy

    return dspy.Example(
        premise=example.premise,
        candidates=example.candidates,
        property_class=example.property_class,
    ).with_inputs("premise", "candidates")
