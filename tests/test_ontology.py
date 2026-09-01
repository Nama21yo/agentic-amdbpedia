from __future__ import annotations

from pathlib import Path

import pytest

from errors import RetrievalUnavailableError
from rag.ontology import (
    DEFAULT_MAPPING_AM_XML,
    DEFAULT_ONTOLOGY_XML,
    AmharicMappingIndex,
    DbpediaOntologyCatalog,
)


def test_default_cache_files_exist() -> None:
    assert DEFAULT_ONTOLOGY_XML.is_file()
    assert DEFAULT_MAPPING_AM_XML.is_file()


def test_catalog_loads_real_property_count() -> None:
    catalog = DbpediaOntologyCatalog.from_default_cache()
    # The cached export has 2,942 OntologyProperty: pages as of the 10.1 seed copy.
    assert len(catalog.properties) > 2500


def test_catalog_finds_length_as_datatype_property() -> None:
    catalog = DbpediaOntologyCatalog.from_default_cache()
    prop = catalog.find("length")
    assert prop is not None
    assert prop.curie == "dbo:length"
    assert prop.uri == "http://dbpedia.org/ontology/length"
    assert prop.property_type == "DatatypeProperty"


def test_catalog_finds_an_object_property() -> None:
    catalog = DbpediaOntologyCatalog.from_default_cache()
    prop = catalog.find("birthPlace")
    assert prop is not None
    assert prop.property_type == "ObjectProperty"


def test_catalog_lookup_is_case_and_prefix_insensitive() -> None:
    catalog = DbpediaOntologyCatalog.from_default_cache()
    assert catalog.find("Length") is catalog.find("dbo:length")
    assert catalog.find("http://dbpedia.org/ontology/length") is catalog.find("length")


def test_catalog_raises_client_safe_error_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(RetrievalUnavailableError):
        DbpediaOntologyCatalog.from_ontology_xml(tmp_path / "does-not-exist.xml")


def test_mapping_index_loads_existing_amharic_mappings() -> None:
    index = AmharicMappingIndex.from_default_cache()
    # The cached export currently has 4 Mapping am:* pages (Person, Country, ...).
    assert len(index) >= 4


def test_mapping_index_lookup_normalizes_whitespace_and_case() -> None:
    index = AmharicMappingIndex.from_default_cache()
    mapping = index.lookup("ስም")
    assert mapping is not None
    assert mapping.ontology_property == "foaf:name"


def test_mapping_index_missing_file_returns_empty_not_error(tmp_path: Path) -> None:
    index = AmharicMappingIndex.from_mapping_xml(tmp_path / "does-not-exist.xml")
    assert len(index) == 0
