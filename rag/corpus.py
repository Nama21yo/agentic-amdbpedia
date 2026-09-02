"""Builds the in-process retrieval corpus over the real DBpedia ontology.

Merges three layers, broadest to most specific (refs implementation.md M10):

1. `DbpediaOntologyCatalog` — the real ~2,942-property ontology, the base
   corpus (replaces the old 36-document hand-authored `data/*.md` corpus).
2. `AmharicMappingIndex` — templateProperty -> ontologyProperty mappings
   already published on mappings.dbpedia.org's `Mapping am:*` pages.
3. `data/*.md` + `aliases.json` — the original hand-authored aliases, kept as
   a supplementary enrichment layer rather than the retrieval corpus itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag.ontology import AmharicMappingIndex, DbpediaOntologyCatalog

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


@dataclass(frozen=True, slots=True)
class RetrievalDocument:
    """One retrievable ontology property, enriched with any known aliases."""

    property: str  # OntologyProperty.local_name, e.g. "openingDate"
    curie: str
    uri: str
    label: str
    property_type: str
    domain: str | None
    amharic_aliases: tuple[str, ...] = ()
    english_aliases: tuple[str, ...] = ()

    def search_text(self) -> str:
        # Not a @property: this class has a field literally named `property`
        # (matching SearchResult.property elsewhere), and mypy resolves a
        # bare `property` inside a class body to that field, not the builtin
        # decorator, once it's been used as an annotation target.
        parts = [
            self.label,
            self.property,
            self.curie,
            *self.amharic_aliases,
            *self.english_aliases,
        ]
        return " | ".join(part for part in parts if part)


def _normalize(name: str) -> str:
    value = name.strip()
    if ":" in value:
        value = value.split(":", 1)[1]
    return value.casefold()


def _dedupe(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


@dataclass
class _LegacyEntry:
    amharic: list[str]
    english: list[str]
    domain: str | None = None


def _load_legacy_aliases(data_dir: Path) -> dict[str, _LegacyEntry]:
    """Amharic/English aliases keyed by ontology property local_name, from the
    legacy hand-authored data/*.md + aliases.json demo corpus."""

    from scripts.validate_corpus import parse_property_documents

    by_property: dict[str, _LegacyEntry] = {}

    aliases_path = data_dir / "aliases.json"
    if aliases_path.is_file():
        payload: Any = json.loads(aliases_path.read_text(encoding="utf-8"))
        for row in payload.get("aliases", []):
            if not isinstance(row, dict):
                continue
            property_name = row.get("ontology_property")
            if not isinstance(property_name, str):
                continue
            entry = by_property.setdefault(_normalize(property_name), _LegacyEntry([], []))
            amharic = row.get("amharic")
            if isinstance(amharic, str):
                entry.amharic.append(amharic)
            for alias in row.get("english_aliases") or []:
                if isinstance(alias, str):
                    entry.english.append(alias)
            row_class = row.get("class")
            if entry.domain is None and isinstance(row_class, str):
                entry.domain = row_class

    if data_dir.is_dir():
        for path in sorted(data_dir.glob("*.md")):
            for document in parse_property_documents(path):
                property_name = document.fields.get("propertyName")
                if not isinstance(property_name, str):
                    continue
                entry = by_property.setdefault(_normalize(property_name), _LegacyEntry([], []))
                raw_aliases = document.fields.get("amharic aliases", "")
                entry.amharic.extend(
                    item.strip() for item in raw_aliases.split(",") if item.strip()
                )
                if entry.domain is None:
                    entry.domain = document.class_name

    return by_property


def _ontology_to_template_aliases(mapping_index: AmharicMappingIndex) -> dict[str, list[str]]:
    """Invert AmharicMappingIndex (templateProperty -> ontologyProperty) so a
    given ontology property can look up any known Amharic template name."""

    by_ontology_property: dict[str, list[str]] = {}
    for mapping in mapping_index.all_mappings():
        key = _normalize(mapping.ontology_property)
        by_ontology_property.setdefault(key, []).append(mapping.template_property)
    return by_ontology_property


def build_corpus(
    *,
    ontology_catalog: DbpediaOntologyCatalog | None = None,
    mapping_index: AmharicMappingIndex | None = None,
    data_dir: Path | str = DEFAULT_DATA_DIR,
) -> list[RetrievalDocument]:
    """Build the merged retrieval corpus described in this module's docstring."""

    catalog = ontology_catalog or DbpediaOntologyCatalog.from_default_cache()
    mappings = mapping_index or AmharicMappingIndex.from_default_cache()
    legacy = _load_legacy_aliases(Path(data_dir))
    template_aliases = _ontology_to_template_aliases(mappings)

    documents: list[RetrievalDocument] = []
    for prop in catalog.properties:
        key = _normalize(prop.local_name)
        legacy_entry = legacy.get(key)
        amharic_aliases = list(template_aliases.get(key, []))
        english_aliases: list[str] = []
        domain = prop.domain

        if legacy_entry is not None:
            amharic_aliases.extend(legacy_entry.amharic)
            english_aliases.extend(legacy_entry.english)
            if domain is None:
                domain = legacy_entry.domain

        documents.append(
            RetrievalDocument(
                property=prop.local_name,
                curie=prop.curie,
                uri=prop.uri,
                label=prop.label,
                property_type=prop.property_type,
                domain=domain,
                amharic_aliases=_dedupe(amharic_aliases),
                english_aliases=_dedupe(english_aliases),
            )
        )

    return documents
