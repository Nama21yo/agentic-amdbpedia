from __future__ import annotations

from pathlib import Path

from rag.corpus import RetrievalDocument, build_corpus
from rag.ontology import AmharicMappingIndex, DbpediaOntologyCatalog


def test_build_corpus_has_one_document_per_ontology_property() -> None:
    catalog = DbpediaOntologyCatalog.from_default_cache()
    documents = build_corpus()

    assert len(documents) == len(catalog.properties)


def test_build_corpus_enriches_with_legacy_demo_aliases() -> None:
    documents = build_corpus()
    by_property = {doc.property: doc for doc in documents}

    icao = by_property["icaoLocationIdentifier"]
    assert "አይካኦ_ኮድ" in icao.amharic_aliases
    assert "ICAO" in icao.english_aliases


def test_build_corpus_enriches_with_published_amharic_mappings() -> None:
    documents = build_corpus()
    by_property = {doc.property: doc for doc in documents}

    # Mapping_am.xml maps templateProperty "አባት" -> ontologyProperty "father",
    # a real dbo: property not covered by the legacy data/*.md demo corpus at
    # all, so this alias can only have come from AmharicMappingIndex.
    father = by_property["father"]
    assert "አባት" in father.amharic_aliases


def test_build_corpus_falls_back_to_legacy_domain_when_ontology_has_none() -> None:
    documents = build_corpus()
    by_property = {doc.property: doc for doc in documents}

    height = by_property["height"]
    # height has no rdfs:domain in the real ontology, but the legacy demo
    # corpus tags it under Dam.
    assert height.domain == "Dam"


def test_build_corpus_keeps_real_ontology_domain_when_present() -> None:
    documents = build_corpus()
    by_property = {doc.property: doc for doc in documents}

    icao = by_property["icaoLocationIdentifier"]
    assert icao.domain == "Airport"


def test_search_text_includes_label_and_aliases() -> None:
    doc = RetrievalDocument(
        property="openingDate",
        curie="dbo:openingDate",
        uri="http://dbpedia.org/ontology/openingDate",
        label="opening date",
        property_type="DatatypeProperty",
        domain="Dam",
        amharic_aliases=("የመክፈቻ_ቀን",),
        english_aliases=("opening date",),
    )

    text = doc.search_text()

    assert "opening date" in text
    assert "openingDate" in text
    assert "dbo:openingDate" in text
    assert "የመክፈቻ_ቀን" in text


def test_build_corpus_accepts_injected_catalog_and_mapping_index(tmp_path: Path) -> None:
    empty_ontology = tmp_path / "empty_ontology.xml"
    empty_ontology.write_text(
        "<mediawiki><page><title>OntologyProperty:Fake</title>"
        "<revision><text>{{DatatypeProperty|labels={{label|en|fake}}}}</text></revision>"
        "</page></mediawiki>",
        encoding="utf-8",
    )
    catalog = DbpediaOntologyCatalog.from_ontology_xml(empty_ontology)
    mapping_index = AmharicMappingIndex.from_mapping_xml(tmp_path / "does-not-exist.xml")

    documents = build_corpus(
        ontology_catalog=catalog, mapping_index=mapping_index, data_dir=tmp_path
    )

    assert len(documents) == 1
    assert documents[0].property == "fake"
    assert documents[0].amharic_aliases == ()


def test_build_corpus_missing_data_dir_does_not_raise(tmp_path: Path) -> None:
    documents = build_corpus(data_dir=tmp_path / "does-not-exist")

    assert len(documents) > 0
