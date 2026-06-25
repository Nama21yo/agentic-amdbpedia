from __future__ import annotations

from pathlib import Path

from scripts.validate_corpus import (
    REQUIRED_PROPERTY_FIELDS,
    class_markdown_files,
    load_aliases,
    parse_property_documents,
    validate_corpus,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


def test_minimum_document_count() -> None:
    assert len(class_markdown_files(DATA_DIR)) >= 7


def test_minimum_property_count() -> None:
    documents = validate_corpus(DATA_DIR)
    assert len(documents) >= 20


def test_property_entries_have_required_fields() -> None:
    documents = [doc for path in class_markdown_files(DATA_DIR) for doc in parse_property_documents(path)]
    assert documents
    for document in documents:
        missing = [field for field in REQUIRED_PROPERTY_FIELDS if not document.fields.get(field)]
        assert missing == [], f"{document.path}:{document.line_number} missing {missing}"


def test_alias_dictionary_has_acronym_collision_case() -> None:
    aliases = load_aliases(DATA_DIR / "aliases.json")
    matching_aliases = []
    for alias in aliases:
        english_aliases = alias["english_aliases"]
        if not isinstance(english_aliases, list):
            continue
        if (
            alias["amharic"] == "አይካኦ_ኮድ"
            and alias["ontology_property"] == "icaoLocationIdentifier"
            and "ICAO" in english_aliases
        ):
            matching_aliases.append(alias)

    assert matching_aliases
