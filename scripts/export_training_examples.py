"""Export a versioned, deduped snapshot of the training-example log.

Reads `data/training_examples.jsonl` (`rag.training_log.read_examples`),
drops exact-duplicate rows, and writes `data/training_exports/<date>.jsonl`
— a plain JSON-Lines file safe to hand to
`datasets.load_dataset("json", data_files=...)` directly (refs
implementation.md 13.2).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logging_config import log_event
from rag.training_log import DEFAULT_LOG_PATH, TrainingExample, read_examples

LOGGER = logging.getLogger("dbpedia_mapping_assistant.export_training_examples")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT_DIR = PROJECT_ROOT / "data" / "training_exports"


def dedupe(examples: list[TrainingExample]) -> list[TrainingExample]:
    """Drop exact-duplicate rows, keeping the first occurrence.

    A duplicate is the same (premise, candidates, property_class,
    model_predicted) — the same review outcome logged more than once, e.g.
    by a retried request. `decided_at`/`run_id` intentionally don't factor
    into the key, since those always differ even for a genuine duplicate
    decision.
    """

    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[TrainingExample] = []
    for example in examples:
        key = (
            example.premise,
            example.candidates,
            example.property_class,
            example.model_predicted,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(example)
    return deduped


def export_training_examples(
    *,
    log_path: Path = DEFAULT_LOG_PATH,
    export_dir: Path = DEFAULT_EXPORT_DIR,
    snapshot_date: date | None = None,
) -> Path:
    """Read, dedupe, and write a versioned snapshot. Returns the written path.

    A missing or empty log still writes a valid (empty) JSONL file rather
    than raising — a downstream `datasets.load_dataset` call should see a
    clear "0 rows" result, not a missing-file crash.
    """

    examples = dedupe(read_examples(log_path))

    resolved_date = snapshot_date or datetime.now(UTC).date()
    export_dir.mkdir(parents=True, exist_ok=True)
    destination = export_dir / f"{resolved_date.isoformat()}.jsonl"

    with destination.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(asdict(example), ensure_ascii=False) + "\n")

    log_event(LOGGER, "export.completed", example_count=len(examples), destination=str(destination))
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-path", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    args = parser.parse_args(argv)

    destination = export_training_examples(log_path=args.log_path, export_dir=args.export_dir)
    print(f"Wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
