"""Validate the Milestone 1 DBpedia ontology corpus."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

REQUIRED_PROPERTY_FIELDS = (
    "propertyName",
    "xsd type",
    "description",
    "amharic aliases",
    "mapping convention",
    "source_url",
)
MIN_CLASS_FILES = 9
MIN_PROPERTY_DOCUMENTS = 35


@dataclass(frozen=True)
class PropertyDocument:
    """A single DBpedia ontology property entry parsed from one class markdown file."""

    class_name: str
    heading: str
    fields: dict[str, str]
    line_number: int
    path: Path


class CorpusValidationError(ValueError):
    """Raised when a corpus document violates the milestone format."""


def class_markdown_files(corpus_dir: Path) -> list[Path]:
    return sorted(path for path in corpus_dir.glob("*.md") if path.is_file())


def parse_property_documents(path: Path) -> list[PropertyDocument]:
    class_name = path.stem
    entries: list[PropertyDocument] = []
    current_heading: str | None = None
    current_line = 0
    fields: dict[str, str] = {}

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if line.startswith("### "):
            if current_heading is not None:
                entries.append(
                    PropertyDocument(class_name, current_heading, fields, current_line, path)
                )
            current_heading = line.removeprefix("### ").strip()
            current_line = line_number
            fields = {}
            continue

        if current_heading is None or not line.startswith("- ") or ":" not in line:
            continue

        key, value = line[2:].split(":", 1)
        fields[key.strip()] = value.strip()

    if current_heading is not None:
        entries.append(PropertyDocument(class_name, current_heading, fields, current_line, path))

    return entries


def load_aliases(path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorpusValidationError(f"{path}:{exc.lineno}: aliases.json is invalid JSON") from exc

    aliases = payload.get("aliases")
    if not isinstance(aliases, list) or not aliases:
        raise CorpusValidationError(f"{path}:1: aliases.json must contain a non-empty aliases list")
    return aliases


def validate_property_documents(documents: Iterable[PropertyDocument]) -> None:
    for document in documents:
        for field in REQUIRED_PROPERTY_FIELDS:
            value = document.fields.get(field)
            if not value:
                raise CorpusValidationError(
                    f"{document.path}:{document.line_number}: property "
                    f"{document.heading!r} missing required field {field!r}"
                )

        property_name = document.fields["propertyName"]
        if property_name != document.heading:
            raise CorpusValidationError(
                f"{document.path}:{document.line_number}: heading {document.heading!r} "
                f"does not match propertyName {property_name!r}"
            )


def validate_aliases(
    aliases: list[dict[str, object]], property_names: set[str], aliases_path: Path
) -> None:
    seen_icao_case = False
    for index, alias in enumerate(aliases, start=1):
        for field in ("class", "amharic", "english_aliases", "ontology_property", "notes"):
            if not alias.get(field):
                raise CorpusValidationError(
                    f"{aliases_path}:{index}: alias row missing required field {field!r}"
                )

        ontology_property = alias["ontology_property"]
        if not isinstance(ontology_property, str) or ontology_property not in property_names:
            raise CorpusValidationError(
                f"{aliases_path}:{index}: ontology_property {ontology_property!r} "
                "does not match any corpus propertyName"
            )

        english_aliases = alias["english_aliases"]
        if not isinstance(english_aliases, list) or not all(
            isinstance(item, str) and item.strip() for item in english_aliases
        ):
            raise CorpusValidationError(
                f"{aliases_path}:{index}: english_aliases must be a non-empty string list"
            )

        if alias.get("amharic") == "አይካኦ_ኮድ" and ontology_property == "icaoLocationIdentifier":
            seen_icao_case = True

    if not seen_icao_case:
        raise CorpusValidationError(
            f"{aliases_path}:1: missing required ICAO acronym-collision alias row"
        )


def validate_corpus(corpus_dir: Path) -> list[PropertyDocument]:
    markdown_files = class_markdown_files(corpus_dir)
    if len(markdown_files) < MIN_CLASS_FILES:
        raise CorpusValidationError(
            f"{corpus_dir}:1: expected at least {MIN_CLASS_FILES} class markdown files, "
            f"found {len(markdown_files)}"
        )

    documents = [document for path in markdown_files for document in parse_property_documents(path)]
    if len(documents) < MIN_PROPERTY_DOCUMENTS:
        raise CorpusValidationError(
            f"{corpus_dir}:1: expected at least {MIN_PROPERTY_DOCUMENTS} property documents, "
            f"found {len(documents)}"
        )

    validate_property_documents(documents)
    aliases_path = corpus_dir / "aliases.json"
    validate_aliases(
        load_aliases(aliases_path), {doc.fields["propertyName"] for doc in documents}, aliases_path
    )
    return documents


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus_dir", nargs="?", default="data", type=Path)
    args = parser.parse_args(argv)

    try:
        documents = validate_corpus(args.corpus_dir)
    except CorpusValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    class_count = len(class_markdown_files(args.corpus_dir))
    print(f"Validated {class_count} classes and {len(documents)} properties")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
