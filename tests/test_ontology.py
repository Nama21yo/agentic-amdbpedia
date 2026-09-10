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


def test_catalog_extracts_declared_domain() -> None:
    catalog = DbpediaOntologyCatalog.from_default_cache()
    icao = catalog.find("icaoLocationIdentifier")
    assert icao is not None
    assert icao.domain == "Airport"


def test_catalog_domain_is_none_when_undeclared_or_owl_thing() -> None:
    catalog = DbpediaOntologyCatalog.from_default_cache()
    height = catalog.find("height")
    assert height is not None
    assert height.domain is None


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


def test_mapping_index_is_known_template_recognizes_a_real_page_with_no_marker_word() -> None:
    # "የቦታ ስም" (Place) contains none of _is_infobox_like's marker words --
    # this is the second, ground-truth recognition signal that rescues it.
    index = AmharicMappingIndex.from_default_cache()
    assert index.is_known_template("የቦታ ስም") is True
    assert index.is_known_template("ይህ_ምንም_ግንኙነት_የሌለው_ስም") is False


def test_mapping_index_scoped_lookup_finds_a_real_per_template_mapping() -> None:
    index = AmharicMappingIndex.from_default_cache()
    mapping = index.is_already_mapped_on_template("የቦታ ስም", "ከፍታ")
    assert mapping is not None
    assert mapping.ontology_property == "elevation"


def test_mapping_index_domain_class_for_template_reads_maptoclass() -> None:
    index = AmharicMappingIndex.from_default_cache()
    assert index.domain_class_for_template("የሀገር መረጃ") == "Country"
    assert index.domain_class_for_template("መረጃሳጥን ሰው") == "Person"
    # whitespace/underscore/case normalized the same as everywhere else
    assert index.domain_class_for_template("የሀገር_መረጃ") == "Country"
    # a template this corpus has never mapped -> no class to offer
    assert index.domain_class_for_template("የሳይንቲስት መረጃ") is None


def test_mapping_index_scoped_lookup_does_not_leak_across_templates() -> None:
    # Regression: confirmed live that Place's "ከፍታ -> elevation" mapping
    # was making Dam's own, genuinely unmapped "ከፍታ" field look
    # already-published via the old global lookup() -- scoped lookup must
    # not repeat that mistake. Dam has no Mapping am:* page in this corpus
    # at all, so this must come back empty regardless of what other
    # templates map the same Amharic word to.
    index = AmharicMappingIndex.from_default_cache()
    assert index.is_already_mapped_on_template("መረጃሳጥን ግድብ", "ከፍታ") is None
    # lookup() (the old, unscoped API) still finds it globally -- unchanged
    # behavior for existing callers, which is exactly what makes the scoped
    # method necessary for mcp_server.pipeline._extract_node's filter.
    assert index.lookup("ከፍታ") is not None
