from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any

from scripts.validate_corpus import (
    MIN_CLASSES,
    MIN_PROPERTY_DOCUMENTS,
    MIN_SOURCE_DOCUMENTS,
    REQUIRED_PROPERTY_FIELDS,
    corpus_markdown_files,
    load_aliases,
    parse_property_documents,
    validate_corpus,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


def test_minimum_document_count() -> None:
    assert len(corpus_markdown_files(DATA_DIR)) >= MIN_SOURCE_DOCUMENTS


def test_minimum_property_count() -> None:
    documents = validate_corpus(DATA_DIR)
    assert len(documents) >= MIN_PROPERTY_DOCUMENTS


def test_minimum_class_count() -> None:
    documents = validate_corpus(DATA_DIR)
    assert len({document.class_name for document in documents}) >= MIN_CLASSES


def test_each_source_file_is_one_indexable_document() -> None:
    for path in corpus_markdown_files(DATA_DIR):
        assert len(parse_property_documents(path)) == 1, path


def test_property_entries_have_required_fields() -> None:
    documents = [
        doc for path in corpus_markdown_files(DATA_DIR) for doc in parse_property_documents(path)
    ]
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


def test_alias_unicode_normalization() -> None:
    aliases = load_aliases(DATA_DIR / "aliases.json")
    for alias in aliases:
        amharic = alias["amharic"]
        assert isinstance(amharic, str)
        assert unicodedata.normalize("NFC", amharic) == amharic


def test_known_acronym_pairs_present() -> None:
    aliases: list[dict[str, Any]] = list(load_aliases(DATA_DIR / "aliases.json"))
    acronym_pairs: dict[str, object] = {}
    for alias in aliases:
        english_aliases = alias["english_aliases"]
        if not isinstance(english_aliases, list):
            continue
        for english_alias in english_aliases:
            acronym_pairs[str(english_alias)] = alias["ontology_property"]

    assert acronym_pairs["IATA"] == "iataLocationIdentifier"
    assert acronym_pairs["ICAO"] == "icaoLocationIdentifier"
    assert acronym_pairs["UTC"] == "utcOffset"
